"""
SABAB HUJJATI sinovi (24-patch) — fayl biriktirish va "ulgurmadik" holati.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp19_test.py

NIMA UCHUN: karta yutqazilganda yoki to'xtaganda `lost_reason` faqat
KOD beradi (narx, muddat, hujjat...). "Aynan nima bo'ldi" degan javob
odatda hujjatda bo'ladi va u shu paytgacha hech qayerda saqlanmasdi.

Bu sinov TO'RTTA jimgina buzilish sinfini qo'riqlaydi:

  1) BAYTLAR SIZIB CHIQISHI. Ro'yxat va jurnal 10 MB lik ustunni
     tortib chiqarsa, interfeys sekinlashgani ham, `doc_audit`
     shishgani ham SEZILMASDI. Sinov ikkalasini ham o'lchaydi.
  2) IZSIZ O'CHIRISH. Fayl o'chirilishi MUMKIN (xato yuklash
     tuzatilsin), lekin izsiz emas. Trigger yozganini tekshiramiz —
     jurnalda `actor` NULL bo'lsa, u "ERP dan tashqarida" degan
     MA'NONI bildiradi va o'z yozuvimizni begona qilib ko'rsatardi.
  3) YOLG'ON QAMROV. "42% kartada hujjat bor" degan raqam 2 ta
     kartada ma'nosiz. Minimal namuna 10 dan kam bo'lsa foiz
     BERILMAYDI.
  4) YAKUNIY HOLAT UNUTILISHI. `ulgurmadik` `FINAL` da bo'lmasa
     `stock.on_status_change` rezervni bo'shatmasdi va tovar
     jimgina band bo'lib qolardi.

Belgisi: 'ZZFIX' (fixture) va 'ZZTEST-FAYL'. Oxirida tozalanadi.
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # fixture.py

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

import fixture as FIX  # noqa: E402
from api import db  # noqa: E402
from api.erp import fayl as F  # noqa: E402
from api.erp import opportunity as O  # noqa: E402

MARK = "ZZTEST-FAYL"

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


def xato(fn, *a, **kw):
    """ErpError ni ushlaydi va (kod, matn) qaytaradi."""
    try:
        fn(*a, **kw)
    except O.ErpError as e:
        return e.code, str(e)
    return None, None


# ---------------------------------------------------------------------------
# 1. Sof mantiq — bazasiz
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq (bazasiz)")

    eq("chegara 10 MB", F.MAX_HAJM, 10 * 1024 * 1024)
    check(all(k.startswith(".") and k == k.lower() for k in F.TURLAR),
          "kengaytmalar nuqta bilan va kichik harfda")
    check(".exe" not in F.TURLAR and ".js" not in F.TURLAR,
          "bajariladigan turlar oq ro'yxatda YO'Q")
    eq("kengaytma() katta harfni ham oladi", F.kengaytma("Sabab.PDF"), ".pdf")
    eq("kengaytmasiz nom -> bo'sh", F.kengaytma("sabab"), "")

    # `YOPIQ_HOLATLAR` — statuslar ro'yxatidagi HAQIQIY kodlar bo'lsin.
    # Xato yozilgan kod jimgina "hech qachon mos kelmaydi" ga aylanardi.
    check(all(s in O.STATUS_LABEL for s in F.YOPIQ_HOLATLAR),
          "fayl holatlari status ro'yxatida bor", str(F.YOPIQ_HOLATLAR))
    check(F.YOPIQ_HOLATLAR <= O.FINAL,
          "fayl holatlarining hammasi YAKUNIY")

    # 24-patchning asosiy qarori: `ulgurmadik` yakuniy. Bu shunchaki
    # ro'yxat emas — `stock.on_status_change` shunga qarab rezervni
    # bo'shatadi (`to_status in FINAL`).
    check("ulgurmadik" in O.FINAL, "'ulgurmadik' YAKUNIY")
    check("ulgurmadik" not in O.TIZIM_QOYADI,
          "'ulgurmadik' ni TIZIM qo'ymaydi — faqat odam")
    eq("tizim hech qanday status qo'ymaydi", O.TIZIM_QOYADI, set())


# ---------------------------------------------------------------------------
# 2. Kod va baza bir xil chegarani ushlaydi
# ---------------------------------------------------------------------------
def test_chegara_bazada():
    head("2. Chegara BAZADA ham bor")

    con = db.query_one(
        "SELECT pg_get_constraintdef(c.oid) AS d FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "WHERE n.nspname = 'erp' AND t.relname = 'opportunity_file' "
        "AND pg_get_constraintdef(c.oid) LIKE '%%hajm%%'")
    check(con is not None, "hajm uchun CHECK bor")
    if con:
        check(str(F.MAX_HAJM) in con["d"],
              "bazadagi chegara kod bilan BIR XIL", con["d"])

    idx = db.query_one(
        "SELECT indexdef AS d FROM pg_indexes WHERE schemaname = 'erp' "
        "AND tablename = 'opportunity_file' AND indexdef LIKE '%%UNIQUE%%' "
        "AND indexdef LIKE '%%sha256%%'")
    check(idx is not None, "takror yuklashni to'suvchi UNIQUE bor", str(idx))

    trg = db.query_one(
        "SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'erp' AND c.relname = 'opportunity_file' "
        "AND NOT t.tgisinternal")
    check(trg is not None, "jurnal triggeri ULANGAN", str(trg))

    # `v_tender_status` — tender-ai o'qiydigan shartnoma. Yangi status
    # uning CASE ida bo'lmasa `status_label` NULL bo'lardi.
    lab = db.query_one(
        "SELECT pg_get_viewdef('erp.v_tender_status'::regclass) AS d")
    check("ulgurmadik" in lab["d"],
          "tender-ai view i yangi statusni biladi")


# ---------------------------------------------------------------------------
# 3. Haqiqiy baza
# ---------------------------------------------------------------------------
def test_db():
    head("3. Fayl biriktirish (haqiqiy baza)")

    opp = FIX.ensure_opportunity()
    if not opp:
        print("  SKIP bazada tender yo'q — ETL yurmagan. Fayl sinovi "
              "o'tkazildi (bu XATO emas).")
        return
    oid = opp["id"]

    pdf = b"%PDF-1.4\n" + b"Z" * 5000
    pdf2 = b"%PDF-1.4\n" + b"Q" * 4000

    # --- ochiq kartaga biriktirilmaydi ------------------------------------
    # Izoh bilan: fixture kartasi oldingi yurishdan YAKUNIY holatda
    # qolgan bo'lishi mumkin va undan qaytish izohsiz taqiqlangan.
    O.set_status(oid, "reviewing", MARK, MARK + " qayta ochish")
    kod, matn = xato(F.qosh, oid, "sabab.pdf", pdf, None, MARK)
    eq("ochiq kartaga biriktirilmaydi -> 409", kod, 409)
    check("Ko'rib chiqilmoqda" in (matn or ""),
          "409 hozirgi holatni AYTADI", matn)

    # --- yakunlaymiz: `ulgurmadik` ----------------------------------------
    # SABAB MAJBURIY (24-patch): usiz 400.
    eq("sababsiz yakunlash -> 400",
       xato(O.set_status, oid, "ulgurmadik", MARK, "izoh")[0], 400)
    r = O.set_status(oid, "ulgurmadik", MARK, "muddatga ulgurmadik",
                     lost_reason="deadline")
    eq("sabab saqlandi", r["lost_reason"], "deadline")
    eq("'ulgurmadik' ga o'tdi", r["status"], "ulgurmadik")
    check(r["is_final"], "yakuniy deb belgilandi")
    check(r["closed_at"] is not None, "closed_at qo'yildi")

    try:
        # --- yaroqsiz kiritishlar -----------------------------------------
        eq("yaroqsiz tur -> 400",
           xato(F.qosh, oid, "virus.exe", pdf, None, MARK)[0], 400)
        eq("kengaytmasiz nom -> 400",
           xato(F.qosh, oid, "sabab", pdf, None, MARK)[0], 400)
        eq("bo'sh fayl -> 400",
           xato(F.qosh, oid, "sabab.pdf", b"", None, MARK)[0], 400)
        kod, matn = xato(F.qosh, oid, "katta.pdf",
                         b"z" * (F.MAX_HAJM + 1), None, MARK)
        eq("chegaradan katta -> 400", kod, 400)
        check("MB" in (matn or ""), "xato matni HAJMNI aytadi", matn)

        # --- to'g'ri yuklash ----------------------------------------------
        f1 = F.qosh(oid, "Sabab xati.pdf", pdf, "buyurtmachi xati", MARK)
        eq("hajm yozildi", f1["hajm"], len(pdf))
        eq("sha256 to'g'ri", f1["sha256"], hashlib.sha256(pdf).hexdigest())
        eq("mime kengaytmadan", f1["mime"], "application/pdf")
        eq("kim yuklagani yozildi", f1["created_by"], MARK)
        check("baytlar" not in f1, "JAVOBDA BAYTLAR YO'Q")

        # --- takror ---------------------------------------------------------
        kod, matn = xato(F.qosh, oid, "boshqa nom.pdf", pdf, None, MARK)
        eq("bir xil fayl ikkinchi marta -> 409", kod, 409)
        check("Sabab xati.pdf" in (matn or ""),
              "409 qaysi fayl ekanini aytadi", matn)
        f2 = F.qosh(oid, "Ikkinchi.pdf", pdf2, None, MARK)
        check(f2["id"] != f1["id"], "BOSHQA fayl qabul qilinadi")

        # --- ro'yxat --------------------------------------------------------
        lst = F.royxat(oid)
        eq("ro'yxatda 2 ta", len(lst), 2)
        check(all("baytlar" not in x for x in lst),
              "RO'YXATDA BAYTLAR YO'Q — eng muhim tekshiruv")

        # --- yuklab olish ---------------------------------------------------
        got = F.baytlar_olish(f1["id"])
        eq("yuklab olishda baytlar AYNAN o'sha", got["baytlar"], pdf)
        eq("nomi saqlandi", got["fayl_nom"], "Sabab xati.pdf")

        # --- jurnal ---------------------------------------------------------
        jur = db.query(
            "SELECT action, actor, doc_status, "
            "       length(coalesce(new_value, old_value)) AS n "
            "FROM erp.doc_audit WHERE doc_type = 'karta' AND doc_id = %(i)s "
            "ORDER BY id", {"i": oid})
        check(len(jur) >= 2, "jurnalga yozildi", f"{len(jur)} qator")
        if jur:
            eq("jurnalda aktor bor (NULL emas)", jur[0]["actor"], MARK)
            eq("jurnal kartaning holatini yozdi",
               jur[0]["doc_status"], "ulgurmadik")
            # ENG MUHIM: 5 KB lik fayl jurnalga tushmasin.
            check(max(x["n"] or 0 for x in jur) < 1000,
                  "JURNALDA BAYTLAR YO'Q (yozuv qisqa)",
                  f"eng uzuni {max(x['n'] or 0 for x in jur)} belgi")

        # --- o'chirish ------------------------------------------------------
        F.ochir(f2["id"], MARK)
        eq("o'chgach 1 ta qoldi", len(F.royxat(oid)), 1)
        eq("o'chirilganini qayta o'chirish -> 404",
           xato(F.ochir, f2["id"], MARK)[0], 404)
        och = db.query(
            "SELECT actor FROM erp.doc_audit WHERE doc_type = 'karta' "
            "AND doc_id = %(i)s AND action = 'delete'", {"i": oid})
        check(len(och) == 1 and och[0]["actor"] == MARK,
              "O'CHIRISH IZI JURNALDA QOLDI", str(och))

        # --- qamrov ---------------------------------------------------------
        q = F.qamrov()
        check(q["yopiq_n"] >= 1, "qamrov yopiq kartalarni sanadi", str(q))
        check(q["fayli_bor_n"] >= 1, "fayli borlar sanaldi")
        if q["yopiq_n"] < 10:
            check(q["foiz"] is None,
                  "MINIMAL NAMUNA: 10 dan kam bo'lsa foiz BERILMAYDI",
                  str(q))
    finally:
        db.execute_returning(
            "DELETE FROM erp.opportunity_file WHERE created_by = %(m)s "
            "RETURNING id", {"m": MARK}, actor=MARK)


# ---------------------------------------------------------------------------
# 3b. Eskalatsiya va voronka
# ---------------------------------------------------------------------------
def test_eskalatsiya():
    head("3b. Muddati o'tgan karta ESLATILADI va AJRATIB sanaladi")
    from api.erp import analytics as A
    from api.erp import remind as R
    from api.erp import tasks as T

    data = T.due_reminders()
    check("kechikkan" in data, "eslatma ma'lumotida kechikkanlar bor")
    kech = data.get("kechikkan") or []
    check(all(k["status"] not in O.FINAL for k in kech),
          "kechikkanlar ro'yxatida YOPILGAN karta yo'q")
    check(all((k["kun"] or 0) >= 0 for k in kech),
          "kechikish kunlari manfiy emas")

    # Matnda ko'rinadimi — eslatma OCHIQ aytadimi.
    if kech:
        matn = R.build_message(data)
        check("MUDDATI O'TGAN" in matn,
              "eslatma matnida eskalatsiya bo'limi bor")
        check("yoping" in matn.lower(),
              "matn NIMA QILISHNI aytadi, faqat xabar bermaydi")
        # Ro'yxat cheklangan: 40 qatorlik xabarni hech kim o'qimaydi.
        n_satr = sum(1 for l in matn.splitlines()
                     if l.startswith("  • ") and "kun oldin" in l)
        check(n_satr <= R.MAX_KECHIKKAN,
              f"ro'yxat {R.MAX_KECHIKKAN} ta bilan cheklangan", str(n_satr))

    # Voronka: "hozir ishlanmoqda" va "muddati o'tgan" ARALASHMAYDI.
    rep = A.build()
    for st in rep["stages"]:
        eq(f"{st['code']}: faol + kechikkan = jami",
           st["faol_n"] + st["kechikkan_n"], st["ongoing_n"])
    check(any("kechikkan_n" in st for st in rep["stages"]),
          "tahlil kechikkanlarni AJRATIB beradi")


# ---------------------------------------------------------------------------
# 3c. Sabab majburiyligi
# ---------------------------------------------------------------------------
def test_sabab_majburiy():
    head("3c. Yakunlanmagan holatda SABAB majburiy")

    opp = FIX.ensure_opportunity()
    if not opp:
        print("  SKIP bazada tender yo'q.")
        return
    oid = opp["id"]
    O.set_status(oid, "reviewing", MARK, MARK + " qayta ochish")

    for st in sorted(O.SABAB_HOLATLARI):
        kod, matn = xato(O.set_status, oid, st, MARK, "izoh")
        eq(f"'{st}' sababsiz -> 400", kod, 400)
        check("SABAB" in (matn or ""), f"'{st}': xato SABABNI so'raydi")

    # `won` — bundan tashqarida: "nega yutqazdik" savoli u yerda yo'q.
    check("won" not in O.SABAB_HOLATLARI, "'won' da sabab so'ralmaydi")

    r = O.set_status(oid, "rejected", MARK, "sinov", lost_reason="capacity")
    eq("sabab bilan o'tdi", r["lost_reason"], "capacity")
    O.set_status(oid, "reviewing", MARK, MARK + " tozalash")


# ---------------------------------------------------------------------------
# 4. Endpointlar
# ---------------------------------------------------------------------------
def test_endpoint():
    head("4. Endpointlar")
    from fastapi.testclient import TestClient

    from api import main as _main
    from api.erp import perm as P
    from api.main import app

    user = {"id": 1, "username": "zz", "full_name": MARK, "role": "rahbar",
            "broker_id": None, "active": True, "created_at": None,
            "last_login_at": None, "csrf": "zz"}

    with TestClient(app) as c:
        try:
            app.dependency_overrides[_main.me] = lambda: user

            # TARTIB: `/erp/files/qamrov` `{file_id}` dan OLDIN turishi
            # kerak. Teskarisi bo'lsa "qamrov" `int` ga aylantirilmay
            # 422 berardi — ekranda "yuklanmadi" degan JIM xato.
            r = c.get("/erp/files/qamrov")
            check(r.status_code != 422,
                  "'qamrov' marshruti {file_id} dan OLDIN",
                  f"{r.status_code}: {str(r.json())[:70]}")
            eq("qamrov -> 200", r.status_code, 200)
            check("yopiq_n" in r.json(), "qamrov javobida raqam bor")

            eq("mavjud bo'lmagan fayl -> 404",
               c.get("/erp/files/999999999").status_code, 404)

            # Meta interfeysga chegaralarni AYTADI: ekran o'z lug'atini
            # tutmasin (turlar ro'yxati ikki joyda ajralib ketardi).
            m = c.get("/erp/meta").json()
            check("fayl_ready" in m, "meta: sxema bayrog'i bor")
            eq("meta: turlar serverdan", sorted(m["fayl_turlar"]),
               sorted(F.TURLAR))
            eq("meta: chegara serverdan", m["fayl_max_hajm"], F.MAX_HAJM)
            eq("meta: holatlar serverdan", sorted(m["fayl_holatlar"]),
               sorted(F.YOPIQ_HOLATLAR))
            eq("meta: 10 status", len(m["statuses"]), 10)

            check("karta.fayl" in P.AMALLAR, "huquq matritsasida amal bor")
        finally:
            app.dependency_overrides.pop(_main.me, None)


# ---------------------------------------------------------------------------
# 5. Chegara: public.* ga tegilmadi
# ---------------------------------------------------------------------------
PUBLIC_SQL = """
SELECT (SELECT count(*) FROM public.tender)         AS t_n,
       (SELECT max(fetched_at) FROM public.tender)  AS t_max
"""


def test_chegara(before):
    head("5. Chegara va tozalash")
    # `TestClient` dan chiqishda ilova o'z `shutdown` ini bajaradi va
    # POOLNI YOPADI. Shundan keyingi har so'rov "pool ishga tushmagan"
    # deb yiqilardi — sinovning tozalash qismi umuman bajarilmasdi.
    db.init_pool()
    after = db.query_one(PUBLIC_SQL)
    eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
    eq("public.tender yangilanmadi", after["t_max"], before["t_max"])

    qoldi = db.query_one(
        "SELECT count(*) AS n FROM erp.opportunity_file "
        "WHERE created_by = %(m)s", {"m": MARK})
    eq("sinov fayllari tozalandi", qoldi["n"], 0)
    n = FIX.cleanup()
    check(n >= 0, f"fixture tozalandi ({n} yozuv)")


if __name__ == "__main__":
    test_sof()
    try:
        db.init_pool()
    except Exception as e:                          # noqa: BLE001
        print(f"\n  DIQQAT: bazasiz sinov: {e}")
    else:
        before = db.query_one(PUBLIC_SQL)
        try:
            test_chegara_bazada()
            test_db()
            test_eskalatsiya()
            test_sabab_majburiy()
            test_endpoint()
        finally:
            test_chegara(before)

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
