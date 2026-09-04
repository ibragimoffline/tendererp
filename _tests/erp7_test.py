"""
OMBOR sinovi (5B-1) — qoldiqning egasi ERP.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp7_test.py

QAROR (`docs/erp_arxitektura_3.md` 4.3, 6.1): jurnal ERP da, tender-ai
esa `erp.v_stock_balance` VIEW idan o'qiydi ("A1" yo'li). Shu tufayli
`public.*` ga yozmaslik qoidasi buzilmaydi — sinov buni ham tekshiradi.

Tekshiriladi:
  1) SOF MANTIQ: harakat turlari, ishora qoidasi, miqdor tekshiruvi.
  2) SXEMA: kodda e'lon qilingan turlar bazadagi CHECK bilan bir xil;
     view ustunlari SHARTNOMA (tender-ai aynan shularni o'qiydi).
  3) JURNAL: kirim/chiqim/tuzatish yoziladi, qoldiq YIG'INDI bo'ladi.
  4) QOIDALAR: chiqim manfiy bo'ladi, tuzatish sababsiz o'tmaydi,
     boshlang'ich qoldiq IKKI MARTA kiritilmaydi, nol miqdor rad etiladi.
  5) MANFIY QOLDIQ — TAQIQ EMAS, lekin ogohlantiriladi.
  6) SNAPSHOT: mahsulot nomi jurnalda muzlatiladi.
  7) KO'CHIRISH: `seed-opening` import qoldig'idan bir marta ko'chiradi.
  8) REZERV: qoldiqni KAMAYTIRMAYDI, mavjudni kamaytiradi; kartaning
     statusiga bog'langan (yutildi -> chiqim, yutqazildi -> bo'shaydi,
     yakuniydan qaytish -> teskari kirim va rezerv tiklanadi).
  9) TAKLIF: tender pozitsiyalaridan rezerv taklifi — moslashuv
     tender-ai da, YOZISH esa faqat odam tasdig'i bilan.
 10) CHEGARA: ERP `public.*` ga YOZMAYDI (katalog tegilmaydi).

Sinov o'z mahsulotini YARATMAYDI (katalog tender-ai niki): mavjud
mahsulot ustida ishlaydi va oxirida O'ZI yozgan harakatlarni o'chiradi.
Boshqa hech narsaga tegmaydi.
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

from api import db  # noqa: E402
from api.erp import opportunity as O  # noqa: E402
from api.erp import stock as S  # noqa: E402

#: Sinov yozuvlarini shu belgi bilan topamiz va oxirida o'chiramiz.
MARK = "ZZTEST-OMBOR"

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
# 1. Sof mantiq — bazasiz
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq (bazasiz)")
    eq("4 ta harakat turi", len(S.KINDS), 4)
    eq("turlar takrorlanmaydi", len(S.KIND_LABEL), len(S.KINDS))
    # Ishora qoidasi: kirim +, chiqim -. `adjust` ro'yxatda YO'Q, chunki
    # uning ishorasi chaqiruvchidan keladi.
    eq("kirim musbat", S.SIGN["in"], 1)
    eq("boshlang'ich musbat", S.SIGN["opening"], 1)
    eq("chiqim manfiy", S.SIGN["out"], -1)
    check("adjust" not in S.SIGN,
          "tuzatishning ishorasi qat'iy emas (chaqiruvchidan)")

    for bad in ("", None, "abc"):
        try:
            S._qty(bad)
            check(False, f"{bad!r} miqdor sifatida rad etilishi kerak")
        except O.ErpError:
            check(True, f"{bad!r} rad etildi")
    try:
        S._qty(0)
        check(False, "nol miqdor rad etilishi kerak")
    except O.ErpError:
        check(True, "nol miqdor rad etildi")
    eq("son o'qiladi", float(S._qty("12.5")), 12.5)


# ---------------------------------------------------------------------------
# 2-8. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY_SQL = """
SELECT (SELECT count(*) FROM public.catalog_product)          AS n,
       (SELECT max(updated_at) FROM public.catalog_product)   AS mx,
       (SELECT count(*) FROM public.catalog_product
        WHERE stock_qty IS NOT NULL)                          AS with_stock
"""


#: Faqat SINOV yozganlari. `db.execute_returning` bitta qator qaytaradi,
#: shuning uchun avval sanaymiz, keyin o'chiramiz.
#:
#: UCH manba: endpoint orqali yozilganlar (`created_by` = sinov
#: foydalanuvchisi), modul orqali yozilganlar (`created_by` = MARK) va
#: REZERVDAN avtomatik tug'ilganlar (izohi bizniki emas, lekin
#: `created_by` MARK bo'ladi — status o'zgarishini sinov qildi).
_MINE_SQL = ("FROM erp.stock_move "
             "WHERE created_by IN (%(b)s, %(a)s) OR note LIKE %(m)s")


def _cleanup():
    """Sinov yozgan harakatlarni o'chiradi va SONINI qaytaradi. Faqat
    O'ZINIKINI."""
    p = {"b": TEST_USER["full_name"], "a": MARK, "m": f"%{MARK}%"}
    n = db.scalar(f"SELECT count(*) {_MINE_SQL}", p) or 0
    if n:
        db.execute_returning(f"DELETE {_MINE_SQL} RETURNING id", p)
    return n


def test_db():
    head("2. Sxema va shartnoma")
    from fastapi.testclient import TestClient

    from api.main import app
    _auth_override(app)

    with TestClient(app) as c:
        if not S.schema_ready():
            print("  SKIP schema_patch_erp_8.sql qo'llanmagan")
            return

        before = db.query_one(BOUNDARY_SQL)

        # Kod va bazadagi CHECK bir xil ro'yxatmi.
        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.stock_move'::regclass
              AND conname = 'stock_move_kind_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in S.KINDS),
              "bazadagi CHECK kodda e'lon qilingan 4 turni qamraydi", cdef[:120])
        eq("bazada ortiqcha tur yo'q", cdef.count("'"), 2 * len(S.KINDS))

        # VIEW — tender-ai uchun SHARTNOMA (`tender-ai/api/erp_stock.py`).
        cols = {r["column_name"] for r in db.query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='erp' AND table_name='v_stock_balance'")}
        eq("view ustunlari (shartnoma)", cols,
           {"product_id", "product_name", "unit", "qty", "reserved",
            "available", "updated_at", "move_count", "reserve_count"})

        # Rezerv holatlari ham kodda va bazada bir xil bo'lsin.
        rdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.stock_reserve'::regclass
              AND conname = 'stock_reserve_status_check'
        """) or ""
        check(all(f"'{code}'" in rdef for code, _ in S.RESERVE_STATES),
              "rezerv holatlari kod va bazada bir xil", rdef[:120])
        eq("bazada ortiqcha holat yo'q", rdef.count("'"),
           2 * len(S.RESERVE_STATES))
        ins = db.query_one(
            "SELECT is_insertable_into FROM information_schema.tables "
            "WHERE table_schema='erp' AND table_name='v_stock_balance'")
        eq("view ga yozib bo'lmaydi", ins and ins["is_insertable_into"], "NO")

        # Mahsulot KATALOGDA (tender-ai niki) — sinov o'zi yaratmaydi.
        prod = db.query_one("SELECT id, name FROM public.catalog_product "
                            "ORDER BY id LIMIT 1")
        if not prod:
            print("  SKIP katalogda mahsulot yo'q (tender-ai da yaratiladi)")
            return
        pid = prod["id"]
        _cleanup()          # oldingi yurishdan qolgani bo'lsa

        try:
            head("3. Jurnal va qoldiq")
            base = db.scalar(S.SUM_SQL, {"id": pid}) or 0

            r = c.post("/erp/stock/moves", json={
                "product_id": pid, "kind": "in", "qty": 100,
                "doc_ref": "N-1", "note": f"{MARK} kirim"})
            eq("kirim -> 201", r.status_code, 201)
            eq("kirim musbat yozildi", r.json()["qty"], 100.0)
            eq("qoldiq oshdi", r.json()["balance"], float(base) + 100)
            check(r.json()["warning"] is None, "ogohlantirish yo'q")
            eq("created_by SESSIYADAN", r.json()["created_by"],
               TEST_USER["full_name"])

            r = c.post("/erp/stock/moves", json={
                "product_id": pid, "kind": "out", "qty": 30,
                "note": f"{MARK} chiqim"})
            eq("chiqim -> 201", r.status_code, 201)
            # MUSBAT son yuborildi, ishorani SERVER qo'ydi.
            eq("chiqim manfiy saqlandi", r.json()["qty"], -30.0)
            eq("qoldiq kamaydi", r.json()["balance"], float(base) + 70)

            r = c.post("/erp/stock/moves", json={
                "product_id": pid, "kind": "adjust", "qty": -5,
                "note": f"{MARK} inventarizatsiya"})
            eq("tuzatish -> 201", r.status_code, 201)
            eq("tuzatish ishorasi saqlandi", r.json()["qty"], -5.0)
            eq("qoldiq = YIG'INDI", r.json()["balance"], float(base) + 65)

            # Qoldiq alohida USTUNDA saqlanmaydi — u har safar hisoblanadi.
            check(not db.query_one(
                "SELECT 1 AS x FROM information_schema.columns "
                "WHERE table_schema='erp' AND table_name='stock_move' "
                "AND column_name IN ('balance', 'qty_after')"),
                "jadvalda 'qoldiq' ustuni YO'Q (u hisob natijasi)")

            head("4. Qoidalar")
            eq("noma'lum tur -> 400",
               c.post("/erp/stock/moves", json={
                   "product_id": pid, "kind": "yolgon", "qty": 1}).status_code, 400)
            eq("nol miqdor -> 400",
               c.post("/erp/stock/moves", json={
                   "product_id": pid, "kind": "in", "qty": 0}).status_code, 400)
            eq("kirimda manfiy miqdor -> 400",
               c.post("/erp/stock/moves", json={
                   "product_id": pid, "kind": "in", "qty": -5}).status_code, 400)
            # Tuzatish sababsiz bo'lsa jurnal ma'nosini yo'qotadi.
            eq("sababsiz tuzatish -> 400",
               c.post("/erp/stock/moves", json={
                   "product_id": pid, "kind": "adjust", "qty": 3}).status_code, 400)
            eq("yo'q mahsulot -> 404",
               c.post("/erp/stock/moves", json={
                   "product_id": 99999999, "kind": "in", "qty": 1}).status_code, 404)

            # BOSHLANG'ICH QOLDIQ mahsulotga BIR MARTA qo'yiladi. U
            # bazada allaqachon bo'lishi mumkin (demo yoki real ish
            # ma'lumoti) — o'shanda javob 409 bo'ladi va bu HAM to'g'ri
            # xatti-harakat. Sinov "bo'sh baza" ga tayanmasligi kerak:
            # aynan shunday bog'liqlik oldin qamrovni jimgina tushirgan
            # edi (`fixture.py` hikoyasi).
            had_opening = bool(db.scalar(
                "SELECT count(*) FROM erp.stock_move WHERE product_id = %(i)s "
                "AND kind = 'opening'", {"i": pid}))
            r = c.post("/erp/stock/moves", json={
                "product_id": pid, "kind": "opening", "qty": 10,
                "note": f"{MARK} boshlang'ich"})
            eq("boshlang'ich qoldiq -> " + ("409 (allaqachon bor)"
                                            if had_opening else "201"),
               r.status_code, 409 if had_opening else 201)
            eq("takroriy boshlang'ich -> 409",
               c.post("/erp/stock/moves", json={
                   "product_id": pid, "kind": "opening", "qty": 5,
                   "note": f"{MARK} takror"}).status_code, 409)

            head("5. Manfiy qoldiq — taqiq emas, ogohlantirish")
            bal = db.scalar(S.SUM_SQL, {"id": pid}) or 0
            r = c.post("/erp/stock/moves", json={
                "product_id": pid, "kind": "out", "qty": float(bal) + 50,
                "note": f"{MARK} ortiqcha chiqim"})
            eq("ortiqcha chiqim ham o'tadi -> 201", r.status_code, 201)
            check(r.json()["balance"] < 0, "qoldiq manfiy bo'ldi",
                  str(r.json()["balance"]))
            check(r.json()["warning"], "ogohlantirish qaytdi",
                  str(r.json()["warning"]))
            # Ro'yxat ham manfiylarni ajratib ko'rsatadi.
            lst = c.get("/erp/stock").json()
            check(pid in lst["negative"], "ro'yxatda manfiy deb belgilandi")

            head("6. Snapshot va ko'rinish")
            moves = c.get(f"/erp/stock/moves?product_id={pid}").json()
            check(len(moves) >= 5, "harakatlar tarixi qaytdi", str(len(moves)))
            check(all(m["product_name"] == prod["name"] for m in moves),
                  "mahsulot nomi jurnalda SNAPSHOT qilingan")
            check(all(m["kind_label"] for m in moves),
                  "har harakatda o'qiladigan nom bor")

            one = c.get(f"/erp/stock/{pid}").json()
            eq("mahsulot kartasi: qoldiq", one["qty"], r.json()["balance"])
            check(len(one["moves"]) >= 5, "kartada tarix ham bor")
            check(one["in_catalog"], "mahsulot katalogda")

            lst = c.get("/erp/stock").json()
            eq("turlar ro'yxati javobda", len(lst["kinds"]), len(S.KINDS))
            row = next((x for x in lst["items"] if x["product_id"] == pid), None)
            check(row is not None, "mahsulot qoldiqlar ro'yxatida")
            eq("ro'yxatdagi qoldiq kartadagi bilan bir xil",
               row and row["qty"], one["qty"])

            head("7. Import qoldig'ini ko'chirish")
            r = c.post("/erp/stock/seed-opening")
            eq("seed-opening -> 200", r.status_code, 200)
            # Bizning mahsulotda boshlang'ich ALLAQACHON bor — ikkilanmaydi.
            check(pid not in r.json()["created"],
                  "mavjud boshlang'ich qayta yaratilmadi")
            n1 = db.scalar("SELECT count(*) FROM erp.stock_move "
                           "WHERE kind = 'opening'")
            c.post("/erp/stock/seed-opening")
            eq("ikkinchi yurishda qo'shilmadi",
               db.scalar("SELECT count(*) FROM erp.stock_move "
                         "WHERE kind = 'opening'"), n1)

            # --- REZERV -------------------------------------------------
            head("8. Rezerv")
            import fixture as FIX
            opp = FIX.ensure_opportunity()
            if not opp:
                print("  SKIP yakuniy bo'lmagan karta yo'q")
            else:
                oid, was = opp["id"], opp["status"]
                # Toza boshlash: qoldiqni ma'lum qiymatga keltiramiz.
                _cleanup()
                c.post("/erp/stock/moves", json={
                    "product_id": pid, "kind": "in", "qty": 100,
                    "note": f"{MARK} rezerv uchun"})
                start = float(db.scalar(S.SUM_SQL, {"id": pid}))
                # Boshqa kartalarning rezervi — sinovning "noli".
                res0 = float(db.query_one(S.AVAILABLE_SQL,
                                          {"id": pid})["reserved"])

                # 1) Erta bosqichda rezerv QO'YILMAYDI: karta hali
                #    "bizniki" emas.
                if was not in S._reservable_statuses():
                    eq("erta bosqichda rezerv -> 400",
                       c.post(f"/erp/opportunities/{oid}/reserves",
                              json={"product_id": pid, "qty": 10}).status_code,
                       400)

                O.set_status(oid, "confirmed", MARK, MARK)
                r = c.post(f"/erp/opportunities/{oid}/reserves", json={
                    "product_id": pid, "qty": 30, "note": f"{MARK} ajratma"})
                eq("rezerv qo'yildi -> 201", r.status_code, 201)
                rid = r.json()["id"]
                eq("rezerv holati", r.json()["status"], "held")
                eq("created_by SESSIYADAN", r.json()["created_by"],
                   TEST_USER["full_name"])

                # 2) ENG MUHIMI: qoldiq O'ZGARMAYDI, mavjud kamayadi.
                #
                # Sonlar FARQ bo'yicha tekshiriladi: bazada boshqa
                # kartalarning rezervi ham bo'lishi mumkin va sinov
                # "faqat men bandman" deb hisoblay olmaydi.
                bal = db.query_one(S.AVAILABLE_SQL, {"id": pid})
                eq("jismoniy qoldiq o'zgarmadi", float(bal["qty"]), start)
                eq("band bo'lgani 30 taga oshdi",
                   float(bal["reserved"]) - res0, 30.0)
                eq("mavjud = qoldiq - rezerv", float(bal["available"]),
                   float(bal["qty"]) - float(bal["reserved"]))

                # 3) Topshirilganda USHLAB TURILADI.
                for st in FIX.yol("submitted"):
                    O.set_status(oid, st, MARK, MARK)
                eq("topshirilgach ham band (farq)",
                   float(db.query_one(S.AVAILABLE_SQL,
                                      {"id": pid})["reserved"]) - res0,
                   30.0)

                # 4) YUTILDI -> chiqimga aylanadi.
                res = O.set_status(oid, "won", MARK, MARK)   # submitted dan
                eq("sarflandi", (res.get("stock") or {}).get("consumed"), 1)
                bal = db.query_one(S.AVAILABLE_SQL, {"id": pid})
                eq("qoldiq kamaydi", float(bal["qty"]), start - 30)
                eq("rezerv bo'shadi (farq)",
                   float(bal["reserved"]) - res0, 0.0)
                rr = next(x for x in c.get(f"/erp/reserves?opportunity_id={oid}"
                                           ).json() if x["id"] == rid)
                eq("rezerv holati: sarflandi", rr["status"], "consumed")
                check(rr["move_id"], "chiqim harakatiga bog'landi")

                # 5) YAKUNIYDAN QAYTISH -> teskari kirim, rezerv tiklanadi.
                #    Chiqim O'CHIRILMAYDI: jurnal sodir bo'lganini yozadi.
                n_before = db.scalar("SELECT count(*) FROM erp.stock_move "
                                     "WHERE product_id = %(p)s", {"p": pid})
                res = O.set_status(oid, "preparing", MARK, "qayta ochildi")
                eq("tiklandi", (res.get("stock") or {}).get("restored"), 1)
                bal = db.query_one(S.AVAILABLE_SQL, {"id": pid})
                eq("qoldiq qaytdi", float(bal["qty"]), start)
                eq("rezerv yana band (farq)",
                   float(bal["reserved"]) - res0, 30.0)
                eq("chiqim O'CHIRILMADI, teskarisi yozildi",
                   db.scalar("SELECT count(*) FROM erp.stock_move "
                             "WHERE product_id = %(p)s", {"p": pid}),
                   n_before + 1)

                # 6) YUTQAZILDI -> bo'shaydi.
                res = O.set_status(oid, "lost", MARK, MARK, lost_reason="price")
                eq("bo'shatildi", (res.get("stock") or {}).get("released"), 1)
                bal = db.query_one(S.AVAILABLE_SQL, {"id": pid})
                eq("qoldiq tegilmadi", float(bal["qty"]), start)
                eq("mavjud tiklandi", float(bal["available"]),
                   start - res0)

                # 7) Yopilgan rezervni qayta bo'shatib bo'lmaydi.
                eq("yopilgan rezervni bo'shatish -> 409",
                   c.delete(f"/erp/reserves/{rid}").status_code, 409)
                eq("yo'q rezerv -> 404",
                   c.delete("/erp/reserves/99999999").status_code, 404)

                # 8) Qo'lda bo'shatish: yozuv O'CHIRILMAYDI.
                O.set_status(oid, "confirmed", MARK, "qayta ochildi")
                r2 = c.post(f"/erp/opportunities/{oid}/reserves", json={
                    "product_id": pid, "qty": 5, "note": f"{MARK} qo'lda"})
                rid2 = r2.json()["id"]
                eq("qo'lda bo'shatish -> 200",
                   c.delete(f"/erp/reserves/{rid2}").status_code, 200)
                gone = next((x for x in c.get("/erp/reserves").json()
                             if x["id"] == rid2), None)
                check(gone is not None, "yozuv o'chirilmadi")
                eq("holati: bo'shatildi", gone and gone["status"], "released")

                # 9) Mavjuddan oshiq rezerv — TAQIQ EMAS, ogohlantirish.
                r3 = c.post(f"/erp/opportunities/{oid}/reserves", json={
                    "product_id": pid, "qty": start + 500,
                    "note": f"{MARK} ortiqcha"})
                eq("ortiqcha rezerv ham o'tadi -> 201", r3.status_code, 201)
                check(r3.json()["warning"], "ogohlantirish qaytdi")
                lst = c.get("/erp/stock").json()
                check(pid in lst["over_reserved"],
                      "ro'yxatda 'butunlay band' deb belgilandi")

                # Kartani joyiga qaytaramiz.
                O.set_status(oid, was, MARK, "sinov tugadi")
                db.execute_returning(
                    "DELETE FROM erp.stock_reserve WHERE opportunity_id=%(i)s "
                    "AND (created_by=%(b)s OR note LIKE %(m)s) RETURNING id",
                    {"i": oid, "b": TEST_USER["full_name"], "m": f"%{MARK}%"})
                db.execute_returning(
                    "DELETE FROM erp.opportunity_history WHERE changed_by=%(m)s "
                    "RETURNING id", {"m": MARK})

            # --- TAKLIF -------------------------------------------------
            head("9. Rezerv taklifi (tender pozitsiyalaridan)")
            # Moslashuv TENDER-AI da bajariladi. Uni sinovda soxta javob
            # bilan almashtiramiz: bu yerda tekshirilayotgan narsa —
            # ERP ning MOSLASHTIRISHI emas, taklifni QANDAY hisoblashi
            # (kerak - ajratilgan = taklif) va hech narsani avtomatik
            # yozmasligi. Tarmoq yo'li smoke-tekshiruvda o'tgan.
            from api import tenderai
            real = tenderai.stock_check
            opp2 = FIX.ensure_opportunity()
            if not opp2:
                print("  SKIP yakuniy bo'lmagan karta yo'q")
            else:
                oid2, was2 = opp2["id"], opp2["status"]
                _cleanup()
                db.execute_returning(
                    "DELETE FROM erp.stock_reserve WHERE opportunity_id=%(i)s "
                    "AND (created_by IN (%(b)s, %(a)s) OR note LIKE %(m)s) "
                    "RETURNING id",
                    {"i": oid2, "b": TEST_USER["full_name"], "a": MARK,
                     "m": f"%{MARK}%"})
                c.post("/erp/stock/moves", json={
                    "product_id": pid, "kind": "in", "qty": 40,
                    "note": f"{MARK} taklif uchun"})

                def fake(tender_id):
                    return {
                        "items": [{
                            "name": "Nasos sotib olish",
                            "amount_text": "10 dona",
                            "required_qty": 10.0,
                            "status": "yetarli",
                            "status_label": "Yetarli",
                            "reason": None,
                            "product": {"id": pid, "name": prod["name"],
                                        "unit": "dona"},
                        }],
                        "unmatched": [{"name": "Boshqa tovar",
                                       "amount_text": "5 dona",
                                       "reason": "Katalogda mos mahsulot yo'q."}],
                        "stock": {"warning": "Qoldiq eskirgan"},
                        "preliminary": True,
                    }

                tenderai.stock_check = fake
                try:
                    O.set_status(oid2, "confirmed", MARK, MARK)
                    r = c.get(f"/erp/opportunities/{oid2}/reserve-suggestions")
                    eq("taklif -> 200", r.status_code, 200)
                    sg = r.json()
                    eq("bitta taklif", len(sg["items"]), 1)
                    it = sg["items"][0]
                    eq("kerakli miqdor tender-ai dan", it["required"], 10.0)
                    eq("hali ajratilmagan", it["held"], 0.0)
                    eq("taklif = kerak - ajratilgan", it["suggest"], 10.0)
                    check(it["can_reserve"], "ajratish mumkin")
                    # Moslashmagan pozitsiya ham ko'rsatiladi: "katalogda
                    # yo'q" degan javob ham ma'lumot.
                    eq("moslashmagan pozitsiya ham qaytdi",
                       len(sg["unmatched"]), 1)
                    # Tender-AI ning ogohlantirishi YASHIRILMAYDI.
                    eq("ogohlantirish uzatildi", sg["warning"],
                       "Qoldiq eskirgan")

                    # HECH NARSA AVTOMATIK YOZILMADI.
                    eq("taklif rezerv YARATMADI",
                       db.scalar("SELECT count(*) FROM erp.stock_reserve "
                                 "WHERE opportunity_id = %(i)s", {"i": oid2}), 0)

                    # Odam tasdiqladi -> bir necha qator birdan.
                    r = c.post(f"/erp/opportunities/{oid2}/reserves/bulk",
                               json=[{"product_id": pid, "qty": 10},
                                     {"product_id": 99999999, "qty": 1}])
                    eq("tasdiq -> 201", r.status_code, 201)
                    res = r.json()
                    eq("bittasi yozildi", res["count"], 1)
                    # Bitta qator o'tmasa QOLGANLARI yoziladi.
                    eq("bittasi xato", res["failed"], 1)
                    check(res["errors"][0]["error"],
                          "xato sababi qaytdi", str(res["errors"][0])[:60])

                    # Ikkinchi marta so'ralganda ALLAQACHON ajratilgani
                    # ayiriladi — ikki marta band qilib qo'ymaslik uchun.
                    sg2 = c.get(f"/erp/opportunities/{oid2}"
                                "/reserve-suggestions").json()
                    it2 = sg2["items"][0]
                    eq("ajratilgani ko'rindi", it2["held"], 10.0)
                    eq("taklif nolga tushdi", it2["suggest"], 0.0)
                    check(not it2["can_reserve"],
                          "qayta ajratish taklif qilinmaydi")
                finally:
                    tenderai.stock_check = real
                    O.set_status(oid2, was2, MARK, "sinov tugadi")
                    db.execute_returning(
                        "DELETE FROM erp.stock_reserve "
                        "WHERE opportunity_id = %(i)s RETURNING id",
                        {"i": oid2})
                    db.execute_returning(
                        "DELETE FROM erp.opportunity_history "
                        "WHERE changed_by = %(m)s RETURNING id", {"m": MARK})

        finally:
            head("10. Tozalash va chegara")
            try:
                FIX.cleanup()
            except Exception:                   # noqa: BLE001
                pass
            n = _cleanup()
            # MUHIMI son emas, QOLDIQ: sinovdan keyin bazada bizning
            # birorta yozuvimiz qolmasligi kerak (rezerv bo'limi o'rtada
            # ham tozalaydi, shuning uchun jami son o'zgaruvchan).
            check(n > 0, f"sinov harakatlari o'chirildi ({n} ta)")
            eq("harakatlardan hech narsa qolmadi",
               db.scalar(f"SELECT count(*) {_MINE_SQL}",
                         {"b": TEST_USER["full_name"], "a": MARK,
                          "m": f"%{MARK}%"}), 0)
            eq("rezervlardan ham hech narsa qolmadi",
               db.scalar("SELECT count(*) FROM erp.stock_reserve "
                         "WHERE created_by IN (%(b)s, %(a)s) OR note LIKE %(m)s",
                         {"b": TEST_USER["full_name"], "a": MARK,
                          "m": f"%{MARK}%"}), 0)
            # ERP `public.*` ga YOZMAYDI — ombor ham istisno emas:
            # katalog o'qiladi, lekin tegilmaydi.
            after = db.query_one(BOUNDARY_SQL)
            eq("catalog_product soni tegilmadi", after["n"], before["n"])
            eq("catalog_product yangilanmadi", after["mx"], before["mx"])
            eq("catalog_product.stock_qty tegilmadi",
               after["with_stock"], before["with_stock"])


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
