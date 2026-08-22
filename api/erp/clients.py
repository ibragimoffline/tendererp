"""ERP 2-bosqich: mijoz korxonalar bazasi va KORXONA PASSPORTI.

Chegara:
  - Faqat erp.* jadvallari. public.* ga na yozadi, na o'qiydi.
  - `api.compliance` bu modulni import QILMAYDI — teskarisi ham. Cheklist
    mijoz hujjatlariga qarab ishlashi uchun main.py hujjatlarni SHU MODULDAN
    oladi va `compliance.check(tender_id, docs=...)` ga UZATADI. Shunda
    bog'liqlik bir tomonlama qoladi (erp_arxitektura.md 2.4).
  - opportunity.py ni import QILMAYDI: aksincha bo'lsa halqa hosil bo'lardi
    (stats.py -> opportunity.py -> clients.py). Kichik yordamchilar
    (_iso/_num) shu yerda takrorlanadi — ular uch qatorlik sof funksiyalar.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError, _need_schema

# Passportning tahrirlanadigan maydonlari. Ro'yxat BITTA joyda: INSERT,
# UPDATE va so'rov modeli ham shundan yuradi.
FIELDS = (
    "name", "inn", "oked", "legal_form", "tax_mode", "address_legal",
    "address_actual", "bank_name", "bank_mfo", "bank_account",
    "director_name", "phone", "email", "note", "active",
    # QQS — fakturaning sukut stavkasi shu yerdan olinadi (5B-2).
    # `vat_payer` NULL = HALI SO'RALMAGAN, `false` bilan bir xil emas.
    "vat_payer", "vat_rate",
)

CONTACT_FIELDS = ("full_name", "position", "phone", "email", "is_primary", "note")
DOC_FIELDS = ("doc_type", "name", "number", "issued_at", "valid_until",
              "file_name", "file_ref", "note")


# ---------------------------------------------------------------------------
# Sxema tayyorligi (2-bosqich patchi alohida qo'llanadi)
# ---------------------------------------------------------------------------
_SCHEMA2_READY = False

SCHEMA2_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'client_document'
"""


def schema_ready() -> bool:
    global _SCHEMA2_READY
    if _SCHEMA2_READY:
        return True
    _SCHEMA2_READY = bool(db.query_one(SCHEMA2_CHECK_SQL))
    return _SCHEMA2_READY


def _need_schema2() -> None:
    _need_schema()          # avvalo 1-bosqich jadvallari
    if not schema_ready():
        raise ErpError("Mijoz passporti jadvallari yo'q: schema_patch_erp_2.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_CLIENT_COLS = """
c.id, c.name, c.inn, c.oked, c.legal_form, c.tax_mode,
c.address_legal, c.address_actual, c.bank_name, c.bank_mfo, c.bank_account,
c.director_name, c.phone, c.email, c.note, c.active, c.vat_payer, c.vat_rate,
c.created_at, c.updated_at
"""

# Ro'yxatda darhol ko'rinadigan natija: nechta karta, nechtasi yutilgan.
# Hisob BAZADA (opportunity.md dagi qoida) — frontendда sanalmaydi.
CLIENT_LIST_SQL = f"""
SELECT {_CLIENT_COLS},
       count(o.id)                                        AS opp_n,
       count(o.id) FILTER (WHERE o.status = 'won')         AS won_n,
       count(o.id) FILTER (WHERE o.status = 'lost')        AS lost_n,
       count(o.id) FILTER (WHERE o.status NOT IN ('won','lost','rejected')) AS open_n,
       (SELECT count(*) FROM erp.client_document d WHERE d.client_id = c.id) AS doc_n
FROM erp.client_company c
LEFT JOIN erp.opportunity o ON o.client_id = c.id
WHERE (%(q)s::text IS NULL OR c.name ILIKE '%%' || %(q)s || '%%'
                           OR c.inn  ILIKE '%%' || %(q)s || '%%')
  AND (%(active_only)s::bool IS NOT TRUE OR c.active)
GROUP BY c.id
ORDER BY c.active DESC, c.name
"""

CLIENT_GET_SQL = f"SELECT {_CLIENT_COLS} FROM erp.client_company c WHERE c.id = %(id)s"

CLIENT_BY_INN_SQL = ("SELECT id, name FROM erp.client_company "
                     "WHERE inn = %(inn)s AND (%(id)s::int IS NULL OR id <> %(id)s)")

CLIENT_INSERT_SQL = """
INSERT INTO erp.client_company
    (name, inn, oked, legal_form, tax_mode, address_legal, address_actual,
     bank_name, bank_mfo, bank_account, director_name, phone, email, note,
     vat_payer, vat_rate)
VALUES (%(name)s, %(inn)s, %(oked)s, %(legal_form)s, %(tax_mode)s,
        %(address_legal)s, %(address_actual)s, %(bank_name)s, %(bank_mfo)s,
        %(bank_account)s, %(director_name)s, %(phone)s, %(email)s, %(note)s,
        %(vat_payer)s, %(vat_rate)s)
RETURNING id
"""

CLIENT_UPDATE_SQL = """
UPDATE erp.client_company SET
    name=%(name)s, inn=%(inn)s, oked=%(oked)s, legal_form=%(legal_form)s,
    tax_mode=%(tax_mode)s, address_legal=%(address_legal)s,
    address_actual=%(address_actual)s, bank_name=%(bank_name)s,
    bank_mfo=%(bank_mfo)s, bank_account=%(bank_account)s,
    director_name=%(director_name)s, phone=%(phone)s, email=%(email)s,
    note=%(note)s, active=%(active)s,
    vat_payer=%(vat_payer)s, vat_rate=%(vat_rate)s, updated_at=now()
WHERE id = %(id)s
RETURNING id
"""

CONTACTS_SQL = """
SELECT id, client_id, full_name, position, phone, email, is_primary, note, created_at
FROM erp.client_contact WHERE client_id = %(id)s
ORDER BY is_primary DESC, full_name
"""
CONTACT_INSERT_SQL = """
INSERT INTO erp.client_contact (client_id, full_name, position, phone, email, is_primary, note)
VALUES (%(client_id)s, %(full_name)s, %(position)s, %(phone)s, %(email)s,
        %(is_primary)s, %(note)s)
RETURNING id
"""
CONTACT_UPDATE_SQL = """
UPDATE erp.client_contact SET
    full_name=%(full_name)s, position=%(position)s, phone=%(phone)s,
    email=%(email)s, is_primary=%(is_primary)s, note=%(note)s
WHERE id = %(id)s
RETURNING id
"""
CONTACT_DELETE_SQL = "DELETE FROM erp.client_contact WHERE id = %(id)s RETURNING id"

# Ustun nomlari public.company_document bilan AYNAN bir xil — cheklist
# ikkala manbani ham o'zgarishsiz o'qiydi.
_DOC_COLS = ("id, client_id, doc_type, name, number, issued_at, valid_until, "
             "file_name, file_ref, note, created_at, updated_at")

DOCS_SQL = f"SELECT {_DOC_COLS} FROM erp.client_document WHERE client_id = %(id)s ORDER BY doc_type, id"
DOC_INSERT_SQL = f"""
INSERT INTO erp.client_document
    (client_id, doc_type, name, number, issued_at, valid_until, file_name, file_ref, note)
VALUES (%(client_id)s, %(doc_type)s, %(name)s, %(number)s, %(issued_at)s,
        %(valid_until)s, %(file_name)s, %(file_ref)s, %(note)s)
RETURNING {_DOC_COLS}
"""
DOC_UPDATE_SQL = f"""
UPDATE erp.client_document SET
    doc_type=%(doc_type)s, name=%(name)s, number=%(number)s,
    issued_at=%(issued_at)s, valid_until=%(valid_until)s,
    file_name=%(file_name)s, file_ref=%(file_ref)s, note=%(note)s,
    updated_at=now()
WHERE id=%(id)s
RETURNING {_DOC_COLS}
"""
DOC_DELETE_SQL = "DELETE FROM erp.client_document WHERE id = %(id)s RETURNING id"

# Mijozning kartalari — passport sahifasida "shu korxona bilan nima qilingan".
CLIENT_OPPS_SQL = """
SELECT o.id, o.title, o.tender_id, o.tender_ref, o.status, o.start_price,
       o.currency, o.deadline_at, o.closed_at, b.full_name AS broker_name
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
WHERE o.client_id = %(id)s
ORDER BY o.deadline_at DESC NULLS LAST, o.id DESC
"""


# ---------------------------------------------------------------------------
# Yordamchilar
# ---------------------------------------------------------------------------
def _iso(v):
    return v.isoformat() if v is not None else None


def _num(v):
    return None if v is None else float(v)


def _clean(v: Optional[str]) -> Optional[str]:
    """Bo'sh satr NULL ga aylanadi: '' va NULL ikkalasi ham "kiritilmagan"
    degani, lekin '' qisman UNIQUE indeksda TAKROR sifatida to'qnashardi."""
    if v is None:
        return None
    v = str(v).strip()
    return v or None


def _norm_inn(v: Optional[str]) -> Optional[str]:
    """INN — 9 raqam (O'zbekiston). Bo'shliq va tirelar tashlanadi.
    Format tekshiriladi, chunki noto'g'ri INN takrorni topa olmaydi va
    ariza hujjatlariga xato ko'chib o'tadi."""
    v = _clean(v)
    if v is None:
        return None
    digits = "".join(ch for ch in v if ch.isdigit())
    if len(digits) != 9:
        raise ErpError("INN 9 ta raqamdan iborat bo'lishi kerak.")
    return digits


def shape(r: dict) -> dict:
    """Passport qatori -> API javobi."""
    out = {k: r.get(k) for k in (
        "id", "name", "inn", "oked", "legal_form", "tax_mode", "address_legal",
        "address_actual", "bank_name", "bank_mfo", "bank_account",
        "director_name", "phone", "email", "note", "active", "vat_payer")}
    # NUMERIC -> float: JSON `Decimal` ni bilmaydi.
    out["vat_rate"] = (float(r["vat_rate"]) if r.get("vat_rate") is not None
                       else None)
    out["created_at"] = _iso(r.get("created_at"))
    out["updated_at"] = _iso(r.get("updated_at"))
    # Passport to'liqligi — ro'yxatda "yetishmayapti" belgisini ko'rsatish uchun.
    need = ("inn", "legal_form", "address_legal", "bank_account", "bank_mfo",
            "director_name", "phone")
    out["missing"] = [k for k in need if not r.get(k)]
    return out


def _shape_doc(r: dict) -> dict:
    return {**{k: r[k] for k in ("id", "client_id", "doc_type", "name", "number",
                                 "file_name", "file_ref", "note")},
            "issued_at": _iso(r["issued_at"]), "valid_until": _iso(r["valid_until"]),
            "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"])}


def _check_inn_free(inn: Optional[str], client_id: Optional[int] = None) -> None:
    if not inn:
        return
    ex = db.query_one(CLIENT_BY_INN_SQL, {"inn": inn, "id": client_id})
    if ex:
        raise ErpError(f"Bu INN allaqachon ro'yxatda: {ex['name']}.",
                       409, client_id=ex["id"])


def _params(data: dict, fields, **extra) -> Dict[str, Any]:
    return {**{k: data.get(k) for k in fields}, **extra}


# ---------------------------------------------------------------------------
# Amallar — korxona
# ---------------------------------------------------------------------------
def list_(q: Optional[str] = None, active_only: bool = False) -> List[dict]:
    _need_schema2()
    out = []
    for r in db.query(CLIENT_LIST_SQL, {"q": q or None, "active_only": active_only}):
        item = shape(r)
        item.update({"opp_n": r["opp_n"], "won_n": r["won_n"], "lost_n": r["lost_n"],
                     "open_n": r["open_n"], "doc_n": r["doc_n"],
                     "win_rate": _win_rate(r["won_n"], r["lost_n"])})
        out.append(item)
    return out


def _currencies(opps) -> list:
    """Kartalarda ishlatilgan valyutalar (narxi ko'rsatilganlaridan)."""
    return sorted({(o.get("currency") or "UZS").strip() or "UZS"
                   for o in opps if o.get("start_price") is not None})


def _one_currency(opps):
    """Bitta valyuta bo'lsa o'shanisi, aks holda `None`."""
    c = _currencies(opps)
    return c[0] if len(c) == 1 else None


def _mixed(opps) -> bool:
    return len(_currencies(opps)) > 1


def _win_rate(won: int, lost: int) -> Optional[int]:
    """Yutish foizi HAL BO'LGANLARIDAN: rad etilganlar ishtirok etmagan,
    ularni maxrajga qo'shish ko'rsatkichni pasaytirib yuborardi."""
    return round(100 * won / (won + lost)) if (won + lost) else None


def get(client_id: int) -> dict:
    """Passport + aloqa shaxslari + hujjatlar + shu mijozning kartalari."""
    _need_schema2()
    r = db.query_one(CLIENT_GET_SQL, {"id": client_id})
    if not r:
        raise ErpError("Mijoz topilmadi.", 404)
    out = shape(r)
    out["contacts"] = [{**c, "created_at": _iso(c["created_at"])}
                       for c in db.query(CONTACTS_SQL, {"id": client_id})]
    out["documents"] = [_shape_doc(d) for d in db.query(DOCS_SQL, {"id": client_id})]
    opps = db.query(CLIENT_OPPS_SQL, {"id": client_id})
    out["opportunities"] = [
        {"id": o["id"], "title": o["title"], "tender_id": o["tender_id"],
         "tender_ref": o["tender_ref"], "status": o["status"],
         "start_price": _num(o["start_price"]), "currency": o["currency"],
         "deadline_at": _iso(o["deadline_at"]), "closed_at": _iso(o["closed_at"]),
         "broker_name": o["broker_name"]}
        for o in opps]
    won = sum(1 for o in opps if o["status"] == "won")
    lost = sum(1 for o in opps if o["status"] == "lost")
    out["summary"] = {
        "opp_n": len(opps), "won_n": won, "lost_n": lost,
        "open_n": sum(1 for o in opps if o["status"] not in ("won", "lost", "rejected")),
        # ARALASH VALYUTA QO'SHILMAYDI. Mijozning kartalari bir nechta
        # valyutada bo'lsa summa berilmaydi: "1200 USD + 15 mln UZS"
        # degan son hech narsani anglatmaydi.
        "won_total": (None if _mixed(opps) else
                      float(sum(o["start_price"] or 0
                                for o in opps if o["status"] == "won"))),
        "currency": (_one_currency(opps)),
        "mixed_currency": _mixed(opps),
        "win_rate": _win_rate(won, lost),
    }
    return out


def create(data: dict) -> dict:
    _need_schema2()
    name = _clean(data.get("name"))
    if not name:
        raise ErpError("Korxona nomi bo'sh.")
    inn = _norm_inn(data.get("inn"))
    _check_inn_free(inn)
    params = _params(data, [f for f in FIELDS if f not in ("name", "inn", "active")])
    params = {k: _clean(v) for k, v in params.items()}
    row = db.execute_returning(CLIENT_INSERT_SQL, {**params, "name": name, "inn": inn})
    return get(row["id"])


def update(client_id: int, data: dict) -> dict:
    _need_schema2()
    name = _clean(data.get("name"))
    if not name:
        raise ErpError("Korxona nomi bo'sh.")
    inn = _norm_inn(data.get("inn"))
    _check_inn_free(inn, client_id)
    params = {k: _clean(data.get(k))
              for k in FIELDS if k not in ("name", "inn", "active")}
    row = db.execute_returning(CLIENT_UPDATE_SQL, {
        **params, "id": client_id, "name": name, "inn": inn,
        # active — yagona mantiqiy maydon, _clean unga tegmaydi
        "active": bool(data.get("active", True))})
    if not row:
        raise ErpError("Mijoz topilmadi.", 404)
    return get(client_id)


# ---------------------------------------------------------------------------
# Amallar — aloqa shaxslari
# ---------------------------------------------------------------------------
def add_contact(client_id: int, data: dict) -> dict:
    _need_schema2()
    if not _clean(data.get("full_name")):
        raise ErpError("Ism bo'sh.")
    if not db.query_one(CLIENT_GET_SQL, {"id": client_id}):
        raise ErpError("Mijoz topilmadi.", 404)
    db.execute_returning(CONTACT_INSERT_SQL, {
        **_params(data, CONTACT_FIELDS), "client_id": client_id,
        "is_primary": bool(data.get("is_primary"))})
    return get(client_id)


def update_contact(contact_id: int, data: dict) -> dict:
    _need_schema2()
    if not _clean(data.get("full_name")):
        raise ErpError("Ism bo'sh.")
    cur = db.query_one("SELECT client_id FROM erp.client_contact WHERE id=%(id)s",
                       {"id": contact_id})
    if not cur:
        raise ErpError("Aloqa shaxsi topilmadi.", 404)
    db.execute_returning(CONTACT_UPDATE_SQL, {
        **_params(data, CONTACT_FIELDS), "id": contact_id,
        "is_primary": bool(data.get("is_primary"))})
    return get(cur["client_id"])


def delete_contact(contact_id: int) -> dict:
    _need_schema2()
    cur = db.query_one("SELECT client_id FROM erp.client_contact WHERE id=%(id)s",
                       {"id": contact_id})
    if not cur:
        raise ErpError("Aloqa shaxsi topilmadi.", 404)
    db.execute_returning(CONTACT_DELETE_SQL, {"id": contact_id})
    return get(cur["client_id"])


# ---------------------------------------------------------------------------
# Amallar — hujjatlar
# ---------------------------------------------------------------------------
def documents(client_id: int) -> List[dict]:
    _need_schema2()
    return [_shape_doc(d) for d in db.query(DOCS_SQL, {"id": client_id})]


def docs_for_compliance(client_id: int) -> List[dict]:
    """Cheklist uchun XOM qatorlar (sana obyektlari bilan, ISO satr emas):
    `compliance.build_checklist()` `valid_until` ni `date` deb kutadi.
    main.py shu ro'yxatni compliance.check(..., docs=...) ga uzatadi —
    shu tufayli compliance moduli erp haqida bilmasligicha qoladi."""
    _need_schema2()
    # Mijoz yo'qligini TEKSHIRAMIZ: bo'sh ro'yxat qaytarilsa cheklist
    # "hamma hujjat yetishmayapti" deb ko'rsatardi — noto'g'ri client_id
    # yuborilgani esa umuman sezilmasdi. Yo'q mijoz — 404, bo'sh javob emas.
    if not db.query_one(CLIENT_GET_SQL, {"id": client_id}):
        raise ErpError("Mijoz topilmadi.", 404)
    return db.query(DOCS_SQL, {"id": client_id})


def add_document(client_id: int, data: dict) -> dict:
    _need_schema2()
    if not _clean(data.get("doc_type")) or not _clean(data.get("name")):
        raise ErpError("Hujjat turi va nomi majburiy.")
    if not db.query_one(CLIENT_GET_SQL, {"id": client_id}):
        raise ErpError("Mijoz topilmadi.", 404)
    row = db.execute_returning(DOC_INSERT_SQL, {
        **_params(data, DOC_FIELDS), "client_id": client_id})
    return _shape_doc(row)


def update_document(doc_id: int, data: dict) -> dict:
    _need_schema2()
    if not _clean(data.get("doc_type")) or not _clean(data.get("name")):
        raise ErpError("Hujjat turi va nomi majburiy.")
    row = db.execute_returning(DOC_UPDATE_SQL, {**_params(data, DOC_FIELDS), "id": doc_id})
    if not row:
        raise ErpError("Hujjat topilmadi.", 404)
    return _shape_doc(row)


def delete_document(doc_id: int) -> None:
    _need_schema2()
    if not db.execute_returning(DOC_DELETE_SQL, {"id": doc_id}):
        raise ErpError("Hujjat topilmadi.", 404)


# --- shablon importi --------------------------------------------------------
# Bir korxonaning 10 ta hujjatini formadan kiritish — bazani birinchi marta
# to'ldirishdagi eng katta to'siq. Shablon uni bir faylga aylantiradi.
#
# CHEGARA: faylni O'QISH va tekshirish tender-ai'da (`parse_documents`),
# YOZISH shu yerda. Parser ikki joyda bo'lmaydi, hujjatlar esa ERP bazasida
# qoladi.

DOC_FIND_SQL = """
SELECT id FROM erp.client_document
WHERE client_id = %(client_id)s AND doc_type = %(doc_type)s
  AND lower(name) = lower(%(name)s)
ORDER BY id LIMIT 1
"""


def import_documents(client_id: int, rows: List[Dict[str, Any]],
                     dry_run: bool = True) -> Dict[str, int]:
    """Tozalangan qatorlarni mijoz hujjatlariga yozadi.

    TUR + NOM bo'yicha mavjudi YANGILANADI, yo'g'i qo'shiladi — shablon
    ikkinchi marta yuklanganda takror yozuv paydo bo'lmasin (kompaniya
    hujjatlari importidagi qoida bilan bir xil).

    dry_run=True — bazaga tegmaydi, faqat "nechtasi qo'shiladi / nechtasi
    yangilanadi" ni hisoblaydi.
    """
    _need_schema2()
    if not db.query_one(CLIENT_GET_SQL, {"id": client_id}):
        raise ErpError("Mijoz topilmadi.", 404)

    inserted = updated = 0
    for r in rows:
        params = {"client_id": client_id,
                  **{k: r.get(k) for k in DOC_FIELDS}}
        if not _clean(params.get("doc_type")) or not _clean(params.get("name")):
            continue                    # parser buni allaqachon xato deb belgilagan
        found = db.query_one(DOC_FIND_SQL, params)
        if found:
            updated += 1
            if not dry_run:
                db.execute_returning(DOC_UPDATE_SQL, {**params, "id": found["id"]})
        else:
            inserted += 1
            if not dry_run:
                db.execute_returning(DOC_INSERT_SQL, params)
    return {"inserted": inserted, "updated": updated}
