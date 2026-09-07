"""
DALOLATNOMA (akt) — bajarilgan ish / topshirilgan tovar.

Faktura "qancha to'lash kerak" deydi, dalolatnoma esa "ish BAJARILDI"
deydi. Bular ikki xil fakt: to'lov nizosida "pulni to'ladim" bilan
"ishni oldim" boshqa-boshqa dalil.

HISOB-KITOB FAKTURANIKI BILAN BIR XIL KOD (`invoice.line_totals` /
`invoice.totals`). Bu ataylab: ikki xil yaxlitlash ikki xil summa degani
bo'lardi va aktdagi son fakturadagidan bir tiyinga farq qilib turardi —
buxgalter buni xato deb hisoblardi.

Fakturadagi UCH QOIDA bu yerda ham amal qiladi:
  1. rekvizitlar SNAPSHOT;
  2. summalar SAQLANMAYDI (qatorlardan hisoblanadi);
  3. `draft` dan chiqqach hujjat MUZLAYDI.

FAKTURAGA BOG'LANISH IXTIYORIY: akt fakturasiz ham bo'ladi (bosqichma-
bosqich topshirish), faktura ham aktsiz (oldindan to'lov). Lekin odatda
ikkalasi juftlik bo'lib yuradi — shuning uchun `from_invoice()` bor.

YUBORISH bu yerda ham YO'Q: O'zbekistonda dalolatnoma ham elektron
shaklda operator orqali yuboriladi. ERP ma'lumotni saqlaydi va bosma
shaklni beradi (`api/erp/invoice_export.py` dagi izohga qarang).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp import invoice as inv_mod
from api.erp.opportunity import ErpError

# Holatlar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_12.sql).
STATUSES = [
    ("draft",     "Qoralama"),
    ("issued",    "Chiqarildi"),
    ("signed",    "Imzolandi"),
    ("cancelled", "Bekor qilindi"),
]
STATUS_LABEL = dict(STATUSES)

#: Qatorlar TAHRIRLANADIGAN holat.
EDITABLE = "draft"


SCHEMA_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'act'
"""

_READY = False


def schema_ready() -> bool:
    global _READY
    if _READY:
        return True
    _READY = bool(db.query_one(SCHEMA_CHECK_SQL))
    return _READY


def _need_schema() -> None:
    if not schema_ready():
        raise ErpError("Dalolatnoma jadvallari yo'q: schema_patch_erp_12.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
ACT_COLS = """
a.id, a.invoice_id, a.contract_id, a.opportunity_id, a.client_id, a.number,
a.act_date, a.period_from, a.period_to, a.currency, a.status,
a.status_changed_at, a.signed_at,
a.client_name, a.client_inn, a.client_address, a.client_director,
a.own_name, a.own_inn, a.own_address, a.own_director,
a.note, a.created_by, a.created_at, a.updated_at
"""

ACT_GET_SQL = f"""
SELECT {ACT_COLS}, i.number AS invoice_number, k.number AS contract_number,
       o.title AS opportunity_name
FROM erp.act a
LEFT JOIN erp.invoice i     ON i.id = a.invoice_id
LEFT JOIN erp.contract k    ON k.id = a.contract_id
LEFT JOIN erp.opportunity o ON o.id = a.opportunity_id
WHERE a.id = %(id)s
"""

ACT_LIST_SQL = f"""
SELECT {ACT_COLS}, i.number AS invoice_number, k.number AS contract_number,
       o.title AS opportunity_name
FROM erp.act a
LEFT JOIN erp.invoice i     ON i.id = a.invoice_id
LEFT JOIN erp.contract k    ON k.id = a.contract_id
LEFT JOIN erp.opportunity o ON o.id = a.opportunity_id
WHERE (%(status)s::text IS NULL OR a.status = %(status)s)
  AND (%(client_id)s::int IS NULL OR a.client_id = %(client_id)s)
  AND (%(invoice_id)s::int IS NULL OR a.invoice_id = %(invoice_id)s)
  AND (%(opportunity_id)s::int IS NULL OR a.opportunity_id = %(opportunity_id)s)
  -- EGALIK — fakturadagi bilan bir xil qoida (api/erp/egalik.py).
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s
       OR (a.opportunity_id IS NULL AND EXISTS (
             SELECT 1 FROM erp.opportunity oo
              WHERE oo.client_id = a.client_id
                AND oo.broker_id = %(owner_broker_id)s)))
ORDER BY a.act_date DESC NULLS FIRST, a.id DESC
"""

ACT_INSERT_SQL = """
INSERT INTO erp.act
    (invoice_id, contract_id, opportunity_id, client_id, number, act_date,
     period_from, period_to, currency, note, created_by,
     client_name, client_inn, client_address, client_director,
     own_name, own_inn, own_address, own_director)
VALUES
    (%(invoice_id)s, %(contract_id)s, %(opportunity_id)s, %(client_id)s,
     %(number)s, %(act_date)s, %(period_from)s, %(period_to)s, %(currency)s,
     %(note)s, %(created_by)s,
     %(client_name)s, %(client_inn)s, %(client_address)s, %(client_director)s,
     %(own_name)s, %(own_inn)s, %(own_address)s, %(own_director)s)
RETURNING id
"""

ACT_UPDATE_SQL = """
UPDATE erp.act SET
    number = %(number)s, act_date = %(act_date)s,
    period_from = %(period_from)s, period_to = %(period_to)s,
    currency = %(currency)s, note = %(note)s, updated_at = now()
WHERE id = %(id)s
RETURNING id
"""

ACT_STATUS_SQL = """
UPDATE erp.act
SET status = %(status)s, status_changed_at = now(),
    signed_at = COALESCE(%(signed_at)s, signed_at), updated_at = now()
WHERE id = %(id)s
RETURNING id
"""

LINES_SQL = ("SELECT id, act_id, pos, product_id, name, unit, qty, price, "
             "vat_rate, note FROM erp.act_line "
             "WHERE act_id = %(id)s ORDER BY pos, id")

LINE_INSERT_SQL = """
INSERT INTO erp.act_line
    (act_id, pos, product_id, name, unit, qty, price, vat_rate, note)
VALUES (%(act_id)s, %(pos)s, %(product_id)s, %(name)s, %(unit)s,
        %(qty)s, %(price)s, %(vat_rate)s, %(note)s)
RETURNING id
"""

LINE_DELETE_SQL = ("DELETE FROM erp.act_line WHERE id = %(id)s "
                   "AND act_id = %(act_id)s RETURNING id")

CLIENT_SQL = """
SELECT id, name, inn, address_legal, address_actual, director_name
FROM erp.client_company WHERE id = %(id)s
"""

OWN_SQL = """
SELECT name, inn, address_legal, address_actual, director_name
FROM erp.own_company LIMIT 1
"""


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def shape_line(r: Dict[str, Any]) -> Dict[str, Any]:
    """Faktura qatori bilan AYNAN bir xil hisob (`invoice.shape_line`)."""
    return inv_mod.shape_line({**r, "invoice_id": r["act_id"]})


def shape(r: Dict[str, Any], *, lines=None) -> Dict[str, Any]:
    out = {
        "id": r["id"], "invoice_id": r["invoice_id"],
        "invoice_number": r.get("invoice_number"),
        "contract_id": r["contract_id"],
        "contract_number": r.get("contract_number"),
        "opportunity_id": r["opportunity_id"],
        "opportunity_name": r.get("opportunity_name"),
        "client_id": r["client_id"], "number": r["number"],
        "act_date": inv_mod._iso(r["act_date"]),
        "period_from": inv_mod._iso(r["period_from"]),
        "period_to": inv_mod._iso(r["period_to"]),
        "currency": r["currency"], "status": r["status"],
        "status_label": STATUS_LABEL.get(r["status"]),
        "status_changed_at": inv_mod._iso(r["status_changed_at"]),
        "signed_at": inv_mod._iso(r["signed_at"]),
        "editable": r["status"] == EDITABLE,
        "client": {
            "name": r["client_name"], "inn": r["client_inn"],
            "address": r["client_address"], "director": r["client_director"],
        },
        "own": {
            "name": r["own_name"], "inn": r["own_inn"],
            "address": r["own_address"], "director": r["own_director"],
        },
        "note": r["note"], "created_by": r["created_by"],
        "created_at": inv_mod._iso(r["created_at"]),
        "updated_at": inv_mod._iso(r["updated_at"]),
    }
    if lines is not None:
        out["lines"] = [shape_line(x) for x in lines]
        t = inv_mod.totals(lines)
        out["totals"] = {
            "net": float(t["net"]), "vat": float(t["vat"]),
            "total": float(t["total"]),
            "words": inv_mod.amount_words(t["total"], r["currency"]),
        }
    return out


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def list_(status: Optional[str] = None, client_id: Optional[int] = None,
          invoice_id: Optional[int] = None,
          opportunity_id: Optional[int] = None,
          owner_broker_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _need_schema()
    if status and status not in STATUS_LABEL:
        raise ErpError("Noma'lum status.")
    out = []
    for r in db.query(ACT_LIST_SQL, {"status": status, "client_id": client_id,
                                     "invoice_id": invoice_id,
                                     "opportunity_id": opportunity_id,
                                     "owner_broker_id": owner_broker_id}):
        out.append(shape(r, lines=db.query(LINES_SQL, {"id": r["id"]})))
    return out


def get(act_id: int) -> Dict[str, Any]:
    _need_schema()
    r = db.query_one(ACT_GET_SQL, {"id": act_id})
    if not r:
        raise ErpError("Dalolatnoma topilmadi.", 404)
    return shape(r, lines=db.query(LINES_SQL, {"id": act_id}))


def _editable(a: Dict[str, Any]) -> None:
    if a["status"] != EDITABLE:
        raise ErpError(
            f"Dalolatnoma '{STATUS_LABEL.get(a['status'])}' holatida — "
            f"tahrirlanmaydi. Xato bo'lsa bekor qiling va yangisini "
            f"chiqaring.", 409)


def create(data: Dict[str, Any]) -> Dict[str, Any]:
    """Yangi dalolatnoma (qoralama). Rekvizitlar SHU PAYTDA ko'chiriladi."""
    _need_schema()
    client_id = data.get("client_id")
    if not client_id:
        raise ErpError("Mijoz tanlanmagan.")
    cl = db.query_one(CLIENT_SQL, {"id": client_id})
    if not cl:
        raise ErpError("Mijoz topilmadi.", 404)

    own = db.query_one(OWN_SQL) or {}
    # Kim o'zgartirgani `erp.doc_audit` ga trigger orqali yoziladi —
    # ism `actor=` bilan beriladi (izoh: `invoice.py`).
    row = db.execute_returning(ACT_INSERT_SQL, actor=data.get("created_by"),
                               params={
        "invoice_id": data.get("invoice_id"),
        "contract_id": data.get("contract_id"),
        "opportunity_id": data.get("opportunity_id"),
        "client_id": client_id, "number": (data.get("number") or None),
        "act_date": data.get("act_date"),
        "period_from": data.get("period_from"),
        "period_to": data.get("period_to"),
        "currency": (data.get("currency") or "UZS").strip().upper(),
        "note": data.get("note"), "created_by": data.get("created_by"),
        "client_name": cl["name"], "client_inn": cl["inn"],
        "client_address": cl["address_legal"] or cl["address_actual"],
        "client_director": cl["director_name"],
        "own_name": own.get("name"), "own_inn": own.get("inn"),
        "own_address": own.get("address_legal") or own.get("address_actual"),
        "own_director": own.get("director_name")})
    return get(row["id"])


def from_invoice(invoice_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Fakturadan dalolatnoma: qatorlar KO'CHIRILADI.

    Nega ko'chiriladi, bog'lanmaydi: faktura keyin bekor qilinishi yoki
    o'zgarishi mumkin (yangisi chiqariladi), dalolatnoma esa BAJARILGAN
    ishning dalili va u o'z holicha turishi kerak. Bog'lanish (`invoice_id`)
    faqat "qaysi faktura bilan juft" degan savol uchun.

    QORALAMA fakturadan akt chiqarilmaydi: hali chiqarilmagan hujjat
    bo'yicha "ish bajarildi" deb yozish mantiqsiz."""
    _need_schema()
    inv = inv_mod.get(invoice_id)
    if inv["status"] == "draft":
        raise ErpError("Qoralama fakturadan dalolatnoma chiqarilmaydi — "
                       "avval fakturani chiqaring.", 409)
    if inv["status"] == "cancelled":
        raise ErpError("Bekor qilingan fakturadan dalolatnoma "
                       "chiqarilmaydi.", 409)

    act = create({
        "client_id": inv["client_id"], "invoice_id": invoice_id,
        "contract_id": inv["contract_id"],
        "opportunity_id": inv["opportunity_id"],
        "number": data.get("number"), "act_date": data.get("act_date"),
        "period_from": data.get("period_from"),
        "period_to": data.get("period_to"),
        "currency": inv["currency"], "note": data.get("note"),
        "created_by": data.get("created_by")})

    for i, ln in enumerate(inv.get("lines") or [], start=1):
        db.execute_returning(LINE_INSERT_SQL, actor=data.get("created_by"),
                             params={
            "act_id": act["id"], "pos": i, "product_id": ln["product_id"],
            "name": ln["name"], "unit": ln["unit"], "qty": ln["qty"],
            "price": ln["price"], "vat_rate": ln["vat_rate"],
            "note": ln["note"]})

    out = get(act["id"])
    out["filled"] = {"lines": len(inv.get("lines") or []),
                     "invoice_number": inv["number"]}
    return out


def update(act_id: int, data: Dict[str, Any],
           actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(ACT_GET_SQL, {"id": act_id})
    if not cur:
        raise ErpError("Dalolatnoma topilmadi.", 404)
    _editable(cur)
    db.execute_returning(ACT_UPDATE_SQL, actor=actor, params={
        "id": act_id, "number": (data.get("number") or None),
        "act_date": data.get("act_date") or cur["act_date"],
        "period_from": data.get("period_from"),
        "period_to": data.get("period_to"),
        "currency": (data.get("currency") or cur["currency"]).strip().upper(),
        "note": data.get("note")})
    return get(act_id)


def add_line(act_id: int, data: Dict[str, Any],
             actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(ACT_GET_SQL, {"id": act_id})
    if not cur:
        raise ErpError("Dalolatnoma topilmadi.", 404)
    _editable(cur)

    name = (data.get("name") or "").strip()
    if not name:
        raise ErpError("Qator nomi bo'sh.")
    qty = inv_mod._dec(data.get("qty"), "qty")
    price = inv_mod._dec(data.get("price"), "price")
    if qty <= 0:
        raise ErpError("Miqdor musbat bo'lishi kerak.")
    if price < 0:
        raise ErpError("Narx manfiy bo'lolmaydi.")
    rate = data.get("vat_rate")
    rate = (inv_mod.default_vat_rate(cur["client_id"]) if rate is None
            else inv_mod._dec(rate, "vat_rate"))
    if rate < 0:
        raise ErpError("QQS stavkasi manfiy bo'lolmaydi.")

    pos = data.get("pos")
    if pos is None:
        pos = (db.scalar("SELECT COALESCE(max(pos), 0) + 1 FROM erp.act_line "
                         "WHERE act_id = %(id)s", {"id": act_id}) or 1)

    db.execute_returning(LINE_INSERT_SQL, actor=actor, params={
        "act_id": act_id, "pos": pos, "product_id": data.get("product_id"),
        "name": name, "unit": (data.get("unit") or None), "qty": qty,
        "price": price, "vat_rate": rate,
        "note": (data.get("note") or None)})
    return get(act_id)


def delete_line(act_id: int, line_id: int,
                actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(ACT_GET_SQL, {"id": act_id})
    if not cur:
        raise ErpError("Dalolatnoma topilmadi.", 404)
    _editable(cur)
    if not db.execute_returning(LINE_DELETE_SQL, actor=actor,
                                params={"id": line_id, "act_id": act_id}):
        raise ErpError("Qator topilmadi.", 404)
    return get(act_id)


def set_status(act_id: int, status: str, signed_at=None,
               actor: Optional[str] = None) -> Dict[str, Any]:
    """Holatni o'zgartirish.

    `issued` va `signed` uchun hujjat TO'LIQ bo'lishi kerak: raqam, sana
    va kamida bitta qator. `signed` — aktning maqsadi, shuning uchun
    imzo sanasi ham so'raladi (berilmasa akt sanasi olinadi)."""
    _need_schema()
    if status not in STATUS_LABEL:
        raise ErpError("Noma'lum status.")
    cur = db.query_one(ACT_GET_SQL, {"id": act_id})
    if not cur:
        raise ErpError("Dalolatnoma topilmadi.", 404)
    if cur["status"] == status:
        return get(act_id)
    if cur["status"] == "cancelled":
        raise ErpError("Bekor qilingan dalolatnomani qaytarib bo'lmaydi — "
                       "yangisini chiqaring.", 409)

    if status in ("issued", "signed"):
        missing = []
        if not cur["number"]:
            missing.append("raqam")
        if not cur["act_date"]:
            missing.append("sana")
        if not db.query(LINES_SQL, {"id": act_id}):
            missing.append("kamida bitta qator")
        if missing:
            raise ErpError("Chiqarish uchun yetishmayapti: "
                           + ", ".join(missing) + ".")

    db.execute_returning(ACT_STATUS_SQL, actor=actor, params={
        "id": act_id, "status": status,
        # Imzolanganda sana MAJBURIY: aktning butun ma'nosi "qachon
        # topshirildi" degan savolda.
        "signed_at": (signed_at or cur["act_date"]) if status == "signed"
                     else None})
    return get(act_id)
