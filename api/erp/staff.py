"""
HODIMLAR — `erp.broker` va ularning hisoblari.

NEGA ALOHIDA MODUL: bu yerda IKKI tushuncha uchrashadi.

  - HODIM (`erp.broker`) — ish yuritish tushunchasi: kartaga mas'ul,
    vazifa bajaruvchisi, tarixdagi ism. Tizimga KIRMASLIGI ham mumkin
    (masalan omborchi yoki hujjatchi).
  - HISOB (`erp.app_user`) — kirish tushunchasi: login, parol, rol.

Ular bir-biriga majburiy emas: hodim hisobsiz bo'lishi mumkin, hisob esa
hodimga bog'lanmasligi mumkin (masalan `admin` — tizim administratori,
u tenderlar bilan ishlamaydi).

Shuning uchun boshqarish EKRANI bitta bo'lishi kerak: ikki ro'yxatni
alohida ko'rsatsak, "Karimovga hisob ochilganmi?" degan savolga javob
ikki joyni solishtirib topilardi.

Hisoblarning O'ZI bu modulda emas — u `api/auth.py` da (parol, sessiya).
Bu modul faqat BOG'LANISHNI ko'rsatadi va hodim yozuvini tahrirlaydi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import FINAL, ErpError, _need_schema

# Hodim + unga bog'langan hisob. LEFT JOIN: hisobsiz hodim ham chiqadi.
# `app_user_broker_uq` tufayli bitta hodimga bittadan ortiq hisob
# bo'lolmaydi, ya'ni JOIN qatorni ko'paytirmaydi.
STAFF_SQL = """
SELECT b.id, b.full_name, b.email, b.phone, b.active,
       u.id AS user_id, u.username, u.role, u.active AS user_active,
       u.last_login_at,
       (SELECT count(*) FROM erp.opportunity o WHERE o.broker_id = b.id) AS opp_count,
       (SELECT count(*) FROM erp.opportunity_task t
        WHERE t.assignee_broker_id = b.id AND t.done_at IS NULL) AS open_tasks
FROM erp.broker b
LEFT JOIN erp.app_user u ON u.broker_id = b.id
ORDER BY b.active DESC, b.full_name
"""

BROKER_BY_ID_SQL = ("SELECT id, full_name, email, phone, active FROM erp.broker "
                    "WHERE id = %(id)s")

BROKER_UPDATE_SQL = """
UPDATE erp.broker SET
    full_name = %(full_name)s, email = %(email)s, phone = %(phone)s,
    active = %(active)s
WHERE id = %(id)s
RETURNING id, full_name, email, phone, active
"""

# Faolsizlantirilayotgan hodimda ochiq ish qolmaganini tekshirish uchun.
# Yakuniy statuslar ro'yxati SQL ga YOZILMAYDI - `FINAL` dan parametr
# sifatida uzatiladi, aks holda status qo'shilganda ikki joy ajralib
# ketardi.
OPEN_WORK_SQL = """
SELECT (SELECT count(*) FROM erp.opportunity o
        WHERE o.broker_id = %(id)s AND o.status <> ALL(%(final)s)) AS opps,
       (SELECT count(*) FROM erp.opportunity_task t
        WHERE t.assignee_broker_id = %(id)s AND t.done_at IS NULL) AS tasks
"""


def _iso(v):
    return v.isoformat() if v is not None else None


def shape(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "full_name": r["full_name"], "email": r["email"],
        "phone": r["phone"], "active": r["active"],
        "opp_count": r["opp_count"], "open_tasks": r["open_tasks"],
        # Hisob bo'lmasa `null` — interfeys "hisob yo'q" deb ko'rsatadi.
        "user": ({"id": r["user_id"], "username": r["username"],
                  "role": r["role"], "active": r["user_active"],
                  "last_login_at": _iso(r["last_login_at"])}
                 if r["user_id"] else None),
    }


def staff() -> List[Dict[str, Any]]:
    _need_schema()
    return [shape(r) for r in db.query(STAFF_SQL)]


def update_broker(broker_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Hodim yozuvini tahrirlash.

    Hodim O'CHIRILMAYDI — `active=false`. Uning ismi kartalarda,
    vazifalarda va tarixda qolgan; o'chirish ularni "kimsiz" qoldirardi.
    """
    _need_schema()
    cur = db.query_one(BROKER_BY_ID_SQL, {"id": broker_id})
    if not cur:
        raise ErpError("Hodim topilmadi.", 404)
    full_name = (data.get("full_name") or cur["full_name"]).strip()
    if not full_name:
        raise ErpError("Ism bo'sh.")
    # `None` — "tegilmasin". `data.get(..., default)` YETMAYDI: kalit bor,
    # lekin qiymati None bo'lsa u `False` ga aylanib, hodimni jimgina
    # faolsizlantirardi.
    active = cur["active"] if data.get("active") is None else bool(data["active"])

    if cur["active"] and not active:
        # OCHIQ ISH bilan faolsizlantirish TO'XTATILADI: aks holda karta
        # va vazifalar ko'rinmas mas'ulga qolib ketardi. Avval ish boshqa
        # hodimga o'tkaziladi.
        w = db.query_one(OPEN_WORK_SQL, {"id": broker_id,
                                 "final": sorted(FINAL)})
        if w["opps"] or w["tasks"]:
            raise ErpError(
                f"Faolsizlantirib bo'lmaydi: {w['opps']} ta ochiq karta va "
                f"{w['tasks']} ta bajarilmagan vazifa bor. Avval ularni "
                f"boshqa hodimga o'tkazing.", 409)

    return db.execute_returning(BROKER_UPDATE_SQL, {
        "id": broker_id, "full_name": full_name,
        "email": data.get("email"), "phone": data.get("phone"),
        "active": active})


def broker_exists(broker_id: Optional[int]) -> bool:
    if not broker_id:
        return True
    return bool(db.query_one(BROKER_BY_ID_SQL, {"id": broker_id}))
