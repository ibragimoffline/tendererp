"""
EGALIK sinovi — "o'z kartalari" haqiqatan ham O'ZINIKIMI.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp13_test.py

NIMA UCHUN: huquqlar matritsasida (`api/erp/perm.py`) broker uchun ko'p
qatorda `own` turadi, lekin matritsa OBYEKTNI bilmaydi. Egalik zanjiri
`api/erp/egalik.py` da:

    app_user.broker_id -> broker.id -> opportunity.broker_id

Bu sinov aynan shu zanjirni SO'ROV yuborib tekshiradi: begona kartani
o'qish, tahrirlash, uning vazifasini yozish, mijozini ko'rish va
fakturasini ochish — hammasi 403 bo'lishi kerak, o'ziniki esa ochiq.

MUHIM: sinov ikki hodim va ikki karta YARATADI. Bazadagi ma'lumotga
tayanmaydi — demo tozalanganda qamrov jimgina tushib ketmaydi.

Tekshiriladi:
  1) RO'YXAT: broker faqat o'z kartalarini, mijozlarini, fakturalarini
     va rezervlarini ko'radi; menejerda cheklov yo'q.
  2) OBYEKT: begonasi 403 (404 EMAS — mavjudligini ham aytmaydi).
  3) BOG'LANMAGAN HISOB: "o'ziniki" bo'sh to'plam, sabab aytiladi.
  4) CHEGARA: `public.*` ga tegilmaydi.

Belgisi: 'ZZTEST-EGA'. Oxirida hammasi o'chiriladi.
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
from api.erp import egalik as E  # noqa: E402
from api.erp import perm as P  # noqa: E402

MARK = "ZZTEST-EGA"
#: `public.tender` ga bog'lanmaydi (FK yo'q) — sinov tender katalogiga
#: tayanmasin.
TENDER_A, TENDER_B = 990000001, 990000002

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


def _user(rol, broker_id=None):
    return {"id": 0, "username": "zz", "full_name": "ZZTEST", "role": rol,
            "role_label": A.ROLE_LABEL.get(rol), "broker_id": broker_id,
            "email": None, "active": True, "last_login_at": None, "csrf": "zz"}


PUBLIC_MAX_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def _seed(d):
    """Ikki hodim, ikki mijoz, ikki karta, ikki faktura va bitta vazifa.

    Yozuvlar `d` ga DARHOL qo'yiladi (qaytarilmaydi): o'rtada xato
    chiqsa ham tozalash yarim yaratilgan ma'lumotni topa olsin."""
    for k, suffix in (("a", "A"), ("b", "B")):
        d[f"broker_{k}"] = db.execute_returning(
            "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
            {"n": f"{MARK} hodim {suffix}"})["id"]
        d[f"client_{k}"] = db.execute_returning(
            "INSERT INTO erp.client_company (name) VALUES (%(n)s) RETURNING id",
            {"n": f"{MARK} mijoz {suffix}"})["id"]
    for k, tid in (("a", TENDER_A), ("b", TENDER_B)):
        d[f"opp_{k}"] = db.execute_returning(
            "INSERT INTO erp.opportunity (tender_id, title, broker_id, client_id, "
            "status) VALUES (%(t)s, %(n)s, %(b)s, %(c)s, 'new') RETURNING id",
            {"t": tid, "n": f"{MARK} karta {k.upper()}",
             "b": d[f"broker_{k}"], "c": d[f"client_{k}"]})["id"]
        d[f"inv_{k}"] = db.execute_returning(
            "INSERT INTO erp.invoice (client_id, client_name, opportunity_id, "
            "number, status) VALUES (%(c)s, %(cn)s, %(o)s, %(num)s, 'draft') "
            "RETURNING id",
            {"c": d[f"client_{k}"], "cn": f"{MARK} mijoz {k.upper()}",
             "o": d[f"opp_{k}"], "num": f"{MARK}-{k}"})["id"]
    d["task_b"] = db.execute_returning(
        "INSERT INTO erp.opportunity_task (opportunity_id, title) "
        "VALUES (%(o)s, %(n)s) RETURNING id",
        {"o": d["opp_b"], "n": f"{MARK} vazifa B"})["id"]


def _cleanup(d):
    n = 0
    for sql, ids in (
            ("DELETE FROM erp.invoice WHERE id = ANY(%(v)s) RETURNING id",
             [d.get("inv_a"), d.get("inv_b")]),
            ("DELETE FROM erp.opportunity_task WHERE opportunity_id = ANY(%(v)s) "
             "RETURNING id", [d.get("opp_a"), d.get("opp_b")]),
            ("DELETE FROM erp.opportunity_history WHERE opportunity_id = ANY(%(v)s) "
             "RETURNING id", [d.get("opp_a"), d.get("opp_b")]),
            ("DELETE FROM erp.opportunity WHERE id = ANY(%(v)s) RETURNING id",
             [d.get("opp_a"), d.get("opp_b")]),
            ("DELETE FROM erp.client_company WHERE id = ANY(%(v)s) RETURNING id",
             [d.get("client_a"), d.get("client_b")]),
            ("DELETE FROM erp.broker WHERE id = ANY(%(v)s) RETURNING id",
             [d.get("broker_a"), d.get("broker_b")])):
        v = [i for i in ids if i]
        if not v:
            continue
        while db.execute_returning(sql, {"v": v}):
            n += 1
    return n


def test_sof():
    head("1. Sof mantiq")
    eq("egalik filtri yoqilgan", P.OZ_FILTRI_TAYYOR, True)
    eq("bog'lanmagan hisob -> hodim yo'q",
       E.oz_broker_id(_user("broker")), None)
    eq("bog'langan hisob -> hodim bor",
       E.oz_broker_id(_user("broker", 7)), 7)
    check(not E.tegishli(_user("broker"), "opportunity", 1),
          "bog'lanmagan hisobga hech narsa tegishli emas")
    try:
        E.tegishli(_user("broker", 1), "yolgon", 1)
        check(False, "noma'lum obyekt turi xato berishi kerak")
    except KeyError:
        check(True, "noma'lum obyekt turi -> KeyError")


def test_db():
    head("2. Ro'yxatlar faqat o'ziniki")
    from fastapi.testclient import TestClient

    from api import main as _main
    from api.main import app

    with TestClient(app) as c:
        before = db.query_one(PUBLIC_MAX_SQL)
        d = {}
        try:
            _seed(d)
            A_USER = _user("broker", d["broker_a"])
            B_USER = _user("broker", d["broker_b"])

            def kir(u):
                app.dependency_overrides[_main.me] = lambda: u

            kir(A_USER)
            ids = [o["id"] for o in c.get("/erp/opportunities").json()]
            check(d["opp_a"] in ids and d["opp_b"] not in ids,
                  "kartalar ro'yxati — faqat o'ziniki", str(ids[:6]))
            # So'rovdagi `broker_id` bilan begonasini KO'RIB BO'LMAYDI.
            ids2 = [o["id"] for o in
                    c.get(f"/erp/opportunities?broker_id={d['broker_b']}").json()]
            check(d["opp_b"] not in ids2,
                  "so'rovdagi broker_id begonani ochmaydi", str(ids2[:6]))

            cl = [x["id"] for x in c.get("/erp/clients").json()]
            check(d["client_a"] in cl and d["client_b"] not in cl,
                  "mijozlar — faqat o'z kartalaridagi", str(cl[:6]))

            inv = [x["id"] for x in c.get("/erp/invoices").json()]
            check(d["inv_a"] in inv and d["inv_b"] not in inv,
                  "fakturalar — faqat o'ziniki", str(inv[:6]))

            head("3. Begona obyekt -> 403")
            eq("begona karta: GET -> 403",
               c.get(f"/erp/opportunities/{d['opp_b']}").status_code, 403)
            eq("o'z kartasi: GET -> 200",
               c.get(f"/erp/opportunities/{d['opp_a']}").status_code, 200)
            eq("begona karta: PUT -> 403",
               c.put(f"/erp/opportunities/{d['opp_b']}",
                     json={"priority": "high"}).status_code, 403)
            eq("begona karta: status -> 403",
               c.patch(f"/erp/opportunities/{d['opp_b']}/status",
                       json={"status": "reviewing"}).status_code, 403)
            eq("begona kartaga vazifa -> 403",
               c.post(f"/erp/opportunities/{d['opp_b']}/tasks",
                      json={"title": "ZZ"}).status_code, 403)
            eq("begona vazifani yopish -> 403",
               c.patch(f"/erp/tasks/{d['task_b']}/done").status_code, 403)
            eq("begona mijoz -> 403",
               c.get(f"/erp/clients/{d['client_b']}").status_code, 403)
            eq("begona faktura -> 403",
               c.get(f"/erp/invoices/{d['inv_b']}").status_code, 403)
            eq("o'z fakturasi -> 200",
               c.get(f"/erp/invoices/{d['inv_a']}").status_code, 200)

            # Xato matni SABABINI aytadi.
            msg = str(c.get(f"/erp/opportunities/{d['opp_b']}").json()["detail"])
            check("biriktirilmagan" in msg, "403 matni sababni aytadi", msg[:70])

            head("4. Bog'lanmagan hisob")
            kir(_user("broker"))
            eq("kartalar bo'sh", c.get("/erp/opportunities").json(), [])
            r = c.get(f"/erp/opportunities/{d['opp_a']}")
            eq("o'z kartasi ham yo'q -> 403", r.status_code, 403)
            check("bog'lanmagan" in str(r.json()["detail"]),
                  "sabab aytiladi: hisob hodimga bog'lanmagan",
                  str(r.json()["detail"])[:80])

            head("5. Menejerda cheklov yo'q")
            kir(_user("menejer"))
            ids = [o["id"] for o in c.get("/erp/opportunities").json()]
            check(d["opp_a"] in ids and d["opp_b"] in ids,
                  "menejer ikkala kartani ham ko'radi")
            eq("menejer begona kartani ochadi",
               c.get(f"/erp/opportunities/{d['opp_b']}").status_code, 200)
            cl = [x["id"] for x in c.get("/erp/clients").json()]
            check(d["client_a"] in cl and d["client_b"] in cl,
                  "menejer hamma mijozni ko'radi")

            # B hodimi o'zinikini ko'radi — filtr hodimga bog'langan,
            # "birinchi kartaga" emas.
            kir(B_USER)
            ids = [o["id"] for o in c.get("/erp/opportunities").json()]
            check(d["opp_b"] in ids and d["opp_a"] not in ids,
                  "ikkinchi hodim — o'z kartasi")

        finally:
            app.dependency_overrides.pop(_main.me, None)
            head("6. Tozalash va chegara")
            check(_cleanup(d) > 0, "sinov ma'lumoti o'chirildi")
            eq("qoldiq yo'q",
               db.scalar("SELECT count(*) FROM erp.opportunity "
                         "WHERE title LIKE %(m)s", {"m": MARK + "%"}), 0)
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
