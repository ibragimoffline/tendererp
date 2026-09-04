"""
HISOB-FAKTURA (5B-2) — ma'lumot modeli.

QAROR: fakturani ERP O'ZI chiqaradi (javob olingan). Bu modul uning
MA'LUMOTINI yuritadi; YUBORISH qatlami ataylab bo'sh —
`api/erp/invoice_export.py` ga qarang.

UCH QOIDA, uchalasi ham "bir haqiqat" tamoyilidan chiqadi:

1. QQS STAVKASI HAR QATORDA. Sukut mijoz passportidan olinadi
   (`erp.client_company.vat_payer` / `vat_rate`), lekin qatorga
   NUSXA ko'chiriladi. Keyin mijozning rejimi o'zgarsa yoki qonun
   o'zgarsa — CHIQARILGAN hujjat o'zgarmaydi.

2. SUMMALAR SAQLANMAYDI. `net = qty * price`, `vat = net * rate/100` —
   bular hisob natijasi. Ustunga yozilsa "nega bu son?" degan savolga
   ikki xil javob paydo bo'lardi. Ombordagi qoldiq bilan bir xil qoida.

3. REKVIZITLAR SNAPSHOT. Ikkala tomonniki fakturaga ko'chiriladi:
   hujjat chiqarilgandan keyin passport o'zgarsa (bank almashdi, manzil
   ko'chdi) eski hujjat o'zgarmasligi kerak.

MUZLATISH: `draft` dan chiqqach qatorlar va rekvizitlar tahrirlanmaydi.
Xato bo'lsa faktura BEKOR QILINADI va yangisi chiqariladi — chiqarilgan
hujjatni jimgina o'zgartirish buxgalteriyada yo'q qoida.

PUL — BUTUN TIYINDA EMAS, `NUMERIC`. `float` ishlatilmaydi: 0.1 + 0.2
muammosi hisob-kitobda ko'rinadigan xatoga aylanadi. Bazada `NUMERIC`,
Pythonda `Decimal`, JSON ga chiqishda esa `float` (mijoz uni faqat
ko'rsatadi, qayta hisoblamaydi).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError

# Holatlar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_11.sql).
STATUSES = [
    ("draft",     "Qoralama"),
    ("issued",    "Chiqarildi"),
    ("sent",      "Yuborildi"),
    ("paid",      "To'landi"),
    ("cancelled", "Bekor qilindi"),
]
STATUS_LABEL = dict(STATUSES)

#: Qatorlar TAHRIRLANADIGAN holat. Qolganida hujjat muzlatilgan.
EDITABLE = "draft"

#: Yakuniy holatlar — ulardan keyin faktura o'zgarmaydi.
FINAL = {"paid", "cancelled"}

METHODS = [
    ("bank",  "Bank o'tkazmasi"),
    ("cash",  "Naqd"),
    ("other", "Boshqa"),
]
METHOD_LABEL = dict(METHODS)

# --- SUMMA SO'Z BILAN --------------------------------------------------------
# Hujjatda summa raqam bilan ham, SO'Z bilan ham yoziladi: raqamdagi bitta
# nolni qo'shib qo'yish oson, so'zdagisini esa emas. Bu buxgalteriyaning
# eski va foydali odati.
#
# NEGA SERVERDA, INTERFEYSDA EMAS: bu sof mantiq va u SINALADI. Brauzerda
# yozilsa sinovsiz qolardi (ERP sinovlari Pythonda) va bosma shakl bilan
# API javobi ajralib ketishi mumkin edi.
_ONES = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti",
         "sakkiz", "to'qqiz"]
_TENS = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish",
         "yetmish", "sakson", "to'qson"]

#: Uch xonali guruhlar: birlik, ming, million, milliard, trillion.
#: `bir` TUSHIB QOLADIGAN guruhlar — `ming` va `yuz`: o'zbekchada
#: "bir ming" emas, "ming" deyiladi. `million` va undan kattasi esa
#: "bir million" bo'lib qoladi.
_GROUPS = ["", "ming", "million", "milliard", "trillion"]


def _under_thousand(n: int) -> str:
    """0..999 -> so'z. Bo'sh satr = nol (chaqiruvchi hal qiladi)."""
    out = []
    h, rest = divmod(n, 100)
    if h:
        # 100 -> "yuz", 200 -> "ikki yuz" (birinchisida "bir" yo'q).
        out.append("yuz" if h == 1 else f"{_ONES[h]} yuz")
    t, o = divmod(rest, 10)
    if t:
        out.append(_TENS[t])
    if o:
        out.append(_ONES[o])
    return " ".join(out)


def number_words(n: int) -> str:
    """Butun sonni o'zbekcha so'z bilan yozadi."""
    n = int(n)
    if n == 0:
        return "nol"
    if n < 0:
        return "minus " + number_words(-n)

    parts, i = [], 0
    while n > 0:
        n, chunk = divmod(n, 1000)
        if chunk:
            word = _under_thousand(chunk)
            g = _GROUPS[i] if i < len(_GROUPS) else f"10^{i * 3}"
            if g == "ming" and chunk == 1:
                word = ""              # "bir ming" emas, "ming"
            parts.append(f"{word} {g}".strip() if g else word)
        i += 1
    return " ".join(reversed(parts))


#: Valyuta nomlari va mayda birligi. Ro'yxatda bo'lmagan valyuta uchun
#: kod o'zi yoziladi ("120.00 EUR") — noto'g'ri nom o'ylab topilmaydi.
CURRENCY_WORDS = {
    "UZS": ("so'm", "tiyin"),
    "USD": ("AQSH dollari", "sent"),
    "RUB": ("rubl", "tiyin"),
    "EUR": ("evro", "sent"),
}


def amount_words(value, currency: str = "UZS") -> str:
    """Summani hujjat uchun so'z bilan yozadi.

    Masalan: 5240001.68 UZS ->
        "besh million ikki yuz qirq ming bir so'm 68 tiyin"

    Tiyin RAQAM bilan qoladi — hujjatlarda odatda shunday va u so'z bilan
    yozilganda matn o'qilmas darajada uzayadi."""
    amount = _dec(value, "summa").quantize(CENTS, rounding=ROUND_HALF_UP)
    sign = "minus " if amount < 0 else ""
    amount = abs(amount)
    whole = int(amount)
    cents = int((amount - whole) * 100)

    cur = (currency or "UZS").upper()
    main, small = CURRENCY_WORDS.get(cur, (cur, None))
    out = f"{sign}{number_words(whole)} {main}"
    if small:
        out += f" {cents:02d} {small}"
    elif cents:
        out += f" {cents:02d}"
    return out


#: Pul tiyingacha yaxlitlanadi. Yaxlitlash QATOR darajasida bo'ladi —
#: aks holda yig'indi bilan qatorlar summasi bir tiyinga farq qilardi va
#: buxgalter buni xato deb hisoblardi.
CENTS = Decimal("0.01")


SCHEMA_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'invoice'
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
        raise ErpError("Faktura jadvallari yo'q: schema_patch_erp_11.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
INV_COLS = """
i.id, i.opportunity_id, i.contract_id, i.client_id, i.number, i.issued_at,
i.due_at, i.currency, i.status, i.status_changed_at,
i.client_name, i.client_inn, i.client_address, i.client_bank, i.client_mfo,
i.client_account, i.client_director, i.client_vat_payer,
i.own_name, i.own_inn, i.own_address, i.own_bank, i.own_mfo, i.own_account,
i.own_director, i.note, i.created_by, i.created_at, i.updated_at
"""

INV_GET_SQL = f"""
SELECT {INV_COLS}, o.title AS opportunity_name, k.number AS contract_number
FROM erp.invoice i
LEFT JOIN erp.opportunity o ON o.id = i.opportunity_id
LEFT JOIN erp.contract k    ON k.id = i.contract_id
WHERE i.id = %(id)s
"""

INV_LIST_SQL = f"""
SELECT {INV_COLS}, o.title AS opportunity_name, k.number AS contract_number
FROM erp.invoice i
LEFT JOIN erp.opportunity o ON o.id = i.opportunity_id
LEFT JOIN erp.contract k    ON k.id = i.contract_id
WHERE (%(status)s::text IS NULL OR i.status = %(status)s)
  AND (%(client_id)s::int IS NULL OR i.client_id = %(client_id)s)
  AND (%(opportunity_id)s::int IS NULL OR i.opportunity_id = %(opportunity_id)s)
  -- EGALIK (api/erp/egalik.py): karta orqali; KARTASIZ faktura esa
  -- mijoz orqali, aks holda broker o'zi chiqargan hujjatni ko'rmasdi.
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s
       OR (i.opportunity_id IS NULL AND EXISTS (
             SELECT 1 FROM erp.opportunity oo
              WHERE oo.client_id = i.client_id
                AND oo.broker_id = %(owner_broker_id)s)))
ORDER BY i.issued_at DESC NULLS FIRST, i.id DESC
"""

INV_INSERT_SQL = """
INSERT INTO erp.invoice
    (opportunity_id, contract_id, client_id, number, issued_at, due_at,
     currency, note, created_by,
     client_name, client_inn, client_address, client_bank, client_mfo,
     client_account, client_director, client_vat_payer,
     own_name, own_inn, own_address, own_bank, own_mfo, own_account,
     own_director)
VALUES
    (%(opportunity_id)s, %(contract_id)s, %(client_id)s, %(number)s,
     %(issued_at)s, %(due_at)s, %(currency)s, %(note)s, %(created_by)s,
     %(client_name)s, %(client_inn)s, %(client_address)s, %(client_bank)s,
     %(client_mfo)s, %(client_account)s, %(client_director)s,
     %(client_vat_payer)s,
     %(own_name)s, %(own_inn)s, %(own_address)s, %(own_bank)s, %(own_mfo)s,
     %(own_account)s, %(own_director)s)
RETURNING id
"""

INV_UPDATE_SQL = """
UPDATE erp.invoice SET
    number = %(number)s, issued_at = %(issued_at)s, due_at = %(due_at)s,
    currency = %(currency)s, note = %(note)s,
    contract_id = %(contract_id)s, updated_at = now()
WHERE id = %(id)s
RETURNING id
"""

INV_STATUS_SQL = """
UPDATE erp.invoice
SET status = %(status)s, status_changed_at = now(), updated_at = now()
WHERE id = %(id)s
RETURNING id
"""

LINES_SQL = ("SELECT id, invoice_id, pos, product_id, name, unit, qty, price, "
             "vat_rate, note FROM erp.invoice_line "
             "WHERE invoice_id = %(id)s ORDER BY pos, id")

LINE_INSERT_SQL = """
INSERT INTO erp.invoice_line
    (invoice_id, pos, product_id, name, unit, qty, price, vat_rate, note)
VALUES (%(invoice_id)s, %(pos)s, %(product_id)s, %(name)s, %(unit)s,
        %(qty)s, %(price)s, %(vat_rate)s, %(note)s)
RETURNING id
"""

LINE_DELETE_SQL = ("DELETE FROM erp.invoice_line WHERE id = %(id)s "
                   "AND invoice_id = %(invoice_id)s RETURNING id")

PAYMENTS_SQL = ("SELECT id, invoice_id, paid_at, amount, method, doc_ref, "
                "note, created_by, created_at FROM erp.invoice_payment "
                "WHERE invoice_id = %(id)s ORDER BY paid_at, id")

PAYMENT_INSERT_SQL = """
INSERT INTO erp.invoice_payment
    (invoice_id, paid_at, amount, method, doc_ref, note, created_by)
VALUES (%(invoice_id)s, %(paid_at)s, %(amount)s, %(method)s, %(doc_ref)s,
        %(note)s, %(created_by)s)
RETURNING id
"""

PAYMENT_DELETE_SQL = ("DELETE FROM erp.invoice_payment WHERE id = %(id)s "
                      "RETURNING id, invoice_id")

CLIENT_SQL = """
SELECT id, name, inn, legal_form, address_legal, address_actual, bank_name,
       bank_mfo, bank_account, director_name, vat_payer, vat_rate
FROM erp.client_company WHERE id = %(id)s
"""

OWN_SQL = """
SELECT name, inn, address_legal, address_actual, bank_name, bank_mfo,
       bank_account, director_name, vat_payer, vat_rate
FROM erp.own_company LIMIT 1
"""

CONTRACT_SQL = ("SELECT id, opportunity_id, number, currency FROM erp.contract "
                "WHERE id = %(id)s")

# --- ZANJIR: karta -> shartnoma -> faktura ----------------------------------
OPP_SQL = ("SELECT id, client_id, currency, title, status FROM erp.opportunity "
           "WHERE id = %(id)s")

#: Kartaning ENG SO'NGGI shartnomasi. Bir kartada bir nechta bo'lishi
#: mumkin (bosqichma-bosqich), oxirgisi odatda amaldagisi.
OPP_CONTRACT_SQL = ("SELECT id, number, currency, amount FROM erp.contract "
                    "WHERE opportunity_id = %(id)s "
                    "ORDER BY signed_at DESC NULLS LAST, id DESC LIMIT 1")

#: Kartaga AJRATILGAN tovar — faktura qatorlarining manbai.
#: `held` va `consumed` ikkalasi ham olinadi: birinchisi hali chiqmagan,
#: ikkinchisi yutilgach chiqib bo'lgan — ikkalasi ham SOTILGAN tovar.
#: `released` esa bekor qilingani, u fakturaga tushmaydi.
#:
#: NARX — tender-ai katalogidan (`price`, sotuv narxi), FAQAT O'QISH.
#: Bo'lmasa 0 qoladi va odam to'ldiradi: taxmin qilib tannarxni yozib
#: qo'yish fakturani jimgina noto'g'ri qilardi.
OPP_RESERVES_SQL = """
SELECT r.product_id,
       (array_agg(r.product_name ORDER BY r.id DESC))[1] AS product_name,
       (array_agg(r.unit ORDER BY r.id DESC))[1]         AS unit,
       SUM(r.qty)                                        AS qty,
       max(p.price)                                      AS price
FROM erp.stock_reserve r
LEFT JOIN public.catalog_product p ON p.id = r.product_id
WHERE r.opportunity_id = %(id)s AND r.status IN ('held', 'consumed')
GROUP BY r.product_id
ORDER BY 2
"""


# ---------------------------------------------------------------------------
# Hisob (sof funksiyalar — bazasiz sinaladi)
# ---------------------------------------------------------------------------
def _dec(v, field: str) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        raise ErpError(f"'{field}' son bo'lishi kerak.")


def line_totals(qty, price, vat_rate) -> Dict[str, Decimal]:
    """Bitta qator: QQS siz summa, QQS va jami.

    Yaxlitlash QATOR darajasida: aks holda yig'indi bilan qatorlar
    summasi bir tiyinga farq qilardi va buxgalter buni xato deb
    hisoblardi."""
    q = _dec(qty, "qty")
    p = _dec(price, "price")
    r = _dec(vat_rate, "vat_rate")
    net = (q * p).quantize(CENTS, rounding=ROUND_HALF_UP)
    vat = (net * r / Decimal(100)).quantize(CENTS, rounding=ROUND_HALF_UP)
    return {"net": net, "vat": vat, "total": net + vat}


def totals(lines: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    """Faktura jami. Qator summalari QO'SHILADI (qayta hisoblanmaydi)."""
    net = vat = Decimal("0")
    for ln in lines:
        t = line_totals(ln["qty"], ln["price"], ln["vat_rate"])
        net += t["net"]
        vat += t["vat"]
    return {"net": net, "vat": vat, "total": net + vat}


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def _iso(v):
    return v.isoformat() if v is not None else None


def _num(v):
    return float(v) if v is not None else None


def shape_line(r: Dict[str, Any]) -> Dict[str, Any]:
    t = line_totals(r["qty"], r["price"], r["vat_rate"])
    return {
        "id": r["id"], "invoice_id": r["invoice_id"], "pos": r["pos"],
        "product_id": r["product_id"], "name": r["name"], "unit": r["unit"],
        "qty": _num(r["qty"]), "price": _num(r["price"]),
        "vat_rate": _num(r["vat_rate"]), "note": r["note"],
        # Hisob natijalari — saqlanmaydi, har safar chiqariladi.
        "net": float(t["net"]), "vat": float(t["vat"]),
        "total": float(t["total"]),
    }


def shape_payment(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "invoice_id": r["invoice_id"],
        "paid_at": _iso(r["paid_at"]), "amount": _num(r["amount"]),
        "method": r["method"], "method_label": METHOD_LABEL.get(r["method"]),
        "doc_ref": r["doc_ref"], "note": r["note"],
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
    }


def shape(r: Dict[str, Any], *, lines=None, payments=None) -> Dict[str, Any]:
    out = {
        "id": r["id"], "opportunity_id": r["opportunity_id"],
        "opportunity_name": r.get("opportunity_name"),
        "contract_id": r["contract_id"],
        "contract_number": r.get("contract_number"),
        "client_id": r["client_id"], "number": r["number"],
        "issued_at": _iso(r["issued_at"]), "due_at": _iso(r["due_at"]),
        "currency": r["currency"], "status": r["status"],
        "status_label": STATUS_LABEL.get(r["status"]),
        "status_changed_at": _iso(r["status_changed_at"]),
        "editable": r["status"] == EDITABLE,
        "client": {
            "name": r["client_name"], "inn": r["client_inn"],
            "address": r["client_address"], "bank": r["client_bank"],
            "mfo": r["client_mfo"], "account": r["client_account"],
            "director": r["client_director"],
            "vat_payer": r["client_vat_payer"],
        },
        "own": {
            "name": r["own_name"], "inn": r["own_inn"],
            "address": r["own_address"], "bank": r["own_bank"],
            "mfo": r["own_mfo"], "account": r["own_account"],
            "director": r["own_director"],
        },
        "note": r["note"], "created_by": r["created_by"],
        "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
    }
    if lines is not None:
        out["lines"] = [shape_line(x) for x in lines]
        t = totals(lines)
        out["totals"] = {
            "net": float(t["net"]), "vat": float(t["vat"]),
            "total": float(t["total"]),
            # Bosma shakl uchun: raqamdagi nolni qo'shib qo'yish oson,
            # so'zdagisini esa emas.
            "words": amount_words(t["total"], r["currency"]),
        }
    if payments is not None:
        out["payments"] = [shape_payment(x) for x in payments]
        paid = sum(Decimal(str(p["amount"])) for p in payments)
        total = Decimal(str(out.get("totals", {}).get("total", 0)))
        out["paid"] = float(paid)
        # "Qisman to'landi" — HISOB natijasi, status emas.
        out["balance"] = float(total - paid)
        out["fully_paid"] = bool(payments) and paid >= total
    return out


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def list_(status: Optional[str] = None, client_id: Optional[int] = None,
          opportunity_id: Optional[int] = None,
          owner_broker_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _need_schema()
    if status and status not in STATUS_LABEL:
        raise ErpError("Noma'lum status.")
    rows = db.query(INV_LIST_SQL, {"status": status, "client_id": client_id,
                                   "opportunity_id": opportunity_id,
                                   "owner_broker_id": owner_broker_id})
    out = []
    for r in rows:
        lines = db.query(LINES_SQL, {"id": r["id"]})
        pays = db.query(PAYMENTS_SQL, {"id": r["id"]})
        out.append(shape(r, lines=lines, payments=pays))
    return out


def get(invoice_id: int) -> Dict[str, Any]:
    _need_schema()
    r = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not r:
        raise ErpError("Faktura topilmadi.", 404)
    return shape(r, lines=db.query(LINES_SQL, {"id": invoice_id}),
                 payments=db.query(PAYMENTS_SQL, {"id": invoice_id}))


def _editable(inv: Dict[str, Any]) -> None:
    if inv["status"] != EDITABLE:
        raise ErpError(
            f"Faktura '{STATUS_LABEL.get(inv['status'])}' holatida — "
            f"tahrirlanmaydi. Xato bo'lsa bekor qiling va yangisini "
            f"chiqaring.", 409)



# --- KIM O'ZGARTIRDI (audit) ------------------------------------------------
# Pul hujjatlarining har o'zgarishi `erp.doc_audit` ga TRIGGER orqali
# yoziladi (schema_patch_erp_16.sql). Trigger ismni bazadan bila olmaydi
# — u `SET LOCAL erp.actor` dan o'qiydi, ya'ni ismni SHU YERDA berish
# kerak: `db.execute_returning(..., actor=...)`.
#
# Berilmasa jurnalda `actor IS NULL` qoladi va bu "ERP dan tashqarida
# o'zgartirilgan" degani. Shuning uchun har yozuvda ism uzatiladi —
# aks holda ilovaning o'z o'zgarishi ham "tashqaridan" bo'lib ko'rinardi.


def create(data: Dict[str, Any]) -> Dict[str, Any]:
    """Yangi faktura (qoralama). Rekvizitlar SHU PAYTDA ko'chiriladi."""
    _need_schema()
    client_id = data.get("client_id")
    if not client_id:
        raise ErpError("Mijoz tanlanmagan.")
    cl = db.query_one(CLIENT_SQL, {"id": client_id})
    if not cl:
        raise ErpError("Mijoz topilmadi.", 404)

    contract_id = data.get("contract_id")
    opp_id = data.get("opportunity_id")
    currency = (data.get("currency") or "").strip().upper() or None
    if contract_id:
        k = db.query_one(CONTRACT_SQL, {"id": contract_id})
        if not k:
            raise ErpError("Shartnoma topilmadi.", 404)
        # Shartnomadan MEROS: kartani va valyutani ikki marta yozmaslik uchun.
        opp_id = opp_id or k["opportunity_id"]
        currency = currency or k["currency"]

    own = db.query_one(OWN_SQL) or {}
    row = db.execute_returning(INV_INSERT_SQL, actor=data.get("created_by"),
                               params={
        "opportunity_id": opp_id, "contract_id": contract_id,
        "client_id": client_id, "number": (data.get("number") or None),
        "issued_at": data.get("issued_at"), "due_at": data.get("due_at"),
        "currency": currency or "UZS", "note": data.get("note"),
        "created_by": data.get("created_by"),
        "client_name": cl["name"], "client_inn": cl["inn"],
        "client_address": cl["address_legal"] or cl["address_actual"],
        "client_bank": cl["bank_name"], "client_mfo": cl["bank_mfo"],
        "client_account": cl["bank_account"],
        "client_director": cl["director_name"],
        "client_vat_payer": cl["vat_payer"],
        "own_name": own.get("name"), "own_inn": own.get("inn"),
        "own_address": own.get("address_legal") or own.get("address_actual"),
        "own_bank": own.get("bank_name"), "own_mfo": own.get("bank_mfo"),
        "own_account": own.get("bank_account"),
        "own_director": own.get("director_name")})
    return get(row["id"])


def update(invoice_id: int, data: Dict[str, Any],
           actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not cur:
        raise ErpError("Faktura topilmadi.", 404)
    _editable(cur)
    db.execute_returning(INV_UPDATE_SQL, actor=actor, params={
        "id": invoice_id,
        "number": (data.get("number") or None),
        "issued_at": data.get("issued_at") or cur["issued_at"],
        "due_at": data.get("due_at"),
        "currency": ((data.get("currency") or cur["currency"]).strip().upper()),
        "contract_id": data.get("contract_id", cur["contract_id"]),
        "note": data.get("note")})
    return get(invoice_id)


def default_vat_rate(client_id: int) -> Decimal:
    """Sukut stavka — IKKALA TOMONGA qarab.

    QQS ni SOTUVCHI hisoblaydi: biz to'lovchi bo'lmasak, mijoz to'lovchi
    bo'lsa ham faktura QQS'siz chiqadi. Shuning uchun ikki savol:

        BIZ to'lovchimizmi?   -> `erp.own_company.vat_payer`
        MIJOZ to'lovchimi?    -> `erp.client_company.vat_payer`

    Uchala javob ham `NULL` bo'lishi mumkin va u "HALI SO'RALMAGAN"
    degani — `false` bilan bir xil emas:

      - bizniki `false`  -> 0 (biz QQS hisoblamaymiz, savol tugadi);
      - bizniki `NULL`   -> ESKI xatti-harakat: stavka mijozdan. Patch
        qo'llangan kuniyoq fakturalar QQS'siz chiqib ketmasligi kerak;
      - mijozniki `false`/`NULL` -> 0 (taxmin qilib 12% qo'yish QQS'siz
        mijozga jimgina soliq qo'shib qo'yardi).

    Ikkala stavka ham berilgan va FARQ QILSA — KICHIGI olinadi: ortiqcha
    soliq qo'shib qo'yish, kam qo'shishdan xavfliroq (mijoz to'lamagan
    pulni keyin undirib bo'lmaydi).
    """
    own = db.query_one(OWN_SQL) or {}
    if own.get("vat_payer") is False:
        return Decimal("0")

    cl = db.query_one(CLIENT_SQL, {"id": client_id})
    if not cl or not cl["vat_payer"]:
        return Decimal("0")
    rate = Decimal(str(cl["vat_rate"] or 0))

    if own.get("vat_payer") and own.get("vat_rate") is not None:
        rate = min(rate, Decimal(str(own["vat_rate"])))
    return rate


def add_line(invoice_id: int, data: Dict[str, Any],
             actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not cur:
        raise ErpError("Faktura topilmadi.", 404)
    _editable(cur)

    name = (data.get("name") or "").strip()
    if not name:
        raise ErpError("Qator nomi bo'sh.")
    qty = _dec(data.get("qty"), "qty")
    price = _dec(data.get("price"), "price")
    if qty <= 0:
        raise ErpError("Miqdor musbat bo'lishi kerak.")
    if price < 0:
        raise ErpError("Narx manfiy bo'lolmaydi.")

    # Stavka berilmasa — mijoz passportidan. Qatorga NUSXA yoziladi.
    rate = data.get("vat_rate")
    rate = (default_vat_rate(cur["client_id"]) if rate is None
            else _dec(rate, "vat_rate"))
    if rate < 0:
        raise ErpError("QQS stavkasi manfiy bo'lolmaydi.")

    pos = data.get("pos")
    if pos is None:
        pos = (db.scalar("SELECT COALESCE(max(pos), 0) + 1 FROM erp.invoice_line "
                         "WHERE invoice_id = %(id)s", {"id": invoice_id}) or 1)

    db.execute_returning(LINE_INSERT_SQL, actor=actor, params={
        "invoice_id": invoice_id, "pos": pos,
        "product_id": data.get("product_id"), "name": name,
        "unit": (data.get("unit") or None), "qty": qty, "price": price,
        "vat_rate": rate, "note": (data.get("note") or None)})
    return get(invoice_id)


def delete_line(invoice_id: int, line_id: int,
                actor: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not cur:
        raise ErpError("Faktura topilmadi.", 404)
    _editable(cur)
    if not db.execute_returning(LINE_DELETE_SQL, actor=actor,
                                params={"id": line_id,
                                        "invoice_id": invoice_id}):
        raise ErpError("Qator topilmadi.", 404)
    return get(invoice_id)


def set_status(invoice_id: int, status: str,
               actor: Optional[str] = None) -> Dict[str, Any]:
    """Holatni o'zgartirish.

    `issued` ga o'tish uchun faktura TO'LIQ bo'lishi kerak: raqam, sana va
    kamida bitta qator. Bo'sh hujjatni "chiqarildi" deb belgilash uni
    yolg'onga aylantiradi."""
    _need_schema()
    if status not in STATUS_LABEL:
        raise ErpError("Noma'lum status.")
    cur = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not cur:
        raise ErpError("Faktura topilmadi.", 404)
    if cur["status"] == status:
        return get(invoice_id)
    if cur["status"] == "cancelled":
        raise ErpError("Bekor qilingan fakturani qaytarib bo'lmaydi — "
                       "yangisini chiqaring.", 409)

    if status in ("issued", "sent", "paid"):
        missing = []
        if not cur["number"]:
            missing.append("raqam")
        if not cur["issued_at"]:
            missing.append("sana")
        if not db.query(LINES_SQL, {"id": invoice_id}):
            missing.append("kamida bitta qator")
        if missing:
            raise ErpError("Chiqarish uchun yetishmayapti: "
                           + ", ".join(missing) + ".")

    db.execute_returning(INV_STATUS_SQL, actor=actor,
                         params={"id": invoice_id, "status": status})
    return get(invoice_id)


def add_payment(invoice_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """To'lov qayd etish.

    Ortiqcha to'lov TAQIQLANMAYDI (ombordagi manfiy qoldiq bilan bir xil
    sabab: haqiqiy hayotda shunday bo'ladi), lekin javobda `balance`
    manfiy bo'ladi va interfeys ko'rsatadi.

    To'liq to'langanda status AVTOMATIK `paid` bo'ladi — odam ikkinchi
    marta bosib o'tirmasin."""
    _need_schema()
    cur = db.query_one(INV_GET_SQL, {"id": invoice_id})
    if not cur:
        raise ErpError("Faktura topilmadi.", 404)
    if cur["status"] == "cancelled":
        raise ErpError("Bekor qilingan fakturaga to'lov yozilmaydi.", 409)
    if cur["status"] == "draft":
        raise ErpError("Qoralamaga to'lov yozilmaydi — avval fakturani "
                       "chiqaring.", 409)

    amount = _dec(data.get("amount"), "amount")
    if amount <= 0:
        raise ErpError("To'lov summasi musbat bo'lishi kerak.")
    method = (data.get("method") or "bank").strip()
    if method not in METHOD_LABEL:
        raise ErpError("Noma'lum to'lov usuli.")
    if not data.get("paid_at"):
        raise ErpError("To'lov sanasi majburiy.")

    db.execute_returning(PAYMENT_INSERT_SQL, actor=data.get("created_by"),
                         params={
        "invoice_id": invoice_id, "paid_at": data.get("paid_at"),
        "amount": amount, "method": method,
        "doc_ref": (data.get("doc_ref") or None),
        "note": (data.get("note") or None),
        "created_by": data.get("created_by")})

    out = get(invoice_id)
    if out.get("fully_paid") and out["status"] != "paid":
        db.execute_returning(INV_STATUS_SQL, actor=data.get("created_by"),
                             params={"id": invoice_id,
                                              "status": "paid"})
        out = get(invoice_id)
    return out


def delete_payment(payment_id: int,
                   actor: Optional[str] = None) -> Dict[str, Any]:
    """To'lovni o'chirish (xato kiritilgan bo'lsa).

    Faktura `paid` edi va endi yetmay qolsa — status `issued` ga
    QAYTARILADI: aks holda "to'landi" deb turgan, lekin qarzi bor
    faktura qolardi."""
    _need_schema()
    row = db.execute_returning(PAYMENT_DELETE_SQL, actor=actor,
                               params={"id": payment_id})
    if not row:
        raise ErpError("To'lov topilmadi.", 404)
    out = get(row["invoice_id"])
    if out["status"] == "paid" and not out.get("fully_paid"):
        db.execute_returning(INV_STATUS_SQL, actor=actor,
                             params={"id": row["invoice_id"],
                                              "status": "issued"})
        out = get(row["invoice_id"])
    return out


def stats() -> Dict[str, Any]:
    """Rahbar ko'rinishi: holat bo'yicha soni va summasi, qarz."""
    _need_schema()
    rows = list_()
    by_status: Dict[str, Dict[str, Any]] = {}
    debt = Decimal("0")
    for inv in rows:
        b = by_status.setdefault(inv["status"], {
            "code": inv["status"], "label": inv["status_label"],
            "count": 0, "total": 0.0})
        b["count"] += 1
        b["total"] = round(b["total"] + (inv.get("totals", {}).get("total") or 0), 2)
        if inv["status"] in ("issued", "sent"):
            debt += Decimal(str(inv.get("balance") or 0))
    return {
        "by_status": [by_status[c] for c, _ in STATUSES if c in by_status],
        "count": len(rows),
        # Qarz — CHIQARILGAN, lekin to'lanmagan qismi.
        "debt": float(debt),
    }


# ---------------------------------------------------------------------------
# ZANJIR: karta -> shartnoma -> faktura
# ---------------------------------------------------------------------------
def from_opportunity(opp_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Kartadan faktura chiqarish (qoralama).

    NIMA AVTOMATIK TO'LDIRILADI:
      - mijoz va valyuta — kartadan (shartnoma bo'lsa undan);
      - shartnoma — kartaning eng so'nggisi;
      - QATORLAR — kartaga AJRATILGAN tovarlardan (`erp.stock_reserve`):
        nomi, o'lchov birligi va miqdori haqiqiy, narx esa tender-ai
        katalogidagi SOTUV narxi.

    NIMA AVTOMATIK TO'LDIRILMAYDI VA NEGA:
      - narx bo'lmasa 0 qoladi — taxmin qilib tannarxni yozib qo'yish
        fakturani jimgina noto'g'ri qilardi;
      - shartnoma SUMMASI qatorga aylantirilmaydi: u QQS bilanmi yoki
        QQS sizmi — noma'lum, va bu farq fakturaning butun hisobini
        o'zgartiradi. Rezerv yo'q bo'lsa faktura QATORSIZ chiqadi va
        odam o'zi to'ldiradi.

    Javobda `filled` bo'ladi: nechta qator qayerdan kelgani. Interfeys
    buni ochiq aytadi — "3 ta qator rezervdan olindi, narxlarni
    tekshiring"."""
    _need_schema()
    opp = db.query_one(OPP_SQL, {"id": opp_id})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)
    if not opp["client_id"]:
        raise ErpError("Kartada mijoz ko'rsatilmagan — faktura kimga "
                       "yozilishi noma'lum.")

    k = db.query_one(OPP_CONTRACT_SQL, {"id": opp_id})
    inv = create({
        "client_id": opp["client_id"],
        "contract_id": k["id"] if k else None,
        "opportunity_id": opp_id,
        "number": data.get("number"),
        "issued_at": data.get("issued_at"),
        "due_at": data.get("due_at"),
        "currency": (data.get("currency") or (k["currency"] if k else None)
                     or opp["currency"]),
        "note": data.get("note"),
        "created_by": data.get("created_by"),
    })

    rows = db.query(OPP_RESERVES_SQL, {"id": opp_id})
    no_price = 0
    for i, r in enumerate(rows, start=1):
        if r["price"] is None:
            no_price += 1
        add_line(inv["id"], {
            "product_id": r["product_id"], "name": r["product_name"],
            "unit": r["unit"], "qty": r["qty"],
            "price": r["price"] if r["price"] is not None else 0,
            "pos": i})

    out = get(inv["id"])
    out["filled"] = {
        "lines": len(rows),
        # Narxi topilmaganlar: interfeys ularni ajratib ko'rsatadi.
        "no_price": no_price,
        "from_contract": bool(k),
        "contract_number": k["number"] if k else None,
    }
    return out
