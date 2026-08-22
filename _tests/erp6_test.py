"""
AUTH sinovi — kirish, himoya, rollar va HODIM hisoblari.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp6_test.py

Boshqa ERP sinovlaridan FARQI: bu yerda bog'liqlik ALMASHTIRILMAYDI —
haqiqiy login qilinadi.

TENDER-AI KERAK EMAS. Hodim hisoblari ERP niki (`erp.app_user`), chunki
odam — ERP ning tushunchasi. Tender-AI esa KOMPANIYA hisobi bilan
kiriladi va uning o'z sinovi bor (`tender-ai/_tests/auth_test.py`).
Auth-1 da bu sinov foydalanuvchilarni tender-ai API'si orqali yaratardi
va u ishlamasa SKIP bo'lardi — endi bunday bog'liqlik yo'q.

Tekshiriladi:
  1) Sof mantiq: rol ierarxiyasi, parol xeshi, `actor()`.
  2) TOKENSIZ: himoyalangan endpointlar 401; ataylab ochiqlari 200.
  3) LOGIN: noto'g'ri parol 401 va xato matni QAYSI BIRI xato ekanini
     AYTMAYDI; to'g'ri parol token beradi.
  4) TOKEN BILAN: endpointlar ochiladi; `/erp/auth/me` kim ekanini aytadi.
  5) ROLLAR: broker rahbar hisobotiga 403; admin 200.
  6) HODIM HISOBLARI: `/erp/users` faqat adminga; bitta hodimga bitta
     hisob; hisob HODIMGA bog'lanadi va `created_by` o'sha hodim ismini
     oladi.
  7) `created_by` SESSIYADAN olinadi — mijoz yuborgan ism E'TIBORGA
     OLINMAYDI.
  8) CHIQISH: token bekor bo'ladi va endpointlar yana 401.
  9) CHEGARA: ERP `public.*` ga yozmaydi — jumladan tender-ai ning
     kompaniya hisobiga (`company_account`) ham tegmaydi.

Sinov hisoblari 'zztest_' prefiksi bilan yaratiladi va oxirida
FAOLSIZLANTIRILADI (o'chirilmaydi — ism tarixda qoladi). Shuning uchun
sinov qayta yurishga chidamli.
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
from api.erp import opportunity as K  # noqa: E402

PREFIX = "zztest_"
PASSWORD = "zzSinov12345"

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


def _clean_attempts():
    """Kirish urinishlari jurnalidan SINOV izlarini o'chirish.

    Bu shunchaki tozalik emas: cheklov 15 daqiqalik oynada ishlaydi,
    ya'ni tozalanmasa sinovni ketma-ket ikki marta yurgizish o'zini
    o'zi bloklab qo'yardi."""
    if not A._attempts_ready():
        return
    db.execute_returning(
        "DELETE FROM erp.login_attempt "
        "WHERE username LIKE %(p)s OR ip <<= '203.0.113.0/24'::inet "
        "RETURNING id", {"p": PREFIX + "%"})


def _seed_user(username, full_name, role, broker_id=None):
    """Hisobni ERP ning O'Z moduli orqali yaratadi.

    Bu chegara buzilishi EMAS: `erp.app_user` — ERP ning o'z jadvali.
    Auth-1 da hisob tender-ai da edi va sinov HTTP orqali yaratishga
    majbur edi.

    QAYTA YURISHGA CHIDAMLI: oldingi yurishdan qolgan hisob qayta
    yoqiladi va paroli tiklanadi."""
    cur = db.query_one(A.USER_BY_NAME_SQL, {"username": username})
    if cur:
        A.update_user(cur["id"], {"full_name": full_name, "role": role,
                                  "broker_id": broker_id, "active": True})
        A.set_password(cur["id"], PASSWORD)
        return A.shape(db.query_one(A.USER_BY_ID_SQL, {"id": cur["id"]}))
    return A.create_user(username, full_name, PASSWORD, role=role,
                         broker_id=broker_id)


def _disable(username):
    row = db.query_one(A.USER_BY_NAME_SQL, {"username": username})
    if not row:
        return False
    # Hisob ATAYLAB o'chirilmaydi: ismi `created_by` / `changed_by` da
    # tarixda qolgan. `active=false` — yozuv qoladi, lekin kira olmaydi.
    A.update_user(row["id"], {"full_name": row["full_name"],
                              "role": row["role"], "broker_id": None,
                              "active": False})
    return True


# ---------------------------------------------------------------------------
# 1. Sof mantiq — bazasiz
# ---------------------------------------------------------------------------
def test_sof():
    head("1. Sof mantiq")

    eq("rol ierarxiyasi", (A.ROLE_RANK["admin"] > A.ROLE_RANK["manager"]
                           > A.ROLE_RANK["broker"]), True)

    user = {"role": "broker", "full_name": "A. Karimov"}
    try:
        A.require_role(user, "manager")
        check(False, "broker rahbar huquqini olmasligi kerak")
    except A.AuthError as e:
        eq("broker -> manager: 403", e.code, 403)
    A.require_role({"role": "admin"}, "manager")
    check(True, "admin rahbar huquqini oladi")

    eq("actor sessiyadan ismni oladi", A.actor(user), "A. Karimov")
    eq("ism bo'lmasa login", A.actor({"username": "karimov"}), "karimov")
    # Hisob hodimga bog'langan bo'lsa HODIM ismi ustun: kartalarda va
    # tarixda bitta ism ko'rinsin.
    eq("hodim ismi ustun",
       A.actor({"full_name": "Hisob nomi", "broker_name": "A. Karimov"}),
       "A. Karimov")

    h = A.hash_password(PASSWORD)
    check(h.startswith("pbkdf2_sha256$"), "parol xeshi formati", h[:20])
    check(PASSWORD not in h, "xeshda ochiq parol YO'Q")
    check(A.verify_password(PASSWORD, h), "to'g'ri parol tasdiqlanadi")
    check(not A.verify_password("boshqa", h), "noto'g'ri parol rad etiladi")
    check(not A.verify_password(PASSWORD, "buzuq-xesh"),
          "buzuq xesh yiqilmaydi, False qaytaradi")
    try:
        A.hash_password("qisqa")
        check(False, "qisqa parol rad etilishi kerak")
    except A.AuthError as e:
        eq("qisqa parol -> 400", e.code, 400)

    try:
        A.verify("")
        check(False, "bo'sh token rad etilishi kerak")
    except A.AuthError as e:
        eq("bo'sh token -> 401", e.code, 401)


# ---------------------------------------------------------------------------
# 2-9. Haqiqiy login
# ---------------------------------------------------------------------------
PROTECTED = ["/erp/opportunities", "/erp/clients", "/erp/contracts",
             "/erp/my-tasks", "/erp/own-company",
             # Auth-3 da yopildi: ilgari uni tender-ai interfeysi
             # brauzerdan chaqirardi va shuning uchun ochiq edi. Endi
             # tender-ai `erp.v_tender_status` VIEW ini o'qiydi.
             "/erp/tenders/1/opportunities"]
PUBLIC = ["/health", "/erp/meta"]

PUBLIC_MAX_SQL = """
SELECT (SELECT count(*) FROM public.company_account)      AS acc,
       (SELECT max(updated_at) FROM public.company_account) AS acc_max,
       (SELECT count(*) FROM public.tender)               AS t_n,
       (SELECT max(fetched_at) FROM public.tender)        AS t_max
"""


def test_db():
    head("2. Kirish va himoya (haqiqiy login)")
    from fastapi.testclient import TestClient

    from api.main import app

    uname, aname = PREFIX + "broker", PREFIX + "admin"
    made = []
    made_brokers = []

    # Baza puli ilova ishga tushganda ochiladi, shuning uchun `before`
    # SNIMKASI ham shu blok ichida olinadi.
    with TestClient(app) as c:
        if not A.schema_ready():
            print("  SKIP schema_patch_erp_6.sql qo'llanmagan")
            return
        before = db.query_one(PUBLIC_MAX_SQL)
        try:
            # --- TOKENSIZ ----------------------------------------------------
            for p in PROTECTED:
                eq(f"tokensiz {p} -> 401", c.get(p).status_code, 401)
            for p in PUBLIC:
                eq(f"ochiq {p} -> 200", c.get(p).status_code, 200)
            # Tender-AI ga boradigan endpoint ham himoyalangan: tokensiz
            # 401 (503 EMAS) - kimlik tender-ai holatiga bog'liq emas.
            eq("tokensiz /erp/document-types -> 401",
               c.get("/erp/document-types").status_code, 401)
            eq("noto'g'ri sarlavha formati -> 401",
               c.get("/erp/clients",
                     headers={"Authorization": "Basic xyz"}).status_code, 401)
            eq("yaroqsiz token -> 401",
               c.get("/erp/clients",
                     headers={"Authorization": "Bearer yolgon-token"}).status_code,
               401)

            # --- LOGIN -------------------------------------------------------
            head("3. Login")
            # Broker hisobi HODIMGA bog'lanadi: `created_by` da hodim ismi
            # chiqishini tekshirish uchun.
            # Hodimni O'ZIMIZ yaratamiz: bazadagi ma'lumotga tayanish
            # demo tozalanganda qamrovni jimgina tushirardi.
            import fixture as FIX
            # Karta ham yaratiladi: "ochiq ishi bor hodimni
            # faolsizlantirib bo'lmaydi" tekshiruvi shunga tayanadi.
            FIX.ensure_opportunity()
            brk = db.query_one("SELECT id, full_name FROM erp.broker "
                               "WHERE active ORDER BY id LIMIT 1")
            _seed_user(uname, "ZZTEST Broker", "broker",
                       broker_id=brk["id"] if brk else None)
            _seed_user(aname, "ZZTEST Admin", "admin")
            made += [uname, aname]

            r = c.post("/erp/auth/login",
                       json={"username": uname, "password": "notogri"})
            eq("noto'g'ri parol -> 401", r.status_code, 401)
            msg = str(r.json()["detail"]).lower()
            check("login yoki parol" in msg,
                  "xato matni QAYSI BIRI xato ekanini aytmaydi", msg[:60])
            eq("mavjud bo'lmagan login -> 401",
               c.post("/erp/auth/login",
                      json={"username": PREFIX + "yoq", "password": PASSWORD}
                      ).status_code, 401)

            r = c.post("/erp/auth/login",
                       json={"username": uname, "password": PASSWORD})
            eq("to'g'ri parol -> 200", r.status_code, 200)
            body = r.json()
            eq("javobda foydalanuvchi", body["user"]["username"], uname)
            check("password" not in str(body).lower(),
                  "javobda parol yoki xesh YO'Q")
            # AUTH-4: sessiya tokeni javob tanasida QAYTMAYDI — u
            # `HttpOnly` cookie'da va sahifadagi JS uni ko'rmaydi.
            check("token" not in body, "javobda sessiya tokeni YO'Q")
            check(body.get("csrf"), "javobda CSRF tokeni bor")
            eq("kirish javobi keshlanmaydi",
               r.headers.get("cache-control"), "no-store")

            # Bearer yo'li API mijozlari uchun qoladi: tokenni MODULDAN
            # olamiz (brauzer uni ko'rmaydi).
            tok = A.login(uname, PASSWORD)["token"]
            check(len(tok) > 20, "token berildi", f"{len(tok)} belgi")
            # Token bazada XESH ko'rinishida: xom token faqat brauzerda.
            eq("xom token bazada saqlanmaydi",
               db.scalar("SELECT count(*) FROM erp.app_session "
                         "WHERE token_hash = %(t)s", {"t": tok}), 0)

            H = {"Authorization": f"Bearer {tok}"}

            # --- TOKEN BILAN -------------------------------------------------
            head("4. Token bilan")
            for p in PROTECTED:
                eq(f"{p} -> 200", c.get(p, headers=H).status_code, 200)
            me = c.get("/erp/auth/me", headers=H).json()
            eq("me: login", me["username"], uname)
            eq("me: rol", me["role"], "broker")
            check("password_hash" not in me, "me javobida xesh yo'q")
            if brk:
                eq("me: bog'langan hodim", me["broker_name"], brk["full_name"])

            # --- ROLLAR ------------------------------------------------------
            head("5. Rollar")
            for p in ("/erp/analytics", "/erp/stats", "/erp/contracts/stats"):
                eq(f"broker {p} -> 403", c.get(p, headers=H).status_code, 403)
            atok = A.login(aname, PASSWORD)["token"]
            AH = {"Authorization": f"Bearer {atok}"}
            for p in ("/erp/analytics", "/erp/stats"):
                eq(f"admin {p} -> 200", c.get(p, headers=AH).status_code, 200)

            # --- HODIM HISOBLARI ---------------------------------------------
            head("6. Hodim hisoblari (/erp/users)")
            eq("broker /erp/users -> 403",
               c.get("/erp/users", headers=H).status_code, 403)
            r = c.get("/erp/users", headers=AH)
            eq("admin /erp/users -> 200", r.status_code, 200)
            rows = r.json()
            check(any(u["username"] == uname for u in rows),
                  "ro'yxatda sinov hisobi bor", f"{len(rows)} ta")
            check(all("password_hash" not in u for u in rows),
                  "ro'yxatda xesh YO'Q")

            new_name = PREFIX + "yangi"
            # Bu hisob HECH NARSA yaratmaydi, ya'ni ismi tarixda yo'q -
            # shuning uchun uni butunlay o'chirish mumkin. Oldingi
            # yurishdan qolgani POST ni 409 qilib qo'yardi.
            db.execute_returning("DELETE FROM erp.app_user "
                                 "WHERE username = %(u)s RETURNING id",
                                 {"u": new_name})
            r = c.post("/erp/users", headers=AH,
                       json={"username": new_name, "full_name": "ZZTEST Yangi",
                             "password": PASSWORD, "role": "manager"})
            eq("hisob yaratildi -> 201", r.status_code, 201)
            made.append(new_name)
            new_id = r.json()["id"]
            eq("yangi hisob roli", r.json()["role"], "manager")
            eq("bir xil login -> 409",
               c.post("/erp/users", headers=AH,
                      json={"username": new_name, "full_name": "X",
                            "password": PASSWORD}).status_code, 409)
            eq("parolsiz yaratish -> 400",
               c.post("/erp/users", headers=AH,
                      json={"username": PREFIX + "parolsiz",
                            "full_name": "X"}).status_code, 400)
            eq("noma'lum rol -> 400",
               c.post("/erp/users", headers=AH,
                      json={"username": PREFIX + "rol", "full_name": "X",
                            "password": PASSWORD,
                            "role": "shoh"}).status_code, 400)
            if brk:
                # Bitta hodimga bitta hisob: aks holda "mening ishlarim"
                # ikki xil javob berardi.
                eq("band hodimga ikkinchi hisob -> 409",
                   c.put(f"/erp/users/{new_id}", headers=AH,
                         json={"full_name": "ZZTEST Yangi", "role": "manager",
                               "broker_id": brk["id"]}).status_code, 409)

            eq("hisob yangilandi",
               c.put(f"/erp/users/{new_id}", headers=AH,
                     json={"full_name": "ZZTEST Yangi 2", "role": "broker"}
                     ).json()["full_name"], "ZZTEST Yangi 2")
            eq("yo'q hisobni yangilash -> 404",
               c.put("/erp/users/99999999", headers=AH,
                     json={"full_name": "X"}).status_code, 404)

            # Parolni ADMIN almashtiradi; har kim O'ZINIKINI ham.
            eq("admin parolni almashtiradi",
               c.put(f"/erp/users/{new_id}/password", headers=AH,
                     json={"password": PASSWORD + "9"}).status_code, 200)
            eq("yangi parol ishlaydi",
               c.post("/erp/auth/login",
                      json={"username": new_name,
                            "password": PASSWORD + "9"}).status_code, 200)
            # Login cookie qo'ydi — keyingi tekshiruvlar Bearer bilan
            # ketishi uchun uni tozalaymiz (aks holda ikki kimlik
            # aralashardi).
            c.cookies.clear()
            eq("eski parol ishlamaydi",
               c.post("/erp/auth/login",
                      json={"username": new_name,
                            "password": PASSWORD}).status_code, 401)
            eq("broker BOSHQANING parolini almashtira olmaydi",
               c.put(f"/erp/users/{new_id}/password", headers=H,
                     json={"password": PASSWORD}).status_code, 403)

            # --- PAROL ALMASHTIRISH (auth-6) --------------------------
            head("6d. Parol: talab va xavfsiz almashtirish")
            # ZAIF parol qabul qilinmaydi — yaratishda ham.
            for bad, why in [("qisqa", "qisqa parol"),
                             ("password123", "ko'p uchraydigan parol"),
                             (PREFIX + "zaif_parol", "login nomi ichida")]:
                try:
                    A.create_user(PREFIX + "zaif", "ZZ Zaif", bad)
                    check(False, f"{why} rad etilishi kerak edi")
                except A.AuthError as e:
                    eq(f"{why} -> 400", e.code, 400)

            pid = _seed_user(PREFIX + "parol", "ZZTEST Parol",
                             "broker")["id"]
            made.append(PREFIX + "parol")

            # Uchta qurilmadan kirgan deb faraz qilamiz.
            ptoks = [A.login(PREFIX + "parol", PASSWORD)["token"]
                     for _ in range(3)]
            eq("uchta sessiya ochildi",
               db.scalar("SELECT count(*) FROM erp.app_session "
                         "WHERE user_id = %(i)s", {"i": pid}), 3)

            NEWPW = PASSWORD + "-yangi"
            # JORIY parolsiz O'ZINIKINI almashtirib bo'lmaydi.
            PH = {"Authorization": f"Bearer {ptoks[0]}"}
            eq("joriy parolsiz -> 400",
               c.put(f"/erp/users/{pid}/password", headers=PH,
                     json={"password": NEWPW}).status_code, 400)
            eq("noto'g'ri joriy parol -> 400",
               c.put(f"/erp/users/{pid}/password", headers=PH,
                     json={"password": NEWPW,
                           "current_password": "notogri"}).status_code, 400)
            # Yangi parol eskisidan farq qilsin.
            eq("yangi = eski -> 400",
               c.put(f"/erp/users/{pid}/password", headers=PH,
                     json={"password": PASSWORD,
                           "current_password": PASSWORD}).status_code, 400)

            r = c.put(f"/erp/users/{pid}/password", headers=PH,
                      json={"password": NEWPW, "current_password": PASSWORD})
            eq("to'g'ri almashtirish -> 200", r.status_code, 200)
            eq("boshqa sessiyalar yopildi", r.json()["closed_sessions"], 2)

            # O'Z sessiyasi QOLADI: odam parol almashtirgani uchun
            # tizimdan chiqib ketmasligi kerak.
            eq("o'z sessiyasi ishlaydi",
               c.get("/erp/auth/me", headers=PH).status_code, 200)
            # BOSHQA sessiyalar esa o'chdi — o'g'irlangan token endi
            # ishlamaydi. Butun amalning ma'nosi shunda.
            eq("boshqa sessiya endi ishlamaydi",
               c.get("/erp/auth/me",
                     headers={"Authorization": f"Bearer {ptoks[1]}"}
                     ).status_code, 401)
            eq("yangi parol bilan kirish ishlaydi",
               c.post("/erp/auth/login",
                      json={"username": PREFIX + "parol",
                            "password": NEWPW}).status_code, 200)
            c.cookies.clear()

            # ADMIN tiklaganda joriy parol so'ralmaydi (bu "unutdim"
            # holati), lekin o'sha hisobning HAMMA sessiyalari o'chadi.
            ptoks2 = [A.login(PREFIX + "parol", NEWPW)["token"]
                      for _ in range(2)]
            r2 = c.put(f"/erp/users/{pid}/password", headers=AH,
                       json={"password": PASSWORD})
            eq("admin joriy parolsiz tiklaydi -> 200", r2.status_code, 200)
            eq("hisobning HAMMA sessiyasi yopildi",
               db.scalar("SELECT count(*) FROM erp.app_session "
                         "WHERE user_id = %(i)s", {"i": pid}), 0)
            eq("admin tiklagach eski token ishlamaydi",
               c.get("/erp/auth/me",
                     headers={"Authorization": f"Bearer {ptoks2[0]}"}
                     ).status_code, 401)
            # Zaif parolni ADMIN ham qo'yolmaydi.
            eq("admin ham zaif parol qo'yolmaydi",
               c.put(f"/erp/users/{pid}/password", headers=AH,
                     json={"password": "1234"}).status_code, 400)

            r = c.get("/erp/auth/roles")
            eq("rollar ro'yxati -> 200", r.status_code, 200)
            eq("uch rol", len(r.json()["roles"]), 3)
            eq("kodlar bazadagi CHECK bilan bir xil",
               sorted(x["code"] for x in r.json()["roles"]),
               sorted(A.ROLE_RANK))

            # --- HODIMLAR EKRANI ---------------------------------------------
            head("6b. Hodimlar ekrani (/erp/staff)")
            eq("broker /erp/staff -> 403",
               c.get("/erp/staff", headers=H).status_code, 403)
            r = c.get("/erp/staff", headers=AH)
            eq("admin /erp/staff -> 200", r.status_code, 200)
            data = r.json()
            check("staff" in data and "unlinked_users" in data,
                  "hodimlar va bog'lanmagan hisoblar alohida qaytadi",
                  str(list(data))[:60])
            check(all("password" not in str(x).lower() for x in data["staff"]),
                  "ro'yxatda parol/xesh YO'Q")
            if brk:
                row = next((x for x in data["staff"] if x["id"] == brk["id"]), None)
                check(row is not None, "hodim ro'yxatda bor")
                check(row and row["user"] and row["user"]["username"] == uname,
                      "hodim qatorida uning HISOBI ham ko'rinadi",
                      str(row and row["user"]))
                check(row and row["opp_count"] >= 0 and row["open_tasks"] >= 0,
                      "ish hajmi ko'rsatiladi (karta va vazifa soni)")
            check(all(u["broker_id"] is None for u in data["unlinked_users"]),
                  "bog'lanmagan ro'yxatda faqat hodimsiz hisoblar")
            check(any(u["username"] == aname for u in data["unlinked_users"]),
                  "sinov admini bog'lanmaganlar ro'yxatida")

            # Hodimni tahrirlash — ADMIN ishi. Tez qo'shish (POST) esa
            # "Ishga olish" formasidan har kimga ochiq.
            nb = c.post("/erp/brokers", headers=H,
                        json={"full_name": PREFIX + "Hodim"}).json()
            made_brokers.append(nb["id"])
            eq("broker hodimni tahrirlay olmaydi -> 403",
               c.put(f"/erp/brokers/{nb['id']}", headers=H,
                     json={"full_name": "X"}).status_code, 403)
            r = c.put(f"/erp/brokers/{nb['id']}", headers=AH,
                      json={"full_name": PREFIX + "Hodim 2",
                            "phone": "+998900000000"})
            eq("admin hodimni tahrirladi", r.status_code, 200)
            eq("yangi ism saqlandi", r.json()["full_name"], PREFIX + "Hodim 2")
            eq("yo'q hodim -> 404",
               c.put("/erp/brokers/99999999", headers=AH,
                     json={"full_name": "X"}).status_code, 404)
            eq("bo'sh ism -> 400",
               c.put(f"/erp/brokers/{nb['id']}", headers=AH,
                     json={"full_name": "   "}).status_code, 400)
            eq("ishsiz hodimni faolsizlantirish mumkin",
               c.put(f"/erp/brokers/{nb['id']}", headers=AH,
                     json={"full_name": PREFIX + "Hodim 2",
                           "active": False}).json()["active"], False)
            if brk:
                # Ochiq ishi borni faolsizlantirib bo'lmaydi: karta va
                # vazifalar ko'rinmas mas'ulga qolib ketardi.
                busy_brk = db.query_one(
                    "SELECT b.id, b.full_name FROM erp.broker b "
                    "JOIN erp.opportunity o ON o.broker_id = b.id "
                    "WHERE b.active AND o.status <> ALL(%(final)s) LIMIT 1",
                    {"final": sorted(K.FINAL)})
                if busy_brk:
                    # Ism O'ZGARTIRILMAY yuboriladi: sinov haqiqiy hodim
                    # yozuvini buzmasligi kerak.
                    eq("ochiq ishi borni faolsizlantirib bo'lmaydi -> 409",
                       c.put(f"/erp/brokers/{busy_brk['id']}", headers=AH,
                             json={"full_name": busy_brk["full_name"],
                                   "active": False}).status_code, 409)
                    eq("rad etilgandan keyin hodim ismi o'zgarmagan",
                       db.scalar("SELECT full_name FROM erp.broker "
                                 "WHERE id = %(id)s", {"id": busy_brk["id"]}),
                       busy_brk["full_name"])

            # --- "MENING ISHLARIM" SESSIYADAN --------------------------------
            head("6c. Mening ishlarim (sessiyadagi hodim)")
            r = c.get("/erp/my-tasks", headers=H)
            eq("my-tasks -> 200", r.status_code, 200)
            mt = r.json()
            if brk:
                # Ekranning nomi "MENING ishlarim": ro'yxatdan o'zini
                # qidirib topish kerak emas.
                eq("sukut bo'yicha O'ZINIKI", mt["broker_id"], brk["id"])
                eq("interfeys uchun: kim kirgan", mt["self_broker_id"], brk["id"])
                eq("everyone=true -> hammaniki",
                   c.get("/erp/my-tasks?everyone=true", headers=H).json()["broker_id"],
                   None)
                eq("aniq hodim so'ralsa o'sha",
                   c.get(f"/erp/my-tasks?broker_id={brk['id']}",
                         headers=H).json()["broker_id"], brk["id"])
            # Admin hisobi hodimga bog'lanmagan — u holda sukut hammaniki.
            am = c.get("/erp/my-tasks", headers=AH).json()
            eq("hodimsiz hisob -> hammaniki", am["broker_id"], None)
            eq("hodimsiz hisob: self yo'q", am["self_broker_id"], None)

            # --- created_by SESSIYADAN ---------------------------------------
            head("7. created_by sessiyadan")
            t = db.query_one("SELECT id FROM tender ORDER BY id LIMIT 1")
            if not t:
                print("  SKIP bazada tender yo'q")
            else:
                want = brk["full_name"] if brk else "ZZTEST Broker"
                cl = c.post("/erp/clients", json={"name": "ZZTEST Mijoz auth"},
                            headers=H).json()
                r = c.post(f"/erp/tenders/{t['id']}/take", headers=H, json={
                    "client_id": cl["id"], "priority": "medium",
                    # MIJOZ yolg'on ism yuboradi — e'tiborga OLINMASLIGI kerak
                    "created_by": "BOSHQA ODAM"})
                eq("ishga olindi -> 201", r.status_code, 201)
                opp = r.json()
                eq("created_by sessiyadan", opp["created_by"], want)
                check(opp["history"][0]["changed_by"] == want,
                      "tarixga ham sessiyadagi ism yozildi",
                      str(opp["history"][0]["changed_by"]))
                db.execute_returning("DELETE FROM erp.opportunity_history "
                                     "WHERE opportunity_id=%(id)s RETURNING id",
                                     {"id": opp["id"]})
                db.execute_returning("DELETE FROM erp.opportunity WHERE id=%(id)s "
                                     "RETURNING id", {"id": opp["id"]})
                db.execute_returning("DELETE FROM erp.client_company WHERE id=%(id)s "
                                     "RETURNING id", {"id": cl["id"]})

            # --- COOKIE va CSRF (auth-4) --------------------------------------
            head("7b. Cookie va CSRF")
            # Alohida mijoz: `https` — `Secure` cookie faqat shunda
            # saqlanadi (brauzer `localhost` ni ham ishonchli deb biladi,
            # lekin sinov serveri "testserver" nomi bilan ishlaydi).
            # DIQQAT: `with` ISHLATILMAYDI — u lifespan'ni qayta yuritib,
            # blokdan chiqishda baza pulini YOPADI va tashqaridagi mijoz
            # yiqilardi. Pul allaqachon ochiq, bizga faqat alohida cookie
            # idishi kerak.
            cc = TestClient(app, base_url="https://testserver")
            r = cc.post("/erp/auth/login",
                        json={"username": uname, "password": PASSWORD})
            eq("cookie bilan kirish -> 200", r.status_code, 200)
            raw = r.headers.get("set-cookie", "")
            check("erp_session" in raw and "HttpOnly" in raw,
                  "sessiya cookie'si HttpOnly")
            check("samesite=lax" in raw.lower(), "SameSite=Lax qo'yilgan",
                  raw[:80])
            check("erp_csrf" in raw, "CSRF cookie'si ham qo'yildi")
            # CSRF cookie'si ATAYLAB HttpOnly EMAS: sahifa uni o'qib
            # sarlavhaga qo'yishi kerak.
            csrf_part = [p for p in raw.split(",") if "erp_csrf" in p]
            check(csrf_part and "HttpOnly" not in csrf_part[0],
                  "CSRF cookie'si HttpOnly EMAS (sahifa o'qiydi)")

            csrf = r.json()["csrf"]
            eq("cookie bilan me -> 200",
               cc.get("/erp/auth/me").status_code, 200)
            eq("cookie bilan GET -> 200",
               cc.get("/erp/clients").status_code, 200)

            # O'ZGARTIRUVCHI so'rov CSRF sarlavhasisiz o'tmasligi kerak.
            eq("CSRF sarlavhasiz POST -> 403",
               cc.post("/erp/clients",
                       json={"name": "ZZTEST CSRF"}).status_code, 403)
            eq("noto'g'ri CSRF -> 403",
               cc.post("/erp/clients", json={"name": "ZZTEST CSRF"},
                       headers={"X-CSRF-Token": "yolgon"}).status_code, 403)
            r2 = cc.post("/erp/clients", json={"name": "ZZTEST CSRF"},
                         headers={"X-CSRF-Token": csrf})
            eq("to'g'ri CSRF bilan POST -> 201", r2.status_code, 201)
            if r2.status_code == 201:
                db.execute_returning(
                    "DELETE FROM erp.client_company WHERE id=%(i)s "
                    "RETURNING id", {"i": r2.json()["id"]})

            # Boshqa sessiyaning CSRF tokeni ham ishlamaydi: token
            # SESSIYAGA bog'langan (oddiy "double-submit" dan farqi).
            other = A.login(aname, PASSWORD)["csrf"]
            eq("boshqa sessiyaning CSRF tokeni -> 403",
               cc.post("/erp/clients", json={"name": "ZZTEST CSRF"},
                       headers={"X-CSRF-Token": other}).status_code, 403)

            r3 = cc.post("/erp/auth/logout")
            eq("chiqish -> 200", r3.status_code, 200)
            cleared = r3.headers.get("set-cookie", "")
            check("erp_session=" in cleared,
                  "chiqishda cookie tozalanadi", cleared[:60])
            eq("chiqqandan keyin me -> 401",
               cc.get("/erp/auth/me").status_code, 401)

            # --- CHIQISH ------------------------------------------------------
            head("8. Chiqish")
            eq("logout -> 200",
               c.post("/erp/auth/logout", headers=H).status_code, 200)
            eq("chiqqandan keyin 401",
               c.get("/erp/clients", headers=H).status_code, 401)
            eq("admin sessiyasi tegilmadi",
               c.get("/erp/auth/me", headers=AH).status_code, 200)
            # Faol emas hisob kira olmaydi.
            _disable(new_name)
            eq("faolsizlantirilgan hisob kira olmaydi",
               c.post("/erp/auth/login",
                      json={"username": new_name,
                            "password": PASSWORD + "9"}).status_code, 401)

            # --- PAROL TANLASHDAN HIMOYA ------------------------------
            head("8b. Parol tanlashdan himoya")
            if not A._attempts_ready():
                print("  SKIP schema_patch_erp_15.sql qo'llanmagan")
            else:
                # 203.0.113.0/24 — TEST-NET-3, hech kimga tegishli emas.
                gname, gip, gip2 = PREFIX + "guard", "203.0.113.7", "203.0.113.8"
                _clean_attempts()

                # Cheklovga YETGUNCHA odatiy 401, keyin 429.
                codes = []
                for _ in range(A.MAX_PER_USER + 2):
                    try:
                        A.login(gname, "notogri", ip=gip)
                        codes.append(200)
                    except A.AuthError as e:
                        codes.append(e.code)
                eq("cheklovgacha 401", codes[:A.MAX_PER_USER],
                   [401] * A.MAX_PER_USER)
                eq("cheklovdan keyin 429", codes[A.MAX_PER_USER:], [429, 429])

                # Bloklangan urinish jurnalga YOZILMAYDI — u parolni ham
                # tekshirmaydi (aks holda cheklovning o'zi yuk keltirish
                # vositasiga aylanardi).
                eq("bloklangandan keyin jurnal o'smadi",
                   db.scalar("SELECT count(*) FROM erp.login_attempt "
                             "WHERE username = %(u)s", {"u": gname}),
                   A.MAX_PER_USER)

                # HISOB BLOKLANMAYDI: boshqa manzildan urinish oddiy 401
                # bo'lib qolaveradi. Ataylab — aks holda loginni bilgan
                # har kim hodimni ishdan chiqarib qo'ya olardi.
                try:
                    A.login(gname, "notogri", ip=gip2)
                    check(False, "boshqa IP dan ham javob kelishi kerak edi")
                except A.AuthError as e:
                    eq("boshqa IP dan -> 401 (hisob bloklanmagan)", e.code, 401)

                # Qancha kutish kerakligi AYTILADI.
                try:
                    A.login(gname, "notogri", ip=gip)
                    check(False, "429 kutilgan edi")
                except A.AuthError as e:
                    check(getattr(e, "retry_after", 0) > 0,
                          "429 da kutish vaqti bor",
                          str(getattr(e, "retry_after", None)))
                    check("daqiqa" in str(e), "matn kutish vaqtini aytadi",
                          str(e)[:60])

                # PAROL JURNALGA TUSHMAYDI.
                acols = {r["column_name"] for r in db.query(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='erp' AND table_name='login_attempt'")}
                check(not any("pass" in x for x in acols),
                      "jurnalda parol ustuni YO'Q", str(sorted(acols)))

                # TO'G'RI PAROL ZANJIRNI UZADI — hisob emas, urinishlar
                # ketma-ketligi hisoblanadi.
                gname2, gip3 = PREFIX + "guard2", "203.0.113.9"
                _seed_user(gname2, "ZZTEST Guard", "broker")
                made.append(gname2)
                for _ in range(A.MAX_PER_USER - 1):
                    try:
                        A.login(gname2, "notogri", ip=gip3)
                    except A.AuthError:
                        pass
                try:
                    A.login(gname2, PASSWORD, ip=gip3)
                    check(True, "cheklov chegarasida to'g'ri parol o'tdi")
                except A.AuthError as e:
                    check(False, "to'g'ri parol o'tishi kerak edi", str(e))

                after_ok = []
                for _ in range(A.MAX_PER_USER + 1):
                    try:
                        A.login(gname2, "notogri", ip=gip3)
                        after_ok.append(200)
                    except A.AuthError as e:
                        after_ok.append(e.code)
                eq("muvaffaqiyatdan keyin hisob NOLDAN boshlandi",
                   after_ok, [401] * A.MAX_PER_USER + [429])

                # HTTP qatlami: 429 va `Retry-After` sarlavhasi.
                hname = PREFIX + "guard3"
                for _ in range(A.MAX_PER_USER):
                    c.post("/erp/auth/login",
                           json={"username": hname, "password": "x"})
                rr = c.post("/erp/auth/login",
                            json={"username": hname, "password": "x"})
                eq("HTTP: cheklovdan keyin 429", rr.status_code, 429)
                check(rr.headers.get("retry-after"),
                      "javobda Retry-After sarlavhasi",
                      str(rr.headers.get("retry-after")))

                # Admin ro'yxati: yo'q loginlar ham ko'rinadi va aynan
                # shundayligi belgilanadi.
                lst = A.attempts(hours=1, limit=200)
                grow = next((x for x in lst if x["username"] == hname), None)
                check(grow is not None, "urinish admin ro'yxatida ko'rinadi")
                if grow:
                    eq("bunday login YO'Qligi belgilangan",
                       grow["known_user"], False)
                check(all("password" not in str(x).lower() for x in lst),
                      "ro'yxatda parol yo'q")

                # Ro'yxat FAQAT adminga: unda mavjud loginlar ko'rinadi.
                btok = A.login(uname, PASSWORD)["token"]
                eq("brokerga urinishlar ro'yxati -> 403",
                   c.get("/erp/auth/attempts",
                         headers={"Authorization": f"Bearer {btok}"}
                         ).status_code, 403)
                eq("adminga -> 200",
                   c.get("/erp/auth/attempts", headers=AH).status_code, 200)
                eq("tokensiz -> 401",
                   c.get("/erp/auth/attempts").status_code, 401)

                # --- PROKSI ORQASIDA MANZIL ----------------------------
                # `X-Forwarded-For` ga ODATDA ISHONILMAYDI: uni mijoz
                # o'zi yozib yuborishi mumkin edi va IP cheklovi bir
                # qator matn bilan chetlab o'tilardi.
                from api import main as _m

                _clean_attempts()
                fname = PREFIX + "proxy"
                FAKE = "203.0.113.55"
                was_trust = _m.TRUST_PROXY
                try:
                    # 1) O'CHIQ (default): sarlavha E'TIBORGA OLINMAYDI.
                    _m.TRUST_PROXY = False
                    c.post("/erp/auth/login",
                           json={"username": fname, "password": "x"},
                           headers={"X-Forwarded-For": FAKE})
                    eq("TRUST_PROXY o'chiq -> soxta manzil yozilmadi",
                       db.scalar("SELECT count(*) FROM erp.login_attempt "
                                 "WHERE ip = %(i)s::inet", {"i": FAKE}), 0)

                    # 2) YOQILGAN: oxirgi manzil olinadi.
                    _m.TRUST_PROXY = True
                    c.post("/erp/auth/login",
                           json={"username": fname, "password": "x"},
                           headers={"X-Forwarded-For": f"10.0.0.9, {FAKE}"})
                    eq("TRUST_PROXY yoqilgan -> OXIRGI manzil yozildi",
                       db.scalar("SELECT host(ip) FROM erp.login_attempt "
                                 "WHERE username = %(u)s "
                                 "ORDER BY id DESC LIMIT 1", {"u": fname}),
                       FAKE)
                    # Boshidagi qiymat (mijoz yozgani) OLINMAYDI.
                    eq("boshidagi soxta manzil olinmadi",
                       db.scalar("SELECT count(*) FROM erp.login_attempt "
                                 "WHERE ip = '10.0.0.9'::inet"), 0)

                    # 3) Yoqilgan, lekin sarlavha YO'Q -> odatdagi
                    #    manzilga qaytadi (sinovda u "testclient",
                    #    ya'ni jurnalda `NULL`).
                    c.post("/erp/auth/login",
                           json={"username": fname, "password": "x"})
                    eq("sarlavhasiz -> odatdagi manzilga qaytadi",
                       db.scalar("SELECT ip IS NULL FROM erp.login_attempt "
                                 "WHERE username = %(u)s "
                                 "ORDER BY id DESC LIMIT 1", {"u": fname}),
                       True)
                finally:
                    _m.TRUST_PROXY = was_trust
                    _clean_attempts()

        finally:
            head("9. Tozalash va chegara")
            _clean_attempts()
            db.execute_returning("DELETE FROM erp.app_user "
                                 "WHERE username = %(u)s RETURNING id",
                                 {"u": PREFIX + "yangi"})
            # Sinov hodimlari O'CHIRILADI: ular hech qanday kartaga yoki
            # vazifaga tegmadi, ya'ni ismlari tarixda yo'q.
            for bid in made_brokers:
                db.execute_returning("DELETE FROM erp.broker WHERE id = %(id)s "
                                     "RETURNING id", {"id": bid})
            made = [u for u in made if u != PREFIX + "yangi"]
            try:
                FIX.cleanup()
            except Exception:                   # noqa: BLE001
                pass
            n = 0
            for u in sorted(set(made)):
                try:
                    if _disable(u):
                        n += 1
                except Exception as e:          # noqa: BLE001
                    print(f"  ! {u} faolsizlantirilmadi: {e}")
            eq("sinov hisoblari faolsizlantirildi", n, len(set(made)))

            # ERP `public.*` ga YOZMAYDI — auth ham istisno emas. Kompaniya
            # hisobi (`company_account`) tender-ai niki va tegilmasligi kerak.
            after = db.query_one(PUBLIC_MAX_SQL)
            eq("company_account soni tegilmadi", after["acc"], before["acc"])
            eq("company_account yangilanmadi", after["acc_max"], before["acc_max"])
            eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
            eq("public.tender yangilanmadi", after["t_max"], before["t_max"])
            check(not db.query_one(
                "SELECT 1 AS x FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='app_user'"),
                "public.app_user yo'q — hodimlar ERP ga ko'chgan")

            # Tender-AI uchun SHARTNOMA-VIEW joyidami (auth-3).
            check(db.query_one(
                "SELECT 1 AS x FROM information_schema.views "
                "WHERE table_schema='erp' AND table_name='v_tender_status'"),
                "erp.v_tender_status view i bor (schema_patch_erp_7.sql)")


if __name__ == "__main__":
    test_sof()
    try:
        test_db()
    except Exception as e:                     # noqa: BLE001
        print(f"  DIQQAT: sinov bajarilmadi: {type(e).__name__}: {e}")
        _fail += 1
    print(f"\n{'=' * 50}\nNATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
