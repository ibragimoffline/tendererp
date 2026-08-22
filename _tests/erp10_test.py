"""
ERP sinovi 10 — PUL HUJJATLARI O'ZGARISHLAR JURNALI (audit).

Yurgizish:
    .venv\\Scripts\\python.exe _tests\\erp10_test.py

Bu suite bitta savolga javob beradi: **"chiqarilgan fakturaga
tegilganmi?"** va uni tekshiradigan dalil ishonchlimi.

Sinovning o'zi ATAYLAB to'g'ridan-to'g'ri SQL yozadi: audit qatlamining
butun ma'nosi ilova chetlab o'tilganda ham iz qolishida. Agar sinov
faqat ilova orqali yozsa, u aslida hech narsani tekshirmagan bo'lardi.

Tozalash: jurnal yozuvlari `erp.audit_purge` bayrog'i bilan
o'chiriladi — bayroqni ataylab yoqish shart, tasodifan o'chib
ketmasin.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                   # noqa: BLE001
    pass

from dotenv import load_dotenv

load_dotenv()

from api import db  # noqa: E402
from api.erp import audit as A  # noqa: E402
from api.erp import invoice as I  # noqa: E402

MARK = "ZZTEST-AUDIT"
WHO = "zztest_karimov"
TODAY = dt.date(2026, 8, 22)

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


def _purge(doc_ids):
    """Sinov izlarini jurnaldan o'chirish.

    Bayroq ATAYLAB yoqiladi: jurnal tasodifan o'chib ketmasligi kerak."""
    if not doc_ids:
        return
    with db.get_conn() as cn:
        with cn.cursor() as cur:
            cur.execute("SET LOCAL erp.audit_purge = 'on'")
            cur.execute("DELETE FROM erp.doc_audit WHERE doc_id = ANY(%(ids)s)",
                        {"ids": list(doc_ids)})
        cn.commit()


def main():
    head("1. Sxema")
    db.init_pool()
    if not A.schema_ready():
        print("  SKIP schema_patch_erp_16.sql qo'llanmagan")
        return 0
    check(True, "erp.doc_audit bor")

    # Triggerlar BESH jadvalda ham turibdimi — bittasi tushib qolsa
    # o'sha yo'l jimgina iz qoldirmay qolardi.
    trg = {r["t"] for r in db.query(
        "SELECT tgrelid::regclass::text AS t FROM pg_trigger "
        "WHERE tgname = 'doc_audit_trg'")}
    for t in ("erp.invoice", "erp.invoice_line", "erp.invoice_payment",
              "erp.act", "erp.act_line"):
        check(t in trg, f"{t} da trigger bor")

    import fixture as FIX
    cl = FIX.ensure_client()
    if not cl:
        print("  SKIP mijoz yo'q")
        return 0

    docs = set()
    try:
        head("2. Oddiy hayot: yaratish, qator, chiqarish")
        inv = I.create({"client_id": cl["id"], "number": f"{MARK}-1",
                        "note": MARK, "issued_at": TODAY.isoformat(),
                        "created_by": WHO})
        docs.add(inv["id"])
        I.add_line(inv["id"], {"name": "tovar", "qty": 2, "price": 100000},
                   actor=WHO)
        rows = A.for_document("invoice", inv["id"])
        eq("yaratish va qator yozildi", len(rows), 2)
        check(all(r["actor"] == WHO for r in rows),
              "ism jurnalga tushdi (SET LOCAL erp.actor)",
              str([r["actor"] for r in rows]))
        check(not any(r["outside_erp"] for r in rows),
              "ERP dan qilingan o'zgarish 'tashqarida' deb belgilanmadi")
        check(not any(r["after_issue"] for r in rows),
              "qoralamadagi o'zgarish shubhali emas")

        I.set_status(inv["id"], "issued", WHO)
        rows = A.for_document("invoice", inv["id"])
        st = [r for r in rows if r["field"] == "status"]
        eq("status o'zgarishi yozildi", len(st), 1)
        eq("eski qiymat saqlandi", st[0]["old_value"], "draft")
        eq("yangi qiymat saqlandi", st[0]["new_value"], "issued")
        # "Qoralamadan chiqarildi" o'tishning O'ZI shubhali EMAS:
        # holat o'zgarishdan OLDINGI holat bo'yicha yoziladi.
        check(not st[0]["after_issue"],
              "chiqarish amalining o'zi shubhali deb belgilanmadi",
              str(st[0]["doc_status"]))

        head("3. Ilova qoidasi: chiqarilgan hujjat tahrirlanmaydi")
        try:
            I.update(inv["id"], {"number": "BOSHQA"}, actor=WHO)
            check(False, "chiqarilgan fakturani tahrirlab bo'lmasligi kerak")
        except Exception as e:                      # noqa: BLE001
            check("qoralama" in str(e).lower() or "tahrir" in str(e).lower(),
                  "ilova chiqarilgan fakturani tahrirlashga yo'l bermadi",
                  str(e)[:70])

        head("4. Ilovani CHETLAB O'TISH — asosiy tekshiruv")
        # Bu — audit qatlamining butun sababi. Ilova qoidasi baza
        # darajasida majburlanmagan, ya'ni qo'lda yozilgan `UPDATE`
        # o'tib ketadi. Iz qolishi SHART.
        before = len(A.for_document("invoice", inv["id"]))
        db.execute_returning(
            "UPDATE erp.invoice SET number = %(n)s WHERE id = %(i)s "
            "RETURNING id", {"n": f"{MARK}-SOXTA", "i": inv["id"]})
        rows = A.for_document("invoice", inv["id"])
        eq("qo'lda yozilgan UPDATE ham yozildi", len(rows), before + 1)

        bad = [r for r in rows if r["after_issue"]]
        eq("chiqarilgandan keyingi o'zgarish topildi", len(bad), 1)
        eq("qaysi ustun ekani ma'lum", bad[0]["field"], "number")
        eq("eski qiymat", bad[0]["old_value"], f"{MARK}-1")
        eq("yangi qiymat", bad[0]["new_value"], f"{MARK}-SOXTA")
        check(bad[0]["outside_erp"],
              "ERP dan TASHQARIDA qilingani belgilandi")
        eq("ism yo'q (chunki berilmagan)", bad[0]["actor"], None)

        # HAYOT SIKLI shubhali EMAS: `issued -> paid` hujjatning o'z
        # yo'li. Aks holda har faktura bayroq ostida qolardi va bayroq
        # bir hafta ichida e'tibordan chiqardi.
        life = [r for r in rows
                if r["field"] in ("status", "status_changed_at")]
        check(life and not any(r["after_issue"] for r in life),
              "status o'tishlari shubhali deb belgilanmadi",
              str([(r["field"], r["after_issue"]) for r in life]))

        head("5. Yig'ma javob")
        rep = A.recent(days=1, limit=100)
        check(rep["summary"]["after_issue"] >= 1,
              "yig'mada 'chiqarilgandan keyin' sanaldi",
              str(rep["summary"]))
        check(rep["summary"]["outside_erp"] >= 1,
              "yig'mada 'tashqarida' sanaldi")
        check(not rep["clean"], "'toza' deb belgilanmadi")
        # Faqat shubhalilarini so'rash.
        only = A.recent(days=1, limit=100, only_outside=True)
        check(all(x["outside_erp"] for x in only["items"]),
              "faqat tashqaridagilar filtri ishlaydi")

        head("6. Jurnalning o'zi o'zgarmaydi")
        rid = rows[0]["id"]
        try:
            db.execute_returning("UPDATE erp.doc_audit SET actor = 'boshqa' "
                                 "WHERE id = %(i)s RETURNING id", {"i": rid})
            check(False, "jurnal yozuvini o'zgartirib bo'lmasligi kerak")
        except Exception as e:                      # noqa: BLE001
            check("audit" in str(e).lower(),
                  "jurnal yozuvini O'ZGARTIRIB bo'lmadi", str(e)[:70])
        try:
            db.execute_returning("DELETE FROM erp.doc_audit WHERE id = %(i)s "
                                 "RETURNING id", {"i": rid})
            check(False, "bayroqsiz o'chirib bo'lmasligi kerak")
        except Exception as e:                      # noqa: BLE001
            check("audit_purge" in str(e),
                  "bayroqsiz O'CHIRIB bo'lmadi", str(e)[:70])

        head("7. Hujjat o'chsa ham tarix qoladi")
        n_before = len(A.for_document("invoice", inv["id"]))
        db.execute_returning("DELETE FROM erp.invoice WHERE id = %(i)s "
                             "RETURNING id", {"i": inv["id"]})
        after = A.for_document("invoice", inv["id"])
        # O'chirish ham yoziladi, ya'ni yozuvlar KO'PAYADI.
        check(len(after) > n_before,
              "faktura o'chirilgach ham tarix joyida (va o'chirish yozildi)",
              f"{n_before} -> {len(after)}")
        eq("faktura bazadan ketdi",
           db.scalar("SELECT count(*) FROM erp.invoice WHERE id = %(i)s",
                     {"i": inv["id"]}), 0)

        head("8. To'lov ham kuzatiladi")
        inv2 = I.create({"client_id": cl["id"], "number": f"{MARK}-2",
                         "note": MARK, "issued_at": TODAY.isoformat(),
                         "created_by": WHO})
        docs.add(inv2["id"])
        I.add_line(inv2["id"], {"name": "tovar", "qty": 1, "price": 50000},
                   actor=WHO)
        I.set_status(inv2["id"], "issued", WHO)
        I.add_payment(inv2["id"], {"paid_at": TODAY.isoformat(),
                                   "amount": 50000, "method": "bank",
                                   "created_by": WHO})
        pays = [r for r in A.for_document("invoice", inv2["id"])
                if r["entity"] == "payment"]
        eq("to'lov jurnalga tushdi", len(pays), 1)
        eq("to'lov kim tomonidan", pays[0]["actor"], WHO)
        # To'lov QATORI hujjat holatini o'zgartirmaydi, lekin u
        # chiqarilgan fakturaga qo'shilgani uchun `after_issue` bo'ladi —
        # bu NORMAL va shuning uchun turi ham javobda bor.
        eq("to'lov turi ko'rsatilgan", pays[0]["entity_label"], "To'lov")

    finally:
        head("9. Tozalash va chegara")
        db.execute_returning("DELETE FROM erp.invoice WHERE note = %(m)s "
                             "RETURNING id", {"m": MARK})
        _purge(docs)
        n = db.scalar("SELECT count(*) FROM erp.doc_audit "
                      "WHERE doc_id = ANY(%(ids)s)", {"ids": list(docs)}) \
            if docs else 0
        eq("sinov yozuvlari jurnaldan tozalandi", n, 0)
        try:
            import fixture as FIX2
            FIX2.cleanup()
        except Exception:                           # noqa: BLE001
            pass
        # ERP `public.*` ga YOZMAYDI — audit ham istisno emas.
        # Triggerlar FAQAT `erp.*` jadvallariga qo'yilgan; `public.*` da
        # bitta ham bo'lmasligi kerak.
        eq("public.* da ERP triggeri yo'q",
           db.scalar("SELECT count(*) FROM pg_trigger t "
                     "JOIN pg_class c ON c.oid = t.tgrelid "
                     "JOIN pg_namespace n ON n.oid = c.relnamespace "
                     "WHERE n.nspname = 'public' "
                     "AND t.tgname LIKE %(p)s", {"p": "doc_audit%"}), 0)

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    return 1 if _fail else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        db.close_pool()
    sys.exit(code)
