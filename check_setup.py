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

from api import db  # noqa: E402

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
    ("schema_patch_erp_2.sql",  "erp", "client_company",  "mijoz passporti"),
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
]

#: 13- va 14-patch USTUN qo'shadi (jadval emas), shuning uchun alohida.
PATCH_COLUMNS = [
    ("schema_patch_erp_13.sql", "erp", "own_company", "vat_payer",
     "bizning QQS holatimiz"),
    ("schema_patch_erp_14.sql", "erp", "stock_move", "unit_cost",
     "muzlatilgan tannarx (foyda hisobi)"),
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


def main() -> int:
    print("TENDER ERP — tayyorlik tekshiruvi")

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

        # AUTH-4: CSRF ustuni alohida patch (9), jadval o'zgargani uchun
        # yuqoridagi ro'yxatga tushmaydi.
        if db.query_one("SELECT 1 AS x FROM information_schema.columns "
                        "WHERE table_schema='erp' AND table_name='app_session' "
                        "AND column_name='csrf_token'"):
            say(OK, "schema_patch_erp_9.sql — cookie/CSRF")
        else:
            say(ERR, "schema_patch_erp_9.sql qo'llanmagan — kirish ishlamaydi",
                "psql ... -f schema_patch_erp_9.sql")

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
                say(OK, f"passport to'liq — {own['name']}")

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
        pats = ["%DEMO%", "%ZZTEST%", "%ZZSMOKE%"]
        demo = 0
        for sql in ("SELECT count(*) FROM erp.opportunity "
                    "WHERE created_by ILIKE ANY(%(p)s)",
                    "SELECT count(*) FROM erp.client_company "
                    "WHERE name ILIKE ANY(%(p)s)",
                    "SELECT count(*) FROM erp.broker "
                    "WHERE full_name ILIKE ANY(%(p)s)"):
            demo += db.scalar(sql, {"p": pats}) or 0
        if demo:
            say(WARN, f"{demo} ta demo/sinov yozuvi bor",
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
        steps.append((f"Hodimlar ({brokers} ta) va hisoblar ({accounts} ta)",
                      brokers > 0 and linked > 0,
                      "interfeys -> Hodimlar; hisob HODIMGA bog'lansin, "
                      "aks holda 'mening ishlarim' bo'sh qoladi"))

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
        for task, what in (("TenderERP-Backup", "kunlik zaxira"),
                           ("TenderERP-Reminders", "vazifa eslatmalari")):
            state = _task_state(task)
            if state is None:
                say(WARN, f"'{task}' jadvalga qo'yilmagan ({what} ishlamaydi)",
                    f"register_{'backup' if 'Backup' in task else 'erp'}_task.ps1")
            elif state.lower() in ("disabled", "o'chirilgan"):
                say(WARN, f"'{task}' O'CHIRILGAN", "Task Scheduler'dan yoqing")
            else:
                say(OK, f"'{task}' jadvalda ({what})")

        # 2) Qurilgan interfeys.
        import datetime as _dt
        dist = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "frontend", "dist", "index.html")
        if os.path.isfile(dist):
            age_d = (_dt.datetime.now()
                     - _dt.datetime.fromtimestamp(os.path.getmtime(dist))).days
            say(OK, f"frontend qurilgan ({age_d} kun oldin)")
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
    sys.exit(main())
