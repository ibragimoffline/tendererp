"""
O'LCHOV ASBOBI sinovi — `olchov.py`.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/olchov_test.py

NIMA UCHUN BOR: asbob hisobot beradi, ya'ni o'zi "yiqilmaydi" — yolg'on
raqam ko'rsatsa ham yashil qoladi. Shuning uchun uning UCHTA VA'DASI
alohida tekshiriladi:

  1. `—` VA `0` FARQ QILADI. O'lchanmagan narsa nol emas: jadval yo'q
     bo'lsa `None` qaytadi va ekranda `—` chiqadi. Ular aralashsa
     "chat ishlatilmayapti" bilan "chat jadvali yo'q" bir xil
     ko'rinardi.
  2. FAQAT O'QIYDI. Bazadagi qator soni yurishdan oldin va keyin
     AYNAN bir xil (`_olchov/` dagi o'z fayli bundan mustasno).
  3. MANBA BITTA. `check_setup.py` faol rahbar/menejer sonini
     `olchov.boshliq_soni()` dan oladi va o'z SQL so'rovini
     YOZMAYDI — aks holda rol ro'yxati o'zgarganda bittasi
     yangilanib, ikkinchisi eskirardi.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

import olchov  # noqa: E402
from api import db  # noqa: E402

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
# 1. Bazasiz — sof mantiq
# ---------------------------------------------------------------------------
def test_korsatish():
    head("1. `—` va `0` FARQ qiladi")

    # Bu ikki qator butun asbobning ma'nosini ushlab turadi.
    eq("o'lchanmagan -> `—`", olchov._k(olchov.YOQ), "—")
    eq("nol -> `0`", olchov._k(0), "0")
    check(olchov.YOQ is None, "`YOQ` — `None`, `0` EMAS")
    eq("oddiy son", olchov._k(42), "42")

    # Farq ustuni ham aralashtirmasin.
    eq("farq: o'lchanmagandan", olchov._farq(5, None), "—")
    eq("farq: o'lchanmaganga", olchov._farq(None, 5), "—")
    eq("farq: o'sish", olchov._farq(7, 5), "+2")
    eq("farq: o'zgarmadi", olchov._farq(5, 5), "0")
    eq("farq: kamayish", olchov._farq(3, 5), "-2")


def test_manba_bitta():
    head("2. MANBA bitta — check_setup o'z so'rovini yozmaydi")

    kod = open(os.path.join(ROOT, "check_setup.py"), encoding="utf-8").read()
    check("olchov.boshliq_soni()" in kod,
          "check_setup `olchov.boshliq_soni()` ni chaqiradi")

    # Rol ro'yxatini QO'LDA so'raydigan SQL qolmagan bo'lsin.
    qoldi = re.findall(r"role IN \('rahbar'[^)]*\)", kod)
    eq("check_setup da qo'lda rol so'rovi qolmadi", len(qoldi), 0)

    # Ro'yxatning O'ZI ham bitta joyda: `olchov.py` da.
    kod_o = open(os.path.join(ROOT, "olchov.py"), encoding="utf-8").read()
    eq("olchov da rol ro'yxati BIR marta",
       len(re.findall(r"role IN \('rahbar'[^)]*\)", kod_o)), 1)


# ---------------------------------------------------------------------------
# 3. Baza bilan
# ---------------------------------------------------------------------------
SANOQ_SQL = """
SELECT (SELECT count(*) FROM erp.opportunity)         AS opp,
       (SELECT count(*) FROM erp.app_user)            AS usr,
       (SELECT count(*) FROM erp.opportunity_history) AS hist,
       (SELECT count(*) FROM public.tender)           AS tender
"""


def test_faqat_oqiydi():
    head("3. FAQAT O'QIYDI")

    oldin = db.query_one(SANOQ_SQL)
    qatorlar = olchov.olcha()
    keyin = db.query_one(SANOQ_SQL)
    eq("bazadagi qator soni O'ZGARMADI", dict(keyin), dict(oldin))

    check(len(qatorlar) >= 7, f"{len(qatorlar)} ta hisoblagich o'lchandi")
    for q in qatorlar:
        check(set(q) == {"kalit", "nomi", "jami", "odam", "izoh"},
              f"`{q['kalit']}` shakli to'g'ri", str(set(q)))
        check(q["izoh"].strip() != "",
              f"`{q['kalit']}` da izoh bor — raqam o'zi gapirmaydi")


def test_odam_jami_dan_kop_emas():
    head("4. ODAM ustuni JAMI dan oshmaydi")

    for q in olchov.olcha():
        if q["jami"] is None or q["odam"] is None:
            continue
        check(q["odam"] <= q["jami"],
              f"`{q['kalit']}`: odam ({q['odam']}) <= jami ({q['jami']})")


def test_yoq_jadval():
    head("5. Jadval yo'q bo'lsa — `—`, `0` emas")

    check(olchov._jadval_bor("erp", "opportunity"),
          "mavjud jadval topiladi")
    check(not olchov._jadval_bor("erp", "bunday_jadval_yoq"),
          "yo'q jadval topilmaydi")
    # Xato so'rov ham `None` qaytarsin, `0` emas — aks holda
    # "o'lchandi, hech narsa yo'q" degan YOLG'ON xabar chiqardi.
    eq("yaroqsiz so'rov -> None (`—`)",
       olchov._son("SELECT count(*) FROM erp.bunday_jadval_yoq"), None)
    eq("bo'sh natija -> 0 (haqiqatan nol)",
       olchov._son("SELECT count(*) FROM erp.app_user WHERE id = -1"), 0)


if __name__ == "__main__":
    test_korsatish()
    test_manba_bitta()
    try:
        db.init_pool()
    except Exception as e:                          # noqa: BLE001
        print(f"\n  DIQQAT: bazasiz sinov: {e}")
    else:
        test_faqat_oqiydi()
        test_odam_jami_dan_kop_emas()
        test_yoq_jadval()

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
