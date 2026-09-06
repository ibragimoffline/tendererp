"""
JAMOA va UMUMIY VAZIFALAR sinovi (28-patch) — `api/erp/jamoa.py`,
`api/erp/tasks.py` va ularning egalik/chat/bildirishnoma bilan
bog'lanishi.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp_jamoa_test.py

NIMA UCHUN: bu ikki funksiya HUQUQ chegarasini o'zgartiradi — jamoaga
qo'shilgan odam kartani, chatini va vazifalarini KO'RA BOSHLAYDI.
Shuning uchun sinov beshta buzilish sinfini qo'riqlaydi:

  1) HUQUQ KENGAYIB KETISHI. Jamoaga qo'shish faqat O'SHA kartani
     ochishi kerak, boshqasini emas. Chiqarilgan odam esa darhol
     yopilishi kerak — "chiqardim, lekin hali ham ko'radi" eng yomon
     variant, chunki hech kim sezmaydi.
  2) HUQUQ OCHILMAY QOLISHI. Teskarisi ham nuqson: jamoaga
     qo'shilgan narxchi kartani ocha olmasa, u mas'ulning hisobidan
     kirishga majbur bo'ladi va audit ma'nosini yo'qotadi.
  3) IKKI MAS'UL. Asosiy mas'ul BITTA bo'lishi kerak; u
     `opportunity.broker_id` da va jamoa jadvalida IKKINCHI marta
     paydo bo'lmasligi kerak.
  4) UMUMIY VAZIFANING JIM YO'QOLISHI. `JOIN erp.opportunity`
     kartasiz vazifani ro'yxatdan ham, eslatmadan ham tashlab
     yuborardi — xato bermasdan.
  5) YAKUNLANGAN ISHNING YO'QOLISHI. Bajarilgan/bekor qilingan
     vazifa TARIX: u o'chirilmasligi va jurnalda izi qolishi kerak.

Belgisi: 'ZZTEST-JAMOA'. Oxirida tozalanadi.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # fixture.py

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

import fixture as FIX  # noqa: E402
from api import db  # noqa: E402
from api.erp import chat as C  # noqa: E402
from api.erp import egalik as E  # noqa: E402
from api.erp import jamoa as J  # noqa: E402
from api.erp import opportunity as O  # noqa: E402
from api.erp import perm as P  # noqa: E402
from api.erp import tasks as T  # noqa: E402
from api.erp import xabar as X  # noqa: E402

MARK = "ZZTEST-JAMOA"
PREFIX = "zztest_jam"

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


def xato(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except O.ErpError as e:
        return e.code, str(e)
    return None, None


# ---------------------------------------------------------------------------
# Yordamchi
# ---------------------------------------------------------------------------
def _broker(nom, active=True):
    r = db.query_one("SELECT id FROM erp.broker WHERE full_name = %(n)s",
                     {"n": nom})
    if r:
        db.execute_returning("UPDATE erp.broker SET active = %(a)s "
                             "WHERE id = %(i)s RETURNING id",
                             {"i": r["id"], "a": active})
        return r["id"]
    return db.execute_returning(
        "INSERT INTO erp.broker (full_name, active) VALUES (%(n)s, %(a)s) "
        "RETURNING id", {"n": nom, "a": active})["id"]


def _user(username, rol, broker_id=None):
    u = db.query_one("SELECT id FROM erp.app_user WHERE username = %(u)s",
                     {"u": username})
    if u:
        db.execute_returning(
            "UPDATE erp.app_user SET active = TRUE, role = %(r)s, "
            "broker_id = %(b)s WHERE id = %(id)s RETURNING id",
            {"id": u["id"], "r": rol, "b": broker_id})
        return u["id"]
    return db.execute_returning(
        "INSERT INTO erp.app_user (username, full_name, password_hash, role, "
        "broker_id, active) VALUES (%(u)s, %(f)s, 'x', %(r)s, %(b)s, TRUE) "
        "RETURNING id",
        {"u": username, "f": f"{MARK} {rol}", "r": rol, "b": broker_id})["id"]


def _foydalanuvchi(uid, rol, broker_id):
    """`egalik`/`perm` uchun minimal foydalanuvchi (sessiyadagi shakl)."""
    return {"id": uid, "role": rol, "broker_id": broker_id, "active": True}


def _karta(broker_id):
    """Sinov kartasi. `public.tender` dan O'QILADI, yozilmaydi."""
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


def _oqilmagan(uid, kind=None):
    sql = ("SELECT count(*) FROM erp.notification "
           "WHERE app_user_id = %(u)s AND read_at IS NULL")
    if kind:
        sql += " AND kind = %(k)s"
    return db.scalar(sql, {"u": uid, "k": kind}) or 0


# ---------------------------------------------------------------------------
# 1. Sof mantiq — bazasiz
# ---------------------------------------------------------------------------
def test_mantiq():
    head("1. Rollar, holatlar va huquq matritsasi (bazasiz)")

    # ROLLAR RO'YXATI QISQA (§12): o'ntadan ortiq rol tanlanmay
    # qolardi va hamma "kuzatuvchi" ni bosardi.
    check(len(J.ROLLAR) <= 8, f"jamoa rollari qisqa ({len(J.ROLLAR)} ta)")
    check(J.ASOSIY_ROL not in J.ROLLAR,
          "asosiy mas'ul rollar ro'yxatida YO'Q (u kartada, jadvalda emas)")

    # HOLATLAR: kechikkan holat SAQLANMAYDI — u hisoblanadi.
    eq("to'rtta holat", sorted(T.STATUSLAR),
       ["bajarildi", "bajarilmoqda", "bekor", "yangi"])
    check("kechikkan" not in T.STATUSLAR and "overdue" not in T.STATUSLAR,
          "KECHIKKAN holat sifatida saqlanmaydi (hisoblanadi)")
    eq("ochiq holatlar", sorted(T.OCHIQ), ["bajarilmoqda", "yangi"])

    # USTUVORLIK — kartadagi bilan BIR XIL shkala.
    from api.erp.opportunity import PRIORITIES
    eq("ustuvorlik shkalasi kartadagi bilan bir xil",
       T.PRIORITIES, PRIORITIES)

    # HUQUQ: broker jamoaga qo'sha oladi, CHIQARA olmaydi.
    br = {"role": "broker"}
    eq("broker: jamoaga qo'shish — o'z kartasida",
       P.can(br, "karta.jamoa_qosh"), P.OZ)
    eq("broker: jamoadan chiqarish YO'Q",
       P.can(br, "karta.jamoa_chiqar"), None)
    eq("broker: boshqaga vazifa biriktirish YO'Q",
       P.can(br, "vazifa.biriktirish"), None)
    eq("broker: o'ziga vazifa qo'yish — mumkin",
       P.can(br, "vazifa.yaratish"), P.OZ)
    eq("broker: yuklama ko'rinishi YO'Q",
       P.can(br, "vazifa.yuklama"), None)
    # ADMIN ish taqsimlamaydi (`erp_rollar.md` §3.6).
    eq("matritsada admin vazifa biriktirmaydi",
       P.AMALLAR["vazifa.biriktirish"][1]["admin"], None)
    eq("matritsada admin jamoaga qo'shmaydi",
       P.AMALLAR["karta.jamoa_qosh"][1]["admin"], None)


# ---------------------------------------------------------------------------
# 2. Sxema
# ---------------------------------------------------------------------------
def test_sxema():
    head("2. 28-patch sxemasi")
    check(J.schema_ready(), "erp.opportunity_assignee jadvali bor")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.columns WHERE "
        "table_schema='erp' AND table_name='opportunity_task' "
        "AND column_name='status'")), "opportunity_task.status ustuni bor")
    eq("opportunity_id endi NULL bo'lishi mumkin",
       db.scalar("SELECT is_nullable FROM information_schema.columns "
                 "WHERE table_schema='erp' AND table_name='opportunity_task' "
                 "AND column_name='opportunity_id'"), "YES")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM pg_indexes WHERE schemaname='erp' "
        "AND indexname='opp_assignee_faol_uk'")),
        "faol a'zolik noyob indeksi bor (takror biriktirish to'siladi)")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.views WHERE "
        "table_schema='erp' AND table_name='v_hodim_yuklama'")),
        "yuklama view'i bor")
    # JURNAL TRIGGERI ulanganmi.
    for jadval in ("opportunity_task", "opportunity_assignee"):
        check(bool(db.query_one(
            "SELECT 1 AS x FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "WHERE c.relname = %(j)s AND t.tgname = 'doc_audit_trg'",
            {"j": jadval})), f"{jadval}: jurnal triggeri ulangan")


# ---------------------------------------------------------------------------
# 3. Umumiy vazifa
# ---------------------------------------------------------------------------
def test_umumiy_vazifa():
    head("3. Umumiy vazifa (tendersiz)")
    b_ishchi = _broker(f"{MARK} Ishchi")
    b_begona = _broker(f"{MARK} Begona")
    u_ishchi = _user(f"{PREFIX}_ishchi", "broker", b_ishchi)
    u_begona = _user(f"{PREFIX}_begona", "broker", b_begona)
    u_menejer = _user(f"{PREFIX}_menejer", "menejer")
    X.oqildi(u_ishchi)

    r = T.add(None, {"title": f"{MARK} sertifikatni yangilash",
                     "assignee_broker_id": b_ishchi, "priority": "high",
                     "note": "Litsenziya muddati tugayapti",
                     "created_by": MARK, "actor_user_id": u_menejer})
    eq("bitta vazifa qaytdi", len(r), 1)
    t = r[0]
    tid = t["id"]
    eq("kartaga bog'lanmagan", t["opportunity_id"], None)
    eq("kontekst — umumiy", t["kontekst"], "umumiy")
    eq("karta konteksti YO'Q (bo'sh obyekt emas)", t["opportunity"], None)
    eq("holat — yangi", t["status"], "yangi")
    eq("ustuvorlik saqlandi", t["priority"], "high")
    check(t["priority_label"], "ustuvorlik yorlig'i bor")

    # BILDIRISHNOMA (§18): biriktirilgan odam xabar oladi.
    eq("bajaruvchiga bildirishnoma keldi", _oqilmagan(u_ishchi, "vazifa"), 1)
    n = db.query_one("SELECT task_id, matn FROM erp.notification "
                     "WHERE app_user_id = %(u)s AND kind = 'vazifa' "
                     "ORDER BY id DESC LIMIT 1", {"u": u_ishchi})
    eq("bildirishnoma nishoni — AYNAN shu vazifa", n["task_id"], tid)

    # BIRIKTIRUVCHI O'ZI xabar olmaydi (§18).
    eq("biriktirgan menejer o'ziga xabar olmadi",
       _oqilmagan(u_menejer, "vazifa"), 0)

    # RO'YXATDA KO'RINADI — `JOIN` nuqsoni qaytmasin.
    mine = T.my_tasks(b_ishchi, days=30)
    check(any(x["id"] == tid for x in
              mine["overdue"] + mine["today"] + mine["later"]),
          "umumiy vazifa 'mening ishlarim' da KO'RINADI")
    umumiy = T.royxat(kontekst="umumiy", limit=50)
    check(any(x["id"] == tid for x in umumiy), "kontekst filtri ishlaydi")
    karta_only = T.royxat(kontekst="karta", limit=50)
    check(not any(x["id"] == tid for x in karta_only),
          "'karta' filtrida umumiy vazifa YO'Q")

    # EGALIK: bajaruvchi ko'radi, begona KO'RMAYDI.
    check(E.tegishli(_foydalanuvchi(u_ishchi, "broker", b_ishchi),
                     "task", tid), "bajaruvchi o'z vazifasini ko'radi")
    check(not E.tegishli(_foydalanuvchi(u_begona, "broker", b_begona),
                         "task", tid),
          "BEGONA hodim umumiy vazifani KO'RMAYDI")
    begonaniki = T.royxat(limit=100, owner_broker_id=b_begona)
    check(not any(x["id"] == tid for x in begonaniki),
          "begona hodimning ro'yxatida u YO'Q")

    # FAOLSIZ HODIM rad etiladi (§31.11).
    b_faolsiz = _broker(f"{MARK} Faolsiz", active=False)
    kod, matn = xato(T.add, None, {"title": f"{MARK} faolsizga",
                                   "assignee_broker_id": b_faolsiz,
                                   "created_by": MARK})
    eq("faolsiz hodimga vazifa berilmaydi", kod, 400)
    check("Faolsizlantirilgan" in (matn or ""), "sabab ochiq aytiladi")
    kod, _ = xato(T.add, None, {"title": f"{MARK} yo'q hodim",
                                "assignee_broker_id": 99999999,
                                "created_by": MARK})
    eq("mavjud bo'lmagan hodim -> 404", kod, 404)
    return {"tid": tid, "b_ishchi": b_ishchi, "b_begona": b_begona,
            "u_ishchi": u_ishchi, "u_begona": u_begona,
            "u_menejer": u_menejer}


# ---------------------------------------------------------------------------
# 4. Vazifa hayot sikli
# ---------------------------------------------------------------------------
def test_hayot_sikli(ctx):
    head("4. Vazifa: holat, qayta biriktirish, kechikish")
    tid, b_ishchi = ctx["tid"], ctx["b_ishchi"]
    u_ishchi, u_menejer = ctx["u_ishchi"], ctx["u_menejer"]

    # BOSHLASH.
    r = T.holat(tid, "bajarilmoqda", MARK, u_menejer)[0]
    eq("holat — bajarilmoqda", r["status"], "bajarilmoqda")
    eq("hali ochiq", r["ochiq"], True)
    eq("`done` ko'zgusi FALSE", r["done"], False)

    # BAJARISH — `done` va `done_at` ni TRIGGER qo'yadi.
    X.oqildi(u_ishchi)
    r = T.holat(tid, "bajarildi", MARK, u_menejer)[0]
    eq("holat — bajarildi", r["status"], "bajarildi")
    eq("`done` ko'zgusi TRUE", r["done"], True)
    check(r["done_at"], "bajarilgan vaqt yozildi")
    eq("bekor vaqti bo'sh", r["cancelled_at"], None)
    eq("endi ochiq emas", r["ochiq"], False)
    eq("bajaruvchiga xabar ketdi", _oqilmagan(u_ishchi, "vazifa"), 1)

    # QAYTA OCHISH (§9) — xato bosilgan "bajarildi" tuzatilishi kerak.
    r = T.holat(tid, "yangi", MARK, u_menejer)[0]
    eq("qayta ochildi", r["status"], "yangi")
    eq("bajarilgan vaqti tozalandi", r["done_at"], None)
    eq("`done` ko'zgusi qaytdi", r["done"], False)

    # BEKOR QILISH — "bajarildi" dan AJRALADI.
    r = T.holat(tid, "bekor", MARK, u_menejer)[0]
    eq("holat — bekor", r["status"], "bekor")
    check(r["cancelled_at"], "bekor qilingan vaqt yozildi")
    eq("bajarilgan deb HISOBLANMAYDI", r["done_at"], None)
    check(r["done"], "eski `done` ustuni uchun u 'ochiq emas'")

    # YAKUNLANGAN VAZIFA O'CHIRILMAYDI (§26).
    kod, matn = xato(T.delete, tid, MARK)
    eq("yakunlangan vazifa o'chirilmaydi", kod, 400)
    check("tarix" in (matn or "").lower(), "sabab: u ish tarixi")

    T.holat(tid, "yangi", MARK, u_menejer)

    # QAYTA BIRIKTIRISH (§9).
    X.oqildi(u_ishchi)
    yangi_b = ctx["b_begona"]
    r = T.biriktir(tid, yangi_b, MARK, u_menejer)[0]
    eq("yangi bajaruvchi", r["assignee"]["id"], yangi_b)
    eq("yangi bajaruvchiga xabar", _oqilmagan(ctx["u_begona"], "vazifa"), 1)
    eq("ESKI bajaruvchiga ham xabar (ish jim yo'qolmasin)",
       _oqilmagan(u_ishchi, "vazifa"), 1)
    T.biriktir(tid, b_ishchi, MARK, u_menejer)

    # KECHIKKAN — HISOBLANADI, saqlanmaydi.
    db.execute_returning("UPDATE erp.opportunity_task "
                         "SET due_at = current_date - 3 WHERE id = %(i)s "
                         "RETURNING id", {"i": tid})
    r = T.bitta(tid)
    eq("kechikkan deb hisoblandi", r["overdue"], True)
    kech = T.royxat(overdue=True, limit=100)
    check(any(x["id"] == tid for x in kech), "kechikkanlar filtri topdi")
    # BAJARILGANI KECHIKKAN EMAS: yopilgan ish diqqat talab qilmaydi (§20).
    T.holat(tid, "bajarildi", MARK, u_menejer)
    eq("bajarilgan vazifa kechikkan EMAS", T.bitta(tid)["overdue"], False)
    kech2 = T.royxat(overdue=True, limit=100)
    check(not any(x["id"] == tid for x in kech2),
          "bajarilgani kechikkanlar ro'yxatidan chiqdi")
    T.holat(tid, "yangi", MARK, u_menejer)

    # TARIX (§22) — MAVJUD jurnalda.
    tarix = T.tarix(tid)
    check(len(tarix) >= 5, f"jurnalda {len(tarix)} ta yozuv bor")
    amallar = {t["action"] for t in tarix}
    check("create" in amallar, "yaratilgani yozilgan")
    maydonlar = {t["field"] for t in tarix if t["action"] == "update"}
    check("status" in maydonlar, "holat o'zgarishlari yozilgan")
    check("assignee_broker_id" in maydonlar, "qayta biriktirish yozilgan")
    check(any(t["actor"] == MARK for t in tarix),
          "KIM o'zgartirgani yozilgan (actor)")
    check(not any(t["field"] == "done" for t in tarix),
          "`done` ko'zgusi jurnalni IKKILANTIRMAYDI")


# ---------------------------------------------------------------------------
# 5. Karta jamoasi
# ---------------------------------------------------------------------------
def test_jamoa(ctx):
    head("5. Karta jamoasi")
    b_masul = _broker(f"{MARK} Mas'ul")
    b_narx = ctx["b_ishchi"]
    b_hujjat = ctx["b_begona"]
    u_masul = _user(f"{PREFIX}_masul", "broker", b_masul)
    u_menejer = ctx["u_menejer"]
    oid = _karta(b_masul)
    C.karta_chati_yarat(oid, f"{MARK} karta", b_masul, u_masul)

    # BOSHIDA faqat asosiy mas'ul.
    r = J.royxat(oid)
    eq("boshida bitta a'zo", r["soni"], 1)
    eq("u — asosiy", r["azolar"][0]["asosiy"], True)
    eq("asosiy mas'ul kartadan olinadi", r["asosiy_broker_id"], b_masul)

    # BIRINCHI A'ZO.
    X.oqildi(ctx["u_ishchi"])
    r = J.qosh(oid, b_narx, "narx", u_menejer, MARK)
    eq("ikkita a'zo", r["soni"], 2)
    narx = next(a for a in r["azolar"] if a["broker_id"] == b_narx)
    eq("roli saqlandi", narx["rol"], "narx")
    check(narx["rol_label"], "rol yorlig'i bor")
    eq("asosiy emas", narx["asosiy"], False)
    eq("qo'shilgan hodimga bildirishnoma",
       _oqilmagan(ctx["u_ishchi"], "jamoa_qoshildi"), 1)

    # IKKINCHI A'ZO.
    r = J.qosh(oid, b_hujjat, "hujjat", u_menejer, MARK)
    eq("uchta a'zo", r["soni"], 3)
    rollar = {a["broker_id"]: a["rol"] for a in r["azolar"]}
    eq("har kimning o'z mas'uliyati", rollar[b_hujjat], "hujjat")

    # TAKROR BIRIKTIRISH to'siladi (§32.3).
    kod, matn = xato(J.qosh, oid, b_narx, "texnik", u_menejer, MARK)
    eq("takror biriktirish rad etildi", kod, 409)
    check("allaqachon" in (matn or ""), "sabab ochiq aytiladi")
    # ASOSIY MAS'ULNI jamoaga qo'shib bo'lmaydi — ikki marta ko'rinardi.
    kod, _ = xato(J.qosh, oid, b_masul, "narx", u_menejer, MARK)
    eq("asosiy mas'ulni jamoaga qo'shib bo'lmaydi", kod, 409)
    # FAOLSIZ hodim ham.
    kod, _ = xato(J.qosh, oid, _broker(f"{MARK} Faolsiz", active=False),
                  "narx", u_menejer, MARK)
    eq("faolsiz hodim jamoaga qo'shilmaydi", kod, 400)
    kod, _ = xato(J.qosh, oid, b_narx, "yolgon_rol", u_menejer, MARK)
    eq("noma'lum rol rad etiladi", kod, 400)

    # ROL O'ZGARTIRISH (§32.7).
    r = J.rol_ozgart(oid, b_hujjat, "yuridik", u_menejer, MARK)
    yangi = next(a for a in r["azolar"] if a["broker_id"] == b_hujjat)
    eq("rol o'zgardi", yangi["rol"], "yuridik")
    eq("a'zolar soni o'zgarmadi", r["soni"], 3)

    # MAS'UL BOSHQA YO'L BILAN o'zgarsa ham ro'yxat BUZILMAYDI.
    #
    # `PUT /erp/opportunities/{id}` (kartani tahrirlash formasi)
    # `broker_id` ni to'g'ridan-to'g'ri yozadi va `asosiy_qil()` dan
    # o'tmaydi. Jamoada bo'lgan odam shu yo'l bilan mas'ul qilinsa,
    # u ro'yxatda IKKI marta ko'rinardi: "Mas'ul" va "Narx".
    db.execute_returning("UPDATE erp.opportunity SET broker_id = %(b)s "
                         "WHERE id = %(o)s RETURNING id",
                         {"b": b_narx, "o": oid})
    r = J.royxat(oid)
    idlar = [a["broker_id"] for a in r["azolar"]]
    eq("bir odam ro'yxatda BIR marta", len(idlar), len(set(idlar)))
    eq("va u ASOSIY deb ko'rsatiladi",
       [a["asosiy"] for a in r["azolar"] if a["broker_id"] == b_narx], [True])
    db.execute_returning("UPDATE erp.opportunity SET broker_id = %(b)s "
                         "WHERE id = %(o)s RETURNING id",
                         {"b": b_masul, "o": oid})

    # HUQUQ: jamoa a'zosi kartani KO'RADI (§2 buzilish sinfi).
    fnarx = _foydalanuvchi(ctx["u_ishchi"], "broker", b_narx)
    check(E.tegishli(fnarx, "opportunity", oid),
          "jamoa a'zosi kartani ochа oladi")
    check(J.azomi(oid, b_narx), "azomi() jamoani biladi")
    check(J.azomi(oid, b_masul), "azomi() asosiy mas'ulni ham biladi")
    ozga = _broker(f"{MARK} Chetdagi")
    check(not J.azomi(oid, ozga), "chetdagi hodim a'zo emas")
    check(not E.tegishli(_foydalanuvchi(0, "broker", ozga),
                         "opportunity", oid),
          "chetdagi hodim kartani KO'RMAYDI")

    # RO'YXAT FILTRI: jamoadagi karta o'z ro'yxatida ko'rinadi.
    mening = O.list_(broker_id=b_narx)
    check(any(o["id"] == oid for o in mening),
          "jamoadagi karta hodimning ro'yxatida ko'rinadi")

    # CHAT: a'zolik jamoaga ergashadi (§17).
    chat_id = C.karta_chati(oid)
    u_narx = db.scalar("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                       "AND active LIMIT 1", {"b": b_narx})
    check(bool(db.query_one(C.AZOMI_SQL, {"chat": chat_id, "uid": u_narx})),
          "jamoa a'zosi karta chatiga QO'SHILDI")
    return {"oid": oid, "b_masul": b_masul, "b_narx": b_narx,
            "b_hujjat": b_hujjat, "u_masul": u_masul, "chat_id": chat_id,
            "u_narx": u_narx, **ctx}


# ---------------------------------------------------------------------------
# 6. Asosiy mas'ulni almashtirish va chiqarish
# ---------------------------------------------------------------------------
def test_asosiy_va_chiqarish(ctx):
    head("6. Asosiy mas'ul va jamoadan chiqarish")
    oid, b_masul, b_narx = ctx["oid"], ctx["b_masul"], ctx["b_narx"]
    u_menejer = ctx["u_menejer"]

    # ASOSIY MAS'ULNI chiqarib bo'lmaydi.
    kod, matn = xato(J.chiqar, oid, b_masul, u_menejer, MARK)
    eq("asosiy mas'ulni chiqarib bo'lmaydi", kod, 400)
    check("avval boshqa" in (matn or ""), "nima qilish kerakligi aytiladi")

    # ASOSIYNI ALMASHTIRISH (§11).
    X.oqildi(ctx["u_ishchi"])
    X.oqildi(ctx["u_masul"])
    r = J.asosiy_qil(oid, b_narx, u_menejer, MARK)
    eq("yangi asosiy", r["asosiy_broker_id"], b_narx)
    asosiylar = [a for a in r["azolar"] if a["asosiy"]]
    eq("ASOSIY BITTA (tuzilma darajasida)", len(asosiylar), 1)
    eq("va u yangi hodim", asosiylar[0]["broker_id"], b_narx)
    # Yangi asosiy jamoa qatorida IKKINCHI marta turmasin.
    eq("yangi asosiy ro'yxatda bir marta",
       len([a for a in r["azolar"] if a["broker_id"] == b_narx]), 1)
    # ESKI mas'ul jamoada QOLADI — konteksti kerak.
    eski = [a for a in r["azolar"] if a["broker_id"] == b_masul]
    eq("eski mas'ul jamoada qoldi", len(eski), 1)
    eq("kuzatuvchi bo'ldi", eski[0]["rol"], "kuzatuvchi")
    check(E.tegishli(_foydalanuvchi(ctx["u_masul"], "broker", b_masul),
                     "opportunity", oid),
          "eski mas'ul kartani hali ham ko'radi")
    eq("yangi mas'ulga xabar", _oqilmagan(ctx["u_ishchi"], "otkazildi"), 1)
    eq("eski mas'ulga ham xabar",
       _oqilmagan(ctx["u_masul"], "biriktirish_olib_tashlandi"), 1)

    # CHIQARISH — YUMSHOQ (§26).
    X.oqildi(ctx["u_masul"])
    r = J.chiqar(oid, b_masul, u_menejer, MARK)
    check(not any(a["broker_id"] == b_masul and not a["removed_at"]
                  for a in r["azolar"]), "chiqarilgan a'zo ro'yxatda yo'q")
    eq("chiqarilganga xabar",
       _oqilmagan(ctx["u_masul"], "jamoa_chiqarildi"), 1)
    # QATOR QOLADI: "kim qachon jamoada edi" javobsiz qolmasin.
    tarix = J.royxat(oid, tarix=True)
    chiqarilgan = [a for a in tarix["azolar"]
                   if a["broker_id"] == b_masul and a["removed_at"]]
    eq("tarixda chiqarilgan qator QOLDI", len(chiqarilgan), 1)
    eq("bazada ham qator o'chmadi",
       db.scalar("SELECT count(*) FROM erp.opportunity_assignee "
                 "WHERE opportunity_id = %(o)s AND broker_id = %(b)s",
                 {"o": oid, "b": b_masul}), 1)

    # HUQUQ DARHOL YOPILADI (§1 buzilish sinfi).
    check(not E.tegishli(_foydalanuvchi(ctx["u_masul"], "broker", b_masul),
                         "opportunity", oid),
          "chiqarilgan odam kartani ENDI KO'RMAYDI")
    check(not J.azomi(oid, b_masul), "azomi() ham yo'q deydi")
    # CHATDAN ham chiqarildi.
    chat_id = ctx["chat_id"]
    check(not db.query_one(C.AZOMI_SQL,
                           {"chat": chat_id, "uid": ctx["u_masul"]}),
          "chatdan ham chiqarildi (yozishma yopildi)")
    # YOZGANLARI esa lentada QOLADI — chat moduli qoidasi.

    # QAYTA QO'SHISH — yangi qator, eskisini tiriltirish emas.
    J.qosh(oid, b_masul, "texnik", u_menejer, MARK)
    eq("qayta qo'shilgach ikkita davr yozuvi bor",
       db.scalar("SELECT count(*) FROM erp.opportunity_assignee "
                 "WHERE opportunity_id = %(o)s AND broker_id = %(b)s",
                 {"o": oid, "b": b_masul}), 2)
    check(E.tegishli(_foydalanuvchi(ctx["u_masul"], "broker", b_masul),
                     "opportunity", oid), "huquq qaytdi")

    # KARTA TARIXIDA jamoa o'zgarishlari (§22).
    tarix_rows = db.query(
        "SELECT note FROM erp.opportunity_history "
        "WHERE opportunity_id = %(o)s AND note LIKE 'Jamoa%%' "
        "   OR (opportunity_id = %(o)s AND note LIKE 'Asosiy%%')",
        {"o": oid})
    check(len(tarix_rows) >= 3,
          f"karta tarixida jamoa yozuvlari bor ({len(tarix_rows)} ta)")
    # JURNALDA ham (trigger).
    jurnal = db.scalar(
        "SELECT count(*) FROM erp.doc_audit WHERE doc_type = 'karta' "
        "AND entity = 'jamoa' AND doc_id = %(o)s", {"o": oid})
    check(jurnal >= 4, f"jurnalda jamoa o'zgarishlari bor ({jurnal} ta)")


# ---------------------------------------------------------------------------
# 7. Kartadagi vazifalar — har xil hodimlarga
# ---------------------------------------------------------------------------
def test_karta_vazifalari(ctx):
    head("7. Bitta tenderda uch odam, uch vazifa")
    oid, u_menejer = ctx["oid"], ctx["u_menejer"]
    b_narx, b_masul = ctx["b_narx"], ctx["b_masul"]

    T.add(oid, {"title": f"{MARK} marjani hisoblash",
                "assignee_broker_id": b_narx, "created_by": MARK,
                "actor_user_id": u_menejer})
    r = T.add(oid, {"title": f"{MARK} sertifikat tayyorlash",
                    "assignee_broker_id": b_masul, "created_by": MARK,
                    "actor_user_id": u_menejer})
    check(len(r) >= 2, "kartada bir nechta vazifa")
    kimlar = {t["assignee"]["id"] for t in r if t["assignee"]}
    check({b_narx, b_masul} <= kimlar,
          "vazifalar HAR XIL jamoa a'zolariga biriktirilgan")

    # Har kim O'ZINIKINI ko'radi.
    narxniki = T.royxat(opportunity_id=oid, limit=50, owner_broker_id=b_narx)
    check(any(f"marjani" in t["title"] for t in narxniki),
          "narxchi o'z vazifasini ko'radi")
    check(any(f"sertifikat" in t["title"] for t in narxniki),
          "va jamoadosh vazifasini ham ko'radi (bitta tender ustida ishlashadi)")
    chetdagi = _broker(f"{MARK} Chetdagi")
    yoq = T.royxat(opportunity_id=oid, limit=50, owner_broker_id=chetdagi)
    eq("CHETDAGI hodim bu kartaning vazifalarini KO'RMAYDI", len(yoq), 0)

    # YUKLAMA (§21).
    y = T.yuklama()
    narx_row = next((x for x in y if x["broker_id"] == b_narx), None)
    check(narx_row is not None, "yuklama ro'yxatida hodim bor")
    check(narx_row["ochiq_vazifa"] >= 1, "ochiq vazifalari sanaldi")
    check(narx_row["ochiq_karta"] >= 1, "ochiq kartalari sanaldi")
    check("reyting" not in str(y[0]) and "ball" not in str(y[0]),
          "yuklama BAHO bermaydi (reyting/ball yo'q)")


# ---------------------------------------------------------------------------
# 8. Chegara: sxema va begona ma'lumot
# ---------------------------------------------------------------------------
def test_chegara(ctx):
    head("8. Chegara")
    # Tender-AI (`tai_app`) jamoa va vazifani KO'RMAYDI.
    nomlar = sorted(r["table_name"] for r in db.query(
        "SELECT DISTINCT table_name FROM information_schema.role_table_grants "
        "WHERE grantee = 'tai_app' AND table_schema = 'erp'"))
    check(not any("assignee" in n or "task" in n for n in nomlar),
          f"tai_app jamoa/vazifani ko'rmaydi: {nomlar}")
    # SOXTA id.
    kod, _ = xato(J.royxat, 99999999)
    eq("mavjud bo'lmagan karta jamoasi -> 404", kod, 404)
    kod, _ = xato(J.qosh, 99999999, ctx["b_narx"], "narx", None, MARK)
    eq("mavjud bo'lmagan kartaga qo'shish -> 404", kod, 404)
    kod, _ = xato(T.bitta, 99999999)
    eq("mavjud bo'lmagan vazifa -> 404", kod, 404)
    kod, _ = xato(T.holat, 99999999, "bajarildi", MARK)
    eq("mavjud bo'lmagan vazifa holati -> 404", kod, 404)
    kod, _ = xato(T.royxat, None, "yolgon_holat")
    eq("noma'lum holat filtri -> 400", kod, 400)


# ---------------------------------------------------------------------------
# 9. Tozalash
# ---------------------------------------------------------------------------
PUBLIC_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def test_tozalash(before):
    head("9. Chegara va tozalash")
    after = db.query_one(PUBLIC_SQL)
    eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
    eq("public.tender yangilanmadi", after["t_max"], before["t_max"])

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('erp.audit_purge', 'on', false)")
            cur.execute("DELETE FROM erp.notification WHERE matn LIKE %(p)s "
                        "OR app_user_id = ANY(SELECT id FROM erp.app_user "
                        "WHERE username LIKE %(u)s)",
                        {"p": "%" + MARK + "%", "u": PREFIX + "%"})
            cur.execute(
                "DELETE FROM erp.chat_message_history WHERE message_id IN ("
                "  SELECT id FROM erp.chat_message WHERE text LIKE %(p)s)",
                {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message WHERE text LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_member WHERE chat_id IN ("
                        "  SELECT id FROM erp.chat WHERE title LIKE %(p)s)",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_task WHERE title LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_assignee "
                        "WHERE opportunity_id IN (SELECT id FROM erp.opportunity "
                        "WHERE title LIKE %(p)s)", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_history "
                        "WHERE opportunity_id IN (SELECT id FROM erp.opportunity "
                        "WHERE title LIKE %(p)s)", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat WHERE opportunity_id IN ("
                        "  SELECT id FROM erp.opportunity WHERE title LIKE %(p)s)",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.doc_audit WHERE actor = %(m)s",
                        {"m": MARK})
            cur.execute("DELETE FROM erp.opportunity WHERE title LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute("UPDATE erp.app_user SET active = FALSE, "
                        "broker_id = NULL WHERE username LIKE %(p)s",
                        {"p": PREFIX + "%"})
            cur.execute("DELETE FROM erp.broker WHERE full_name LIKE %(p)s",
                        {"p": MARK + "%"})
        conn.commit()
    eq("sinov kartalari tozalandi",
       db.scalar("SELECT count(*) FROM erp.opportunity WHERE title LIKE %(p)s",
                 {"p": "%" + MARK + "%"}), 0)
    eq("sinov vazifalari tozalandi",
       db.scalar("SELECT count(*) FROM erp.opportunity_task "
                 "WHERE title LIKE %(p)s", {"p": "%" + MARK + "%"}), 0)
    eq("sinov hodimlari tozalandi",
       db.scalar("SELECT count(*) FROM erp.broker WHERE full_name LIKE %(p)s",
                 {"p": MARK + "%"}), 0)
    check(FIX.cleanup() >= 0, "fixture tozalandi")


if __name__ == "__main__":
    test_mantiq()
    try:
        db.init_pool()
    except Exception as e:                          # noqa: BLE001
        print(f"\n  DIQQAT: bazasiz sinov: {e}")
    else:
        before = db.query_one(PUBLIC_SQL)
        try:
            test_sxema()
            ctx = test_umumiy_vazifa()
            test_hayot_sikli(ctx)
            ctx = test_jamoa(ctx)
            test_asosiy_va_chiqarish(ctx)
            test_karta_vazifalari(ctx)
            test_chegara(ctx)
        finally:
            test_tozalash(before)
        db.close_pool()

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
