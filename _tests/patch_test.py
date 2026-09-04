"""
TEKSHIRUVNI TEKSHIRISH — `check_setup.py` haqiqatan shu patchni
o'lchayaptimi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/patch_test.py

NIMA UCHUN BOR
==============
`check_setup.py` har patch uchun bitta obyektga qaraydi: bor bo'lsa
"OK". Lekin obyekt SHU PATCH tomonidan yaratilgani hech qayerda
tekshirilmasdi. Natijada tekshiruv BOR, o'tadi va BOSHQA NARSANI
o'lchaydi — loyihada tanish sinf (`UPDATED.md` §16: "o'zi yaratgan
qatorni sanash", "o'lchanmagan = nol").

Ikki haqiqiy holat topildi va tuzatildi:

  26-patch  `chat_message` jadvaliga qarardi. Jadval 25-patchda
            yaratilgan, ya'ni 26-patch UMUMAN qo'llanmasa ham "OK".
  2-patch   `client_company` ga qarardi. U 1-patchda yaratilgan.
            (`api/erp/clients.py` ning o'zi to'g'ri jadvalga —
            `client_document` ga — qarardi, ya'ni ikki manba
            ajralib ketgan edi.)
  20-patch  UMUMAN ro'yxatda yo'q edi. U `erp.v_tai_actor` ni
            TASHLAB, boshqa shaklda qayta yaratadi; qo'llanmasa view
            eski shaklda qoladi va Tender-AI undan HECH NARSA
            topolmaydi — "ikkala tomon ham ulandik deb o'ylaydi".

BU SINOV BAZAGA TEGMAYDI: u `.sql` FAYLLARINI o'qiydi va `check_setup`
ro'yxatlari bilan solishtiradi. Ya'ni bo'sh o'rnatmada ham ishlaydi va
yangi patch qo'shilganda darhol ogohlantiradi.
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

import check_setup as CS  # noqa: E402

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


def head(t):
    print(f"\n=== {t} ===")


# ---------------------------------------------------------------------------
# Patch fayllarini o'qish
# ---------------------------------------------------------------------------
IZOH = re.compile(r"--[^\n]*")
RE_TABLE = re.compile(r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\.(\w+)", re.I)
RE_VIEW = re.compile(
    r"CREATE\s+(?:OR REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+(\w+)\.(\w+)", re.I)
RE_COL = re.compile(r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+(\w+)", re.I)
RE_NUM = re.compile(r"schema_patch_erp_(\d+)\.sql$")


def patchlar():
    """fayl nomi -> {"obyekt": {...}, "ustun": {...}} (izohlarsiz)."""
    out = {}
    for nom in sorted(os.listdir(ROOT)):
        if not RE_NUM.search(nom):
            continue
        sql = IZOH.sub("", open(os.path.join(ROOT, nom), encoding="utf-8").read())
        out[nom] = {
            # Jadval ham, view ham `information_schema.tables` da
            # ko'rinadi — `check_setup.table_exists()` ikkalasini ham
            # topadi, shuning uchun bitta to'plamda.
            "obyekt": {f"{a}.{b}" for a, b in RE_TABLE.findall(sql)}
                      | {f"{a}.{b}" for a, b in RE_VIEW.findall(sql)},
            "ustun": set(RE_COL.findall(sql)),
        }
    return out


def test_royxatlar():
    head("1. Har tekshiruv O'Z patchini o'lchaydi")
    P = patchlar()
    check(len(P) >= 26, f"{len(P)} ta patch fayli topildi")

    for fname, schema, obj, what in CS.PATCHES:
        nima = f"{schema}.{obj}"
        g = P.get(fname)
        if not g:
            check(False, f"{fname} — fayl topilmadi")
            continue
        # ENG MUHIM TEKSHIRUV: obyekt AYNAN shu patchda yaratilgan
        # bo'lsin. Aks holda tekshiruv oldingi patchni o'lchaydi va
        # bu patch qo'llanmasa ham "OK" beradi.
        check(nima in g["obyekt"],
              f"{fname}: `{nima}` shu patchda yaratilgan",
              "obyekt bu faylda YARATILMAYDI — tekshiruv boshqa "
              "patchni o'lchayapti (yolg'on OK)")

    for fname, schema, tbl, col, what in CS.PATCH_COLUMNS:
        g = P.get(fname)
        if not g:
            check(False, f"{fname} — fayl topilmadi")
            continue
        # Ustun `ADD COLUMN` bilan qo'shilishi SHART emas: 20-patch
        # view ni butunlay qayta yaratadi va ustun `CREATE VIEW`
        # ichida chiqadi. Shuning uchun ikki yo'ldan biri yetadi.
        obyektda = f"{schema}.{tbl}" in g["obyekt"]
        check(col in g["ustun"] or obyektda,
              f"{fname}: `{tbl}.{col}` shu patchda paydo bo'ladi",
              "ustun ham, uni o'z ichiga olgan obyekt ham bu faylda "
              "yo'q — yolg'on OK xavfi")


def test_qamrov():
    head("2. Har patch tekshiriladi")
    P = patchlar()
    royxatda = ({f for f, *_ in CS.PATCHES}
                | {f for f, *_ in CS.PATCH_COLUMNS})

    # Ro'yxatga tushmagan patchlar `check_setup.py` da QO'LDA
    # tekshiriladi (rol CHECK i, CSRF ustuni, huquqlar). Ular fayl
    # matnida nomi bilan uchraydi — shuni tekshiramiz.
    kod = open(os.path.join(ROOT, "check_setup.py"), encoding="utf-8").read()
    for nom in P:
        if nom in royxatda:
            continue
        check(nom in kod,
              f"{nom}: ro'yxatda yo'q, lekin QO'LDA tekshiriladi",
              "patch hech qayerda tekshirilmaydi — qo'llanmagani "
              "bilinmay qoladi")


def test_ozini_tekshirish():
    head("3. Sinovning O'ZI ishlaydimi")
    P = patchlar()

    # Skript haqiqatan obyekt nomlarini topayaptimi — aks holda
    # yuqoridagi hamma "OK" bo'sh gap bo'lardi.
    check("erp.opportunity" in P["schema_patch_erp_1.sql"]["obyekt"],
          "1-patchda `erp.opportunity` topildi")
    check("erp.chat_message" in P["schema_patch_erp_25.sql"]["obyekt"],
          "25-patchda `erp.chat_message` topildi")
    check("eslatilgan" in P["schema_patch_erp_26.sql"]["ustun"],
          "26-patchda `eslatilgan` ustuni topildi")
    check("erp.v_tai_actor" in P["schema_patch_erp_20.sql"]["obyekt"],
          "20-patchda `erp.v_tai_actor` topildi")

    # IZOHLAR HISOBGA OLINMASIN: patch izohlarida "CREATE TABLE"
    # ko'p uchraydi va ular obyekt sanalsa, sinov yolg'on "OK"
    # bergan bo'lardi — ya'ni tekshiruvni tekshiruvchining o'zi
    # buzilardi.
    check("erp.opportunity_file" not in P["schema_patch_erp_25.sql"]["obyekt"],
          "izohdagi nomlar obyekt deb sanalmaydi")


if __name__ == "__main__":
    test_royxatlar()
    test_qamrov()
    test_ozini_tekshirish()
    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
