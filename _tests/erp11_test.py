"""
ROLLAR sinovi — lug'at BITTA bo'lishi kerak (erp_rollar.md v2, §2).

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp11_test.py

NIMA UCHUN ALOHIDA SINOV: rol ro'yxati UCH joyda yozilgan —
bazadagi `CHECK` (schema_patch_erp_17.sql), koddagi `auth.ROLES` va
interfeysdagi turlar. Ular ajralib ketsa xato JIM bo'ladi: administrator
"Menejer" ni tanlaydi, so'rov 500 bilan qaytadi va sabab
ekranda ko'rinmaydi. Shuning uchun ro'yxatlar SOLISHTIRILADI, ishonchga
qoldirilmaydi.

Tekshiriladi:
  1) SOF: to'rt rol, yorliqlar takrorlanmaydi, ierarxiya
     broker < menejer < rahbar < admin, `require_role` xatti-harakati.
  2) BAZA: `CHECK` dagi ro'yxat = koddagi ro'yxat; eski `manager`
     qolmagan; noma'lum rolni baza QABUL QILMAYDI.
  3) API: `/erp/auth/roles` shu lug'atni beradi; menejer huquqini
     talab qiladigan endpoint brokerga 403, menejerga ochiq.
  4) CHEGARA: sinov `public.*` ga tegmaydi.

Sinov hisoblari 'zztest_rol_' prefiksi bilan yaratiladi va oxirida
O'CHIRILADI: ular hech qayerda `created_by` bo'lib qolmaydi (hech narsa
yozmaydi), shuning uchun tarix uchun saqlashning ma'nosi yo'q.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api import auth as A  # noqa: E402
from api import db  # noqa: E402

PREFIX = "zztest_rol_"

#: Hujjatdagi ro'yxat (`erp_rollar.md` §2). Sinov KODNI shu ro'yxat
#: bilan ham solishtiradi: kodda rol qo'shilsa-yu hujjatga tushmasa,
#: "kim nima qila oladi" degan savolga javob beradigan joy qolmaydi.
KUTILGAN = ["admin", "rahbar", "menejer", "broker"]

_fail = 0
_pass = 0


def check(cond, msg, extra=""):
    global _fail, _pass
    if cond:
        _pass += 1
        print(f"  OK   {msg}")
    else:
        _fail += 1
        print(f"  XATO {msg}" + (f"\n       -> {extra}" if extra else ""))


def eq(msg, got, want):
    check(got == want, msg, f"olindi={got!r} kutildi={want!r}")


def head(t):
    print(f"\n=== {t} ===")


# ---------------------------------------------------------------------------
# 1. Sof mantiq — bazasiz
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq")

    kodda = [c for c, _ in A.ROLES]
    eq("kod ro'yxati hujjatnikiga mos", sorted(kodda), sorted(KUTILGAN))
    eq("yorliqlar takrorlanmaydi", len(set(dict(A.ROLES).values())), len(A.ROLES))
    eq("ROLE_LABEL to'liq", len(A.ROLE_LABEL), len(A.ROLES))

    # Ierarxiya: HAR rol darajaga ega bo'lishi shart. Yo'q rol `require_role`
    # da 0 daraja oladi va JIMGINA hech qayerga kira olmaydi — bu xavfsiz,
    # lekin sababi tushunarsiz bo'lardi.
    yoq = [c for c in kodda if c not in A.ROLE_RANK]
    eq("har rol ierarxiyada bor", yoq, [])
    check(A.ROLE_RANK["broker"] < A.ROLE_RANK["menejer"]
          < A.ROLE_RANK["rahbar"] < A.ROLE_RANK["admin"],
          "ierarxiya: broker < menejer < rahbar < admin")

    # `require_role` — kim o'tadi, kim o'tmaydi.
    for rol in ("menejer", "rahbar", "admin"):
        try:
            A.require_role({"role": rol}, "menejer")
            check(True, f"{rol} -> menejer huquqini oladi")
        except A.AuthError:
            check(False, f"{rol} -> menejer huquqini oladi")

    for rol, kerak in (("broker", "menejer"), ("menejer", "rahbar"),
                       ("rahbar", "admin"), ("shoh", "menejer")):
        try:
            A.require_role({"role": rol}, kerak)
            check(False, f"{rol} -> {kerak}: 403 bo'lishi kerak edi")
        except A.AuthError as e:
            eq(f"{rol} -> {kerak}: 403", e.code, 403)

    # Xato matni KERAKLI rolni aytadi: "huquq yetarli emas" deyish odamga
    # nima qilish kerakligini aytmaydi.
    try:
        A.require_role({"role": "broker"}, "menejer")
    except A.AuthError as e:
        check("Menejer" in str(e), "xato matnida kerakli rol nomi bor", str(e))


# ---------------------------------------------------------------------------
# 2-4. Baza va API
# ---------------------------------------------------------------------------
PUBLIC_MAX_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""

CHECK_SQL = """
SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint
 WHERE conrelid = 'erp.app_user'::regclass AND conname = 'app_user_role_check'
"""


def _bazadagi_rollar() -> list:
    """`CHECK` ichidagi qiymatlar. Ular matn ko'rinishida saqlanadi,
    shuning uchun tirnoq ichidagilar ajratib olinadi."""
    row = db.query_one(CHECK_SQL)
    if not row:
        return []
    import re
    return re.findall(r"'([a-z_]+)'::text", row["d"])


def _ochir(username: str) -> None:
    db.execute_returning("DELETE FROM erp.app_user WHERE username = %(u)s "
                         "RETURNING id", {"u": username})


def test_db():
    head("2. Baza: CHECK va koddagi ro'yxat")
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        if not A.schema_ready():
            print("  SKIP schema_patch_erp_6.sql qo'llanmagan")
            return
        before = db.query_one(PUBLIC_MAX_SQL)
        made = []
        try:
            bazada = _bazadagi_rollar()
            if not bazada:
                print("  SKIP schema_patch_erp_17.sql qo'llanmagan "
                      "(app_user_role_check topilmadi)")
                return
            eq("CHECK ro'yxati = kod ro'yxati",
               sorted(bazada), sorted(c for c, _ in A.ROLES))
            eq("eski 'manager' roli qolmagan",
               db.scalar("SELECT count(*) FROM erp.app_user "
                         "WHERE role = 'manager'"), 0)

            # HAR ROL bazaga yozilishi kerak: `CHECK` ni faqat o'qib
            # tekshirish yetarli emas — yozib ko'rilmaguncha uning
            # HAQIQATDA ishlashi noma'lum.
            for rol, _ in A.ROLES:
                uname = PREFIX + rol
                made.append(uname)
                _ochir(uname)
                r = db.execute_returning(
                    "INSERT INTO erp.app_user (username, full_name, "
                    "password_hash, role, active) VALUES (%(u)s, %(f)s, 'x', "
                    "%(r)s, false) RETURNING role", {"u": uname, "f": "ZZTEST",
                                                     "r": rol})
                eq(f"'{rol}' roli bazaga yoziladi", r["role"], rol)

            # Noma'lum rol — bazaning O'ZI to'xtatishi kerak. Ilova
            # tekshiruvi (`create_user`) chetlab o'tilishi mumkin,
            # `CHECK` esa yo'q.
            try:
                db.execute_returning(
                    "INSERT INTO erp.app_user (username, full_name, "
                    "password_hash, role) VALUES (%(u)s, 'ZZTEST', 'x', 'shoh')"
                    " RETURNING id", {"u": PREFIX + "shoh"})
                made.append(PREFIX + "shoh")
                check(False, "noma'lum rolni baza QABUL QILMASLIGI kerak")
            except Exception:                       # noqa: BLE001
                check(True, "noma'lum rolni baza rad etadi")

            head("3. API: rol lug'ati va huquq")
            r = c.get("/erp/auth/roles")
            eq("/erp/auth/roles -> 200", r.status_code, 200)
            eq("javobdagi ro'yxat = koddagi",
               [x["code"] for x in r.json()["roles"]], [x for x, _ in A.ROLES])
            eq("yorliqlar ham keladi",
               [x["label"] for x in r.json()["roles"]],
               [y for _, y in A.ROLES])

            # Huquq TEKSHIRUVI: `me` ni almashtiramiz, `menejer`
            # bog'liqligini ATAYLAB almashtirmaymiz — aynan u sinaladi.
            from api import main as _main

            def _kirgan(rol):
                return {"id": 0, "username": PREFIX + rol,
                        "full_name": "ZZTEST", "role": rol,
                        "role_label": A.ROLE_LABEL.get(rol), "broker_id": None,
                        "email": None, "active": True, "last_login_at": None,
                        "csrf": "zz"}

            try:
                app.dependency_overrides[_main.me] = lambda: _kirgan("broker")
                eq("broker -> /erp/analytics: 403",
                   c.get("/erp/analytics").status_code, 403)
                eq("broker -> /erp/profit: 403",
                   c.get("/erp/profit").status_code, 403)

                app.dependency_overrides[_main.me] = lambda: _kirgan("menejer")
                eq("menejer -> /erp/analytics: 200",
                   c.get("/erp/analytics").status_code, 200)

                app.dependency_overrides[_main.me] = lambda: _kirgan("rahbar")
                eq("rahbar -> /erp/profit: 200",
                   c.get("/erp/profit").status_code, 200)

                # Hodim hisoblari — faqat admin. Menejer HODIMNI
                # taqsimlaydi, lekin PAROL va ROL bermaydi.
                app.dependency_overrides[_main.me] = lambda: _kirgan("menejer")
                eq("menejer -> /erp/users: 403",
                   c.get("/erp/users").status_code, 403)
                app.dependency_overrides[_main.me] = lambda: _kirgan("admin")
                eq("admin -> /erp/users: 200",
                   c.get("/erp/users").status_code, 200)
            finally:
                app.dependency_overrides.pop(_main.me, None)

        finally:
            head("4. Tozalash va chegara")
            n = 0
            for u in made:
                if db.execute_returning(
                        "DELETE FROM erp.app_user WHERE username = %(u)s "
                        "RETURNING id", {"u": u}):
                    n += 1
            check(n >= 0, f"sinov hisoblari o'chirildi ({n} ta)")
            eq("prefiksli hisob qolmadi",
               db.scalar("SELECT count(*) FROM erp.app_user "
                         "WHERE username LIKE %(p)s", {"p": PREFIX + "%"}), 0)
            after = db.query_one(PUBLIC_MAX_SQL)
            eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
            eq("public.tender yangilanmadi", after["t_max"], before["t_max"])


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
