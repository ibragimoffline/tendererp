"""
ERP 1-bosqich sinovi — "Ishga olish" + Opportunity pipeline.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp_test.py

Uch qism:
  1) SOF MANTIQ — DB'siz: statuslar/ustuvorliklar ro'yxati, shape(), _num/_iso.
  2) HAQIQIY BAZA — TestClient orqali endpointlar. Sinov yozuvlari 'ZZTEST '
     prefiksi bilan yaratiladi va oxirida TOZALANADI (tozalanganini ham
     tekshiradi). Ishga olish uchun bazadagi HAQIQIY tender kerak; baza bo'sh
     bo'lsa shu qism SKIP bo'ladi, sinov yiqilmaydi.
  3) CHEGARA — public.* jadvallari sinovdan oldin va keyin AYNAN bir xil
     (ERP hech narsa yozmagan). Bu 1-bosqichning asosiy va'dasi.

Uvicorn ISHGA TUSHIRILMAYDI — TestClient ilovani to'g'ridan-to'g'ri chaqiradi.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows konsoli cp1251/cp866 da ochiladi, xabarlar esa o'zbekcha (') va
# kirill bo'lishi mumkin — chiqishni utf-8 ga o'tkazamiz.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api.erp import opportunity as O  # noqa: E402

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
# 1. SOF MANTIQ — baza kerak emas
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq (bazasiz)")

    eq("9 ta status", len(O.STATUSES), 9)
    eq("3 ta ustuvorlik", len(O.PRIORITIES), 3)
    eq("yakuniylar", O.FINAL, {"won", "lost", "rejected"})
    check(all(c in O.STATUS_LABEL for c in O.FINAL),
          "yakuniy statuslar umumiy ro'yxatda ham bor")
    check(len(O.STATUS_LABEL) == len(O.STATUSES), "status kodlari takrorlanmaydi")

    eq("_num: Decimal -> float", O._num(3), 3.0)
    eq("_num: None -> None", O._num(None), None)
    eq("_iso: None -> None", O._iso(None), None)

    # shape() — javob shakli. Baza qatorini qo'lda yasaymiz.
    import datetime as dt
    row = {
        "id": 1, "tender_id": 7886728, "source_platform": "xt-xarid",
        "tender_ref": "7886728", "customer_name": "AGROBANK", "title": "Server",
        "start_price": 100, "currency": "UZS",
        "deadline_at": dt.datetime(2026, 7, 31, 18, 51),
        "region_name": "Toshkent", "source_url": "https://x/1",
        "broker_id": None, "broker_name": None, "client_id": None, "client_name": None,
        "priority": "high", "win_probability": 60, "note": None,
        "next_task": None, "next_task_at": None,
        "status": "won", "status_changed_at": dt.datetime(2026, 7, 1),
        "closed_at": dt.datetime(2026, 7, 1), "created_by": "A. Karimov",
        "created_at": dt.datetime(2026, 6, 1), "updated_at": dt.datetime(2026, 6, 1),
    }
    s = O.shape(row)
    eq("shape: snapshot alohida 'tender' obyektida", s["tender"]["title"], "Server")
    eq("shape: start_price float", s["tender"]["start_price"], 100.0)
    eq("shape: deadline ISO", s["tender"]["deadline_at"], "2026-07-31T18:51:00")
    eq("shape: status yorlig'i", s["status_label"], "Yutildi")
    eq("shape: is_final", s["is_final"], True)
    eq("shape: broker yo'q -> None", s["broker"], None)
    eq("shape: ustuvorlik yorlig'i", s["priority_label"], "Yuqori")

    # Xato turi FastAPI'dan mustaqil: kod va qo'shimcha ma'lumot o'zida.
    e = O.ErpError("takror", 409, opportunity_id=12)
    eq("ErpError kodi", e.code, 409)
    eq("ErpError qo'shimchasi", e.extra, {"opportunity_id": 12})

    for bad in ({"priority": "xxx"}, {"priority": None}):
        try:
            O._check_fields(bad)
            check(False, f"noto'g'ri ustuvorlik rad etilishi kerak: {bad}")
        except O.ErpError as err:
            eq(f"ustuvorlik {bad['priority']!r} -> 400", err.code, 400)
    try:
        O._check_fields({"priority": "low", "win_probability": 140})
        check(False, "140% ehtimol rad etilishi kerak")
    except O.ErpError as err:
        eq("win_probability 140 -> 400", err.code, 400)


# ---------------------------------------------------------------------------
# Chegara o'lchagichi — public.* o'zgarmaganini isbotlash uchun
# ---------------------------------------------------------------------------
# tender va tender_document da updated_at ustuni YO'Q (ETL yozuvlari
# fetched_at bilan belgilanadi), shuning uchun har jadval uchun mavjud
# "oxirgi tegilgan vaqt" ustuni alohida ko'rsatilgan.
BOUNDARY = [
    ("tender", "fetched_at"),
    ("tender_document", "fetched_at"),
    ("company_profile", "updated_at"),
    ("catalog_product", "updated_at"),
]


def _boundary(db):
    out = {}
    for table, ts in BOUNDARY:
        r = db.query_one(f"SELECT count(*) AS n, max({ts}) AS mx FROM public.{table}")
        out[table] = (r["n"], r["mx"])
    return out


# ---------------------------------------------------------------------------
# 2 + 3. HAQIQIY BAZA
# ---------------------------------------------------------------------------
def test_db():
    head("2. Endpointlar (haqiqiy baza, TestClient)")
    from fastapi.testclient import TestClient

    from api import db
    from api.main import app

    created_opps = []
    _auth_override(app)

    with TestClient(app) as c:                  # lifespan -> db.init_pool()
        before = _boundary(db)

        # --- meta ---------------------------------------------------------
        m = c.get("/erp/meta").json()
        check(m["schema_ready"], "schema_ready=true (patch qo'llangan)",
              "schema_patch_erp_1.sql bazaga qo'llanmagan")
        if not m["schema_ready"]:
            return
        eq("meta: 9 status", len(m["statuses"]), 9)
        eq("meta: 3 yakuniy", sum(1 for s in m["statuses"] if s["final"]), 3)
        eq("meta: 3 ustuvorlik", len(m["priorities"]), 3)

        # Kod va bazadagi CHECK bir xil ro'yxatmi — ikki manba ajralib
        # ketsa status qo'shilganda 500 chiqadi, sinov shu yerda ushlaydi.
        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.opportunity'::regclass
              AND conname = 'opportunity_status_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in O.STATUSES),
              "bazadagi CHECK kodda e'lon qilingan 9 statusni qamraydi", cdef[:120])
        check(cdef.count("'") == 2 * len(O.STATUSES),
              "bazada ortiqcha status yo'q (ro'yxatlar aynan bir xil)", cdef[:200])

        # TENDER-AI UCHUN SHARTNOMA-VIEW (auth-3, schema_patch_erp_7.sql).
        # `status_label` view ichida CASE bilan hisoblanadi — bu UCHINCHI
        # nusxa (kod, CHECK, view). Shuning uchun u ham shu yerda
        # solishtiriladi: yangi status qo'shilib CASE unutilsa, tender-ai
        # panelida bo'sh nom chiqardi.
        vdef = db.scalar("SELECT pg_get_viewdef('erp.v_tender_status'::regclass)") or ""
        if not vdef:
            check(False, "erp.v_tender_status view i yo'q — schema_patch_erp_7.sql")
        else:
            missing = [code for code, _ in O.STATUSES if f"'{code}'" not in vdef]
            check(not missing, "view CASE i hamma statusni qamraydi", str(missing))
            # SQL da apostrof IKKI marta yoziladi ('Ko''rib chiqilmoqda') va
            # `pg_get_viewdef` ham shunday qaytaradi — solishtirishdan oldin
            # kod tomondagi nomni ham shu ko'rinishga keltiramiz.
            wrong = [label for _, label in O.STATUSES
                     if label.replace("'", "''") not in vdef]
            check(not wrong, "view dagi nomlar kod bilan bir xil", str(wrong))
            # Ustunlar SHARTNOMA: tender-ai aynan shularni o'qiydi
            # (`tender-ai/api/erp_status.py`).
            #
            # `assignee_full_name` schema_patch_erp_19.sql da OXIRIGA
            # qo'shildi — eski o'quvchi buzilmaydi. Ustunlar TARTIBI
            # va qolgan uch shartnoma-view `_tests/erp15_test.py` da
            # qulflangan; bu yerda faqat shu view ning to'plami.
            cols = {r["column_name"] for r in db.query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='erp' AND table_name='v_tender_status'")}
            eq("view ustunlari (shartnoma)", cols,
               {"opportunity_id", "tender_id", "status", "status_label",
                "priority", "broker_name", "client_name", "created_at",
                "updated_at", "assignee_full_name"})

        try:
            # --- lug'atlar -------------------------------------------------
            b = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker",
                                             "email": "zz@test.uz"})
            eq("POST /erp/brokers -> 201", b.status_code, 201)
            broker = b.json()
            cl1 = c.post("/erp/clients", json={"name": PREFIX + "Mijoz A"}).json()
            cl2 = c.post("/erp/clients", json={"name": PREFIX + "Mijoz B"}).json()
            check(any(x["id"] == broker["id"] for x in c.get("/erp/brokers").json()),
                  "yangi broker ro'yxatda ko'rinadi")
            eq("bo'sh nom -> 400", c.post("/erp/clients", json={"name": "  "}).status_code, 400)

            # --- ishga olish uchun haqiqiy tender ---------------------------
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q — 'ishga olish' sinovi o'tkazilmadi")
                return
            tid = t["id"]

            body = {"broker_id": broker["id"], "client_id": cl1["id"],
                    "priority": "high", "win_probability": 60,
                    "note": PREFIX + "izoh", "next_task": "KP yuborish",
                    "next_task_at": "2026-09-01", "created_by": PREFIX + "Broker"}
            r = c.post(f"/erp/tenders/{tid}/take", json=body)
            eq("POST /tenders/{id}/take -> 201", r.status_code, 201)
            opp = r.json()
            created_opps.append(opp["id"])
            eq("yangi karta statusi", opp["status"], "new")
            eq("closed_at bo'sh", opp["closed_at"], None)
            eq("tarixda 1 yozuv", len(opp["history"]), 1)
            eq("tarix: NULL -> new", (opp["history"][0]["from_status"],
                                      opp["history"][0]["to_status"]), (None, "new"))
            snap = opp["tender"]
            check(snap["title"] and snap["tender_ref"],
                  "snapshot to'lgan (nom, manba raqami)", str(snap)[:120])
            live = db.query_one("""SELECT t.name, t.company_name, t.source_id, t.close_at
                                   FROM tender t WHERE t.id = %(id)s""", {"id": tid})
            eq("snapshot nomi tenderdan", snap["title"], live["name"])
            eq("snapshot buyurtmachisi tenderdan", snap["customer_name"], live["company_name"])
            eq("tender_ref = manbadagi asl id", snap["tender_ref"],
               str(live["source_id"] or tid))
            check(snap["source_url"] is None or str(live["source_id"] or tid) in snap["source_url"],
                  "manba havolasi asl id bilan qurilgan", str(snap["source_url"]))
            # MANBA HAVOLASI BAZADAN (`v_tender_manba`), kodda lug'at
            # EMAS: ilgari `SOURCE_URL` lug'ati tender-ai dagi view
            # bilan ikkinchi nusxa edi va ular ajralib ketishi mumkin
            # edi (`erp_rollar.md` §10).
            import inspect
            src = inspect.getsource(O)
            # IZOHLARSIZ matn: izohda `SOURCE_URL` BOR (nega olib
            # tashlangani yozilgan) va u kod bilan adashmasligi kerak.
            sof = chr(10).join(q for q in src.split(chr(10))
                               if not q.strip().startswith("#"))
            check("SOURCE_URL" not in sof, "kodda SOURCE_URL lug'ati QOLMAGAN")
            check("v_tender_manba" in src, "havola v_tender_manba dan olinadi")
            bazada = db.query_one("SELECT ommaviy_url FROM v_tender_manba "
                                  "WHERE ichki_id = %(i)s", {"i": tid})
            if bazada:
                eq("havola bazadagi bilan AYNAN bir xil",
                   snap["source_url"], bazada["ommaviy_url"])

            # --- "KEYINGI VAZIFA" HAQIQIY VAZIFAGA AYLANADI -----------------
            # Ilgari u faqat `erp.opportunity.next_task` ustuniga
            # yozilardi va HECH QAYERDA ko'rinmasdi: vazifalar ro'yxati,
            # "mening ishlarim" va eslatma skripti — hammasi
            # `erp.opportunity_task` dan o'qiydi. Ya'ni odam muddat
            # yozardi va u jimgina yo'qolardi.
            rt = c.get(f"/erp/opportunities/{opp['id']}/tasks")
            if rt.status_code == 200:
                nomlar = [t["title"] for t in rt.json()]
                check("KP yuborish" in nomlar,
                      "ishga olishdagi 'keyingi vazifa' VAZIFAGA aylandi",
                      str(nomlar))
                v = next((t for t in rt.json() if t["title"] == "KP yuborish"), {})
                eq("vazifa muddati ko'chdi", v.get("due_at"), "2026-09-01")
                eq("vazifa mas'uli — kartaning brokeri",
                   (v.get("assignee") or {}).get("id"), broker["id"])
            else:
                print("  SKIP vazifalar sxemasi yo'q — ko'chirish tekshirilmadi")

            # --- takror va 404/400 ------------------------------------------
            r = c.post(f"/erp/tenders/{tid}/take", json=body)
            eq("o'sha tender + o'sha mijoz -> 409", r.status_code, 409)
            eq("409 detail'da mavjud karta id si",
               r.json()["detail"].get("opportunity_id"), opp["id"])

            r2 = c.post(f"/erp/tenders/{tid}/take", json={**body, "client_id": cl2["id"]})
            eq("o'sha tender + boshqa mijoz -> 201", r2.status_code, 201)
            created_opps.append(r2.json()["id"])

            eq("mavjud bo'lmagan tender -> 404",
               c.post("/erp/tenders/999999999/take", json=body).status_code, 404)
            eq("noto'g'ri ustuvorlik -> 400",
               c.post(f"/erp/tenders/{tid}/take",
                      json={**body, "priority": "xxx", "client_id": None}).status_code, 400)

            # --- status quvuri ----------------------------------------------
            oid = opp["id"]
            for st in ("reviewing", "submitted", "won"):
                r = c.patch(f"/erp/opportunities/{oid}/status",
                            json={"status": st, "changed_by": PREFIX + "Broker"})
                eq(f"status -> {st}", (r.status_code, r.json()["status"]), (200, st))
            cur = r.json()
            eq("tarixda 4 yozuv (new + 3 o'tish)", len(cur["history"]), 4)
            check(cur["closed_at"] is not None, "yakuniy status closed_at ni qo'ydi")
            eq("is_final", cur["is_final"], True)

            r = c.patch(f"/erp/opportunities/{oid}/status", json={"status": "preparing"})
            eq("yakuniydan izohsiz qaytish -> 400", r.status_code, 400)
            r = c.patch(f"/erp/opportunities/{oid}/status",
                        json={"status": "preparing", "note": PREFIX + "xato kiritilgan"})
            eq("izoh bilan qaytish -> 200", r.status_code, 200)
            eq("qayta ochilganda closed_at tozalandi", r.json()["closed_at"], None)
            check(any(h["note"] == PREFIX + "xato kiritilgan" for h in r.json()["history"]),
                  "qaytarish sababi tarixda qoldi")
            eq("noma'lum status -> 400",
               c.patch(f"/erp/opportunities/{oid}/status",
                       json={"status": "qwe"}).status_code, 400)
            eq("mavjud bo'lmagan karta -> 404",
               c.patch("/erp/opportunities/999999999/status",
                       json={"status": "won"}).status_code, 404)

            # --- PUT: faqat xodim maydonlari ---------------------------------
            before_put = c.get(f"/erp/opportunities/{oid}").json()
            r = c.put(f"/erp/opportunities/{oid}", json={
                "broker_id": broker["id"], "client_id": cl1["id"], "priority": "low",
                "win_probability": 10, "note": PREFIX + "yangi izoh",
                "next_task": "Hujjat yig'ish", "next_task_at": None,
                "created_by": "BOSHQA ODAM"})
            eq("PUT -> 200", r.status_code, 200)
            put = r.json()
            eq("ustuvorlik o'zgardi", put["priority"], "low")
            eq("ehtimol o'zgardi", put["win_probability"], 10)
            eq("snapshot O'ZGARMADI", put["tender"], before_put["tender"])
            eq("status O'ZGARMADI", put["status"], before_put["status"])
            eq("created_by O'ZGARMADI", put["created_by"], before_put["created_by"])
            eq("PUT: noto'g'ri ehtimol -> 400",
               c.put(f"/erp/opportunities/{oid}",
                     json={"priority": "low", "win_probability": 500}).status_code, 400)

            # --- SNAPSHOT / JONLI TENDER FARQI (0.3) ---------------------------
            head("2b. Snapshot va jonli tender farqi")
            r = c.get(f"/erp/opportunities/{oid}/tender-diff")
            eq("tender-diff -> 200", r.status_code, 200)
            d = r.json()
            eq("tender manbada bor", d["exists"], True)
            eq("yangi kartada farq yo'q", d["changed"], [])

            # Snapshotni QO'LDA buzamiz — farq topilishi kerak
            saved = db.query_one("SELECT customer_name, start_price, deadline_at "
                                 "FROM erp.opportunity WHERE id=%(id)s", {"id": oid})
            db.execute_returning(
                "UPDATE erp.opportunity SET customer_name='ZZTEST ESKI NOM', "
                "start_price=1 WHERE id=%(id)s RETURNING id", {"id": oid})
            d = c.get(f"/erp/opportunities/{oid}/tender-diff").json()
            fields = {x["field"] for x in d["changed"]}
            eq("ikki maydon o'zgargani ko'rindi", fields,
               {"customer_name", "start_price"})
            item = next(x for x in d["changed"] if x["field"] == "customer_name")
            eq("eski qiymat kartadagi", item["was"], "ZZTEST ESKI NOM")
            eq("yangi qiymat tenderdagi", item["now"], live["company_name"])
            eq("yorliq o'zbekcha", item["label"], "Buyurtmachi")

            # SNAPSHOT O'ZGARMAGAN bo'lishi kerak — diff faqat o'qiydi
            still = c.get(f"/erp/opportunities/{oid}").json()
            eq("diff snapshotni o'zgartirmadi", still["tender"]["customer_name"],
               "ZZTEST ESKI NOM")

            db.execute_returning(
                "UPDATE erp.opportunity SET customer_name=%(c)s, start_price=%(p)s "
                "WHERE id=%(id)s RETURNING id",
                {"id": oid, "c": saved["customer_name"], "p": saved["start_price"]})
            eq("qaytargandan keyin farq yo'q",
               c.get(f"/erp/opportunities/{oid}/tender-diff").json()["changed"], [])

            # Manbada yo'q tender — XATO EMAS, exists=false
            db.execute_returning("UPDATE erp.opportunity SET tender_id=999999999 "
                                 "WHERE id=%(id)s RETURNING id", {"id": oid})
            d = c.get(f"/erp/opportunities/{oid}/tender-diff").json()
            eq("o'chirilgan tender -> exists=false", d["exists"], False)
            eq("o'chirilgan tenderda farq ro'yxati bo'sh", d["changed"], [])
            db.execute_returning("UPDATE erp.opportunity SET tender_id=%(t)s "
                                 "WHERE id=%(id)s RETURNING id", {"id": oid, "t": tid})
            eq("mavjud bo'lmagan karta -> 404",
               c.get("/erp/opportunities/999999999/tender-diff").status_code, 404)

            # --- filtrlar ------------------------------------------------------
            def ids(**params):
                return [x["id"] for x in c.get("/erp/opportunities", params=params).json()]

            check(oid in ids(), "filtrsiz ro'yxatda karta bor")
            check(oid in ids(broker_id=broker["id"]), "broker filtri")
            check(oid in ids(client_id=cl1["id"]) and oid not in ids(client_id=cl2["id"]),
                  "mijoz filtri")
            check(oid in ids(status="preparing") and oid not in ids(status="won"),
                  "status filtri")
            check(oid in ids(q=(before_put["tender"]["title"] or "")[:8]), "qidiruv (q)")
            check(oid in ids(open_only=True), "open_only ochiq kartani ko'rsatadi")
            c.patch(f"/erp/opportunities/{oid}/status", json={"status": "lost"})
            check(oid not in ids(open_only=True), "open_only yopilgan kartani yashiradi")

            # --- tender paneli uchun ro'yxat -------------------------------------
            bt = c.get(f"/erp/tenders/{tid}/opportunities").json()
            check(len(bt) >= 2, "tender bo'yicha ikkala karta ham qaytdi", str(len(bt)))

            # --- rahbar hisoboti --------------------------------------------------
            st = c.get("/erp/stats", params={"days": 7}).json()
            eq("stats: by_status 9 qator", len(st["by_status"]), 9)
            eq("stats: upcoming_days", st["upcoming_days"], 7)
            check(st["total"] >= 2, "stats: jami kartalar sanaldi", str(st["total"]))
            n_lost = sum(s["n"] for s in st["by_status"] if s["code"] == "lost")
            eq("stats: 'lost' soni by_status bilan mos", st["lost"], n_lost)
            check(any(b["full_name"] == PREFIX + "Broker" for b in st["by_broker"]),
                  "stats: broker kesimida sinov brokeri bor")
            eq("stats: days chegarasi (0) -> 422",
               c.get("/erp/stats", params={"days": 0}).status_code, 422)

        finally:
            # --- tozalash: bola -> ota tartibida --------------------------
            head("3. Tozalash va chegara")
            for oid in created_opps:
                db.execute_returning(
                    "DELETE FROM erp.opportunity_history WHERE opportunity_id = %(id)s "
                    "RETURNING id", {"id": oid})
                db.execute_returning(
                    "DELETE FROM erp.opportunity WHERE id = %(id)s RETURNING id", {"id": oid})
            db.execute_returning(
                "DELETE FROM erp.broker WHERE full_name LIKE %(p)s RETURNING id",
                {"p": PREFIX + "%"})
            db.execute_returning(
                "DELETE FROM erp.client_company WHERE name LIKE %(p)s RETURNING id",
                {"p": PREFIX + "%"})

            left = (db.scalar("SELECT count(*) FROM erp.broker WHERE full_name LIKE %(p)s",
                              {"p": PREFIX + "%"})
                    + db.scalar("SELECT count(*) FROM erp.client_company WHERE name LIKE %(p)s",
                                {"p": PREFIX + "%"})
                    + db.scalar("SELECT count(*) FROM erp.opportunity WHERE created_by LIKE %(p)s",
                                {"p": PREFIX + "%"}))
            eq("sinov yozuvlari tozalandi", left, 0)
            orphan = db.scalar("""SELECT count(*) FROM erp.opportunity_history h
                                  LEFT JOIN erp.opportunity o ON o.id = h.opportunity_id
                                  WHERE o.id IS NULL""")
            eq("yetim tarix yozuvi qolmadi", orphan, 0)

            # ENG MUHIM: ERP public.* ga tegmaganini isbotlaydi.
            after = _boundary(db)
            for table, _ in BOUNDARY:
                eq(f"public.{table} o'zgarmadi (soni, oxirgi vaqti)",
                   after[table], before[table])


# ---------------------------------------------------------------------------
# TOZALASH SKRIPTI — xavfsizligi
#
# `cleanup_demo.py` o'chirish vositasi, ya'ni undagi xato QAYTARIB
# BO'LMAYDIGAN zarar keltiradi. Shuning uchun uch narsa sinovda qayd
# etiladi:
#   1) sukut bo'yicha (`--yes` siz) HECH NARSA o'chmasligi;
#   2) sanash so'rovi (`_count_sql`) HAR QADAM uchun haqiqiy SQL berishi;
#   3) skript FAQAT `erp` sxemasiga tegishi.
# ---------------------------------------------------------------------------
def test_cleanup_xavfsizligi():
    head("9. Tozalash skripti (cleanup_demo.py)")
    import cleanup_demo as CL

    eq("uch belgi", len(CL.MARKERS), 3)
    check("DEMO" in CL.MARKERS and "ZZTEST" in CL.MARKERS,
          "belgilar hujjatdagidek")

    # Skript FAQAT `erp` sxemasiga tegadi: `public.*` ga yozmaslik
    # qoidasi o'chirishga ham tegishli.
    for label, sql in CL.STEPS:
        check("public." not in sql.replace("public.catalog_product", ""),
              f"'{label[:24]}' faqat erp sxemasida", sql[:80])
        check("DELETE FROM erp." in sql, f"'{label[:24]}' erp dan o'chiradi")

    from api import db as _db
    _db.init_pool()
    try:
        before = {
            "opportunity": _db.scalar("SELECT count(*) FROM erp.opportunity"),
            "client": _db.scalar("SELECT count(*) FROM erp.client_company"),
            "broker": _db.scalar("SELECT count(*) FROM erp.broker"),
            "user": _db.scalar("SELECT count(*) FROM erp.app_user"),
        }

        # Har qadamning sanash so'rovi HAQIQIY SQL bo'lishi kerak:
        # ishlamasa skript "0 ta topildi" deb yolg'on aytardi.
        total = 0
        for label, sql in CL.STEPS:
            try:
                n = _db.scalar(CL._count_sql(sql), {"pat": "%DEMO%"})
                total += n or 0
            except Exception as e:              # noqa: BLE001
                check(False, f"'{label[:24]}' sanash so'rovi ishlamadi",
                      str(e)[:80])
                continue
            check(True, f"'{label[:24]}' sanash so'rovi ishlaydi")

        # ENG MUHIMI: sanash HECH NARSANI o'zgartirmaydi.
        after = {
            "opportunity": _db.scalar("SELECT count(*) FROM erp.opportunity"),
            "client": _db.scalar("SELECT count(*) FROM erp.client_company"),
            "broker": _db.scalar("SELECT count(*) FROM erp.broker"),
            "user": _db.scalar("SELECT count(*) FROM erp.app_user"),
        }
        eq("sanash hech narsani o'chirmadi", after, before)
        check(total >= 0, f"DEMO belgili yozuvlar sanaldi ({total} ta)")
    finally:
        _db.close_pool()


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
        test_cleanup_xavfsizligi()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: baza sinovi bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
