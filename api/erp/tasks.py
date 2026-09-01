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
from api.erp.opportunity import ErpError, _iso, _need_schema, _num

TASK_FIELDS = ("title", "assignee_broker_id", "due_at", "note")


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
t.due_at, t.done, t.done_at, t.note, t.reminded_at, t.created_by, t.created_at
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

TASK_INSERT_SQL = """
INSERT INTO erp.opportunity_task
    (opportunity_id, title, assignee_broker_id, due_at, note, created_by)
VALUES (%(opportunity_id)s, %(title)s, %(assignee_broker_id)s, %(due_at)s,
        %(note)s, %(created_by)s)
RETURNING id
"""

# Muddat O'ZGARSA eslatma qaytadan yuborilishi kerak — shuning uchun
# `reminded_at` tozalanadi. Aks holda ko'chirilgan muddat jimgina o'tib ketardi.
TASK_UPDATE_SQL = """
UPDATE erp.opportunity_task SET
    title=%(title)s, assignee_broker_id=%(assignee_broker_id)s,
    due_at=%(due_at)s, note=%(note)s,
    reminded_at = CASE WHEN due_at IS DISTINCT FROM %(due_at)s
                       THEN NULL ELSE reminded_at END
WHERE id = %(id)s
RETURNING id
"""

TASK_DONE_SQL = """
UPDATE erp.opportunity_task SET
    done = %(done)s,
    done_at = CASE WHEN %(done)s THEN now() ELSE NULL END
WHERE id = %(id)s
RETURNING id, done
"""

TASK_DELETE_SQL = "DELETE FROM erp.opportunity_task WHERE id = %(id)s RETURNING id"

# "Mening ishlarim": bajarilmagan vazifalar + karta konteksti. Muddati
# o'tganlar ham chiqadi va eng yuqorida turadi — ular eng shoshilinchi.
MY_TASKS_SQL = f"""
SELECT {_TASK_COLS},
       o.title AS opp_title, o.status, o.deadline_at, o.tender_id,
       o.start_price, o.currency,
       c.name AS client_name, ob.full_name AS opp_broker_name
{_TASK_FROM}
JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE NOT t.done
  AND (%(broker_id)s::int IS NULL
       OR t.assignee_broker_id = %(broker_id)s
       OR (t.assignee_broker_id IS NULL AND o.broker_id = %(broker_id)s))
  AND (t.due_at IS NULL OR t.due_at <= current_date + %(days)s::int)
  AND o.status NOT IN ('won','lost','rejected')
ORDER BY t.due_at NULLS LAST, t.id
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
JOIN erp.opportunity o ON o.id = t.opportunity_id
LEFT JOIN erp.client_company c ON c.id = o.client_id
LEFT JOIN erp.broker ob ON ob.id = o.broker_id
WHERE NOT t.done
  AND t.reminded_at IS NULL
  AND t.due_at IS NOT NULL
  AND t.due_at <= current_date + %(days)s::int
  AND o.status NOT IN ('won','lost','rejected')
  -- EGALIK (api/erp/egalik.py): brokerga faqat O'Z kartalari.
  AND (%(owner_broker_id)s::int IS NULL OR o.broker_id = %(owner_broker_id)s)
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
WHERE o.status NOT IN ('won','lost','rejected')
  AND o.deadline_reminded_at IS NULL
  AND o.deadline_at IS NOT NULL
  AND o.deadline_at <= now() + (%(days)s || ' days')::interval
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
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"], "title": r["title"],
        "assignee": ({"id": r["assignee_broker_id"], "name": r["assignee_name"]}
                     if r["assignee_broker_id"] else None),
        "due_at": _iso(r["due_at"]), "done": r["done"], "done_at": _iso(r["done_at"]),
        "note": r["note"], "reminded_at": _iso(r["reminded_at"]),
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
        # Kechikkanini SERVER aytadi: brauzer soati noto'g'ri bo'lishi mumkin,
        # "kechikdi" degan xabar esa qaror qabul qilishga ta'sir qiladi.
        "overdue": bool(r["due_at"] and not r["done"] and _is_past(r["due_at"])),
    }


def _is_past(d) -> bool:
    import datetime as _dt
    return d < _dt.date.today()


def _shape_my(r: dict) -> dict:
    out = shape(r)
    out["opportunity"] = {
        "id": r["opportunity_id"], "title": r["opp_title"], "status": r["status"],
        "tender_id": r["tender_id"], "client_name": r["client_name"],
        "broker_name": r["opp_broker_name"], "deadline_at": _iso(r["deadline_at"]),
        "start_price": _num(r["start_price"]), "currency": r["currency"],
    }
    return out


def _check(data: dict) -> None:
    if not (data.get("title") or "").strip():
        raise ErpError("Vazifa nomi bo'sh.")


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def list_(opp_id: int) -> List[dict]:
    _need_schema3()
    return [shape(r) for r in db.query(TASKS_SQL, {"id": opp_id})]


def add(opp_id: int, data: dict) -> List[dict]:
    """Javob — kartaning BUTUN vazifalar ro'yxati: interfeys qayta so'ramasin."""
    _need_schema3()
    _check(data)
    if not db.query_one("SELECT 1 AS x FROM erp.opportunity WHERE id=%(id)s",
                        {"id": opp_id}):
        raise ErpError("Karta topilmadi.", 404)
    db.execute_returning(TASK_INSERT_SQL, {
        **{k: data.get(k) for k in TASK_FIELDS},
        "title": data["title"].strip(),
        "opportunity_id": opp_id, "created_by": data.get("created_by")})
    return list_(opp_id)


def update(task_id: int, data: dict) -> List[dict]:
    _need_schema3()
    _check(data)
    cur = db.query_one(TASK_GET_SQL, {"id": task_id})
    if not cur:
        raise ErpError("Vazifa topilmadi.", 404)
    db.execute_returning(TASK_UPDATE_SQL, {
        **{k: data.get(k) for k in TASK_FIELDS},
        "title": data["title"].strip(), "id": task_id})
    return list_(cur["opportunity_id"])


def set_done(task_id: int, done: bool) -> List[dict]:
    _need_schema3()
    cur = db.query_one(TASK_GET_SQL, {"id": task_id})
    if not cur:
        raise ErpError("Vazifa topilmadi.", 404)
    db.execute_returning(TASK_DONE_SQL, {"id": task_id, "done": bool(done)})
    return list_(cur["opportunity_id"])


def delete(task_id: int) -> List[dict]:
    _need_schema3()
    cur = db.query_one(TASK_GET_SQL, {"id": task_id})
    if not cur:
        raise ErpError("Vazifa topilmadi.", 404)
    db.execute_returning(TASK_DELETE_SQL, {"id": task_id})
    return list_(cur["opportunity_id"])


def my_tasks(broker_id: Optional[int] = None, days: int = 0) -> Dict[str, Any]:
    """"Mening bugungi ishlarim". `days=0` — bugun va kechikkanlar;
    `days=7` — kelasi haftaga ham qaraydi.

    Mas'ul ko'rsatilmagan vazifa KARTA BROKERINIKI hisoblanadi — aks holda
    "keyingi vazifa" dan ko'chirilgan eski yozuvlar hech kimda ko'rinmasdi."""
    _need_schema3()
    rows = [_shape_my(r) for r in db.query(MY_TASKS_SQL,
                                           {"broker_id": broker_id, "days": days})]
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
    tasks = [_shape_task_reminder(r)
             for r in db.query(DUE_TASKS_SQL, {
                 "days": days, "owner_broker_id": owner_broker_id})]
    deadlines = [{"id": r["id"], "title": r["title"], "tender_ref": r["tender_ref"],
                  "deadline_at": _iso(r["deadline_at"]), "status": r["status"],
                  "start_price": _num(r["start_price"]), "currency": r["currency"],
                  "broker_name": r["broker_name"], "broker_id": r["broker_id"],
                  "client_name": r["client_name"]}
                 for r in db.query(DUE_DEADLINES_SQL, {
                     "days": str(deadline_days),
                     "owner_broker_id": owner_broker_id})]
    return {"tasks": tasks, "deadlines": deadlines,
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
