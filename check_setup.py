"""
TAYYORLIK TEKSHIRUVI — real ishga o'tishdan oldin.

    .venv/Scripts/python.exe check_setup.py

Bitta savolga javob beradi: "shu o'rnatma ishlashga tayyormi?"

NEGA KERAK: loyihada 12 ta sxema patchi, ikki `.env`, ikki backend va
umumiy kalit bor. Ularning birortasi qo'llanmagan bo'lsa xato KEYIN
chiqadi — odam interfeysda "503" ni ko'radi va sababini qidiradi. Bu
skript hammasini OLDINDAN, bir joyda ko'rsatadi.

NIMANI TEKSHIRMAYDI: ma'lumotning to'g'riligini. U faqat "sozlangami"
degan savolga javob beradi.

Chiqish kodi: 0 — hammasi joyida yoki faqat OGOHLANTIRISH bor;
             1 — kamida bitta XATO (ishlamaydigan holat).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

import olchov  # noqa: E402
from api import auth, db  # noqa: E402

OK, WARN, ERR = "OK  ", "OGOH", "XATO"
_counts = {OK: 0, WARN: 0, ERR: 0}


def say(level: str, msg: str, hint: str = "") -> None:
    _counts[level] += 1
    print(f"  {level}  {msg}")
    if hint and level != OK:
        print(f"        -> {hint}")


def head(t: str) -> None:
    print(f"\n=== {t} ===")


#: Sxema patchlari: (fayl, sxema, jadval/view, nima beradi).
#: Ro'yxat KODDA saqlanadi, chunki "qaysi patch nima uchun" degan savolga
#: javob shu yerda bo'lishi kerak — README da emas, ishlaydigan joyda.
PATCHES = [
    ("schema_patch_erp_1.sql",  "erp", "opportunity",     "ish kartalari"),
    # `client_company` EMAS: u 1-patchda yaratilgan va bu qator 2-patch
    # qo'llanmagan bo'lsa ham "OK" berardi. `client_document` — aynan
    # 2-patch qo'shadigan jadval va `api/erp/clients.py` ning O'ZI ham
    # tayyorlikni shundan tekshiradi (`SCHEMA2_CHECK_SQL`).
    ("schema_patch_erp_2.sql",  "erp", "client_document", "mijoz passporti"),
    ("schema_patch_erp_3.sql",  "erp", "opportunity_task", "vazifalar"),
    ("schema_patch_erp_4.sql",  "erp", "submission",      "takliflar"),
    ("schema_patch_erp_5.sql",  "erp", "contract",        "shartnomalar"),
    ("schema_patch_erp_6.sql",  "erp", "app_user",        "hodim hisoblari"),
    ("schema_patch_erp_7.sql",  "erp", "v_tender_status", "tender-ai uchun view"),
    ("schema_patch_erp_8.sql",  "erp", "stock_move",      "ombor"),
    ("schema_patch_erp_10.sql", "erp", "stock_reserve",   "rezerv"),
    ("schema_patch_erp_11.sql", "erp", "invoice",         "hisob-faktura"),
    ("schema_patch_erp_12.sql", "erp", "act",             "dalolatnoma"),
    ("schema_patch_erp_15.sql", "erp", "login_attempt",
     "kirish urinishlari (parol tanlashdan himoya)"),
    ("schema_patch_erp_16.sql", "erp", "doc_audit",
     "hujjat o'zgarishlari jurnali"),
    ("schema_patch_erp_18.sql", "erp", "setting",
     "tizim sozlamalari (huquqning kompaniyaga bog'liq qismi)"),
    ("schema_patch_erp_19.sql", "erp", "v_tai_actor",
     "tender-ai uchun shartnoma-view'lar"),
    ("schema_patch_erp_21.sql", "erp", "opportunity_analysis",
     "Tender-AI yo'naltirishi (tahlil snapshoti)"),
    ("schema_patch_erp_22.sql", "erp", "notification",
     "hodimga bildirishnoma"),
    ("schema_patch_erp_24.sql", "erp", "opportunity_file",
     "sabab hujjati va 'ulgurmadik' holati"),
    ("schema_patch_erp_25.sql", "erp", "chat_message",
     "ichki chat (hodimlar muloqoti)"),
    # 27-patch YANGI JADVAL qo'shadi (`notification_delivery`), shuning
    # uchun shu ro'yxatda. `notification` ning O'ZIGA qaralmaydi: u
    # 22-patchda yaratilgan va tekshiruv YOLG'ON "OK" berardi
    # (`_tests/patch_test.py` topgan nuqson sinfi).
    ("schema_patch_erp_27.sql", "erp", "notification_delivery",
     "bildirishnoma yetkazish navbati (retry, kuzatuv)"),
    # 28-patch YANGI JADVAL qo'shadi (`opportunity_assignee`).
    # `opportunity_task` ga QARALMAYDI: u 3-patchda yaratilgan va
    # tekshiruv YOLG'ON "OK" berardi (`_tests/patch_test.py`).
    ("schema_patch_erp_28.sql", "erp", "opportunity_assignee",
     "karta jamoasi (bir tenderda bir nechta hodim)"),
]

#: 23-patch JADVAL qo'shmaydi — u HUQUQ beradi, shuning uchun
#: alohida tekshiriladi (pastda).


#: 13- va 14-patch USTUN qo'shadi (jadval emas), shuning uchun alohida.
PATCH_COLUMNS = [
    ("schema_patch_erp_13.sql", "erp", "own_company", "vat_payer",
     "bizning QQS holatimiz"),
    ("schema_patch_erp_14.sql", "erp", "stock_move", "unit_cost",
     "muzlatilgan tannarx (foyda hisobi)"),
    # 26-patch YANGI JADVAL QO'SHMAYDI — faqat ustun. Yuqoridagi
    # `PATCHES` ro'yxatiga qo'yilsa `chat_message` allaqachon 25-patchda
    # yaratilgani uchun tekshiruv YOLG'ON "OK" berardi.
    ("schema_patch_erp_26.sql", "erp", "chat_message", "eslatilgan",
     "chatda eslatish: kimga bildirishnoma yuborilgan"),
    # 20-patch `erp.v_tai_actor` ni TASHLAB, BOSHQA SHAKLDA qayta
    # yaratadi (`token_hash`, `login`, `ism`). U umuman tekshirilmasdi,
    # va aynan shu patch tuzatgan nuqson eng yomon turdan edi: view
    # "bor" bo'lib turadi, Tender-AI esa undan hech narsa topolmaydi —
    # ikkala tomon ham "ulandik" deb o'ylaydi. `token_hash` — 19-patch
    # shaklida BO'LMAGAN ustun, ya'ni ikkalasini ajratadigan yagona
    # belgi.
    ("schema_patch_erp_20.sql", "erp", "v_tai_actor", "token_hash",
     "kimlik shartnomasi (Tender-AI sessiya isboti)"),
]


def _task_state(name: str):
    """Windows jadvalidagi vazifa holati (`None` — umuman yo'q).

    PowerShell orqali: `schtasks` chiqishi tilga bog'liq, `Get-ScheduledTask`
    esa obyekt qaytaradi va uni aniq o'qib bo'ladi."""
    import subprocess
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-ScheduledTask -TaskName '{name}' "
             f"-ErrorAction SilentlyContinue).State"],
            capture_output=True, text=True, timeout=25)
        out = (r.stdout or "").strip()
        return out or None
    except Exception:                               # noqa: BLE001
        # Windows bo'lmasa yoki huquq yetmasa — tekshirib bo'lmadi.
        return None


def table_exists(schema: str, name: str) -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = %(s)s AND table_name = %(n)s "
        "UNION ALL "
        "SELECT 1 FROM information_schema.views "
        "WHERE table_schema = %(s)s AND table_name = %(n)s",
        {"s": schema, "n": name}))


#: DEPLOY DARVOZASI: `--kutilgan prod` berilsa, muhit AYNAN shu
#: bo'lishi shart (`.env` ham, baza ham). Berilmasa — oddiy
#: tekshiruv: manbalar bir-biriga mos kelyaptimi.
KUTILGAN = None


class _Otkazish(Exception):
    """Darvoza rejimida qolgan muhit tekshiruvlari ortiqcha.

    Bayroq o'rniga istisno: tekshiruv `try` bloki ichida va
    bayroqli `if` uni ikki qavatga bo'lardi."""


def main() -> int:
    print("TENDER ERP — tayyorlik tekshiruvi")
    if KUTILGAN:
        print(f"DEPLOY DARVOZASI: kutilgan muhit — {KUTILGAN}")

    # --- 1. Baza ---
    head("1. Baza")
    if not os.environ.get("XT_DB_DSN"):
        say(ERR, "XT_DB_DSN sozlanmagan", ".env faylini to'ldiring")
        return 1
    try:
        db.init_pool()
        db.scalar("SELECT 1")
        say(OK, "bazaga ulanish")
    except Exception as e:                      # noqa: BLE001
        say(ERR, f"bazaga ulanib bo'lmadi: {e}", "XT_DB_DSN ni tekshiring")
        return 1

    try:
        # --- 2. Sxema patchlari ---
        head("2. Sxema patchlari")
        for fname, schema, obj, what in PATCHES:
            if table_exists(schema, obj):
                say(OK, f"{fname} — {what}")
            else:
                say(ERR, f"{fname} qo'llanmagan — {what} ishlamaydi",
                    f'psql "dbname=... " -f {fname}')

        for fname, schema, tbl, col, what in PATCH_COLUMNS:
            if db.query_one(
                    "SELECT 1 AS x FROM information_schema.columns "
                    "WHERE table_schema=%(s)s AND table_name=%(t)s "
                    "AND column_name=%(c)s",
                    {"s": schema, "t": tbl, "c": col}):
                say(OK, f"{fname} — {what}")
            else:
                say(ERR, f"{fname} qo'llanmagan — {what} ishlamaydi",
                    f"psql ... -f {fname}")

        # 17-patch na jadval, na ustun qo'shadi — u ROL LUG'ATINI
        # (CHECK ni) almashtiradi. Shuning uchun tekshiruv CHECK ning
        # o'zidan: bazadagi ro'yxat kodnikidan (auth.ROLES) kam bo'lsa,
        # yangi rolli hisob yaratishga urinish 500 beradi.
        rc = db.scalar("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                       "WHERE conrelid = 'erp.app_user'::regclass "
                       "AND conname = 'app_user_role_check'") or ""
        yoq = [c for c, _ in auth.ROLES if f"'{c}'" not in rc]
        if not yoq:
            say(OK, "schema_patch_erp_17.sql — rollar (rahbar/menejer ajratilgan)")
        else:
            say(ERR, "schema_patch_erp_17.sql qo'llanmagan — bazada "
                     f"{', '.join(yoq)} roli yo'q",
                "psql ... -f schema_patch_erp_17.sql")

        # AUTH-4: CSRF ustuni alohida patch (9), jadval o'zgargani uchun
        # yuqoridagi ro'yxatga tushmaydi.
        if db.query_one("SELECT 1 AS x FROM information_schema.columns "
                        "WHERE table_schema='erp' AND table_name='app_session' "
                        "AND column_name='csrf_token'"):
            say(OK, "schema_patch_erp_9.sql — cookie/CSRF")
        else:
            say(ERR, "schema_patch_erp_9.sql qo'llanmagan — kirish ishlamaydi",
                "psql ... -f schema_patch_erp_9.sql")

        # Shartnoma-view'lar TO'RTTA (schema_patch_erp_19.sql) va
        # ular tender-ai ga ochiladigan YAGONA yuza. Bittasi yetishmasa
        # ikkinchi tomon jimgina eski ma'lumot ko'rsatib turardi.
        yoq_view = [v for v in ("v_tai_actor", "v_tender_status", "v_stock",
                                "v_client_document")
                    if not table_exists("erp", v)]
        if yoq_view:
            say(ERR, "shartnoma-view yetishmayapti: " + ", ".join(yoq_view),
                "psql ... -f schema_patch_erp_19.sql")
        elif db.query_one("SELECT 1 AS x FROM pg_roles WHERE rolname = 'tai_app'"):
            berilgan = {r["table_name"] for r in db.query(
                "SELECT table_name FROM information_schema.role_table_grants "
                "WHERE grantee = 'tai_app' AND table_schema = 'erp'")}
            kam = [v for v in ("v_tai_actor", "v_tender_status", "v_stock",
                               "v_client_document") if v not in berilgan]
            if kam:
                say(WARN, "tai_app ga SELECT berilmagan: " + ", ".join(kam),
                    "psql ... -f schema_patch_erp_19.sql")
            else:
                say(OK, "shartnoma-view'lar va tai_app huquqlari joyida")
        else:
            say(OK, "shartnoma-view'lar joyida (tai_app roli yo'q)")

        # Sozlamalar STANDART qiymatda ham ishlaydi, shuning uchun bu
        # xato emas — lekin "kim nimani o'zgartirgan" ko'rinib tursin.
        if table_exists("erp", "setting"):
            from api.erp import sozlama as _soz
            ozgargan = [x for x in _soz.hammasi() if x["changed"]]
            if ozgargan:
                say(OK, "tizim sozlamalari: "
                        + ", ".join(f"{x['label']} — "
                                    + ("ha" if x["value"] else "yo'q")
                                    for x in ozgargan))
            else:
                say(OK, "tizim sozlamalari standart qiymatda")

        # YO'NALTIRISH OQIMI: xarita qo'yilmagan bo'lsa topshiriq
        # KELMAYDI va bu jimgina o'tib ketmasligi kerak — "nega
        # hech narsa kelmayapti" degan savol shu yerdan javob oladi.
        if table_exists("erp", "opportunity_analysis"):
            from api.erp import topshiriq as _top
            h = _top.holat()
            if not h.get("ready"):
                say(WARN, "yo'naltirish oqimi: " + str(h.get("sabab")),
                    "Tender-AI tomonida schema_patch_topshiriq.sql")
            elif not h.get("tai_company_id"):
                say(WARN, "yo'naltirish oqimi sozlanmagan — "
                          "own_company.tai_company_id qo'yilmagan",
                    "PUT /erp/topshiriq/xarita yoki docs/erp_integratsiya_7.md")
            else:
                say(OK, f"yo'naltirish oqimi: ijarachi {h['tai_company_id']}, "
                        f"{h.get('kutayotgan', 0)} ta kutmoqda, "
                        f"{h.get('kartalar', 0)} ta karta")

        # HUQUQ CHEGARASI (23-patch): `erp` roli `public.*` dan
        # faqat olti obyektni O'QIYDI. Himoya hozir YOQILMAGAN
        # (ilova `postgres` bilan ulanadi) va bu JIM qolmasligi kerak.
        if db.query_one("SELECT 1 AS x FROM pg_roles WHERE rolname = 'erp'"):
            yozish = db.query(
                "SELECT DISTINCT privilege_type FROM "
                "information_schema.role_table_grants WHERE grantee = 'erp' "
                "AND table_schema = 'public' AND privilege_type <> 'SELECT'")
            oqish = db.scalar(
                "SELECT count(DISTINCT table_name) FROM "
                "information_schema.role_table_grants WHERE grantee = 'erp' "
                "AND table_schema = 'public'") or 0
            kim = "postgres"
            for qism in (os.environ.get("XT_DB_DSN", "") or "").split():
                if qism.startswith("user="):
                    kim = qism[5:]
            if yozish:
                say(ERR, "erp roli public.* ga YOZA oladi",
                    "psql ... -f schema_patch_erp_23.sql")
            elif not oqish:
                say(WARN, "erp roliga huquq berilmagan",
                    "psql ... -f schema_patch_erp_23.sql")
            elif kim == "erp":
                say(OK, f"huquq chegarasi YOQILGAN (public da {oqish} obyekt, "
                        "faqat o'qish)")
            else:
                say(WARN, f"huquq chegarasi tayyor, lekin ishlamayapti "
                          f"(ilova user={kim} bilan ulanadi)",
                    "ALTER ROLE erp LOGIN PASSWORD '...' + .env dagi XT_DB_DSN")

        # --- 3. Kirish ---
        head("3. Kirish")
        if not table_exists("erp", "app_user"):
            say(ERR, "hodim hisoblari jadvali yo'q", "6-patchni qo'llang")
        else:
            n = db.scalar("SELECT count(*) FROM erp.app_user WHERE active") or 0
            admins = db.scalar("SELECT count(*) FROM erp.app_user "
                               "WHERE active AND role = 'admin'") or 0
            if not n:
                say(ERR, "faol hisob yo'q — tizimga kirib bo'lmaydi",
                    "create_user.py admin \"Bosh administrator\" --role admin")
            elif not admins:
                say(WARN, f"{n} ta hisob bor, lekin ADMIN yo'q",
                    "hodim hisoblarini boshqarish uchun admin kerak")
            else:
                say(OK, f"{n} ta faol hisob, shundan {admins} tasi admin")

            # ROLLAR AJRATILGANMI. Bu XATO emas va OGOHLANTIRISH ham
            # "ishlamayapti" degani emas: `admin_faqat_koradi` o'chiq
            # turganda admin hamma narsani qila oladi, ya'ni tizim
            # ISHLAYDI. Lekin u holda kompaniyada bitta hisob HAMMA
            # ishni bajaradi va 18 ta amal (karta yaratish, chat
            # moderatsiyasi, yakuniydan qaytarish...) rollar bo'yicha
            # AJRATILMAYDI.
            #
            # NEGA KERAK: shu paytgacha bu holat hech qayerda
            # ko'rinmasdi — 9-bo'lim "hisoblar bor" deb "joyida"
            # yozardi. Ya'ni tekshiruv BOR edi, lekin BOSHQA narsani
            # o'lchardi (`_tests/patch_test.py` dagi bilan bir sinf).
            # SO'ROV `olchov.py` DA, bu yerda emas. Ikki joyda ikki
            # so'rov bo'lsa, rol ro'yxati o'zgarganda bittasi
            # yangilanib ikkinchisi eskirardi ("bir tuzatish, ikki
            # chaqiruv joyi" sinfi).
            boshliq = olchov.boshliq_soni() or 0
            if boshliq:
                say(OK, f"{boshliq} ta faol rahbar/menejer — rollar ajratilgan")
            else:
                say(WARN, "faol rahbar/menejer yo'q — hamma ish ADMIN "
                          "hisobidan qilinadi",
                    "tizim ishlaydi, lekin: (1) rollar ajratilmagan, "
                    "(2) `admin_faqat_koradi` sozlamasini yoqib bo'lmaydi. "
                    "Interfeys -> Hodimlar -> hisob ochib, rolini "
                    "'rahbar' qiling")

        # --- 4. Bizning rekvizitlar ---
        head("4. Bizning rekvizitlar")
        own = db.query_one("SELECT name, inn, bank_account, bank_mfo, "
                           "director_name FROM erp.own_company LIMIT 1") \
            if table_exists("erp", "own_company") else None
        if not own or not (own.get("name") or "").strip():
            say(WARN, "kompaniya passporti to'ldirilmagan",
                "shartnoma va faktura uchun kerak: interfeys -> Kompaniya")
        else:
            miss = [k for k in ("inn", "bank_account", "bank_mfo",
                                "director_name") if not own.get(k)]
            if miss:
                say(WARN, f"passportda yetishmayapti: {', '.join(miss)}",
                    "faktura shu rekvizitlar bilan chiqadi")
            else:
                # TO'LDIRILGAN != YAROQLI. Ilgari tekshiruv faqat maydon
                # BO'SH EMASLIGINI ko'rardi: "-" yoki "keyin to'ldiraman"
                # ham "to'liq" bo'lib o'tardi va faktura shu bilan
                # chiqardi. Uzunlik — eng arzon yaroqlilik belgisi
                # (INN 9, MFO 5, hisob raqami 20 raqam).
                shakl = {"inn": 9, "bank_mfo": 5, "bank_account": 20}
                nom = {"inn": "INN", "bank_mfo": "MFO",
                       "bank_account": "hisob raqami"}
                xato = []
                for k, uzunlik in shakl.items():
                    v = "".join(ch for ch in str(own.get(k) or "")
                                if ch.isdigit())
                    if len(v) != uzunlik:
                        xato.append(f"{nom[k]} {len(v)} raqam "
                                    f"({uzunlik} kutilgan)")
                if xato:
                    say(WARN, "passport to'ldirilgan, lekin SHAKLI shubhali: "
                              + "; ".join(xato),
                        "faktura va shartnoma shu raqamlar bilan chiqadi — "
                        "buxgalter qaytarib yuboradi")
                else:
                    say(OK, f"passport to'liq va shakli to'g'ri — {own['name']}")

        # --- 5. Tender-AI bilan bog'lanish ---
        head("5. Tender-AI bilan bog'lanish")
        key = (os.environ.get("ERP_SERVICE_KEY") or "").strip()
        if not key:
            say(ERR, "ERP_SERVICE_KEY sozlanmagan",
                "cheklist, hujjat shabloni va xabar yuborish ishlamaydi")
        elif len(key) < 20:
            say(WARN, "ERP_SERVICE_KEY juda qisqa",
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        else:
            say(OK, "service kaliti sozlangan")

        from api import tenderai
        try:
            tenderai.document_types()
            # NIMANI ISBOTLAYDI: tender-ai ko'tarilgan va so'rov o'tdi.
            # NIMANI ISBOTLAMAYDI: `ERP_SERVICE_KEY` ning to'g'riligini —
            # agar u yerda endpoint ochiq bo'lsa, noto'g'ri kalit bilan
            # ham javob keladi. Kalitni tekshiradigan yagona ishonchli
            # yo'l — tender-ai tomonidan 401 qaytishi.
            say(OK, f"tender-ai javob berdi ({tenderai.API})")
        except Exception as e:                  # noqa: BLE001
            # Bu OGOHLANTIRISH, xato emas: ERP tender-ai siz ham ishlaydi,
            # faqat cheklist va yangi karta olish ishlamaydi.
            say(WARN, f"tender-ai javob bermadi: {str(e)[:60]}",
                "ERP ishlayveradi; cheklist va yangi karta olish ishlamaydi")

        # --- 6. Cookie ---
        head("6. Cookie (auth-4)")
        secure = os.environ.get("AUTH_COOKIE_SECURE", "1")
        if secure in ("0", "false", ""):
            say(WARN, "AUTH_COOKIE_SECURE=0 — cookie HTTPS siz ham yuboriladi",
                "faqat ichki tarmoqdagi ishlab chiqish uchun")
        else:
            say(OK, "cookie Secure bayrog'i yoqilgan")

        # --- 7. Demo ma'lumot ---
        head("7. Demo va sinov ma'lumotlari")
        # QAMROV. Ilgari UCHTA jadval sanalardi (karta, mijoz, hodim) va
        # natija "23 ta" chiqardi — haqiqiy son esa uch barobar ko'p edi
        # (hisoblar 11, bildirishnoma 9, vazifa 24). Ya'ni tekshiruv
        # BOR edi, lekin QISMNI o'lchardi va egasi tozalash hajmini
        # kam baholardi.
        #
        # `ZZFIX` ham qo'shildi: `_tests/fixture.py` shu belgini
        # ishlatadi va u ro'yxatda umuman yo'q edi.
        pats = ["%DEMO%", "%ZZTEST%", "%ZZSMOKE%", "%ZZFIX%", "%ZZOQIM%"]
        JADVALLAR = [
            ("opportunity", "created_by", "karta"),
            ("client_company", "name", "mijoz"),
            ("broker", "full_name", "hodim"),
            ("app_user", "username", "hisob"),
            ("opportunity_task", "title", "vazifa"),
            ("notification", "matn", "bildirishnoma"),
            ("opportunity_file", "created_by", "sabab hujjati"),
            ("chat_message", "text", "chat xabari"),
        ]
        demo = 0
        qismlar = []
        for tbl, col, nom in JADVALLAR:
            # Jadval hali yaratilmagan bo'lishi mumkin (patch qo'llanmagan)
            # — bunda tekshiruv YIQILMASLIGI kerak.
            if not table_exists("erp", tbl):
                continue
            n = db.scalar(f"SELECT count(*) FROM erp.{tbl} "
                          f"WHERE {col}::text ILIKE ANY(%(p)s)",
                          {"p": pats}) or 0
            if n:
                demo += n
                qismlar.append(f"{nom} {n}")
        if demo:
            say(WARN, f"{demo} ta demo/sinov yozuvi bor: "
                      + ", ".join(qismlar),
                "cleanup_demo.py (avval belgisiz, keyin --yes bilan)")
        else:
            say(OK, "demo/sinov yozuvi yo'q")

        # --- 9. Ma'lumot kiritish holati ---
        # KOD TAYYOR, MA'LUMOTSIZ SINAB BO'LMAYDI. Tartib muhim: har
        # qadam o'zidan oldingisiga tayanadi, shuning uchun ro'yxat
        # aynan shu ketma-ketlikda va birinchi to'ldirilmagan qadam
        # ALOHIDA ko'rsatiladi — "nimadan boshlayman?" degan savolga
        # javob bitta bo'lsin.
        head("9. Ma'lumot kiritish (egasi to'ldiradi)")
        steps = []

        # 1) Kompaniya passporti — 4-bo'limda tekshirildi, bu yerda
        #    faqat qadamlar ro'yxatida turadi.
        own_ok = bool(own and (own.get("name") or "").strip()
                      and not [k for k in ("inn", "bank_account", "bank_mfo",
                                           "director_name")
                               if not own.get(k)])
        steps.append(("Kompaniya passporti (QQS bilan)", own_ok,
                      "interfeys -> Kompaniya"))

        # 2) Hodimlar va ularning hisoblari.
        brokers = db.scalar("SELECT count(*) FROM erp.broker WHERE active") or 0
        accounts = db.scalar("SELECT count(*) FROM erp.app_user "
                             "WHERE active") or 0
        linked = db.scalar("SELECT count(*) FROM erp.app_user "
                           "WHERE active AND broker_id IS NOT NULL") or 0
        boshliq_n = olchov.boshliq_soni() or 0
        steps.append((f"Hodimlar ({brokers} ta), hisoblar ({accounts} ta), "
                      f"rahbar/menejer ({boshliq_n} ta)",
                      # RAHBAR/MENEJER ham SHART: usiz qadam "bajarildi"
                      # deb ko'rinardi, holbuki kompaniyada rollar
                      # ajratilmagan va bitta hisob hamma ishni qiladi.
                      brokers > 0 and linked > 0 and boshliq_n > 0,
                      "interfeys -> Hodimlar; hisob HODIMGA bog'lansin "
                      "(aks holda 'mening ishlarim' bo'sh qoladi) va "
                      "kamida bittasi 'rahbar' yoki 'menejer' bo'lsin"))

        # 3) Mijoz passportlari.
        clients = db.scalar("SELECT count(*) FROM erp.client_company") or 0
        cl_full = db.scalar("SELECT count(*) FROM erp.client_company "
                            "WHERE inn IS NOT NULL "
                            "AND bank_account IS NOT NULL") or 0
        steps.append((f"Mijoz passportlari ({clients} ta, {cl_full} tasi "
                      "rekvizitlari bilan)",
                      clients > 0 and cl_full > 0,
                      "faktura mijoz rekvizitlarisiz chiqmaydi"))

        # 4) Ombor boshlang'ich qoldig'i.
        if table_exists("erp", "stock_move"):
            moves = db.scalar("SELECT count(*) FROM erp.stock_move") or 0
            opening = db.scalar("SELECT count(*) FROM erp.stock_move "
                                "WHERE kind = 'opening'") or 0
            steps.append((f"Ombor boshlang'ich qoldig'i ({opening} ta "
                          f"pozitsiya, jami {moves} ta harakat)",
                          opening > 0,
                          "interfeys -> Ombor -> import qoldig'idan ko'chirish"))
        else:
            steps.append(("Ombor boshlang'ich qoldig'i", False,
                          "schema_patch_erp_8.sql qo'llanmagan"))

        # 5) Tannarx — foyda hisobining sharti.
        prods = db.scalar("SELECT count(*) FROM public.catalog_product") or 0
        with_cost = db.scalar("SELECT count(*) FROM public.catalog_product "
                              "WHERE cost_price IS NOT NULL") or 0
        steps.append((f"Katalogda tannarx ({with_cost}/{prods} mahsulot)",
                      prods > 0 and with_cost > 0,
                      "tannarxsiz foyda hisoboti 'to'liq emas' bo'lib "
                      "turaveradi — bu dastur xatosi EMAS"))

        done = 0
        first_missing = None
        for i, (title, ok_, hint) in enumerate(steps, start=1):
            if ok_:
                done += 1
                say(OK, f"{i}. {title}")
            else:
                if first_missing is None:
                    first_missing = (i, title, hint)
                say(WARN, f"{i}. {title} — to'ldirilmagan", hint)

        if first_missing:
            i, title, hint = first_missing
            print(f"\n  KEYINGI QADAM: {i}. {title}")
            if hint:
                print(f"        -> {hint}")
        else:
            say(OK, "hamma ma'lumot kiritilgan — tizim to'liq ishlaydi")

        # --- 11. Joylashtirish ---
        # KO'R NUQTA EDI: 10-bo'lim zaxira FAYLLARINI sanaydi va
        # "oxirgisi 0 kun oldin" deb SOG'LOM ko'rsatadi — hatto
        # jadvalga qo'yilmagan bo'lsa ham. Ya'ni tekshiruvning o'zi
        # yolg'on xotirjamlik berardi: fayl qo'lda olingan bo'lishi
        # mumkin va ertaga hech kim olmaydi.
        head("11. Joylashtirish")

        # 1) Jadvalga qo'yilgan vazifalar.
        # `TenderERP-Notifications` ro'yxatda: usiz TASHQI kanal
        # (Telegram/email) UMUMAN yubormaydi — navbat to'ladi va
        # buni hech narsa ko'rsatmasdi. Ilova bildirishnomasi esa
        # ishlayveradi, ya'ni nuqson JIM: "xabar bordi" deb
        # o'ylanadi, aslida faqat ekranda turadi.
        SKRIPT = {"TenderERP-Backup": "register_backup_task.ps1",
                  "TenderERP-Reminders": "register_erp_task.ps1",
                  "TenderERP-Notifications": "register_navbat_task.ps1"}
        for task, what in (("TenderERP-Backup", "kunlik zaxira"),
                           ("TenderERP-Reminders", "vazifa eslatmalari"),
                           ("TenderERP-Notifications",
                            "bildirishnoma navbati: Telegram/email")):
            state = _task_state(task)
            if state is None:
                say(WARN, f"'{task}' jadvalga qo'yilmagan ({what} ishlamaydi)",
                    SKRIPT[task])
            elif state.lower() in ("disabled", "o'chirilgan"):
                say(WARN, f"'{task}' O'CHIRILGAN", "Task Scheduler'dan yoqing")
            else:
                say(OK, f"'{task}' jadvalda ({what})")

        # 1b) NAVBAT TO'XTAB QOLMAGANMI.
        #
        # Vazifa jadvalda TURISHI yetarli emas: u yiqilib, o'chib
        # yoki xato bilan tugab turgan bo'lishi mumkin. Yagona
        # ishonchli belgi — eng eski kutayotgan qatorning YOSHI.
        try:
            from api.erp import navbat as _navbat
            if _navbat.schema_ready():
                import datetime as _dt2
                _eng = None
                for _k in _navbat.sogliq().get("kanallar", []):
                    if _k["kanal"] == "inapp" or not _k["eng_eski_pending"]:
                        continue
                    _t = _dt2.datetime.fromisoformat(_k["eng_eski_pending"])
                    if _eng is None or _t < _eng:
                        _eng = _t
                    if _k["terminal"]:
                        say(WARN, f"'{_k['kanal']}': {_k['terminal']} ta xabar "
                            "butunlay yetkazilmadi",
                            "sabab: erp.notification_delivery.last_error")
                if _eng is not None:
                    _soat = (_dt2.datetime.now(_eng.tzinfo) - _eng).total_seconds() / 3600
                    if _soat > 1:
                        say(WARN, f"navbatda {_soat:.0f} soatdan beri kutayotgan "
                            "xabar bor", "navbat yurmayapti: register_navbat_task.ps1")
                    else:
                        say(OK, "bildirishnoma navbati harakatda")
                else:
                    say(OK, "bildirishnoma navbati bo'sh")
        except Exception as _e:                     # noqa: BLE001
            say(WARN, f"navbat holatini o'qib bo'lmadi: {_e}")

        # 1b0) QAYSI MUHIT. Bu birinchi savol: quyidagi hamma
        # tekshiruv MA'LUM bir bazaga tegishli va u qaysi ekani
        # ko'rinmasa, natija ham ma'nosiz.
        #
        # `ERP_MUHIT` shunchaki yorliq emas — `api/muhit.py` qulfi
        # shunga qaraydi va `prod` bo'lsa sinovlarni umuman ishga
        # tushirmaydi.
        # QATTIQ TALAB (deploy darvozasi). Qoidalar:
        #
        #   .env va baza ZID       -> XATO. Bu deyarli har doim
        #                             noto'g'ri `.env` bilan ishga
        #                             tushirish, ya'ni ma'lumot
        #                             xavf ostida.
        #   .env `prod`, baza yo'q -> XATO. Ishlab chiqarish belgisiz
        #                             bo'lsa, qulfning ikkinchi qavati
        #                             ishlamaydi — aynan `.env`
        #                             almashib ketgan holatda.
        #   baza `prod`, .env yo'q -> XATO (yuqoridagi bilan bir sinf).
        #   .env yo'q, baza yo'q   -> OGOH. Bu eski o'rnatma: uni
        #                             XATO qilish bugungi hamma
        #                             ishni bir zarbada to'xtatardi
        #                             va birinchi qilinadigan ish
        #                             tekshiruvni o'chirish bo'lardi.
        #
        # Ya'ni: `ERP_MUHIT=prod` yozilgach, u ARTGA qaytmaydi —
        # belgisiz qolgan ishlab chiqarish darvozadan o'tmaydi.
        try:
            from api import muhit as _muhit
            if KUTILGAN:
                # DARVOZA REJIMI: niyat ham tekshiriladi.
                #
                # Ikkala manba mos, lekin STAGING bo'lgan
                # o'rnatmaga "ishlab chiqarish deploy" qilish ham
                # xato — mos, lekin noto'g'ri muhit. Aynan shu
                # noto'g'ri DSN bilan deploy qilish holati.
                _h, _x = _muhit.darvoza(KUTILGAN)
                if _h == "ok":
                    say(OK, f"muhit darvozasi: {_x}")
                else:
                    say(ERR, f"MUHIT DARVOZASI YOPIQ: {_x}",
                        f"kutilgan: .env va baza — ikkalasi ham "
                        f"'{KUTILGAN}'. Bazani belgilash: "
                        f"python -m api.muhit --belgila {KUTILGAN}")
                raise _Otkazish()
            _holat, _xabar = _muhit.moslik()
            if _holat == "zid":
                say(ERR, f"MUHIT ZID: {_xabar}",
                    "noto'g'ri .env bilan ishga tushirilgan bo'lishi "
                    "mumkin. Tekshiring: python -m api.muhit")
            elif _holat == "ok":
                say(OK, f"muhit: {_xabar}")
            elif _holat == "baza_yoq":
                if _muhit.prodmi():
                    say(ERR, f"ISHLAB CHIQARISH bazasi BELGILANMAGAN "
                        f"({_xabar})",
                        "python -m api.muhit --belgila prod")
                else:
                    say(WARN, f"baza belgilanmagan ({_xabar})",
                        f"python -m api.muhit --belgila {_muhit.nomi()}")
            else:                                   # env_yoq
                if _muhit.baza_muhiti() == _muhit.PROD:
                    say(ERR, f"baza ISHLAB CHIQARISH deb belgilangan, "
                        f".env da esa ERP_MUHIT yo'q ({_xabar})",
                        ".env ga yozing: ERP_MUHIT=prod")
                else:
                    say(WARN, _xabar,
                        "ishlab chiqarish qulfi ISHLAMAYDI: .env ga "
                        "ERP_MUHIT=prod / staging / dev yozing")
        except _Otkazish:
            pass
        except Exception as _e:                     # noqa: BLE001
            say(WARN, f"muhit nomi o'qilmadi: {_e}")

        # 1c) 28-PATCH INVARIANTLARI — faqat O'QIYDI.
        #
        # NEGA KERAK: patch qo'llangani (yuqorida) obyekt BORLIGINI
        # aytadi, ishlayotganini emas. Eng qimmat holat — ko'zgu
        # trigger tushib qolishi: u yo'q bo'lsa `done` va `status`
        # JIMGINA ajralib ketadi va bajarilgan vazifa ro'yxatda
        # ochiq bo'lib qolaveradi. Xato chiqmaydi.
        try:
            if db.query_one("SELECT 1 AS x FROM information_schema.tables "
                            "WHERE table_schema='erp' "
                            "AND table_name='opportunity_assignee'"):
                if db.query_one(
                        "SELECT 1 AS x FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid = t.tgrelid "
                        "WHERE c.relname = 'opportunity_task' "
                        "AND t.tgname = 'task_done_mirror_trg'"):
                    say(OK, "vazifa `done` ko'zgu triggeri ulangan")
                else:
                    say(ERR, "`done` ko'zgu triggeri YO'Q",
                        "bajarilgan vazifa ochiq bo'lib qolaveradi: "
                        "psql ... -f schema_patch_erp_28.sql")
                _nomos = db.scalar(
                    "SELECT count(*) FROM erp.opportunity_task "
                    "WHERE done IS DISTINCT FROM "
                    "      (status IN ('bajarildi', 'bekor'))") or 0
                if _nomos:
                    say(ERR, f"{_nomos} ta vazifada `done` va `status` "
                        "mos kelmaydi", "trigger tushib qolgan edi: "
                        "schema_patch_erp_28.sql qayta qo'llang")
                else:
                    say(OK, "vazifa holati va `done` ustuni mos")
                # ASOSIY MAS'UL BITTA: u `opportunity.broker_id` da,
                # ya'ni ikkitasi TUZILMA darajasida bo'lishi mumkin
                # emas. Tekshiriladigan narsa boshqa: o'sha odam
                # jamoa jadvalida IKKINCHI marta turibdimi.
                _ikki = db.scalar(
                    "SELECT count(*) FROM erp.opportunity_assignee a "
                    "JOIN erp.opportunity o ON o.id = a.opportunity_id "
                    "WHERE a.removed_at IS NULL "
                    "  AND a.broker_id = o.broker_id") or 0
                if _ikki:
                    say(WARN, f"{_ikki} ta kartada asosiy mas'ul jamoa "
                        "jadvalida ham turibdi",
                        "ekranda bir marta ko'rinadi (jamoa.royxat), "
                        "lekin qator ortiqcha")
                else:
                    say(OK, "asosiy mas'ul jamoa jadvalida takrorlanmagan")
                _umumiy = db.scalar(
                    "SELECT count(*) FROM erp.opportunity_task "
                    "WHERE opportunity_id IS NULL") or 0
                say(OK, f"umumiy vazifalar: {_umumiy} ta")
        except Exception as _e:                     # noqa: BLE001
            say(WARN, f"28-patch invariantlari o'qilmadi: {_e}")

        # 2) Qurilgan interfeys.
        import datetime as _dt
        dist = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "frontend", "dist", "index.html")
        if os.path.isfile(dist):
            age_d = (_dt.datetime.now()
                     - _dt.datetime.fromtimestamp(os.path.getmtime(dist))).days
            say(OK, f"frontend qurilgan ({age_d} kun oldin)",
                "natijasi to'g'rimi: check_build.py")
        else:
            say(WARN, "frontend qurilmagan (frontend/dist yo'q)",
                "ishlab chiqarishda: run_erp.ps1 -Prod")

        # 3) Cookie va HTTPS — birga ishlamaydigan juftlik.
        secure = (os.environ.get("AUTH_COOKIE_SECURE", "1").strip()
                  not in ("0", "false", "no", "off"))
        if secure:
            say(OK, "cookie Secure — HTTPS yoki localhost uchun to'g'ri",
                "tarmoq manzilida (192.168.x.x) HTTP orqali ochsangiz "
                "kirish ISHLAMAYDI: AUTH_COOKIE_SECURE=0 qiling")
        else:
            say(WARN, "AUTH_COOKIE_SECURE=0 — sessiya cookie'si HTTP orqali "
                      "ham yuboriladi",
                "faqat ishonchli ichki tarmoqda; tashqariga chiqarsangiz "
                "HTTPS qo'ying va 1 ga qaytaring")

        # 4) Zaxira BOSHQA joyda ham bormi — buni tekshirib bo'lmaydi,
        #    lekin eslatib turish kerak.
        say(OK, "eslatma: zaxira boshqa diskka/bulutga ham nusxalanishi kerak",
            "bitta disk ishdan chiqsa, undagi zaxira ham ketadi")

        # --- 10. Zaxira ---
        head("10. Zaxira nusxasi")
        bdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "backups")
        dumps = []
        if os.path.isdir(bdir):
            dumps = sorted(
                (f for f in os.listdir(bdir) if f.endswith(".dump")),
                key=lambda f: os.path.getmtime(os.path.join(bdir, f)))
        if not dumps:
            say(WARN, "zaxira nusxasi yo'q",
                "backup_erp.ps1 (va register_backup_task.ps1 bilan jadvalga)")
        else:
            import datetime as _dt
            last = os.path.join(bdir, dumps[-1])
            age = (_dt.datetime.now()
                   - _dt.datetime.fromtimestamp(os.path.getmtime(last))).days
            size_kb = os.path.getsize(last) / 1024
            if age > 7:
                say(WARN, f"oxirgi zaxira {age} kun oldin ({dumps[-1]})",
                    "jadvalga qo'yilganmi? register_backup_task.ps1")
            elif size_kb < 1:
                # Bo'sh fayl "zaxira bor" degan yolg'on tuyg'u beradi.
                say(ERR, f"oxirgi zaxira BO'SH ({size_kb:.0f} KB)",
                    "backup_erp.ps1 ni qo'lda ishga tushirib xatoni ko'ring")
            else:
                say(OK, f"{len(dumps)} ta nusxa, oxirgisi {age} kun oldin "
                        f"({size_kb:,.0f} KB)")

        # --- Xulosa ---
        print(f"\n{'=' * 50}")
        print(f"XULOSA: {_counts[OK]} joyida, {_counts[WARN]} ogohlantirish, "
              f"{_counts[ERR]} xato")
        if _counts[ERR]:
            print("Xatolar tuzatilmaguncha tizim to'liq ishlamaydi.")
        elif _counts[WARN]:
            print("Ishlaydi, lekin ogohlantirishlarni ko'rib chiqing.")
        else:
            print("Hammasi tayyor.")
        return 1 if _counts[ERR] else 0
    finally:
        db.close_pool()


if __name__ == "__main__":
    import argparse

    _ap = argparse.ArgumentParser(description="ERP tayyorlik tekshiruvi")
    _ap.add_argument("--kutilgan", metavar="MUHIT",
                     help="deploy darvozasi: .env ham, baza ham AYNAN "
                          "shu muhit bo'lsin (prod | staging | dev)")
    KUTILGAN = _ap.parse_args().kutilgan
    sys.exit(main())
