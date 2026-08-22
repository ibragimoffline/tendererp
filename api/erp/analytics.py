"""ERP 5A-2: rahbar tahlili — bosqich vaqtlari, voronka, qotib qolganlar.

YANGI JADVAL YO'Q. Hamma javob `erp.opportunity_history` da allaqachon bor:
har status o'tishi vaqti bilan yozilgan (1-bosqichdan beri). Bu modul faqat
o'sha yozuvlardan savol so'raydi.

Chegara:
  - Faqat erp.* o'qiladi, hech narsa yozilmaydi.
  - Hisob BAZADA (window funksiyalar va GROUP BY), frontendда emas.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from api import db
from api.erp.opportunity import FINAL, STATUS_LABEL, _need_schema, _num

# --- 1. Bosqichda o'tgan vaqt ------------------------------------------------
# LEAD: har yozuvdan keyingi o'tish vaqti — ikkisining farqi shu bosqichda
# turgan vaqt. TUGAGAN turishlargina o'rtachaga kiradi (`next_at IS NOT NULL`):
# hozir shu bosqichda turgan kartaning vaqti hali tugamagan, uni o'rtachaga
# qo'shish ko'rsatkichni pasaytirib yuborardi. Ular alohida sanaladi.
STAGE_TIME_SQL = """
WITH steps AS (
    SELECT h.opportunity_id, h.to_status, h.changed_at,
           LEAD(h.changed_at) OVER (PARTITION BY h.opportunity_id
                                    ORDER BY h.changed_at, h.id) AS next_at
    FROM erp.opportunity_history h
),
done AS (
    SELECT to_status,
           EXTRACT(EPOCH FROM (next_at - changed_at)) / 86400.0 AS days
    FROM steps WHERE next_at IS NOT NULL
),
ongoing AS (
    SELECT s.to_status, count(*) AS n,
           EXTRACT(EPOCH FROM (now() - max(s.changed_at))) / 86400.0 AS oldest_days
    FROM steps s
    JOIN erp.opportunity o ON o.id = s.opportunity_id
    WHERE s.next_at IS NULL AND o.status NOT IN ('won','lost','rejected')
    GROUP BY s.to_status
)
SELECT st.code AS status,
       coalesce(d.n, 0)         AS finished_n,
       d.avg_days, d.median_days, d.max_days,
       coalesce(g.n, 0)         AS ongoing_n,
       g.oldest_days
FROM (SELECT unnest(%(codes)s::text[]) AS code) st
LEFT JOIN (
    SELECT to_status, count(*) AS n,
           round(avg(days)::numeric, 1) AS avg_days,
           round((percentile_cont(0.5) WITHIN GROUP (ORDER BY days))::numeric, 1)
               AS median_days,
           round(max(days)::numeric, 1) AS max_days
    FROM done GROUP BY to_status
) d ON d.to_status = st.code
LEFT JOIN ongoing g ON g.to_status = st.code
"""

# --- 2. Voronka --------------------------------------------------------------
# "Necha karta shu bosqichga YETIB BORGAN" — hozirgi holati emas, tarixi.
# Karta 'new' dan 'won' ga o'tsa, u 'submitted' ni ham bosib o'tgan bo'lishi
# SHART emas (ish jarayoni erkin), shuning uchun sanoq tarixdan olinadi.
FUNNEL_SQL = """
SELECT st.code AS status, count(DISTINCT h.opportunity_id) AS reached
FROM (SELECT unnest(%(codes)s::text[]) AS code) st
LEFT JOIN erp.opportunity_history h ON h.to_status = st.code
GROUP BY st.code
"""

# --- 3. Broker bo'yicha sikl vaqti -------------------------------------------
# "Ishga olishdan topshirishgacha necha kun" — brokerni emas, JARAYONni
# o'lchaydi: qayerda sekinlashuv borligini ko'rsatadi.
BROKER_CYCLE_SQL = """
WITH firsts AS (
    SELECT opportunity_id, min(changed_at) AS started
    FROM erp.opportunity_history GROUP BY opportunity_id
),
marks AS (
    SELECT opportunity_id,
           min(changed_at) FILTER (WHERE to_status = 'submitted') AS submitted_at,
           min(changed_at) FILTER (WHERE to_status = 'won')       AS won_at
    FROM erp.opportunity_history GROUP BY opportunity_id
)
SELECT b.id, b.full_name,
       count(o.id) AS n,
       round(avg(EXTRACT(EPOCH FROM (m.submitted_at - f.started)) / 86400.0)
             ::numeric, 1) AS avg_to_submit,
       round(avg(EXTRACT(EPOCH FROM (m.won_at - f.started)) / 86400.0)
             ::numeric, 1) AS avg_to_win,
       count(m.submitted_at) AS submitted_n,
       count(m.won_at)       AS won_n
FROM erp.broker b
LEFT JOIN erp.opportunity o ON o.broker_id = b.id
LEFT JOIN firsts f ON f.opportunity_id = o.id
LEFT JOIN marks  m ON m.opportunity_id = o.id
GROUP BY b.id, b.full_name
ORDER BY n DESC, b.full_name
"""

# --- 4. Qotib qolganlar ------------------------------------------------------
# Ochiq, lekin uzoq vaqtdan beri qimirlamagan kartalar. Deadline yaqinlashsa
# bu ikki barobar muhim — shuning uchun muddat ham qaytadi.
STUCK_SQL = """
SELECT o.id, o.title, o.status, o.deadline_at, o.start_price, o.currency,
       o.status_changed_at,
       round(EXTRACT(EPOCH FROM (now() - o.status_changed_at)) / 86400.0) AS idle_days,
       b.full_name AS broker_name, c.name AS client_name,
       (SELECT count(*) FROM erp.opportunity_task t
        WHERE t.opportunity_id = o.id AND NOT t.done) AS open_tasks
FROM erp.opportunity o
LEFT JOIN erp.broker b ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
WHERE o.status NOT IN ('won','lost','rejected')
  AND o.status_changed_at < now() - (%(days)s || ' days')::interval
ORDER BY o.status_changed_at
"""

# --- 5. Yutqazish sabablari --------------------------------------------------
#: Nechta har xil valyuta ishlatilgan (aralashda summalar berilmaydi).
CURRENCIES_SQL = """
SELECT DISTINCT coalesce(nullif(trim(currency), ''), 'UZS') AS currency
FROM erp.opportunity WHERE start_price IS NOT NULL
"""

LOST_REASON_SQL = """
SELECT coalesce(lost_reason, 'unknown') AS reason, count(*) AS n,
       coalesce(sum(start_price), 0) AS total
FROM erp.opportunity WHERE status = 'lost'
GROUP BY 1 ORDER BY n DESC
"""


def build(stuck_days: int = 14) -> Dict[str, Any]:
    """Rahbar tahlili. `stuck_days` — necha kundan beri qimirlamagan karta
    "qotib qolgan" hisoblanadi."""
    _need_schema()
    codes = [c for c, _ in STATUS_LABEL.items()]

    stages = []
    for r in db.query(STAGE_TIME_SQL, {"codes": codes}):
        stages.append({
            "code": r["status"], "label": STATUS_LABEL.get(r["status"]),
            "finished_n": r["finished_n"],
            "avg_days": _num(r["avg_days"]), "median_days": _num(r["median_days"]),
            "max_days": _num(r["max_days"]),
            "ongoing_n": r["ongoing_n"],
            "oldest_days": (round(float(r["oldest_days"]), 1)
                            if r["oldest_days"] is not None else None),
            "final": r["status"] in FINAL,
        })
    # Kanban tartibini saqlaymiz — jadval ustunlari bilan bir xil o'qilsin
    order = {c: i for i, c in enumerate(codes)}
    stages.sort(key=lambda s: order.get(s["code"], 99))

    funnel_raw = {r["status"]: r["reached"] for r in db.query(FUNNEL_SQL, {"codes": codes})}
    new_n = funnel_raw.get("new", 0)
    funnel = [{"code": c, "label": STATUS_LABEL.get(c), "reached": funnel_raw.get(c, 0),
               # Konversiya BOSHLANG'ICHDAN: "ishga olinganlarning necha foizi
               # shu bosqichga yetdi". Bosqichdan bosqichga emas, chunki ish
               # jarayoni erkin — karta bosqichni o'tkazib yuborishi mumkin.
               "pct": (round(100 * funnel_raw.get(c, 0) / new_n) if new_n else None)}
              for c in codes]

    # ARALASH VALYUTA QO'SHILMAYDI: summalar bir nechta valyutadan
    # yig'ilgan bo'lsa son o'rniga `None` qaytadi. Sanoq (`n`) esa
    # valyutaga bog'liq emas va qoladi.
    mixed = len(db.query(CURRENCIES_SQL)) > 1
    lost = [{"code": r["reason"], "n": r["n"],
             "total": (None if mixed else _num(r["total"]))}
            for r in db.query(LOST_REASON_SQL)]

    return {
        "stages": stages,
        "funnel": funnel,
        "by_broker": [{**r, "avg_to_submit": _num(r["avg_to_submit"]),
                       "avg_to_win": _num(r["avg_to_win"])}
                      for r in db.query(BROKER_CYCLE_SQL)],
        "stuck": [{"id": r["id"], "title": r["title"], "status": r["status"],
                   "status_label": STATUS_LABEL.get(r["status"]),
                   "idle_days": int(r["idle_days"]),
                   "status_changed_at": r["status_changed_at"].isoformat()
                   if r["status_changed_at"] else None,
                   "deadline_at": r["deadline_at"].isoformat() if r["deadline_at"] else None,
                   "start_price": _num(r["start_price"]), "currency": r["currency"],
                   "broker_name": r["broker_name"], "client_name": r["client_name"],
                   "open_tasks": r["open_tasks"]}
                  for r in db.query(STUCK_SQL, {"days": str(stuck_days)})],
        "lost_reasons": lost,
        "stuck_days": stuck_days,
    }
