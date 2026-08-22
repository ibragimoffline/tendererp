"""
PUL HUJJATLARI O'ZGARISHLAR JURNALI — "kim, qachon va nimani o'zgartirdi?"

Bu modul FAQAT O'QIYDI. Yozishni trigger bajaradi
(`schema_patch_erp_16.sql`) va sabab shunda: ilova qatlamidagi jurnal
o'zi yozgan o'zgarishlarni yozadi — ya'ni u "men hech narsa
o'zgartirmadim" degan gapning O'ZI aytgan dalili. Trigger esa `psql`
dan kelgan qo'lda yozilgan `UPDATE` ni ham ushlaydi.

ENG MUHIM SAVOL: **chiqarilgan fakturaga tegilganmi?**

Kodda "faqat qoralama tahrirlanadi" degan qoida bor (`invoice.py`
`_editable`), lekin u faqat ILOVA orqali o'tgan o'zgarishlarni to'sadi.
Jurnaldagi `doc_status` ustuni esa o'zgarish PAYTIDAGI holatni saqlaydi,
ya'ni "issued bo'lgandan keyin nima o'zgardi" degan savolga
to'g'ridan-to'g'ri javob beradi — kimga ishonishdan qat'i nazar.

`actor IS NULL` — "ERP interfeysidan tashqarida o'zgartirilgan". Bu
holat YASHIRILMAYDI va alohida sanaladi: aynan shunday qatorlar eng
qiziq.

Kim ko'radi: `manager`. Jurnalda pul hujjatlarining ichki tarixi bor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError

#: Hujjat turlari — kod va bazadagi qiymatlar bir xil ro'yxat.
DOC_TYPES = [("invoice", "Hisob-faktura"), ("act", "Dalolatnoma")]
DOC_LABEL = dict(DOC_TYPES)

#: Yozuv turlari.
ENTITY_LABEL = {"invoice": "Faktura", "act": "Dalolatnoma",
                "line": "Qator", "payment": "To'lov"}
ACTION_LABEL = {"create": "yaratildi", "update": "o'zgartirildi",
                "delete": "o'chirildi"}

#: Chiqarilgandan keyin o'zgarish SHUBHALI bo'lgan holatlar. Qoralama
#: (`draft`) tabiiy ravishda o'zgaradi — u hali hujjat emas.
FROZEN_STATUSES = ("issued", "partial", "paid", "signed")

#: HAYOT SIKLI maydonlari — chiqarilgan hujjatda ham NORMAL o'zgaradi.
#:
#: `issued -> paid`, `issued -> signed` — hujjatning o'z yo'li, uni
#: buzilish deb belgilash YOLG'ON OGOHLANTIRISH bo'lardi. Demo
#: ma'lumotda aynan shu chiqdi: 7 ta "shubhali" o'zgarishning hammasi
#: oddiy status o'tishi edi. Bunday bayroq bir hafta ichida e'tibordan
#: qoladi va shundan keyin HAQIQIY buzilishni ham hech kim ko'rmaydi.
#:
#: Yozuvlar jurnalda QOLADI — faqat "shubhali" belgisi qo'yilmaydi.
LIFECYCLE_FIELDS = ("status", "status_changed_at", "signed_at",
                    "issued_at", "updated_at")

SCHEMA_SQL = ("SELECT 1 AS x FROM information_schema.tables "
              "WHERE table_schema = 'erp' AND table_name = 'doc_audit'")

LIST_SQL = """
SELECT a.id, a.doc_type, a.doc_id, a.entity, a.entity_id, a.action,
       a.field, a.old_value, a.new_value, a.doc_status, a.actor,
       a.created_at
FROM erp.doc_audit a
WHERE (%(doc_type)s::text IS NULL OR a.doc_type = %(doc_type)s)
  AND (%(doc_id)s::bigint IS NULL OR a.doc_id = %(doc_id)s)
  AND (%(only_frozen)s = false OR a.doc_status = ANY(%(frozen)s))
  AND (%(only_outside)s = false OR a.actor IS NULL)
  AND a.created_at > now() - (%(days)s || ' days')::interval
ORDER BY a.created_at DESC, a.id DESC
LIMIT %(limit)s
"""

# "Nechta shubhali o'zgarish bor" — ro'yxatni ochmasdan javob.
SUMMARY_SQL = """
SELECT count(*)                                        AS n,
       count(*) FILTER (WHERE actor IS NULL)           AS outside_n,
       count(*) FILTER (WHERE doc_status = ANY(%(frozen)s)
                        AND action <> 'create'
                        AND (field IS NULL
                             OR field <> ALL(%(lifecycle)s)))
                                                       AS after_issue_n,
       max(created_at)                                 AS last_at
FROM erp.doc_audit
WHERE created_at > now() - (%(days)s || ' days')::interval
"""


def schema_ready() -> bool:
    return bool(db.query_one(SCHEMA_SQL))


def _need_schema() -> None:
    if not schema_ready():
        raise ErpError("O'zgarishlar jurnali yo'q: schema_patch_erp_16.sql "
                       "bazaga qo'llanmagan.", 503)


def _row(r: Dict[str, Any]) -> Dict[str, Any]:
    # "Chiqarilgandan keyin o'zgardi" degan belgi UCH shartning
    # hammasini talab qiladi:
    #   1. hujjat muzlatilgan holatda edi;
    #   2. bu yangi qator/to'lov QO'SHISH emas (ular normal);
    #   3. o'zgargan ustun hayot sikliga tegishli emas.
    frozen = (r["doc_status"] in FROZEN_STATUSES
              and r["action"] != "create"
              and r["field"] not in LIFECYCLE_FIELDS)
    return {
        "id": r["id"],
        "doc_type": r["doc_type"], "doc_label": DOC_LABEL.get(r["doc_type"]),
        "doc_id": r["doc_id"],
        "entity": r["entity"], "entity_label": ENTITY_LABEL.get(r["entity"]),
        "entity_id": r["entity_id"],
        "action": r["action"], "action_label": ACTION_LABEL.get(r["action"]),
        "field": r["field"],
        "old_value": r["old_value"], "new_value": r["new_value"],
        "doc_status": r["doc_status"],
        # HUJJAT MUZLATILGANDAN KEYIN o'zgargan bo'lsa — belgilanadi.
        "after_issue": frozen,
        "actor": r["actor"],
        # `actor` yo'qligi — ma'lumot, kamchilik emas.
        "outside_erp": r["actor"] is None,
        "created_at": (r["created_at"].isoformat() if r["created_at"] else None),
    }


def for_document(doc_type: str, doc_id: int,
                 limit: int = 500) -> List[Dict[str, Any]]:
    """Bitta hujjatning butun tarixi."""
    _need_schema()
    if doc_type not in DOC_LABEL:
        raise ErpError("Noma'lum hujjat turi.")
    return [_row(r) for r in db.query(LIST_SQL, {
        "doc_type": doc_type, "doc_id": doc_id, "only_frozen": False,
        "only_outside": False, "days": 36500, "frozen": list(FROZEN_STATUSES),
        "limit": max(1, min(limit, 2000))})]


def recent(days: int = 30, limit: int = 200,
           doc_type: Optional[str] = None,
           only_frozen: bool = False,
           only_outside: bool = False) -> Dict[str, Any]:
    """Umumiy ko'rinish + yig'ma javob.

    `only_frozen` — faqat MUZLATILGAN hujjatdagi o'zgarishlar;
    `only_outside` — faqat ERP dan tashqarida qilinganlari."""
    _need_schema()
    if doc_type is not None and doc_type not in DOC_LABEL:
        raise ErpError("Noma'lum hujjat turi.")
    days = max(1, min(days, 3650))
    frozen = list(FROZEN_STATUSES)
    items = [_row(r) for r in db.query(LIST_SQL, {
        "doc_type": doc_type, "doc_id": None, "only_frozen": bool(only_frozen),
        "only_outside": bool(only_outside), "days": days, "frozen": frozen,
        "limit": max(1, min(limit, 2000))})]
    s = db.query_one(SUMMARY_SQL, {"days": days, "frozen": frozen,
                                   "lifecycle": list(LIFECYCLE_FIELDS)}) or {}
    return {
        "items": items,
        "days": days,
        "summary": {
            "n": s.get("n") or 0,
            # ERP dan tashqarida qilingan o'zgarishlar.
            "outside_erp": s.get("outside_n") or 0,
            # Muzlatilgan hujjatdagi o'zgarishlar — eng shubhalisi.
            "after_issue": s.get("after_issue_n") or 0,
            "last_at": (s["last_at"].isoformat() if s.get("last_at") else None),
        },
        # "Hammasi joyida" degan javob ham AYTILADI: bo'sh ro'yxat
        # "tekshirilmadi" degani emas.
        "clean": not ((s.get("outside_n") or 0) or (s.get("after_issue_n") or 0)),
    }
