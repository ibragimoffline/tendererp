"""
SHARTNOMA-VIEW'LAR sinovi — ERP dan Tender-AI ga ochilgan yuza.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp15_test.py

NIMA UCHUN: bu to'rt view — IKKI LOYIHA orasidagi shartnoma
(`schema_patch_erp_19.sql`). Ustun nomini o'zgartirish yoki tartibini
almashtirish TENDER-AI ni buzadi, va u boshqa repozitoriyda —
sinovlari bu yerda ishlamaydi. Shuning uchun shartnoma SHU YERDA
qulflanadi: ustunlar ro'yxati sinovda YOZILGAN va farq bo'lsa sinov
yiqiladi.

Ikkinchi savol — MAXFIYLIK: view faqat kerakli ustunni berishi kerak.
Parol xeshi, email, sessiya, summa va izoh tender-ai ga kerak emas va
BERILMASLIGI kerak. Sinov ularning YO'QLIGINI tekshiradi.

Tekshiriladi:
  1) SHAKL: har view da AYNAN kutilgan ustunlar, kutilgan tartibda.
  2) MAXFIYLIK: taqiqlangan ustunlar yo'q.
  3) MA'LUMOT: view lar haqiqiy qatorlarni to'g'ri ko'rsatadi
     (hodim, karta mas'uli, muddati o'tgan hujjat, qoldiq).
  4) HUQUQ: `tai_app` faqat view larni ko'radi, JADVALNI emas.
  5) CHEGARA: sinov `public.*` ga tegmaydi.

Belgisi: 'ZZTEST-VIEW'. Oxirida hammasi o'chiriladi.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api import db  # noqa: E402

MARK = "ZZTEST-VIEW"
TENDER = 990000021

#: SHARTNOMA: view -> ustunlar AYNAN shu tartibda.
#: Yangi ustun faqat OXIRIGA qo'shiladi (eski o'quvchi buzilmasin).
SHAKL = {
    # Shakl TENDER-AI KODIDA yozilgan (`api/aktor.py:_erp_sessiyadan`)
    # va uning hujjatida e'lon qilingan (`docs/erp_kimlik.md` §4).
    # 19-patchda boshqa nomlar bilan chiqqan edi — 20-patch to'g'riladi.
    "v_tai_actor": ["erp_user_id", "login", "ism", "rol", "erp_broker_id",
                    "faol", "token_hash", "expires_at"],
    "v_tender_status": ["opportunity_id", "tender_id", "status", "status_label",
                        "priority", "broker_name", "client_name", "created_at",
                        "updated_at", "assignee_full_name"],
    "v_stock": ["product_id", "product_name", "unit", "qty", "reserved",
                "available", "updated_at"],
    "v_client_document": ["client_id", "client_name", "client_inn",
                          "document_id", "doc_type", "name", "number",
                          "issued_at", "valid_until", "expired"],
}

#: Bu ustunlar HECH QAYSI shartnoma-view da bo'lmasligi kerak.
#:
#: `token_hash` ro'yxatda YO'Q va bu ataylab: u sessiya ISBOTI
#: (`sha256`, xom token emas) va aynan shu ustun `erp_sessiya`
#: darajasini mumkin qiladi. Xom token esa ERP da ham saqlanmaydi.
TAQIQ = ["password_hash", "email", "csrf_token", "start_price", "note",
         "win_probability", "unit_cost", "file_ref"]

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


COLS_SQL = """
SELECT column_name FROM information_schema.columns
 WHERE table_schema = 'erp' AND table_name = %(t)s
 ORDER BY ordinal_position
"""

PUBLIC_MAX_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def _cols(view):
    return [r["column_name"] for r in db.query(COLS_SQL, {"t": view})]


def _seed(d):
    d["broker"] = db.execute_returning(
        "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
        {"n": f"{MARK} hodim"})["id"]
    d["user"] = db.execute_returning(
        "INSERT INTO erp.app_user (username, full_name, password_hash, role, "
        "broker_id, active) VALUES (%(u)s, %(f)s, 'x', 'menejer', %(b)s, true) "
        "RETURNING id",
        {"u": "zztest_view", "f": f"{MARK} hisob", "b": d["broker"]})["id"]
    d["client"] = db.execute_returning(
        "INSERT INTO erp.client_company (name, inn) VALUES (%(n)s, %(i)s) "
        "RETURNING id", {"n": f"{MARK} mijoz", "i": "999000111"})["id"]
    d["opp"] = db.execute_returning(
        "INSERT INTO erp.opportunity (tender_id, title, broker_id, client_id, "
        "status) VALUES (%(t)s, %(n)s, %(b)s, %(c)s, 'preparing') RETURNING id",
        {"t": TENDER, "n": f"{MARK} karta", "b": d["broker"], "c": d["client"]})["id"]
    kecha = dt.date.today() - dt.timedelta(days=1)
    ertaga = dt.date.today() + dt.timedelta(days=365)
    for suffix, until in (("eski", kecha), ("yangi", ertaga)):
        d[f"doc_{suffix}"] = db.execute_returning(
            "INSERT INTO erp.client_document (client_id, doc_type, name, "
            "number, valid_until) VALUES (%(c)s, 'license', %(n)s, %(num)s, "
            "%(v)s) RETURNING id",
            {"c": d["client"], "n": f"{MARK} {suffix}",
             "num": f"{MARK}-{suffix}", "v": until})["id"]


def _cleanup(d):
    for sql, key in (
            ("DELETE FROM erp.app_session WHERE user_id = %(v)s RETURNING id",
             "user"),
            ("DELETE FROM erp.client_document WHERE client_id = %(v)s RETURNING id",
             "client"),
            ("DELETE FROM erp.opportunity_history WHERE opportunity_id = %(v)s "
             "RETURNING id", "opp"),
            ("DELETE FROM erp.opportunity WHERE id = %(v)s RETURNING id", "opp"),
            ("DELETE FROM erp.app_user WHERE id = %(v)s RETURNING id", "user"),
            ("DELETE FROM erp.client_company WHERE id = %(v)s RETURNING id",
             "client"),
            ("DELETE FROM erp.broker WHERE id = %(v)s RETURNING id", "broker")):
        if d.get(key):
            while db.execute_returning(sql, {"v": d[key]}):
                pass


def test_shakl():
    head("1. Shakl — ustunlar AYNAN shartnomadagidek")
    for view, kutilgan in SHAKL.items():
        bor = _cols(view)
        if not bor:
            check(False, f"{view} yo'q — schema_patch_erp_19.sql qo'llanmagan")
            continue
        eq(f"{view}: ustunlar", bor, kutilgan)

    head("2. Maxfiylik — ortiqcha ustun yo'q")
    for view in SHAKL:
        bor = set(_cols(view))
        yomon = [c for c in TAQIQ if c in bor]
        eq(f"{view}: taqiqlangan ustun yo'q", yomon, [])


def test_malumot():
    head("3. Ma'lumot to'g'ri ko'rinadi")
    d = {}
    before = db.query_one(PUBLIC_MAX_SQL)
    try:
        _seed(d)

        a = db.query_one("SELECT * FROM erp.v_tai_actor WHERE erp_user_id = %(i)s",
                         {"i": d["user"]})
        eq("v_tai_actor: rol ustuni `role` dan keladi", a["rol"], "menejer")
        eq("v_tai_actor: faol", a["faol"], True)
        eq("v_tai_actor: login", a["login"], "zztest_view")
        eq("v_tai_actor: ism", a["ism"], f"{MARK} hisob")
        eq("v_tai_actor: hodimga bog'lanish", a["erp_broker_id"], d["broker"])
        # SESSIYASIZ hodim ham KO'RINADI: tender-ai xaritani shu view
        # bilan tekshiradi va bugun kirmagan odam "yetim" bo'lib
        # chiqmasligi kerak.
        eq("sessiyasiz hodim ham ro'yxatda", a["token_hash"], None)

        # --- SESSIYA ISBOTI ---
        # Tender-AI aynan shu so'rovni yuboradi (`api/aktor.py`).
        d["sessiya"] = db.execute_returning(
            "INSERT INTO erp.app_session (user_id, token_hash, expires_at, "
            "csrf_token) VALUES (%(u)s, %(h)s, now() + interval '1 day', 'zz') "
            "RETURNING id", {"u": d["user"], "h": MARK + "-xesh"})["id"]
        r = db.query_one(
            "SELECT erp_user_id, login, ism, rol FROM erp.v_tai_actor "
            "WHERE token_hash = %(h)s AND expires_at > now()",
            {"h": MARK + "-xesh"})
        check(r is not None and r["erp_user_id"] == d["user"],
              "sessiya xeshi bo'yicha aktor topiladi")
        # Muddati o'tgan sessiya ISBOT EMAS.
        db.execute_returning(
            "UPDATE erp.app_session SET expires_at = now() - interval '1 day' "
            "WHERE id = %(i)s RETURNING id", {"i": d["sessiya"]})
        eq("muddati o'tgan sessiya ko'rinmaydi",
           db.scalar("SELECT count(*) FROM erp.v_tai_actor "
                     "WHERE token_hash = %(h)s", {"h": MARK + "-xesh"}), 0)
        # Faolsizlantirilgan hisob orqali ham kirib bo'lmaydi.
        db.execute_returning(
            "UPDATE erp.app_session SET expires_at = now() + interval '1 day' "
            "WHERE id = %(i)s RETURNING id", {"i": d["sessiya"]})
        db.execute_returning("UPDATE erp.app_user SET active = false "
                             "WHERE id = %(i)s RETURNING id", {"i": d["user"]})
        eq("faolsiz hisobning sessiyasi isbot emas",
           db.scalar("SELECT count(*) FROM erp.v_tai_actor "
                     "WHERE token_hash = %(h)s", {"h": MARK + "-xesh"}), 0)
        eq("faolsiz hisob ro'yxatda qoladi (yetim emas)",
           db.scalar("SELECT faol FROM erp.v_tai_actor "
                     "WHERE erp_user_id = %(i)s", {"i": d["user"]}), False)
        db.execute_returning("UPDATE erp.app_user SET active = true "
                             "WHERE id = %(i)s RETURNING id", {"i": d["user"]})

        s = db.query_one("SELECT * FROM erp.v_tender_status "
                         "WHERE opportunity_id = %(i)s", {"i": d["opp"]})
        eq("v_tender_status: kimga biriktirilgan",
           s["assignee_full_name"], f"{MARK} hodim")
        eq("v_tender_status: status yorlig'i",
           s["status_label"], "Taklif tayyorlanmoqda")
        eq("v_tender_status: mijoz nomi", s["client_name"], f"{MARK} mijoz")

        docs = db.query("SELECT * FROM erp.v_client_document "
                        "WHERE client_id = %(i)s ORDER BY number", {"i": d["client"]})
        eq("v_client_document: ikki hujjat", len(docs), 2)
        eski = next(x for x in docs if x["number"].endswith("eski"))
        yangi = next(x for x in docs if x["number"].endswith("yangi"))
        eq("muddati o'tgan hujjat belgilanadi", eski["expired"], True)
        eq("amaldagi hujjat belgilanmaydi", yangi["expired"], False)
        eq("mijoz INN si ham beriladi", eski["client_inn"], "999000111")

        # `v_stock` — `v_stock_balance` ning shartnoma yuzasi: ikkalasi
        # BIR XIL qatorni ko'rsatishi kerak.
        eq("v_stock qatorlari v_stock_balance bilan bir xil",
           db.scalar("SELECT count(*) FROM erp.v_stock"),
           db.scalar("SELECT count(*) FROM erp.v_stock_balance"))
        farq = db.scalar("""
            SELECT count(*) FROM erp.v_stock s
              JOIN erp.v_stock_balance b ON b.product_id = s.product_id
             WHERE s.qty IS DISTINCT FROM b.qty
                OR s.available IS DISTINCT FROM b.available""")
        eq("qoldiq qiymatlari mos", farq, 0)
    finally:
        head("4. Tozalash va chegara")
        _cleanup(d)
        eq("sinov ma'lumoti o'chirildi",
           db.scalar("SELECT count(*) FROM erp.opportunity "
                     "WHERE title LIKE %(m)s", {"m": MARK + "%"}), 0)
        after = db.query_one(PUBLIC_MAX_SQL)
        eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
        eq("public.tender yangilanmadi", after["t_max"], before["t_max"])


GRANT_SQL = """
SELECT table_name, privilege_type
  FROM information_schema.role_table_grants
 WHERE grantee = 'tai_app' AND table_schema = 'erp'
"""


def test_huquq():
    head("5. tai_app — faqat view, jadval EMAS")
    if not db.query_one("SELECT 1 AS x FROM pg_roles WHERE rolname = 'tai_app'"):
        print("  SKIP tai_app roli yo'q (tender-ai o'rnatilmagan)")
        return
    rows = db.query(GRANT_SQL)
    berilgan = {r["table_name"] for r in rows}
    huquqlar = {r["privilege_type"] for r in rows}
    for view in SHAKL:
        check(view in berilgan, f"{view}: SELECT berilgan")
    eq("faqat SELECT (yozish yo'q)", sorted(huquqlar), ["SELECT"])

    # ENG MUHIMI: jadvallarga huquq berilmagan bo'lsin.
    jadvallar = db.query("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'erp' AND table_type = 'BASE TABLE'""")
    ochiq = [t["table_name"] for t in jadvallar if t["table_name"] in berilgan]
    eq("hech bir JADVAL ochilmagan", ochiq, [])


if __name__ == "__main__":
    try:
        db.init_pool()
        test_shakl()
        test_malumot()
        test_huquq()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
