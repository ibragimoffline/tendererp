"""ERP 3-bosqich: karta vazifalari, "mening ishlarim" va eslatma tanlovi.

Chegara:
  - Faqat erp.* jadvallari. public.* ga murojaat yo'q.
  - Xabar YUBORMAYDI: bu modul faqat "kimga nima eslatish kerak" degan
    ro'yxatni tuzadi. Yuborish `api/erp/remind.py` da, transport esa
    tender-ai'da (bot tokeni va SMTP rekvizitlari o'sha yerda qoladi).
  - opportunity.py ni import qiladi (ErpError, _need_schema, _iso) — teskari
    yo'nalish YO'Q, aks holda halqa hosil bo'lardi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import (PRIORITIES, ErpError, _iso, _need_schema,
                                 _num)

TASK_FIELDS = ("title", "assignee_broker_id", "due_at", "note", "priority")

#: HOLATLAR. `done` ustuni endi shu maydonning KO'ZGUSI (trigger
#: `erp.task_done_mirror`, `schema_patch_erp_28.sql`).
#:
#: KECHIKKAN HOLAT YO'Q va bu ongli qaror: u `due_at` dan HISOBLANADI
#: (`shape()` -> `overdue`). Saqlansa, ikkinchi haqiqat manbai paydo
#: bo'lardi va uni har kecha yangilab turadigan skript kerak bo'lardi —
#: skript bir kun yurmasa, ekran "kechikmagan" deb yolg'on gapirardi.
STATUSLAR = {
    "yangi": "Yangi",
    "bajarilmoqda": "Bajarilmoqda",
    "bajarildi": "Bajarildi",
    "bekor": "Bekor qilindi",
}
#: Ochiq deb hisoblanadiganlar — hisoblagich va ro'yxatlar shu bo'yicha.
OCHIQ = ("yangi", "bajarilmoqda")

#: USTUVORLIK — kartadagi bilan BIR XIL ro'yxat (`opportunity.PRIORITIES`:
#: low/medium/high). Ikkinchi shkala kiritilsa ekranda "O'rta" va
#: "Normal" yonma-yon turardi va ular bir xil narsani anglatardi.


# ---------------------------------------------------------------------------
# Sxema tayyorligi (3-bosqich patchi alohida qo'llanadi)
# ---------------------------------------------------------------------------
_SCHEMA3_READY = False

SCHEMA3_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'opportunity_task'
"""


def schema_ready() -> bool:
    global _SCHEMA3_READY
    if _SCHEMA3_READY:
        return True
    _SCHEMA3_READY = bool(db.query_one(SCHEMA3_CHECK_SQL))
    return _SCHEMA3_READY


def _need_schema3() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Vazifalar jadvali yo'q: schema_patch_erp_3.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_TASK_COLS = """
t.id, t.opportunity_id, t.title, t.assignee_broker_id, b.full_name AS assignee_name,
t.due_at, t.done, t.done_at, t.note, t.reminded_at, t.created_by, t.created_at,
t.status, t.priority, t.updated_at, t.cancelled_at, t.created_by_user_id
"""
_TASK_FROM = """
FROM erp.opportunity_task t
LEFT JOIN erp.broker b ON b.id = t.assignee_broker_id
"""

# Bajarilmaganlar yuqorida, muddat bo'yicha; muddatsizlar OXIRIDA — "sana yo'q"
# "juda uzoq" degani emas.
TASKS_SQL = f"""
SELECT {_TASK_COLS} {_TASK_FROM}
WHERE t.opportunity_id = %(id)s
ORDER BY t.done, t.due_at NULLS LAST, t.id
"""
TASK_GET_SQL = f"SELECT {_TASK_COLS} {_TASK_FROM} WHERE t.id = %(id)s"

# Bitta vazifa + KARTA KONTEKSTI. Ro'yxat so'rovini satr almashtirish
# bilan qayta yasash EMAS (`chat.BITTA_SQL` dagi saboq): so'rov matni
# ozgina o'zgarsa ikkinchisi JIMGINA buzilardi.
BITTA_SQL = f"""
SELECT {_TASK_COLS},
       o.title AS opp_title, o.status AS opp_status, o.deadline_at,
       o.tender_id, o.start_price, o.currency,
       c.name AS client_name, ob.full_name AS opp_broker_name
{_TASK_FROM}
LEFT JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE t.id = %(id)s
"""

TASK_INSERT_SQL = """
INSERT INTO erp.opportunity_task
    (opportunity_id, title, assignee_broker_id, due_at, note, priority,
     created_by, created_by_user_id)
VALUES (%(opportunity_id)s, %(title)s, %(assignee_broker_id)s, %(due_at)s,
        %(note)s, %(priority)s, %(created_by)s, %(created_by_user_id)s)
RETURNING id
"""

# Muddat O'ZGARSA eslatma qaytadan yuborilishi kerak — shuning uchun
# `reminded_at` tozalanadi. Aks holda ko'chirilgan muddat jimgina o'tib ketardi.
TASK_UPDATE_SQL = """
UPDATE erp.opportunity_task SET
    title=%(title)s, assignee_broker_id=%(assignee_broker_id)s,
    due_at=%(due_at)s, note=%(note)s, priority=%(priority)s,
    reminded_at = CASE WHEN due_at IS DISTINCT FROM %(due_at)s
                       THEN NULL ELSE reminded_at END
WHERE id = %(id)s
RETURNING id
"""

# HOLAT. `done`/`done_at`/`cancelled_at` bu yerda YOZILMAYDI — ularni
# trigger yuritadi (`schema_patch_erp_28.sql`). Ikki joyda yozilsa
# ular ajralib ketardi.
#
# MUDDAT ESLATMASI QAYTA OCHILGANDA TOZALANADI: yopilgan vazifa qayta
# ochilsa, uning muddati haqida eslatma yana kerak.
TASK_STATUS_SQL = """
UPDATE erp.opportunity_task SET
    status = %(status)s,
    reminded_at = CASE WHEN %(status)s = ANY(%(ochiq)s) THEN NULL
                       ELSE reminded_at END
WHERE id = %(id)s
RETURNING id, status, done
"""

# BIRIKTIRISH — alohida amal, chunki u boshqa savolga javob beradi
# ("kim qiladi", "nima qilinadi" emas) va boshqa huquq talab qiladi.
TASK_ASSIGN_SQL = """
UPDATE erp.opportunity_task SET assignee_broker_id = %(b)s
WHERE id = %(id)s
RETURNING id, assignee_broker_id
"""

TASK_DELETE_SQL = "DELETE FROM erp.opportunity_task WHERE id = %(id)s RETURNING id"

# "Mening ishlarim": bajarilmagan vazifalar + karta konteksti. Muddati
# o'tganlar ham chiqadi va eng yuqorida turadi — ular eng shoshilinchi.
# "MENING ISHLARIM" — karta vazifalari VA umumiy vazifalar birga.
#
# `JOIN` -> `LEFT JOIN` (28-patch): umumiy vazifada karta YO'Q va
# `JOIN` ularni JIMGINA tashlab yuborardi. Ya'ni ekran "ishim yo'q"
# deb ko'rsatardi, aslida esa ish bor edi — eng yomon nuqson turi.
#
# Yakuniy statusli KARTA vazifalari chiqmaydi (yutilgan tenderning
# ishi eslatilmaydi), umumiy vazifada esa karta yo'q, ya'ni bu shart
# unga TEGISHLI EMAS — shuning uchun `o.id IS NULL OR ...`.
MY_TASKS_SQL = f"""
SELECT {_TASK_COLS},
       o.title AS opp_title, o.status AS opp_status, o.deadline_at,
       o.tender_id, o.start_price, o.currency,
       c.name AS client_name, ob.full_name AS opp_broker_name
{_TASK_FROM}
LEFT JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE t.status = ANY(%(ochiq)s)
  AND (%(broker_id)s::int IS NULL
       OR t.assignee_broker_id = %(broker_id)s
       OR (t.assignee_broker_id IS NULL AND o.broker_id = %(broker_id)s))
  AND (t.due_at IS NULL OR t.due_at <= current_date + %(days)s::int)
  AND (o.id IS NULL OR o.status <> ALL(%(final)s))
ORDER BY t.due_at NULLS LAST, t.id
"""

# UMUMIY RO'YXAT — filtrlar bilan (menejer ko'rinishi va "mening
# ishlarim" ning kengaytirilgan varianti).
#
# Filtrlar "%(x)s IS NULL OR ..." uslubida: bitta so'rov, bitta reja
# (`OPP_LIST_SQL` bilan bir xil naqsh).
TASK_ROYXAT_SQL = f"""
SELECT {_TASK_COLS},
       o.title AS opp_title, o.status AS opp_status, o.deadline_at,
       o.tender_id, o.start_price, o.currency,
       c.name AS client_name, ob.full_name AS opp_broker_name
{_TASK_FROM}
LEFT JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE (%(broker_id)s::int IS NULL OR t.assignee_broker_id = %(broker_id)s)
  AND (%(status)s::text IS NULL OR t.status = %(status)s)
  AND (%(ochiq_only)s::bool IS NOT TRUE OR t.status = ANY(%(ochiq)s))
  AND (%(priority)s::text IS NULL OR t.priority = %(priority)s)
  -- KONTEKST: 'umumiy' (kartasiz) yoki 'karta' (kartaga bog'langan).
  AND (%(kontekst)s::text IS NULL
       OR (%(kontekst)s = 'umumiy' AND t.opportunity_id IS NULL)
       OR (%(kontekst)s = 'karta' AND t.opportunity_id IS NOT NULL))
  AND (%(opportunity_id)s::int IS NULL
       OR t.opportunity_id = %(opportunity_id)s)
  -- KECHIKKAN — hisoblanadi, saqlanmaydi.
  AND (%(overdue)s::bool IS NOT TRUE
       OR (t.due_at IS NOT NULL AND t.due_at < current_date
           AND t.status = ANY(%(ochiq)s)))
  AND (%(q)s::text IS NULL OR t.title ILIKE '%%' || %(q)s || '%%'
                           OR o.title ILIKE '%%' || %(q)s || '%%')
  -- EGALIK: brokerga faqat O'ZIGA biriktirilgani va O'Z kartasiniki.
  AND (%(owner_broker_id)s::int IS NULL
       OR t.assignee_broker_id = %(owner_broker_id)s
       OR o.broker_id = %(owner_broker_id)s
       OR EXISTS (SELECT 1 FROM erp.opportunity_assignee a
                   WHERE a.opportunity_id = t.opportunity_id
                     AND a.broker_id = %(owner_broker_id)s
                     AND a.removed_at IS NULL))
ORDER BY (t.status = ANY(%(ochiq)s)) DESC, t.due_at NULLS LAST, t.id DESC
LIMIT %(limit)s
"""

# --- eslatma tanlovi --------------------------------------------------------
# Muddati kelgan/o'tgan, hali eslatilmagan vazifalar. Yopilgan kartalar
# qatnashmaydi: yutilgan tenderning vazifasi eslatilmaydi.
DUE_TASKS_SQL = f"""
SELECT {_TASK_COLS},
       o.title AS opp_title, o.tender_ref, o.deadline_at,
       c.name AS client_name,
       coalesce(b.full_name, ob.full_name) AS notify_name,
       -- Xabar KIMGA ketishini aniqlash uchun (`api/erp/xabar.py`).
       o.broker_id AS opp_broker_id
{_TASK_FROM}
-- `LEFT JOIN` (28-patch): UMUMIY vazifada karta yo'q va `JOIN` uni
-- eslatmadan JIMGINA tashlab yuborardi — ya'ni kartaga bog'lanmagan
-- ish muddati hech qachon eslatilmasdi.
LEFT JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE t.status = ANY(%(ochiq)s)
  AND t.reminded_at IS NULL
  AND t.due_at IS NOT NULL
  AND t.due_at <= current_date + %(days)s::int
  -- YAKUNIY statuslar ro'yxati KODDAN keladi (`opportunity.FINAL`), bu
  -- yerda takrorlanmaydi: 24-patchda `ulgurmadik` qo'shilganda qo'lda
  -- yozilgan har bir nusxa uni JIMGINA "ochiq" deb sanardi.
  AND (o.id IS NULL OR o.status <> ALL(%(final)s))
  -- EGALIK (api/erp/egalik.py): brokerga faqat O'Z ishlari — o'ziga
  -- biriktirilgani yoki o'z kartasiniki.
  AND (%(owner_broker_id)s::int IS NULL
       OR o.broker_id = %(owner_broker_id)s
       OR t.assignee_broker_id = %(owner_broker_id)s)
ORDER BY t.due_at, t.id
"""

# Deadline yaqin kartalar (vazifasidan qat'i nazar) — tender muddati
# o'tib ketishi vazifa kechikishidan qimmatroq.
DUE_DEADLINES_SQL = """
SELECT o.id, o.title, o.tender_ref, o.deadline_at, o.status, o.start_price,
       o.currency, b.full_name AS broker_name, c.name AS client_name,
       -- KIMGA yuborish kerakligi uchun (`api/erp/xabar.py`): ism
       -- ekranga, id esa manzilga kerak.
       o.broker_id
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
-- Ro'yxat KODDAN (`opportunity.FINAL`), bu yerda TAKRORLANMAYDI.
-- Ilgari ('won','lost','rejected') qo'lda yozilgan edi va 24-patchda
-- qo'shilgan `ulgurmadik` undan tashqarida qolardi: yopilgan kartaning
-- muddati haqida eslatma kelaverardi.
WHERE o.status <> ALL(%(final)s)
  AND o.deadline_reminded_at IS NULL
  AND o.deadline_at IS NOT NULL
  AND o.deadline_at <= now() + (%(days)s || ' days')::interval
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s)
ORDER BY o.deadline_at
"""

# MUDDATI O'TGAN, LEKIN YOPILMAGAN kartalar — ESKALATSIYA.
#
# NEGA KERAK: 24-patchda `ulgurmadik` statusi qo'shildi, lekin uni
# TIZIM QO'YMAYDI — qaror odamniki. Demak hech kim yopmasa, karta
# `preparing` da abadiy turadi va `analytics.py` uni "hozir shu
# bosqichda ishlanmoqda" deb sanaydi: voronka ham, bosqich vaqti ham
# YOLG'ON bo'ladi. Ya'ni qaror odamda qolgani uchun ESLATISH SHART.
#
# NEGA `deadline_reminded_at` GA QARAMAYDI: u "muddat yaqinlashdi"
# eslatmasi uchun va bir marta qo'yiladi. Bu esa boshqa savol —
# "muddat O'TDI, karta hali ochiq" — va u kartani yopmaguncha
# JAVOBSIZ qoladi. Shuning uchun ro'yxat har kuni qaytadi; bu shovqin
# emas, ochiq qarzning o'zi.
KECHIKKAN_KARTALAR_SQL = """
SELECT o.id, o.title, o.tender_ref, o.deadline_at, o.status,
       b.full_name AS broker_name, o.broker_id, c.name AS client_name,
       floor(EXTRACT(EPOCH FROM (now() - o.deadline_at)) / 86400)::int AS kun
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
WHERE o.status <> ALL(%(final)s)
  AND o.deadline_at IS NOT NULL
  AND o.deadline_at < now()
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s)
ORDER BY o.deadline_at
"""

MARK_TASK_SQL = ("UPDATE erp.opportunity_task SET reminded_at = now() "
                 "WHERE id = ANY(%(ids)s) RETURNING id")
MARK_OPP_SQL = ("UPDATE erp.opportunity SET deadline_reminded_at = now() "
                "WHERE id = ANY(%(ids)s) RETURNING id")


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def shape(r: dict) -> dict:
    ochiq = r["status"] in OCHIQ
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"], "title": r["title"],
        "assignee": ({"id": r["assignee_broker_id"], "name": r["assignee_name"]}
                     if r["assignee_broker_id"] else None),
        "due_at": _iso(r["due_at"]), "done": r["done"], "done_at": _iso(r["done_at"]),
        "note": r["note"], "reminded_at": _iso(r["reminded_at"]),
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
        "status": r["status"], "status_label": STATUSLAR.get(r["status"]),
        "priority": r["priority"], "priority_label": PRIORITIES.get(r["priority"]),
        "updated_at": _iso(r["updated_at"]),
        "cancelled_at": _iso(r["cancelled_at"]),
        # KONTEKST — ekran umumiy va karta vazifasini AJRATIB
        # ko'rsatishi kerak (§3). Ikkalasi bitta ro'yxatda aralashib
        # ketsa, odam "bu qaysi tenderga tegishli?" degan savolga
        # javob topa olmasdi.
        "kontekst": "karta" if r["opportunity_id"] else "umumiy",
        "ochiq": ochiq,
        # Kechikkanini SERVER aytadi: brauzer soati noto'g'ri bo'lishi mumkin,
        # "kechikdi" degan xabar esa qaror qabul qilishga ta'sir qiladi.
        "overdue": bool(r["due_at"] and ochiq and _is_past(r["due_at"])),
    }


def _is_past(d) -> bool:
    import datetime as _dt
    return d < _dt.date.today()


def _shape_my(r: dict) -> dict:
    out = shape(r)
    # UMUMIY vazifada karta YO'Q. `None` beriladi, bo'sh maydonlarga
    # to'la obyekt EMAS: ekran "tender ko'rsatilmagan" bilan "tenderga
    # tegishli emas" ni ajrata olishi kerak.
    out["opportunity"] = None if not r["opportunity_id"] else {
        "id": r["opportunity_id"], "title": r["opp_title"],
        "status": r["opp_status"],
        "tender_id": r["tender_id"], "client_name": r["client_name"],
        "broker_name": r["opp_broker_name"], "deadline_at": _iso(r["deadline_at"]),
        "start_price": _num(r["start_price"]), "currency": r["currency"],
    }
    return out


def _check(data: dict) -> None:
    """Kirish ma'lumoti. Xato matni ODAM tuzatadigan tilda (§29)."""
    if not (data.get("title") or "").strip():
        raise ErpError("Vazifa nomi bo'sh.")
    pr = data.get("priority")
    if pr is not None and pr not in PRIORITIES:
        raise ErpError(f"Noma'lum ustuvorlik: {pr}")
    b = data.get("assignee_broker_id")
    if b:
        # HODIM MAVJUD VA FAOL bo'lishi shart (§31.11). Faolsizga
        # biriktirilgan ish hech kimda ko'rinmasdi va jimgina
        # yo'qolardi.
        r = db.query_one("SELECT active FROM erp.broker WHERE id = %(b)s",
                         {"b": b})
        if not r:
            raise ErpError("Hodim topilmadi.", 404)
        if not r["active"]:
            raise ErpError("Faolsizlantirilgan hodimga vazifa "
                           "biriktirilmaydi.")


def _bor(task_id: int) -> dict:
    t = db.query_one(TASK_GET_SQL, {"id": task_id})
    if not t:
        raise ErpError("Vazifa topilmadi.", 404)
    return t


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def list_(opp_id: int) -> List[dict]:
    _need_schema3()
    return [shape(r) for r in db.query(TASKS_SQL, {"id": opp_id})]


def add(opp_id: Optional[int], data: dict) -> List[dict]:
    """Vazifa yaratish. `opp_id=None` — UMUMIY vazifa (tendersiz).

    Javob — kartaning BUTUN vazifalar ro'yxati (interfeys qayta
    so'ramasin); umumiy vazifada esa yaratilganning O'ZI ro'yxat
    sifatida: kartasiz "ro'yxat" degan tushuncha yo'q."""
    _need_schema3()
    _check(data)
    if opp_id is not None and not db.query_one(
            "SELECT 1 AS x FROM erp.opportunity WHERE id=%(id)s",
            {"id": opp_id}):
        raise ErpError("Karta topilmadi.", 404)
    row = db.execute_returning(TASK_INSERT_SQL, {
        **{k: data.get(k) for k in TASK_FIELDS},
        "title": data["title"].strip(),
        "priority": data.get("priority") or "medium",
        "opportunity_id": opp_id, "created_by": data.get("created_by"),
        # `or None`: hisob id si 0 bo'lishi mumkin emas, lekin
        # sinovdagi soxta sessiyada shunday keladi va FK ni buzardi.
        # Nol — "noma'lum", ya'ni `NULL` ning o'zi.
        "created_by_user_id": data.get("actor_user_id") or None},
        # `actor` SHART: usiz jurnalda `actor IS NULL` qoladi va u
        # "ERP dan tashqarida o'zgartirilgan" MA'NOSINI bildiradi
        # (`api/db.py`) — ya'ni o'z yozuvimizni begona qilib
        # ko'rsatardik.
        actor=data.get("created_by"))
    _biriktirildi(row, opp_id, data)
    if opp_id is None:
        return [bitta(row["id"])]
    return list_(opp_id)


def bitta(task_id: int) -> dict:
    """Bitta vazifa + karta konteksti (umumiy vazifada `None`)."""
    _need_schema3()
    r = db.query_one(BITTA_SQL, {"id": task_id})
    if not r:
        raise ErpError("Vazifa topilmadi.", 404)
    return _shape_my(r)


def royxat(broker_id: Optional[int] = None, status: Optional[str] = None,
           priority: Optional[str] = None, kontekst: Optional[str] = None,
           overdue: bool = False, ochiq_only: bool = False,
           opportunity_id: Optional[int] = None, q: Optional[str] = None,
           limit: int = 200,
           owner_broker_id: Optional[int] = None) -> List[dict]:
    """Filtrlangan ro'yxat: menejer ko'rinishi va kengaytirilgan
    "mening ishlarim".

    `owner_broker_id` — EGALIK filtri (broker uchun). U berilsa,
    odam faqat o'ziga biriktirilgan yoki o'zi ishlayotgan kartaning
    vazifalarini ko'radi. Filtrni interfeys emas, SERVER qo'yadi."""
    _need_schema3()
    if status is not None and status not in STATUSLAR:
        raise ErpError(f"Noma'lum holat: {status}")
    if kontekst is not None and kontekst not in ("umumiy", "karta"):
        raise ErpError("Kontekst 'umumiy' yoki 'karta' bo'lishi kerak.")
    rows = db.query(TASK_ROYXAT_SQL, {
        "broker_id": broker_id, "status": status, "priority": priority,
        "kontekst": kontekst, "overdue": bool(overdue),
        "ochiq_only": bool(ochiq_only), "opportunity_id": opportunity_id,
        "q": (q or "").strip() or None, "ochiq": list(OCHIQ),
        "limit": max(1, min(int(limit or 200), 500)),
        "owner_broker_id": owner_broker_id})
    return [_shape_my(r) for r in rows]


def _biriktirildi(row: Optional[dict], opp_id: Optional[int],
                  data: dict) -> None:
    """Vazifa BOSHQA odamga biriktirilgan bo'lsa — bildirishnoma.

    MAS'ULSIZ vazifa xabar bermaydi: u kartaning brokeriniki
    hisoblanadi (`my_tasks`) va u karta haqida allaqachon biladi.
    Har vazifaga xabar yuborish ro'yxatni shovqinga aylantirardi.

    UMUMIY vazifada esa mas'ul KO'RSATILISHI SHART (`main.py` da
    tekshiriladi): kartasiz, egasiz vazifa hech kimning ishi emas.

    YIQITMAYDI: vazifa yozilishi bildirishnomadan muhimroq."""
    if not row or not data.get("assignee_broker_id"):
        return
    try:
        from api.erp import hodisa
        hodisa.vazifa_biriktirildi(
            row["id"], data["assignee_broker_id"], data["title"].strip(),
            opp_id, muddat=(str(data.get("due_at"))[:10]
                            if data.get("due_at") else None),
            chiqaruvchi=data.get("actor_user_id"))
    except Exception:                               # noqa: BLE001
        import logging
        logging.getLogger("erp.tasks").exception(
            "vazifa bildirishnomasi yozilmadi (karta %s)", opp_id)


def update(task_id: int, data: dict) -> List[dict]:
    _need_schema3()
    _check(data)
    cur = _bor(task_id)
    db.execute_returning(TASK_UPDATE_SQL, {
        **{k: data.get(k) for k in TASK_FIELDS},
        "title": data["title"].strip(),
        "priority": data.get("priority") or cur["priority"],
        "id": task_id}, actor=data.get("created_by"))
    # MAS'UL O'ZGARGANDA xabar. Boshqa maydon (izoh, muddat)
    # o'zgarganda YO'Q: `hodisa.vazifa_biriktirildi` dedup kaliti
    # vazifa id si bo'yicha va `kotar=False`, ya'ni takror yozilmaydi.
    if data.get("assignee_broker_id") != cur.get("assignee_broker_id"):
        _biriktirildi({"id": task_id}, cur["opportunity_id"], data)
    return _javob(cur["opportunity_id"], task_id)


def holat(task_id: int, status: str, kim: Optional[str] = None,
          actor_user_id: Optional[int] = None) -> List[dict]:
    """Holatni o'zgartirish: boshlash, bajarish, bekor qilish, qayta ochish.

    QAYTA OCHISH RUXSAT ETILADI (§9): xato bosilgan "bajarildi" ni
    orqaga qaytarib bo'lmasa, odam yangi vazifa yaratardi va ro'yxatda
    ikkita bir xil qator qolardi. Iz esa jurnalda qoladi
    (`erp.doc_audit`), ya'ni "kim qaytarib ochdi" javobsiz qolmaydi."""
    _need_schema3()
    if status not in STATUSLAR:
        raise ErpError(f"Noma'lum holat: {status}")
    cur = _bor(task_id)
    if cur["status"] == status:
        return _javob(cur["opportunity_id"], task_id)
    db.execute_returning(TASK_STATUS_SQL,
                         {"id": task_id, "status": status,
                          "ochiq": list(OCHIQ)}, actor=kim)
    _holat_xabari(cur, status, actor_user_id)
    return _javob(cur["opportunity_id"], task_id)


def _holat_xabari(cur: dict, status: str,
                  actor_user_id: Optional[int]) -> None:
    """Bajarilgan/bekor qilingan vazifa haqida KIMGA xabar berish kerak.

    Vazifani BOSHQA odam yopgan bo'lsa — BAJARUVCHIGA (uning ishi
    qo'lidan olindi yoki yopildi); yaratuvchi boshqa odam bo'lsa —
    UNGA (u so'ragan ish tugadi). O'z amali haqida xabar kelmaydi.

    "Boshlandi" xabar bermaydi: bu kundalik harakat va u haqda xabar
    berish bildirishnomalarni shovqinga aylantirardi."""
    if status not in ("bajarildi", "bekor"):
        return
    try:
        from api.erp import hodisa
        nom = cur["title"]
        holat = STATUSLAR[status].lower()
        qabul = []
        if cur.get("created_by_user_id"):
            qabul.append(cur["created_by_user_id"])
        hodisa.chiqar("vazifa", f"Vazifa {holat}: {nom}",
                      qabul=qabul, broker_id=cur.get("assignee_broker_id"),
                      opportunity_id=cur.get("opportunity_id"),
                      task_id=cur["id"], chiqaruvchi=actor_user_id,
                      dedup=f"vazifa_holat:{cur['id']}:{status}", kotar=False)
    except Exception:                               # noqa: BLE001
        import logging
        logging.getLogger("erp.tasks").exception("vazifa holati xabari")


def biriktir(task_id: int, broker_id: Optional[int],
             kim: Optional[str] = None,
             actor_user_id: Optional[int] = None) -> List[dict]:
    """QAYTA BIRIKTIRISH — alohida amal.

    Nega alohida: u boshqa savolga javob beradi ("kim qiladi") va
    boshqa huquq talab qiladi. Tahrirlash ichida qolsa, vazifa
    matnini o'zgartira oladigan har kim uni boshqaga surib
    qo'yishi mumkin bo'lardi."""
    _need_schema3()
    cur = _bor(task_id)
    _check({"title": cur["title"], "assignee_broker_id": broker_id})
    if cur.get("assignee_broker_id") == broker_id:
        return _javob(cur["opportunity_id"], task_id)
    db.execute_returning(TASK_ASSIGN_SQL, {"id": task_id, "b": broker_id},
                         actor=kim)
    if broker_id:
        _biriktirildi({"id": task_id}, cur["opportunity_id"],
                      {"assignee_broker_id": broker_id, "title": cur["title"],
                       "due_at": cur.get("due_at"),
                       "actor_user_id": actor_user_id})
    # ESKI BAJARUVCHIGA ham xabar: ish uning ro'yxatidan JIMGINA
    # yo'qolmasin (karta o'tkazish bilan bir xil qoida).
    if cur.get("assignee_broker_id"):
        try:
            from api.erp import hodisa
            hodisa.chiqar(
                "vazifa", f"Vazifa boshqa hodimga o'tkazildi: {cur['title']}",
                broker_id=cur["assignee_broker_id"],
                opportunity_id=cur.get("opportunity_id"), task_id=task_id,
                chiqaruvchi=actor_user_id)
        except Exception:                           # noqa: BLE001
            import logging
            logging.getLogger("erp.tasks").exception("qayta biriktirish xabari")
    return _javob(cur["opportunity_id"], task_id)


def set_done(task_id: int, done: bool, kim: Optional[str] = None,
             actor_user_id: Optional[int] = None) -> List[dict]:
    """Eski nom — `holat()` ga o'tadi.

    SAQLANDI: interfeys va sinovlar bu nomni ishlatadi va uni bir
    zarbada almashtirish foydasiz xavf edi. Ma'nosi ham aniq:
    belgilangan = "bajarildi", olib tashlangan = "yangi"."""
    return holat(task_id, "bajarildi" if done else "yangi", kim,
                 actor_user_id)


def delete(task_id: int, kim: Optional[str] = None) -> List[dict]:
    """O'CHIRISH — faqat xato yaratilgan vazifa uchun.

    Bajarilgan va bekor qilingan vazifalar TARIX (§26) va ular
    ro'yxatda qoladi; ularni yo'qotish "ish qilinganmi?" degan
    savolni javobsiz qoldirardi. Iz jurnalda qoladi
    (`erp.doc_audit`), ya'ni o'chirish ham ko'rinadi."""
    _need_schema3()
    cur = _bor(task_id)
    if cur["status"] in ("bajarildi", "bekor"):
        raise ErpError(
            "Yakunlangan vazifa o'chirilmaydi — u ish tarixi. "
            "Kerak bo'lsa qayta oching yoki bekor qiling.")
    db.execute_returning(TASK_DELETE_SQL, {"id": task_id}, actor=kim)
    return _javob(cur["opportunity_id"], None)


def _javob(opp_id: Optional[int], task_id: Optional[int]) -> List[dict]:
    """Kartaniki — BUTUN ro'yxat, umumiysi — bittasi.

    Sabab: karta oynasida ro'yxat ko'rinadi va uni qayta so'rash
    ortiqcha aylanish bo'lardi; umumiy vazifada esa "ro'yxat"
    degan kontekst yo'q."""
    if opp_id:
        return list_(opp_id)
    if task_id:
        return [bitta(task_id)]
    return []


def yuklama(faqat_faol: bool = True) -> List[dict]:
    """HODIM YUKLAMASI: ochiq vazifa, kechikkan, ochiq karta.

    "Kimga ish berish mumkin" degan savolga javob (§21). Bu BAHO
    EMAS: bajarilganlar soni ko'rsatiladi, lekin reyting, ball yoki
    "samaradorlik" hisoblanmaydi — bunday ko'rsatkich odamni ishni
    tez yopishga undardi, sifatga emas."""
    _need_schema3()
    rows = db.query(
        "SELECT * FROM erp.v_hodim_yuklama "
        "WHERE (%(f)s::bool IS NOT TRUE OR active) "
        "ORDER BY kechikkan DESC, ochiq_vazifa DESC, full_name",
        {"f": bool(faqat_faol)})
    return [{"broker_id": r["broker_id"], "full_name": r["full_name"],
             "active": r["active"], "ochiq_vazifa": int(r["ochiq_vazifa"]),
             "kechikkan": int(r["kechikkan"]),
             "bajarilgan": int(r["bajarilgan"]),
             "ochiq_karta": int(r["ochiq_karta"])} for r in rows]


def tarix(task_id: int) -> List[dict]:
    """Vazifa tarixi — MAVJUD jurnaldan (`erp.doc_audit`).

    Alohida "task_history" jadvali ochilmadi: ikkita jurnal ikkita
    haqiqat manbai bo'lardi va "kim o'zgartirdi" ikki joydan
    qidirilardi (`api/erp/audit.py` sarlavhasidagi qoida)."""
    _need_schema3()
    _bor(task_id)
    rows = db.query(
        "SELECT id, action, field, old_value, new_value, actor, created_at "
        "FROM erp.doc_audit WHERE doc_type = 'vazifa' AND doc_id = %(id)s "
        "ORDER BY created_at, id", {"id": task_id})
    return [{"id": r["id"], "action": r["action"], "field": r["field"],
             "old_value": r["old_value"], "new_value": r["new_value"],
             # `actor IS NULL` = "ERP dan tashqarida o'zgartirilgan"
             # (`api/db.py`). Yashirilmaydi.
             "actor": r["actor"], "at": _iso(r["created_at"])} for r in rows]


def my_tasks(broker_id: Optional[int] = None, days: int = 0) -> Dict[str, Any]:
    """"Mening bugungi ishlarim". `days=0` — bugun va kechikkanlar;
    `days=7` — kelasi haftaga ham qaraydi.

    Mas'ul ko'rsatilmagan vazifa KARTA BROKERINIKI hisoblanadi — aks holda
    "keyingi vazifa" dan ko'chirilgan eski yozuvlar hech kimda ko'rinmasdi."""
    _need_schema3()
    from api.erp.opportunity import FINAL
    rows = [_shape_my(r) for r in db.query(
        MY_TASKS_SQL, {"broker_id": broker_id, "days": days,
                       "final": sorted(FINAL), "ochiq": list(OCHIQ)})]
    return {
        "broker_id": broker_id, "days": days,
        "overdue": [t for t in rows if t["overdue"]],
        "today": [t for t in rows if not t["overdue"] and t["due_at"]
                  and t["due_at"] == _today_iso()],
        "later": [t for t in rows if not t["overdue"]
                  and (not t["due_at"] or t["due_at"] != _today_iso())],
        "total": len(rows),
    }


def _today_iso() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()


# --- eslatma uchun ----------------------------------------------------------
def due_reminders(days: int = 1, deadline_days: int = 3,
                  owner_broker_id: Optional[int] = None) -> Dict[str, Any]:
    """Eslatilishi kerak bo'lgan vazifalar va deadline'lar.

    HECH NARSA YUBORMAYDI va hech narsani belgilamaydi — shuning uchun uni
    sinovda ham, "quruq yurish" (dry-run) rejimida ham xavfsiz chaqirish
    mumkin."""
    _need_schema3()
    from api.erp.opportunity import FINAL
    yakuniy = sorted(FINAL)
    tasks = [_shape_task_reminder(r)
             for r in db.query(DUE_TASKS_SQL, {
                 "days": days, "final": yakuniy, "ochiq": list(OCHIQ),
                 "owner_broker_id": owner_broker_id})]
    deadlines = [{"id": r["id"], "title": r["title"], "tender_ref": r["tender_ref"],
                  "deadline_at": _iso(r["deadline_at"]), "status": r["status"],
                  "start_price": _num(r["start_price"]), "currency": r["currency"],
                  "broker_name": r["broker_name"], "broker_id": r["broker_id"],
                  "client_name": r["client_name"]}
                 for r in db.query(DUE_DEADLINES_SQL, {
                     "days": str(deadline_days), "final": yakuniy,
                     "owner_broker_id": owner_broker_id})]
    kechikkan = [{"id": r["id"], "title": r["title"], "tender_ref": r["tender_ref"],
                  "deadline_at": _iso(r["deadline_at"]), "status": r["status"],
                  "broker_name": r["broker_name"], "broker_id": r["broker_id"],
                  "client_name": r["client_name"], "kun": r["kun"]}
                 for r in db.query(KECHIKKAN_KARTALAR_SQL, {
                     "final": yakuniy, "owner_broker_id": owner_broker_id})]
    return {"tasks": tasks, "deadlines": deadlines, "kechikkan": kechikkan,
            "days": days, "deadline_days": deadline_days}


def _shape_task_reminder(r: dict) -> dict:
    return {"id": r["id"], "opportunity_id": r["opportunity_id"], "title": r["title"],
            "due_at": _iso(r["due_at"]), "overdue": _is_past(r["due_at"]),
            "opp_title": r["opp_title"], "tender_ref": r["tender_ref"],
            "client_name": r["client_name"], "assignee": r["notify_name"],
            # Vazifa bajaruvchisi ko'rsatilmagan bo'lsa — KARTA
            # mas'uli (`api/erp/xabar.py` shu id ga yuboradi).
            "broker_id": r["assignee_broker_id"] or r["opp_broker_id"],
            "deadline_at": _iso(r["deadline_at"])}


def mark_reminded(task_ids: List[int], opp_ids: List[int]) -> Dict[str, int]:
    """Eslatma yuborilgach belgilanadi — takror yubormaslik uchun."""
    _need_schema3()
    n_t = n_o = 0
    if task_ids:
        db.execute_returning(MARK_TASK_SQL, {"ids": list(task_ids)})
        n_t = len(task_ids)
    if opp_ids:
        db.execute_returning(MARK_OPP_SQL, {"ids": list(opp_ids)})
        n_o = len(opp_ids)
    return {"tasks": n_t, "opportunities": n_o}
