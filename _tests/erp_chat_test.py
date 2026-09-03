"""
ICHKI CHAT sinovi (25-patch) — `docs/erp_chat.md` §8.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp_chat_test.py

NIMA UCHUN: chat — ERP dagi birinchi funksiya bo'lib, unda MA'LUMOT
odamlar o'rtasida yuradi va uni keyin tekshirib bo'lmaydi. Shuning
uchun sinov to'rtta buzilish sinfini qo'riqlaydi:

  1) JIM SIZIB CHIQISH. Broker begona karta chatini KO'RMASLIGI kerak.
     403 emas, jimgina bo'sh lenta qaytsa — hech kim sezmaydi.
  2) IZSIZ O'ZGARTIRISH. Tahrir va o'chirish `chat_message_history`
     ga yozilishi shart, jadval esa O'ZGARMASLIGI. Aks holda "men
     bunday yozmagandim" degan bahsda hakam yo'q.
  3) YOZILGAN NARSANING YO'QOLISHI. O'chirilgan xabar QATORI qoladi;
     unga qilingan javob ham yo'qolmaydi; chatdan chiqarilgan odamning
     yozganlari lentada turaveradi.
  4) "JIMGINA KUZATIB YOZISH". Rahbar chatni a'zosiz o'qiydi, lekin
     yozish uchun o'zini qo'shishi shart va bu qo'shilish LENTADA
     ko'rinadi.

Belgisi: 'ZZTEST-CHAT'. Oxirida tozalanadi (jurnal `audit_purge` bilan).
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
from api.erp import opportunity as O  # noqa: E402
from api.erp import perm as P  # noqa: E402

MARK = "ZZTEST-CHAT"

_fail = 0
_pass = 0
#: Sinov yaratgan hisoblar — oxirida faolsizlantiriladi.
_made_users = []


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
# Yordamchi: sinov hisoblari
# ---------------------------------------------------------------------------
def _user(username, rol, broker_id=None):
    """Sinov hisobi. `erp.app_user` ga to'g'ridan-to'g'ri — parol
    kerak emas, sinov modul darajasida ishlaydi (HTTP emas)."""
    u = db.query_one("SELECT id FROM erp.app_user WHERE username = %(u)s",
                     {"u": username})
    if u:
        db.execute_returning(
            "UPDATE erp.app_user SET active = TRUE, role = %(r)s, "
            "broker_id = %(b)s WHERE id = %(id)s RETURNING id",
            {"id": u["id"], "r": rol, "b": broker_id})
        return u["id"]
    r = db.execute_returning(
        "INSERT INTO erp.app_user (username, full_name, password_hash, role, "
        "broker_id, active) VALUES (%(u)s, %(f)s, 'x', %(r)s, %(b)s, TRUE) "
        "RETURNING id",
        {"u": username, "f": f"{MARK} {rol}", "r": rol, "b": broker_id})
    _made_users.append(r["id"])
    return r["id"]


def _rol(rol):
    """`perm.can()` uchun minimal foydalanuvchi."""
    return {"id": 0, "role": rol, "active": True}


# ---------------------------------------------------------------------------
# 1. Sof mantiq — huquq matritsasi
# ---------------------------------------------------------------------------
def test_huquq():
    head("1. Huquq matritsasi")

    amallar = [a for a in P.AMALLAR if a.startswith("chat.")]
    eq("ettita chat amali bor", len(amallar), 7)

    # ADMIN YOZISHMADA QATNASHMAYDI — "biznes ma'lumotga ko'r".
    #
    # TEKSHIRUV MATRITSA USTIDAN, `can()` ustidan EMAS. Sabab loyihaning
    # mavjud qarori: `admin_faqat_koradi` sozlamasi O'CHIQ turganda
    # admin HAMMA NARSAGA `full` oladi (`api/erp/perm.py` -> `can()`),
    # chunki bitta o'rnatmada admin — aynan ishni yuritayotgan odam.
    # Chat matritsasi o'sha sozlama YOQILGANDA kuchga kiradi.
    for a in ("chat.korish", "chat.yozish", "chat.azo_qosh",
              "chat.azo_chiqar", "chat.moderatsiya", "chat.hammasi"):
        eq(f"matritsada admin: {a} yo'q", P.AMALLAR[a][1]["admin"], None)
    # Yagona istisno: NAZORAT jurnali.
    check(P.AMALLAR["chat.tarix"][1]["admin"] is not None,
          "matritsada admin tahrir tarixini KO'RADI (nazorat)")

    # Broker o'z chatini ko'radi, hammasini emas.
    eq("broker: chat.korish = own", P.can(_rol("broker"), "chat.korish"), P.OZ)
    eq("broker: chat.hammasi yo'q", P.can(_rol("broker"), "chat.hammasi"), None)
    # Chiqarish — nizoli amal, boshliqda qoladi.
    eq("broker: a'zo chiqara olmaydi",
       P.can(_rol("broker"), "chat.azo_chiqar"), None)
    check(P.can(_rol("broker"), "chat.azo_qosh") == P.OZ,
          "broker O'Z kartasiga hamkasb qo'sha oladi")
    eq("broker: moderatsiya yo'q",
       P.can(_rol("broker"), "chat.moderatsiya"), None)
    for r in ("rahbar", "menejer"):
        check(P.can(_rol(r), "chat.hammasi") is not None,
              f"{r} barcha karta chatlarini ko'radi")
        check(P.can(_rol(r), "chat.moderatsiya") is not None,
              f"{r} moderatsiya qila oladi")

    eq("arxiv holatlari = FINAL", C.ARXIV_HOLATLAR, O.FINAL)


# ---------------------------------------------------------------------------
# 2. Sxema
# ---------------------------------------------------------------------------
def test_sxema():
    head("2. Sxema va kafolatlar")

    umumiy = db.query("SELECT id FROM erp.chat WHERE turi = 'umumiy'", {})
    eq("umumiy chat BITTA", len(umumiy), 1)

    # Ikkinchi umumiy chat — BAZA rad etadi (qisman UNIQUE indeks).
    # Ilova qatlamidagi tekshiruvga tayanmaymiz: qo'lda yozilgan SQL
    # ham shu to'siqqa urilishi kerak.
    try:
        db.execute_returning(
            "INSERT INTO erp.chat (turi, title) VALUES ('umumiy', 'x') "
            "RETURNING id")
        check(False, "ikkinchi umumiy chat RAD ETILISHI kerak edi")
    except Exception as e:                          # noqa: BLE001
        check("chat_umumiy_bitta" in str(e),
              "ikkinchi umumiy chat — BAZA rad etadi", str(e)[:70])

    # Tarix jadvali O'ZGARMAYDI (trigger).
    r = db.query_one("SELECT id FROM erp.chat_message_history LIMIT 1")
    if r:
        try:
            db.execute_returning(
                "UPDATE erp.chat_message_history SET old_text = 'x' "
                "WHERE id = %(id)s RETURNING id", {"id": r["id"]})
            check(False, "tarixga UPDATE rad etilishi kerak edi")
        except Exception as e:                      # noqa: BLE001
            check("o'zgartirib bo'lmaydi" in str(e) or "chat_message_history" in str(e),
                  "tarix jadvaliga UPDATE — trigger RAD etadi")
    else:
        print("  SKIP tarix bo'sh — UPDATE to'sig'i 5-bo'limda tekshiriladi")

    # Har kartada chat bor (patch ko'chirgan + `take()` ochadigan).
    yoq = db.query_one(
        "SELECT count(*) AS n FROM erp.opportunity o "
        "WHERE NOT EXISTS (SELECT 1 FROM erp.chat c "
        "                   WHERE c.opportunity_id = o.id)")
    eq("chatsiz karta yo'q", yoq["n"], 0)


# ---------------------------------------------------------------------------
# 3. Haqiqiy oqim
# ---------------------------------------------------------------------------
def test_oqim():
    head("3. Ko'rish, yozish, tahrir, o'chirish")

    opp = FIX.ensure_opportunity()
    if not opp:
        print("  SKIP bazada tender yo'q — ETL yurmagan.")
        return None
    oid = opp["id"]
    # Ochiq holatga qaytaramiz (oldingi sinovdan yakuniy qolgan bo'lishi mumkin).
    if O.get(oid)["is_final"]:
        O.set_status(oid, "reviewing", MARK, MARK + " qayta ochish")

    brk = FIX.ensure_broker()
    egasi = _user("zztest_chat_broker", "broker", brk["id"])
    begona = _user("zztest_chat_begona", "broker")
    boshliq = _user("zztest_chat_rahbar", "rahbar")

    ch = C.karta_chati_id(oid, egasi)
    cid = ch["chat_id"]
    check(cid > 0, "kartaning chati bor", str(ch))

    # --- BEGONA ko'rmaydi -------------------------------------------------
    kod, _ = xato(C.lenta, cid, begona, False)
    eq("begona broker karta chatini KO'RMAYDI -> 403", kod, 403)
    check(all(c["id"] != cid for c in C.chatlarim(begona)),
          "begona brokerning ro'yxatida bu chat YO'Q")
    # Umumiy chat esa hammaga ko'rinadi — a'zosiz.
    check(any(c["turi"] == "umumiy" for c in C.chatlarim(begona)),
          "umumiy chatni HAMMA ko'radi (a'zolik virtual)")

    # --- RAHBAR o'qiydi, lekin YOZOLMAYDI ---------------------------------
    l = C.lenta(cid, boshliq, hammasi=True)
    check(l is not None, "rahbar a'zo bo'lmasa ham LENTANI o'qiydi")
    kod, matn = xato(C.yoz, cid, boshliq, "yozib ko'raman")
    eq("rahbar a'zosiz YOZOLMAYDI -> 403", kod, 403)
    check("qo'shiling" in (matn or ""), "xato NIMA QILISHNI aytadi", matn)

    C.azo_qosh(cid, boshliq, boshliq)
    lenta = C.lenta(cid, boshliq, hammasi=True)["messages"]
    check(any(m["tizim"] and "qo'shildi" in (m["text"] or "")
              for m in lenta),
          "qo'shilish LENTADA ko'rinadi — jimgina kuzatib yozish yo'q")

    # --- Egasi yozadi -----------------------------------------------------
    C.azo_qosh(cid, boshliq, egasi)
    m1 = C.yoz(cid, egasi, f"{MARK} birinchi xabar")
    check(m1["id"] > 0 and not m1["tizim"], "xabar yozildi", str(m1)[:60])
    m2 = C.yoz(cid, boshliq, f"{MARK} javob", reply_to_id=m1["id"])
    eq("javob asl xabarga bog'landi", m2["reply"]["id"], m1["id"])

    # Boshqa chatdagi xabarga javob — bog'lanmaydi.
    umumiy_id = db.query_one("SELECT id FROM erp.chat WHERE turi='umumiy'")["id"]
    um = C.yoz(umumiy_id, egasi, f"{MARK} umumiyda")
    kod, _ = xato(C.yoz, cid, egasi, "x", reply_to_id=um["id"])
    eq("BOSHQA chatdagi xabarga javob -> 400", kod, 400)

    # --- Tahrir -----------------------------------------------------------
    kod, _ = xato(C.tahrir, m1["id"], boshliq, "o'zgartiraman")
    eq("boshqaning xabarini tahrirlash -> 403", kod, 403)
    t = C.tahrir(m1["id"], egasi, f"{MARK} tuzatilgan matn")
    check(t["tahrirlangan"], "tahrir belgisi qo'yildi")
    tar = C.tarix(m1["id"])
    eq("tarixda bitta yozuv", len(tar), 1)
    check("birinchi xabar" in tar[0]["old_text"], "ESKI matn tarixda saqlandi")

    # --- O'chirish --------------------------------------------------------
    kod, matn = xato(C.ochir, m1["id"], boshliq, True, None)
    eq("moderatsiyada IZOHSIZ o'chirish -> 400", kod, 400)
    check("SABAB" in (matn or ""), "xato sababni SO'RAYDI", matn)
    d = C.ochir(m1["id"], boshliq, True, "ZZTEST sabab")
    check(d["ochirilgan"], "o'chirildi")
    eq("matn oddiy foydalanuvchiga BERILMAYDI", d["text"], None)
    qator = db.query_one("SELECT id, text FROM erp.chat_message "
                         "WHERE id = %(i)s", {"i": m1["id"]})
    check(qator is not None and "tuzatilgan" in qator["text"],
          "QATOR va MATN bazada QOLDI (yumshoq o'chirish)")
    eq("tarixda ikkita yozuv (tahrir + o'chirish)",
       len(C.tarix(m1["id"])), 2)

    # Javob o'chirilgan xabarga ishora qiladi, lekin YO'QOLMAYDI.
    lenta = C.lenta(cid, egasi)["messages"]
    javob = [m for m in lenta if m["id"] == m2["id"]][0]
    check(javob["reply"]["ochirilgan"] and javob["reply"]["text"] is None,
          "o'chirilgan xabarga javob KO'RINADI, matni yo'q")

    # Muallifga bildirishnoma ketdi.
    x = db.query_one("SELECT count(*) AS n FROM erp.notification "
                     "WHERE app_user_id = %(u)s AND kind = 'chat_ochirildi'",
                     {"u": egasi})
    check(x["n"] >= 1, "muallifga BILDIRISHNOMA yozildi", str(x))

    # --- Rahbar tarixni to'liq ko'radi ------------------------------------
    to_liq = C.lenta(cid, boshliq, hammasi=True, tarix_korish=True)["messages"]
    ochirilgan = [m for m in to_liq if m["id"] == m1["id"]][0]
    check(ochirilgan["text"] is not None,
          "rahbar o'chirilgan xabar MATNINI ko'radi")

    return {"oid": oid, "cid": cid, "egasi": egasi, "boshliq": boshliq,
            "begona": begona, "umumiy": umumiy_id}


# ---------------------------------------------------------------------------
# 4. A'zolar
# ---------------------------------------------------------------------------
def test_azolar(ctx):
    head("4. A'zolar")
    if not ctx:
        print("  SKIP")
        return
    cid, egasi, boshliq, begona = (ctx["cid"], ctx["egasi"],
                                   ctx["boshliq"], ctx["begona"])

    kod, _ = xato(C.azo_qosh, ctx["umumiy"], boshliq, begona)
    eq("umumiy chatga a'zo qo'shib bo'lmaydi -> 400", kod, 400)
    kod, _ = xato(C.azo_chiqar, ctx["umumiy"], boshliq, egasi)
    eq("umumiy chatdan chiqib bo'lmaydi -> 400", kod, 400)

    C.azo_qosh(cid, boshliq, begona)
    check(any(a["app_user_id"] == begona
              for a in C.azolar(cid, boshliq, True)["members"]),
          "qo'shilgach a'zolar ro'yxatida ko'rinadi")
    check(C.lenta(cid, begona) is not None, "endi lentani O'QIYDI")
    kod, _ = xato(C.azo_qosh, cid, boshliq, begona)
    eq("ikkinchi marta qo'shish -> 409", kod, 409)

    # MAS'ULNI chiqarib bo'lmaydi.
    kod, matn = xato(C.azo_chiqar, cid, boshliq, egasi)
    eq("kartaning MAS'ULINI chiqarish -> 400", kod, 400)
    check("almashtiring" in (matn or ""), "xato yo'lni ko'rsatadi", matn)

    # Boshqasini chiqarish — mumkin, yozganlari QOLADI.
    yozgan = C.yoz(cid, begona, f"{MARK} chiqarilishdan oldin")
    C.azo_chiqar(cid, boshliq, begona)
    check(all(a["app_user_id"] != begona
              for a in C.azolar(cid, boshliq, True)["members"]),
          "chiqarildi")
    kod, _ = xato(C.lenta, cid, begona, False)
    eq("chiqarilgach ko'rmaydi -> 403", kod, 403)
    lenta = C.lenta(cid, boshliq, hammasi=True)["messages"]
    check(any(m["id"] == yozgan["id"] and m["text"] for m in lenta),
          "chiqarilgan a'zoning XABARLARI lentada QOLDI")

    # Qayta qo'shilsa — butun tarix ko'rinadi ("davr kesish" yo'q).
    #
    # Ikkala lenta BIR PAYTDA olinadi: `azo_qosh`/`azo_chiqar` ning
    # o'zi tizim xabari yozadi, ya'ni turli paytdagi sonlarni
    # solishtirish har doim bittaga farq qilardi.
    C.azo_qosh(cid, boshliq, begona)
    l2 = C.lenta(cid, begona)["messages"]
    l3 = C.lenta(cid, boshliq, hammasi=True)["messages"]
    eq("qayta qo'shilgach BUTUN tarix ko'rinadi", len(l2), len(l3))
    check(any(m["id"] == yozgan["id"] for m in l2),
          "chiqarilgan davrdagi o'z xabari ham ko'rinadi")

    # Faolsizlantirilgan hisob qo'shilmaydi.
    db.execute_returning("UPDATE erp.app_user SET active = FALSE "
                         "WHERE id = %(id)s RETURNING id", {"id": begona})
    C.azo_chiqar(cid, boshliq, begona)
    kod, _ = xato(C.azo_qosh, cid, boshliq, begona)
    eq("faolsiz hisobni qo'shish -> 400", kod, 400)
    db.execute_returning("UPDATE erp.app_user SET active = TRUE "
                         "WHERE id = %(id)s RETURNING id", {"id": begona})


# ---------------------------------------------------------------------------
# 5. Arxiv va o'qilganlik
# ---------------------------------------------------------------------------
def test_arxiv_va_oqilganlik(ctx):
    head("5. Arxiv va o'qilmaganlar")
    if not ctx:
        print("  SKIP")
        return
    oid, cid, egasi, boshliq = (ctx["oid"], ctx["cid"],
                               ctx["egasi"], ctx["boshliq"])

    # --- o'qilmaganlar ----------------------------------------------------
    C.yoz(cid, boshliq, f"{MARK} o'qilmagan xabar")
    mine = [c for c in C.chatlarim(egasi) if c["id"] == cid]
    check(mine and mine[0]["oqilmagan"] > 0,
          "o'qilmagan xabar SANALADI", str(mine[:1]))
    C.oqildi(cid, egasi)
    mine = [c for c in C.chatlarim(egasi) if c["id"] == cid]
    eq("o'qilgach hisoblagich nol", mine[0]["oqilmagan"], 0)

    # O'z xabaring o'qilmagan deb sanalmaydi.
    C.yoz(cid, egasi, f"{MARK} o'zim yozdim")
    mine = [c for c in C.chatlarim(egasi) if c["id"] == cid]
    eq("O'Z xabaring o'qilmaganga qo'shilmaydi", mine[0]["oqilmagan"], 0)

    # Chegara ORQAGA ketmaydi (ikki oyna ochiq bo'lsa hisoblagich tirilmasin).
    oxirgi = C.oqildi(cid, egasi)["last_read_id"]
    C.oqildi(cid, egasi, 1)
    eq("o'qilgan chegara ORQAGA ketmaydi",
       C.oqildi(cid, egasi, 1)["last_read_id"], oxirgi)

    # --- arxiv ------------------------------------------------------------
    O.set_status(oid, "rejected", MARK, "sinov", lost_reason="other")
    l = C.lenta(cid, egasi)
    check(l["chat"]["arxiv"], "karta yakunlandi -> chat ARXIV")
    kod, matn = xato(C.yoz, cid, egasi, "arxivda yozaman")
    eq("arxiv chatga yozish -> 400", kod, 400)
    check("arxiv" in (matn or "").lower(), "xato sababni aytadi", matn)
    check(any(m["tizim"] and "Holat:" in (m["text"] or "")
              for m in l["messages"]),
          "status o'zgarishi LENTADA tizim xabari bo'lib ko'rindi")

    O.set_status(oid, "reviewing", MARK, MARK + " qayta ochish")
    l = C.lenta(cid, egasi)
    check(not l["chat"]["arxiv"], "karta qayta ochildi -> chat ham OCHILDI")
    m = C.yoz(cid, egasi, f"{MARK} qayta ochilgach")
    check(m["id"] > 0, "endi yoziladi")


# ---------------------------------------------------------------------------
# 5b. pg_notify — WebSocket uchun tayyorgarlik
# ---------------------------------------------------------------------------
def test_signal(ctx):
    head("5b. pg_notify signali")
    if not ctx:
        print("  SKIP")
        return
    import os

    import psycopg2
    import psycopg2.extensions

    # TINGLOVCHI HOZIR YO'Q va bu ataylab (polling ishlaydi). Lekin
    # signalning YOZILISHI xabar yozilayotgan joyda bo'lishi kerak:
    # keyin qo'shilsa bir-ikki joyda unutilardi va WebSocket "ba'zan
    # ishlaydi" bo'lib qolardi. Sinov aynan shuni qo'riqlaydi.
    conn = psycopg2.connect(os.environ["XT_DB_DSN"])
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute(f"LISTEN {C.NOTIFY_KANAL};")

        m = C.yoz(ctx["cid"], ctx["egasi"], f"{MARK} signal sinovi")
        conn.poll()
        kelgan = [(n.channel, n.payload) for n in conn.notifies]
        check((C.NOTIFY_KANAL, str(ctx["cid"])) in kelgan,
              "xabar yozilganda signal ketdi", str(kelgan))

        conn.notifies.clear()
        C.tahrir(m["id"], ctx["egasi"], f"{MARK} tahrirlandi")
        conn.poll()
        check(any(n.payload == str(ctx["cid"]) for n in conn.notifies),
              "TAHRIR ham signal beradi (lenta o'zgardi)")

        conn.notifies.clear()
        C.ochir(m["id"], ctx["egasi"])
        conn.poll()
        check(any(n.payload == str(ctx["cid"]) for n in conn.notifies),
              "O'CHIRISH ham signal beradi")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5c. Eslatish (@ism)
# ---------------------------------------------------------------------------
def test_eslatish(ctx):
    head("5c. @ism eslatish")
    if not ctx:
        print("  SKIP")
        return
    cid, egasi, boshliq, begona = (ctx["cid"], ctx["egasi"],
                                   ctx["boshliq"], ctx["begona"])

    def xabarlar(uid):
        return db.query_one(
            "SELECT count(*) AS n FROM erp.notification "
            "WHERE app_user_id = %(u)s AND kind = 'chat_mention'",
            {"u": uid})["n"]

    # `begona` hozir a'zo (4-bo'limda qayta qo'shilgan); ishonch uchun.
    try:
        C.azo_qosh(cid, boshliq, begona)
    except O.ErpError:
        pass

    m = C.yoz(cid, egasi, f"{MARK} @kimdir qarab yuboring")
    oldin = xabarlar(begona)
    r = C.eslat(cid, egasi, m["id"], [begona])
    eq("a'zoni eslatish -> bildirishnoma", r["eslatildi"], 1)
    eq("bildirishnoma yozildi", xabarlar(begona), oldin + 1)

    # TAKROR YO'Q: "eslatishni unutdim, tahrirlab qo'shdim" ishlashi
    # kerak, lekin har tahrirda hammaga takror ketmasligi ham.
    r = C.eslat(cid, egasi, m["id"], [begona])
    eq("ikkinchi marta -> takror YO'Q", r["eslatildi"], 0)
    eq("bildirishnoma soni o'zgarmadi", xabarlar(begona), oldin + 1)

    # A'ZO BO'LMAGAN id JIMGINA tashlanadi, 400 EMAS: foydalanuvchi
    # tuzata olmaydigan holat (u ro'yxatdan tanlagan, oradan a'zo
    # chiqarilgan bo'lishi mumkin). Xato qaytarsak uning XABARI
    # sababsiz yuborilmay qolardi.
    yoq = _user("zztest_chat_azo_emas", "broker")
    r = C.eslat(cid, egasi, m["id"], [yoq])
    eq("a'zo bo'lmagan id -> jimgina tashlandi", r["eslatildi"], 0)
    eq("tashlangani SANALADI", r["tashlandi"], 1)
    eq("unga bildirishnoma yozilmadi", xabarlar(yoq), 0)

    # O'ZINI eslatish sanalmaydi.
    r = C.eslat(cid, egasi, m["id"], [egasi])
    eq("o'zini eslatish -> 0", r["eslatildi"], 0)

    # TAHRIRDA yangi odam qo'shilsa — unga ketadi.
    oldin_b = xabarlar(boshliq)
    C.tahrir(m["id"], egasi, f"{MARK} @boshliq ham qarasin")
    r = C.eslat(cid, egasi, m["id"], [begona, boshliq])
    eq("tahrirda YANGI id ga ketdi", r["eslatildi"], 1)
    eq("boshliqqa yozildi", xabarlar(boshliq), oldin_b + 1)
    eq("eskisiga TAKROR ketmadi", xabarlar(begona), oldin + 1)

    # Jadvalda kimga yuborilgani QOLADI (26-patch).
    saqlangan = db.query_one(
        "SELECT eslatilgan FROM erp.chat_message WHERE id = %(i)s",
        {"i": m["id"]})["eslatilgan"]
    check(set(saqlangan) == {begona, boshliq},
          "kimga yuborilgani xabarda saqlandi", str(saqlangan))

    db.execute_returning(
        "UPDATE erp.app_user SET active = FALSE WHERE id = %(i)s "
        "RETURNING id", {"i": yoq})


# ---------------------------------------------------------------------------
# 6. Tozalash va chegara
# ---------------------------------------------------------------------------
PUBLIC_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def test_tozalash(before):
    head("6. Chegara va tozalash")
    db.init_pool()
    after = db.query_one(PUBLIC_SQL)
    eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
    eq("public.tender yangilanmadi", after["t_max"], before["t_max"])

    # Jurnal `audit_purge` bilan tozalanadi — bu QOIDANING O'ZI ham
    # tekshiruv: usiz o'chirilmasligi kerak.
    n = db.query_one(
        "SELECT count(*) AS n FROM erp.chat_message WHERE text LIKE %(p)s",
        {"p": MARK + "%"})["n"]
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('erp.audit_purge', 'on', false)")
            cur.execute(
                "DELETE FROM erp.chat_message_history WHERE message_id IN ("
                "  SELECT id FROM erp.chat_message WHERE text LIKE %(p)s)",
                {"p": MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message WHERE text LIKE %(p)s",
                        {"p": MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message WHERE author_id IS NULL "
                        "AND text LIKE %(p)s", {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.notification WHERE app_user_id = ANY("
                        "  SELECT id FROM erp.app_user WHERE username LIKE "
                        "  'zztest_chat%')")
            cur.execute("DELETE FROM erp.chat_member WHERE app_user_id = ANY("
                        "  SELECT id FROM erp.app_user WHERE username LIKE "
                        "  'zztest_chat%')")
            cur.execute("UPDATE erp.app_user SET active = FALSE "
                        "WHERE username LIKE 'zztest_chat%'")
        conn.commit()
    eq("sinov xabarlari tozalandi",
       db.query_one("SELECT count(*) AS n FROM erp.chat_message "
                    "WHERE text LIKE %(p)s", {"p": MARK + "%"})["n"], 0)
    check(n >= 0, f"({n} ta xabar yaratilgan edi)")
    check(FIX.cleanup() >= 0, "fixture tozalandi")


if __name__ == "__main__":
    test_huquq()
    try:
        db.init_pool()
    except Exception as e:                          # noqa: BLE001
        print(f"\n  DIQQAT: bazasiz sinov: {e}")
    else:
        before = db.query_one(PUBLIC_SQL)
        ctx = None
        try:
            test_sxema()
            ctx = test_oqim()
            test_azolar(ctx)
            test_arxiv_va_oqilganlik(ctx)
            test_signal(ctx)
            test_eslatish(ctx)
        finally:
            test_tozalash(before)

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
