"""
FOYDA — "bu tenderdan qancha ishladik?"

Javob uchun uch son kerak va har biri boshqa joydan keladi:

    DAROMAD  — chiqarilgan fakturalarning QQS SIZ summasi.
               QQS daromad EMAS: u davlatniki, biz faqat yig'ib beramiz.
               Bekor qilingan faktura hisobga olinmaydi.

    TANNARX  — kartaga sarflangan tovarning tannarxi. Ombor harakatida
               MUZLATILGAN narx olinadi (`stock_move.unit_cost`), joriy
               katalog narxi emas: aks holda foyda raqami katalog
               o'zgargan sayin o'zgarib turardi.

    FOYDA    — daromad - tannarx. Foiz: foyda / daromad.

TO'LIQ BO'LMAGAN HISOB OCHIQ AYTILADI. Uch holat bor va ular
yashirilmaydi:

  1. tannarxi NOMA'LUM chiqimlar (`unit_cost IS NULL`) — katalogda narx
     ko'rsatilmagan yoki harakat eski. Ular `unknown_cost_moves` da
     sanaladi va tannarxga QO'SHILMAYDI (nolga aylantirilmaydi);
  2. faktura yo'q — daromad nol, lekin bu "zarar" degani emas: hujjat
     hali chiqarilmagan;
  3. ombor ishlatilmagan — tannarx nol. Xizmat ko'rsatishda bu normal.

Har uchalasi javobda alohida ko'rsatiladi, chunki "foyda 5 mln"
degan raqamdan ko'ra "foyda 5 mln, lekin 3 ta chiqimning tannarxi
noma'lum" degani ancha foydali.

ARALASH VALYUTA QO'SHILMAYDI. Yig'indi HAR VALYUTA uchun alohida
chiqadi (UZS: ..., USD: ...), umumiy bitta son esa faqat hamma karta
bitta valyutada bo'lgandagina. Kurs bo'yicha konvertatsiya YO'Q:
kurs qaysi kunniki degan savolga javob yo'q va noto'g'ri yig'indi
yo'q yig'indidan yomonroq. Bu — loyihadagi umumiy qoida (narx va
ball aralashtirilmaydi, `erp_arxitektura.md`).

RAHBAR KO'RINISHI: pul haqidagi umumiy ko'rsatkich har kimga emas —
endpointlar `manager` huquqini talab qiladi.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError, _need_schema

#: Daromadga kirmaydigan faktura holatlari.
#: `draft` ham kirmaydi: qoralama hali hujjat emas.
REVENUE_EXCLUDE = ("draft", "cancelled")


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
# Daromad: faktura QATORLARIDAN (QQS siz). `invoice` jadvalida summa
# saqlanmaydi — bu loyihaning umumiy qoidasi.
REVENUE_SQL = """
SELECT i.opportunity_id,
       COALESCE(SUM(l.qty * l.price), 0)               AS net,
       COALESCE(SUM(l.qty * l.price * l.vat_rate / 100), 0) AS vat,
       count(DISTINCT i.id)                            AS invoices
FROM erp.invoice i
JOIN erp.invoice_line l ON l.invoice_id = i.id
WHERE i.status <> ALL(%(exclude)s)
  AND (%(opp_id)s::int IS NULL OR i.opportunity_id = %(opp_id)s)
  AND i.opportunity_id IS NOT NULL
GROUP BY i.opportunity_id
"""

# Tannarx: kartaga bog'langan CHIQIMLAR (`qty < 0`). Kirim va tuzatish
# hisobga olinmaydi — ular sotuv emas.
#
# `unit_cost IS NULL` bo'lgan qatorlar ALOHIDA sanaladi va summaga
# qo'shilmaydi.
COST_SQL = """
SELECT m.opportunity_id,
       COALESCE(SUM(CASE WHEN m.unit_cost IS NOT NULL
                         THEN -m.qty * m.unit_cost END), 0) AS cost,
       count(*) FILTER (WHERE m.unit_cost IS NULL)          AS unknown_moves,
       count(*)                                             AS moves
FROM erp.stock_move m
WHERE m.kind = 'out' AND m.qty < 0
  AND m.opportunity_id IS NOT NULL
  AND (%(opp_id)s::int IS NULL OR m.opportunity_id = %(opp_id)s)
GROUP BY m.opportunity_id
"""

OPPS_SQL = """
SELECT o.id, o.title, o.status, o.currency, o.created_at,
       b.full_name AS broker_name, c.name AS client_name
FROM erp.opportunity o
LEFT JOIN erp.broker b         ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
WHERE (%(opp_id)s::int IS NULL OR o.id = %(opp_id)s)
  AND (%(status)s::text IS NULL OR o.status = %(status)s)
ORDER BY o.created_at DESC, o.id DESC
"""


def _num(v):
    return float(v) if v is not None else None


def _row(opp: Dict[str, Any], rev: Dict[str, Any],
         cost: Dict[str, Any]) -> Dict[str, Any]:
    net = Decimal(str(rev.get("net") or 0))
    c = Decimal(str(cost.get("cost") or 0))
    profit = net - c
    return {
        "opportunity_id": opp["id"], "title": opp["title"],
        "status": opp["status"], "currency": opp["currency"] or "UZS",
        "broker_name": opp.get("broker_name"),
        "client_name": opp.get("client_name"),
        # Daromad QQS SIZ: QQS davlatniki.
        "revenue": float(net),
        "vat": _num(rev.get("vat")) or 0.0,
        "invoices": rev.get("invoices") or 0,
        "cost": float(c),
        "profit": float(profit),
        # Foiz faqat daromad bo'lganda ma'noga ega: nolga bo'lish ham,
        # "0% foyda" degan yolg'on ham bo'lmasin.
        "margin": (round(float(profit / net * 100), 1) if net else None),
        # HISOB TO'LIQMI — javobda ochiq turadi.
        "unknown_cost_moves": cost.get("unknown_moves") or 0,
        "cost_moves": cost.get("moves") or 0,
        "complete": not (cost.get("unknown_moves") or 0),
    }


def for_opportunity(opp_id: int) -> Dict[str, Any]:
    _need_schema()
    opp = db.query_one(OPPS_SQL, {"opp_id": opp_id, "status": None})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)
    p = {"opp_id": opp_id, "exclude": list(REVENUE_EXCLUDE)}
    rev = db.query_one(REVENUE_SQL, p) or {}
    cost = db.query_one(COST_SQL, {"opp_id": opp_id}) or {}
    return _row(opp, rev, cost)


def report(status: Optional[str] = None,
           limit: int = 200) -> Dict[str, Any]:
    """Rahbar ko'rinishi: kartalar bo'yicha foyda va umumiy yig'indi."""
    _need_schema()
    opps = db.query(OPPS_SQL, {"opp_id": None, "status": status})[:max(1, limit)]
    rev = {r["opportunity_id"]: r for r in db.query(
        REVENUE_SQL, {"opp_id": None, "exclude": list(REVENUE_EXCLUDE)})}
    cost = {r["opportunity_id"]: r for r in db.query(
        COST_SQL, {"opp_id": None})}

    rows: List[Dict[str, Any]] = []
    for o in opps:
        row = _row(o, rev.get(o["id"], {}), cost.get(o["id"], {}))
        # Hech qanday pul harakati bo'lmagan kartalar ro'yxatni
        # to'ldirib yuboradi — ularni tashlab yuboramiz. Lekin tannarxi
        # NOMA'LUM karta qoladi: uning summasi nol ko'rinsa ham, aynan
        # shu karta hisobni to'liqsiz qilyapti — uni yashirish
        # yig'indini yolg'on qilardi.
        if row["revenue"] or row["cost"] or row["unknown_cost_moves"]:
            rows.append(row)

    unknown = sum(r["unknown_cost_moves"] for r in rows)
    by_cur = _by_currency(rows)
    return {
        "items": rows,
        # HAR VALYUTA uchun alohida qator. Aralashtirib qo'shilmaydi.
        "by_currency": by_cur,
        # Umumiy bitta son FAQAT hamma karta bitta valyutada bo'lganda.
        # Aks holda `None`: noto'g'ri yig'indi yo'q yig'indidan yomon.
        "totals": (by_cur[0] if len(by_cur) == 1 else None),
        "currencies": [c["currency"] for c in by_cur],
        "mixed_currency": len(by_cur) > 1,
        # Umumiy hisob to'liqmi. Bitta noma'lum tannarx ham butun
        # yig'indini shubhali qiladi, shuning uchun bu yerda ham bor.
        "unknown_cost_moves": unknown,
        "complete": not unknown,
    }


def _by_currency(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Valyutalar bo'yicha yig'indi.

    Konvertatsiya YO'Q va bo'lmaydi ham: "1200 USD + 15 mln UZS"
    degan yig'indi qaysi kungi kurs bilan hisoblangani noma'lum bo'lardi
    va hisobot har kuni boshqacha chiqardi."""
    acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        cur = r["currency"] or "UZS"
        a = acc.setdefault(cur, {"currency": cur, "revenue": Decimal("0"),
                                 "cost": Decimal("0"), "cards": 0,
                                 "unknown_cost_moves": 0})
        a["revenue"] += Decimal(str(r["revenue"]))
        a["cost"] += Decimal(str(r["cost"]))
        a["cards"] += 1
        a["unknown_cost_moves"] += r["unknown_cost_moves"]

    out = []
    for a in acc.values():
        profit = a["revenue"] - a["cost"]
        out.append({
            "currency": a["currency"],
            "revenue": float(a["revenue"]),
            "cost": float(a["cost"]),
            "profit": float(profit),
            "margin": (round(float(profit / a["revenue"] * 100), 1)
                       if a["revenue"] else None),
            "cards": a["cards"],
            "unknown_cost_moves": a["unknown_cost_moves"],
            "complete": not a["unknown_cost_moves"],
        })
    # Katta daromad birinchi: rahbar avval eng muhim valyutani ko'radi.
    out.sort(key=lambda x: (-x["revenue"], x["currency"]))
    return out
