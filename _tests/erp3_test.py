"""
ERP 3-bosqich sinovi — vazifalar, "mening ishlarim", eslatma tanlovi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp3_test.py

Tekshiriladi:
  1) SOF MANTIQ — DB'siz: sabablar ro'yxati, eslatma matnini yig'ish.
  2) VAZIFALAR: qo'shish, tahrirlash, bajarildi, o'chirish; kechikkanini
     SERVER belgilaydi.
  3) "MENING ISHLARIM": kechikkan / bugun / keyingi guruhlari, broker
     filtri, yopilgan kartalar chiqmasligi.
  4) ESLATMA TANLOVI: muddati kelganlar topiladi, belgilangач TAKROR
     chiqmaydi, muddat o'zgarsa belgi tozalanadi.
  5) YUTQAZISH SABABI: `lost` da saqlanadi, boshqa statusda tozalanadi;
     noto'g'ri kod bazaga tushmaydi.
  6) CHEGARA: `public.*` o'zgarmaydi.

Yozuvlar 'ZZTEST ' prefiksi bilan yaratiladi va oxirida TOZALANADI.
Xabar YUBORILMAYDI: sinov faqat "kimga nima ketardi" ro'yxatini tekshiradi.
"""
import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api.erp import opportunity as O  # noqa: E402
from api.erp import remind as R  # noqa: E402
from api.erp import tasks as T  # noqa: E402

PREFIX = "ZZTEST "


# ---------------------------------------------------------------------------
# Sinov uchun kimlik
# ---------------------------------------------------------------------------
# Barcha /erp/* endpointlari auth talab qiladi. Sinov haqiqiy login
# QILMAYDI: u tender-ai ishlab turishini talab qilardi va ERP sinovlarini
# ikkinchi loyihaga bog'lab qo'yardi. Buning o'rniga FastAPI ning standart
# usuli — bog'liqlikni almashtirish (`dependency_overrides`).
#
# Auth'ning O'ZI alohida sinovda tekshiriladi (`erp6_test.py`): u haqiqiy
# login qiladi va tender-ai ishlamasa SKIP bo'ladi.
TEST_USER = {"id": 0, "username": "zztest", "full_name": "ZZTEST Sinov",
             "role": "admin", "role_label": "Administrator", "broker_id": None,
             "email": None, "active": True, "last_login_at": None}


def _auth_override(app):
    from api import main as _main
    app.dependency_overrides[_main.me] = lambda: TEST_USER
    app.dependency_overrides[_main.manager] = lambda: TEST_USER

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


def _d(days):
    return (_dt.date.today() + _dt.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# 1. Sof mantiq
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq (bazasiz)")

    eq("7 ta yutqazish sababi", len(O.LOST_REASONS), 7)
    check(all(isinstance(c, str) and l for c, l in O.LOST_REASONS),
          "har sababda kod va o'zbekcha yorliq bor")
    eq("yorliq lug'ati mos", O.LOST_REASON_LABEL["price"], "Narx yuqori bo'ldi")

    eq("sana formati", R._when("2026-08-21T07:43:00+05:00"), "21.08.2026 07:43")
    eq("sanasiz vaqt", R._when("2026-08-21"), "21.08.2026")
    eq("bo'sh sana", R._when(None), "—")

    msg = R.build_message({
        "tasks": [
            {"id": 1, "title": "Kechikkan ish", "due_at": "2026-08-01",
             "overdue": True, "assignee": "A. Karimov", "opp_title": "Server xaridi",
             "client_name": "Alfa", "tender_ref": "1", "opportunity_id": 1,
             "deadline_at": None},
            {"id": 2, "title": "Bugungi ish", "due_at": "2026-08-21",
             "overdue": False, "assignee": None, "opp_title": None,
             "client_name": None, "tender_ref": "2", "opportunity_id": 2,
             "deadline_at": None},
        ],
        "deadlines": [{"id": 3, "title": "Yo'l qurilishi", "tender_ref": "3",
                       "deadline_at": "2026-08-22T10:00:00+05:00", "status": "new",
                       "start_price": None, "currency": None,
                       "broker_name": "S. Yo'ldoshev", "client_name": None}],
        "days": 1, "deadline_days": 3,
    })
    check("KECHIKKAN VAZIFALAR (1)" in msg, "kechikkanlar alohida bo'limda", msg[:80])
    check("MUDDATI KELGAN VAZIFALAR (1)" in msg, "bugungilar alohida bo'limda")
    check("TENDER MUDDATI YAQIN (1)" in msg, "deadline'lar alohida bo'limda")
    check("01.08.2026" in msg and "22.08.2026 10:00" in msg,
          "sanalar odam o'qiydigan ko'rinishda")
    check("A. Karimov" in msg and "Alfa" in msg, "mas'ul va mijoz ko'rsatilgan")
    check("<" not in msg, "matnda HTML teg yo'q (email ham, Telegram ham o'qiydi)")


# ---------------------------------------------------------------------------
# 2-6. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY = [("tender", "fetched_at"), ("company_document", "updated_at")]


def _boundary(db):
    return {t: tuple(db.query_one(
        f"SELECT count(*) AS n, max({ts}) AS mx FROM public.{t}").values())
        for t, ts in BOUNDARY}


def test_db():
    head("2. Vazifalar (haqiqiy baza)")
    from fastapi.testclient import TestClient

    from api import db
    from api.main import app

    made_opps, made_brokers, made_clients = [], [], []

    _auth_override(app)

    with TestClient(app) as c:
        before = _boundary(db)

        if not T.schema_ready():
            check(False, "schema_patch_erp_3.sql bazaga qo'llanmagan")
            return
        check(True, "3-bosqich jadvali bazada")

        # Kod va bazadagi CHECK bir xil ro'yxatmi
        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.opportunity'::regclass
              AND conname = 'opportunity_lost_reason_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in O.LOST_REASONS),
              "bazadagi CHECK koddagi 7 sababni qamraydi", cdef[:120])

        try:
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q")
                return
            tid = t["id"]

            brk = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker"}).json()
            made_brokers.append(brk["id"])
            brk2 = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker 2"}).json()
            made_brokers.append(brk2["id"])
            cl = c.post("/erp/clients", json={"name": PREFIX + "Mijoz"}).json()
            made_clients.append(cl["id"])

            opp = c.post(f"/erp/tenders/{tid}/take", json={
                "broker_id": brk["id"], "client_id": cl["id"], "priority": "medium",
                "created_by": PREFIX + "Broker"}).json()
            made_opps.append(opp["id"])
            oid = opp["id"]

            # --- CRUD ---------------------------------------------------------
            r = c.post(f"/erp/opportunities/{oid}/tasks", json={
                "title": PREFIX + "Kechikkan ish", "due_at": _d(-2),
                "created_by": PREFIX + "Broker"})
            eq("vazifa qo'shildi -> 201", r.status_code, 201)
            eq("javob — butun ro'yxat", len(r.json()), 1)
            t1 = r.json()[0]
            eq("kechikkanini SERVER belgiladi", t1["overdue"], True)
            eq("mas'ul ko'rsatilmagan", t1["assignee"], None)

            r = c.post(f"/erp/opportunities/{oid}/tasks", json={
                "title": PREFIX + "Bugungi ish", "due_at": _d(0),
                "assignee_broker_id": brk2["id"]})
            eq("ikkinchi vazifa", len(r.json()), 2)
            t2 = next(x for x in r.json() if x["title"] == PREFIX + "Bugungi ish")
            eq("mas'ul saqlandi", t2["assignee"]["id"], brk2["id"])
            eq("bugungi ish kechikkan emas", t2["overdue"], False)

            eq("nomsiz vazifa -> 400",
               c.post(f"/erp/opportunities/{oid}/tasks", json={"title": "  "}).status_code, 400)
            eq("mavjud bo'lmagan kartaga -> 404",
               c.post("/erp/opportunities/999999999/tasks",
                      json={"title": "x"}).status_code, 404)

            r = c.put(f"/erp/tasks/{t2['id']}", json={
                "title": PREFIX + "Bugungi ish (yangi nom)", "due_at": _d(3)})
            got = next(x for x in r.json() if x["id"] == t2["id"])
            eq("tahrirlandi", got["title"], PREFIX + "Bugungi ish (yangi nom)")
            eq("muddat ko'chdi", got["due_at"], _d(3))

            r = c.patch(f"/erp/tasks/{t1['id']}/done", params={"done": True})
            done = next(x for x in r.json() if x["id"] == t1["id"])
            eq("bajarildi belgilandi", done["done"], True)
            check(done["done_at"], "bajarilgan vaqti yozildi")
            eq("bajarilgan endi kechikkan emas", done["overdue"], False)
            r = c.patch(f"/erp/tasks/{t1['id']}/done", params={"done": False})
            eq("qaytarildi", next(x for x in r.json()
                                  if x["id"] == t1["id"])["done_at"], None)

            # --- "Mening ishlarim" --------------------------------------------
            head("3. Mening ishlarim")
            my = c.get("/erp/my-tasks", params={"broker_id": brk["id"], "days": 7}).json()
            ids = {x["id"] for x in my["overdue"] + my["today"] + my["later"]}
            check(t1["id"] in ids,
                  "mas'ulsiz vazifa KARTA BROKERIDA ko'rinadi", str(ids))
            eq("kechikkan guruhida", [x["id"] for x in my["overdue"]], [t1["id"]])
            check(any(x["id"] == t2["id"] for x in my["later"]),
                  "3 kundan keyingisi 'keyingi' guruhida")
            check(my["overdue"][0]["opportunity"]["title"] is not None,
                  "vazifa yonida karta konteksti bor")

            my2 = c.get("/erp/my-tasks", params={"broker_id": brk2["id"]}).json()
            check(all(x["id"] != t1["id"] for x in
                      my2["overdue"] + my2["today"] + my2["later"]),
                  "boshqa brokerning ishlari ko'rinmaydi")

            zero = c.get("/erp/my-tasks", params={"broker_id": brk["id"], "days": 0}).json()
            check(all(x["id"] != t2["id"] for x in zero["later"]),
                  "days=0 da kelasi hafta chiqmaydi")

            # --- eslatma tanlovi -----------------------------------------------
            head("4. Eslatma tanlovi (yuborilmaydi)")
            rem = c.get("/erp/reminders", params={"days": 1, "deadline_days": 0}).json()
            due_ids = {x["id"] for x in rem["tasks"]}
            check(t1["id"] in due_ids, "muddati kelgan vazifa ro'yxatda", str(due_ids))
            check(t2["id"] not in due_ids, "kelasi haftadagi vazifa ro'yxatda YO'Q")

            marked = T.mark_reminded([t1["id"]], [])
            eq("belgilandi", marked["tasks"], 1)
            rem2 = c.get("/erp/reminders", params={"days": 1, "deadline_days": 0}).json()
            check(t1["id"] not in {x["id"] for x in rem2["tasks"]},
                  "belgilangach TAKROR chiqmaydi")

            # Muddat o'zgarsa belgi tozalanadi -> eslatma qaytadan ketadi
            c.put(f"/erp/tasks/{t1['id']}", json={"title": PREFIX + "Kechikkan ish",
                                                  "due_at": _d(-1)})
            rem3 = c.get("/erp/reminders", params={"days": 1, "deadline_days": 0}).json()
            check(t1["id"] in {x["id"] for x in rem3["tasks"]},
                  "muddat o'zgargach eslatma qaytadan chiqadi")

            # Skript quruq yurishi — hech narsa yubormaydi/belgilamaydi
            res = R.run(days=1, deadline_days=0, dry_run=True)
            eq("dry-run yubormadi", res["sent"], False)
            check(res.get("text"), "xabar matni yig'ildi")
            rem4 = c.get("/erp/reminders", params={"days": 1, "deadline_days": 0}).json()
            eq("dry-run belgilamadi", len(rem4["tasks"]), len(rem3["tasks"]))

            # --- yutqazish sababi ----------------------------------------------
            head("5. Yutqazish sababi")
            meta = c.get("/erp/meta").json()
            eq("meta'da 7 sabab", len(meta["lost_reasons"]), 7)
            eq("meta: vazifalar tayyor", meta["tasks_ready"], True)

            r = c.patch(f"/erp/opportunities/{oid}/status",
                        json={"status": "lost", "lost_reason": "price",
                              "changed_by": PREFIX + "Broker"})
            eq("lost -> 200", r.status_code, 200)
            eq("sabab saqlandi", r.json()["lost_reason"], "price")
            eq("sababni to'g'rilash (status o'zgarmaydi)",
               c.patch(f"/erp/opportunities/{oid}/status",
                       json={"status": "lost", "lost_reason": "deadline"}
                       ).json()["lost_reason"], "deadline")
            eq("noto'g'ri sabab kodi -> 400",
               c.patch(f"/erp/opportunities/{oid}/status",
                       json={"status": "lost", "lost_reason": "xxx"}).status_code, 400)
            eq("noto'g'ri kod bazaga tushmadi",
               c.get(f"/erp/opportunities/{oid}").json()["lost_reason"], "deadline")

            r = c.patch(f"/erp/opportunities/{oid}/status",
                        json={"status": "preparing", "note": PREFIX + "qayta ochildi"})
            eq("qayta ochilganda sabab tozalandi", r.json()["lost_reason"], None)

            # Yopilgan kartaning vazifasi eslatilmaydi
            c.patch(f"/erp/opportunities/{oid}/status",
                    json={"status": "won", "changed_by": PREFIX + "Broker"})
            rem5 = c.get("/erp/reminders", params={"days": 30, "deadline_days": 0}).json()
            check(all(x["opportunity_id"] != oid for x in rem5["tasks"]),
                  "yopilgan kartaning vazifasi eslatilmaydi")
            my3 = c.get("/erp/my-tasks", params={"broker_id": brk["id"], "days": 30}).json()
            eq("yopilgan karta 'mening ishlarim'da ham yo'q", my3["total"], 0)

            # --- o'chirish ------------------------------------------------------
            r = c.delete(f"/erp/tasks/{t2['id']}")
            eq("vazifa o'chirildi", [x["id"] for x in r.json()], [t1["id"]])
            eq("o'chirilganini qayta o'chirish -> 404",
               c.delete(f"/erp/tasks/{t2['id']}").status_code, 404)

        finally:
            head("6. Tozalash va chegara")
            for oid_ in made_opps:
                db.execute_returning("DELETE FROM erp.opportunity_task "
                                     "WHERE opportunity_id=%(id)s RETURNING id", {"id": oid_})
                db.execute_returning("DELETE FROM erp.opportunity_history "
                                     "WHERE opportunity_id=%(id)s RETURNING id", {"id": oid_})
                db.execute_returning("DELETE FROM erp.opportunity WHERE id=%(id)s "
                                     "RETURNING id", {"id": oid_})
            db.execute_returning("DELETE FROM erp.broker WHERE full_name LIKE %(p)s "
                                 "RETURNING id", {"p": PREFIX + "%"})
            db.execute_returning("DELETE FROM erp.client_company WHERE name LIKE %(p)s "
                                 "RETURNING id", {"p": PREFIX + "%"})
            left = db.scalar("SELECT count(*) FROM erp.opportunity_task "
                             "WHERE title LIKE %(p)s", {"p": PREFIX + "%"})
            eq("sinov vazifalari tozalandi", left, 0)

            after = _boundary(db)
            for table, _ in BOUNDARY:
                eq(f"public.{table} o'zgarmadi", after[table], before[table])


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: baza sinovi bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
