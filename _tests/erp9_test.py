"""
DALOLATNOMA (akt) sinovi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp9_test.py

NIMA UCHUN AKT: faktura "qancha to'lash kerak" deydi, dalolatnoma esa
"ish BAJARILDI" deydi. Ikki xil fakt, ikki xil dalil.

Tekshiriladi:
  1) SOF: statuslar kodda va bazadagi CHECK da bir xil; hisob-kitob
     FAKTURANIKI bilan AYNAN bir xil kod bilan bajariladi (ikki xil
     yaxlitlash ikki xil summa degani bo'lardi).
  2) SNAPSHOT: rekvizitlar ko'chiriladi.
  3) FAKTURADAN: qatorlar KO'CHIRILADI (bog'lanmaydi) va qoralama
     fakturadan akt chiqarilmaydi.
  4) MUZLATISH: `draft` dan chiqqach tahrirlanmaydi.
  5) IMZO: `signed` — aktning maqsadi; sana hujjatdan olinadi.
  6) CHEGARA: `public.*` ga yozilmaydi.

Sinov o'z mijozini yaratmaydi va oxirida faqat O'ZI yozganini o'chiradi.
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
from api.erp import act as A  # noqa: E402
from api.erp import invoice as I  # noqa: E402
from api.erp import opportunity as O  # noqa: E402

MARK = "ZZTEST-AKT"
TODAY = dt.date(2026, 8, 21)

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
    head("1. Sof mantiq")
    eq("4 ta status", len(A.STATUSES), 4)
    eq("statuslar takrorlanmaydi", len(A.STATUS_LABEL), len(A.STATUSES))
    # Aktning MAQSADI — imzo. Shunday status bo'lishi shart.
    check("signed" in A.STATUS_LABEL, "'imzolandi' statusi bor")
    eq("tahrirlanadigan holat", A.EDITABLE, "draft")

    # HISOB-KITOB FAKTURANIKI: `act.py` o'z formulasini YOZMAYDI.
    import inspect
    src = inspect.getsource(A)
    check("inv_mod.totals" in src and "inv_mod.shape_line" in src,
          "hisob fakturaning kodidan olinadi")
    check("quantize" not in src,
          "aktda o'z yaxlitlashi YO'Q (ikki xil yaxlitlash = ikki xil summa)")


# ---------------------------------------------------------------------------
# 2-6. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY_SQL = """
SELECT (SELECT count(*) FROM public.tender)          AS n,
       (SELECT max(fetched_at) FROM public.tender)   AS mx
"""


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
    n = 0
    ids = []
    for tbl, cond in (("erp.act", "note = %(m)s OR number LIKE %(p)s"),
                      ("erp.invoice", "note = %(m)s OR number LIKE %(p)s")):
        p = {"m": MARK, "p": f"{MARK}%"}
        rows = db.query(f"SELECT id FROM {tbl} WHERE {cond}", p)
        ids += [r["id"] for r in rows]
        if rows:
            db.execute_returning(
                f"DELETE FROM {tbl} WHERE {cond} RETURNING id", p)
        n += len(rows)
    # Jurnal yozuvlari hujjat bilan CASCADE ketmaydi (FK ataylab yo'q).
    _purge_audit(ids)
    return n


def test_db():
    head("2. Sxema va snapshot")
    from fastapi.testclient import TestClient

    from api.main import app
    _auth_override(app)

    with TestClient(app) as c:
        if not A.schema_ready():
            print("  SKIP schema_patch_erp_12.sql qo'llanmagan")
            return

        before = db.query_one(BOUNDARY_SQL)

        cdef = db.scalar("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'erp.act'::regclass
              AND conname = 'act_status_check'
        """) or ""
        check(all(f"'{code}'" in cdef for code, _ in A.STATUSES),
              "bazadagi CHECK kodda e'lon qilingan 4 statusni qamraydi",
              cdef[:120])
        eq("bazada ortiqcha status yo'q", cdef.count("'"), 2 * len(A.STATUSES))

        # Summalar SAQLANMAYDI — fakturadagi bilan bir xil qoida.
        cols = {r["column_name"] for r in db.query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='erp' AND table_name='act'")}
        check(not (cols & {"total", "amount", "vat_amount"}),
              "aktda 'jami' ustuni YO'Q (u hisob natijasi)")
        # Bank rekvizitlari ham yo'q: akt to'lov hujjati emas.
        check(not (cols & {"client_bank", "client_account", "own_account"}),
              "aktda bank rekvizitlari yo'q (u to'lov hujjati emas)")

        import fixture as FIX
        cl = FIX.ensure_client()
        _cleanup()

        try:
            r = c.post("/erp/acts", json={
                "client_id": cl["id"], "number": f"{MARK}-1",
                "act_date": TODAY.isoformat(), "note": MARK})
            eq("dalolatnoma yaratildi -> 201", r.status_code, 201)
            act = r.json()
            aid = act["id"]
            eq("qoralama holatida", act["status"], "draft")
            eq("rekvizitlar ko'chirildi", act["client"]["name"], cl["name"])
            eq("created_by SESSIYADAN", act["created_by"],
               TEST_USER["full_name"])
            eq("mijozsiz -> 400",
               c.post("/erp/acts", json={"note": MARK}).status_code, 400)

            head("3. Qatorlar va hisob")
            act = c.post(f"/erp/acts/{aid}/lines", json={
                "name": "Montaj ishlari", "qty": 3, "price": 1500000.50,
                "unit": "soat", "vat_rate": 12}).json()
            # AYNAN fakturadagi son: hisob bitta koddan.
            eq("qator summasi fakturanikidek", act["lines"][0]["total"],
               I.line_totals(3, "1500000.50", 12)["total"].__float__())
            eq("jami", act["totals"]["total"], 5040001.68)
            check(act["totals"]["words"], "summa so'z bilan ham bor",
                  str(act["totals"].get("words"))[:40])

            head("4. Fakturadan dalolatnoma")
            inv = c.post("/erp/invoices", json={
                "client_id": cl["id"], "number": f"{MARK}-F",
                "issued_at": TODAY.isoformat(), "note": MARK}).json()
            # QORALAMA fakturadan akt chiqarilmaydi.
            eq("qoralama fakturadan -> 409",
               c.post(f"/erp/invoices/{inv['id']}/act",
                      json={"number": f"{MARK}-A0"}).status_code, 409)

            c.post(f"/erp/invoices/{inv['id']}/lines", json={
                "name": "Nasos", "qty": 2, "price": 500000, "vat_rate": 12})
            c.post(f"/erp/invoices/{inv['id']}/lines", json={
                "name": "Yetkazish", "qty": 1, "price": 100000, "vat_rate": 0})
            c.put(f"/erp/invoices/{inv['id']}/status", json={"status": "issued"})

            r = c.post(f"/erp/invoices/{inv['id']}/act", json={
                "number": f"{MARK}-A1", "act_date": TODAY.isoformat(),
                "note": MARK})
            eq("fakturadan akt -> 201", r.status_code, 201)
            a2 = r.json()
            eq("ikki qator ko'chirildi", a2["filled"]["lines"], 2)
            eq("fakturaga bog'landi", a2["invoice_id"], inv["id"])
            eq("faktura raqami ko'rinadi", a2["invoice_number"], f"{MARK}-F")
            eq("valyuta fakturadan", a2["currency"], inv["currency"])
            inv_full = c.get(f"/erp/invoices/{inv['id']}").json()
            eq("summa fakturaniki bilan bir xil",
               a2["totals"]["total"], inv_full["totals"]["total"])

            # Qatorlar KO'CHIRILGAN, bog'lanmagan: fakturani bekor qilsak
            # ham akt o'z holicha turadi.
            c.put(f"/erp/invoices/{inv['id']}/status",
                  json={"status": "cancelled"})
            a2b = c.get(f"/erp/acts/{a2['id']}").json()
            eq("faktura bekor bo'lsa ham akt qoladi", len(a2b["lines"]), 2)
            eq("akt summasi o'zgarmadi", a2b["totals"]["total"],
               a2["totals"]["total"])
            eq("bekor qilingan fakturadan yangi akt -> 409",
               c.post(f"/erp/invoices/{inv['id']}/act",
                      json={"number": f"{MARK}-A2"}).status_code, 409)

            head("5. Muzlatish va imzo")
            r = c.put(f"/erp/acts/{aid}/status", json={"status": "issued"})
            eq("chiqarildi -> 200", r.status_code, 200)
            check(not r.json()["editable"], "chiqarilgan hujjat muzlatilgan")
            eq("muzlatilganga qator -> 409",
               c.post(f"/erp/acts/{aid}/lines",
                      json={"name": "X", "qty": 1, "price": 1}).status_code, 409)
            eq("muzlatilganni tahrirlash -> 409",
               c.put(f"/erp/acts/{aid}", json={"number": "boshqa"}).status_code,
               409)

            # To'liqmas hujjatni chiqarib bo'lmaydi.
            empty = c.post("/erp/acts",
                           json={"client_id": cl["id"], "note": MARK}).json()
            r = c.put(f"/erp/acts/{empty['id']}/status",
                      json={"status": "issued"})
            eq("to'liqmas akt -> 400", r.status_code, 400)
            check("raqam" in r.json()["detail"], "nima yetishmayotgani aytiladi",
                  r.json()["detail"][:70])

            # IMZO — aktning maqsadi.
            r = c.put(f"/erp/acts/{aid}/status",
                      json={"status": "signed",
                            "signed_at": TODAY.isoformat()})
            eq("imzolandi", r.json()["status"], "signed")
            eq("imzo sanasi hujjatdan", r.json()["signed_at"],
               TODAY.isoformat())

            # Sana berilmasa akt sanasi olinadi.
            a3 = c.post("/erp/acts", json={
                "client_id": cl["id"], "number": f"{MARK}-3",
                "act_date": TODAY.isoformat(), "note": MARK}).json()
            c.post(f"/erp/acts/{a3['id']}/lines",
                   json={"name": "X", "qty": 1, "price": 1000})
            c.put(f"/erp/acts/{a3['id']}/status", json={"status": "issued"})
            r = c.put(f"/erp/acts/{a3['id']}/status", json={"status": "signed"})
            eq("sanasiz imzoda akt sanasi olinadi", r.json()["signed_at"],
               TODAY.isoformat())

            c.put(f"/erp/acts/{a3['id']}/status", json={"status": "cancelled"})
            eq("bekor qilinganni qaytarib bo'lmaydi -> 409",
               c.put(f"/erp/acts/{a3['id']}/status",
                     json={"status": "issued"}).status_code, 409)

            head("6. Ro'yxat va meta")
            lst = c.get(f"/erp/acts?client_id={cl['id']}").json()
            check(len(lst) >= 3, "ro'yxat qaytdi", str(len(lst)))
            byinv = c.get(f"/erp/acts?invoice_id={inv['id']}").json()
            eq("faktura bo'yicha filtr", len(byinv), 1)
            eq("noma'lum status -> 400",
               c.get("/erp/acts?status=yolgon").status_code, 400)
            eq("yo'q akt -> 404", c.get("/erp/acts/99999999").status_code, 404)

            meta = c.get("/erp/meta").json()
            eq("meta: akt tayyor", meta["act_ready"], True)
            eq("meta: statuslar", len(meta["act_statuses"]), 4)

        finally:
            head("7. Tozalash va chegara")
            n = _cleanup()
            check(n > 0, f"sinov hujjatlari o'chirildi ({n} ta)")
            FIX.cleanup()
            eq("qatorlar ham o'chdi (CASCADE)",
               db.scalar("SELECT count(*) FROM erp.act_line l "
                         "WHERE NOT EXISTS (SELECT 1 FROM erp.act a "
                         "WHERE a.id = l.act_id)"), 0)
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
