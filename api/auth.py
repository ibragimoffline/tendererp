"""ERP kimlik qatlami — HODIM hisoblari, sessiyalar va rollar.

DOMEN MODELI (buni tushunmasdan bu fayl mantiqsiz ko'rinadi):

    Tender-AI  — KOMPANIYA hisobi bilan kiriladi (tender agregatori,
                 kompaniyaga qarashli tashqi xizmat).
    Tender ERP — kompaniyaning O'Z ERP tizimi. HODIMLAR shu yerda ishlaydi:
                 kartalar, vazifalar, shartnomalar — hammasi ularniki.

Ya'ni ODAM — ERP ning tushunchasi. Shuning uchun hisoblar shu yerda
(`erp.app_user`) va ERP tekshirish uchun tarmoqqa CHIQMAYDI.

    (Auth-1 da buning teskarisi qilingan edi: hisoblar tender-ai'da,
     ERP esa har so'rovda HTTP bilan tekshirardi. Model bo'yicha noto'g'ri
     va sekin edi; `schema_patch_erp_6.sql` uni ko'chirdi.)

QARORLAR:
  - PAROL XESHI — PBKDF2-HMAC-SHA256, `hashlib` (stdlib). `bcrypt`/`passlib`
    qo'shilmaydi: C-kengaytma va Windows'da o'rnatish muammosi evaziga bu
    hajmda foyda yo'q. Algoritm va iteratsiya soni USTUNDA saqlanadi,
    shuning uchun keyin kuchliroqqa o'tish migratsiyasiz.
  - TOKEN bazada sha256 XESHI ko'rinishida. Xom token faqat brauzerda.
  - "Login yoki parol noto'g'ri" — BITTA matn: qaysi biri xato ekanini
    aytish mavjud loginlarni topishga yo'l ochadi.
  - Hisob O'CHIRILMAYDI (`active=false`): hodim ismi `created_by` /
    `changed_by` da tarixda qolgan.
  - HODIM BILAN BOG'LANISH (`broker_id`) — ERP ning asosiy foydasi:
    kirgan odamning kartalari va vazifalari darhol ma'lum.
  - PAROL ALMASHTIRISH (auth-6) — O'ZINIKINI almashtirayotgan odam
    ESKI parolni ham kiritadi, va almashtirishdan keyin uning BOSHQA
    sessiyalari o'chadi. Aks holda "parolimni o'zgartirdim" degan
    harakat o'g'irlangan tokenni bekor qilmasdi.
  - PAROL TANLASHDAN HIMOYA — urinishlar JURNALI (`erp.login_attempt`),
    hisoblagich ustuni emas. Bloklash jurnaldan hisoblanadi va HISOBGA
    emas, (login + IP) juftligiga tegadi: aks holda direktorning
    loginini bilgan har kim uni ishdan chiqarib qo'ya olardi.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, List, Optional

from api import db

# Rollar — bazadagi CHECK bilan BIR XIL ro'yxat (schema_patch_erp_17.sql).
# `_tests/erp11_test.py` ikkalasini solishtiradi: ro'yxatlar ajralib
# ketsa sinov yiqiladi, ilova esa 500 bermaydi.
#
# NEGA TO'RTTA (avval uchta edi): `manager` ikki xil odamni — direktorni
# va tender bo'limi boshlig'ini — bitta nom ostiga qo'yardi, ya'ni
# KUNDALIK ishning (taqsimlash, yo'naltirish, muddat kuzatish) egasi
# yo'q edi. Batafsil sabab: schema_patch_erp_17.sql sarlavhasida.
ROLES = [
    ("admin",   "Administrator"),
    ("rahbar",  "Rahbar"),
    ("menejer", "Menejer"),
    ("broker",  "Broker"),
]
ROLE_LABEL = dict(ROLES)

#: Ierarxiya: yuqoridagi quyidagining hamma huquqini oladi.
#
#: `admin` ENG YUQORIDA — HOZIRCHA. `erp_rollar.md` §3.6 ga ko'ra admin
#: biznes ma'lumotni ko'rishi kerak, lekin O'ZGARTIRMASLIGI kerak (tizim
#: sozlovchi va pul hujjatini o'zgartiruvchi bitta odam bo'lmasin). Buni
#: ierarxiya bilan ifodalab bo'lmaydi — u faqat "kim kimdan yuqori"
#: deydi, "kim nimaga tegmaydi" demaydi. Shuning uchun cheklov keyingi
#: bosqichda `api/erp/perm.py` (huquqlar MATRITSASI) bilan keladi va
#: o'shanda bu ro'yxat faqat "ierarxiya" ma'nosida qoladi.
ROLE_RANK = {"broker": 1, "menejer": 2, "rahbar": 3, "admin": 4}

ITERATIONS = 240_000
SESSION_DAYS = int(os.environ.get("AUTH_SESSION_DAYS", "14"))

# --- PAROL TANLASHDAN HIMOYA ------------------------------------------------
# Raqamlar ODAM uchun tanlangan, mashina uchun emas: ishga kelib parolini
# ikki-uch marta noto'g'ri yozgan hodim to'silib qolmasligi kerak, lug'at
# bo'yicha urinayotgan dastur esa deyarli darhol to'xtashi kerak.
#
#: Qancha vaqt ichidagi xatolar sanaladi.
ATTEMPT_WINDOW_MIN = int(os.environ.get("AUTH_ATTEMPT_WINDOW_MIN", "15"))
#: Shu oynada bitta (login + IP) uchun ruxsat etilgan xato.
MAX_PER_USER = int(os.environ.get("AUTH_MAX_ATTEMPTS", "5"))
#: Shu oynada bitta IP uchun — HAMMA loginlar bo'yicha. Bu login nomlarini
#: aylantirib chiqib cheklovni chetlab o'tishga qarshi.
MAX_PER_IP = int(os.environ.get("AUTH_MAX_ATTEMPTS_IP", "25"))
#: Jurnal shuncha kundan keyin tozalanadi. Bu — sessiyalar bilan bir xil
#: qoida: kerakmas ma'lumot saqlanmaydi.
ATTEMPT_KEEP_DAYS = int(os.environ.get("AUTH_ATTEMPT_KEEP_DAYS", "90"))

# --- PAROL TALABI (auth-6) --------------------------------------------------
# UZUNLIK talab qilinadi, "katta harf + raqam + belgi" EMAS.
#
# Murakkablik qoidalari amalda teskari natija beradi: odam `Parol123!`
# yozadi va uni monitorga yopishtiradi. Uzun, lekin sodda ibora
# (`qishloqdagi katta olma`) buni ancha ortda qoldiradi va yodda
# qoladi. Bu — NIST 800-63B tavsiyasi.
#
# Ikkita qo'shimcha shart bor va ikkalasi ham amaliy: parol LOGINNING
# o'zini o'z ichiga olmasin va eng ko'p uchraydigan parollar ro'yxatida
# bo'lmasin.
PASSWORD_MIN = int(os.environ.get("AUTH_PASSWORD_MIN", "10"))
#: Yuqori chegara — PBKDF2 ni ataylab uzun matn bilan yuklamasin.
PASSWORD_MAX = 200

#: Eng ko'p uchraydigan parollar. Ro'yxat qisqa ATAYLAB: uzun ro'yxat
#: xavfsizlikni sezilarli oshirmaydi, lekin faylni to'ldiradi. Uzunlik
#: talabi (10) allaqachon ko'pchiligini chetlab o'tadi — bu yerda faqat
#: o'sha talabdan o'tib ketadiganlari qoldi.
WEAK_PASSWORDS = {
    "1234567890", "0123456789", "qwertyuiop", "parol12345", "password1",
    "password123", "administrator", "qwerty12345", "iloveyou11",
    "1qaz2wsx3edc", "passw0rd123", "welcome123",
}


def check_password(password: str, username: str = "") -> None:
    """Yangi parol talabga mos keladimi. Mos kelmasa `AuthError(400)`.

    Xato matni NIMA QILISH kerakligini aytadi ("kamida N belgi"), aks
    holda odam taxmin qilib urinaverardi."""
    p = password or ""
    if len(p) < PASSWORD_MIN:
        raise AuthError(f"Parol kamida {PASSWORD_MIN} belgi bo'lsin. "
                        f"Uzun sodda ibora eng yaxshi tanlov.", 400)
    if len(p) > PASSWORD_MAX:
        raise AuthError(f"Parol {PASSWORD_MAX} belgidan uzun bo'lmasin.", 400)
    if p.lower() in WEAK_PASSWORDS:
        raise AuthError("Bu parol juda ko'p ishlatiladi — boshqasini "
                        "tanlang.", 400)
    u = (username or "").strip().lower()
    if u and u in p.lower():
        raise AuthError("Parol login nomini o'z ichiga olmasin.", 400)


class AuthError(RuntimeError):
    """Kirish/huquq xatosi -> main.py da 400/401/403/404/409/503."""

    def __init__(self, msg: str, code: int = 401):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------------------
# Parol
# ---------------------------------------------------------------------------
def hash_password(password: str, *, iterations: int = ITERATIONS,
                  salt: Optional[bytes] = None) -> str:
    if not password or len(password) < 6:
        raise AuthError("Parol kamida 6 belgidan iborat bo'lishi kerak.", 400)
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Doimiy vaqtli solishtirish — vaqt bo'yicha sizib chiqish bo'lmasin."""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"),
                             bytes.fromhex(salt_hex), int(iters))
    return hmac.compare_digest(dk.hex(), hash_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sxema tayyorligi
# ---------------------------------------------------------------------------
_READY = False

SCHEMA_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'app_user'
"""


def schema_ready() -> bool:
    global _READY
    if _READY:
        return True
    _READY = bool(db.query_one(SCHEMA_CHECK_SQL))
    return _READY


def _need_schema() -> None:
    if not schema_ready():
        raise AuthError("Kimlik jadvallari yo'q: schema_patch_erp_6.sql "
                        "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
# Hodim nomi ham qaytadi: interfeys "kim kirgan va u qaysi hodim" ni
# ko'rsatadi, ikkinchi so'rovsiz.
_USER_COLS = """
u.id, u.username, u.full_name, u.role, u.broker_id, u.email, u.active,
u.last_login_at, u.created_at, b.full_name AS broker_name
"""
_USER_FROM = """
FROM erp.app_user u
LEFT JOIN erp.broker b ON b.id = u.broker_id
"""

USER_BY_NAME_SQL = (f"SELECT {_USER_COLS}, u.password_hash {_USER_FROM} "
                    "WHERE u.username = %(username)s")
USER_BY_ID_SQL = f"SELECT {_USER_COLS} {_USER_FROM} WHERE u.id = %(id)s"
#: Parol almashtirishda ESKI xesh kerak (joriy parolni solishtirish uchun).
#: Bu so'rov `shape()` ga BERILMAYDI — xesh javobga chiqmasligi kerak.
USER_HASH_BY_ID_SQL = (f"SELECT {_USER_COLS}, u.password_hash {_USER_FROM} "
                       "WHERE u.id = %(id)s")
USERS_SQL = f"SELECT {_USER_COLS} {_USER_FROM} ORDER BY u.active DESC, u.username"

USER_INSERT_SQL = """
INSERT INTO erp.app_user (username, full_name, password_hash, role, broker_id, email)
VALUES (%(username)s, %(full_name)s, %(password_hash)s, %(role)s, %(broker_id)s,
        %(email)s)
RETURNING id
"""

USER_UPDATE_SQL = """
UPDATE erp.app_user SET
    full_name=%(full_name)s, role=%(role)s, broker_id=%(broker_id)s,
    email=%(email)s, active=%(active)s, updated_at=now()
WHERE id = %(id)s
RETURNING id
"""

PASSWORD_UPDATE_SQL = ("UPDATE erp.app_user SET password_hash=%(h)s, updated_at=now() "
                       "WHERE id=%(id)s RETURNING id")

BROKER_TAKEN_SQL = ("SELECT id, username FROM erp.app_user "
                    "WHERE broker_id = %(broker_id)s "
                    "AND (%(id)s::int IS NULL OR id <> %(id)s)")

# --- Kirish urinishlari ----------------------------------------------------
#: Jadval bormi. Patch qo'llanmagan bo'lsa himoya JIM o'chadi — eski baza
#: bilan tizim ishlashdan to'xtamasligi kerak (ammo bu holat `check_setup.py`
#: da ogohlantirish sifatida ko'rinadi).
ATTEMPT_SCHEMA_SQL = ("SELECT 1 AS x FROM information_schema.tables "
                      "WHERE table_schema = 'erp' "
                      "AND table_name = 'login_attempt'")

ATTEMPT_INSERT_SQL = """
INSERT INTO erp.login_attempt (username, ip, ok, user_agent)
VALUES (%(username)s, %(ip)s, %(ok)s, %(user_agent)s)
RETURNING id
"""

# OXIRGI MUVAFFAQIYATLI KIRISHDAN KEYINGI xatolar sanaladi. Ya'ni to'g'ri
# parol zanjirni UZADI: kecha uch marta adashgan hodim bugun toza varaqdan
# boshlaydi.
ATTEMPT_COUNT_SQL = """
SELECT count(*) AS n, max(created_at) AS last_at
FROM erp.login_attempt a
WHERE a.ok = false
  AND a.created_at > now() - (%(mins)s || ' minutes')::interval
  AND a.created_at > COALESCE((
        SELECT max(s.created_at) FROM erp.login_attempt s
        WHERE s.ok = true AND s.username = %(username)s
          AND (%(ip)s::inet IS NULL OR s.ip = %(ip)s::inet)
      ), '-infinity'::timestamptz)
  AND a.username = %(username)s
  AND (%(ip)s::inet IS NULL OR a.ip = %(ip)s::inet)
"""

# IP bo'yicha: login nomiga qaramaydi.
ATTEMPT_IP_COUNT_SQL = """
SELECT count(*) AS n, max(created_at) AS last_at
FROM erp.login_attempt
WHERE ok = false AND ip = %(ip)s::inet
  AND created_at > now() - (%(mins)s || ' minutes')::interval
"""

ATTEMPT_CLEAN_SQL = ("DELETE FROM erp.login_attempt "
                     "WHERE created_at < now() - (%(days)s || ' days')::interval "
                     "RETURNING id")

ATTEMPT_LIST_SQL = """
SELECT a.id, a.username, host(a.ip) AS ip, a.ok, a.user_agent, a.created_at,
       (u.id IS NOT NULL) AS known_user
FROM erp.login_attempt a
LEFT JOIN erp.app_user u ON u.username = a.username
WHERE (%(only_failed)s = false OR a.ok = false)
  AND a.created_at > now() - (%(hours)s || ' hours')::interval
ORDER BY a.created_at DESC
LIMIT %(limit)s
"""


def _attempts_ready() -> bool:
    """Jurnal jadvali bormi (patch 15 qo'llanganmi)."""
    return bool(db.query_one(ATTEMPT_SCHEMA_SQL))


def _clean_ip(ip: Optional[str]) -> Optional[str]:
    """Manzilni tozalash. Yaroqsiz qiymat `None` ga aylanadi — jurnal
    yozuvi shu sabab BUTUNLAY yo'qolmasligi kerak."""
    ip = (ip or "").strip()
    if not ip or ip in ("unknown", "testclient"):
        return None
    return ip[:45] or None


def record_attempt(username: str, ip: Optional[str], ok: bool, *,
                   user_agent: Optional[str] = None) -> None:
    """Urinishni jurnalga yozish. PAROL YOZILMAYDI."""
    if not _attempts_ready():
        return
    try:
        db.execute_returning(ATTEMPT_INSERT_SQL, {
            "username": (username or "")[:150], "ip": _clean_ip(ip),
            "ok": ok, "user_agent": (user_agent or "")[:300] or None})
    except Exception:
        # Jurnal yozilmasa ham kirish ishlashi kerak: audit muhim, lekin
        # u tizimni to'xtatib qo'yadigan darajada emas.
        pass


def guard_attempts(username: str, ip: Optional[str]) -> None:
    """Bloklangan bo'lsa `AuthError(429)` — parol TEKSHIRILMASDAN OLDIN.

    Ikki kesim tekshiriladi:
      1. (login + IP) — odatiy holat;
      2. IP — hamma loginlar bo'yicha, login nomini aylantirib chiqishga
         qarshi.

    IP NOMA'LUM bo'lsa (kutilmagan holat) cheklov faqat login bo'yicha
    qoladi. Bu nazariy jihatdan begonaga hodimni 15 daqiqaga to'sib
    qo'yish imkonini beradi, lekin himoyasiz qoldirishdan afzal:
    to'siq VAQTINCHA, hisob esa tegilmagan holda qoladi.

    Hisobning o'zi bloklanmaydi (sababi modul izohida)."""
    if not _attempts_ready():
        return
    uname = (username or "").strip().lower()
    addr = _clean_ip(ip)
    p = {"username": uname, "ip": addr, "mins": ATTEMPT_WINDOW_MIN}

    r = db.query_one(ATTEMPT_COUNT_SQL, p) or {}
    if (r.get("n") or 0) >= MAX_PER_USER:
        raise _blocked(r["last_at"])

    if addr:
        r2 = db.query_one(ATTEMPT_IP_COUNT_SQL,
                          {"ip": addr, "mins": ATTEMPT_WINDOW_MIN}) or {}
        if (r2.get("n") or 0) >= MAX_PER_IP:
            raise _blocked(r2["last_at"])


def _blocked(last_at) -> "AuthError":
    """429 va necha soniyadan keyin urinish mumkinligi.

    Qolgan vaqt AYTILADI: odam "buzildimi?" deb o'ylab qolmasin. Bu
    hujumchiga foyda bermaydi — u baribir kutishi kerak."""
    wait = ATTEMPT_WINDOW_MIN * 60
    if last_at is not None:
        now = _dt.datetime.now(_dt.timezone.utc)
        passed = (now - last_at).total_seconds()
        wait = max(1, int(ATTEMPT_WINDOW_MIN * 60 - passed))
    mins = max(1, round(wait / 60))
    e = AuthError(f"Juda ko'p urinish. {mins} daqiqadan keyin qayta "
                  f"urinib ko'ring.", 429)
    e.retry_after = wait
    return e


def attempts(hours: int = 24, limit: int = 100,
             only_failed: bool = True) -> List[Dict[str, Any]]:
    """Admin uchun: kim, qayerdan va qachon kirishga urindi.

    `known_user` — bunday login BOR yoki YO'Q. Yo'q loginlar bilan
    urinish hujumning eng ko'p uchraydigan izi."""
    if not _attempts_ready():
        raise AuthError("Urinishlar jurnali yo'q: schema_patch_erp_15.sql "
                        "bazaga qo'llanmagan.", 503)
    return [{**r, "created_at": (r["created_at"].isoformat()
                                 if r["created_at"] else None)}
            for r in db.query(ATTEMPT_LIST_SQL, {
                "hours": max(1, hours), "limit": max(1, min(limit, 1000)),
                "only_failed": bool(only_failed)})]


SESSION_INSERT_SQL = """
INSERT INTO erp.app_session
    (user_id, token_hash, expires_at, user_agent, csrf_token)
VALUES (%(user_id)s, %(token_hash)s, %(expires_at)s, %(user_agent)s,
        %(csrf_token)s)
RETURNING id
"""

SESSION_GET_SQL = f"""
SELECT s.id AS session_id, s.expires_at, s.csrf_token, {_USER_COLS}
FROM erp.app_session s
JOIN erp.app_user u ON u.id = s.user_id
LEFT JOIN erp.broker b ON b.id = u.broker_id
WHERE s.token_hash = %(token_hash)s
"""

SESSION_TOUCH_SQL = ("UPDATE erp.app_session SET last_seen_at = now() "
                     "WHERE id = %(id)s RETURNING id")
SESSION_DELETE_SQL = ("DELETE FROM erp.app_session WHERE token_hash = %(token_hash)s "
                      "RETURNING id")
SESSION_CLEAN_SQL = "DELETE FROM erp.app_session WHERE expires_at < now() RETURNING id"

# Parol almashgach BOSHQA sessiyalar o'chadi (auth-6). `keep` — hozirgi
# sessiya: parolni almashtirgan odamning o'zi tizimdan chiqib qolmasin.
_OTHER_SESSIONS = ("FROM erp.app_session WHERE user_id = %(user_id)s "
                   "AND (%(keep)s::text IS NULL OR token_hash <> %(keep)s)")
SESSION_OTHERS_COUNT_SQL = f"SELECT count(*) AS n {_OTHER_SESSIONS}"
SESSION_KILL_OTHERS_SQL = f"DELETE {_OTHER_SESSIONS} RETURNING id"
LOGIN_STAMP_SQL = ("UPDATE erp.app_user SET last_login_at = now() WHERE id = %(id)s "
                   "RETURNING id")


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def shape(r: Dict[str, Any]) -> Dict[str, Any]:
    """Parol xeshi JAVOBGA HECH QACHON tushmaydi.

    CSRF tokeni esa QASDDAN qo'shiladi (bo'lsa): u sir emas — sahifa uni
    `HttpOnly` bo'lmagan cookie'dan ham o'qiy oladi. Javobda ham berilishi
    sahifa yangilanganda uni qayta login'siz tiklash imkonini beradi."""
    out = {
        "id": r["id"], "username": r["username"], "full_name": r["full_name"],
        "role": r["role"], "role_label": ROLE_LABEL.get(r["role"]),
        "broker_id": r["broker_id"], "broker_name": r.get("broker_name"),
        "email": r["email"], "active": r["active"],
        "last_login_at": (r["last_login_at"].isoformat()
                          if r.get("last_login_at") else None),
    }
    if r.get("csrf_token"):
        out["csrf"] = r["csrf_token"]
    return out


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def login(username: str, password: str, *,
          user_agent: Optional[str] = None,
          ip: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    uname = (username or "").strip().lower()

    # Bloklash PAROLNI TEKSHIRISHDAN OLDIN: to'silgan urinish qimmat
    # xeshlashni ham ishga tushirmasligi kerak, aks holda cheklovning
    # o'zi yuk keltirish vositasiga aylanardi.
    guard_attempts(uname, ip)

    row = db.query_one(USER_BY_NAME_SQL, {"username": uname})

    # Foydalanuvchi topilmasa ham parolni TEKSHIRAMIZ (soxta xesh bilan):
    # aks holda javob vaqti "bunday login bormi?" degan savolga javob berardi.
    stored = row["password_hash"] if row else hash_password("x" * 12)
    ok = verify_password(password, stored)
    if not row or not ok or not row["active"]:
        record_attempt(uname, ip, False, user_agent=user_agent)
        raise AuthError("Login yoki parol noto'g'ri.", 401)

    # Muvaffaqiyatli urinish ham yoziladi: u xatolar zanjirini UZADI va
    # admin uchun "kim qayerdan kirdi" tarixini beradi.
    record_attempt(uname, ip, True, user_agent=user_agent)
    db.execute_returning(SESSION_CLEAN_SQL)      # muddati o'tganlarni tozalash
    if _attempts_ready():
        db.execute_returning(ATTEMPT_CLEAN_SQL, {"days": ATTEMPT_KEEP_DAYS})
    token = secrets.token_urlsafe(32)
    # CSRF tokeni SESSIYA tokenidan ALOHIDA va boshqa maqsadda:
    #   sessiya tokeni — "kimsan" (HttpOnly cookie, sahifa ko'rmaydi);
    #   CSRF tokeni   — "so'rovni bizning sahifamiz yubordimi" (ochiq).
    # Ikkalasi bitta qiymat bo'lsa, ochiq nusxasi o'g'irlansa kirish
    # huquqi ham o'g'irlanardi.
    csrf = secrets.token_urlsafe(24)
    expires = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=SESSION_DAYS)
    db.execute_returning(SESSION_INSERT_SQL, {
        "user_id": row["id"], "token_hash": _token_hash(token),
        "expires_at": expires, "user_agent": (user_agent or "")[:300] or None,
        "csrf_token": csrf})
    db.execute_returning(LOGIN_STAMP_SQL, {"id": row["id"]})
    return {"token": token, "csrf": csrf, "expires_at": expires.isoformat(),
            "user": {**shape(row), "csrf": csrf}}


def verify(token: str) -> Dict[str, Any]:
    """Token -> hodim. Bitta SQL so'rov: tarmoqqa chiqilmaydi.

    Javobda `csrf` ham bo'ladi (sessiyanikidan) — chaqiruvchi uni
    o'zgartiruvchi so'rovlarda sarlavha bilan solishtiradi."""
    # Token yo'qligi bazaga BOG'LIQ EMAS: 401 darhol qaytadi. Aks holda
    # javob baza holatiga qarab 401 yoki 503 bo'lardi.
    if not token:
        raise AuthError("Token yo'q.", 401)
    _need_schema()
    r = db.query_one(SESSION_GET_SQL, {"token_hash": _token_hash(token)})
    if not r:
        raise AuthError("Sessiya topilmadi — qaytadan kiring.", 401)
    if r["expires_at"] <= _dt.datetime.now(_dt.timezone.utc):
        db.execute_returning(SESSION_DELETE_SQL, {"token_hash": _token_hash(token)})
        raise AuthError("Sessiya muddati tugadi — qaytadan kiring.", 401)
    if not r["active"]:
        raise AuthError("Hisob faol emas.", 403)
    db.execute_returning(SESSION_TOUCH_SQL, {"id": r["session_id"]})
    return shape(r)


def logout(token: str) -> bool:
    _need_schema()
    return bool(db.execute_returning(SESSION_DELETE_SQL,
                                     {"token_hash": _token_hash(token)}))


def require_role(user: Dict[str, Any], role: str) -> None:
    have = ROLE_RANK.get(user.get("role"), 0)
    need = ROLE_RANK.get(role, 99)
    if have < need:
        raise AuthError("Bu amal uchun huquq yetarli emas "
                        f"({ROLE_LABEL.get(role, role)} kerak).", 403)


def actor(user: Dict[str, Any]) -> str:
    """Yozuvlarda saqlanadigan ism (`created_by` / `changed_by`).

    MIJOZDAN OLINMAYDI — sessiyadan. Hodimga bog'langan bo'lsa o'sha
    hodimning ismi ustun: kartalarda va tarixda bir xil ism ko'rinsin."""
    return (user.get("broker_name") or user.get("full_name")
            or user.get("username") or "?")


# --- hisoblarni boshqarish (admin) ------------------------------------------
def users() -> List[Dict[str, Any]]:
    _need_schema()
    return [shape(r) for r in db.query(USERS_SQL)]


def _check_broker_free(broker_id: Optional[int], user_id: Optional[int] = None) -> None:
    """Bitta hodimga bitta hisob. Aks holda "mening ishlarim" ikki xil
    javob berardi va tarixda ikki xil ism paydo bo'lardi."""
    if not broker_id:
        return
    ex = db.query_one(BROKER_TAKEN_SQL, {"broker_id": broker_id, "id": user_id})
    if ex:
        raise AuthError(f"Bu hodimga allaqachon hisob bog'langan: {ex['username']}.",
                        409)


def create_user(username: str, full_name: str, password: str, *,
                role: str = "broker", broker_id: Optional[int] = None,
                email: Optional[str] = None) -> Dict[str, Any]:
    _need_schema()
    uname = (username or "").strip().lower()
    if not uname:
        raise AuthError("Login bo'sh.", 400)
    if role not in ROLE_LABEL:
        raise AuthError("Noma'lum rol.", 400)
    if db.query_one(USER_BY_NAME_SQL, {"username": uname}):
        raise AuthError(f"'{uname}' logini band.", 409)
    # Talab YARATISHDA ham amal qiladi: aks holda zaif parol tizimga
    # birinchi kundanoq kirib qolardi.
    check_password(password, uname)
    _check_broker_free(broker_id)
    row = db.execute_returning(USER_INSERT_SQL, {
        "username": uname, "full_name": (full_name or uname).strip(),
        "password_hash": hash_password(password), "role": role,
        "broker_id": broker_id, "email": email})
    return shape(db.query_one(USER_BY_ID_SQL, {"id": row["id"]}))


def update_user(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    _need_schema()
    cur = db.query_one(USER_BY_ID_SQL, {"id": user_id})
    if not cur:
        raise AuthError("Hisob topilmadi.", 404)
    role = data.get("role") or cur["role"]
    if role not in ROLE_LABEL:
        raise AuthError("Noma'lum rol.", 400)
    broker_id = data.get("broker_id")
    _check_broker_free(broker_id, user_id)
    db.execute_returning(USER_UPDATE_SQL, {
        "id": user_id, "full_name": (data.get("full_name") or cur["full_name"]).strip(),
        "role": role, "broker_id": broker_id, "email": data.get("email"),
        "active": bool(data.get("active", cur["active"]))})
    return shape(db.query_one(USER_BY_ID_SQL, {"id": user_id}))


def set_password(user_id: int, password: str, *,
                 current: Optional[str] = None,
                 keep_token: Optional[str] = None) -> Dict[str, Any]:
    """Parolni almashtirish.

    `current` — ESKI parol. O'ZINIKINI almashtirayotgan odam uni
    kiritishi SHART: ochiq qolgan kompyuter yoki o'g'irlangan sessiya
    bilan begona odam parolni o'zgartirib, hisobni butunlay egallab
    olmasin. Admin BOSHQANING parolini tiklayotganda esa eski parol
    so'ralmaydi — u odatda aynan "parolimni unutdim" holati.

    `keep_token` — chaqiruvchining hozirgi tokeni. Uning sessiyasi
    qoladi, hisobning QOLGAN sessiyalari esa o'chadi: aks holda
    "parolimni o'zgartirdim" degan harakat o'g'irlangan tokenni bekor
    qilmasdi va butun amal ma'nosiz bo'lardi.

    Admin tiklaganda `keep_token` berilmaydi — o'sha hisobning HAMMA
    sessiyalari o'chadi. Bu ham to'g'ri: admin parolni tiklayotgan
    bo'lsa, demak hisobga ishonch yo'q."""
    _need_schema()
    row = db.query_one(USER_HASH_BY_ID_SQL, {"id": user_id})
    if not row:
        raise AuthError("Hisob topilmadi.", 404)

    if current is not None and not verify_password(current, row["password_hash"]):
        # 400 (401 emas): kim ekani MA'LUM va sessiyasi joyida —
        # noto'g'ri bo'lgani faqat kiritilgan eski parol.
        raise AuthError("Joriy parol noto'g'ri.", 400)

    check_password(password, row["username"])
    # "Eskisidan farq qilsin" faqat O'ZI ALMASHTIRAYOTGANDA. Qoidaning
    # maqsadi — parolni yangilayapman deb o'sha parolni qayta yozib
    # qo'ymaslik. Admin (yoki CLI) ma'lum parolni QAYTA TIKLAYOTGAN
    # bo'lsa, bu boshqa amal va uni taqiqlash o'rnatishni buzardi.
    if current is not None and verify_password(password, row["password_hash"]):
        raise AuthError("Yangi parol eskisidan farq qilsin.", 400)

    db.execute_returning(PASSWORD_UPDATE_SQL,
                         {"id": user_id, "h": hash_password(password)})
    p = {"user_id": user_id,
         "keep": (_token_hash(keep_token) if keep_token else None)}
    # Avval SANAYMIZ: `execute_returning` bitta qator qaytaradi, ya'ni
    # o'chirilganlar sonini undan bilib bo'lmaydi.
    n = db.scalar(SESSION_OTHERS_COUNT_SQL, p) or 0
    db.execute_returning(SESSION_KILL_OTHERS_SQL, p)
    return {"ok": True, "closed_sessions": int(n)}
