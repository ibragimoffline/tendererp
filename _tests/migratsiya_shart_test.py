"""
MIGRATSIYA SHARTI — "jurnalda qo'llangan" degani "ta'siri bor" EMAS.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/migratsiya_shart_test.py

NIMA UCHUN BOR
==============
`erp.schema_migration` bitta savolga javob beradi: fayl YURITILDIMI.
U ikkinchi savolga — fayl NIMA QILISHINI AYTGAN bo'lsa, o'sha
BAJARILDIMI — javob bermaydi va bermasligi ham mumkin emas:
jurnalga yozuvni yurgizuvchi qo'yadi, patch ichida nima bo'lgani esa
psql ning ichida qoladi.

O'LCHANGAN HOLAT (2026-09-07, staging joylashtiruvi):

    qo'llanmoqda: schema_patch_erp_23.sql
    NOTICE: erp roli yo'q - patch o'tkazib yuborildi.
      OK

`OK` yozildi, jurnalga tushdi, joylashtirish davom etdi — va 23-patch
e'lon qilgan HAMMA huquq berilmadi. Ya'ni eng qimmat holat: xavfsizlik
qadami O'TKAZIB YUBORILDI va natija "muvaffaqiyatli" bo'lib ko'rindi.

Production da o'sha ogohlantirish CHIQMADI, ya'ni ikki muhit bir xil
jurnalga ega bo'lib, HAR XIL haqiqatda turibdi. Jurnalning o'zi buni
KO'RSATA OLMAYDI.

UCH HOLAT, IKKITA EMAS
======================
`BLOKLANGAN` — o'lchay olmadik (DSN yo'q, baza uzilgan). U `PASS`
EMAS va `FAIL` ham emas. Ikkisini bitta belgiga qo'shish
"o'lchanmagan" ni "yaxshi" ga aylantirardi — bu sinovni yozishga
sabab bo'lgan xatoning AYNAN o'zi.

    0 — hamma shart bajarilgan
    1 — kamida bitta shart BUZILGAN (jurnal "qo'llangan" deydi,
        ta'siri esa yo'q)
    2 — BLOKLANGAN: o'lchab bo'lmadi

NEGA JURNAL MATNI TEKSHIRILMAYDI
================================
Joylashtirish jurnalidagi `NOTICE` ni qidirish oson bo'lardi va
YOLG'ON bo'lardi: jurnal aylanib ketadi, boshqa muhitga tegishli
bo'ladi, formati o'zgaradi. Bu yerda BAZANING O'ZIDAN so'raladi —
rol bormi, grantlar bormi.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:                                # noqa: BLE001  # pragma: no cover
    pass

from api import db  # noqa: E402

PASS, FAIL, BLOK = "PASS", "FAIL", "BLOKLANGAN"

_natija: list[tuple[str, str, str]] = []


def qayd(holat: str, nima: str, izoh: str = "") -> None:
    _natija.append((holat, nima, izoh))
    belgi = {PASS: "PASS", FAIL: "FAIL", BLOK: "BLOK"}[holat]
    print(f"  [{belgi}] {nima}" + (f"\n         -> {izoh}" if izoh else ""))


def head(t: str) -> None:
    print(f"\n=== {t} ===")


# ---------------------------------------------------------------------------
# 23-PATCH: `erp` roli va uning huquqlari
# ---------------------------------------------------------------------------
# Ro'yxat PATCHDAN olingan (schema_patch_erp_23.sql, 70-76-qatorlar).
# Patch o'zgarsa bu ro'yxat ham o'zgarishi KERAK — `erp18_test.py`
# ro'yxatni KOD bilan solishtiradi, bu esa BAZA bilan.
P23_PUBLIC = [
    "tender", "dim_status", "dim_area",
    "v_tender_manba", "catalog_product", "v_erp_topshiriq",
]


def shart_23() -> None:
    """23-patch jurnalda bo'lsa — grantlar HAQIQATAN berilgan bo'lsin."""
    # 1) Rol bor-yo'qligi. Patch aynan shu tekshiruvda `RETURN` qiladi
    #    va o'zini muvaffaqiyatli deb tugatadi.
    rol = db.query_one("SELECT 1 AS x FROM pg_roles WHERE rolname = 'erp'")
    if not rol:
        qayd(FAIL, "23-patch: `erp` roli YO'Q",
             "jurnal `qo'llangan` deydi, patch esa rolni topmay "
             "O'TKAZIB YUBORGAN — e'lon qilingan huquqlarning "
             "BIRORTASI berilmagan. Tuzatish: `CREATE ROLE erp LOGIN "
             "PASSWORD '...'` va 23-patchni QAYTA qo'llash "
             "(jurnaldan yozuvni olib tashlab).")
        return
    qayd(PASS, "23-patch: `erp` roli bor")

    # 2) `public` da AYNAN olti obyekt va FAQAT o'qish.
    qatorlar = db.query(
        "SELECT table_name, privilege_type "
        "  FROM information_schema.role_table_grants "
        " WHERE grantee = 'erp' AND table_schema = 'public'")
    berilgan = {r["table_name"] for r in qatorlar}
    huquqlar = {r["privilege_type"] for r in qatorlar}

    yetishmayotgan = sorted(set(P23_PUBLIC) - berilgan)
    if yetishmayotgan:
        qayd(FAIL, "23-patch: `public` da huquq yetishmaydi",
             f"berilmagan: {yetishmayotgan}")
    else:
        qayd(PASS, f"23-patch: `public` da olti obyektga SELECT bor")

    ortiqcha = sorted(huquqlar - {"SELECT"})
    if ortiqcha:
        qayd(FAIL, "23-patch: `public` da O'QISHDAN ORTIQ huquq bor",
             f"{ortiqcha} — chegara qoidasi 'ERP public dan O'QIYDI, "
             "YOZMAYDI' buzilgan")
    else:
        qayd(PASS, "23-patch: `public` da faqat SELECT")

    # 3) O'z sxemasi — to'liq CRUD.
    erp_huquq = {r["privilege_type"] for r in db.query(
        "SELECT privilege_type "
        "  FROM information_schema.role_table_grants "
        " WHERE grantee = 'erp' AND table_schema = 'erp'")}
    yoq = sorted({"SELECT", "INSERT", "UPDATE", "DELETE"} - erp_huquq)
    if yoq:
        qayd(FAIL, "23-patch: `erp.*` da huquq yetishmaydi", f"yo'q: {yoq}")
    else:
        qayd(PASS, "23-patch: `erp.*` da to'liq CRUD")


#: Jurnalga tushgan fayl -> uning SHARTINI tekshiruvchi funksiya.
#: Yangi patch xavfsizlik/huquq ishi qilsa — shu yerga qo'shiladi.
SHARTLAR = {
    "schema_patch_erp_23.sql": shart_23,
}


def main() -> int:
    print("=" * 60)
    print("MIGRATSIYA SHARTI — jurnal AYTGANI bajarilganmi")
    print("=" * 60)

    if not os.environ.get("XT_DB_DSN"):
        head("O'lchash")
        qayd(BLOK, "XT_DB_DSN yo'q — bazadan so'rab bo'lmadi",
             "Bu PASS EMAS. Shart baza ichida yashaydi va uni fayldan "
             "o'qib bo'lmaydi.")
        return 2

    try:
        db.init_pool()
    except Exception as e:                        # noqa: BLE001
        head("O'lchash")
        qayd(BLOK, "bazaga ulanib bo'lmadi", str(e)[:200])
        return 2

    try:
        head("Jurnalga tushgan patchlar uchun SHART")
        jurnal = {r["fayl"] for r in db.query(
            "SELECT fayl FROM erp.schema_migration")}
        if not jurnal:
            qayd(BLOK, "`erp.schema_migration` bo'sh",
                 "migratsiya hali yuritilmagan — shart tekshirilmadi")
            return 2

        for fayl, tekshir in sorted(SHARTLAR.items()):
            if fayl not in jurnal:
                # Qo'llanmagan patchning sharti ham talab qilinmaydi.
                qayd(PASS, f"{fayl}: jurnalda yo'q — shart talab qilinmaydi")
                continue
            tekshir()
    finally:
        db.close_pool()

    print("\n" + "=" * 60)
    yiqilgan = [n for h, n, _ in _natija if h == FAIL]
    blok = [n for h, n, _ in _natija if h == BLOK]
    otgan = [n for h, n, _ in _natija if h == PASS]
    print(f"NATIJA: {len(otgan)} PASS · {len(yiqilgan)} FAIL · "
          f"{len(blok)} BLOKLANGAN")
    if yiqilgan:
        return 1
    if blok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
