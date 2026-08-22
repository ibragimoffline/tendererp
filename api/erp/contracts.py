"""ERP 5A-1: SHARTNOMA va bizning rekvizitlar.

Chegara:
  - Faqat erp.* jadvallari. public.* ga murojaat yo'q — `company_profile`
    ham tegilmaydi (u tender-ai ning qidiruv profili, bizning yuridik
    passportimiz emas).
  - Shartnoma o'chirilmaydi: noto'g'risi 'terminated' ga o'tkaziladi.
  - Auth yo'q: `created_by` — tanlangan brokerning nomi (matn). Pul
    harakati (to'lov, hisob-faktura) SHU MODULDA YO'Q — u 5B da va auth
    talab qiladi (`docs/erp_arxitektura_3.md` 3-bo'lim).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError, _iso, _need_schema, _num

# Holatlar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_5.sql).
CONTRACT_STATUSES = [
    ("draft",      "Loyiha"),
    ("signed",     "Imzolangan"),
    ("executing",  "Ijroda"),
    ("done",       "Bajarilgan"),
    ("terminated", "Bekor qilingan"),
]
CONTRACT_STATUS_LABEL = dict(CONTRACT_STATUSES)
CONTRACT_FINAL = {"done", "terminated"}

# Passport maydonlari — `client_company` bilan BIR XIL nomlar.
OWN_FIELDS = ("name", "inn", "oked", "legal_form", "tax_mode", "address_legal",
              "address_actual", "bank_name", "bank_mfo", "bank_account",
              "director_name", "phone", "email", "note",
              # QQS ni SOTUVCHI hisoblaydi: biz to'lovchi bo'lmasak,
              # mijoz to'lovchi bo'lsa ham faktura QQS'siz chiqadi.
              # `None` = hali so'ralmagan (`False` bilan bir xil emas).
              "vat_payer", "vat_rate")

#: MATN bo'lmagan maydonlar. Ular alohida ishlanadi: `own_save` qolgan
#: hammasini `.strip()` qiladi va bu yerda bool/son bor.
OWN_NON_TEXT = ("vat_payer", "vat_rate")

CONTRACT_FIELDS = ("submission_id", "number", "signed_at", "starts_at",
                   "ends_at", "amount", "currency", "note")


# ---------------------------------------------------------------------------
# Sxema tayyorligi
# ---------------------------------------------------------------------------
_SCHEMA5_READY = False

SCHEMA5_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'contract'
"""


def schema_ready() -> bool:
    global _SCHEMA5_READY
    if _SCHEMA5_READY:
        return True
    _SCHEMA5_READY = bool(db.query_one(SCHEMA5_CHECK_SQL))
    return _SCHEMA5_READY


def _need_schema5() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Shartnoma jadvali yo'q: schema_patch_erp_5.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_OWN_COLS = ("id, " + ", ".join(OWN_FIELDS) + ", updated_at")
OWN_GET_SQL = f"SELECT {_OWN_COLS} FROM erp.own_company WHERE id = 1"
OWN_UPDATE_SQL = f"""
UPDATE erp.own_company SET
    {", ".join(f"{f}=%({f})s" for f in OWN_FIELDS)}, updated_at=now()
WHERE id = 1
RETURNING {_OWN_COLS}
"""

_C_COLS = """
k.id, k.opportunity_id, k.submission_id, k.number, k.signed_at, k.starts_at,
k.ends_at, k.amount, k.currency, k.status, k.status_changed_at, k.note,
k.created_by, k.created_at, k.updated_at,
s.version AS submission_version, s.price AS submission_price
"""
_C_FROM = """
FROM erp.contract k
LEFT JOIN erp.submission s ON s.id = k.submission_id
"""

CONTRACTS_SQL = (f"SELECT {_C_COLS} {_C_FROM} "
                 "WHERE k.opportunity_id = %(id)s ORDER BY k.id DESC")
CONTRACT_GET_SQL = f"SELECT {_C_COLS} {_C_FROM} WHERE k.id = %(id)s"

# Rahbar ko'rinishi: hamma shartnomalar + karta konteksti.
CONTRACT_LIST_SQL = f"""
SELECT {_C_COLS},
       o.title AS opp_title, o.tender_id, o.tender_ref,
       c.name AS client_name, b.full_name AS broker_name
{_C_FROM}
JOIN erp.opportunity o ON o.id = k.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker b ON b.id = o.broker_id
WHERE (%(status)s::text IS NULL OR k.status = %(status)s)
  AND (%(client_id)s::int IS NULL OR o.client_id = %(client_id)s)
  AND (%(open_only)s::bool IS NOT TRUE OR k.status NOT IN ('done','terminated'))
ORDER BY k.signed_at DESC NULLS LAST, k.id DESC
"""

CONTRACT_INSERT_SQL = f"""
INSERT INTO erp.contract
    (opportunity_id, submission_id, number, signed_at, starts_at, ends_at,
     amount, currency, status, note, created_by)
VALUES (%(opportunity_id)s, %(submission_id)s, %(number)s, %(signed_at)s,
        %(starts_at)s, %(ends_at)s, %(amount)s, %(currency)s, %(status)s,
        %(note)s, %(created_by)s)
RETURNING id
"""

CONTRACT_UPDATE_SQL = """
UPDATE erp.contract SET
    submission_id=%(submission_id)s, number=%(number)s, signed_at=%(signed_at)s,
    starts_at=%(starts_at)s, ends_at=%(ends_at)s, amount=%(amount)s,
    currency=%(currency)s, note=%(note)s, updated_at=now()
WHERE id = %(id)s
RETURNING id
"""

CONTRACT_STATUS_SQL = """
UPDATE erp.contract SET
    status=%(status)s, status_changed_at=now(), updated_at=now()
WHERE id = %(id)s
RETURNING id, status
"""

NUMBER_TAKEN_SQL = ("SELECT id FROM erp.contract "
                    "WHERE number = %(number)s AND (%(id)s::int IS NULL OR id <> %(id)s)")


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def shape_own(r: dict) -> dict:
    out = {f: r.get(f) for f in OWN_FIELDS}
    # NUMERIC -> float: JSON `Decimal` ni bilmaydi.
    out["vat_rate"] = (float(r["vat_rate"])
                       if r.get("vat_rate") is not None else None)
    out["updated_at"] = _iso(r.get("updated_at"))
    # Shartnoma uchun MAJBURIY maydonlar — interfeys nimasi yetishmasligini
    # oldindan aytadi (mijoz passportidagi `missing` bilan bir xil uslub).
    need = ("name", "inn", "legal_form", "address_legal", "bank_account",
            "bank_mfo", "director_name")
    out["missing"] = [f for f in need if not r.get(f)]
    return out


def shape(r: dict) -> dict:
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"],
        "submission_id": r["submission_id"],
        "submission": ({"id": r["submission_id"], "version": r["submission_version"],
                        "price": _num(r["submission_price"])}
                       if r["submission_id"] else None),
        "number": r["number"], "signed_at": _iso(r["signed_at"]),
        "starts_at": _iso(r["starts_at"]), "ends_at": _iso(r["ends_at"]),
        "amount": _num(r["amount"]), "currency": r["currency"],
        "status": r["status"], "status_label": CONTRACT_STATUS_LABEL.get(r["status"]),
        "is_final": r["status"] in CONTRACT_FINAL,
        "status_changed_at": _iso(r["status_changed_at"]),
        "note": r["note"], "created_by": r["created_by"],
        "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
    }


def _shape_row(r: dict) -> dict:
    out = shape(r)
    out["opportunity"] = {"id": r["opportunity_id"], "title": r["opp_title"],
                          "tender_id": r["tender_id"], "tender_ref": r["tender_ref"],
                          "client_name": r["client_name"],
                          "broker_name": r["broker_name"]}
    return out


def _check(data: dict, contract_id: Optional[int] = None) -> None:
    num = (data.get("number") or "").strip()
    if num:
        ex = db.query_one(NUMBER_TAKEN_SQL, {"number": num, "id": contract_id})
        if ex:
            raise ErpError(f"Bu raqamli shartnoma allaqachon bor: {num}.",
                           409, contract_id=ex["id"])
    amount = data.get("amount")
    if amount is not None and float(amount) < 0:
        raise ErpError("Shartnoma summasi manfiy bo'la olmaydi.")
    s, e = data.get("starts_at"), data.get("ends_at")
    if s and e and str(e) < str(s):
        raise ErpError("Tugash sanasi boshlanish sanasidan oldin bo'la olmaydi.")


# ---------------------------------------------------------------------------
# Bizning kompaniya
# ---------------------------------------------------------------------------
def own_get() -> dict:
    _need_schema5()
    r = db.query_one(OWN_GET_SQL)
    if not r:
        # Patch qatorni yaratadi; bo'lmasa ham interfeys yiqilmasin.
        return shape_own({f: None for f in OWN_FIELDS})
    return shape_own(r)


def own_save(data: dict) -> dict:
    _need_schema5()
    if not (data.get("name") or "").strip():
        raise ErpError("Kompaniya nomi bo'sh.")
    params = {f: ((data.get(f) or "").strip() or None)
              for f in OWN_FIELDS if f not in OWN_NON_TEXT}
    params["name"] = data["name"].strip()

    # --- QQS: matn emas, shuning uchun alohida ---
    # `None` = HALI SO'RALMAGAN va u `False` bilan bir xil emas
    # (`api/erp/invoice.py` -> `default_vat_rate`).
    vp = data.get("vat_payer")
    params["vat_payer"] = None if vp is None else bool(vp)

    rate = data.get("vat_rate")
    if rate in (None, ""):
        params["vat_rate"] = None
    else:
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            raise ErpError("QQS stavkasi son bo'lishi kerak.")
        if not 0 <= rate <= 100:
            raise ErpError("QQS stavkasi 0 va 100 orasida bo'lishi kerak.")
        params["vat_rate"] = rate
    inn = params.get("inn")
    if inn:
        digits = "".join(ch for ch in inn if ch.isdigit())
        if len(digits) != 9:
            raise ErpError("INN 9 ta raqamdan iborat bo'lishi kerak.")
        params["inn"] = digits
    return shape_own(db.execute_returning(OWN_UPDATE_SQL, params))


# ---------------------------------------------------------------------------
# Shartnoma
# ---------------------------------------------------------------------------
def list_for(opp_id: int) -> List[dict]:
    _need_schema5()
    return [shape(r) for r in db.query(CONTRACTS_SQL, {"id": opp_id})]


def list_(status: Optional[str] = None, client_id: Optional[int] = None,
          open_only: bool = False) -> List[dict]:
    _need_schema5()
    return [_shape_row(r) for r in db.query(CONTRACT_LIST_SQL, {
        "status": status, "client_id": client_id, "open_only": open_only})]


def get(contract_id: int) -> dict:
    _need_schema5()
    r = db.query_one(CONTRACT_GET_SQL, {"id": contract_id})
    if not r:
        raise ErpError("Shartnoma topilmadi.", 404)
    return shape(r)


def create(opp_id: int, data: dict) -> List[dict]:
    """Javob — kartaning BUTUN shartnomalar ro'yxati (vazifalardagi uslub).

    Summa va valyuta berilmasa, taklifdan (yoki kartadagi snapshotdan)
    olinadi: broker bir xil raqamni ikkinchi marta yozmasin."""
    _need_schema5()
    opp = db.query_one(
        "SELECT id, start_price, currency FROM erp.opportunity WHERE id=%(id)s",
        {"id": opp_id})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)
    _check(data)

    sub_id = data.get("submission_id")
    sub = None
    if sub_id:
        sub = db.query_one("SELECT id, price, currency, opportunity_id "
                           "FROM erp.submission WHERE id=%(id)s", {"id": sub_id})
        if not sub:
            raise ErpError("Taklif topilmadi.", 404)
        if sub["opportunity_id"] != opp_id:
            raise ErpError("Taklif boshqa kartaga tegishli.")

    amount = data.get("amount")
    if amount is None:
        amount = (sub or {}).get("price") or opp["start_price"]
    currency = data.get("currency") or (sub or {}).get("currency") or opp["currency"]

    status = data.get("status") or "draft"
    if status not in CONTRACT_STATUS_LABEL:
        raise ErpError("Noma'lum shartnoma holati.")

    db.execute_returning(CONTRACT_INSERT_SQL, {
        **{k: data.get(k) for k in CONTRACT_FIELDS},
        "number": (data.get("number") or "").strip() or None,
        "opportunity_id": opp_id, "amount": amount, "currency": currency,
        "status": status, "created_by": data.get("created_by")})
    return list_for(opp_id)


def update(contract_id: int, data: dict) -> List[dict]:
    _need_schema5()
    cur = db.query_one(CONTRACT_GET_SQL, {"id": contract_id})
    if not cur:
        raise ErpError("Shartnoma topilmadi.", 404)
    _check(data, contract_id)
    db.execute_returning(CONTRACT_UPDATE_SQL, {
        **{k: data.get(k) for k in CONTRACT_FIELDS},
        "number": (data.get("number") or "").strip() or None,
        "id": contract_id})
    return list_for(cur["opportunity_id"])


def set_status(contract_id: int, status: str) -> List[dict]:
    """Holatni o'zgartiradi. Shartnoma O'CHIRILMAYDI — noto'g'risi
    'terminated' ga o'tkaziladi."""
    _need_schema5()
    if status not in CONTRACT_STATUS_LABEL:
        raise ErpError("Noma'lum shartnoma holati.")
    cur = db.query_one(CONTRACT_GET_SQL, {"id": contract_id})
    if not cur:
        raise ErpError("Shartnoma topilmadi.", 404)
    if cur["status"] != status:
        db.execute_returning(CONTRACT_STATUS_SQL, {"id": contract_id, "status": status})
    return list_for(cur["opportunity_id"])


def stats() -> Dict[str, Any]:
    """Rahbar uchun qisqa yig'indi: holat bo'yicha soni va summasi."""
    _need_schema5()
    rows = db.query("""
        SELECT status, count(*) AS n, coalesce(sum(amount),0) AS total
        FROM erp.contract GROUP BY status
    """)
    by = {r["status"]: {"n": r["n"], "total": _num(r["total"])} for r in rows}
    return {
        "by_status": [{"code": c, "label": l,
                       "n": by.get(c, {}).get("n", 0),
                       "total": by.get(c, {}).get("total", 0.0)}
                      for c, l in CONTRACT_STATUSES],
        "total": sum(v["n"] for v in by.values()),
        "active": sum(v["n"] for k, v in by.items() if k not in CONTRACT_FINAL),
    }


# ---------------------------------------------------------------------------
# SHARTNOMA ILOVASI — SPETSIFIKATSIYA
#
# QAROR: ERP shartnoma MATNINI yozmaydi. Huquqiy matn yurist ishi va uni
# shablondan o'ylab topish — noto'g'ri hujjat chiqarish demak. ERP qayd
# qiladi (raqam, sana, summa, holat).
#
# ERP CHIQARADIGAN QISM — ILOVA: tovar/xizmat ro'yxati, miqdor, narx,
# jami. Bu aynan ERP da bor va har bitimda o'zgaradigan qism.
#
# MA'LUMOT QAYERDAN: uch manba, MUZLATILGANI ustun.
#   1. FAKTURA — agar shu shartnoma bo'yicha chiqarilgan bo'lsa. Eng
#      yaxshisi: qatorlari ham, tomonlarning rekvizitlari ham
#      MUZLATILGAN (snapshot).
#   2. REZERV — kartaga ajratilgan tovar. Miqdor haqiqiy, narx katalogdan.
#   3. Hech biri bo'lmasa — ro'yxat BO'SH va shakl buni ochiq aytadi.
#      Taxmin qilinmaydi.
#
# Javobda `source` bor: interfeys ma'lumot qayerdan kelganini ko'rsatadi.
# ---------------------------------------------------------------------------
SPEC_INVOICE_SQL = """
SELECT id, number, issued_at, currency,
       client_name, client_inn, client_address, client_director,
       own_name, own_inn, own_address, own_director
FROM erp.invoice
WHERE contract_id = %(id)s AND status <> 'cancelled'
ORDER BY issued_at DESC NULLS LAST, id DESC
LIMIT 1
"""

SPEC_RESERVES_SQL = """
SELECT r.product_id,
       (array_agg(r.product_name ORDER BY r.id DESC))[1] AS name,
       (array_agg(r.unit ORDER BY r.id DESC))[1]         AS unit,
       SUM(r.qty)                                        AS qty,
       max(p.price)                                      AS price
FROM erp.stock_reserve r
LEFT JOIN public.catalog_product p ON p.id = r.product_id
WHERE r.opportunity_id = %(id)s AND r.status IN ('held', 'consumed')
GROUP BY r.product_id
ORDER BY 2
"""

SPEC_CLIENT_SQL = """
SELECT c.name, c.inn, c.address_legal, c.address_actual, c.director_name,
       c.vat_payer, c.vat_rate
FROM erp.opportunity o
JOIN erp.client_company c ON c.id = o.client_id
WHERE o.id = %(id)s
"""


def specification(contract_id: int) -> dict:
    """Shartnoma ilovasi (spetsifikatsiya) uchun ma'lumot.

    Shartnoma MATNI qaytarilmaydi — u ERP da yo'q (yuqoridagi izohga
    qarang). Bu yerda faqat ilova: tomonlar, qatorlar va jami."""
    _need_schema5()
    k = db.query_one(CONTRACT_GET_SQL, {"id": contract_id})
    if not k:
        raise ErpError("Shartnoma topilmadi.", 404)

    from api.erp import invoice as inv_mod

    out = {
        "contract": shape(k),
        "lines": [],
        "source": "none",
        # Ma'lumot MUZLATILGANMI: fakturadan kelsa — ha (u snapshot),
        # rezervdan kelsa — yo'q (passport hozirgi holatda). Shaklda
        # shu ochiq aytiladi.
        "frozen": False,
    }

    inv = db.query_one(SPEC_INVOICE_SQL, {"id": contract_id})
    if inv:
        full = inv_mod.get(inv["id"])
        out["lines"] = full.get("lines") or []
        out["totals"] = full.get("totals")
        out["client"] = full["client"]
        out["own"] = full["own"]
        out["source"] = "invoice"
        out["invoice_number"] = inv["number"]
        out["frozen"] = True
        return out

    # Faktura yo'q — rezervlardan. Rekvizitlar passportdan (HOZIRGI holat).
    cl = db.query_one(SPEC_CLIENT_SQL, {"id": k["opportunity_id"]}) or {}
    own = db.query_one(OWN_GET_SQL) or {}
    out["client"] = {
        "name": cl.get("name"), "inn": cl.get("inn"),
        "address": cl.get("address_legal") or cl.get("address_actual"),
        "director": cl.get("director_name"),
        "vat_payer": cl.get("vat_payer"),
    }
    out["own"] = {
        "name": own.get("name"), "inn": own.get("inn"),
        "address": own.get("address_legal") or own.get("address_actual"),
        "director": own.get("director_name"),
    }

    rows = db.query(SPEC_RESERVES_SQL, {"id": k["opportunity_id"]})
    if rows:
        rate = (float(cl.get("vat_rate") or 0) if cl.get("vat_payer") else 0)
        lines, no_price = [], 0
        for i, r in enumerate(rows, start=1):
            if r["price"] is None:
                no_price += 1
            price = r["price"] if r["price"] is not None else 0
            t = inv_mod.line_totals(r["qty"], price, rate)
            lines.append({
                "id": i, "pos": i, "product_id": r["product_id"],
                "name": r["name"], "unit": r["unit"],
                "qty": float(r["qty"]), "price": float(price),
                "vat_rate": rate, "note": None,
                "net": float(t["net"]), "vat": float(t["vat"]),
                "total": float(t["total"]),
            })
        tot = inv_mod.totals([
            {"qty": x["qty"], "price": x["price"], "vat_rate": x["vat_rate"]}
            for x in lines])
        out["lines"] = lines
        out["totals"] = {
            "net": float(tot["net"]), "vat": float(tot["vat"]),
            "total": float(tot["total"]),
            "words": inv_mod.amount_words(tot["total"], k["currency"]),
        }
        out["source"] = "reserves"
        out["no_price"] = no_price
    return out
