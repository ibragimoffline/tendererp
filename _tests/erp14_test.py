"""
TIZIM SOZLAMALARI sinovi — huquqning kompaniyaga bog'liq qismi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp14_test.py

NIMA UCHUN: uch qoida har kompaniyada bir xil emas —
"broker kartani o'zi yakunlaydimi", "menejer foydani ko'radimi",
"admin biznes ma'lumotni faqat ko'radimi". Ular kodda o'zgarmas edi;
endi `erp.setting` da (`api/erp/sozlama.py`) va HUQUQQA ta'sir qiladi
(`api/erp/perm.py` -> `SOZLAMAGA_BOGLIQ`).

Sozlama "yozildi" deyish yetarli emas: u ISHLASHI kerak. Shuning uchun
har bir sozlama uchun SO'ROV yuboriladi va javob 200/403 ekani
tekshiriladi.

Tekshiriladi:
  1) STANDART: qiymat berilmagan sozlama kod bergan qiymatda ishlaydi.
  2) YOZISH: kim/qachon yozilgani saqlanadi, kesh darhol yangilanadi.
  3) HUQUQ: uchala sozlama ham endpoint darajasida ta'sir qiladi.
  4) KIRISH: sozlamalar ekrani faqat administratorga.
  5) TOZALASH: sinov o'zgartirgan sozlamalar QAYTARILADI.

DIQQAT: sinov global holatni (sozlamalarni) o'zgartiradi, shuning
uchun oxirida ularni boshlang'ich qiymatiga qaytaradi — yiqilsa ham
(`finally`).
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

from api import auth as A  # noqa: E402
from api import db  # noqa: E402
from api.erp import perm as P  # noqa: E402
from api.erp import sozlama as S  # noqa: E402

MARK = "ZZTEST-SOZ"
TENDER = 990000011

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


def _user(rol, broker_id=None):
    return {"id": 0, "username": "zz", "full_name": "ZZTEST", "role": rol,
            "role_label": A.ROLE_LABEL.get(rol), "broker_id": broker_id,
            "email": None, "active": True, "last_login_at": None, "csrf": "zz"}


def test_sof():
    head("1. Ta'rif va standart qiymatlar")
    eq("uchta sozlama e'lon qilingan", sorted(S.SOZLAMALAR), sorted(
        ["admin_faqat_koradi", "broker_can_close", "menejer_foyda"]))
    for key, (std, nomi, izoh) in S.SOZLAMALAR.items():
        check(isinstance(std, bool), f"{key}: standart qiymat ha/yo'q")
        check(bool(nomi) and bool(izoh), f"{key}: nomi va izohi bor")
    # Har sozlama huquqqa bog'langan bo'lishi kerak — aks holda u
    # "yozib qo'yiladigan, lekin hech narsa qilmaydigan" bayroq.
    boglangan = set(P.SOZLAMAGA_BOGLIQ.values()) | {"admin_faqat_koradi"}
    eq("har sozlama huquqda ishlatiladi",
       sorted(set(S.SOZLAMALAR) - boglangan), [])
    try:
        S.yoq("yolgon_sozlama")
        check(False, "noma'lum sozlama xato berishi kerak")
    except KeyError:
        check(True, "noma'lum sozlama -> KeyError")


def _seed():
    d = {}
    d["broker"] = db.execute_returning(
        "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
        {"n": f"{MARK} hodim"})["id"]
    d["opp"] = db.execute_returning(
        "INSERT INTO erp.opportunity (tender_id, title, broker_id, status) "
        "VALUES (%(t)s, %(n)s, %(b)s, 'submitted') RETURNING id",
        {"t": TENDER, "n": f"{MARK} karta", "b": d["broker"]})["id"]
    return d


def _cleanup(d):
    for sql in ("DELETE FROM erp.opportunity_history WHERE opportunity_id = %(o)s "
                "RETURNING id",
                "DELETE FROM erp.opportunity WHERE id = %(o)s RETURNING id"):
        if d.get("opp"):
            while db.execute_returning(sql, {"o": d["opp"]}):
                pass
    if d.get("broker"):
        db.execute_returning("DELETE FROM erp.broker WHERE id = %(b)s RETURNING id",
                             {"b": d["broker"]})


def test_db():
    head("2. Yozish va kesh")
    from fastapi.testclient import TestClient

    from api import main as _main
    from api.main import app

    d = {}
    # Baza puli ilova ishga tushganda ochiladi — shuning uchun sxema
    # tekshiruvi ham, boshlang'ich qiymatlar ham SHU blok ichida.
    with TestClient(app) as c:
        if not S.schema_ready():
            print("  SKIP schema_patch_erp_18.sql qo'llanmagan")
            return
        S.kesh_tozala()
        # Nafaqat QIYMAT, balki "bazada yozuvi bormidi" ham eslab
        # qolinadi: sinov o'zidan keyin STANDART holatni qoldirishi
        # kerak, aks holda `check_setup.py` "sozlama o'zgartirilgan"
        # deb ko'rsatib turardi.
        oldin = {x["key"]: (x["value"], x["changed"]) for x in S.hammasi()}
        try:
            d = _seed()
            BROKER = _user("broker", d["broker"])

            def kir(u):
                app.dependency_overrides[_main.me] = lambda: u

            r = S.saqla("broker_can_close", False, actor="ZZTEST Sinov")
            eq("yozildi", r["value"], False)
            eq("kim yozgani saqlandi", r["updated_by"], "ZZTEST Sinov")
            eq("standartdan farqli deb belgilandi", r["changed"], True)
            eq("kesh darhol yangilandi", S.yoq("broker_can_close"), False)
            eq("huquq ham darhol o'zgardi",
               P.can(_user("broker"), "karta.yopish"), None)
            check(P.can(_user("broker"), "karta.status") == P.OZ,
                  "oddiy bosqich o'tishi tegilmadi")

            head("3. Sozlama ENDPOINTDA ishlaydi")
            kir(BROKER)
            eq("broker: yakunlash o'chirilgan -> 403",
               c.patch(f"/erp/opportunities/{d['opp']}/status",
                       json={"status": "won"}).status_code, 403)
            eq("broker: oddiy o'tish ochiq",
               c.patch(f"/erp/opportunities/{d['opp']}/status",
                       json={"status": "preparing"}).status_code, 200)

            S.saqla("broker_can_close", True, actor="ZZTEST Sinov")
            eq("broker: yoqilgach yakunlaydi",
               c.patch(f"/erp/opportunities/{d['opp']}/status",
                       json={"status": "won"}).status_code, 200)

            S.saqla("menejer_foyda", False, actor="ZZTEST Sinov")
            kir(_user("menejer"))
            eq("menejer: foyda o'chirilgan -> 403",
               c.get("/erp/profit").status_code, 403)
            S.saqla("menejer_foyda", True, actor="ZZTEST Sinov")
            eq("menejer: foyda yoqilgan -> 200",
               c.get("/erp/profit").status_code, 200)

            S.saqla("admin_faqat_koradi", True, actor="ZZTEST Sinov")
            kir(_user("admin"))
            eq("admin: faqat ko'radi -> kartani tahrirlay olmaydi",
               c.put(f"/erp/opportunities/{d['opp']}",
                     json={"priority": "high"}).status_code, 403)
            eq("admin: ko'rish ochiq qoladi",
               c.get(f"/erp/opportunities/{d['opp']}").status_code, 200)
            eq("admin: tizim ishi o'ziniki",
               c.get("/erp/users").status_code, 200)
            S.saqla("admin_faqat_koradi", False, actor="ZZTEST Sinov")

            head("4. Sozlamalar ekrani — faqat admin")
            kir(_user("admin"))
            r = c.get("/erp/settings")
            eq("admin -> 200", r.status_code, 200)
            eq("uchala sozlama qaytdi", len(r.json()["settings"]),
               len(S.SOZLAMALAR))
            check(all("help" in x and "default" in x
                      for x in r.json()["settings"]),
                  "izoh va standart qiymat ham beriladi")
            eq("admin yozadi",
               c.put("/erp/settings/broker_can_close",
                     json={"value": True}).status_code, 200)
            eq("noma'lum sozlama -> 400",
               c.put("/erp/settings/yolgon", json={"value": True}).status_code,
               400)
            for rol in ("menejer", "rahbar", "broker"):
                kir(_user(rol))
                eq(f"{rol} -> 403", c.get("/erp/settings").status_code, 403)

        finally:
            app.dependency_overrides.pop(_main.me, None)
            head("5. Tozalash")
            for k, (v, bor) in oldin.items():
                if bor:
                    S.saqla(k, v, actor="ZZTEST Sinov")
                else:
                    db.execute_returning(
                        "DELETE FROM erp.setting WHERE key = %(k)s RETURNING key",
                        {"k": k})
            S.kesh_tozala()
            check(all(S.yoq(k) == v for k, (v, _) in oldin.items()),
                  "sozlamalar boshlang'ich holatiga qaytarildi")
            check(all(x["changed"] == oldin[x["key"]][1] for x in S.hammasi()),
                  "bazada ortiqcha yozuv qolmadi")
            _cleanup(d)
            eq("sinov kartasi o'chirildi",
               db.scalar("SELECT count(*) FROM erp.opportunity "
                         "WHERE title LIKE %(m)s", {"m": MARK + "%"}), 0)


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
