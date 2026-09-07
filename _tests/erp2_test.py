"""
ERP 2-bosqich sinovi — mijoz korxonalar bazasi, passport va cheklist ulanishi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp2_test.py

Tekshiriladi:
  1) Passport: to'liq saqlanadi, INN normallashadi, format xato -> 400,
     TAKROR INN -> 409 + mavjud mijoz id si.
  2) Aloqa shaxslari va hujjatlar (qo'shish / tahrirlash / o'chirish).
  3) CHEKLIST ULANISHI — 2-bosqichning asosiy va'dasi:
     `/tenders/{id}/compliance?client_id=N` MIJOZ hujjatlariga qarab ishlaydi,
     parametrsiz esa avvalgidek BROKER kompaniyasining hujjatlariga qarab.
  4) Mijoz sahifasi: kartalari tarixi va yutish foizi.
  5) CHEGARA: `public.*` (shu jumladan `company_document`) o'zgarmaydi —
     mijoz bazasi kompaniya hujjatlarining o'rnini bosmaydi.

Yozuvlar 'ZZTEST ' prefiksi bilan yaratiladi va oxirida TOZALANADI.
Uvicorn ishga tushirilmaydi — TestClient.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # fixture.py

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

import fixture as FIX                   # status yo'li (24-patch)
from dotenv import load_dotenv

load_dotenv()

from api.erp import clients as C  # noqa: E402

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
# Sinov INN'lari — haqiqiy korxonalarniki bilan to'qnashmasligi uchun
# 999 bilan boshlanadi.
INN_A = "999000111"
INN_B = "999000222"

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

    eq("INN: bo'shliq va tire tashlanadi", C._norm_inn(" 999-000-111 "), "999000111")
    eq("INN: bo'sh satr -> None", C._norm_inn("   "), None)
    eq("INN: None -> None", C._norm_inn(None), None)
    for bad in ("12345", "9990001112", "abcdefghi"):
        try:
            C._norm_inn(bad)
            check(False, f"noto'g'ri INN rad etilishi kerak: {bad}")
        except C.ErpError as e:
            eq(f"INN {bad!r} -> 400", e.code, 400)

    eq("_clean: bo'sh satr -> None", C._clean("  "), None)
    eq("_win_rate: 3/1 -> 75", C._win_rate(3, 1), 75)
    eq("_win_rate: hal bo'lgani yo'q -> None", C._win_rate(0, 0), None)

    s = C.shape({"id": 1, "name": "X", "inn": None, "legal_form": "MCHJ",
                 "address_legal": None, "bank_account": None, "bank_mfo": None,
                 "director_name": None, "phone": None, "active": True,
                 "created_at": None, "updated_at": None})
    check("inn" in s["missing"] and "legal_form" not in s["missing"],
          "shape: to'ldirilmagan passport maydonlari sanaladi", str(s["missing"]))


# ---------------------------------------------------------------------------
# 2-5. Haqiqiy baza
# ---------------------------------------------------------------------------
BOUNDARY = [
    ("tender", "fetched_at"),
    ("company_document", "updated_at"),     # BROKER hujjatlari — tegilmasligi shart
    ("company_profile", "updated_at"),
]


def _boundary(db):
    out = {}
    for table, ts in BOUNDARY:
        r = db.query_one(f"SELECT count(*) AS n, max({ts}) AS mx FROM public.{table}")
        out[table] = (r["n"], r["mx"])
    return out


def test_db():
    head("2. Passport va lug'atlar (haqiqiy baza)")
    from fastapi.testclient import TestClient

    from api import db
    from api.main import app

    made = []          # tozalash uchun yaratilgan mijoz id lari
    opps = []

    _auth_override(app)

    with TestClient(app) as c:
        before = _boundary(db)

        if not C.schema_ready():
            check(False, "schema_patch_erp_2.sql bazaga qo'llanmagan")
            return
        check(True, "2-bosqich jadvallari bazada")

        try:
            # --- passport yaratish ------------------------------------------
            body = {
                "name": PREFIX + "Alfa Trade", "inn": " 999-000-111 ",
                "oked": "46900", "legal_form": "MCHJ", "tax_mode": "QQS to'lovchi",
                "address_legal": "Toshkent, Amir Temur 1",
                "address_actual": "Toshkent, Amir Temur 1",
                "bank_name": "Agrobank", "bank_mfo": "00014",
                "bank_account": "20208000900001234001",
                "director_name": "A. Karimov", "phone": "+998901234567",
                "email": "zz@test.uz", "note": PREFIX + "sinov",
            }
            r = c.post("/erp/clients", json=body)
            eq("POST /erp/clients -> 201", r.status_code, 201)
            a = r.json()
            made.append(a["id"])
            eq("INN normallashdi", a["inn"], INN_A)
            eq("bank rekvizitlari saqlandi", a["bank_account"], body["bank_account"])
            eq("to'liq passportda yetishmayotgani yo'q", a["missing"], [])

            # --- INN takrori va formati -------------------------------------
            r = c.post("/erp/clients", json={"name": PREFIX + "Boshqa", "inn": INN_A})
            eq("takror INN -> 409", r.status_code, 409)
            eq("409 detail'da mavjud mijoz id si",
               r.json()["detail"].get("client_id"), a["id"])
            eq("noto'g'ri INN -> 400",
               c.post("/erp/clients", json={"name": PREFIX + "X", "inn": "123"}).status_code, 400)
            eq("nomsiz mijoz -> 400",
               c.post("/erp/clients", json={"name": "   "}).status_code, 400)

            # INN'siz mijoz — qisman UNIQUE indeks NULL larni cheklamaydi
            b = c.post("/erp/clients", json={"name": PREFIX + "INN'siz"}).json()
            made.append(b["id"])
            b2 = c.post("/erp/clients", json={"name": PREFIX + "INN'siz 2"}).json()
            made.append(b2["id"])
            check(b["id"] != b2["id"], "INN'siz ikkita mijoz yonma-yon yashaydi")
            check("inn" in b["missing"], "to'ldirilmagan passport belgilandi")

            # --- tahrirlash --------------------------------------------------
            r = c.put(f"/erp/clients/{b['id']}", json={**body, "name": PREFIX + "INN'siz",
                                                      "inn": INN_B})
            eq("PUT -> 200", r.status_code, 200)
            eq("INN qo'shildi", r.json()["inn"], INN_B)
            r = c.put(f"/erp/clients/{b['id']}", json={"name": PREFIX + "X", "inn": INN_A})
            eq("boshqaning INN'ini olish -> 409", r.status_code, 409)
            eq("mavjud bo'lmagan mijoz -> 404",
               c.put("/erp/clients/999999999", json={"name": "X"}).status_code, 404)

            # --- aloqa shaxslari ---------------------------------------------
            head("3. Aloqa shaxslari va hujjatlar")
            r = c.post(f"/erp/clients/{a['id']}/contacts",
                       json={"full_name": PREFIX + "Buxgalter", "position": "Bosh buxgalter",
                             "phone": "+998901112233", "is_primary": True})
            eq("kontakt qo'shildi -> 201", r.status_code, 201)
            eq("kartada 1 kontakt", len(r.json()["contacts"]), 1)
            cid = r.json()["contacts"][0]["id"]
            r = c.put(f"/erp/client-contacts/{cid}",
                      json={"full_name": PREFIX + "Buxgalter 2", "is_primary": False})
            eq("kontakt tahrirlandi", r.json()["contacts"][0]["full_name"],
               PREFIX + "Buxgalter 2")
            eq("bo'sh ism -> 400",
               c.put(f"/erp/client-contacts/{cid}", json={"full_name": " "}).status_code, 400)
            r = c.delete(f"/erp/client-contacts/{cid}")
            eq("kontakt o'chirildi -> 0 ta qoldi", len(r.json()["contacts"]), 0)

            # --- hujjatlar -----------------------------------------------------
            doc = {"doc_type": "reg_certificate", "name": PREFIX + "Guvohnoma",
                   "number": "AB-1", "issued_at": "2020-01-01", "valid_until": None}
            r = c.post(f"/erp/clients/{a['id']}/documents", json=doc)
            eq("hujjat qo'shildi -> 201", r.status_code, 201)
            did = r.json()["id"]
            eq("muddatsiz hujjat (valid_until=NULL)", r.json()["valid_until"], None)
            r = c.put(f"/erp/client-documents/{did}", json={**doc, "number": "AB-2"})
            eq("hujjat tahrirlandi", r.json()["number"], "AB-2")
            eq("tursiz hujjat -> 400",
               c.post(f"/erp/clients/{a['id']}/documents",
                      json={"doc_type": " ", "name": "x"}).status_code, 400)
            eq("hujjatlar ro'yxati",
               len(c.get(f"/erp/clients/{a['id']}/documents").json()), 1)

            # --- SHABLON VA IMPORT (0.2) --------------------------------------
            # Shablonni tender-ai yasaydi, faylni u tekshiradi, YOZISH ERP'da.
            # Tender-ai ishlamasa bu qism SKIP bo'ladi.
            head("3b. Hujjatlar shabloni va importi")
            tpl = c.get(f"/erp/clients/{a['id']}/documents/template", params={"fmt": "csv"})
            if tpl.status_code == 503:
                print("  SKIP tender-ai ishlamayapti — shablon tekshirilmadi")
            else:
                eq("shablon -> 200", tpl.status_code, 200)
                check(b"Hujjat turi" in tpl.content, "shablonda sarlavha bor",
                      tpl.content[:60].decode("utf-8", "replace"))
                check("attachment" in tpl.headers.get("content-disposition", ""),
                      "shablon fayl sifatida beriladi")

                head_line = tpl.content.decode("utf-8-sig").splitlines()[0]
                filled = "\n".join([
                    head_line,
                    "Litsenziya;" + PREFIX + "Litsenziya;LIC-1;01.02.2026;31.12.2027;;;",
                    "Kafolat xati;" + PREFIX + "Kafolat;KX-1;10.01.2026;;;;",
                    "Ishonchnoma;;IN-1;01.01.2026;;;;",     # NOMI yo'q -> xato qator
                ]).encode("utf-8")
                up = {"file": ("toldirilgan.csv", filled, "text/csv")}

                r = c.post(f"/erp/clients/{a['id']}/documents/import",
                           params={"dry_run": True}, files=up)
                eq("dry-run -> 200", r.status_code, 200)
                res = r.json()
                eq("2 qator qabul qilindi", res["rows_ok"], 2)
                eq("1 qator xato", res["rows_error"], 1)
                eq("bashorat: 2 qo'shiladi", res["inserted"], 2)
                check(any("nomi" in e["column"].lower() for e in res["errors"]),
                      "xato aynan 'Hujjat nomi' ustunida", str(res["errors"][:1]))
                eq("DRY-RUN BAZAGA YOZMADI",
                   len(c.get(f"/erp/clients/{a['id']}/documents").json()), 1)

                r = c.post(f"/erp/clients/{a['id']}/documents/import",
                           params={"dry_run": False}, files=up)
                eq("import -> 200", r.status_code, 200)
                eq("2 hujjat qo'shildi", r.json()["inserted"], 2)
                docs = c.get(f"/erp/clients/{a['id']}/documents").json()
                eq("bazada 3 hujjat (1 eski + 2 yangi)", len(docs), 3)
                lic = next(d for d in docs if d["doc_type"] == "license")
                eq("hujjat turi o'zbekcha nomdan tanildi", lic["name"], PREFIX + "Litsenziya")
                eq("sana kun.oy.yil dan ISO ga o'girildi", lic["valid_until"], "2027-12-31")

                # Takror yuklash — YANGILANADI, takror qo'shilmaydi
                r = c.post(f"/erp/clients/{a['id']}/documents/import",
                           params={"dry_run": False}, files=up)
                eq("takror import: qo'shilmadi", r.json()["inserted"], 0)
                eq("takror import: yangilandi", r.json()["updated"], 2)
                eq("hujjatlar soni o'zgarmadi",
                   len(c.get(f"/erp/clients/{a['id']}/documents").json()), 3)

                r = c.post(f"/erp/clients/{a['id']}/documents/import",
                           files={"file": ("x.csv", b"bu shablon emas", "text/csv")})
                eq("yaroqsiz fayl -> 422", r.status_code, 422)
                check("sarlavha" in str(r.json()["detail"]).lower(),
                      "xato matni sababni aytadi", str(r.json()["detail"])[:80])
                eq("mavjud bo'lmagan mijozga import -> 404",
                   c.post("/erp/clients/999999999/documents/import",
                          params={"dry_run": False}, files=up).status_code, 404)

            # --- CHEKLIST ULANISHI ---------------------------------------------
            # ERP alohida loyiha: cheklist QOIDALARI tender-ai'da qoladi va
            # ERP mijoz hujjatlarini u yerga YUBORADI (api/tenderai.py).
            # Shuning uchun bu qism tender-ai ishlab turishini talab qiladi;
            # ishlamasa SKIP bo'ladi — ERP'ning o'z sinovlari yiqilmasin.
            head("4. Cheklist: mijoz hujjatlari bo'yicha (tender-ai orqali)")
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q")
            else:
                tid = t["id"]
                head("5. Mijoz sahifasi va hisobot")
                brk = c.post("/erp/brokers", json={"full_name": PREFIX + "Broker"}).json()
                take = {"broker_id": brk["id"], "client_id": a["id"], "priority": "medium",
                        "created_by": PREFIX + "Broker"}
                o1 = c.post(f"/erp/tenders/{tid}/take", json=take)
                eq("mijoz nomidan ishga olindi -> 201", o1.status_code, 201)
                opps.append(o1.json()["id"])

                # Mijozsiz karta — cheklist "kompaniya" rejimida bo'lishi kerak
                o2 = c.post(f"/erp/tenders/{tid}/take",
                            json={**take, "client_id": None})
                if o2.status_code == 201:
                    opps.append(o2.json()["id"])

                r = c.get(f"/erp/opportunities/{opps[0]}/compliance")
                if r.status_code == 503:
                    print("  SKIP tender-ai ishlamayapti — cheklist tekshirilmadi")
                else:
                    eq("cheklist -> 200", r.status_code, 200)
                    res = r.json()
                    eq("mijoz rejimi", res["doc_source"], "client")
                    eq("javobda mijoz", res["client"]["id"], a["id"])
                    item = next(i for i in res["items"] if i["doc_type"] == "reg_certificate")
                    eq("mijozda bor hujjat cheklistda 'bor'", item["in_base"], True)
                    eq("hujjat nomi mijozniki", item["document"]["name"], PREFIX + "Guvohnoma")
                    eq("muddatsiz hujjat holati", item["status"], "ok")
                    if len(opps) > 1:
                        res2 = c.get(f"/erp/opportunities/{opps[1]}/compliance").json()
                        eq("mijozsiz karta -> kompaniya rejimi",
                           res2["doc_source"], "company")
                        check(res2["items"][0]["label"] == res["items"][0]["label"],
                              "qoidalar bir xil — bandlar ro'yxati o'zgarmaydi")
                    eq("mavjud bo'lmagan karta -> 404",
                       c.get("/erp/opportunities/999999999/compliance").status_code, 404)

                # `won` ga SAKRAB bo'lmaydi (24-patch): yo'l FIX.yol() da.
                for st in FIX.yol("won"):
                    c.patch(f"/erp/opportunities/{opps[0]}/status",
                            json={"status": st})

                page = c.get(f"/erp/clients/{a['id']}").json()
                eq("mijoz sahifasida 1 karta", page["summary"]["opp_n"], 1)
                eq("yutish foizi 100%", page["summary"]["win_rate"], 100)
                eq("kartalar tarixi ko'rinadi", len(page["opportunities"]), 1)
                eq("kartada mas'ul ko'rsatilgan",
                   page["opportunities"][0]["broker_name"], PREFIX + "Broker")
                # STATUS YORLIG'I SERVERDAN: ekranda `won` emas,
                # "Yutildi" ko'rinishi kerak va ro'yxat frontendда
                # takrorlanmasligi kerak.
                eq("kartada status yorlig'i o'zbekcha",
                   page["opportunities"][0]["status_label"], "Yutildi")
                # RAD ETILGANLAR alohida sanaladi: ular `win_rate`
                # maxrajiga kirmaydi (qatnashmadik — yutqazmadik), lekin
                # ko'rsatilmasa "1 ta karta, yutish 100%" degan qator
                # qayerdan kelgani tushunarsiz qolardi.
                check("rejected_n" in page["summary"],
                      "yig'mada rad etilganlar soni bor",
                      str(page["summary"]))
                eq("rad etilgan yo'q", page["summary"]["rejected_n"], 0)
                if len(opps) > 1:
                    c.patch(f"/erp/opportunities/{opps[1]}/status",
                            json={"status": "rejected"})
                    p2 = c.get(f"/erp/clients/{a['id']}").json()
                    eq("rad etilgan sanaldi", p2["summary"]["rejected_n"],
                       sum(1 for o in p2["opportunities"]
                           if o["status"] == "rejected"))
                    eq("rad etilgan YUTISH FOIZIGA ta'sir qilmadi",
                       p2["summary"]["win_rate"], 100)

                st = c.get("/erp/stats").json()
                row = next(x for x in st["by_client"] if x["id"] == a["id"])
                eq("stats: mijoz kesimida yutish foizi", row["win_rate"], 100)

                lst = c.get("/erp/clients", params={"q": PREFIX.strip()}).json()
                check(any(x["id"] == a["id"] for x in lst), "qidiruv nom bo'yicha ishlaydi")
                lst = c.get("/erp/clients", params={"q": INN_A}).json()
                check(any(x["id"] == a["id"] for x in lst), "qidiruv INN bo'yicha ishlaydi")
                check(next(x for x in lst if x["id"] == a["id"])["won_n"] == 1,
                      "ro'yxatda natija ustunlari to'ldirilgan")

            eq("hujjat o'chirildi -> 204",
               c.delete(f"/erp/client-documents/{did}").status_code, 204)
            eq("o'chirilgan hujjatni qayta o'chirish -> 404",
               c.delete(f"/erp/client-documents/{did}").status_code, 404)

        finally:
            # --- tozalash ------------------------------------------------------
            head("6. Tozalash va chegara")
            for oid in opps:
                db.execute_returning("DELETE FROM erp.opportunity_history "
                                     "WHERE opportunity_id = %(id)s RETURNING id", {"id": oid})
                db.execute_returning("DELETE FROM erp.opportunity WHERE id = %(id)s "
                                     "RETURNING id", {"id": oid})
            db.execute_returning("DELETE FROM erp.broker WHERE full_name LIKE %(p)s "
                                 "RETURNING id", {"p": PREFIX + "%"})
            # client_contact va client_document — ON DELETE CASCADE
            for cid_ in made:
                db.execute_returning("DELETE FROM erp.client_company WHERE id = %(id)s "
                                     "RETURNING id", {"id": cid_})
            left = (db.scalar("SELECT count(*) FROM erp.client_company WHERE name LIKE %(p)s",
                              {"p": PREFIX + "%"})
                    + db.scalar("SELECT count(*) FROM erp.client_document WHERE name LIKE %(p)s",
                                {"p": PREFIX + "%"})
                    + db.scalar("SELECT count(*) FROM erp.client_contact WHERE full_name LIKE %(p)s",
                                {"p": PREFIX + "%"}))
            eq("sinov yozuvlari tozalandi (CASCADE bilan)", left, 0)

            after = _boundary(db)
            for table, _ in BOUNDARY:
                eq(f"public.{table} o'zgarmadi", after[table], before[table])


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: baza sinovi bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
