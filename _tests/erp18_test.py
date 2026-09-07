"""
HUQUQ CHEGARASI sinovi — qoida BAZADA ham ushlab turiladimi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp18_test.py

NIMA UCHUN: "ERP `public.*` dan O'QIYDI, YOZMAYDI" degan qoida shu
paytgacha faqat SINOVDA edi — ya'ni kelishuv, himoya emas. Bitta
noto'g'ri `UPDATE` tender-ai ma'lumotini o'zgartirardi va buni sinov
KEYIN aytardi. `schema_patch_erp_23.sql` shu qoidani bazaga ko'chiradi.

DIQQAT — HIMOYA HALI YOQILMAGAN: ilova `postgres` bilan ulanadi
(`XT_DB_DSN`), ya'ni rol cheklovlari unga tegmaydi. Sinov shuni ham
OCHIQ aytadi: "grantlar to'g'ri, lekin ular hozir ishlamayapti".
Yoqish — operator qadami (`docs/erp_texnik.md`, patch sarlavhasi).

Tekshiriladi:
  1) RO'YXAT KODDAN: ERP kodi `public.*` dan nimani o'qisa, `erp`
     roliga AYNAN o'sha berilgan bo'lsin — ortiq ham, kam ham emas.
  2) FAQAT O'QISH: `public` da birorta INSERT/UPDATE/DELETE yo'q.
  3) O'Z SXEMASI: `erp.*` da to'liq ishlaydi (aks holda ilova rol
     bilan ulanganda darhol yiqilardi).
  4) HOLAT OCHIQ: qaysi foydalanuvchi bilan ulanilyapti va cheklov
     kuchdami.
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

from dotenv import load_dotenv

load_dotenv()

from api import db  # noqa: E402

#: ERP kodi `public.*` dan o'qiydigan obyektlar (patchda ham shu
#: ro'yxat). Yangi obyekt o'qilsa — IKKALASI ham yangilanadi va sinov
#: buni majburlaydi.
KUTILGAN = {"tender", "dim_status", "dim_area", "v_tender_manba",
            "catalog_product", "v_erp_topshiriq"}

#: Kodda uchraydigan, lekin `public` da BO'LMAGAN nomlar (ERP o'z
#: sxemasi yoki SQL kalit so'zlari) — qidiruvdan chiqariladi.
ETIBORSIZ = {"erp", "information_schema", "pg_roles", "pg_constraint"}

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


def _kodda_oqiladigan():
    """ERP kodidagi SQL matnlaridan `public.*` obyektlari.

    IZOH VA DOKSTRING HISOBGA OLINMAYDI — ular tushuntirish uchun va
    u yerda boshqa loyihaning jadvallari ham tilga olinadi (masalan
    "Tender-AI `public.tender_topshiriq` ga yozadi"). Shuning uchun
    fayl `ast` bilan ajratiladi va faqat HAQIQIY satr qiymatlari
    (SQL matnlari) qaraladi."""
    import ast

    nomlar = set()
    for papka in ("api", os.path.join("api", "erp")):
        yol = os.path.join(ROOT, papka)
        for fayl in os.listdir(yol):
            if not fayl.endswith(".py"):
                continue
            src = open(os.path.join(yol, fayl), encoding="utf-8").read()
            daraxt = ast.parse(src)
            # Dokstringlar — chiqarib tashlanadi.
            doklar = set()
            for tugun in ast.walk(daraxt):
                if isinstance(tugun, (ast.Module, ast.ClassDef,
                                      ast.FunctionDef, ast.AsyncFunctionDef)):
                    d = ast.get_docstring(tugun, clean=False)
                    if d:
                        doklar.add(d)
            for tugun in ast.walk(daraxt):
                if not isinstance(tugun, ast.Constant):
                    continue
                if not isinstance(tugun.value, str) or tugun.value in doklar:
                    continue
                matn = tugun.value
                for m in re.finditer(r"(?:^|[\s(])(?:FROM|JOIN)\s+([a-zA-Z_][\w.]*)",
                                     matn):
                    nom = m.group(1)
                    if nom.startswith("erp."):
                        continue
                    nom = (nom.split(".")[-1] if nom.startswith("public.")
                           else nom)
                    if "." in nom or nom in ETIBORSIZ:
                        continue
                    nomlar.add(nom)
                # `FROM {VIEW}` kabi o'zgaruvchili so'rovlar uchun:
                # nom o'zgarmasda yozilgan (`VIEW = "public.v_..."`).
                for m in re.finditer(r"^public\.([a-z_][a-z0-9_]*)$", matn):
                    nomlar.add(m.group(1))
    return nomlar


GRANT_SQL = """
SELECT table_name, privilege_type
  FROM information_schema.role_table_grants
 WHERE grantee = 'erp' AND table_schema = %(s)s
"""


def main():
    db.init_pool()
    head("1. Rol va grantlar")
    if not db.query_one("SELECT 1 AS x FROM pg_roles WHERE rolname = 'erp'"):
        print("  SKIP `erp` roli yo'q (CREATE ROLE erp LOGIN ...)")
        return
    pub = db.query(GRANT_SQL, {"s": "public"})
    berilgan = {r["table_name"] for r in pub}
    huquqlar = {r["privilege_type"] for r in pub}

    eq("public da AYNAN kerakli obyektlar", sorted(berilgan), sorted(KUTILGAN))
    eq("public da FAQAT o'qish", sorted(huquqlar), ["SELECT"])

    head("2. Ro'yxat KOD bilan mos")
    kodda = _kodda_oqiladigan()
    # Kodda uchraydigan, lekin `public` da mavjud bo'lmagan nomlar
    # (masalan CTE nomi) — bazadan tekshirib chiqariladi.
    haqiqiy = {n for n in kodda if db.scalar(
        "SELECT to_regclass(%(n)s) IS NOT NULL", {"n": f"public.{n}"})}
    yetishmayotgan = sorted(haqiqiy - berilgan)
    eq("kod o'qiydigan hamma obyektga huquq bor", yetishmayotgan, [])
    ortiqcha = sorted(berilgan - haqiqiy)
    check(not ortiqcha, "ortiqcha huquq yo'q", str(ortiqcha))

    head("3. O'z sxemasi")
    erp = db.query(GRANT_SQL, {"s": "erp"})
    erp_huquq = {r["privilege_type"] for r in erp}
    for kerak in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        check(kerak in erp_huquq, f"erp.* da {kerak} bor")
    check(len({r["table_name"] for r in erp}) >= 20,
          "erp sxemasidagi jadvallarga huquq berilgan",
          str(len({r["table_name"] for r in erp})))

    head("4. Holat — himoya YOQILGANMI")
    dsn = os.environ.get("XT_DB_DSN", "")
    m = re.search(r"user=(\w+)", dsn)
    kim = m.group(1) if m else "?"
    print(f"       ilova ulanadi: user={kim}")
    if kim == "erp":
        check(True, "himoya YOQILGAN (ilova `erp` roli bilan ulanadi)")
    else:
        check(True, "grantlar tayyor, lekin HIMOYA HALI YOQILMAGAN "
                    f"(user={kim}) — bu ma'lum va hujjatda yozilgan")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
