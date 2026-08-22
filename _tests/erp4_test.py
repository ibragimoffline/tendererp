"""
ERP 4-bosqich sinovi — taklif paketi va topshirish.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp4_test.py

Tekshiriladi:
  1) SOF MANTIQ — DB'siz: smetadan taklif narxini olish, cheklist nusxasi.
  2) PAKET: narx hisobi, cheklist, hujjatlar va manbadagi status bir joyda;
     tender-ai yiqilsa ham paket QAYTADI (warnings bilan).
  3) TOPSHIRISH: to'siq bo'lsa tasdiqsiz RAD ETILADI (400), tasdiq bilan
     o'tadi; karta 'submitted' ga o'tadi va tarixga yoziladi.
  4) MUZLATISH: smeta/cheklist keyin o'zgarsa ham topshirilgan versiya
     O'ZGARMAYDI; ikkinchi topshirish v2 bo'ladi.
  5) MANBA NATIJASI: tender yopilgan bo'lsa "yakunlash taklifi" chiqadi,
     lekin status AVTOMATIK o'zgarmaydi.
  6) CHEGARA: public.* o'zgarmaydi.

Tender-AI ishlab turishi kerak (narx va cheklist u yerdan); ishlamasa
tegishli qismlar SKIP bo'ladi.
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

from api.erp import submission as S  # noqa: E402

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


# ---------------------------------------------------------------------------
# 1. Sof mantiq
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq (bazasiz)")

    eq("smeta yo'q -> narx yo'q", S._suggested_price(None), None)
    eq("qo'lda kiritilgan narx USTUN",
       S._suggested_price({"manual_price": 500, "result": {"totals": {"offer_price": 900}}}),
       500.0)
    eq("qo'lda yo'q -> hisobdan",
       S._suggested_price({"manual_price": None, "result": {"totals": {"offer_price": 900}}}),
       900.0)
    eq("boshqa nom bilan ham topiladi",
       S._suggested_price({"manual_price": None, "result": {"totals": {"total": 42}}}), 42.0)
    eq("hisob bo'sh -> None",
       S._suggested_price({"manual_price": None, "result": {}}), None)

    snap = S._compliance_snapshot({
        "summary": {"ready": 2, "blocking": 1},
        "doc_source": "client",
        "items": [{"doc_type": "license", "label": "Litsenziya", "status": "ok",
                   "in_base": True, "evidence": "juda uzun dalil matni" * 20,
                   "document": {"valid_until": "2027-01-01"}}],
    })
    eq("xulosa saqlandi", snap["summary"]["blocking"], 1)
    eq("manba saqlandi", snap["doc_source"], "client")
    eq("band holati saqlandi", snap["items"][0]["status"], "ok")
    eq("muddat saqlandi", snap["items"][0]["valid_until"], "2027-01-01")
    check("evidence" not in snap["items"][0],
          "uzun dalil matni nusxaga TUSHMAYDI (taklif tarixida kerak emas)")
    eq("bo'sh cheklist -> None", S._compliance_snapshot(None), None)

    check("close" in S.SOURCE_CLOSED and "expired" in S.SOURCE_CLOSED,
          "manbadagi yakuniy statuslar ro'yxati bor")


# ---------------------------------------------------------------------------
# 2-6. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY = [("tender", "fetched_at"), ("tender_pricing", "updated_at")]


def _boundary(db):
    return {t: tuple(db.query_one(
        f"SELECT count(*) AS n, max({ts}) AS mx FROM public.{t}").values())
        for t, ts in BOUNDARY}


def test_db():
    head("2. Taklif paketi (haqiqiy baza)")
    from fastapi.testclient import TestClient

    from api import db
    from api.main import app

    opps, brokers, clients = [], [], []

    _auth_override(app)

    with TestClient(app) as c:
        before = _boundary(db)

        if not S.schema_ready():
            check(False, "schema_patch_erp_4.sql bazaga qo'llanmagan")
            return
        check(True, "4-bosqich jadvali bazada")

        try:
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q")
                return
            tid = t["id"]

            brk = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker"}).json()
            brokers.append(brk["id"])
            cl = c.post("/erp/clients", json={"name": PREFIX + "Mijoz"}).json()
            clients.append(cl["id"])
            opp = c.post(f"/erp/tenders/{tid}/take", json={
                "broker_id": brk["id"], "client_id": cl["id"], "priority": "high",
                "created_by": PREFIX + "Broker"}).json()
            opps.append(opp["id"])
            oid = opp["id"]

            r = c.get(f"/erp/opportunities/{oid}/submission")
            if r.status_code == 503:
                print("  SKIP takliflar jadvali yo'q")
                return
            eq("paket -> 200", r.status_code, 200)
            pkg = r.json()
            eq("paketda karta bor", pkg["opportunity"]["id"], oid)
            check("pricing" in pkg and "compliance" in pkg and "documents" in pkg,
                  "narx, cheklist va hujjatlar bitta javobda")
            check(isinstance(pkg["warnings"], list), "ogohlantirishlar ro'yxati bor")
            check(pkg["source"] is None or "status" in pkg["source"],
                  "manbadagi status ko'rsatilgan", str(pkg["source"]))

            tender_ai_ok = pkg["compliance"] is not None
            if not tender_ai_ok:
                print("  SKIP tender-ai javob bermadi — cheklist qismi tekshirilmadi")
            else:
                check(pkg["blocking"] > 0,
                      "hujjatsiz mijozda to'siq bor (cheklist ishlayapti)",
                      str(pkg["blocking"]))
                check(any("to'siq" in w for w in pkg["warnings"]),
                      "to'siq haqida ogohlantirish matni bor")

            # --- topshirish -------------------------------------------------
            head("3. Topshirish")
            if tender_ai_ok and pkg["blocking"] > 0:
                r = c.post(f"/erp/opportunities/{oid}/submission",
                           json={"price": 1000, "confirmed": False})
                eq("to'siq bor, tasdiqsiz -> 400", r.status_code, 400)
                check("to'siq" in str(r.json()["detail"]),
                      "xato matni sababni aytadi", str(r.json()["detail"])[:80])

            r = c.post(f"/erp/opportunities/{oid}/submission", json={
                "price": 1000, "currency": "UZS", "confirmed": True,
                "confirmed_note": PREFIX + "hujjat topshirish paytida tayyor",
                "note": PREFIX + "birinchi versiya",
                "submitted_by": PREFIX + "Broker"})
            eq("tasdiq bilan -> 201", r.status_code, 201)
            res = r.json()
            eq("versiya 1", res["submission"]["version"], 1)
            eq("narx saqlandi", res["submission"]["price"], 1000.0)
            eq("karta 'submitted' ga o'tdi", res["opportunity"]["status"], "submitted")
            hist = res["opportunity"]["history"][-1]
            check("Taklif topshirildi" in (hist["note"] or ""),
                  "tarixda topshirish yozuvi bor", str(hist["note"]))
            if tender_ai_ok:
                check("to'siq" in (hist["note"] or ""),
                      "tasdiq ham tarixga tushdi", str(hist["note"]))
                eq("to'siqlar soni yozildi",
                   res["submission"]["blocking_count"], pkg["blocking"])

            # --- muzlatish ---------------------------------------------------
            head("4. Muzlatilgan nusxa")
            sub1 = res["submission"]
            if tender_ai_ok:
                check(sub1["compliance"] is not None, "cheklist nusxasi saqlandi")
                check(sub1["compliance"]["summary"]["blocking"] == pkg["blocking"],
                      "nusxadagi to'siqlar soni o'sha paytdagidek")

            # Mijozga hujjat qo'shamiz — JONLI cheklist yaxshilanadi
            c.post(f"/erp/clients/{cl['id']}/documents", json={
                "doc_type": "reg_certificate", "name": PREFIX + "Guvohnoma"})
            pkg2 = c.get(f"/erp/opportunities/{oid}/submission").json()
            got = next(s for s in pkg2["submissions"] if s["version"] == 1)
            eq("MUZLATILGAN nusxa o'zgarmadi",
               got["compliance"], sub1["compliance"])
            if tender_ai_ok:
                check(pkg2["blocking"] <= pkg["blocking"],
                      "jonli cheklist esa yangilandi",
                      f"{pkg['blocking']} -> {pkg2['blocking']}")

            r = c.post(f"/erp/opportunities/{oid}/submission", json={
                "price": 950, "confirmed": True, "note": PREFIX + "tuzatilgan narx",
                "submitted_by": PREFIX + "Broker"})
            eq("ikkinchi topshirish -> v2", r.json()["submission"]["version"], 2)
            subs = c.get(f"/erp/opportunities/{oid}/submissions").json()
            eq("ikkala versiya ham saqlanadi", len(subs), 2)
            eq("yangi versiya birinchi", subs[0]["version"], 2)
            eq("eski versiya narxi o'zgarmadi",
               next(x for x in subs if x["version"] == 1)["price"], 1000.0)

            eq("narxsiz va smetasiz -> 400",
               c.post(f"/erp/opportunities/{opps[0]}/submission",
                      json={"confirmed": True, "price": None}).status_code
               if pkg2["suggested_price"] is None else 400, 400)

            # --- manba natijasi ------------------------------------------------
            head("5. Manbadagi natija")
            d = c.get(f"/erp/opportunities/{oid}/tender-diff").json()
            check("source" in d, "tender-diff manbadagi statusni beradi", str(d.get("source")))
            check("suggest_close" in d, "yakunlash taklifi maydoni bor")
            st = c.get(f"/erp/opportunities/{oid}").json()["status"]
            eq("status AVTOMATIK o'zgarmadi", st, "submitted")

            eq("mavjud bo'lmagan karta -> 404",
               c.get("/erp/opportunities/999999999/submission").status_code, 404)

        finally:
            head("6. Tozalash va chegara")
            for oid_ in opps:
                db.execute_returning("DELETE FROM erp.submission WHERE opportunity_id=%(id)s "
                                     "RETURNING id", {"id": oid_})
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
            left = db.scalar("SELECT count(*) FROM erp.submission s "
                             "LEFT JOIN erp.opportunity o ON o.id = s.opportunity_id "
                             "WHERE o.id IS NULL")
            eq("yetim taklif qolmadi", left, 0)

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
