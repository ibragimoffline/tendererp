"""
HUQUQLAR sinovi — matritsa (`api/erp/perm.py`, `erp_rollar.md` §3).

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp12_test.py

NIMA UCHUN: huquq — "yozib qo'ydim, ishlayapti shekilli" deb
qoldiriladigan narsa emas. Bu yerda ikki xil savol tekshiriladi:

  1. JADVALNING O'ZI to'g'ri terilganmi (har amalda har rol bor,
     darajalar lug'atdan tashqariga chiqmaydi);
  2. ENDPOINT haqiqatan ham shu jadvalga bo'ysunadimi — broker
     fakturani chiqara olmasligi SO'ROV yuborib tekshiriladi, kodni
     o'qib emas.

Uchinchisi ham bor: `main.py` da rol nomi QOLMAGANI. Aks holda vaqt
o'tib yana "bu yerda menejer, u yerda matritsa" degan holat qaytadi va
jadval haqiqatni ko'rsatmay qo'yadi.

Sinov BAZAGA YOZMAYDI: hamma tekshiruv 403 ga qaraydi, ruxsat
berilganda esa faqat "403 EMAS" tekshiriladi (404/400 — ma'lumot yo'qligi,
huquq emas). Shuning uchun tozalash ham kerak emas.
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
from api.erp import perm as P  # noqa: E402

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


def _user(rol):
    return {"id": 0, "username": f"zz_{rol}", "full_name": "ZZTEST",
            "role": rol, "role_label": A.ROLE_LABEL.get(rol),
            "broker_id": None, "email": None, "active": True,
            "last_login_at": None, "csrf": "zz"}


# ---------------------------------------------------------------------------
# 1. Jadvalning o'zi
# ---------------------------------------------------------------------------
def test_jadval():
    head("1. Matritsa to'g'ri terilganmi")

    rollar = [c for c, _ in A.ROLES]
    darajalar = {P.TOLIQ, P.OZ, P.KOR, None}

    kam = {a: [r for r in rollar if r not in row]
           for a, (_, row) in P.AMALLAR.items()}
    kam = {a: v for a, v in kam.items() if v}
    eq("har amalda HAR rol yozilgan", kam, {})

    yomon = {a: [v for v in row.values() if v not in darajalar]
             for a, (_, row) in P.AMALLAR.items()}
    yomon = {a: v for a, v in yomon.items() if v}
    eq("darajalar lug'atdan tashqariga chiqmaydi", yomon, {})

    nomsiz = [a for a, (nom, _) in P.AMALLAR.items() if not nom]
    eq("har amalning odam o'qiydigan nomi bor", nomsiz, [])

    # Noma'lum amal — DASTURCHI xatosi, jimgina "yo'q" emas.
    try:
        P.can(_user("admin"), "yolgon.amal")
        check(False, "noma'lum amal xato berishi kerak")
    except KeyError:
        check(True, "noma'lum amal -> KeyError")


# ---------------------------------------------------------------------------
# 2. can / require / require_write
# ---------------------------------------------------------------------------
def test_qoidalar():
    head("2. can() va require()")

    eq("broker: kartani ko'radi (o'ziniki)",
       P.can(_user("broker"), "karta.korish"), P.OZ)
    eq("broker: karta YARATOLMAYDI",
       P.can(_user("broker"), "karta.yaratish"), None)
    eq("broker: fakturani chiqarolmaydi",
       P.can(_user("broker"), "hujjat.chiqarish"), None)
    eq("broker: qoldiqni faqat ko'radi",
       P.can(_user("broker"), "ombor.korish"), P.KOR)
    eq("menejer: jurnalni faqat ko'radi",
       P.can(_user("menejer"), "hujjat.jurnal"), P.KOR)
    eq("menejer: kompaniya passportiga tegmaydi",
       P.can(_user("menejer"), "tizim.kompaniya"), None)
    eq("rahbar: fakturani chiqaradi",
       P.can(_user("rahbar"), "hujjat.chiqarish"), P.TOLIQ)
    eq("rahbar: hodim boshqaruvi hozircha adminda",
       P.can(_user("rahbar"), "tizim.hodim"), None)
    eq("sozlamalar ekrani — faqat admin",
       P.can(_user("rahbar"), "tizim.sozlama"), None)
    # Sozlamaga bog'liq qatorlar jadvalda ENG KENG holatda turadi;
    # kompaniya ularni sozlama bilan toraytiradi (erp14 sinovi).
    check(all(a in P.AMALLAR for a, _ in P.SOZLAMAGA_BOGLIQ),
          "sozlamaga bog'langan amallar jadvalda bor")

    # 403 matni: nima qilib bo'lmagani VA kim ekani aytiladi.
    try:
        P.require(_user("broker"), "hujjat.tolov")
        check(False, "broker to'lov qaydi qila olmasligi kerak")
    except A.AuthError as e:
        eq("ruxsatsiz amal -> 403", e.code, 403)
        check(P.label("hujjat.tolov") in str(e) and "Broker" in str(e),
              "xato matnida amal nomi ham, rol ham bor", str(e))

    # `KOR` — ruxsat, lekin YOZISH emas.
    check(P.require(_user("broker"), "ombor.korish") == P.KOR,
          "ko'rish ruxsati require() dan o'tadi")
    try:
        P.require_write(_user("broker"), "ombor.korish")
        check(False, "faqat ko'rish huquqi bilan yozib bo'lmasligi kerak")
    except A.AuthError as e:
        eq("require_write: ko'rish -> 403", e.code, 403)

    # ADMIN: sozlama o'chiq bo'lganda hammasi ochiq (bugungi holat),
    # yoqilganda esa jadvaldagi qiymat ishlaydi.
    #
    # Sozlama qiymati BAZADAN keladi (`api/erp/sozlama.py`), bu sinov
    # esa SOF MANTIQNI tekshiradi — shuning uchun sozlama qatlami
    # vaqtincha almashtiriladi. Bazadagi haqiqiy xatti-harakat va
    # endpoint darajasidagi ta'siri: `_tests/erp14_test.py`.
    eq("admin (sozlama o'chiq): to'liq",
       P.can(_user("admin"), "hujjat.chiqarish"), P.TOLIQ)
    asl = P.sozlama.yoq
    P.sozlama.yoq = lambda k: (True if k == "admin_faqat_koradi"
                               else P.sozlama.standart(k))
    try:
        eq("admin (faqat ko'radi): pul hujjatiga tegmaydi",
           P.can(_user("admin"), "hujjat.chiqarish"), None)
        eq("admin (faqat ko'radi): kartani ko'radi",
           P.can(_user("admin"), "karta.korish"), P.KOR)
        eq("admin (faqat ko'radi): tizim o'ziniki",
           P.can(_user("admin"), "tizim.hodim"), P.TOLIQ)
    finally:
        P.sozlama.yoq = asl

    # Noma'lum rol — hech narsa.
    eq("noma'lum rol -> huquq yo'q",
       P.can({"role": "shoh"}, "karta.korish"), None)

    kesim = P.for_user(_user("menejer"))
    eq("for_user butun jadvalni qaytaradi", len(kesim), len(P.AMALLAR))


# ---------------------------------------------------------------------------
# 3. Kodda rol nomi qolmagan
# ---------------------------------------------------------------------------
def test_manba():
    head("3. Endpointlarda rol nomi yo'q")

    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "api", "main.py"), encoding="utf-8").read()
    check("auth.require_role" not in src,
          "main.py da require_role chaqiruvi qolmagan")
    check('user["role"]' not in src and 'user.get("role")' not in src,
          "main.py da rol bilan solishtirish yo'q")
    for rol, _ in A.ROLES:
        # Rol nomi faqat izohda uchrashi mumkin; SHART sifatida emas.
        check(f'== "{rol}"' not in src and f"== '{rol}'" not in src,
              f"main.py da '{rol}' bilan solishtirish yo'q")


# ---------------------------------------------------------------------------
# 4. Endpointlar jadvalga bo'ysunadimi
# ---------------------------------------------------------------------------
#: (rol, metod, yo'l, tana, RUXSATmi)
#: `True`  — 403 BO'LMASLIGI kerak (404/400 bo'lishi mumkin: ma'lumot yo'q);
#: `False` — aynan 403.
HOLATLAR = [
    # broker — kundalik ishi bor, lekin pul va omborga tegmaydi
    ("broker", "GET", "/erp/opportunities", None, True),
    ("broker", "GET", "/erp/invoices", None, True),
    ("broker", "POST", "/erp/tenders/1/take", {"priority": "medium"}, False),
    ("broker", "POST", "/erp/clients", {"name": "ZZTEST-HUQUQ"}, False),
    ("broker", "POST", "/erp/stock/moves",
     {"product_id": 1, "kind": "in", "qty": 1}, False),
    ("broker", "PUT", "/erp/invoices/1/status", {"status": "issued"}, False),
    ("broker", "PUT", "/erp/own-company", {"name": "ZZ"}, False),
    ("broker", "GET", "/erp/analytics", None, False),
    ("broker", "GET", "/erp/profit", None, False),
    ("broker", "GET", "/erp/audit", None, False),
    ("broker", "GET", "/erp/users", None, False),
    # menejer — kundalik ishning egasi
    ("menejer", "POST", "/erp/tenders/1/take", {"priority": "medium"}, True),
    ("menejer", "POST", "/erp/stock/moves",
     {"product_id": 1, "kind": "in", "qty": 1}, True),
    ("menejer", "PUT", "/erp/invoices/1/status", {"status": "issued"}, True),
    ("menejer", "GET", "/erp/analytics", None, True),
    ("menejer", "GET", "/erp/audit", None, True),
    ("menejer", "PUT", "/erp/own-company", {"name": "ZZ"}, False),
    ("menejer", "GET", "/erp/users", None, False),
    # rahbar — hammasini ko'radi, rekvizitni tuzatadi, hisob ochmaydi
    ("rahbar", "GET", "/erp/profit", None, True),
    ("rahbar", "GET", "/erp/audit", None, True),
    ("rahbar", "GET", "/erp/users", None, False),
    # admin — bayroq o'chiq: hammasi ochiq
    ("admin", "GET", "/erp/users", None, True),
    ("admin", "GET", "/erp/profit", None, True),
]


def test_endpointlar():
    head("4. Endpointlar matritsaga bo'ysunadi")
    from fastapi.testclient import TestClient

    from api import main as _main
    from api.main import app

    with TestClient(app) as c:
        try:
            for rol, metod, yol, tana, ruxsat in HOLATLAR:
                app.dependency_overrides[_main.me] = (
                    lambda r=rol: _user(r))
                r = c.request(metod, yol, json=tana)
                nom = f"{rol}: {metod} {yol}"
                if ruxsat:
                    check(r.status_code != 403, f"{nom} -> 403 EMAS",
                          f"{r.status_code}: {str(r.json())[:70]}")
                else:
                    eq(f"{nom} -> 403", r.status_code, 403)

            # Huquqlar kesimi interfeysga uzatiladi (`/erp/auth/me`).
            app.dependency_overrides[_main.me] = lambda: _user("broker")
            me = c.get("/erp/auth/me").json()
            check("perms" in me, "javobda huquqlar kesimi bor")
            eq("kesim to'liq", len(me.get("perms") or {}), len(P.AMALLAR))
            eq("kesim brokerniki", me["perms"]["hujjat.chiqarish"], None)
            eq("kesim: o'z kartalari", me["perms"]["karta.korish"], P.OZ)
        finally:
            app.dependency_overrides.pop(_main.me, None)


if __name__ == "__main__":
    test_jadval()
    test_qoidalar()
    test_manba()
    try:
        test_endpointlar()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
