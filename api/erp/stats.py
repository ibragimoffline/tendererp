"""ERP rahbar paneli — hisob BAZADA (GROUP BY), frontendda emas.

Chegara: faqat erp.* o'qiladi; public.* ga umuman murojaat yo'q.

ARALASH VALYUTA QO'SHILMAYDI. Kartalar bir nechta valyutada bo'lsa,
pul yig'indilari `None` qaytadi va `mixed_currency: true` bo'ladi —
interfeys o'sha joyda son o'rniga sababni yozadi. Kurs bo'yicha
konvertatsiya YO'Q: kurs qaysi kunniki degan savolga javob yo'q va
noto'g'ri yig'indi yo'q yig'indidan yomonroq. Sanoq (nechta karta)
esa doim to'g'ri — u valyutaga bog'liq emas va shuning uchun
qoldiriladi.
"""
from api import db
from api.erp.opportunity import (FINAL, STATUS_LABEL, _iso, _need_schema, _num)


def _yakuniy() -> list:
    """`FINAL` ni SQL massivi uchun. Ro'yxat KODDA, so'rovda emas:
    24-patchda `ulgurmadik` qo'shilganda qo'lda yozilgan har bir nusxa
    uni jimgina "ochiq" deb sanardi."""
    return sorted(FINAL)

BY_STATUS_SQL = """
SELECT status, count(*) AS n, coalesce(sum(start_price),0) AS total
FROM erp.opportunity GROUP BY status
"""

# LEFT JOIN broker'dan: kartasi yo'q broker ham ro'yxatda ko'rinsin
# (rahbar uchun "hech narsa olmagan" ham ma'lumot).
BY_BROKER_SQL = """
SELECT b.id, b.full_name, count(o.id) AS n,
       -- YAKUNIY ro'yxat KODDAN (`opportunity.FINAL`).
       count(o.id) FILTER (WHERE o.status <> ALL(%(final)s)) AS open_n,
       count(o.id) FILTER (WHERE o.status = 'won')  AS won_n,
       count(o.id) FILTER (WHERE o.status = 'lost') AS lost_n,
       coalesce(sum(o.start_price) FILTER (WHERE o.status <> ALL(%(final)s)),0)
           AS open_total
FROM erp.broker b LEFT JOIN erp.opportunity o ON o.broker_id = b.id
GROUP BY b.id, b.full_name ORDER BY n DESC, b.full_name
"""

BY_CLIENT_SQL = """
SELECT c.id, c.name, count(o.id) AS n,
       count(o.id) FILTER (WHERE o.status = 'won')  AS won_n,
       count(o.id) FILTER (WHERE o.status = 'lost') AS lost_n,
       coalesce(sum(o.start_price) FILTER (WHERE o.status = 'won'),0) AS won_total
FROM erp.client_company c LEFT JOIN erp.opportunity o ON o.client_id = c.id
GROUP BY c.id, c.name ORDER BY n DESC, c.name
"""

# Yaqin deadline'lar — faqat OCHIQ kartalar: yopilgan kartaning muddati
# rahbarga qiziq emas. Muddati o'tib ketganlari ham chiqadi (deadline_at < now),
# ular eng yuqorida turadi — "e'tibordan qolgan" degani.
UPCOMING_SQL = """
SELECT o.id, o.title, o.deadline_at, o.status, o.start_price, o.currency,
       b.full_name AS broker_name, c.name AS client_name
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
-- YAKUNIY ro'yxat KODDAN (`opportunity.FINAL`): qo'lda yozilgan
-- nusxa 24-patchdagi `ulgurmadik` ni JIMGINA "ochiq" deb sanardi.
WHERE o.status <> ALL(%(final)s)
  AND o.deadline_at IS NOT NULL
  AND o.deadline_at <= now() + (%(days)s || ' days')::interval
ORDER BY o.deadline_at
"""

#: Kartalarda nechta har xil valyuta bor. Bo'sh baza -> bitta ham yo'q.
CURRENCIES_SQL = """
SELECT DISTINCT coalesce(nullif(trim(currency), ''), 'UZS') AS currency
FROM erp.opportunity WHERE start_price IS NOT NULL
ORDER BY 1
"""

MONTHLY_SQL = """
SELECT to_char(date_trunc('month', closed_at), 'YYYY-MM') AS month,
       count(*) FILTER (WHERE status='won')      AS won,
       count(*) FILTER (WHERE status='lost')     AS lost,
       count(*) FILTER (WHERE status='rejected') AS rejected
FROM erp.opportunity WHERE closed_at IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC LIMIT 12
"""


def build(days: int = 7) -> dict:
    _need_schema()
    currencies = [r["currency"] for r in db.query(CURRENCIES_SQL)]
    mixed = len(currencies) > 1

    def money(v):
        """Aralash valyutada pul yig'indisi BERILMAYDI.

        Nol qaytarish yolg'on bo'lardi ("hech narsa yo'q"), qo'shib
        yuborish esa undan ham yomon ("1200 USD + 15 mln UZS")."""
        return None if mixed else _num(v)

    by_status = {r["status"]: {"n": r["n"], "total": money(r["total"])}
                 for r in db.query(BY_STATUS_SQL)}
    # Bo'sh statuslar ham ro'yxatda qoladi (Kanban ustunlari bilan bir xil
    # tartibda) — "0" ham javob, yo'qlik emas.
    statuses = [{"code": code, "label": label,
                 "n": by_status.get(code, {}).get("n", 0),
                 "total": (None if mixed
                           else by_status.get(code, {}).get("total", 0.0))}
                for code, label in STATUS_LABEL.items()]
    won = by_status.get("won", {}).get("n", 0)
    lost = by_status.get("lost", {}).get("n", 0)
    return {
        # Valyuta holati javobda OCHIQ turadi: interfeys nima
        # ko'rsatishni shundan biladi.
        "currency": (currencies[0] if len(currencies) == 1 else None),
        "currencies": currencies,
        "mixed_currency": mixed,
        "total": sum(s["n"] for s in statuses),
        "open": sum(s["n"] for s in statuses if s["code"] not in FINAL),
        "open_total": (None if mixed else
                       sum(s["total"] for s in statuses
                           if s["code"] not in FINAL)),
        "submitted": by_status.get("submitted", {}).get("n", 0),
        "won": won, "lost": lost,
        "won_total": (None if mixed
                      else by_status.get("won", {}).get("total", 0.0)),
        "rejected": by_status.get("rejected", {}).get("n", 0),
        # Yutish foizi faqat HAL BO'LGANLARIDAN: rad etilganlar ishtirok
        # etmagan, ularni maxrajga qo'shish ko'rsatkichni buzadi.
        "win_rate": (round(100 * won / (won + lost)) if (won + lost) else None),
        "by_status": statuses,
        "by_broker": [{**r, "open_total": money(r["open_total"])}
                      for r in db.query(BY_BROKER_SQL, {"final": _yakuniy()})],
        # 2-bosqich: mijoz kesimida yutish foizi ham. Maxrajda faqat HAL
        # BO'LGANLARI (yutilgan + yutqazilgan) — rad etilganlar qatnashmagan.
        "by_client": [{**r, "won_total": money(r["won_total"]),
                       "win_rate": (round(100 * r["won_n"] / (r["won_n"] + r["lost_n"]))
                                    if (r["won_n"] + r["lost_n"]) else None)}
                      for r in db.query(BY_CLIENT_SQL)],
        "upcoming": [{**r, "deadline_at": _iso(r["deadline_at"]),
                      "start_price": _num(r["start_price"]),
                      "status_label": STATUS_LABEL.get(r["status"])}
                     for r in db.query(UPCOMING_SQL, {"days": str(days), "final": _yakuniy()})],
        "monthly": db.query(MONTHLY_SQL),
        "upcoming_days": days,
    }
