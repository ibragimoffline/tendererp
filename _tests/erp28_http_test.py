"""
28-PATCH — JOYLASHTIRISH DARVOZASI (HTTP orqali, ilova darajasida).

Ishga tushirish:
    .venv/Scripts/python.exe _tests/erp28_http_test.py
    .venv/Scripts/python.exe _tests/erp28_http_test.py --base http://10.0.0.5:8100 --tasdiq

NIMA UCHUN ALOHIDA FAYL: `_tests/erp_jamoa_test.py` MODUL darajasida
ishlaydi — funksiyalarni to'g'ridan-to'g'ri chaqiradi. U mantiqni
tekshiradi, lekin QUVURNI tekshirmaydi: sessiya, CSRF, huquq
tekshiruvi, marshrutlash va JSON shakli undan chetda qoladi.

Bu fayl esa AYNAN o'sha quvurdan o'tadi. Joylashtirishdan keyin
"patch qo'llandi, kod yangilandi — ishlayaptimi?" degan savolga
javob beradigan yagona tekshiruv shu.

BEGONA MUHITDA `--tasdiq` SO'RALADI
═══════════════════════════════════
Sinov haqiqiy yozuv yaratadi (hodim, karta, vazifa) va oxirida
tozalaydi. Mahalliy manzilda bu xavfsiz. Boshqa manzilda esa
ATAYLAB to'siladi: ishlab chiqarish bazasiga sinov yozuvini
tasodifan yozib qo'yish — tozalash ishlagan taqdirda ham — audit
jurnalida iz qoldiradi va uni orqaga qaytarib bo'lmaydi.

BAZAGA TO'G'RIDAN-TO'G'RI kiradi (hisob yaratish va tozalash
uchun): ya'ni `XT_DB_DSN` O'SHA muhitning bazasini ko'rsatishi
SHART. Aks holda sinov bir bazada hisob yaratib, boshqasiga
so'rov yuborardi va natija ma'nosiz bo'lardi — bu tekshiruv
boshida ochiq tekshiriladi.
"""
import argparse
import http.cookiejar as cj
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from api import auth, db  # noqa: E402

MARK = "ZZ28"
PREFIX = "zz28_"
#: Sinov hisoblari uchun parol. Ular oxirida FAOLSIZLANTIRILADI.
PAROL = "Zz28-Darvoza-2026!"
MAHALLIY = ("127.0.0.1", "localhost", "::1")

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


def head(t):
    print(f"\n=== {t} ===")


class Client:
    """Sessiya cookie'si va CSRF sarlavhasi bilan."""

    def __init__(self, base):
        self.base = base
        self.jar = cj.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json"}
        # CSRF: cookie'ni brauzer o'zi qo'shadi, shuning uchun
        # O'ZGARTIRUVCHI so'rovda sarlavha ham kerak (auth-4).
        for c in self.jar:
            if c.name == "erp_csrf":
                h["X-CSRF-Token"] = c.value
        req = urllib.request.Request(self.base + path, data=data,
                                     method=method, headers=h)
        try:
            with self.op.open(req, timeout=30) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "null")
            except ValueError:
                return e.code, None
        except urllib.error.URLError as e:
            return 0, {"detail": str(e)}


# ---------------------------------------------------------------------------
# Tayyorgarlik
# ---------------------------------------------------------------------------
def _broker(nom):
    r = db.query_one("SELECT id FROM erp.broker WHERE full_name = %(n)s",
                     {"n": nom})
    if r:
        db.execute_returning("UPDATE erp.broker SET active = TRUE "
                             "WHERE id = %(i)s RETURNING id", {"i": r["id"]})
        return r["id"]
    return db.execute_returning(
        "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
        {"n": nom})["id"]


def _user(username, rol, broker_id=None):
    r = db.query_one("SELECT id FROM erp.app_user WHERE username = %(u)s",
                     {"u": username})
    if r:
        db.execute_returning(
            "UPDATE erp.app_user SET active = TRUE, role = %(r)s, "
            "broker_id = %(b)s WHERE id = %(i)s RETURNING id",
            {"i": r["id"], "r": rol, "b": broker_id})
        auth.set_password(r["id"], PAROL)
        return r["id"]
    n = auth.create_user(username, f"{MARK} {rol}", PAROL, role=rol)
    uid = n["id"] if isinstance(n, dict) else n
    if broker_id:
        db.execute_returning("UPDATE erp.app_user SET broker_id = %(b)s "
                             "WHERE id = %(i)s RETURNING id",
                             {"i": uid, "b": broker_id})
    return uid


def _karta(broker_id):
    """Sinov kartasi. `tender_id` MAJBURIY — manbadan o'qiladi."""
    o = db.query_one("SELECT id FROM erp.opportunity WHERE title = %(t)s",
                     {"t": f"{MARK} karta"})
    if o:
        db.execute_returning("UPDATE erp.opportunity SET broker_id = %(b)s, "
                             "status = 'new' WHERE id = %(i)s RETURNING id",
                             {"i": o["id"], "b": broker_id})
        return o["id"]
    t = db.query_one("SELECT id FROM public.tender ORDER BY id LIMIT 1")
    return db.execute_returning(
        "INSERT INTO erp.opportunity (tender_id, title, broker_id, status, "
        "created_by) VALUES (%(t)s, %(n)s, %(b)s, 'new', %(m)s) RETURNING id",
        {"t": t["id"] if t else None, "n": f"{MARK} karta",
         "b": broker_id, "m": MARK})["id"]


# ---------------------------------------------------------------------------
# Tekshiruvlar
# ---------------------------------------------------------------------------
def yur(base):
    head("0. Muhit")
    dsn = os.environ.get("XT_DB_DSN", "")
    host = "localhost"
    for qism in dsn.split():
        if qism.startswith("host="):
            host = qism.split("=", 1)[1]
    print(f"  ilova: {base}")
    print(f"  baza:  host={host}")

    c_anon = Client(base)
    s, r = c_anon.call("GET", "/health")
    check(s == 200 and (r or {}).get("ok"), f"ilova javob berdi (HTTP {s})",
          str(r))
    if s != 200:
        print("\n  TO'XTATILDI: ilova javob bermayapti.")
        return

    # SXEMA — patch qo'llanganmi. Buni ilovaning O'ZI ham biladi,
    # lekin bu yerda BAZADAN so'raymiz: "kod yangilandi, patch esa
    # yo'q" holati aynan shu farqda ko'rinadi.
    check(bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables WHERE "
        "table_schema='erp' AND table_name='opportunity_assignee'")),
        "28-patch: erp.opportunity_assignee bor")
    check(db.scalar(
        "SELECT is_nullable FROM information_schema.columns WHERE "
        "table_schema='erp' AND table_name='opportunity_task' "
        "AND column_name='opportunity_id'") == "YES",
        "28-patch: umumiy vazifa uchun opportunity_id NULL bo'la oladi")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = 'opportunity_task' "
        "AND t.tgname = 'task_done_mirror_trg'")),
        "28-patch: `done` ko'zgu triggeri ulangan")

    head("1. Hisoblar")
    b_masul = _broker(f"{MARK} Masul")
    b_narx = _broker(f"{MARK} Narx")
    b_hujjat = _broker(f"{MARK} Hujjat")
    b_chet = _broker(f"{MARK} Chet")
    u_men = _user(f"{PREFIX}menejer", "menejer")
    _user(f"{PREFIX}narx", "broker", b_narx)
    _user(f"{PREFIX}chet", "broker", b_chet)
    oid = _karta(b_masul)
    print(f"  karta={oid}")

    cm, cn, cc = Client(base), Client(base), Client(base)
    for cl, un in ((cm, f"{PREFIX}menejer"), (cn, f"{PREFIX}narx"),
                   (cc, f"{PREFIX}chet")):
        s, r = cl.call("POST", "/erp/auth/login",
                       {"username": un, "password": PAROL})
        check(s == 200, f"{un} kirdi (HTTP {s})", str(r))
    if _fail:
        print("\n  TO'XTATILDI: kirish ishlamadi.")
        return

    head("2. Umumiy vazifa")
    s, r = cm.call("POST", "/erp/tasks", {
        "title": f"{MARK} sertifikatni yangilash",
        "assignee_broker_id": b_narx, "priority": "high",
        # MUALLIF SOXTALASHTIRILADI: server buni e'tiborga
        # olmasligi kerak.
        "created_by": "SOXTA Direktor"})
    check(s == 201, f"umumiy vazifa yaratildi (HTTP {s})", str(r))
    t = (r or [{}])[0]
    tid = t.get("id")
    check(t.get("opportunity_id") is None, "kartaga bog'lanmagan")
    check(t.get("kontekst") == "umumiy", "kontekst — umumiy")
    check("SOXTA" not in str(t.get("created_by")),
          f"so'rovdagi soxta muallif e'tiborga olinmadi: "
          f"{t.get('created_by')!r}")

    head("3. Hodimga biriktirish va bajarish")
    s, r = cn.call("GET", "/erp/tasks")
    check(any(x["id"] == tid for x in (r or [])),
          "bajaruvchi vazifani ro'yxatida ko'radi")
    s, r = cn.call("PATCH", f"/erp/tasks/{tid}/status",
                   {"status": "bajarilmoqda"})
    check(s == 200, f"boshladi (HTTP {s})")
    s, r = cn.call("PATCH", f"/erp/tasks/{tid}/status",
                   {"status": "bajarildi"})
    check(s == 200 and (r or [{}])[0].get("status") == "bajarildi", "bajardi")
    check((r or [{}])[0].get("done") is True, "`done` ko'zgusi to'g'ri")
    s, r = cc.call("PATCH", f"/erp/tasks/{tid}/status", {"status": "bekor"})
    check(s == 403, f"begona hodim vazifaga tegib bo'lmadi (HTTP {s})")

    head("4. Tenderga uch hodim")
    s, _ = cn.call("GET", f"/erp/opportunities/{oid}")
    check(s == 403, f"boshida narxchi kartani KO'RMAYDI (HTTP {s})")
    for b, rol in ((b_narx, "narx"), (b_hujjat, "hujjat")):
        s, r = cm.call("POST", f"/erp/opportunities/{oid}/assignees",
                       {"broker_id": b, "rol": rol})
        check(s == 201, f"{rol} qo'shildi (HTTP {s})", str(r))
    check((r or {}).get("soni") == 3, f"jamoada 3 hodim: {(r or {}).get('soni')}")
    check(len([a for a in (r or {}).get("azolar", []) if a["asosiy"]]) == 1,
          "asosiy mas'ul FAQAT BITTA")

    head("5. Huquq jamoaga ergashadi")
    s, _ = cn.call("GET", f"/erp/opportunities/{oid}")
    check(s == 200, f"narxchi kartani ochа oladi (HTTP {s})")
    s, r = cn.call("GET", "/erp/opportunities")
    check(any(o["id"] == oid for o in (r or [])),
          "karta uning ro'yxatida ko'rinadi")
    s, _ = cc.call("GET", f"/erp/opportunities/{oid}")
    check(s == 403, f"begona hodim uchun 403 (HTTP {s})")
    s, _ = cn.call("DELETE", f"/erp/opportunities/{oid}/assignees/{b_hujjat}")
    check(s == 403, f"broker jamoadan chiqara olmaydi (HTTP {s})")

    head("6. Chat a'zoligi")
    s, r = cn.call("GET", f"/erp/opportunities/{oid}/chat")
    check(s == 200, f"narxchi karta chatiga kira oladi (HTTP {s})")
    chat_id = (r or {}).get("chat_id")
    u_narx = db.scalar("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                       "AND active LIMIT 1", {"b": b_narx})
    check(bool(db.query_one(
        "SELECT 1 AS x FROM erp.chat_member WHERE chat_id = %(c)s "
        "AND app_user_id = %(u)s AND removed_at IS NULL",
        {"c": chat_id, "u": u_narx})), "chat_member qatori qo'shildi")

    head("7. Chiqarilganda chat yopiladi")
    s, r = cm.call("DELETE", f"/erp/opportunities/{oid}/assignees/{b_narx}")
    check(s == 200, f"menejer chiqardi (HTTP {s})")
    s, _ = cn.call("GET", f"/erp/opportunities/{oid}")
    check(s == 403, f"chiqarilgan hodim kartani ENDI KO'RMAYDI (HTTP {s})")
    check(not db.query_one(
        "SELECT 1 AS x FROM erp.chat_member WHERE chat_id = %(c)s "
        "AND app_user_id = %(u)s AND removed_at IS NULL",
        {"c": chat_id, "u": u_narx}), "chatdan ham chiqarildi")
    # QATOR QOLADI — "kim qachon jamoada edi" javobsiz qolmasin.
    check(db.scalar("SELECT count(*) FROM erp.opportunity_assignee "
                    "WHERE opportunity_id = %(o)s AND broker_id = %(b)s",
                    {"o": oid, "b": b_narx}) == 1,
          "a'zolik qatori O'CHIRILMADI (yumshoq chiqarish)")

    head("8. Bildirishnoma")
    n = db.scalar("SELECT count(*) FROM erp.notification "
                  "WHERE app_user_id = %(u)s AND kind = ANY(%(k)s)",
                  {"u": u_narx, "k": ["jamoa_qoshildi", "jamoa_chiqarildi",
                                      "vazifa"]})
    check(n >= 3, f"jamoa va vazifa bildirishnomalari yozildi ({n} ta)")
    s, r = cn.call("GET", "/erp/notifications?only_unread=true")
    check(s == 200 and (r or {}).get("unread", 0) > 0,
          f"hodim ularni ilovada ko'radi: {(r or {}).get('unread')}")

    head("9. Jurnal")
    j_vazifa = db.scalar("SELECT count(*) FROM erp.doc_audit "
                         "WHERE doc_type = 'vazifa' AND doc_id = %(i)s",
                         {"i": tid})
    check(j_vazifa >= 3, f"vazifa tarixi yozildi ({j_vazifa} ta yozuv)")
    j_jamoa = db.scalar("SELECT count(*) FROM erp.doc_audit "
                        "WHERE doc_type = 'karta' AND entity = 'jamoa' "
                        "AND doc_id = %(o)s", {"o": oid})
    check(j_jamoa >= 3, f"jamoa tarixi yozildi ({j_jamoa} ta yozuv)")
    kim = db.scalar("SELECT full_name FROM erp.app_user WHERE id = %(i)s",
                    {"i": u_men})
    check(db.scalar("SELECT actor FROM erp.doc_audit WHERE doc_type = 'vazifa' "
                    "AND doc_id = %(i)s ORDER BY id LIMIT 1",
                    {"i": tid}) == kim,
          "jurnalda SESSIYADAGI odam turadi")

    head("10. Yuklama")
    s, _ = cc.call("GET", "/erp/workload")
    check(s == 403, f"brokerga yuklama YOPIQ (HTTP {s})")
    s, r = cm.call("GET", "/erp/workload")
    check(s == 200, f"menejerga ochiq (HTTP {s})")
    check(any(x["broker_id"] == b_hujjat and x["ochiq_karta"] >= 1
              for x in (r or [])), "jamoadagi karta yuklamada sanaldi")


def tozala():
    """Sinov yozuvlarini olib tashlaydi. TARTIB muhim: tashqi kalitlar."""
    head("Tozalash")
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('erp.audit_purge', 'on', false)")
            cur.execute("DELETE FROM erp.notification WHERE app_user_id = ANY("
                        "  SELECT id FROM erp.app_user WHERE username LIKE %(u)s)"
                        " OR matn LIKE %(p)s",
                        {"u": PREFIX + "%", "p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message_history WHERE message_id IN "
                        "(SELECT m.id FROM erp.chat_message m JOIN erp.chat c "
                        " ON c.id = m.chat_id WHERE c.opportunity_id IN "
                        " (SELECT id FROM erp.opportunity WHERE title LIKE %(p)s))",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message WHERE chat_id IN "
                        "(SELECT id FROM erp.chat WHERE opportunity_id IN "
                        " (SELECT id FROM erp.opportunity WHERE title LIKE %(p)s))",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_member WHERE chat_id IN "
                        "(SELECT id FROM erp.chat WHERE opportunity_id IN "
                        " (SELECT id FROM erp.opportunity WHERE title LIKE %(p)s))",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat WHERE opportunity_id IN "
                        "(SELECT id FROM erp.opportunity WHERE title LIKE %(p)s)",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_task WHERE title LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_assignee "
                        "WHERE opportunity_id IN (SELECT id FROM erp.opportunity "
                        " WHERE title LIKE %(p)s)", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_history "
                        "WHERE opportunity_id IN (SELECT id FROM erp.opportunity "
                        " WHERE title LIKE %(p)s)", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.doc_audit WHERE doc_id IN "
                        "(SELECT id FROM erp.opportunity WHERE title LIKE %(p)s)"
                        " AND doc_type = 'karta'", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity WHERE title LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            # Hisob bog'lanishi AVVAL uziladi, aks holda hodimni
            # o'chirib bo'lmaydi (tashqi kalit).
            cur.execute("UPDATE erp.app_user SET active = FALSE, "
                        "broker_id = NULL WHERE username LIKE %(u)s",
                        {"u": PREFIX + "%"})
            cur.execute("DELETE FROM erp.broker WHERE full_name LIKE %(p)s",
                        {"p": MARK + "%"})
        conn.commit()
    qoldiq = (db.scalar("SELECT count(*) FROM erp.opportunity "
                        "WHERE title LIKE %(p)s", {"p": "%" + MARK + "%"})
              + db.scalar("SELECT count(*) FROM erp.broker "
                          "WHERE full_name LIKE %(p)s", {"p": MARK + "%"}))
    check(qoldiq == 0, "sinov yozuvlari tozalandi", f"qoldiq={qoldiq}")


def main() -> int:
    ap = argparse.ArgumentParser(description="28-patch joylashtirish darvozasi")
    ap.add_argument("--base", default="http://127.0.0.1:8100",
                    help="ERP backend manzili (default: local)")
    ap.add_argument("--tasdiq", action="store_true",
                    help="mahalliy BO'LMAGAN muhitda ishlashga ruxsat")
    a = ap.parse_args()
    base = a.base.rstrip("/")

    mahalliymi = any(h in base for h in MAHALLIY)
    if not mahalliymi and not a.tasdiq:
        print(f"TO'XTATILDI: {base} mahalliy manzil emas.\n"
              "Bu sinov HAQIQIY yozuv yaratadi (hodim, karta, vazifa) va\n"
              "oxirida tozalaydi. Ishlab chiqarish bazasida jurnalda iz\n"
              "qoladi va uni orqaga qaytarib bo'lmaydi.\n"
              "Ataylab bo'lsa: --tasdiq bilan qayta ishga tushiring.")
        return 2

    db.init_pool()
    try:
        yur(base)
    finally:
        tozala()
        db.close_pool()

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
