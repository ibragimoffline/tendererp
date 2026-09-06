"""
MUHIT QULFI sinovi — `api/muhit.py`.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/muhit_test.py

NIMA UCHUN: bu qulf ishlab chiqarish bazasini sinovlardan
qo'riqlaydi. Uning o'zi buzilsa, buni HECH NARSA ko'rsatmaydi —
qulf jimgina ochiq qoladi va birinchi marta kerak bo'lganda
ishlamaydi.

UCHTA BUZILISH SINFI:

  1) QULF OCHIQ QOLISHI. `ERP_MUHIT=prod` bo'lsa sinov ulanmasligi
     kerak. "production", "PROD " kabi yozilishlar ham tanilishi
     shart — aks holda bitta harf qulfni o'chirib qo'yardi.
  2) JIM O'TISH. Qulf ishga tushganda sinov "0 ta xato" deb
     chiqmasligi kerak. Shuning uchun `ProdQulfi` — `SystemExit`,
     `except Exception` uni USHLAMAYDI.
  3) NOTO'G'RI JOYDA ISHLASHI. Ilovaning o'zi (`uvicorn`,
     `check_setup.py`, `remind.py`) qulfga tushmasligi kerak: ular
     ishlab chiqarishda AYNAN ishlashi kerak.
  4) `.env` YOLG'ON GAPIRSA. Qo'riqlanayotgan xavf aynan `.env`
     ning almashib ketishi, ya'ni faqat unga qaraydigan qulf
     aldanadi. Bazadagi belgi bilan ZIDLIK ushlanishi shart.

BAZAGA TEGMAYDI: bu sof mantiq sinovi va bo'sh o'rnatmada ham
ishlaydi. Bazadagi belgi o'rniga uni O'QIYDIGAN funksiya
almashtiriladi — ulanish talab qilinmasin.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from api import muhit as M  # noqa: E402

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


class _Muhit:
    """`ERP_MUHIT` ni vaqtincha almashtiradi va QAYTARADI.

    Qaytarmasa, keyingi tekshiruv oldingisining sozlamasi bilan
    ishlardi va natija tartibga bog'liq bo'lib qolardi."""

    def __init__(self, qiymat):
        self.qiymat = qiymat

    def __enter__(self):
        self.eski = os.environ.get("ERP_MUHIT")
        if self.qiymat is None:
            os.environ.pop("ERP_MUHIT", None)
        else:
            os.environ["ERP_MUHIT"] = self.qiymat
        return self

    def __exit__(self, *a):
        if self.eski is None:
            os.environ.pop("ERP_MUHIT", None)
        else:
            os.environ["ERP_MUHIT"] = self.eski


class _Skript:
    """`sys.argv[0]` ni almashtiradi — "qaysi skript ishlayapti"."""

    def __init__(self, yol):
        self.yol = yol

    def __enter__(self):
        self.eski = sys.argv[0]
        sys.argv[0] = self.yol
        return self

    def __exit__(self, *a):
        sys.argv[0] = self.eski


# ---------------------------------------------------------------------------
def test_nom():
    head("1. Muhit nomi")
    for xom, kutilgan in (("prod", M.PROD), ("production", M.PROD),
                          ("PROD", M.PROD), ("  prod  ", M.PROD),
                          ("ishlab_chiqarish", M.PROD),
                          ("staging", M.STAGING), ("stage", M.STAGING),
                          ("dev", M.DEV), ("local", M.DEV)):
        with _Muhit(xom):
            eq(f"{xom!r} -> {kutilgan}", M.nomi(), kutilgan)
    # BEGONA QIYMAT "nom qo'yilmagan" bo'ladi, `prod` EMAS: taxmin
    # qilish ikki tomonga ham xato bo'lardi.
    for xom in ("", "prodakshn", "ishchi", "xyz"):
        with _Muhit(xom):
            eq(f"{xom!r} -> tanilmadi", M.nomi(), None)
            eq(f"{xom!r} -> prod emas", M.prodmi(), False)
    with _Muhit(None):
        eq("umuman qo'yilmagan -> None", M.nomi(), None)


def test_sinov_aniqlash():
    head("2. Sinov skriptini aniqlash")
    for yol, kutilgan in (
            (os.path.join(ROOT, "_tests", "erp7_test.py"), True),
            (os.path.join(ROOT, "_tests", "fixture.py"), True),
            (os.path.join(ROOT, "boshqa", "erp_test.py"), True),
            # ILOVA VA ASBOBLAR qulfga TUSHMAYDI: ular ishlab
            # chiqarishda aynan ishlashi kerak.
            (os.path.join(ROOT, "check_setup.py"), False),
            (os.path.join(ROOT, "olchov.py"), False),
            (os.path.join(ROOT, "demo_data.py"), False),
            (os.path.join(ROOT, ".venv", "Scripts", "uvicorn.exe"), False)):
        with _Skript(yol):
            eq(f"{os.path.basename(yol)} -> sinovmi={kutilgan}",
               M.sinovmi(), kutilgan)


def test_qulf():
    head("3. Qulf")
    sinov = os.path.join(ROOT, "_tests", "yangi_test.py")

    # ISHLAB CHIQARISH: RAD etiladi.
    with _Muhit("prod"), _Skript(sinov):
        try:
            M.qulf_tekshir()
            check(False, "prod muhitida sinov RAD etildi", "o'tkazib yubordi")
        except M.ProdQulfi as e:
            check(True, "prod muhitida sinov RAD etildi")
            check("staging" in str(e), "xabar nima qilish kerakligini aytadi")

    # `SystemExit` DAN meros — `except Exception` uni USHLAMAYDI.
    # Aks holda sinov qulfni yutib, "0 ta xato" deb chiqardi.
    check(issubclass(M.ProdQulfi, SystemExit),
          "ProdQulfi — SystemExit (sinov uni yutib yubormaydi)")
    check(not issubclass(M.ProdQulfi, Exception),
          "va u `except Exception` ga TUSHMAYDI")
    with _Muhit("prod"), _Skript(sinov):
        yutildi = False
        try:
            try:
                M.qulf_tekshir()
            except Exception:                       # noqa: BLE001
                yutildi = True
        except M.ProdQulfi:
            pass
        eq("qulf `except Exception` bilan yutilmadi", yutildi, False)

    # STAGING va DEV: o'tadi.
    for m in ("staging", "dev"):
        with _Muhit(m), _Skript(sinov):
            try:
                M.qulf_tekshir()
                check(True, f"{m} muhitida sinov o'tadi")
            except M.ProdQulfi:
                check(False, f"{m} muhitida sinov o'tadi", "rad etildi")

    # ILOVA ishlab chiqarishda ham ishlaydi.
    with _Muhit("prod"), _Skript(os.path.join(ROOT, "check_setup.py")):
        try:
            M.qulf_tekshir()
            check(True, "check_setup.py prod muhitida ISHLAYDI")
        except M.ProdQulfi:
            check(False, "check_setup.py prod muhitida ishlaydi", "rad etildi")

    # NOM QO'YILMAGAN: o'tadi, lekin ogohlantiradi.
    M._ogohlantirildi = False
    with _Muhit(None), _Skript(sinov):
        try:
            M.qulf_tekshir()
            check(True, "nom qo'yilmagan bo'lsa sinov to'xtamaydi")
        except M.ProdQulfi:
            check(False, "nom qo'yilmagan bo'lsa sinov to'xtamaydi",
                  "rad etildi")
        check(M._ogohlantirildi, "lekin ogohlantirish chiqadi")


class _Belgi:
    """`muhit.baza_muhiti()` ni vaqtincha almashtiradi.

    Bazaga ULANMAYMIZ: sinov bo'sh o'rnatmada ham ishlashi kerak
    va bu yerda tekshirilayotgan narsa — MANTIQ, so'rovning o'zi
    emas (uni `check_setup.py` haqiqiy bazada tekshiradi)."""

    def __init__(self, qiymat):
        self.qiymat = qiymat

    def __enter__(self):
        self.eski = M.baza_muhiti
        M.baza_muhiti = lambda: self.qiymat
        return self

    def __exit__(self, *a):
        M.baza_muhiti = self.eski


def test_moslik():
    head("5. `.env` va BAZA mosligi")

    # MOS — ishlaydi.
    with _Muhit("staging"), _Belgi(M.STAGING):
        eq("ikkalasi 'staging' -> ok", M.moslik()[0], "ok")

    # ZID — eng muhim holat: noto'g'ri `.env` bilan ishga tushirish.
    for e, b in (("prod", M.STAGING), ("staging", M.PROD),
                 ("dev", M.PROD), ("prod", M.DEV)):
        with _Muhit(e), _Belgi(b):
            holat, xabar = M.moslik()
            eq(f".env '{e}' + baza '{b}' -> zid", holat, "zid")
            check(e in xabar and b in xabar,
                  "xabar IKKALASINI ham aytadi", xabar)

    # Yarim holatlar.
    with _Muhit(None), _Belgi(M.PROD):
        eq(".env yo'q -> env_yoq", M.moslik()[0], "env_yoq")
    with _Muhit("prod"), _Belgi(None):
        eq("baza belgilanmagan -> baza_yoq", M.moslik()[0], "baza_yoq")
    with _Muhit(None), _Belgi(None):
        eq("ikkalasi ham yo'q -> env_yoq", M.moslik()[0], "env_yoq")


def test_baza_qulfi():
    head("6. BAZANING O'ZI aytgan qulf")
    sinov = os.path.join(ROOT, "_tests", "yangi_test.py")

    # ENG MUHIM: `.env` YOLG'ON gapiradi, baza haqiqatni aytadi.
    with _Muhit("dev"), _Belgi(M.PROD), _Skript(sinov):
        try:
            M.qulf_tekshir()        # `.env` ga qaraydi — O'TKAZADI
            check(True, ".env qulfi 'dev' ni o'tkazadi (u aldangan)")
        except M.ProdQulfi:
            check(False, ".env qulfi 'dev' ni o'tkazadi", "rad etdi")
        try:
            M.qulf_tekshir_baza()   # BAZAGA qaraydi — TO'XTATADI
            check(False, "BAZA qulfi to'xtatdi", "o'tkazib yubordi")
        except M.ProdQulfi as e:
            check(True, "BAZA qulfi to'xtatdi (.env yolg'on gapirsa ham)")
            check("belgila" in str(e), "xabar tuzatish yo'lini aytadi")

    # Staging bazada o'tadi.
    with _Muhit("staging"), _Belgi(M.STAGING), _Skript(sinov):
        try:
            M.qulf_tekshir_baza()
            check(True, "staging bazada sinov o'tadi")
        except M.ProdQulfi:
            check(False, "staging bazada sinov o'tadi", "rad etildi")

    # Belgilanmagan bazada o'tadi (eski o'rnatma to'xtamasin).
    with _Muhit("dev"), _Belgi(None), _Skript(sinov):
        try:
            M.qulf_tekshir_baza()
            check(True, "belgilanmagan bazada sinov to'xtamaydi")
        except M.ProdQulfi:
            check(False, "belgilanmagan bazada sinov to'xtamaydi", "rad etildi")

    # ILOVA prod bazada ham ishlaydi.
    with _Muhit("prod"), _Belgi(M.PROD), _Skript(
            os.path.join(ROOT, "check_setup.py")):
        try:
            M.qulf_tekshir_baza()
            check(True, "ilova prod bazada ISHLAYDI")
        except M.ProdQulfi:
            check(False, "ilova prod bazada ishlaydi", "rad etildi")


def test_belgilash():
    head("7. Belgilashni tekshirish")
    # NOMALUM QIYMAT rad etiladi: "prodakshn" deb yozilgan belgi
    # jimgina "belgilanmagan" bo'lib qolardi va qulf ochilardi.
    for yomon in ("prodakshn", "", "ishchi", None):
        try:
            M.baza_belgila(yomon)
            check(False, f"{yomon!r} rad etildi", "qabul qilindi")
        except ValueError as e:
            check("Mumkin" in str(e), f"{yomon!r} rad etildi va yo'l ko'rsatildi")
        except Exception as e:                      # noqa: BLE001
            check(False, f"{yomon!r} rad etildi", f"boshqa xato: {e}")


def test_tavsif():
    head("4. Ko'rsatish")
    with _Muhit("staging"):
        t = M.tavsif()
        check("staging" in t, f"tavsifda muhit nomi bor: {t!r}")
        # BAZA NOMI ham ko'rsatiladi: eng ko'p uchraydigan xato —
        # `.env` da "staging" yozilib, DSN prod bazasini
        # ko'rsatishi.
        check("baza:" in t, "tavsifda baza nomi ham bor")
    with _Muhit(None):
        check("noma'lum" in M.tavsif(), "nom yo'q bo'lsa ochiq aytiladi")


if __name__ == "__main__":
    test_nom()
    test_sinov_aniqlash()
    test_qulf()
    test_moslik()
    test_baza_qulfi()
    test_belgilash()
    test_tavsif()
    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
