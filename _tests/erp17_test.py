"""
BILDIRISHNOMA sinovi — xabar ODAMGA yetadimi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp17_test.py

NIMA UCHUN: yo'naltirish oqimi (`api/erp/topshiriq.py`) karta ochadi,
lekin hodim buni faqat ekranni ochganda ko'rardi. Xabar — o'sha
bo'shliqni yopadi. Va u YO'QOLMASLIGI kerak: eng muhim holat —
karta TAQSIMLANMAGAN bo'lib qolgani, chunki u hech kimning
ro'yxatida ko'rinmaydi.

Tekshiriladi:
  1) HAVOLA QOIDASI: `localhost` manzili xabarga YOZILMAYDI —
     boshqa kompyuterda ochilmaydigan havola buzuq havoladir.
  2) MANZIL: hodimga uning HISOBI orqali; hisobsiz hodimga xabar
     yozilmaydi va bu xato emas.
  3) TAQSIMLANMAGAN karta -> MENEJERGA (menejer yo'q bo'lsa rahbarga)
     — xabar egasiz qolmasin.
  4) O'ZINIKI: har kim faqat o'z xabarini ko'radi va o'qilgan deb
     belgilaydi; begona id yuborilsa hech narsa o'zgarmaydi.
  5) XABAR YOZILMASA ISH TO'XTAMAYDI: `yoz()` chaqiruvchini
     yiqitmaydi.

Belgisi: 'ZZTEST-XAB'. Oxirida hammasi o'chiriladi.
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
from api.erp import xabar as X  # noqa: E402

MARK = "ZZTEST-XAB"

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


def test_sof():
    head("1. Havola qoidasi")
    asl = os.environ.get("ERP_WEB")
    try:
        for manzil in ("http://localhost:5174", "http://127.0.0.1:5174",
                       "http://0.0.0.0:8100", ""):
            os.environ["ERP_WEB"] = manzil
            eq(f"mahalliy manzil havola BERMAYDI ({manzil or 'bo`sh'})",
               X.havola(5), None)
        os.environ["ERP_WEB"] = "https://erp.kompaniya.uz"
        eq("ommaviy manzil havola beradi", X.havola(5),
           "https://erp.kompaniya.uz/?opportunity=5")
    finally:
        if asl is None:
            os.environ.pop("ERP_WEB", None)
        else:
            os.environ["ERP_WEB"] = asl

    # Har tur uchun odam o'qiydigan nomi bo'lishi shart: ekran
    # nishonni shundan tanlaydi.
    check(all(bool(v) for v in X.TURLAR.values()),
          "har hodisa turining nomi bor")


def _tozala(d):
    for uid in (d.get("user"), d.get("menejer")):
        if uid:
            db.execute_returning("DELETE FROM erp.notification "
                                 "WHERE app_user_id = %(u)s RETURNING id",
                                 {"u": uid})
    if d.get("opp"):
        while db.execute_returning("DELETE FROM erp.opportunity_history "
                                   "WHERE opportunity_id = %(o)s RETURNING id",
                                   {"o": d["opp"]}):
            pass
        db.execute_returning("DELETE FROM erp.opportunity WHERE id = %(o)s "
                             "RETURNING id", {"o": d["opp"]})
    for uid in (d.get("user"), d.get("menejer")):
        if uid:
            db.execute_returning("DELETE FROM erp.app_user WHERE id = %(i)s "
                                 "RETURNING id", {"i": uid})
    for bid in (d.get("broker"), d.get("hisobsiz")):
        if bid:
            db.execute_returning("DELETE FROM erp.broker WHERE id = %(i)s "
                                 "RETURNING id", {"i": bid})


def test_db():
    head("2-5. Manzil, taqsimlanmagan, o'ziniki")
    d = {}
    try:
        if not X.schema_ready():
            print("  SKIP schema_patch_erp_22.sql qo'llanmagan")
            return
        d["broker"] = db.execute_returning(
            "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
            {"n": f"{MARK} hodim"})["id"]
        d["hisobsiz"] = db.execute_returning(
            "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
            {"n": f"{MARK} hisobsiz"})["id"]
        d["user"] = db.execute_returning(
            "INSERT INTO erp.app_user (username, full_name, password_hash, "
            "role, broker_id) VALUES ('zztest_xab', %(f)s, 'x', 'broker', "
            "%(b)s) RETURNING id",
            {"f": f"{MARK} hodim", "b": d["broker"]})["id"]
        d["opp"] = db.execute_returning(
            "INSERT INTO erp.opportunity (tender_id, title, broker_id, status) "
            "VALUES (990000031, %(n)s, %(b)s, 'new') RETURNING id",
            {"n": f"{MARK} karta", "b": d["broker"]})["id"]

        # --- 2. MANZIL ---
        r = X.brokerga(d["broker"], "topshiriq", f"{MARK} sizga karta",
                       d["opp"])
        check(bool(r), "hodimga (hisobi orqali) xabar yozildi")
        eq("xabar o'sha hisobga tegishli", r["app_user_id"], d["user"])
        eq("hisobsiz hodimga xabar yozilmaydi",
           X.brokerga(d["hisobsiz"], "topshiriq", "yo'q", d["opp"]), None)
        eq("hodimsiz chaqiruv ham yiqitmaydi",
           X.brokerga(None, "topshiriq", "yo'q"), None)

        # --- 3. TAQSIMLANMAGAN -> menejer (yo'q bo'lsa rahbar) ---
        d["menejer"] = db.execute_returning(
            "INSERT INTO erp.app_user (username, full_name, password_hash, "
            "role) VALUES ('zztest_xab_men', %(f)s, 'x', 'menejer') "
            "RETURNING id", {"f": f"{MARK} menejer"})["id"]
        n = X.menejerlarga("taqsimlanmagan", f"{MARK} taqsimlanmagan",
                           d["opp"])
        check(n >= 1, "menejerga xabar ketdi", str(n))
        eq("menejerning qutisida ko'rinadi",
           any(f"{MARK} taqsimlanmagan" in x["matn"]
               for x in X.royxat(d["menejer"])["items"]), True)

        # --- 4. O'ZINIKI ---
        royxat = X.royxat(d["user"])
        eq("o'z xabari ko'rinadi", len(royxat["items"]) >= 1, True)
        check(all(f"{MARK} taqsimlanmagan" not in x["matn"]
                  for x in royxat["items"]),
              "BEGONA xabar ko'rinmaydi")
        eq("o'qilmaganlar soni", royxat["unread"], len(royxat["items"]))

        # Begona id — hech narsa o'zgarmaydi.
        begona = X.royxat(d["menejer"])["items"][0]["id"]
        eq("begona xabarni o'qilgan deb belgilab bo'lmaydi",
           X.oqildi(d["user"], [begona]), 0)
        eq("begona xabar o'qilmagan qoldi", X.sanoq(d["menejer"]), 1)

        eq("o'zinikini belgilash ishlaydi",
           X.oqildi(d["user"], [r["id"]]), 1)
        eq("hisoblagich kamaydi", X.sanoq(d["user"]),
           len(royxat["items"]) - 1)
        X.oqildi(d["user"])
        eq("hammasini belgilash", X.sanoq(d["user"]), 0)

        # --- 6. MUDDAT ESLATMASI HODIMGA ---
        # Ilgari eslatma FAQAT kompaniya kanaliga (Telegram guruhi)
        # ketardi va odam o'zinikini qidirib topishi kerak edi.
        from api.erp import remind as R
        malumot = {
            "tasks": [{"id": 1, "opportunity_id": d["opp"], "title": "ZZ vazifa",
                       "broker_id": d["broker"], "overdue": True,
                       "opp_title": f"{MARK} karta", "client_name": None}],
            "deadlines": [{"id": d["opp"], "title": f"{MARK} karta",
                           "broker_id": None, "deadline_at": None}],
        }
        n = R._hodimlarga(malumot)
        eq("hodimga muddat xabari ketdi", n, 1)
        check(any("KECHIKKAN" in x["matn"] for x in X.royxat(d["user"])["items"]),
              "kechikkan vazifa OCHIQ belgilanadi")
        # Egasiz muddat — menejerga.
        check(any("Mas'uli yo'q" in x["matn"]
                  for x in X.royxat(d["menejer"])["items"]),
              "egasiz muddat menejerga ketadi")

        # --- 7. QAYTA TAQSIMLASH SO'ROVI ---
        from api.erp import opportunity as O
        try:
            O.taqsimlash_sorovi(d["opp"], "   ", "ZZTEST Broker")
            check(False, "sababsiz so'rov RAD etilishi kerak")
        except Exception as e:                  # noqa: BLE001
            check("majburiy" in str(e).lower(), "sababsiz so'rov rad etiladi",
                  str(e)[:60])
        r3 = O.taqsimlash_sorovi(d["opp"], "Boshqa tenderda bandman",
                                 "ZZTEST Broker")
        check(r3["xabar_ketdi"] >= 1, "so'rov menejerga yetdi")
        check(any("Qayta taqsimlash so'rovi" in x["matn"]
                  for x in X.royxat(d["menejer"])["items"]),
              "menejer qutisida so'rov ko'rinadi")
        tarix = db.query("SELECT note FROM erp.opportunity_history "
                         "WHERE opportunity_id = %(o)s", {"o": d["opp"]})
        check(any("Qayta taqsimlash so'raldi" in (t["note"] or "")
                  for t in tarix), "so'rov TARIXDA qoladi")

        # --- 5. YIQITMAYDI ---
        eq("noma'lum foydalanuvchi -> None",
           X.yoz(99999999, "topshiriq", "yo'q"), None)
        eq("bo'sh matn -> None", X.yoz(d["user"], "topshiriq", ""), None)
        r2 = X.yoz(d["user"], "yolgon_tur", "tur noma'lum")
        eq("noma'lum tur standartga tushadi", r2["kind"], "topshiriq")
    finally:
        head("Tozalash")
        _tozala(d)
        eq("sinov xabarlari qolmadi",
           db.scalar("SELECT count(*) FROM erp.notification "
                     "WHERE matn LIKE %(m)s", {"m": MARK + "%"}), 0)


if __name__ == "__main__":
    try:
        db.init_pool()
        test_sof()
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
