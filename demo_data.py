"""
DEMO MA'LUMOT — interfeysni to'la holida ko'rish uchun.

    .venv/Scripts/python.exe demo_data.py            # nima yaratilishini ko'rsatadi
    .venv/Scripts/python.exe demo_data.py --yes      # yaratadi
    .venv/Scripts/python.exe cleanup_demo.py --yes   # hammasini o'chiradi

BU ISHLAB CHIQARISH VOSITASI EMAS. Maqsad bitta: bo'sh bazada hamma
ekran bo'sh holatda turadi va interfeysni baholab bo'lmaydi. Har yozuv
`DEMO` belgisi bilan yaratiladi, ya'ni `cleanup_demo.py` uni bitta
buyruq bilan olib tashlaydi.

NIMA QILMAYDI — va bu ataylab:

  * `public.*` ga YOZMAYDI. Katalogdagi tannarx (`cost_price`) ham
    tegilmaydi: u tender-ai niki va uni tozalash skripti tiklay
    olmaydi. Buning o'rniga demo o'z chiqimlariga tannarxni
    `erp.stock_move.unit_cost` da to'g'ridan-to'g'ri qo'yadi.
  * `erp.own_company` ni to'ldirmaydi. Bizning rekvizitlar — egasining
    birinchi qadami (`erp_ishga_tushirish.md` "Birinchi kun") va
    tozalash skripti uni o'chirmaydi, ya'ni demo u yerga yozsa iz
    qolib ketardi.

Shu ikki sabab bilan faktura bosma shakli "rekvizitlar yetishmayapti"
deb chiqadi — bu xato emas, kutilgan holat.
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                   # noqa: BLE001
    pass

from api import db                                  # noqa: E402
from api.erp import act as ACT                      # noqa: E402
from api.erp import contracts as CON                # noqa: E402
from api.erp import invoice as INV                  # noqa: E402
from api.erp import opportunity as OPP              # noqa: E402
from api.erp import stock as STK                    # noqa: E402
from api.erp import tasks as TSK                    # noqa: E402

MARK = "DEMO"
TODAY = dt.date.today()

# Tasodif QAT'IY urug' bilan: demo har safar BIR XIL chiqadi, aks holda
# "kecha boshqacha edi" degan savol paydo bo'lardi.
rnd = random.Random(20260822)

BROKERS = ["DEMO A. Karimov", "DEMO S. Rahimova", "DEMO B. To'xtayev"]

CLIENTS = [
    ("DEMO Toshkent Tibbiyot MChJ", "301234567", True, 12),
    ("DEMO Farg'ona Qurilish AJ", "302345678", True, 12),
    ("DEMO Samarqand Ta'lim MChJ", "303456789", False, 0),
    ("DEMO Buxoro Logistika XK", "304567890", None, None),
]

#: (status, nechta karta, necha oy oldin yopilgan)
PLAN = [
    ("new", 3, None),
    ("preparing", 2, None),
    ("submitted", 2, None),
    ("confirmed", 2, None),
    ("won", 4, 1),
    ("won", 2, 3),
    ("lost", 3, 2),
    ("rejected", 1, 4),
]

TASKS = [
    ("Texnik topshiriqni o'qib chiqish", -3),
    ("Yetkazib beruvchidan narx so'rash", -1),
    ("Bank kafolatini tayyorlash", 0),
    ("Taklifni yakuniy tekshirish", 0),
    ("Mijoz bilan uchrashuv", 2),
    ("Shartnoma loyihasini yuborish", 5),
]


def say(msg: str) -> None:
    print(f"  {msg}")


# ---------------------------------------------------------------------------
def make_brokers() -> list:
    out = []
    for name in BROKERS:
        r = db.query_one("SELECT id, full_name FROM erp.broker "
                         "WHERE full_name = %(n)s", {"n": name})
        if not r:
            r = db.execute_returning(
                "INSERT INTO erp.broker (full_name, email, phone) "
                "VALUES (%(n)s, %(e)s, %(p)s) RETURNING id, full_name",
                {"n": name,
                 "e": name.split()[-1].lower().replace("'", "") + "@demo.uz",
                 "p": "+9989" + str(rnd.randint(10000000, 99999999))})
        out.append(r)
    say(f"hodimlar: {len(out)} ta")
    return out


def make_clients() -> list:
    out = []
    for i, (name, inn, vat, rate) in enumerate(CLIENTS, start=1):
        r = db.query_one("SELECT id, name FROM erp.client_company "
                         "WHERE name = %(n)s", {"n": name})
        if not r:
            r = db.execute_returning("""
                INSERT INTO erp.client_company
                    (name, inn, legal_form, address_legal, bank_name,
                     bank_mfo, bank_account, director_name, phone, email,
                     vat_payer, vat_rate)
                VALUES (%(n)s, %(inn)s, 'MCHJ', %(addr)s, 'Ipoteka Bank',
                        %(mfo)s, %(acc)s, %(dir)s, %(ph)s, %(em)s,
                        %(vat)s, %(rate)s)
                RETURNING id, name""",
                {"n": name, "inn": inn,
                 "addr": f"Toshkent sh., {i}-uy",
                 "mfo": f"0012{i}",
                 "acc": f"2020800000000000000{i}",
                 "dir": f"DEMO Rahbar {i}",
                 "ph": "+99871" + str(1000000 + i),
                 "em": f"demo{i}@example.uz",
                 # NULL = "hali so'ralmagan" — bu holat ham demoda bo'lsin.
                 "vat": vat, "rate": rate})
        out.append(r)
    say(f"mijozlar: {len(out)} ta (biri QQS to'lovchisi emas, biri noma'lum)")
    return out


def make_opportunities(brokers, clients) -> list:
    """Kartalar HAQIQIY tenderlardan olinadi (`O.take`) — snapshot ham
    shu yo'l bilan to'ldiriladi."""
    used = {r["tender_id"] for r in db.query(
        "SELECT tender_id FROM erp.opportunity")}

    # BITTA VALYUTA (UZS): aralash valyutada panel pul yig'indilarini
    # ataylab yashiradi (`erp_foyda.md` 9) va demo "hech narsa
    # ko'rsatmaydi" holatiga tushardi. Aralash holat sinovda tekshiriladi,
    # demoda esa raqamlar ko'rinishi kerak.
    #
    # MUDDATI KELAJAKDA bo'lganlari OCHIQ kartalarga: "yaqin muddatlar"
    # bloki o'tib ketgan tender bilan bo'sh qolardi.
    def pick(where: str, limit: int) -> list:
        return [r["id"] for r in db.query(
            "SELECT id FROM public.tender WHERE totalcost IS NOT NULL "
            "AND upper(coalesce(currency, 'UZS')) LIKE 'UZS%%' "
            f"AND {where} ORDER BY close_at LIMIT {limit}")
            if r["id"] not in used]

    future = pick("close_at > now()", 200)
    past = pick("close_at <= now()", 200)
    if not future:
        say("DIQQAT: muddati kelajakdagi UZS tender yo'q — "
            "'yaqin muddatlar' bloki bo'sh qoladi")

    made = []
    for status, n, months_ago in PLAN:
        for _ in range(n):
            # Ochiq kartaga muddati KELAJAKDAGI tender, yopilganiga —
            # o'tgani: hayotda ham shunday.
            pool = past if months_ago else future
            if not pool:
                pool = future or past
            if not pool:
                say("DIQQAT: bo'sh tender qolmadi, kartalar kam yaratildi")
                return made
            tid = pool.pop(0)
            i = len(made) + 1
            b = brokers[i % len(brokers)]
            c = clients[i % len(clients)]
            try:
                o = OPP.take(tid, {"broker_id": b["id"], "client_id": c["id"],
                                   "priority": rnd.choice(
                                       ["low", "medium", "high"]),
                                   "win_probability": rnd.choice(
                                       [None, 30, 50, 70, 85]),
                                   "created_by": MARK})
            except Exception as e:                  # noqa: BLE001
                say(f"o'tkazib yuborildi (tender {tid}): {e}")
                continue

            # Bosqichma-bosqich o'tkazamiz: tarix (`opportunity_history`)
            # ham to'ladi va "bosqichda qancha turdi" tahlili ishlaydi.
            for st in _path(status):
                OPP.set_status(o["id"], st, MARK,
                               "DEMO: bosqich o'zgardi",
                               lost_reason=("price" if st == "lost" else None))

            if months_ago:
                # Yopilgan sana ORQAGA suriladi — oylik grafik bo'sh
                # bo'lmasin. `set_status` uni `now()` qilib qo'yadi.
                db.execute_returning(
                    "UPDATE erp.opportunity SET closed_at = now() - "
                    "(%(m)s || ' months')::interval WHERE id = %(i)s "
                    "RETURNING id", {"m": months_ago, "i": o["id"]})
            made.append(o)
    say(f"kartalar: {len(made)} ta ({len(PLAN)} bosqich bo'yicha)")
    return made


def _path(target: str) -> list:
    """`new` dan maqsad bosqichgacha bo'lgan yo'l."""
    chain = ["preparing", "submitted", "confirmed", "won"]
    if target == "new":
        return []
    if target == "lost":
        return ["preparing", "submitted", "lost"]
    if target == "rejected":
        return ["rejected"]
    return chain[:chain.index(target) + 1]


def make_tasks(opps) -> int:
    n = 0
    for o in opps[:8]:
        for title, days in rnd.sample(TASKS, 3):
            TSK.add(o["id"], {
                "title": f"{MARK}: {title}",
                "due_at": (TODAY + dt.timedelta(days=days)).isoformat(),
                "created_by": MARK})
            n += 1
    say(f"vazifalar: {n} ta (bir qismi muddati o'tgan)")
    return n


def make_stock(opps) -> int:
    prods = db.query("SELECT id, name FROM public.catalog_product "
                     "ORDER BY id LIMIT 5")
    if not prods:
        say("ombor: katalogda mahsulot yo'q — o'tkazib yuborildi")
        return 0

    n = 0
    for p in prods:
        STK.add_move({"product_id": p["id"], "kind": "opening", "qty": 120,
                      "note": f"{MARK}: boshlang'ich qoldiq",
                      "created_by": MARK})
        STK.add_move({"product_id": p["id"], "kind": "in", "qty": 40,
                      "note": f"{MARK}: yetkazib beruvchidan",
                      "created_by": MARK})
        n += 2

    # TANNARX: katalogga tegmaymiz (`public.*` ga yozmaymiz), shuning
    # uchun uni harakatlarning O'ZIGA qo'yamiz — hayotda uni katalogdan
    # `stock.py` ko'chiradi.
    db.execute_returning(
        "UPDATE erp.stock_move SET unit_cost = 240000 "
        "WHERE created_by = %(m)s AND unit_cost IS NULL RETURNING id",
        {"m": MARK})

    # Rezerv `confirmed` da qo'yiladi (`erp_ombor.md` 9.2).
    conf = [o for o in opps
            if db.scalar("SELECT status FROM erp.opportunity WHERE id=%(i)s",
                         {"i": o["id"]}) == "confirmed"]
    for o in conf:
        for p in prods[:2]:
            STK.add_reserve(o["id"], {"product_id": p["id"], "qty": 6,
                                      "note": f"{MARK}: ajratildi",
                                      "created_by": MARK})
            n += 1

    # YUTILGAN kartalarda tovar SARFLANGAN bo'lishi kerak, aks holda
    # tannarx nol chiqadi va foyda 100% bo'lib ko'rinadi — bu demoni
    # yolg'on qilardi. Shuning uchun ikkita kartaga rezerv qo'yib, keyin
    # `won` ga o'tkazamiz: chiqim va MUZLATILGAN tannarx o'zi paydo
    # bo'ladi (`stock.on_status_change`).
    fresh = [o for o in opps
             if db.scalar("SELECT status FROM erp.opportunity WHERE id=%(i)s",
                          {"i": o["id"]}) == "won"][:3]
    for o in fresh:
        db.execute_returning("UPDATE erp.opportunity SET status='confirmed', "
                             "closed_at=NULL WHERE id=%(i)s RETURNING id",
                             {"i": o["id"]})
        for p in prods[:2]:
            STK.add_reserve(o["id"], {"product_id": p["id"], "qty": 8,
                                      "note": f"{MARK}: sotuvga ajratildi",
                                      "created_by": MARK})
            n += 1
        OPP.set_status(o["id"], "won", MARK, "DEMO: yakunlandi")

    # Chiqimlarga ham tannarx (katalogga TEGMAYMIZ).
    db.execute_returning(
        "UPDATE erp.stock_move SET unit_cost = 240000 "
        "WHERE created_by = %(m)s AND unit_cost IS NULL RETURNING id",
        {"m": MARK})

    say(f"ombor: {n} ta yozuv ({len(prods)} mahsulot, {len(conf)} rezerv, "
        f"{len(fresh)} sarflangan karta)")
    return n


def make_money(opps, clients) -> int:
    """Faktura, to'lov, akt va shartnoma — turli holatlarda."""
    won = [o for o in opps
           if db.scalar("SELECT status FROM erp.opportunity WHERE id=%(i)s",
                        {"i": o["id"]}) == "won"]
    n = 0
    for i, o in enumerate(won[:5], start=1):
        row = db.query_one("SELECT client_id, title, start_price, currency "
                           "FROM erp.opportunity WHERE id = %(i)s",
                           {"i": o["id"]})
        # Faktura summasi TENDER narxidan emas, real yetkazib berish
        # hajmidan: haqiqiy tenderlarning boshlang'ich narxi milliardlab
        # so'm bo'lishi mumkin va u paytda demo "596 mlrd daromad,
        # 11 mln tannarx" degan kulgili raqamni ko'rsatardi.
        price = min(float(row["start_price"] or 40_000_000), 40_000_000)
        inv = INV.create({
            "client_id": row["client_id"], "opportunity_id": o["id"],
            "number": f"{MARK}-F-{i:03d}",
            "issued_at": (TODAY - dt.timedelta(days=20 * i)).isoformat(),
            "due_at": (TODAY - dt.timedelta(days=20 * i - 14)).isoformat(),
            "note": MARK, "created_by": MARK})
        INV.add_line(inv["id"], {
            "name": f"{MARK}: tovar yetkazib berish", "unit": "dona",
            "qty": 20, "price": round(price / 20, 2)}, actor=MARK)
        INV.add_line(inv["id"], {
            "name": f"{MARK}: montaj xizmati", "unit": "xizmat",
            "qty": 1, "price": round(price * 0.05, 2)}, actor=MARK)
        n += 1

        if i == 5:
            continue                                # bittasi QORALAMA qoladi
        INV.set_status(inv["id"], "issued", MARK)

        if i <= 2:                                  # to'liq to'langan
            tot = INV.get(inv["id"])["totals"]["total"]
            INV.add_payment(inv["id"], {
                "paid_at": (TODAY - dt.timedelta(days=20 * i - 5)).isoformat(),
                "amount": tot, "method": "bank",
                "doc_ref": f"{MARK}-PP-{i}", "created_by": MARK})
        elif i == 3:                                # QISMAN to'langan
            tot = INV.get(inv["id"])["totals"]["total"]
            INV.add_payment(inv["id"], {
                "paid_at": (TODAY - dt.timedelta(days=10)).isoformat(),
                "amount": round(tot * 0.4, 2), "method": "bank",
                "doc_ref": f"{MARK}-PP-{i}", "created_by": MARK})

        if i == 1:                                  # akt
            a = ACT.from_invoice(inv["id"], {"number": f"{MARK}-A-{i:03d}",
                                             "act_date": TODAY.isoformat(),
                                             "note": MARK,
                                             "created_by": MARK})
            ACT.set_status(a["id"], "issued", None, MARK)
            ACT.set_status(a["id"], "signed", TODAY.isoformat(), MARK)
            n += 1

    # Shartnomalar
    for i, o in enumerate(won[:2], start=1):
        CON.create(o["id"], {
            "number": f"{MARK}-SH-{i:03d}",
            "signed_at": (TODAY - dt.timedelta(days=30 * i)).isoformat(),
            "amount": 15_000_000, "currency": "UZS",
            "subject": f"{MARK}: tovar yetkazib berish shartnomasi",
            "created_by": MARK})
        n += 1

    say(f"pul hujjatlari: {n} ta (to'langan, qisman, qoralama, akt, shartnoma)")
    return n


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Interfeysni ko'rish uchun DEMO ma'lumot")
    ap.add_argument("--yes", action="store_true",
                    help="haqiqatan yaratish (usiz faqat ro'yxat ko'rsatiladi)")
    a = ap.parse_args()

    print("DEMO MA'LUMOT")
    print("=" * 50)
    if not a.yes:
        print("Quyidagilar yaratiladi (hammasi `DEMO` belgisi bilan):\n")
        print(f"  hodimlar          {len(BROKERS)} ta")
        print(f"  mijozlar          {len(CLIENTS)} ta")
        print(f"  kartalar          {sum(n for _, n, _ in PLAN)} ta")
        print("  vazifalar         ~24 ta")
        print("  ombor             boshlang'ich qoldiq, kirim, rezerv")
        print("  fakturalar        5 ta (to'langan / qisman / qoralama)")
        print("  akt, shartnoma    1 + 2 ta")
        print("\nYaratish:   demo_data.py --yes")
        print("O'chirish:  cleanup_demo.py --yes")
        print("\nDIQQAT: `public.*` ga va `erp.own_company` ga TEGILMAYDI"
              " (sabab fayl boshida).")
        return 0

    db.init_pool()
    if db.scalar("SELECT count(*) FROM erp.opportunity "
                 "WHERE created_by = %(m)s", {"m": MARK}):
        print("Demo ma'lumot allaqachon bor. Avval tozalang:")
        print("  .venv/Scripts/python.exe cleanup_demo.py --yes")
        return 1

    print("yaratilyapti...")
    brokers = make_brokers()
    clients = make_clients()
    opps = make_opportunities(brokers, clients)
    if not opps:
        print("Karta yaratilmadi — bazada bo'sh tender yo'q.")
        return 1
    make_tasks(opps)
    make_stock(opps)
    make_money(opps, clients)

    print("=" * 50)
    print("TAYYOR. http://localhost:5174 — `admin` bilan kiring.")
    print("O'chirish: .venv/Scripts/python.exe cleanup_demo.py --yes")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        try:
            db.close_pool()
        except Exception:                           # noqa: BLE001
            pass
    sys.exit(code)
