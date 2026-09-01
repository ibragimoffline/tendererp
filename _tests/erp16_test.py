"""
YO'NALTIRISH sinovi — Tender-AI topshirig'i ish kartasiga aylanadi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp16_test.py
    .venv/Scripts/python.exe _tests/erp16_test.py --e2e    (pastga qarang)

NIMA UCHUN: qaror Tender-AI da, ish esa ERP da edi va o'rtada ODAM
turardi — u tenderni qidirib, kartani qo'lda ochardi. Endi
`public.v_erp_topshiriq` o'qiladi va karta o'zi ochiladi
(`api/erp/topshiriq.py`).

CHEGARA — SINOVGA HAM TEGISHLI
══════════════════════════════
ERP `public.*` ga YOZMAYDI. Bu qoida sinovga ham tegishli
(`_tests/fixture.py` dagi bilan bir xil), shuning uchun bu yerda
topshiriq qatori YARATILMAYDI. Uning o'rniga modulning KIRISH nuqtasi
(`_bitta`) topshiriq DIKTIONARISI bilan chaqiriladi — view dan
o'qilgan qator ham aynan shunday keladi.

To'liq zanjir (Tender-AI yozadi -> ERP o'qiydi) ikki joyda
tekshiriladi:
  * Tender-AI tomonida `_tests/topshiriq_test.py` (yozish, xabar,
    view shakli);
  * shu yerda `--e2e` bayrog'i bilan — u ATAYLAB standart emas:
    bayroq bilan yurganda sinov Tender-AI ROLINI o'ynaydi va
    `public.tender_topshiriq` ga yozadi. Ya'ni chegarani buzish
    ONGLI qaror bo'ladi, tasodif emas.

Tekshiriladi:
  1) XARITA: `own_company.tai_company_id` yo'q bo'lsa modul hech
     narsa qilmaydi va SABABINI aytadi.
  2) KARTA: topshiriqdan karta ochiladi — snapshot, ustuvorlik,
     izoh, muddat, tarix yozuvi va tahlil snapshoti bilan.
  3) TAQSIMLANMAGAN: xaritalanmagan hodim JIMGINA yo'qolmaydi.
  4) TAKRORLANMAYDI: bitta qarordan bitta karta.
  5) BEKOR: qaror qaytarilsa karta O'CHMAYDI, `rejected` bo'ladi.
  6) TAHLIL YANGILANISHI: yangi snapshot qo'shiladi, KARTA
     MAYDONLARI tegilmaydi (hodim ishini bekor qilmaslik uchun).
  7) ISHONCH: yorliq dalildan oshmaydi.

Belgisi: 'ZZTEST-YON'. Oxirida hammasi o'chiriladi.
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
from api.erp import topshiriq as T  # noqa: E402

MARK = "ZZTEST-YON"
E2E = "--e2e" in sys.argv

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


PUBLIC_MAX_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def _topshiriq(tender_id, **kw):
    """View dan keladigan qatorning AYNAN shakli (soxta qator).

    Ustunlar `public.v_erp_topshiriq` bilan bir xil — shakl
    o'zgarsa bu sinov ham yangilanishi kerak va bu ATAYLAB: ikki
    loyiha orasidagi shartnoma jimgina o'zgarmasin."""
    t = {"id": 900001, "company_id": 999001, "routing_id": 900001,
         "tender_id": tender_id, "hodim_app_user_id": None, "hodim_ism": None,
         "yonaltirgan_app_user_id": None, "yonaltirgan_ism": "D. Rashidova",
         "ishonch": "aktor_elon", "ustuvorlik": "high",
         "izoh": f"{MARK} izoh", "muddat": None,
         "tahlil": {"moslik": {"ok": True, "data": {"ball": 0.9}}},
         "yaratilgan_at": None, "bekor_at": None}
    t.update(kw)
    return t


def _tozala(routing_ids, broker_id=None, user_id=None):
    n = 0
    for rid in routing_ids:
        opp = db.query_one("SELECT id FROM erp.opportunity WHERE routing_id = %(r)s",
                           {"r": rid})
        if not opp:
            continue
        db.execute_returning("DELETE FROM erp.opportunity_analysis "
                             "WHERE opportunity_id = %(o)s RETURNING id",
                             {"o": opp["id"]})
        while db.execute_returning("DELETE FROM erp.opportunity_history "
                                   "WHERE opportunity_id = %(o)s RETURNING id",
                                   {"o": opp["id"]}):
            pass
        db.execute_returning("DELETE FROM erp.opportunity WHERE id = %(o)s "
                             "RETURNING id", {"o": opp["id"]})
        n += 1
    if user_id:
        db.execute_returning("DELETE FROM erp.app_user WHERE id = %(i)s "
                             "RETURNING id", {"i": user_id})
    if broker_id:
        db.execute_returning("DELETE FROM erp.broker WHERE id = %(i)s "
                             "RETURNING id", {"i": broker_id})
    return n


def test_xarita():
    head("1. Xarita — sozlanmagan holat JIM QOLMAYDI")
    asl = T.xarita()
    try:
        T.xarita_qoy(None)
        h = T.holat()
        eq("xarita yo'q -> tinglovchi ishlamaydi", h.get("tai_company_id"), None)
        check("tai_company_id" in (h.get("sabab") or ""), "sabab aytiladi",
              str(h.get("sabab"))[:80])
        eq("sync xaritasiz hech narsa qilmaydi",
           T.sync()["holat"], "xarita_yoq")
        eq("tinglovchi xaritasiz boshlanmaydi", T.tingla_boshla(), False)

        # Begona ijarachining topshirig'i — JIMGINA o'tkaziladi.
        T.xarita_qoy(999001)
        eq("boshqa ijarachining topshirig'i o'tkaziladi",
           T.bitta_id(-1)["holat"], "o'tkazildi")
    finally:
        T.xarita_qoy(asl)
    eq("xarita tiklandi", T.xarita(), asl)


def test_karta():
    head("2-7. Topshiriqdan karta")
    before = db.query_one(PUBLIC_MAX_SQL)
    asl = T.xarita()
    routing_ids, broker_id, user_id = [], None, None
    try:
        T.xarita_qoy(999001)
        t = db.query_one("SELECT id FROM public.tender ORDER BY id LIMIT 1")
        if not t:
            print("  SKIP public.tender bo'sh — snapshot olib bo'lmaydi")
            return

        # --- 2. KARTA OCHILADI ---
        top = _topshiriq(t["id"])
        routing_ids.append(top["routing_id"])
        r = T._bitta(top)
        eq("karta yaratildi", r["holat"], "yaratildi")
        opp = O.get(r["opportunity_id"])
        eq("ustuvorlik topshiriqdan", opp["priority"], "high")
        eq("izoh topshiriqdan", opp["note"], f"{MARK} izoh")
        eq("snapshot olindi (tender id)", opp["tender_id"], t["id"])
        check(any("Tender-AI'dan yo'naltirildi" in (h["note"] or "")
                  for h in opp["history"]), "tarixda yo'naltirish yozuvi bor")

        # --- 3. TAQSIMLANMAGAN ---
        eq("xaritalanmagan hodim -> taqsimlanmagan", r["taqsimlanmagan"], True)
        eq("mas'ul yo'q", (opp["broker"] or {}).get("id"), None)
        # Bunday karta hech kimning ro'yxatida ko'rinmaydi —
        # menejer uni FILTR bilan topadi (`unassigned=true`).
        taqsimlanmagan = [x["id"] for x in O.list_(unassigned=True)]
        check(opp["id"] in taqsimlanmagan,
              "taqsimlanmagan filtri kartani topadi", str(taqsimlanmagan[:5]))
        check(opp["id"] not in [x["id"] for x in O.list_(broker_id=-1)],
              "begona hodim filtriga tushmaydi")

        # --- 7. ISHONCH yorlig'i dalildan oshmaydi ---
        row = db.query_one("SELECT assigned_ishonch, routing_id, topshiriq_id, "
                           "tai_company_id, created_by FROM erp.opportunity "
                           "WHERE id = %(i)s", {"i": opp["id"]})
        eq("ishonch saqlandi", row["assigned_ishonch"], "aktor_elon")
        eq("qaror bilan bog'landi", row["routing_id"], top["routing_id"])
        check("(e'lon qilingan)" in (row["created_by"] or ""),
              "yorliq dalildan oshmaydi", str(row["created_by"]))

        # --- TAHLIL SNAPSHOTI ---
        tah = T.tahlil(opp["id"])
        eq("tahlil saqlandi", len(tah), 1)
        eq("tahlil ichidagi ball", tah[0]["payload"]["moslik"]["data"]["ball"], 0.9)

        # --- 4. TAKRORLANMAYDI ---
        r2 = T._bitta(top)
        eq("takror topshiriq ikkinchi karta ochmaydi", r2["holat"], "o'tkazildi")
        eq("karta soni o'zgarmadi",
           db.scalar("SELECT count(*) FROM erp.opportunity "
                     "WHERE routing_id = %(r)s", {"r": top["routing_id"]}), 1)

        # --- 6. TAHLIL YANGILANISHI ---
        yangi = _topshiriq(t["id"], id=900002, ustuvorlik="low",
                           izoh="BOSHQA izoh",
                           tahlil={"moslik": {"ok": True, "data": {"ball": 0.4}}})
        r3 = T._bitta(yangi)
        eq("yangi versiya -> tahlil yangilandi", r3["holat"], "tahlil_yangilandi")
        eq("ikkita snapshot bor", len(T.tahlil(opp["id"])), 2)
        opp2 = O.get(opp["id"])
        # KARTA MAYDONLARI TEGILMAYDI: hodim ularni o'zgartirgan
        # bo'lishi mumkin va Tender-AI qiymatiga qaytarish uning
        # ishini bekor qilardi.
        eq("ustuvorlik TEGILMADI", opp2["priority"], "high")
        eq("izoh TEGILMADI", opp2["note"], f"{MARK} izoh")

        # --- 5. BEKOR ---
        bekor = _topshiriq(t["id"], id=900002, bekor_at="2026-09-02T00:00:00+05")
        r4 = T._bitta(bekor)
        eq("bekor qilindi", r4["holat"], "bekor_qilindi")
        opp3 = O.get(opp["id"])
        eq("karta O'CHMAYDI, rejected bo'ladi", opp3["status"], "rejected")
        check(any("bekor" in (h["note"] or "").lower() for h in opp3["history"]),
              "tarixda bekor sababi bor")
        r5 = T._bitta(bekor)
        eq("takror bekor — o'tkaziladi", r5["holat"], "o'tkazildi")

        # --- 9. MAVJUD KARTA — ikkinchisi ochilmaydi, BOG'LANADI ---
        # Hodim kartani qo'lda ochib qo'ygan bo'lishi mumkin (yoki
        # eski qaror bo'yicha ochilgan). "Bir tender + bir mijoz =
        # bir karta" qoidasi buzilmasin.
        mavjud = _topshiriq(t["id"], id=900004, routing_id=900004)
        routing_ids.append(mavjud["routing_id"])
        r7 = T._bitta(mavjud)
        eq("mavjud karta qarorga bog'landi", r7["holat"], "mavjudga_boglandi")
        eq("ikkinchi karta ochilmadi", r7["opportunity_id"], opp["id"])

        # --- HODIM XARITALANGAN HOLAT (boshqa tender) ---
        t2 = db.query_one("SELECT id FROM public.tender ORDER BY id OFFSET 1 "
                          "LIMIT 1")
        if not t2:
            print("  SKIP ikkinchi tender yo'q")
            return
        broker_id = db.execute_returning(
            "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
            {"n": f"{MARK} hodim"})["id"]
        user_id = db.execute_returning(
            "INSERT INTO erp.app_user (username, full_name, password_hash, "
            "role, broker_id) VALUES ('zztest_yon', %(f)s, 'x', 'broker', "
            "%(b)s) RETURNING id", {"f": f"{MARK} hodim", "b": broker_id})["id"]
        top2 = _topshiriq(t2["id"], id=900003, routing_id=900003,
                          hodim_app_user_id=user_id, hodim_ism=f"{MARK} hodim")
        routing_ids.append(top2["routing_id"])
        r6 = T._bitta(top2)
        eq("xaritalangan hodimga biriktirildi", r6["taqsimlanmagan"], False)
        opp4 = O.get(r6["opportunity_id"])
        eq("mas'ul qo'yildi", (opp4["broker"] or {}).get("id"), broker_id)
    finally:
        head("Tozalash va chegara")
        n = _tozala(routing_ids, broker_id, user_id)
        check(n > 0, f"sinov kartalari o'chirildi ({n} ta)")
        T.xarita_qoy(asl)
        after = db.query_one(PUBLIC_MAX_SQL)
        eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
        eq("public.tender yangilanmadi", after["t_max"], before["t_max"])


def test_e2e():
    """TO'LIQ ZANJIR — sinov Tender-AI ROLINI o'ynaydi.

    ATAYLAB standart emas (`--e2e`): bu yerda `public.*` ga yoziladi
    va chegara qoidasi ONGLI ravishda chetlab o'tiladi."""
    head("8. To'liq zanjir (--e2e)")
    asl = T.xarita()
    tid = None
    try:
        cid = db.scalar("SELECT company_id FROM tender_routing "
                        "GROUP BY company_id ORDER BY count(*) DESC LIMIT 1")
        rid = db.scalar("SELECT id FROM tender_routing WHERE company_id = %(c)s "
                        "AND NOT EXISTS (SELECT 1 FROM tender_topshiriq p "
                        "WHERE p.routing_id = tender_routing.id) LIMIT 1",
                        {"c": cid})
        if not rid:
            print("  SKIP bo'sh yo'naltirish qatori topilmadi")
            return
        row = db.query_one("SELECT tender_id FROM tender_routing WHERE id=%(i)s",
                           {"i": rid})
        T.xarita_qoy(cid)
        tid = db.execute_returning(
            "INSERT INTO tender_topshiriq (company_id, routing_id, tender_id, "
            "ishonch, ustuvorlik, izoh, tahlil) VALUES (%(c)s, %(r)s, %(t)s, "
            "'aktor_elon', 'medium', %(iz)s, '{}'::jsonb) RETURNING id",
            {"c": cid, "r": rid, "t": row["tender_id"],
             "iz": f"{MARK} e2e"})["id"]
        res = T.sync()
        eq("sync ishladi", res["holat"], "ok")
        check(res["yaratildi"] >= 1, "karta ochildi", str(res))
        _tozala([rid])
    finally:
        if tid:
            db.execute_returning("DELETE FROM tender_topshiriq WHERE id = %(i)s "
                                 "RETURNING id", {"i": tid})
        T.xarita_qoy(asl)


if __name__ == "__main__":
    try:
        db.init_pool()
        test_xarita()
        test_karta()
        if E2E:
            test_e2e()
        else:
            print("\n  (--e2e berilmadi: to'liq zanjir sinovi o'tkazib "
                  "yuborildi — u `public.*` ga yozadi)")
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
