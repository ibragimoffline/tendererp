"""
HISOB-FAKTURA sinovi (5B-2).

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp8_test.py

QAROR: fakturani ERP o'zi chiqaradi. Uchta qoida tekshiriladi va ular
bir tamoyildan chiqadi — BIR HAQIQAT:

  1) QQS STAVKASI HAR QATORDA. Sukut mijoz passportidan, lekin qatorga
     NUSXA ko'chiriladi: passport keyin o'zgarsa chiqarilgan hujjat
     o'zgarmasin.
  2) SUMMALAR SAQLANMAYDI — qatorlardan hisoblanadi (ombordagi qoldiq
     bilan bir xil qoida). Jadvalda `total` ustuni bo'lmasligi ham
     tekshiriladi.
  3) REKVIZITLAR SNAPSHOT — ikkala tomonniki fakturaga ko'chiriladi.

Yana: muzlatish (`draft` dan chiqqach tahrirlanmaydi), to'lovlar
(qisman/to'liq, avtomatik `paid`, o'chirilganda qaytish), eksport
qatlamining ATAYLAB bo'shligi, ZANJIR (karta -> shartnoma -> faktura:
qatorlar ajratilgan tovardan) va chegara (`public.*` ga yozilmaydi).

Sinov o'z mijozini YARATMAYDI: mavjud mijoz ustida ishlaydi, uning
passportini vaqtincha o'zgartiradi va OXIRIDA TIKLAYDI.
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
from api.erp import clients as C  # noqa: E402
from api.erp import invoice as I  # noqa: E402
from api.erp import invoice_export as X  # noqa: E402
from api.erp import opportunity as O  # noqa: E402

MARK = "ZZTEST-FAKTURA"
TODAY = dt.date(2026, 8, 21)

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
# 1. Sof hisob — bazasiz
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Hisob (bazasiz)")
    eq("5 ta status", len(I.STATUSES), 5)
    eq("statuslar takrorlanmaydi", len(I.STATUS_LABEL), len(I.STATUSES))
    # "partly_paid" ATAYLAB yo'q: qisman to'lov — hisob natijasi.
    check("partly_paid" not in I.STATUS_LABEL,
          "'qisman to'landi' STATUS emas (u hisob natijasi)")
    eq("3 to'lov usuli", len(I.METHODS), 3)

    t = I.line_totals(3, "1500000.50", 12)
    eq("net = miqdor * narx", float(t["net"]), 4500001.50)
    eq("qqs = net * stavka", float(t["vat"]), 540000.18)
    eq("jami = net + qqs", float(t["total"]), 5040001.68)

    # Nol stavka — QQS to'lovchi bo'lmagan mijoz uchun.
    t0 = I.line_totals(2, "1000", 0)
    eq("nol stavkada qqs yo'q", float(t0["vat"]), 0.0)
    eq("nol stavkada jami = net", float(t0["total"]), 2000.0)

    # YAXLITLASH QATOR darajasida: aks holda yig'indi qatorlar summasidan
    # farq qilardi va buxgalter buni xato deb hisoblardi.
    lines = [{"qty": 1, "price": "0.05", "vat_rate": 12},
             {"qty": 1, "price": "0.05", "vat_rate": 12}]
    tot = I.totals(lines)
    per = I.line_totals(1, "0.05", 12)
    eq("jami = qatorlar yig'indisi", float(tot["total"]),
       float(per["total"]) * 2)

    for bad in ("abc", None, ""):
        try:
            I.line_totals(bad, 1, 0)
            check(False, f"{bad!r} miqdor sifatida rad etilishi kerak")
        except O.ErpError:
            check(True, f"{bad!r} rad etildi")

    # --- SUMMA SO'Z BILAN (bosma shakl uchun) ---
    # Raqamdagi bitta nolni qo'shib qo'yish oson, so'zdagisini esa emas.
    eq("nol", I.number_words(0), "nol")
    eq("bir xonali", I.number_words(7), "yetti")
    eq("o'n bir", I.number_words(11), "o'n bir")
    eq("yigirma bir", I.number_words(21), "yigirma bir")
    # 100 va 1000 da "bir" TUSHIB QOLADI: "bir yuz" emas, "yuz".
    eq("yuz ('bir yuz' emas)", I.number_words(100), "yuz")
    eq("ming ('bir ming' emas)", I.number_words(1000), "ming")
    # Million esa "bir million" bo'lib qoladi.
    eq("bir million", I.number_words(1000000), "bir million")
    eq("aralash", I.number_words(5240001),
       "besh million ikki yuz qirq ming bir")
    eq("nol o'rtada tushib qolmaydi", I.number_words(1000001), "bir million bir")
    eq("milliard", I.number_words(2000000000), "ikki milliard")

    eq("summa + tiyin", I.amount_words("5240001.68", "UZS"),
       "besh million ikki yuz qirq ming bir so'm 68 tiyin")
    eq("nol so'm", I.amount_words("0.50", "UZS"), "nol so'm 50 tiyin")
    eq("boshqa valyuta", I.amount_words(1200, "USD"),
       "ming ikki yuz AQSH dollari 00 sent")
    # NOMA'LUM valyuta: nom O'YLAB TOPILMAYDI, kodning o'zi yoziladi.
    eq("noma'lum valyuta -> kod", I.amount_words(150, "XYZ"), "yuz ellik XYZ")

    # Eksport qatlami ATAYLAB bo'sh.
    eq("eksport formatlari yo'q", X.available(), [])
    try:
        X.build({}, "didox")
        check(False, "eksport 501 qaytarishi kerak")
    except O.ErpError as e:
        eq("eksport -> 501", e.code, 501)
        check("sozlanmagan" in str(e), "sabab ochiq aytiladi", str(e)[:60])


# ---------------------------------------------------------------------------
# 2-8. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY_SQL = """
SELECT (SELECT count(*) FROM public.tender)          AS n,
       (SELECT max(fetched_at) FROM public.tender)   AS mx
"""


def _restore(cl):
    """Mijoz passportini SINOVDAN OLDINGI holatiga qaytaradi."""
    C.update(cl["id"], {k: cl.get(k) for k in C.FIELDS})


def _purge_audit(doc_ids):
    """Sinov hujjatlarining AUDIT yozuvlarini o'chirish.

    Jurnal tasodifan o'chib ketmasligi uchun `erp.audit_purge`
    bayrog'ini ATAYLAB yoqish kerak (schema_patch_erp_16.sql). Sinov
    o'zidan keyin baza toza qolishi kerak, shuning uchun bu yerda
    bayroq yoqiladi — real ishda buni hech kim qilmaydi."""
    ids = [i for i in doc_ids if i]
    if not ids:
        return
    try:
        with db.get_conn() as cn:
            with cn.cursor() as cur:
                cur.execute("SET LOCAL erp.audit_purge = 'on'")
                cur.execute("DELETE FROM erp.doc_audit "
                            "WHERE doc_id = ANY(%(ids)s)", {"ids": ids})
            cn.commit()
    except Exception:                               # noqa: BLE001
        # Patch qo'llanmagan bo'lsa jadval yo'q — bu xato emas.
        pass


def _cleanup():
    p = {"m": MARK, "p": f"{MARK}%"}
    ids = [r["id"] for r in db.query(
        "SELECT id FROM erp.invoice WHERE note = %(m)s "
        "OR number LIKE %(p)s", p)]
    if ids:
        db.execute_returning("DELETE FROM erp.invoice WHERE note = %(m)s "
                             "OR number LIKE %(p)s RETURNING id", p)
    # Jurnal yozuvlari hujjat bilan CASCADE ketmaydi (FK ataylab yo'q) —
    # ularni alohida o'chirish kerak.
    _purge_audit(ids)
    return len(ids)


def test_db():
    head("2. Sxema")
    from fastapi.testclient import TestClient

    from api.main import app
    _auth_override(app)

    with TestClient(app) as c:
        if not I.schema_ready():
            print("  SKIP schema_patch_erp_11.sql qo'llanmagan")
            return

        before = db.query_one(BOUNDARY_SQL)

        # Kod va bazadagi CHECK bir xil ro'yxatmi.
        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.invoice'::regclass
              AND conname = 'invoice_status_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in I.STATUSES),
              "bazadagi CHECK kodda e'lon qilingan 5 statusni qamraydi",
              cdef[:120])
        eq("bazada ortiqcha status yo'q", cdef.count("'"), 2 * len(I.STATUSES))

        mdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.invoice_payment'::regclass
              AND conname = 'invoice_payment_method_check'
        """) or ""
        check(all(f"'{code}'" in mdef for code, _ in I.METHODS),
              "to'lov usullari kod va bazada bir xil", mdef[:100])

        # SUMMALAR SAQLANMAYDI — jadvalda ular uchun ustun bo'lmasligi kerak.
        cols = {r["column_name"] for r in db.query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='erp' AND table_name='invoice'")}
        check(not (cols & {"total", "amount", "vat_amount", "net_amount"}),
              "fakturada 'jami' ustuni YO'Q (u hisob natijasi)",
              str(sorted(cols & {"total", "amount", "vat_amount"})))
        lcols = {r["column_name"] for r in db.query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='erp' AND table_name='invoice_line'")}
        check("vat_rate" in lcols, "stavka HAR QATORDA saqlanadi")
        check(not (lcols & {"total", "net", "vat"}),
              "qatorda ham summa ustuni yo'q")

        # Mijozni O'ZIMIZ yaratamiz — bazadagi ma'lumotga tayanmaymiz.
        import fixture as FIX
        FIX.ensure_client()
        cl_row = db.query_one("SELECT * FROM erp.client_company "
                              "ORDER BY id LIMIT 1")
        if not cl_row:
            print("  SKIP mijoz yo'q")
            return
        cid = cl_row["id"]
        _cleanup()

        try:
            head("3. QQS mijoz passportidan")
            # NULL = hali so'ralmagan -> stavka 0 (taxmin QILINMAYDI).
            C.update(cid, {**{k: None for k in C.FIELDS},
                           "name": cl_row["name"], "active": True})
            eq("so'ralmagan -> 0", float(I.default_vat_rate(cid)), 0.0)

            C.update(cid, {**{k: None for k in C.FIELDS},
                           "name": cl_row["name"], "active": True,
                           "vat_payer": False, "vat_rate": 12})
            eq("to'lovchi EMAS -> 0 (stavka yozilgan bo'lsa ham)",
               float(I.default_vat_rate(cid)), 0.0)

            C.update(cid, {**{k: None for k in C.FIELDS},
                           "name": cl_row["name"], "active": True,
                           "vat_payer": True, "vat_rate": 12})
            eq("to'lovchi -> passportdagi stavka",
               float(I.default_vat_rate(cid)), 12.0)
            got = c.get(f"/erp/clients/{cid}").json()
            eq("passport javobida vat_payer", got["vat_payer"], True)
            eq("passport javobida vat_rate", got["vat_rate"], 12.0)

            # --- QQS IKKALA TOMONGA qarab ---------------------------
            # QQS ni SOTUVCHI hisoblaydi: biz to'lovchi bo'lmasak, mijoz
            # to'lovchi bo'lsa ham faktura QQS'siz chiqadi.
            from api.erp import contracts as KK
            own_before = KK.own_get()

            def _set_own(payer, rate):
                KK.own_save({**{f: own_before.get(f) for f in KK.OWN_FIELDS},
                             "name": own_before.get("name") or "ZZTEST Kompaniya",
                             "vat_payer": payer, "vat_rate": rate})

            try:
                # BIZ to'lovchi emasmiz -> mijoz 12% bo'lsa ham 0.
                _set_own(False, None)
                eq("BIZ to'lovchi emas -> 0",
                   float(I.default_vat_rate(cid)), 0.0)

                # `None` = HALI SO'RALMAGAN: eski xatti-harakat saqlanadi.
                # Bu MUHIM — patch qo'llangan kuniyoq fakturalar QQS'siz
                # chiqib ketmasligi kerak.
                _set_own(None, None)
                eq("bizniki so'ralmagan -> mijozdan",
                   float(I.default_vat_rate(cid)), 12.0)

                # Ikkala stavka farq qilsa — KICHIGI olinadi: ortiqcha
                # soliq qo'shib qo'yish kam qo'shishdan xavfliroq.
                _set_own(True, 0)
                eq("bizniki 0% -> kichigi", float(I.default_vat_rate(cid)), 0.0)
                _set_own(True, 12)
                eq("ikkalasi 12% -> 12", float(I.default_vat_rate(cid)), 12.0)

                # Stavka son bo'lishi va chegarada bo'lishi kerak.
                for bad in ("abc", -1, 101):
                    try:
                        _set_own(True, bad)
                        check(False, f"{bad!r} stavka rad etilishi kerak")
                    except O.ErpError:
                        check(True, f"{bad!r} stavka rad etildi")
            finally:
                _set_own(own_before.get("vat_payer"),
                         own_before.get("vat_rate"))
                eq("bizning passport TIKLANDI",
                   KK.own_get().get("vat_payer"), own_before.get("vat_payer"))

            head("4. Faktura va snapshot")
            r = c.post("/erp/invoices", json={
                "client_id": cid, "number": f"{MARK}-1",
                "issued_at": TODAY.isoformat(), "currency": "UZS",
                "note": MARK})
            eq("faktura yaratildi -> 201", r.status_code, 201)
            inv = r.json()
            iid = inv["id"]
            eq("qoralama holatida", inv["status"], "draft")
            check(inv["editable"], "qoralama tahrirlanadi")
            eq("created_by SESSIYADAN", inv["created_by"],
               TEST_USER["full_name"])
            eq("mijoz rekvizitlari ko'chirildi", inv["client"]["name"],
               cl_row["name"])
            eq("QQS holati ham ko'chirildi", inv["client"]["vat_payer"], True)
            check("own" in inv, "bizning rekvizitlar ham snapshot")

            eq("mijozsiz faktura -> 400",
               c.post("/erp/invoices", json={"note": MARK}).status_code, 400)
            eq("yo'q mijoz -> 404",
               c.post("/erp/invoices",
                      json={"client_id": 99999999}).status_code, 404)

            head("5. Qatorlar va hisob")
            r = c.post(f"/erp/invoices/{iid}/lines", json={
                "name": "Nasos", "qty": 3, "price": 1500000.50, "unit": "dona"})
            eq("qator qo'shildi -> 201", r.status_code, 201)
            inv = r.json()
            eq("stavka passportdan olindi", inv["lines"][0]["vat_rate"], 12.0)
            eq("qator qqs si", inv["lines"][0]["vat"], 540000.18)

            # Stavka QATORGA nusxa ko'chirilgan: passport o'zgarsa ham
            # eski qator o'zgarmaydi.
            C.update(cid, {**{k: None for k in C.FIELDS},
                           "name": cl_row["name"], "active": True,
                           "vat_payer": True, "vat_rate": 0})
            inv = c.get(f"/erp/invoices/{iid}").json()
            eq("passport o'zgardi, QATOR o'zgarmadi",
               inv["lines"][0]["vat_rate"], 12.0)
            C.update(cid, {**{k: None for k in C.FIELDS},
                           "name": cl_row["name"], "active": True,
                           "vat_payer": True, "vat_rate": 12})

            inv = c.post(f"/erp/invoices/{iid}/lines", json={
                "name": "Yetkazib berish", "qty": 1, "price": 200000,
                "vat_rate": 0}).json()
            eq("aniq stavka berilsa o'sha", inv["lines"][1]["vat_rate"], 0.0)
            eq("jami = qatorlar yig'indisi", inv["totals"]["total"], 5240001.68)
            eq("qqs alohida ko'rinadi", inv["totals"]["vat"], 540000.18)
            # Bosma shakl uchun: javobda summa SO'Z bilan ham bo'ladi.
            eq("javobda summa so'z bilan", inv["totals"]["words"],
               "besh million ikki yuz qirq ming bir so'm 68 tiyin")

            eq("nomsiz qator -> 400",
               c.post(f"/erp/invoices/{iid}/lines",
                      json={"name": " ", "qty": 1, "price": 1}).status_code, 400)
            eq("nol miqdor -> 400",
               c.post(f"/erp/invoices/{iid}/lines",
                      json={"name": "X", "qty": 0, "price": 1}).status_code, 400)
            eq("manfiy narx -> 400",
               c.post(f"/erp/invoices/{iid}/lines",
                      json={"name": "X", "qty": 1, "price": -5}).status_code, 400)

            head("6. Muzlatish")
            eq("qoralamaga to'lov -> 409",
               c.post(f"/erp/invoices/{iid}/payments",
                      json={"paid_at": TODAY.isoformat(),
                            "amount": 100}).status_code, 409)
            r = c.put(f"/erp/invoices/{iid}/status", json={"status": "issued"})
            eq("chiqarildi -> 200", r.status_code, 200)
            check(not r.json()["editable"], "chiqarilgan hujjat muzlatilgan")
            eq("muzlatilgan hujjatga qator -> 409",
               c.post(f"/erp/invoices/{iid}/lines",
                      json={"name": "X", "qty": 1, "price": 1}).status_code, 409)
            eq("muzlatilgan hujjatni tahrirlash -> 409",
               c.put(f"/erp/invoices/{iid}",
                     json={"number": "boshqa"}).status_code, 409)

            # Bo'sh fakturani "chiqarildi" deb belgilash — yolg'on.
            empty = c.post("/erp/invoices",
                           json={"client_id": cid, "note": MARK}).json()
            r = c.put(f"/erp/invoices/{empty['id']}/status",
                      json={"status": "issued"})
            eq("to'liqmas fakturani chiqarib bo'lmaydi -> 400",
               r.status_code, 400)
            check("raqam" in r.json()["detail"] and "qator" in r.json()["detail"],
                  "nima yetishmayotgani aytiladi", r.json()["detail"][:80])

            head("7. To'lovlar")
            inv = c.post(f"/erp/invoices/{iid}/payments", json={
                "paid_at": TODAY.isoformat(), "amount": 1000000,
                "method": "bank"}).json()
            eq("qisman to'lov yozildi", inv["paid"], 1000000.0)
            eq("qoldiq hisoblandi", inv["balance"], 4240001.68)
            eq("qisman to'lovda status O'ZGARMAYDI", inv["status"], "issued")
            check(not inv["fully_paid"], "to'liq to'lanmagan")

            inv = c.post(f"/erp/invoices/{iid}/payments", json={
                "paid_at": TODAY.isoformat(), "amount": inv["balance"],
                "method": "cash"}).json()
            eq("to'liq to'langach status AVTOMATIK", inv["status"], "paid")
            eq("qoldiq nol", inv["balance"], 0.0)

            pid = inv["payments"][-1]["id"]
            inv = c.delete(f"/erp/payments/{pid}").json()
            eq("to'lov o'chirilgach status QAYTADI", inv["status"], "issued")
            check(inv["balance"] > 0, "qarz qaytdi", str(inv["balance"]))

            eq("nol to'lov -> 400",
               c.post(f"/erp/invoices/{iid}/payments",
                      json={"paid_at": TODAY.isoformat(),
                            "amount": 0}).status_code, 400)
            eq("noma'lum usul -> 400",
               c.post(f"/erp/invoices/{iid}/payments",
                      json={"paid_at": TODAY.isoformat(), "amount": 10,
                            "method": "bitcoin"}).status_code, 400)
            eq("yo'q to'lov -> 404",
               c.delete("/erp/payments/99999999").status_code, 404)

            head("8. Bekor qilish va eksport")
            inv = c.put(f"/erp/invoices/{iid}/status",
                        json={"status": "cancelled"}).json()
            eq("bekor qilindi", inv["status"], "cancelled")
            eq("bekor qilinganni qaytarib bo'lmaydi -> 409",
               c.put(f"/erp/invoices/{iid}/status",
                     json={"status": "issued"}).status_code, 409)
            eq("bekor qilinganga to'lov -> 409",
               c.post(f"/erp/invoices/{iid}/payments",
                      json={"paid_at": TODAY.isoformat(),
                            "amount": 10}).status_code, 409)

            r = c.get("/erp/invoices/export-formats")
            eq("eksport formatlari ro'yxati -> 200", r.status_code, 200)
            eq("ro'yxat BO'SH (ataylab)", r.json()["formats"], [])
            eq("eksport urinishi -> 501",
               c.get(f"/erp/invoices/{iid}/export?fmt=didox").status_code, 501)

            st = c.get("/erp/invoices/stats").json()
            check("debt" in st and "by_status" in st,
                  "statistika: qarz va holatlar", str(list(st)))

            meta = c.get("/erp/meta").json()
            eq("meta: faktura tayyor", meta["invoice_ready"], True)
            eq("meta: statuslar", len(meta["invoice_statuses"]), 5)
            eq("meta: eksport formatlari bo'sh",
               meta["invoice_export_formats"], [])

            # --- ZANJIR: karta -> shartnoma -> faktura ------------------
            head("9. Kartadan faktura (zanjir)")
            opp = FIX.ensure_opportunity()
            prod = db.query_one("SELECT id, name, price FROM public.catalog_product "
                                "ORDER BY id LIMIT 1")
            if not opp or not prod:
                print("  SKIP mos karta yoki mahsulot yo'q")
            else:
                oid, was = opp["id"], opp["status"]
                from api.erp import stock as S
                S.add_move({"product_id": prod["id"], "kind": "in", "qty": 50,
                            "note": MARK, "created_by": MARK})
                O.set_status(oid, "confirmed", MARK, MARK)
                S.add_reserve(oid, {"product_id": prod["id"], "qty": 7,
                                    "note": MARK, "created_by": MARK})

                r = c.post(f"/erp/opportunities/{oid}/invoice",
                           json={"number": f"{MARK}-Z", "note": MARK,
                                 "issued_at": TODAY.isoformat()})
                eq("kartadan faktura -> 201", r.status_code, 201)
                inv = r.json()
                eq("kartaga bog'landi", inv["opportunity_id"], oid)
                eq("mijoz kartadan olindi", inv["client_id"], opp["client_id"])
                # QATORLAR ajratilgan tovardan: miqdor HAQIQIY.
                eq("bitta qator to'ldirildi", inv["filled"]["lines"], 1)
                eq("qator miqdori rezervdan", inv["lines"][0]["qty"], 7.0)
                eq("nomi ham rezervdan", inv["lines"][0]["name"], prod["name"])
                # Narx katalogdan; bo'lmasa 0 va JIM QOLDIRILMAYDI.
                if prod["price"] is None:
                    eq("narxsiz qator sanaldi", inv["filled"]["no_price"], 1)
                    eq("narx 0 qoldi", inv["lines"][0]["price"], 0.0)
                else:
                    eq("narx katalogdan", inv["lines"][0]["price"],
                       float(prod["price"]))

                # BEKOR QILINGAN rezerv fakturaga TUSHMAYDI.
                rid = S.add_reserve(oid, {"product_id": prod["id"], "qty": 3,
                                          "note": MARK,
                                          "created_by": MARK})["id"]
                S.release_reserve(rid, MARK)
                inv2 = c.post(f"/erp/opportunities/{oid}/invoice",
                              json={"number": f"{MARK}-Z2",
                                    "note": MARK}).json()
                eq("bo'shatilgan rezerv qo'shilmadi",
                   inv2["lines"][0]["qty"], 7.0)

                # Mijozsiz kartadan faktura chiqmaydi.
                nc = db.query_one("SELECT id FROM erp.opportunity "
                                  "WHERE client_id IS NULL LIMIT 1")
                if nc:
                    eq("mijozsiz kartadan -> 400",
                       c.post(f"/erp/opportunities/{nc['id']}/invoice",
                              json={}).status_code, 400)
                eq("yo'q kartadan -> 404",
                   c.post("/erp/opportunities/99999999/invoice",
                          json={}).status_code, 404)

                # Tozalash: karta va ombor joyiga qaytadi.
                O.set_status(oid, was, MARK, "sinov tugadi")
                db.execute_returning(
                    "DELETE FROM erp.stock_reserve WHERE created_by = %(m)s "
                    "RETURNING id", {"m": MARK})
                db.execute_returning(
                    "DELETE FROM erp.stock_move WHERE created_by = %(m)s "
                    "RETURNING id", {"m": MARK})
                db.execute_returning(
                    "DELETE FROM erp.opportunity_history WHERE changed_by = %(m)s "
                    "RETURNING id", {"m": MARK})

            # --- FOYDA -------------------------------------------------
            head("10. Foyda (daromad - tannarx)")
            from api.erp import stock as STK

            if not opp or not prod:
                print("  SKIP karta yoki mahsulot yo'q")
            else:
                oid3 = opp["id"]
                back = db.scalar("SELECT status FROM erp.opportunity "
                                 "WHERE id = %(i)s", {"i": oid3})
                # Tannarxni VAQTINCHA qo'yamiz va oxirida TIKLAYMIZ. Buni
                # sinov OPERATOR rolida qiladi (ERP kodi `public.*` ga
                # yozmaydi); aks holda katalogda narx yo'qligi tufayli
                # hisobning eng muhim qismi tekshirilmay qolardi.
                old_cost = db.scalar(
                    "SELECT cost_price FROM public.catalog_product "
                    "WHERE id = %(i)s", {"i": prod["id"]})
                db.execute_returning(
                    "UPDATE public.catalog_product SET cost_price = 300000 "
                    "WHERE id = %(i)s RETURNING id", {"i": prod["id"]})
                try:
                    STK.add_move({"product_id": prod["id"], "kind": "in",
                                  "qty": 50, "note": MARK,
                                  "created_by": MARK})
                    O.set_status(oid3, "confirmed", MARK, MARK)
                    STK.add_reserve(oid3, {"product_id": prod["id"], "qty": 4,
                                           "note": MARK, "created_by": MARK})

                    # Pul harakati yo'q -> foiz NULL ("0% foyda" degan
                    # yolg'on bo'lmasin).
                    p0 = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    eq("daromadsiz -> foiz yo'q", p0["margin"], None)
                    eq("daromad nol", p0["revenue"], 0.0)

                    # Yutildi -> rezerv chiqimga aylanadi, TANNARX muzlaydi.
                    O.set_status(oid3, "won", MARK, MARK)
                    mv = db.query_one(
                        "SELECT unit_cost FROM erp.stock_move "
                        "WHERE opportunity_id = %(i)s AND kind = 'out' "
                        "ORDER BY id DESC LIMIT 1", {"i": oid3})
                    eq("chiqimda tannarx muzlatildi",
                       float(mv["unit_cost"]), 300000.0)

                    inv3 = c.post("/erp/invoices", json={
                        "client_id": opp["client_id"], "opportunity_id": oid3,
                        "number": f"{MARK}-P", "issued_at": TODAY.isoformat(),
                        "note": MARK}).json()
                    c.post(f"/erp/invoices/{inv3['id']}/lines", json={
                        "name": prod["name"], "qty": 4, "price": 500000,
                        "vat_rate": 12})
                    c.put(f"/erp/invoices/{inv3['id']}/status",
                          json={"status": "issued"})

                    p = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    # QQS DAROMAD EMAS: u davlatniki.
                    eq("daromad QQS SIZ", p["revenue"], 2000000.0)
                    eq("QQS alohida ko'rsatiladi", p["vat"], 240000.0)
                    eq("tannarx = 4 x 300000", p["cost"], 1200000.0)
                    eq("foyda = daromad - tannarx", p["profit"], 800000.0)
                    eq("foiz", p["margin"], 40.0)
                    check(p["complete"], "hisob to'liq deb belgilandi")

                    # ENG MUHIMI: katalog narxi o'zgarsa ham TANNARX
                    # o'zgarmaydi — o'tgan foyda qayta yozilmaydi.
                    db.execute_returning(
                        "UPDATE public.catalog_product SET cost_price = 999999 "
                        "WHERE id = %(i)s RETURNING id", {"i": prod["id"]})
                    p2 = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    eq("katalog narxi o'zgardi -> tannarx O'ZGARMADI",
                       p2["cost"], p["cost"])

                    # QORALAMA faktura hali hujjat emas -> daromad emas.
                    d = c.post("/erp/invoices", json={
                        "client_id": opp["client_id"], "opportunity_id": oid3,
                        "number": f"{MARK}-D", "note": MARK}).json()
                    c.post(f"/erp/invoices/{d['id']}/lines", json={
                        "name": "X", "qty": 1, "price": 1000000})
                    p3 = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    eq("qoralama daromadga kirmaydi", p3["revenue"],
                       p["revenue"])

                    # BEKOR QILINGAN ham kirmaydi.
                    c.put(f"/erp/invoices/{inv3['id']}/status",
                          json={"status": "cancelled"})
                    p4 = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    eq("bekor qilingan daromadga kirmaydi", p4["revenue"], 0.0)

                    # TANNARXI NOMA'LUM chiqim nolga aylantirilmaydi —
                    # alohida sanaladi va hisob "to'liq emas" deyiladi.
                    db.execute_returning(
                        "UPDATE erp.stock_move SET unit_cost = NULL "
                        "WHERE opportunity_id = %(i)s AND kind = 'out' "
                        "RETURNING id", {"i": oid3})
                    p5 = c.get(f"/erp/opportunities/{oid3}/profit").json()
                    eq("noma'lum tannarx NOLGA aylanmadi", p5["cost"], 0.0)
                    eq("noma'lum chiqim sanaldi", p5["unknown_cost_moves"], 1)
                    check(not p5["complete"], "hisob TO'LIQ EMAS deb aytildi")

                    # Rahbar hisoboti: summasi nol ko'ringan, lekin
                    # tannarxi noma'lum karta ro'yxatdan TUSHIB QOLMAYDI.
                    rep = c.get("/erp/profit").json()
                    check(any(r["opportunity_id"] == oid3
                              for r in rep["items"]),
                          "noma'lum tannarxli karta hisobotda qoldi")
                    check(not rep["complete"],
                          "umumiy hisob ham to'liq emas deb belgilandi")

                    # --- ARALASH VALYUTA QO'SHILMAYDI ----------------
                    # Bitta valyutada umumiy yig'indi BOR.
                    one = c.get("/erp/profit").json()
                    if len(one["currencies"]) == 1:
                        check(one["totals"] is not None,
                              "bitta valyutada umumiy yig'indi bor",
                              str(one["currencies"]))
                        check(not one["mixed_currency"],
                              "bitta valyuta -> aralash emas")

                    # Ikkinchi valyutali karta qo'shamiz.
                    tid2 = db.scalar(
                        "SELECT id FROM public.tender WHERE id NOT IN "
                        "(SELECT tender_id FROM erp.opportunity) "
                        "ORDER BY id LIMIT 1")
                    usd_id = None
                    if not tid2:
                        print("  SKIP bo'sh tender yo'q — valyuta "
                              "tekshiruvi qisman")
                    else:
                        usd_id = db.execute_returning(
                            "INSERT INTO erp.opportunity (tender_id, title, "
                            " status, client_id, start_price, currency, "
                            " created_by) VALUES (%(t)s, %(n)s, 'confirmed', "
                            " %(c)s, 1200, 'USD', %(m)s) RETURNING id",
                            {"t": tid2, "n": f"{MARK}-USD",
                             "c": opp["client_id"], "m": MARK})["id"]
                        iu = c.post("/erp/invoices", json={
                            "client_id": opp["client_id"],
                            "opportunity_id": usd_id,
                            "number": f"{MARK}-USD",
                            "issued_at": TODAY.isoformat(),
                            "note": MARK}).json()
                        c.post(f"/erp/invoices/{iu['id']}/lines",
                               json={"name": "tovar", "qty": 1,
                                     "price": 1200})
                        c.put(f"/erp/invoices/{iu['id']}/status",
                              json={"status": "issued"})

                        mix = c.get("/erp/profit").json()
                        check(mix["mixed_currency"],
                              "ikki valyuta -> aralash deb belgilandi",
                              str(mix["currencies"]))
                        # ENG MUHIMI: aralashda umumiy yig'indi BERILMAYDI.
                        eq("aralashda umumiy yig'indi YO'Q",
                           mix["totals"], None)
                        eq("har valyuta uchun alohida qator",
                           len(mix["by_currency"]), 2)
                        usd = next(x for x in mix["by_currency"]
                                   if x["currency"] == "USD")
                        eq("USD qatori aralashmagan", usd["revenue"], 1200.0)
                        # Valyutalar bir-biriga QO'SHILMAGAN.
                        check(all(x["revenue"] < 2_000_000 or
                                  x["currency"] == "UZS"
                                  for x in mix["by_currency"]),
                              "valyutalar qo'shilib ketmadi")

                        # Rahbar paneli `start_price` ni yig'adi, foyda
                        # esa fakturani — ya'ni "aralashmi?" degan savol
                        # ikkalasida BOSHQA to'plamdan hisoblanadi. Panel
                        # uchun UZS kartasida ham narx bo'lishi kerak.
                        db.execute_returning(
                            "UPDATE erp.opportunity SET start_price = 5000000, "
                            "currency = 'UZS' WHERE id = %(i)s RETURNING id",
                            {"i": oid3})
                        st = c.get("/erp/stats").json()
                        check(st["mixed_currency"],
                              "panel: aralash valyuta belgilandi")
                        eq("panel: 'ishda' summasi berilmadi",
                           st["open_total"], None)
                        eq("panel: 'yutilgan' summasi berilmadi",
                           st["won_total"], None)
                        # Sanoq esa TO'G'RI qoladi — u valyutaga bog'liq
                        # emas va yashirilmaydi.
                        check(st["total"] > 0, "panel: kartalar soni qoldi")
                finally:
                    db.execute_returning(
                        "UPDATE public.catalog_product SET cost_price = %(c)s "
                        "WHERE id = %(i)s RETURNING id",
                        {"c": old_cost, "i": prod["id"]})
                    eq("katalog tannarxi TIKLANDI",
                       db.scalar(
                           "SELECT cost_price FROM public.catalog_product "
                           "WHERE id = %(i)s", {"i": prod["id"]}), old_cost)
                    O.set_status(oid3, back, MARK, "sinov tugadi")
                    db.execute_returning(
                        "DELETE FROM erp.stock_reserve WHERE created_by = %(m)s "
                        "RETURNING id", {"m": MARK})
                    db.execute_returning(
                        "DELETE FROM erp.stock_move WHERE created_by = %(m)s "
                        "RETURNING id", {"m": MARK})
                    db.execute_returning(
                        "DELETE FROM erp.opportunity_history "
                        "WHERE changed_by = %(m)s RETURNING id", {"m": MARK})
                    # Valyuta sinovi uchun yaratilgan karta.
                    db.execute_returning(
                        "DELETE FROM erp.opportunity WHERE title = %(t)s "
                        "RETURNING id", {"t": f"{MARK}-USD"})

        finally:
            head("11. Tozalash va chegara")
            n = _cleanup()
            check(n > 0, f"sinov fakturalari o'chirildi ({n} ta)")
            eq("hech narsa qolmadi",
               db.scalar("SELECT count(*) FROM erp.invoice WHERE note = %(m)s "
                         "OR number LIKE %(p)s",
                         {"m": MARK, "p": f"{MARK}%"}), 0)
            # Qatorlar va to'lovlar CASCADE bilan ketdimi.
            eq("qatorlar ham o'chdi (CASCADE)",
               db.scalar("SELECT count(*) FROM erp.invoice_line l "
                         "WHERE NOT EXISTS (SELECT 1 FROM erp.invoice i "
                         "WHERE i.id = l.invoice_id)"), 0)
            _restore(cl_row)
            FIX.cleanup()
            eq("mijoz passporti tiklandi",
               db.scalar("SELECT vat_payer FROM erp.client_company "
                         "WHERE id = %(i)s", {"i": cid}), cl_row["vat_payer"])
            # ERP `public.*` ga YOZMAYDI — faktura ham istisno emas.
            after = db.query_one(BOUNDARY_SQL)
            eq("public.tender soni tegilmadi", after["n"], before["n"])
            eq("public.tender yangilanmadi", after["mx"], before["mx"])


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
