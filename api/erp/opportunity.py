"""ERP 1-bosqich: tenderni "ishga olish" va opportunity pipeline.

Chegara:
  - public.* faqat O'QILADI va faqat BITTA joyda — TENDER_SNAPSHOT_SQL.
    ERP alohida servisga ajratilsa shu bitta funksiya HTTP chaqiruviga
    almashadi, boshqa hech qayer tender bazasiga tegmaydi.
  - public.* ga hech qachon YOZILMAYDI.
  - Modul FastAPI'dan mustaqil: HTTPException import QILINMAYDI, xato
    ErpError ko'rinishida chiqadi va main.py uni HTTP kodiga aylantiradi
    (pricing.py bilan bir xil uslub) — modul bazasiz ham sinaladi.
"""
from __future__ import annotations

from typing import Optional

from api import db

# Statuslar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_1.sql).
# Ikkala joyda turadi; sinov ularni solishtiradi.
STATUSES = [
    ("new",            "Yangi"),
    ("reviewing",      "Ko'rib chiqilmoqda"),
    ("sent_to_client", "Mijozga yuborildi"),
    ("confirmed",      "Qatnashish tasdiqlandi"),
    ("preparing",      "Taklif tayyorlanmoqda"),
    ("submitted",      "Topshirildi"),
    ("won",            "Yutildi"),
    ("lost",           "Yutqazildi"),
    ("rejected",       "Rad etildi"),
]
STATUS_LABEL = dict(STATUSES)
FINAL = {"won", "lost", "rejected"}
PRIORITIES = {"low": "Past", "medium": "O'rta", "high": "Yuqori"}

# Yutqazish sabablari — bazadagi CHECK bilan BIR XIL ro'yxat
# (schema_patch_erp_3.sql). Statusga tegishli bo'lgani uchun shu modulda:
# ustun ham `erp.opportunity` da yashaydi.
LOST_REASONS = [
    ("price",           "Narx yuqori bo'ldi"),
    ("deadline",        "Muddatga ulgurmadik"),
    ("documents",       "Hujjatlar yetishmadi"),
    ("requirements",    "Texnik talablarga mos kelmadik"),
    ("capacity",        "Resurs/quvvat yetmadi"),
    ("client_declined", "Mijoz qatnashishdan voz kechdi"),
    ("other",           "Boshqa sabab"),
]
LOST_REASON_LABEL = dict(LOST_REASONS)

# MANBA HAVOLASI — BAZADAN, kodda lug'at emas.
#
# Ilgari bu yerda `SOURCE_URL` lug'ati turardi: platforma -> URL
# shabloni. U tender-ai dagi `v_tender_manba` view i bilan IKKINCHI
# NUSXA edi va ular ajralib ketishi mumkin edi (yangi platforma
# qo'shilsa yoki manba saytining manzili o'zgarsa — bir tomonda
# yangilanadi, ikkinchisida yo'q). `erp_rollar.md` §10: "SOURCE_URL
# lug'ati o'chadi, manba_url bazadan".
#
# ZAXIRA yo'q: view bo'lmasa havola BERILMAYDI. Noto'g'ri havola
# "bor, lekin ochilmaydi" degan holat yaratardi — havola yo'qligi
# ochiqroq.
MANBA_SQL = ("SELECT ommaviy_url FROM v_tender_manba "
             "WHERE ichki_id = %(id)s")


class ErpError(Exception):
    """Foydalanuvchi tuzata oladigan xato -> main.py da 400/404/409/503."""

    def __init__(self, msg, code=400, **extra):
        super().__init__(msg)
        self.code = code
        self.extra = extra


# ---------------------------------------------------------------------------
# Sxema tayyorligi
# ---------------------------------------------------------------------------
# Patch qo'llanmagan bazada ilova YIQILMAYDI (notify_lang.md uslubi):
# /erp/meta "schema_ready": false qaytaradi va interfeys buni ochiq aytadi,
# qolgan endpointlar 503. Bir marta rost bo'lgach keshlanadi — jadval
# ish vaqtida yo'qolmaydi, har so'rovda information_schema so'rash ortiqcha.
_SCHEMA_READY = False

SCHEMA_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'opportunity'
"""


def schema_ready() -> bool:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return True
    _SCHEMA_READY = bool(db.query_one(SCHEMA_CHECK_SQL))
    return _SCHEMA_READY


def _need_schema() -> None:
    if not schema_ready():
        raise ErpError("ERP jadvallari yaratilmagan: schema_patch_erp_1.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
# public.* ga YAGONA murojaat. Ustun nomlari api/queries.py dagi _TENDER_SELECT
# bilan bir xil manbadan: buyurtmachi = company_name, deadline = close_at
# (loyihada DEFAULT_SORT ham shu), hudud = dim_area JOIN orqali.
# Manbadagi HOZIRGI status — snapshotga kirmaydi (u muzlatilgan), lekin
# "tender yopilganmi?" degan savol uchun kerak. Alohida so'rov: snapshot
# so'rovi o'zgarmasin.
TENDER_STATUS_SQL = """
-- name_uz ko'p statusda bo'sh (dim_status to'liq tarjima qilinmagan) —
-- shuning uchun ruscha nomga, u ham bo'lmasa kodga tushamiz.
SELECT t.status, COALESCE(s.name_uz, s.name_ru, t.status) AS status_name,
       s.is_terminal
FROM tender t
LEFT JOIN dim_status s ON s.status_code = t.status AND s.domain = 'tender'
WHERE t.id = %(id)s
"""

TENDER_SNAPSHOT_SQL = """
SELECT t.id, t.source_id, t.source_platform,
       t.name                         AS title,
       t.company_name                 AS customer_name,
       t.totalcost                    AS start_price,
       t.currency,
       t.close_at                     AS deadline_at,
       COALESCE(a.name_uz, a.name_ru) AS region_name
FROM tender t
LEFT JOIN dim_area a ON a.area_id = t.area_leaf_id
WHERE t.id = %(id)s
"""

# f-string faqat USTUN RO'YXATI uchun; qiymatlar har doim %(name)s parametri.
_OPP_COLS = """
o.id, o.tender_id, o.source_platform, o.tender_ref, o.customer_name, o.title,
o.start_price, o.currency, o.deadline_at, o.region_name, o.source_url,
o.broker_id, b.full_name AS broker_name,
o.client_id, c.name AS client_name,
o.priority, o.win_probability, o.note, o.next_task, o.next_task_at,
o.status, o.status_changed_at, o.closed_at, o.lost_reason,
o.created_by, o.created_at, o.updated_at
"""
_OPP_FROM = """
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
"""

# Filtrlar ixtiyoriy: shartli qator yig'ish o'rniga "%(x)s IS NULL OR ..." —
# bitta so'rov, bitta reja (queries.py dagi uslub).
OPP_LIST_SQL = f"""
SELECT {_OPP_COLS} {_OPP_FROM}
WHERE (%(status)s::text IS NULL OR o.status = %(status)s)
  AND (%(broker_id)s::int IS NULL OR o.broker_id = %(broker_id)s)
  -- "TAQSIMLANMAGAN": Tender-AI yo'naltirishi hodimni topa olmasa
  -- karta baribir ochiladi (`api/erp/topshiriq.py`) va u YO'QOLMASLIGI
  -- kerak. Menejer aynan shu ro'yxatni ochadi.
  AND (%(unassigned)s::bool IS NOT TRUE OR o.broker_id IS NULL)
  AND (%(client_id)s::int IS NULL OR o.client_id = %(client_id)s)
  AND (%(q)s::text IS NULL OR o.title ILIKE '%%' || %(q)s || '%%'
                           OR o.customer_name ILIKE '%%' || %(q)s || '%%'
                           OR o.tender_ref ILIKE '%%' || %(q)s || '%%')
  AND (%(open_only)s::bool IS NOT TRUE OR o.status NOT IN ('won','lost','rejected'))
ORDER BY o.deadline_at NULLS LAST, o.id
"""
OPP_GET_SQL = f"SELECT {_OPP_COLS} {_OPP_FROM} WHERE o.id = %(id)s"
OPP_BY_TENDER_SQL = (f"SELECT {_OPP_COLS} {_OPP_FROM} "
                     "WHERE o.tender_id = %(tender_id)s ORDER BY o.id")

OPP_INSERT_SQL = """
INSERT INTO erp.opportunity (
    tender_id, source_platform, tender_ref, customer_name, title, start_price,
    currency, deadline_at, region_name, source_url,
    broker_id, client_id, priority, win_probability, note, next_task, next_task_at,
    created_by)
VALUES (%(tender_id)s, %(source_platform)s, %(tender_ref)s, %(customer_name)s,
        %(title)s, %(start_price)s, %(currency)s, %(deadline_at)s, %(region_name)s,
        %(source_url)s,
        %(broker_id)s, %(client_id)s, %(priority)s, %(win_probability)s, %(note)s,
        %(next_task)s, %(next_task_at)s, %(created_by)s)
RETURNING id
"""

# Faqat XODIM maydonlari. Snapshot va status bu yerdan O'ZGARMAYDI: snapshot
# ataylab muzlatilgan, status esa o'z endpointi orqali (tarix yozilishi uchun).
OPP_UPDATE_SQL = """
UPDATE erp.opportunity SET
    broker_id=%(broker_id)s, client_id=%(client_id)s, priority=%(priority)s,
    win_probability=%(win_probability)s, note=%(note)s,
    next_task=%(next_task)s, next_task_at=%(next_task_at)s, updated_at=now()
WHERE id = %(id)s
RETURNING id
"""

OPP_STATUS_SQL = """
UPDATE erp.opportunity SET
    status=%(status)s, status_changed_at=now(), updated_at=now(),
    closed_at = CASE WHEN %(status)s IN ('won','lost','rejected') THEN now() ELSE NULL END,
    -- Sabab faqat 'lost' ga tegishli: boshqa statusga o'tilganda tozalanadi,
    -- aks holda qayta ochilgan kartada eski sabab qolib ketardi.
    lost_reason = CASE WHEN %(status)s = 'lost' THEN %(lost_reason)s ELSE NULL END
WHERE id = %(id)s
RETURNING id, status
"""

# Faqat sababni to'g'rilash (status o'zgarmaydi -> tarixga yozilmaydi).
OPP_REASON_SQL = """
UPDATE erp.opportunity SET lost_reason=%(lost_reason)s, updated_at=now()
WHERE id = %(id)s
RETURNING id
"""

HISTORY_INSERT_SQL = """
INSERT INTO erp.opportunity_history (opportunity_id, from_status, to_status, changed_by, note)
VALUES (%(opportunity_id)s, %(from_status)s, %(to_status)s, %(changed_by)s, %(note)s)
RETURNING id
"""
HISTORY_LIST_SQL = """
SELECT id, from_status, to_status, changed_by, note, changed_at
FROM erp.opportunity_history WHERE opportunity_id = %(id)s ORDER BY changed_at, id
"""

BROKERS_SQL = ("SELECT id, full_name, email, phone, active FROM erp.broker "
               "ORDER BY active DESC, full_name")
BROKER_INSERT_SQL = ("INSERT INTO erp.broker (full_name, email, phone) "
                     "VALUES (%(full_name)s, %(email)s, %(phone)s) "
                     "RETURNING id, full_name, email, phone, active")
CLIENTS_SQL = "SELECT id, name, active FROM erp.client_company ORDER BY active DESC, name"
CLIENT_INSERT_SQL = ("INSERT INTO erp.client_company (name) VALUES (%(name)s) "
                     "RETURNING id, name, active")


# ---------------------------------------------------------------------------
# Shakllantirish (sof funksiyalar — bazasiz sinaladi)
# ---------------------------------------------------------------------------
def _iso(v):
    """TIMESTAMPTZ/DATE -> ISO satr. JSON date turini bilmaydi."""
    return v.isoformat() if v is not None else None


def _num(v):
    """NUMERIC -> Decimal keladi, JSON uni bilmaydi (pricing.py dagi _pnum)."""
    return None if v is None else float(v)


def shape(r: dict) -> dict:
    """Baza qatori -> API javobi. Snapshot alohida "tender" obyektida:
    u tenderning MUZLATILGAN nusxasi, jonli tender emas — chalkashmasin."""
    return {
        "id": r["id"], "tender_id": r["tender_id"],
        "tender": {
            "source_platform": r["source_platform"], "tender_ref": r["tender_ref"],
            "customer_name": r["customer_name"], "title": r["title"],
            "start_price": _num(r["start_price"]), "currency": r["currency"],
            "deadline_at": _iso(r["deadline_at"]), "region_name": r["region_name"],
            "source_url": r["source_url"],
        },
        "broker": ({"id": r["broker_id"], "name": r["broker_name"]} if r["broker_id"] else None),
        "client": ({"id": r["client_id"], "name": r["client_name"]} if r["client_id"] else None),
        "priority": r["priority"], "priority_label": PRIORITIES.get(r["priority"]),
        "win_probability": r["win_probability"],
        "note": r["note"], "next_task": r["next_task"], "next_task_at": _iso(r["next_task_at"]),
        "status": r["status"], "status_label": STATUS_LABEL.get(r["status"]),
        "is_final": r["status"] in FINAL,
        "status_changed_at": _iso(r["status_changed_at"]), "closed_at": _iso(r["closed_at"]),
        "lost_reason": r.get("lost_reason"),
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
        "updated_at": _iso(r["updated_at"]),
    }


def _check_fields(data: dict) -> None:
    """Xodim maydonlarining qiymatlari. Bazada ham CHECK bor, lekin u yerga
    yetib borsa 500 chiqadi — foydalanuvchi tuzata oladigan xato 400 bo'lishi
    kerak, shuning uchun kodda oldindan tekshiriladi."""
    if data.get("priority") not in PRIORITIES:
        raise ErpError("Ustuvorlik: low | medium | high.")
    wp = data.get("win_probability")
    if wp is not None and not (0 <= int(wp) <= 100):
        raise ErpError("Yutish ehtimoli 0 dan 100 gacha bo'lishi kerak.")


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def _manba_url(tender_id: int) -> Optional[str]:
    """Manbadagi e'lon havolasi — `v_tender_manba` dan.

    View yo'q bo'lsa (eski o'rnatma) `None`: ERP yiqilmaydi, havola
    ko'rsatilmaydi, xolos."""
    try:
        r = db.query_one(MANBA_SQL, {"id": tender_id})
    except Exception:                           # noqa: BLE001
        return None
    return (r or {}).get("ommaviy_url")


def _tender_snapshot(tender_id: int) -> dict:
    """Tenderdan 9 maydon. ERP ajratilsa — SHU BITTA funksiya HTTP chaqiruviga
    almashadi."""
    t = db.query_one(TENDER_SNAPSHOT_SQL, {"id": tender_id})
    if not t:
        raise ErpError("Tender topilmadi.", 404)
    # Manbadagi asl raqam: KO'RSATILADIGAN raqam shundan (bizning
    # `t.id` global va manba saytida mavjud emas).
    ref = t["source_id"] or t["id"]
    return {
        "tender_id": t["id"],
        "source_platform": t["source_platform"],
        "tender_ref": str(ref),
        "customer_name": t["customer_name"],
        "title": t["title"],
        "start_price": t["start_price"],
        # tender.currency ustuni CHAR(n) — qiymat bo'shliq bilan to'ldirilib keladi.
        "currency": (t["currency"] or "").strip() or None,
        "deadline_at": t["deadline_at"],
        "region_name": t["region_name"],
        "source_url": _manba_url(tender_id),
    }


# ---------------------------------------------------------------------------
# Snapshot va jonli tender farqi
# ---------------------------------------------------------------------------
# Snapshot ATAYLAB muzlatilgan (erp_arxitektura.md 2.2) va bu yerda ham
# O'ZGARTIRILMAYDI. Lekin "tenderda nimadir o'zgardi" degani xodim uchun
# muhim xabar: muddat ko'chgan bo'lsa reja buziladi, narx qayta e'lon
# qilingan bo'lsa hisob eskiradi. Shuning uchun farq KO'RSATILADI, lekin
# avtomatik ko'chirilmaydi — qaysi qiymat to'g'ri ekanini odam hal qiladi.
DIFF_FIELDS = [
    ("title",           "Nomi"),
    ("customer_name",   "Buyurtmachi"),
    ("start_price",     "Boshlang'ich narx"),
    ("currency",        "Valyuta"),
    ("deadline_at",     "Deadline"),
    ("region_name",     "Hudud"),
    ("tender_ref",      "Manba raqami"),
    ("source_platform", "Manba"),
    ("source_url",      "Manba havolasi"),
]


def _cmp_val(v):
    """Taqqoslash uchun bir xil ko'rinishga keltiradi: NUMERIC -> float,
    sana -> ISO satr, bo'sh satr -> None (ular bir xil ma'noni bildiradi)."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip() or None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def diff_with_tender(opp_id: int) -> dict:
    """Kartadagi snapshotni JONLI tender bilan solishtiradi.

    Hech narsa yozilmaydi. Tender manbadan o'chirilgan bo'lsa (ETL uni
    o'chirishi mumkin) — xato emas, `exists: false`: karta o'z joyida
    qoladi, interfeys esa buni ochiq aytadi.
    """
    _need_schema()
    r = db.query_one(OPP_GET_SQL, {"id": opp_id})
    if not r:
        raise ErpError("Karta topilmadi.", 404)

    try:
        live = _tender_snapshot(r["tender_id"])
    except ErpError as e:
        if e.code == 404:
            return {"opportunity_id": opp_id, "tender_id": r["tender_id"],
                    "exists": False, "changed": []}
        raise

    # Manbadagi status: yakuniy bo'lsa-yu karta ochiq bo'lsa — interfeys
    # "yakunlash kerakmi?" deb TAKLIF qiladi. AVTOMATIK o'zgartirmaydi:
    # manba g'olibni ochiq bermaydi (bazada bunday ustun yo'q), shuning
    # uchun "yutdik" yoki "yutqazdik" ni tizim bila olmaydi.
    st = db.query_one(TENDER_STATUS_SQL, {"id": r["tender_id"]}) or {}
    source = {"status": st.get("status"), "status_name": st.get("status_name"),
              "closed": bool(st.get("is_terminal"))}
    suggest_close = bool(source["closed"] and r["status"] not in FINAL)

    changed = []
    for field, label in DIFF_FIELDS:
        was, now = _cmp_val(r[field]), _cmp_val(live[field])
        if was == now:
            continue
        changed.append({"field": field, "label": label,
                        "was": _iso(r[field]) if hasattr(r[field], "isoformat")
                        else _num(r[field]) if field == "start_price" else r[field],
                        "now": _iso(live[field]) if hasattr(live[field], "isoformat")
                        else _num(live[field]) if field == "start_price" else live[field]})
    return {"opportunity_id": opp_id, "tender_id": r["tender_id"],
            "exists": True, "changed": changed,
            "source": source, "suggest_close": suggest_close}


def list_(status=None, broker_id=None, client_id=None, q=None,
          open_only=False, unassigned=False):
    """`unassigned` — mas'uli yo'q kartalar (Tender-AI yo'naltirishi
    hodimni topa olmagan yoki karta hali taqsimlanmagan)."""
    _need_schema()
    rows = db.query(OPP_LIST_SQL, {"status": status, "broker_id": broker_id,
                                   "client_id": client_id, "q": q or None,
                                   "open_only": open_only,
                                   "unassigned": bool(unassigned)})
    return [shape(r) for r in rows]


def get(opp_id: int) -> dict:
    _need_schema()
    r = db.query_one(OPP_GET_SQL, {"id": opp_id})
    if not r:
        raise ErpError("Karta topilmadi.", 404)
    out = shape(r)
    out["history"] = [
        {"id": h["id"], "from_status": h["from_status"], "to_status": h["to_status"],
         "from_label": STATUS_LABEL.get(h["from_status"]),
         "to_label": STATUS_LABEL.get(h["to_status"]), "changed_by": h["changed_by"],
         "note": h["note"], "changed_at": _iso(h["changed_at"])}
        for h in db.query(HISTORY_LIST_SQL, {"id": opp_id})]
    return out


def by_tender(tender_id: int) -> list:
    """TenderDrawer uchun: shu tender ishga olinganmi, qaysi mijozlar uchun."""
    _need_schema()
    return [shape(r) for r in db.query(OPP_BY_TENDER_SQL, {"tender_id": tender_id})]


def take(tender_id: int, data: dict) -> dict:
    """"Ishga olish": tender ro'yxatdan ichki kartaga aylanadi.
    data: broker_id, client_id, priority, win_probability, note, next_task,
    next_task_at, created_by."""
    _need_schema()
    _check_fields(data)
    # Takror: bir tender + bir mijoz. Bazadagi UNIQUE ham ushlaydi, lekin u
    # 500 berardi — bu yerda 409 va MAVJUD karta id si qaytadi (frontend
    # o'sha kartaga havola quradi).
    for ex in by_tender(tender_id):
        if (ex["client"] or {}).get("id") == data.get("client_id"):
            raise ErpError("Bu tender shu mijoz uchun allaqachon ishga olingan.",
                           409, opportunity_id=ex["id"])
    snap = _tender_snapshot(tender_id)
    params = {**snap, **{k: data.get(k) for k in (
        "broker_id", "client_id", "priority", "win_probability",
        "note", "next_task", "next_task_at", "created_by")}}
    row = db.execute_returning(OPP_INSERT_SQL, params)
    # db.py har chaqiruvni o'zi commit qiladi (loyiha kelishuvi; transaction()
    # yordamchisi yo'q). Ikkinchi yozuv yiqilsa karta tarixsiz qoladi —
    # ma'lumot yo'qolmaydi, 1-bosqichda shu qabul qilingan.
    db.execute_returning(HISTORY_INSERT_SQL, {
        "opportunity_id": row["id"], "from_status": None, "to_status": "new",
        "changed_by": data.get("created_by"), "note": "Ishga olindi"})
    return get(row["id"])


def update(opp_id: int, data: dict) -> dict:
    """Faqat xodim maydonlari. Snapshot va status tegilmaydi."""
    _need_schema()
    _check_fields(data)
    # MAS'UL O'ZGARDIMI — xabar uchun kerak (pastga qarang).
    oldingi = db.query_one("SELECT broker_id, title FROM erp.opportunity "
                           "WHERE id = %(id)s", {"id": opp_id})
    row = db.execute_returning(OPP_UPDATE_SQL, {
        **{k: data.get(k) for k in ("broker_id", "client_id", "priority",
                                    "win_probability", "note", "next_task",
                                    "next_task_at")},
        "id": opp_id})
    if not row:
        raise ErpError("Karta topilmadi.", 404)
    # KARTA O'TKAZILDI — yangi mas'ulga xabar. Import SHU YERDA:
    # modul darajasida qilinsa `xabar` -> `opportunity` aylanma
    # bog'lanish xavfi paydo bo'lardi (`stock` bilan bir xil naqsh).
    yangi = data.get("broker_id")
    if oldingi and yangi and yangi != oldingi.get("broker_id"):
        from api.erp import xabar as _xabar
        _xabar.brokerga(yangi, "otkazildi",
                        f"Karta sizga o'tkazildi: "
                        f"{oldingi.get('title') or f'#{opp_id}'}.", opp_id)
    return get(opp_id)


def taqsimlash_sorovi(opp_id: int, izoh: Optional[str],
                      kim: Optional[str]) -> dict:
    """"Bu ish menga to'g'ri kelmadi" — MENEJERGA so'rov.

    Broker kartani o'zi boshqa hodimga o'tkaza olmaydi (huquqlar
    matritsasi): aks holda ish jimgina bir-biriga surilardi va
    "kim mas'ul" degan savol javobsiz qolardi.

    So'rov TARIXGA yoziladi va menejerga xabar boradi. Ya'ni u
    og'zaki emas — keyin "aytgan edim" degan bahs bo'lmaydi.
    """
    _need_schema()
    cur = db.query_one("SELECT id, status, title, broker_id "
                       "FROM erp.opportunity WHERE id = %(id)s", {"id": opp_id})
    if not cur:
        raise ErpError("Karta topilmadi.", 404)
    matn = (izoh or "").strip()
    if not matn:
        raise ErpError("Sabab majburiy: menejer nima qilishini bilishi kerak.")
    db.execute_returning(HISTORY_INSERT_SQL, {
        "opportunity_id": opp_id, "from_status": cur["status"],
        "to_status": cur["status"], "changed_by": kim,
        "note": f"Qayta taqsimlash so'raldi: {matn[:500]}"})
    from api.erp import xabar as _xabar
    nom = cur.get("title") or f"#{opp_id}"
    n = _xabar.menejerlarga(
        "otkazildi", f"Qayta taqsimlash so'rovi: {nom}. "
                     f"So'radi: {kim or 'noma`lum'}. Sabab: {matn[:300]}",
        opp_id)
    return {"ok": True, "xabar_ketdi": n, "opportunity_id": opp_id}


def set_status(opp_id: int, status: str, changed_by: Optional[str],
               note: Optional[str], lost_reason: Optional[str] = None) -> dict:
    _need_schema()
    if status not in STATUS_LABEL:
        raise ErpError("Noma'lum status.")
    # Sababni KODDA tekshiramiz: bazadagi CHECK ham bor, lekin u yerga
    # yetib borsa 500 chiqadi — foydalanuvchi tuzata oladigan xato esa 400.
    if lost_reason is not None and lost_reason not in LOST_REASON_LABEL:
        raise ErpError("Noma'lum yutqazish sababi.")
    cur = db.query_one(OPP_GET_SQL, {"id": opp_id})
    if not cur:
        raise ErpError("Karta topilmadi.", 404)
    if cur["status"] == status:
        # Status o'zgarmagan, lekin SABAB o'zgargan bo'lishi mumkin (yopilgan
        # kartada sababni to'g'rilash). Uni yozamiz, tarixga esa yozmaymiz:
        # bosqich o'tishi bo'lmadi.
        if status == "lost" and lost_reason != cur.get("lost_reason"):
            db.execute_returning(OPP_REASON_SQL,
                                 {"id": opp_id, "lost_reason": lost_reason})
        return get(opp_id)
    # Yakuniydan qaytish — faqat izoh bilan: "nega qayta ochildi" tarixda qolsin.
    if cur["status"] in FINAL and status not in FINAL and not (note or "").strip():
        raise ErpError("Yakuniy statusdan qaytarish uchun izoh majburiy.")
    db.execute_returning(OPP_STATUS_SQL, {"id": opp_id, "status": status,
                                          "lost_reason": lost_reason})
    db.execute_returning(HISTORY_INSERT_SQL, {
        "opportunity_id": opp_id, "from_status": cur["status"], "to_status": status,
        "changed_by": changed_by, "note": note})

    # OMBOR REZERVI statusga bog'langan: yutilganda sarflanadi,
    # yutqazilganda bo'shaydi (`api/erp/stock.py` -> on_status_change).
    # Import SHU YERDA — modul darajasida qilinsa ikki modul bir-birini
    # aylanma import qilardi (`stock` allaqachon `opportunity` dan
    # `ErpError` va `FINAL` ni oladi).
    from api.erp import stock as _stock
    stock_result = _stock.on_status_change(opp_id, cur["status"], status,
                                           changed_by)

    out = get(opp_id)
    # Nima bo'lganini JIM QOLDIRMAYMIZ: interfeys "3 ta rezerv sarflandi"
    # deb ko'rsatadi, aks holda ombor o'zgargani sezilmay qolardi.
    if any(stock_result.values()):
        out["stock"] = stock_result
    return out


# --- Lug'atlar: broker va mijoz (1-bosqichda oddiy ro'yxat) -----------------
def brokers():
    _need_schema()
    return db.query(BROKERS_SQL)


def add_broker(full_name: str, email=None, phone=None):
    _need_schema()
    if not (full_name or "").strip():
        raise ErpError("Ism bo'sh.")
    return db.execute_returning(BROKER_INSERT_SQL, {
        "full_name": full_name.strip(), "email": email, "phone": phone})


def clients():
    _need_schema()
    return db.query(CLIENTS_SQL)


def add_client(name: str):
    _need_schema()
    if not (name or "").strip():
        raise ErpError("Nom bo'sh.")
    return db.execute_returning(CLIENT_INSERT_SQL, {"name": name.strip()})
