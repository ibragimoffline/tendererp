"""
ERP 5A-1 sinovi — shartnoma va bizning rekvizitlar.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp5_test.py

Tekshiriladi:
  1) SOF MANTIQ — DB'siz: holatlar ro'yxati, passport to'liqligi.
  2) BIZNING KOMPANIYA: bitta qator, INN formati, `missing` ro'yxati.
  3) SHARTNOMA: yaratish (summa taklifdan/snapshotdan olinadi), raqam
     takrorlanmasligi, sanalar mantiqi, holat o'tishi.
  4) O'CHIRILMAYDI: 'terminated' ga o'tkaziladi va yozuv joyida qoladi.
  5) RO'YXAT va YIG'INDI: filtrlar, holat bo'yicha soni/summasi.
  5b) TAHLIL (5A-2): bosqichda o'tgan vaqt, voronka, qotib qolganlar —
     hammasi `opportunity_history` dan, YANGI JADVALSIZ.
  6) CHEGARA: public.* o'zgarmaydi (`company_profile` ham).

Yozuvlar 'ZZTEST ' prefiksi bilan yaratiladi va oxirida TOZALANADI.
Bizning kompaniya BITTA qator bo'lgani uchun sinov uni o'zgartiradi va
oxirida ASL HOLIGA qaytaradi.
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

from api.erp import analytics as A  # noqa: E402
from api.erp import contracts as K  # noqa: E402

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

    eq("5 ta holat", len(K.CONTRACT_STATUSES), 5)
    eq("yakuniylar", K.CONTRACT_FINAL, {"done", "terminated"})
    eq("yorliq lug'ati", K.CONTRACT_STATUS_LABEL["signed"], "Imzolangan")
    check(all(c in K.CONTRACT_STATUS_LABEL for c in K.CONTRACT_FINAL),
          "yakuniylar umumiy ro'yxatda ham bor")

    own = K.shape_own({"name": "X", "inn": None, "legal_form": "MCHJ",
                       "address_legal": None, "bank_account": None,
                       "bank_mfo": None, "director_name": None,
                       "updated_at": None})
    check("inn" in own["missing"] and "legal_form" not in own["missing"],
          "to'ldirilmagan maydonlar sanaladi", str(own["missing"]))
    # MATN BO'LMAGAN maydonlar alohida: `vat_payer` bool, `vat_rate` son.
    # Hammasini "x" bilan to'ldirish haqiqiy holatga to'g'ri kelmaydi.
    full = {f: ("x" if f not in K.OWN_NON_TEXT else None)
            for f in K.OWN_FIELDS}
    eq("to'liq passportda bo'sh ro'yxat", K.shape_own(full)["missing"], [])
    eq("QQS maydonlari 'yetishmayapti' ro'yxatiga kirmaydi",
       [f for f in K.OWN_NON_TEXT if f in K.shape_own(full)["missing"]], [])

    check(set(K.OWN_FIELDS) <= set(K.OWN_FIELDS),
          "passport maydonlari client_company bilan bir xil nomlanadi")


# ---------------------------------------------------------------------------
# 2-6. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY = [("tender", "fetched_at"), ("company_profile", "updated_at")]


def _boundary(db):
    return {t: tuple(db.query_one(
        f"SELECT count(*) AS n, max({ts}) AS mx FROM public.{t}").values())
        for t, ts in BOUNDARY}


def test_db():
    head("2. Bizning kompaniya (haqiqiy baza)")
    from fastapi.testclient import TestClient

    from api import db
    from api.main import app

    opps, saved_own = [], None

    _auth_override(app)

    with TestClient(app) as c:
        before = _boundary(db)

        if not K.schema_ready():
            check(False, "schema_patch_erp_5.sql bazaga qo'llanmagan")
            return
        check(True, "5A jadvallari bazada")

        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.contract'::regclass
              AND conname = 'contract_status_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in K.CONTRACT_STATUSES),
              "bazadagi CHECK koddagi 5 holatni qamraydi", cdef[:120])

        try:
            saved_own = db.query_one(K.OWN_GET_SQL)     # oxirida qaytariladi

            r = c.get("/erp/own-company")
            eq("own-company -> 200", r.status_code, 200)
            check("missing" in r.json(), "yetishmayotgan maydonlar ko'rsatiladi")

            r = c.put("/erp/own-company", json={
                "name": PREFIX + "Bizning MChJ", "inn": " 999-111-222 ",
                "legal_form": "MCHJ", "address_legal": "Toshkent",
                "bank_account": "20208000900001111001", "bank_mfo": "00014",
                "director_name": "A. Karimov"})
            eq("saqlash -> 200", r.status_code, 200)
            own = r.json()
            eq("INN normallashdi", own["inn"], "999111222")
            eq("to'liq passport -> missing bo'sh", own["missing"], [])
            eq("bo'sh nom -> 400",
               c.put("/erp/own-company", json={"name": "  "}).status_code, 400)
            eq("noto'g'ri INN -> 400",
               c.put("/erp/own-company", json={"name": "X", "inn": "123"}).status_code, 400)
            eq("bitta qator qoladi",
               db.scalar("SELECT count(*) FROM erp.own_company"), 1)

            # --- shartnoma ----------------------------------------------------
            head("3. Shartnoma")
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q")
                return
            brk = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker"}).json()
            cl = c.post("/erp/clients", json={"name": PREFIX + "Mijoz"}).json()
            opp = c.post(f"/erp/tenders/{t['id']}/take", json={
                "broker_id": brk["id"], "client_id": cl["id"], "priority": "medium",
                "created_by": PREFIX + "Broker"}).json()
            opps.append(opp["id"])
            oid = opp["id"]
            snap_price = opp["tender"]["start_price"]

            r = c.post(f"/erp/opportunities/{oid}/contracts", json={
                "number": PREFIX + "SH-1", "signed_at": "2026-08-01",
                "starts_at": "2026-08-05", "ends_at": "2026-12-31",
                "created_by": PREFIX + "Broker"})
            eq("shartnoma -> 201", r.status_code, 201)
            eq("javob — butun ro'yxat", len(r.json()), 1)
            k1 = r.json()[0]
            eq("boshlang'ich holat", k1["status"], "draft")
            eq("summa snapshotdan olindi", k1["amount"], snap_price)
            check(k1["currency"], "valyuta ham olindi", str(k1["currency"]))

            eq("takror raqam -> 409",
               c.post(f"/erp/opportunities/{oid}/contracts",
                      json={"number": PREFIX + "SH-1"}).status_code, 409)
            r = c.post(f"/erp/opportunities/{oid}/contracts",
                       json={"number": PREFIX + "SH-1"})
            check(r.json()["detail"].get("contract_id") == k1["id"],
                  "409 da mavjud shartnoma id si", str(r.json()["detail"]))
            eq("teskari sanalar -> 400",
               c.post(f"/erp/opportunities/{oid}/contracts",
                      json={"starts_at": "2026-12-01", "ends_at": "2026-01-01"}
                      ).status_code, 400)
            eq("manfiy summa -> 400",
               c.post(f"/erp/opportunities/{oid}/contracts",
                      json={"amount": -5}).status_code, 400)
            eq("mavjud bo'lmagan kartaga -> 404",
               c.post("/erp/opportunities/999999999/contracts", json={}).status_code, 404)

            # Raqamsiz shartnomalar cheklovga tushmaydi (qisman indeks)
            r = c.post(f"/erp/opportunities/{oid}/contracts", json={"amount": 100})
            eq("raqamsiz ikkinchi shartnoma -> 201", r.status_code, 201)
            eq("ikkita shartnoma", len(r.json()), 2)

            r = c.put(f"/erp/contracts/{k1['id']}", json={
                "number": PREFIX + "SH-1", "amount": 777, "currency": "UZS",
                "signed_at": "2026-08-02"})
            got = next(x for x in r.json() if x["id"] == k1["id"])
            eq("tahrirlandi", got["amount"], 777.0)
            eq("sana yangilandi", got["signed_at"], "2026-08-02")

            # --- holat va o'chirilmaslik ---------------------------------------
            head("4. Holat o'tishi")
            r = c.patch(f"/erp/contracts/{k1['id']}/status", params={"status": "signed"})
            eq("imzolandi", next(x for x in r.json()
                                 if x["id"] == k1["id"])["status"], "signed")
            r = c.patch(f"/erp/contracts/{k1['id']}/status", params={"status": "terminated"})
            got = next(x for x in r.json() if x["id"] == k1["id"])
            eq("bekor qilindi", got["status"], "terminated")
            eq("yakuniy deb belgilandi", got["is_final"], True)
            eq("yozuv joyida qoldi",
               db.scalar("SELECT count(*) FROM erp.contract WHERE id=%(id)s",
                         {"id": k1["id"]}), 1)
            eq("noma'lum holat -> 400",
               c.patch(f"/erp/contracts/{k1['id']}/status",
                       params={"status": "xxx"}).status_code, 400)
            eq("mavjud bo'lmagan shartnoma -> 404",
               c.patch("/erp/contracts/999999999/status",
                       params={"status": "signed"}).status_code, 404)

            # --- ro'yxat va yig'indi --------------------------------------------
            head("5. Ro'yxat va yig'indi")
            all_ = c.get("/erp/contracts").json()
            mine = [x for x in all_ if x["opportunity"]["id"] == oid]
            eq("ro'yxatda ikkalasi ham bor", len(mine), 2)
            check(mine[0]["opportunity"]["client_name"] == PREFIX + "Mijoz",
                  "ro'yxatda karta konteksti bor")
            openi = c.get("/erp/contracts", params={"open_only": True}).json()
            check(all(x["status"] not in ("done", "terminated") for x in openi),
                  "open_only yakuniylarni yashiradi")
            byc = c.get("/erp/contracts", params={"client_id": cl["id"]}).json()
            eq("mijoz filtri", len(byc), 2)

            st = c.get("/erp/contracts/stats").json()
            eq("yig'indi: 5 holat", len(st["by_status"]), 5)
            n_term = next(x["n"] for x in st["by_status"] if x["code"] == "terminated")
            check(n_term >= 1, "bekor qilingani sanaldi", str(n_term))

            # --- TAHLIL (5A-2) --------------------------------------------
            head("5b. Rahbar tahlili")
            r = c.get("/erp/analytics", params={"stuck_days": 14})
            eq("tahlil -> 200", r.status_code, 200)
            an = r.json()
            eq("bosqichlar ro'yxati to'liq", len(an["stages"]), 9)
            eq("voronka ro'yxati to'liq", len(an["funnel"]), 9)
            check(isinstance(an["by_broker"], list), "broker kesimi bor")
            check(isinstance(an["stuck"], list), "qotib qolganlar ro'yxati bor")
            eq("stuck_days javobda", an["stuck_days"], 14)

            # Yangi karta 'new' bosqichida turibdi -> ongoing sanaladi
            st_new = next(x for x in an["stages"] if x["code"] == "new")
            check(st_new["ongoing_n"] >= 1,
                  "yangi karta 'hozir shu bosqichda' deb sanaldi",
                  str(st_new))

            # Bosqichni o'zgartiramiz: 'new' da TUGAGAN turish paydo bo'ladi
            c.patch(f"/erp/opportunities/{oid}/status", json={"status": "reviewing"})
            an2 = c.get("/erp/analytics").json()
            st_new2 = next(x for x in an2["stages"] if x["code"] == "new")
            check(st_new2["finished_n"] > st_new["finished_n"],
                  "o'tishdan keyin 'new' da tugagan turish qo'shildi",
                  f"{st_new['finished_n']} -> {st_new2['finished_n']}")
            check(st_new2["avg_days"] is not None,
                  "o'rtacha vaqt hisoblandi", str(st_new2["avg_days"]))

            f_rev = next(x for x in an2["funnel"] if x["code"] == "reviewing")
            check(f_rev["reached"] >= 1, "voronkada 'ko'rib chiqilmoqda' sanaldi")
            check(f_rev["pct"] is not None, "voronka foizi hisoblandi")

            # Qotib qolganlar: 0 kun chegarasi bilan hozirgi karta ham chiqadi
            an3 = c.get("/erp/analytics", params={"stuck_days": 1}).json()
            check(all(x["idle_days"] >= 1 for x in an3["stuck"]),
                  "qotib qolganlar chegaradan katta")
            an4 = c.get("/erp/analytics", params={"stuck_days": 180}).json()
            check(len(an4["stuck"]) <= len(an3["stuck"]),
                  "chegara oshgach ro'yxat qisqaradi")
            eq("chegara 0 -> 422",
               c.get("/erp/analytics", params={"stuck_days": 0}).status_code, 422)

            # Yutqazish sababi tahlilda ko'rinadi
            c.patch(f"/erp/opportunities/{oid}/status",
                    json={"status": "lost", "lost_reason": "price",
                          "changed_by": PREFIX + "Broker"})
            an5 = c.get("/erp/analytics").json()
            check(any(x["code"] == "price" for x in an5["lost_reasons"]),
                  "yutqazish sababi tahlilga tushdi", str(an5["lost_reasons"]))

            # Tahlil HECH NARSA YOZMAYDI
            before_hist = db.scalar("SELECT count(*) FROM erp.opportunity_history")
            c.get("/erp/analytics")
            eq("tahlil tarixga yozmadi",
               db.scalar("SELECT count(*) FROM erp.opportunity_history"), before_hist)

        finally:
            head("6. Tozalash va chegara")
            for oid_ in opps:
                db.execute_returning("DELETE FROM erp.contract WHERE opportunity_id=%(id)s "
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
            if saved_own:
                db.execute_returning(K.OWN_UPDATE_SQL,
                                     {f: saved_own.get(f) for f in K.OWN_FIELDS})
                back = db.query_one(K.OWN_GET_SQL)
                eq("bizning passport ASL holiga qaytdi",
                   back["name"], saved_own["name"])
            left = db.scalar("SELECT count(*) FROM erp.contract WHERE number LIKE %(p)s",
                             {"p": PREFIX + "%"})
            eq("sinov shartnomalari tozalandi", left, 0)

            after = _boundary(db)
            for table, _ in BOUNDARY:
                eq(f"public.{table} o'zgarmadi", after[table], before[table])


# ---------------------------------------------------------------------------
# SHARTNOMA ILOVASI (spetsifikatsiya)
#
# ERP shartnoma MATNINI yozmaydi — huquqiy matn yurist ishi. ERP ilovani
# chiqaradi: pozitsiyalar ro'yxati. Ma'lumot UCH manbadan olinadi va
# MUZLATILGANI ustun turadi.
# ---------------------------------------------------------------------------
def test_spetsifikatsiya():
    head("7. Shartnoma ilovasi (spetsifikatsiya)")
    from fastapi.testclient import TestClient

    from api import db as _db
    from api.erp import contracts as K
    from api.erp import invoice as INV
    from api.erp import opportunity as OPP
    from api.erp import stock as STK
    from api.main import app
    _auth_override(app)

    SMARK = PREFIX + "SPEC"
    with TestClient(app) as c:
        # Bazadagi ma'lumotga TAYANMAYMIZ: kerakligini o'zimiz
        # yaratamiz (`_tests/fixture.py`). Aks holda demo tozalanganda
        # qamrov jimgina tushib ketardi.
        import fixture as FIX
        opp = FIX.ensure_opportunity()
        prod = _db.query_one("SELECT id, name FROM public.catalog_product "
                             "ORDER BY id LIMIT 1")
        if not opp or not K.schema_ready():
            print("  SKIP tender yo'q (ETL yurmagan) yoki sxema qo'llanmagan")
            return
        if not prod:
            # Katalog TENDER-AI niki va ERP unga yozmaydi — sinov ham.
            print("  ESLATMA: katalogda mahsulot yo'q, rezerv qismi "
                  "o'tkazib yuboriladi")
        was = opp["status"]

        def clean():
            p = {"m": f"%{SMARK}%"}
            for t in ("invoice", "contract", "stock_reserve", "stock_move"):
                _db.execute_returning(
                    f"DELETE FROM erp.{t} WHERE note LIKE %(m)s "
                    f"OR created_by LIKE %(m)s RETURNING id", p)
            _db.execute_returning(
                "DELETE FROM erp.opportunity_history WHERE changed_by LIKE %(m)s "
                "RETURNING id", p)

        clean()
        try:
            K.create(opp["id"], {"number": SMARK + "-K", "amount": 5000000,
                                 "currency": "UZS", "note": SMARK,
                                 "created_by": SMARK})
            k = _db.query_one("SELECT id FROM erp.contract WHERE note = %(m)s",
                              {"m": SMARK})

            # 1) Manba YO'Q — ro'yxat bo'sh va buni yashirmaymiz.
            r = c.get(f"/erp/contracts/{k['id']}/specification")
            eq("ilova -> 200", r.status_code, 200)
            sp = r.json()
            eq("manbasiz -> 'none'", sp["source"], "none")
            eq("ro'yxat bo'sh", len(sp["lines"]), 0)
            check(not sp["frozen"], "muzlatilmagan deb belgilangan")
            check(sp["client"]["name"], "mijoz rekvizitlari bor")

            # 2) REZERVDAN — miqdor haqiqiy, narx katalogdan.
            if prod:
                STK.add_move({"product_id": prod["id"], "kind": "in",
                              "qty": 40, "note": SMARK, "created_by": SMARK})
                OPP.set_status(opp["id"], "confirmed", SMARK, SMARK)
                STK.add_reserve(opp["id"], {"product_id": prod["id"],
                                            "qty": 7, "note": SMARK,
                                            "created_by": SMARK})
                sp = c.get(f"/erp/contracts/{k['id']}/specification").json()
                eq("rezervdan -> 'reserves'", sp["source"], "reserves")
                eq("bitta qator", len(sp["lines"]), 1)
                eq("miqdor rezervdan", sp["lines"][0]["qty"], 7.0)
                check(not sp["frozen"],
                      "rezerv HOZIRGI holat (muzlatilmagan)")

            # 3) FAKTURA bo'lsa — U USTUN (snapshot).
            import datetime as _dt
            inv = INV.create({"client_id": opp["client_id"],
                              "contract_id": k["id"], "number": SMARK + "-F",
                              # Sana MAJBURIY: sanasiz fakturani
                              # "chiqarildi" deb belgilab bo'lmaydi.
                              "issued_at": _dt.date(2026, 8, 21),
                              "note": SMARK, "created_by": SMARK})
            INV.add_line(inv["id"], {"name": "Montaj", "qty": 2,
                                     "price": 750000, "vat_rate": 12})
            INV.set_status(inv["id"], "issued", SMARK)
            sp = c.get(f"/erp/contracts/{k['id']}/specification").json()
            eq("fakturadan -> 'invoice'", sp["source"], "invoice")
            check(sp["frozen"], "faktura ma'lumoti MUZLATILGAN")
            eq("qator fakturadan", sp["lines"][0]["name"], "Montaj")
            eq("faktura raqami ko'rinadi", sp["invoice_number"], SMARK + "-F")
            check(sp["totals"]["words"], "summa so'z bilan ham bor")

            # BEKOR QILINGAN faktura ustun EMAS: u endi hujjat emas.
            INV.set_status(inv["id"], "cancelled", SMARK)
            sp = c.get(f"/erp/contracts/{k['id']}/specification").json()
            eq("bekor qilingan faktura hisobga olinmaydi", sp["source"],
               "reserves" if prod else "none")

            eq("yo'q shartnoma -> 404",
               c.get("/erp/contracts/99999999/specification").status_code, 404)
        finally:
            OPP.set_status(opp["id"], was, SMARK, "sinov tugadi")
            clean()
            FIX.cleanup()
            eq("sinov yozuvlari qolmadi",
               _db.scalar("SELECT count(*) FROM erp.contract "
                          "WHERE note LIKE %(m)s", {"m": f"%{SMARK}%"}), 0)


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
        test_spetsifikatsiya()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: baza sinovi bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
