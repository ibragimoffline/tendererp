"""
OMBOR — harakatlar jurnali va qoldiq (5B-1).

QAROR (`erp_arxitektura_3.md` 4.3, 6.1): qoldiqning EGASI — ERP.
Tender-AI qoldiqni `erp.v_stock_balance` view idan o'qiydi va o'zining
`catalog_product.stock_qty` ustuniga tayanmaydi ("A1" yo'li). Shu tufayli
`public.*` ga yozmaslik qoidasi buzilmaydi.

NEGA JURNAL, "qoldiq" USTUNI EMAS: qoldiq — hisob natijasi. Ustun bo'lsa
"nega 12 dona?" degan savolga javob yo'q; jurnal bo'lsa har o'zgarish kim,
qachon va nima uchun deb yozilgan.

MAHSULOT KATALOGI TENDER-AI DA (`public.catalog_product`) — u yerda
moslashtirish va bildirishnoma uchun ishlatiladi, ikkinchi nusxasi kerak
emas. Bu modul undan FAQAT O'QIYDI (nom, o'lchov birligi), yozmaydi.
Harakat yozilganda nom SNAPSHOT qilinadi: mahsulot o'chirilsa ham ombor
tarixi o'qiladigan bo'lib qoladi (kartadagi tender snapshoti bilan bir xil
sabab).

REZERV — TO'RTINCHI HOLAT. Jurnal "nima kirdi, nima chiqdi" deydi,
lekin tender ustida ishlaganda tovar HALI CHIQMAGAN, ammo boshqa
tenderga va'da qilib bo'lmaydi. Buni chiqim bilan yozib qo'yish xato
bo'lardi: omborda tovar turibdi, jurnalda esa yo'q. Shuning uchun rezerv
qoldiqni KAMAYTIRMAYDI, MAVJUD miqdorni kamaytiradi
(mavjud = qoldiq - rezerv) va u kartaning statusiga bog'langan.

MANFIY QOLDIQ TAQIQLANMAYDI, OGOHLANTIRILADI. Haqiqiy omborda hujjat
kechikadi: tovar chiqib ketgan, kirim qog'ozi ertaga keladi. Taqiq
qo'yilsa odam raqamni "to'g'rilab" yozardi va jurnal yolg'onga aylanardi.
Shuning uchun chiqim o'tadi, lekin javobda `warning` qaytadi va interfeys
uni ko'rsatadi.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError

# Harakat turlari — bazadagi CHECK bilan BIR XIL ro'yxat
# (schema_patch_erp_8.sql). Sinov ikkalasini solishtiradi.
KINDS = [
    ("opening", "Boshlang'ich qoldiq"),
    ("in",      "Kirim"),
    ("out",     "Chiqim"),
    ("adjust",  "Tuzatish (inventarizatsiya)"),
]
KIND_LABEL = dict(KINDS)

#: Kirim musbat, chiqim manfiy. `adjust` ikki tomonga ham bo'lishi mumkin —
#: uning ishorasi chaqiruvchidan keladi.
SIGN = {"opening": 1, "in": 1, "out": -1}

# --- REZERV ------------------------------------------------------------------
# Holatlar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_10.sql).
RESERVE_STATES = [
    ("held",     "Ushlab turilibdi"),
    ("consumed", "Sarflandi"),
    ("released", "Bo'shatildi"),
]
RESERVE_LABEL = dict(RESERVE_STATES)

#: Rezerv QAYSI STATUSDA qo'yiladi. Undan oldin karta hali "bizniki"
#: emas — qatnashish tasdiqlanmagan, ya'ni tovarni band qilish erta.
RESERVE_FROM = "confirmed"

#: Rezerv qo'yish mumkin bo'lgan statuslar: tasdiqlangandan yakuniygacha.
#: Ro'yxat `opportunity.STATUSES` tartibiga tayanadi — u yerda status
#: qo'shilsa bu yer ham o'zi to'g'rilanadi.
def _reservable_statuses() -> set:
    from api.erp.opportunity import FINAL, STATUSES
    codes = [c for c, _ in STATUSES]
    i = codes.index(RESERVE_FROM)
    return {c for c in codes[i:] if c not in FINAL}


SCHEMA_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'stock_move'
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
        raise ErpError("Ombor jadvali yo'q: schema_patch_erp_8.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
# Katalog TENDER-AI da: LEFT JOIN bilan qo'shamiz, chunki mahsulot
# o'chirilgan bo'lsa ham qoldiq ko'rinishi kerak (jurnal qoladi).
BALANCE_SQL = """
SELECT b.product_id, b.product_name, b.unit, b.qty, b.reserved, b.available,
       b.updated_at, b.move_count, b.reserve_count,
       p.id IS NOT NULL          AS in_catalog,
       p.name                    AS catalog_name,
       p.stock_qty               AS import_qty,
       p.stock_updated_at        AS import_at
FROM erp.v_stock_balance b
LEFT JOIN public.catalog_product p ON p.id = b.product_id
ORDER BY b.product_name
"""

# Katalogda bor, lekin omborda hali bitta ham harakati yo'q mahsulotlar.
# Ular ham ko'rsatiladi: "qoldiq kiritilmagan" — bu ham ma'lumot.
CATALOG_ONLY_SQL = """
SELECT p.id AS product_id, p.name AS product_name,
       COALESCE(p.stock_unit, p.unit) AS unit,
       p.stock_qty AS import_qty, p.stock_updated_at AS import_at
FROM public.catalog_product p
WHERE NOT EXISTS (SELECT 1 FROM erp.stock_move m WHERE m.product_id = p.id)
ORDER BY p.name
"""

PRODUCT_SQL = """
SELECT id, name, COALESCE(stock_unit, unit) AS unit, stock_qty,
       stock_updated_at, cost_price
FROM public.catalog_product WHERE id = %(id)s
"""

BALANCE_ONE_SQL = ("SELECT product_id, product_name, unit, qty, reserved, "
                   "available, updated_at, move_count, reserve_count "
                   "FROM erp.v_stock_balance WHERE product_id = %(id)s")

MOVES_SQL = """
SELECT m.id, m.product_id, m.product_name, m.unit, m.kind, m.qty,
       m.opportunity_id, m.doc_ref, m.note, m.created_by, m.created_at,
       m.unit_cost, o.title AS opportunity_name
FROM erp.stock_move m
LEFT JOIN erp.opportunity o ON o.id = m.opportunity_id
WHERE (%(product_id)s::int IS NULL OR m.product_id = %(product_id)s)
  AND (%(opportunity_id)s::int IS NULL OR m.opportunity_id = %(opportunity_id)s)
ORDER BY m.created_at DESC, m.id DESC
LIMIT %(limit)s
"""

# TANNARX harakat paytida MUZLATILADI (`unit_cost`): katalogdagi narx
# o'zgarsa, o'tgan chiqimlarning foydasi qayta hisoblanib ketmasin.
MOVE_INSERT_SQL = """
INSERT INTO erp.stock_move
    (product_id, product_name, unit, kind, qty, opportunity_id, doc_ref,
     note, created_by, unit_cost)
VALUES
    (%(product_id)s, %(product_name)s, %(unit)s, %(kind)s, %(qty)s,
     %(opportunity_id)s, %(doc_ref)s, %(note)s, %(created_by)s,
     %(unit_cost)s)
RETURNING id
"""

#: Katalogdagi joriy tannarx. Topilmasa `NULL` qoladi — NOL EMAS.
COST_SQL = ("SELECT cost_price FROM public.catalog_product "
            "WHERE id = %(id)s")


def _unit_cost(product_id) -> Optional[Any]:
    """Harakat paytidagi tannarx. Katalogda yo'q bo'lsa `None`.

    Nolga aylantirmaymiz: nol "tekin keldi" degani, `None` esa
    "bilmaymiz" — foyda hisobi bu ikkisini ajratadi."""
    r = db.query_one(COST_SQL, {"id": product_id})
    return r["cost_price"] if r else None

MOVE_GET_SQL = """
SELECT m.id, m.product_id, m.product_name, m.unit, m.kind, m.qty,
       m.opportunity_id, m.doc_ref, m.note, m.created_by, m.created_at,
       m.unit_cost, o.title AS opportunity_name
FROM erp.stock_move m
LEFT JOIN erp.opportunity o ON o.id = m.opportunity_id
WHERE m.id = %(id)s
"""

OPENING_EXISTS_SQL = ("SELECT id FROM erp.stock_move "
                      "WHERE product_id = %(id)s AND kind = 'opening'")

RESERVES_SQL = """
SELECT r.id, r.opportunity_id, r.product_id, r.product_name, r.unit, r.qty,
       r.status, r.move_id, r.note, r.created_by, r.created_at,
       r.closed_at, r.closed_by,
       o.title AS opportunity_name, o.status AS opportunity_status
FROM erp.stock_reserve r
JOIN erp.opportunity o ON o.id = r.opportunity_id
WHERE (%(opportunity_id)s::int IS NULL OR r.opportunity_id = %(opportunity_id)s)
  AND (%(product_id)s::int IS NULL OR r.product_id = %(product_id)s)
  AND (%(only_held)s IS FALSE OR r.status = 'held')
  -- EGALIK: rezerv KARTAGA qo'yiladi (api/erp/egalik.py).
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s)
ORDER BY r.created_at DESC, r.id DESC
"""

RESERVE_GET_SQL = """
SELECT r.id, r.opportunity_id, r.product_id, r.product_name, r.unit, r.qty,
       r.status, r.move_id, r.note, r.created_by, r.created_at,
       r.closed_at, r.closed_by,
       o.title AS opportunity_name, o.status AS opportunity_status
FROM erp.stock_reserve r
JOIN erp.opportunity o ON o.id = r.opportunity_id
WHERE r.id = %(id)s
"""

RESERVE_INSERT_SQL = """
INSERT INTO erp.stock_reserve
    (opportunity_id, product_id, product_name, unit, qty, note, created_by)
VALUES (%(opportunity_id)s, %(product_id)s, %(product_name)s, %(unit)s,
        %(qty)s, %(note)s, %(created_by)s)
RETURNING id
"""

RESERVE_CLOSE_SQL = """
UPDATE erp.stock_reserve
SET status = %(status)s, move_id = %(move_id)s,
    closed_at = now(), closed_by = %(closed_by)s
WHERE id = %(id)s AND status = 'held'
RETURNING id
"""

HELD_BY_OPP_SQL = ("SELECT id, product_id, product_name, unit, qty "
                   "FROM erp.stock_reserve "
                   "WHERE opportunity_id = %(id)s AND status = 'held' "
                   "ORDER BY id")

#: Shu kartaga ALLAQACHON ajratilgani (mahsulot bo'yicha). Taklifda
#: shuncha ayiriladi — ikkinchi marta ajratib qo'ymaslik uchun.
HELD_BY_PRODUCT_SQL = ("SELECT product_id, SUM(qty) AS qty "
                       "FROM erp.stock_reserve "
                       "WHERE opportunity_id = %(id)s AND status = 'held' "
                       "GROUP BY product_id")

#: Sarflangan rezervlar — yakuniydan QAYTGANDA ular tiklanadi.
CONSUMED_BY_OPP_SQL = ("SELECT id, product_id, product_name, unit, qty, move_id "
                       "FROM erp.stock_reserve "
                       "WHERE opportunity_id = %(id)s AND status = 'consumed' "
                       "ORDER BY id")

RESERVE_REOPEN_SQL = """
UPDATE erp.stock_reserve
SET status = 'held', move_id = NULL, closed_at = NULL, closed_by = NULL
WHERE id = %(id)s
RETURNING id
"""

AVAILABLE_SQL = ("SELECT qty, reserved, available FROM erp.v_stock_balance "
                 "WHERE product_id = %(id)s")

SUM_SQL = ("SELECT COALESCE(SUM(qty), 0) AS qty FROM erp.stock_move "
           "WHERE product_id = %(id)s")


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def _iso(v):
    return v.isoformat() if v is not None else None


def _num(v):
    """NUMERIC -> float. JSON `Decimal` ni bilmaydi."""
    return float(v) if v is not None else None


def shape_move(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "product_id": r["product_id"],
        "product_name": r["product_name"], "unit": r["unit"],
        "kind": r["kind"], "kind_label": KIND_LABEL.get(r["kind"]),
        "qty": _num(r["qty"]),
        "opportunity_id": r["opportunity_id"],
        "opportunity_name": r.get("opportunity_name"),
        "doc_ref": r["doc_ref"], "note": r["note"],
        # Muzlatilgan tannarx. `None` = noma'lum (nol emas).
        "unit_cost": _num(r.get("unit_cost")),
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
    }


def shape_balance(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "product_id": r["product_id"], "product_name": r["product_name"],
        "unit": r["unit"], "qty": _num(r.get("qty")) or 0.0,
        # Rezerv qoldiqni kamaytirmaydi, MAVJUD miqdorni kamaytiradi.
        "reserved": _num(r.get("reserved")) or 0.0,
        "available": (_num(r.get("available"))
                      if r.get("available") is not None
                      else (_num(r.get("qty")) or 0.0)),
        "reserve_count": r.get("reserve_count") or 0,
        "updated_at": _iso(r.get("updated_at")),
        "move_count": r.get("move_count") or 0,
        # Katalogdan o'chirilganmi (jurnal qoladi, lekin buni ko'rsatamiz).
        "in_catalog": bool(r.get("in_catalog", True)),
        # Tender-AI ga IMPORT qilingan eski qoldiq — solishtirish uchun.
        # Endi u HAQIQAT MANBAI EMAS, faqat ma'lumot.
        "import_qty": _num(r.get("import_qty")),
        "import_at": _iso(r.get("import_at")),
    }


def shape_reserve(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"],
        "opportunity_name": r.get("opportunity_name"),
        "opportunity_status": r.get("opportunity_status"),
        "product_id": r["product_id"], "product_name": r["product_name"],
        "unit": r["unit"], "qty": _num(r["qty"]),
        "status": r["status"], "status_label": RESERVE_LABEL.get(r["status"]),
        "move_id": r["move_id"], "note": r["note"],
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
        "closed_at": _iso(r["closed_at"]), "closed_by": r["closed_by"],
    }


def _qty(raw: Any) -> Decimal:
    try:
        q = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ErpError("Miqdor son bo'lishi kerak.")
    if q == 0:
        raise ErpError("Miqdor noldan farqli bo'lishi kerak.")
    return q


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def balances(*, include_empty: bool = True) -> Dict[str, Any]:
    """Qoldiqlar ro'yxati.

    `include_empty` — katalogda bor, lekin harakati yo'q mahsulotlar ham
    qo'shiladi: "qoldiq kiritilmagan" ham ma'lumot va uni yashirish
    omborni to'liq ko'rinmaydigan qiladi."""
    _need_schema()
    rows = [shape_balance(r) for r in db.query(BALANCE_SQL)]
    if include_empty:
        for r in db.query(CATALOG_ONLY_SQL):
            rows.append(shape_balance({**r, "qty": 0, "updated_at": None,
                                       "move_count": 0, "in_catalog": True}))
        rows.sort(key=lambda x: (x["product_name"] or "").lower())
    return {
        "items": rows,
        "kinds": [{"code": c, "label": l} for c, l in KINDS],
        # Manfiy qoldiq — taqiq emas, lekin ko'rinib tursin.
        "negative": [r["product_id"] for r in rows if (r["qty"] or 0) < 0],
        # Rezerv qoldiqdan OSHIB ketgan mahsulotlar: jismonan bor, lekin
        # hammasi band. Bu ham taqiq emas — ko'rinib tursin.
        "over_reserved": [r["product_id"] for r in rows
                          if (r["available"] or 0) < 0 <= (r["qty"] or 0)],
        "reserve_states": [{"code": c, "label": l} for c, l in RESERVE_STATES],
    }


def product(product_id: int) -> Dict[str, Any]:
    """Bitta mahsulot: qoldiq + harakatlar tarixi."""
    _need_schema()
    bal = db.query_one(BALANCE_ONE_SQL, {"id": product_id})
    cat = db.query_one(PRODUCT_SQL, {"id": product_id})
    if not bal and not cat:
        raise ErpError("Mahsulot topilmadi.", 404)
    if not bal:
        bal = {"product_id": product_id, "product_name": cat["name"],
               "unit": cat["unit"], "qty": 0, "updated_at": None,
               "move_count": 0}
    out = shape_balance({**bal,
                         "in_catalog": cat is not None,
                         "import_qty": cat["stock_qty"] if cat else None,
                         "import_at": cat["stock_updated_at"] if cat else None})
    out["moves"] = moves(product_id=product_id)
    out["reserves"] = reserves(product_id=product_id)
    return out


def moves(*, product_id: Optional[int] = None,
          opportunity_id: Optional[int] = None,
          limit: int = 200) -> List[Dict[str, Any]]:
    _need_schema()
    return [shape_move(r) for r in db.query(MOVES_SQL, {
        "product_id": product_id, "opportunity_id": opportunity_id,
        "limit": max(1, min(limit, 1000))})]


def add_move(data: Dict[str, Any]) -> Dict[str, Any]:
    """Yangi harakat. `qty` MUSBAT keladi — ishorani shu funksiya qo'yadi.

    Chaqiruvchi `created_by` ni sessiyadan beradi (mijozdan qabul
    qilinmaydi)."""
    _need_schema()
    kind = (data.get("kind") or "").strip()
    if kind not in KIND_LABEL:
        raise ErpError("Noma'lum harakat turi.")

    pid = data.get("product_id")
    if not pid:
        raise ErpError("Mahsulot tanlanmagan.")
    cat = db.query_one(PRODUCT_SQL, {"id": pid})
    # Mahsulot katalogdan o'chirilgan bo'lsa nomni jurnaldan olamiz —
    # eski qoldiqni tuzatish imkoni yo'qolmasin.
    last = db.query_one(BALANCE_ONE_SQL, {"id": pid})
    if not cat and not last:
        raise ErpError("Bunday mahsulot katalogda ham, omborda ham yo'q.", 404)

    q = _qty(data.get("qty"))
    if kind == "adjust":
        # Tuzatishda ishora MA'NO tashiydi (kam chiqdi / ko'p chiqdi),
        # shuning uchun uni chaqiruvchidan olamiz.
        signed = q
        if not (data.get("note") or "").strip():
            # Tuzatish sababsiz bo'lsa jurnal o'z ma'nosini yo'qotadi.
            raise ErpError("Tuzatish uchun sabab (izoh) majburiy.")
    else:
        if q < 0:
            raise ErpError("Miqdor musbat bo'lishi kerak.")
        signed = q * SIGN[kind]

    if kind == "opening" and db.query_one(OPENING_EXISTS_SQL, {"id": pid}):
        raise ErpError("Bu mahsulotga boshlang'ich qoldiq allaqachon "
                       "kiritilgan. Tuzatish uchun 'adjust' ishlating.", 409)

    row = db.execute_returning(MOVE_INSERT_SQL, {
        "product_id": pid,
        "product_name": (cat["name"] if cat else last["product_name"]),
        "unit": (cat["unit"] if cat else last["unit"]),
        "kind": kind, "qty": signed,
        "opportunity_id": data.get("opportunity_id"),
        "doc_ref": (data.get("doc_ref") or None),
        "note": (data.get("note") or None),
        "created_by": data.get("created_by"),
        # Tannarx SHU PAYTDA muzlatiladi.
        "unit_cost": (cat["cost_price"] if cat else None)})

    out = shape_move(db.query_one(MOVE_GET_SQL, {"id": row["id"]}))
    out["balance"] = _num(db.scalar(SUM_SQL, {"id": pid}))
    # Manfiy qoldiq TAQIQ EMAS — hujjat kechikishi normal hol. Lekin
    # jimgina qoldirilmaydi.
    out["warning"] = ("Qoldiq manfiy bo'lib qoldi — kirim hujjati "
                      "kiritilmagan bo'lishi mumkin."
                      if (out["balance"] or 0) < 0 else None)
    return out


def seed_opening(created_by: Optional[str] = None) -> Dict[str, Any]:
    """Tender-AI ga IMPORT qilingan qoldiqlarni boshlang'ich harakat
    sifatida ko'chiradi (bir martalik, idempotent).

    NEGA KERAK: ombor ishga tushganda nol qoldiqdan boshlanmasin. Excel
    importi allaqachon `catalog_product.stock_qty` ni to'ldirgan bo'lishi
    mumkin; shu son "boshlang'ich qoldiq" harakatiga aylanadi va shundan
    keyin HAQIQAT MANBAI jurnal bo'ladi.

    Idempotent: `stock_move_opening_uq` tufayli ikkinchi marta yurganda
    hech narsa qo'shilmaydi."""
    _need_schema()
    made, skipped = [], []
    for p in db.query("SELECT id, name, COALESCE(stock_unit, unit) AS unit, "
                      "stock_qty FROM public.catalog_product "
                      "WHERE stock_qty IS NOT NULL AND stock_qty <> 0 "
                      "ORDER BY id"):
        if db.query_one(OPENING_EXISTS_SQL, {"id": p["id"]}):
            skipped.append(p["id"])
            continue
        db.execute_returning(MOVE_INSERT_SQL, {
            "product_id": p["id"], "product_name": p["name"],
            "unit": p["unit"], "kind": "opening", "qty": p["stock_qty"],
            "opportunity_id": None, "doc_ref": None,
            "note": "Tender-AI import qoldig'idan ko'chirildi",
            "created_by": created_by, "unit_cost": _unit_cost(p["id"])})
        made.append(p["id"])
    return {"created": made, "skipped": skipped}


# ---------------------------------------------------------------------------
# REZERV
# ---------------------------------------------------------------------------
def reserves(*, opportunity_id: Optional[int] = None,
             product_id: Optional[int] = None,
             only_held: bool = False,
             owner_broker_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _need_schema()
    return [shape_reserve(r) for r in db.query(RESERVES_SQL, {
        "opportunity_id": opportunity_id, "product_id": product_id,
        "only_held": bool(only_held), "owner_broker_id": owner_broker_id})]


def add_reserve(opportunity_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Kartaga rezerv qo'yish.

    Miqdor MUSBAT. Mavjuddan oshib ketsa TAQIQLANMAYDI — chiqimdagi bilan
    bir xil sabab: haqiqiy ishda hujjat kechikadi va taqiq odamni raqamni
    "to'g'rilab" yozishga majbur qilardi. Javobda `warning` qaytadi."""
    _need_schema()
    opp = db.query_one("SELECT id, status, title FROM erp.opportunity "
                       "WHERE id = %(id)s", {"id": opportunity_id})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)

    ok = _reservable_statuses()
    if opp["status"] not in ok:
        from api.erp.opportunity import STATUS_LABEL
        raise ErpError(
            f"Bu bosqichda rezerv qo'yilmaydi: "
            f"{STATUS_LABEL.get(opp['status'], opp['status'])}. "
            f"Rezerv '{STATUS_LABEL.get(RESERVE_FROM)}' dan boshlab "
            f"qo'yiladi va yakuniy statusda yopiladi.")

    pid = data.get("product_id")
    if not pid:
        raise ErpError("Mahsulot tanlanmagan.")
    cat = db.query_one(PRODUCT_SQL, {"id": pid})
    last = db.query_one(BALANCE_ONE_SQL, {"id": pid})
    if not cat and not last:
        raise ErpError("Bunday mahsulot katalogda ham, omborda ham yo'q.", 404)

    q = _qty(data.get("qty"))
    if q < 0:
        raise ErpError("Rezerv miqdori musbat bo'lishi kerak.")

    row = db.execute_returning(RESERVE_INSERT_SQL, {
        "opportunity_id": opportunity_id, "product_id": pid,
        "product_name": (cat["name"] if cat else last["product_name"]),
        "unit": (cat["unit"] if cat else last["unit"]),
        "qty": q, "note": (data.get("note") or None),
        "created_by": data.get("created_by")})

    out = shape_reserve(db.query_one(RESERVE_GET_SQL, {"id": row["id"]}))
    bal = db.query_one(AVAILABLE_SQL, {"id": pid}) or {}
    out["balance"] = _num(bal.get("qty")) or 0.0
    out["available"] = _num(bal.get("available")) or 0.0
    out["warning"] = ("Mavjud miqdordan oshib ketdi — tovar yetmasligi "
                      "mumkin." if (out["available"] or 0) < 0 else None)
    return out


def release_reserve(reserve_id: int, actor: Optional[str] = None) -> Dict[str, Any]:
    """Rezervni QO'LDA bo'shatish. Yozuv o'chirilmaydi — `released` bo'ladi:
    "nega band edi va nega bo'shadi" tarixda qolsin."""
    _need_schema()
    cur = db.query_one(RESERVE_GET_SQL, {"id": reserve_id})
    if not cur:
        raise ErpError("Rezerv topilmadi.", 404)
    if cur["status"] != "held":
        raise ErpError(f"Bu rezerv allaqachon yopilgan "
                       f"({RESERVE_LABEL.get(cur['status'])}).", 409)
    db.execute_returning(RESERVE_CLOSE_SQL, {
        "id": reserve_id, "status": "released", "move_id": None,
        "closed_by": actor})
    return shape_reserve(db.query_one(RESERVE_GET_SQL, {"id": reserve_id}))


def on_status_change(opportunity_id: int, from_status: str, to_status: str,
                     actor: Optional[str] = None) -> Dict[str, Any]:
    """Karta statusi o'zgarganda rezervlar bilan nima bo'ladi.

    QOIDA (`docs/erp_ombor.md`):
        won              -> SARFLANADI: har rezervga chiqim harakati
        lost / rejected  -> BO'SHAYDI
        won dan QAYTISH  -> chiqim TESKARISI yoziladi va rezerv tiklanadi

    Oxirgisi muhim: sarflangan chiqim O'CHIRILMAYDI — jurnal sodir
    bo'lgan narsani yozadi. Uning o'rniga TESKARI kirim yoziladi va
    ikkalasi ham tarixda qoladi.

    Ombor sxemasi qo'llanmagan bo'lsa hech narsa qilinmaydi: rezerv —
    ixtiyoriy imkoniyat, u kartalar ishini to'xtatmasligi kerak."""
    if not schema_ready():
        return {"consumed": 0, "released": 0, "restored": 0}

    from api.erp.opportunity import FINAL

    consumed = released = restored = 0

    if to_status == "won":
        for r in db.query(HELD_BY_OPP_SQL, {"id": opportunity_id}):
            mv = db.execute_returning(MOVE_INSERT_SQL, {
                "product_id": r["product_id"], "product_name": r["product_name"],
                "unit": r["unit"], "kind": "out", "qty": -r["qty"],
                "opportunity_id": opportunity_id, "doc_ref": None,
                "note": "Rezervdan sarflandi (karta yutildi)",
                "created_by": actor,
                # FOYDA HISOBI shu songa tayanadi.
                "unit_cost": _unit_cost(r["product_id"])})
            db.execute_returning(RESERVE_CLOSE_SQL, {
                "id": r["id"], "status": "consumed", "move_id": mv["id"],
                "closed_by": actor})
            consumed += 1

    elif to_status in FINAL:                      # lost / rejected
        for r in db.query(HELD_BY_OPP_SQL, {"id": opportunity_id}):
            db.execute_returning(RESERVE_CLOSE_SQL, {
                "id": r["id"], "status": "released", "move_id": None,
                "closed_by": actor})
            released += 1

    elif from_status == "won":
        # Yutilgan karta qaytarildi: sarflangan tovar omborga QAYTADI.
        for r in db.query(CONSUMED_BY_OPP_SQL, {"id": opportunity_id}):
            db.execute_returning(MOVE_INSERT_SQL, {
                "product_id": r["product_id"], "product_name": r["product_name"],
                "unit": r["unit"], "kind": "in", "qty": r["qty"],
                "opportunity_id": opportunity_id, "doc_ref": None,
                "note": "Sarflash bekor qilindi (karta yakuniydan qaytarildi)",
                "created_by": actor,
                # Teskari harakat ham AYNAN o'sha tannarx bilan: aks
                # holda bekor qilish foydani o'zgartirib yuborardi.
                "unit_cost": (db.scalar(
                    "SELECT unit_cost FROM erp.stock_move WHERE id = %(id)s",
                    {"id": r["move_id"]}) if r.get("move_id")
                    else _unit_cost(r["product_id"]))})
            db.execute_returning(RESERVE_REOPEN_SQL, {"id": r["id"]})
            restored += 1

    return {"consumed": consumed, "released": released, "restored": restored}


# ---------------------------------------------------------------------------
# TAKLIF: tender pozitsiyalaridan rezerv
# ---------------------------------------------------------------------------
def suggest(opportunity_id: int) -> Dict[str, Any]:
    """"Shu tenderga nima kerak va omboringizda bormi" — TAKLIF.

    Moslashtirish TENDER-AI da bajariladi (`api/stock.py`, 400 qator
    qoida) — biz uni takrorlamaymiz, natijasini o'qiymiz
    (`api/tenderai.py` -> `stock_check`).

    HECH NARSA AVTOMATIK YOZILMAYDI. Sabab: moslashuv nom bo'yicha
    ishlaydi va har doim ham to'g'ri emas ("nasos" har xil nasos
    bo'lishi mumkin). Tasdiqsiz rezerv omborni ifloslantirardi va uni
    keyin qo'lda tozalash kerak bo'lardi. Shuning uchun bu funksiya
    faqat RO'YXAT qaytaradi; yozishni `add_reserve` qiladi.

    Har taklifda uchta son bor va ular uchta boshqa savolga javob:
      `required`  — tenderga qancha kerak (tender-ai o'qigan);
      `held`      — shu kartaga ALLAQACHON ajratilgani (ayiriladi);
      `available` — omborda hozir nechta bo'sh (`qty - rezerv`).
    """
    _need_schema()
    from api import tenderai

    opp = db.query_one("SELECT id, tender_id, status FROM erp.opportunity "
                       "WHERE id = %(id)s", {"id": opportunity_id})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)

    try:
        check = tenderai.stock_check(opp["tender_id"])
    except tenderai.TenderAiUnavailable as e:
        # Tender-AI yiqilsa ERP ishlashda davom etadi: taklif yo'q, lekin
        # rezervni qo'lda qo'yish mumkin.
        raise ErpError(f"Moslashuv xizmati javob bermadi: {e}", 503)

    held = {r["product_id"]: r["qty"]
            for r in db.query(HELD_BY_PRODUCT_SQL, {"id": opportunity_id})}
    bal = {r["product_id"]: r for r in db.query(BALANCE_SQL)}

    items: List[Dict[str, Any]] = []
    for it in check.get("items") or []:
        p = it.get("product") or {}
        pid = p.get("id")
        if not pid:
            continue
        req = it.get("required_qty")
        b = bal.get(pid) or {}
        already = float(held.get(pid) or 0)
        # Taklif qilinadigan miqdor: kerakligidan ALLAQACHON ajratilgani
        # ayiriladi. Manfiy chiqsa 0 — ortiqchasini o'zi bo'shatadi.
        need = max(0.0, float(req) - already) if req is not None else None
        items.append({
            "product_id": pid,
            "product_name": p.get("name"),
            "unit": p.get("unit") or p.get("stock_unit"),
            # Tenderdagi pozitsiya — odam nimaga qarab tasdiqlashini bilsin.
            "position": it.get("name"),
            "position_amount": it.get("amount_text"),
            "required": float(req) if req is not None else None,
            "held": already,
            "suggest": need,
            "available": b.get("available"),
            "qty": b.get("qty"),
            # Tender-AI ning xulosasi: yetarli / yetishmaydi / noma'lum.
            "status": it.get("status"),
            "status_label": it.get("status_label"),
            "reason": it.get("reason"),
            # Miqdor o'qilmagan bo'lsa taklif ham yo'q — TAXMIN QILINMAYDI.
            "can_reserve": bool(need and need > 0),
        })

    return {
        "opportunity_id": opportunity_id,
        "tender_id": opp["tender_id"],
        "items": items,
        # Moslashmagan pozitsiyalar: ular ham ko'rsatiladi, chunki
        # "katalogda yo'q" degan javob ham ma'lumot.
        "unmatched": [{"position": u.get("name"),
                       "amount": u.get("amount_text"),
                       "reason": u.get("reason")}
                      for u in (check.get("unmatched") or [])],
        # Tender-AI ning ogohlantirishi (eskirgan qoldiq va h.k.) —
        # yashirilmaydi.
        "warning": (check.get("stock") or {}).get("warning"),
        "preliminary": check.get("preliminary"),
    }


def add_reserves(opportunity_id: int, rows: List[Dict[str, Any]],
                 created_by: Optional[str] = None) -> Dict[str, Any]:
    """Tasdiqlangan takliflarni rezervga aylantirish (bir necha qator).

    Har qator alohida tekshiriladi; birortasi o'tmasa QOLGANLARI
    yoziladi va xatolar ro'yxatda qaytadi. Sabab: o'nta qatordan
    bittasi tufayli hammasini rad etish odamni boshidan boshlashga
    majbur qilardi."""
    _need_schema()
    made, errors = [], []
    for r in rows or []:
        try:
            made.append(add_reserve(opportunity_id, {
                "product_id": r.get("product_id"), "qty": r.get("qty"),
                "note": r.get("note") or "Tender pozitsiyasidan taklif",
                "created_by": created_by}))
        except ErpError as e:
            errors.append({"product_id": r.get("product_id"),
                           "error": str(e)})
    return {"created": made, "errors": errors,
            "count": len(made), "failed": len(errors)}
