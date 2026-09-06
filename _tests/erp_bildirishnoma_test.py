"""
BILDIRISHNOMA QUVURI sinovi (27-patch) — `api/erp/hodisa.py`,
`api/erp/xabar.py`, `api/erp/navbat.py` va chat bilan bog'lanish.

Ishga tushirish (loyiha ildizidan):
    .venv/Scripts/python.exe _tests/erp_bildirishnoma_test.py

NIMA UCHUN: bildirishnoma — JIM buziladigan qism. U ishlamay qolsa
hech kim xato ko'rmaydi; odamlar shunchaki xabar olmaydi va buni
haftalar o'tib "menga aytishmagan edi" degan gapdan bilib olinadi.
Shuning uchun sinov OLTITA buzilish sinfini qo'riqlaydi:

  1) NOTO'G'RI ODAM. Xabar aloqasi yo'q hodimga borsa — sizib chiqish;
     o'z amali haqida o'ziga borsa — shovqin va ishonchsizlik.
  2) TAKROR. Qayta urinish yoki ikki marta bosilgan tugma ikkinchi
     bildirishnoma yozmasligi kerak (§17).
  3) YO'QOLISH. Tashqi kanal (Telegram) yiqilsa CHAT XABARI va
     bildirishnomaning O'ZI qolishi shart (§22, §23).
  4) NAVBAT TO'XTAB QOLISHI. Xato bo'lgan qator qayta urinishga
     qaytishi, tuzalmaydigan xato esa TERMINAL bo'lishi kerak (§19).
  5) NISHONNING YO'QOLISHI. Chat bildirishnomasi CHATga olib borishi
     kerak, "umumiy panelga" emas (§15).
  6) LENTANING TESKARI SAHIFALANISHI. 50 dan oshgan chatda oxirgi
     xabarlar ko'rinmay qolgan edi — sinov shuni qo'riqlaydi.

Belgisi: 'ZZTEST-BILD'. Oxirida tozalanadi.
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
from api.erp import hodisa as H  # noqa: E402
from api.erp import navbat as N  # noqa: E402
from api.erp import opportunity as O  # noqa: E402
from api.erp import xabar as X  # noqa: E402

MARK = "ZZTEST-BILD"
PREFIX = "zztest_bild"

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
def _user(username, rol, broker_id=None):
    """Sinov hisobi (`erp.app_user` ga to'g'ridan-to'g'ri)."""
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
    return r["id"]


def _broker(nom):
    r = db.query_one("SELECT id FROM erp.broker WHERE full_name = %(n)s",
                     {"n": nom})
    if r:
        return r["id"]
    return db.execute_returning(
        "INSERT INTO erp.broker (full_name) VALUES (%(n)s) RETURNING id",
        {"n": nom})["id"]


def _oqilmagan(uid, kind=None):
    sql = ("SELECT count(*) FROM erp.notification "
           "WHERE app_user_id = %(u)s AND read_at IS NULL")
    if kind:
        sql += " AND kind = %(k)s"
    return db.scalar(sql, {"u": uid, "k": kind}) or 0


# ---------------------------------------------------------------------------
# 1. Reyestr — sof mantiq, bazasiz
# ---------------------------------------------------------------------------
def test_reyestr():
    head("1. Hodisa reyestri (bazasiz)")

    # REYESTR VA EKRAN AJRALIB KETMASIN. `hodisa.HODISALAR` da bor
    # tur `xabar.TURLAR` da ham bo'lishi shart, aks holda ekranda
    # yorliqsiz, nishonsiz qator chiqardi.
    yoq = sorted(set(H.HODISALAR) - set(X.TURLAR))
    eq("har hodisa turining ekran yorlig'i bor", yoq, [])

    # TASHQI KANAL FAQAT KOMPANIYAGA TEGISHLI hodisalarda. Chat
    # yozishmasini Telegram guruhiga ko'chirish yozishmaning o'zini
    # ma'nosiz qilardi.
    for k in ("chat_yangi", "chat_mention", "chat_qoshildi",
              "chat_ochirildi"):
        eq(f"{k}: tashqi kanal yo'q", H.HODISALAR[k][1], [])
    check(H.TELEGRAM in H.HODISALAR["muddat"][1],
          "muddat: kompaniya kanaliga ham ketadi")

    # ORQAGA CHEKINISH RO'YXATI urinishlar soni bilan MOS bo'lsin,
    # aks holda oxirgi urinishda `IndexError` chiqardi.
    eq("kechikish ro'yxati urinishlar soniga teng",
       len(N.KECHIKISH_DAQ), N.MAX_URINISH)
    check(list(N.KECHIKISH_DAQ) == sorted(N.KECHIKISH_DAQ),
          "kechikish o'sib boradi (orqaga chekinish)")

    # TERMINAL XATO qayta urinilmaydi (§19).
    check(N._terminalmi("Tender-AI 404: Not Found"),
          "404 — terminal (qayta urinish tuzatmaydi)")
    check(N._terminalmi("chat not found"), "'chat not found' — terminal")
    check(not N._terminalmi("Tender-AI javob bermadi: timed out"),
          "tarmoq uzilishi — terminal EMAS, qayta uriniladi")
    check(not N._terminalmi("Tender-AI 503: Service Unavailable"),
          "503 — vaqtinchalik, qayta uriniladi")

    # ILOVA KANALI SOZLANMAYDI: u yagona ishonchli joy.
    check("inapp" not in H.SOZLANADIGAN,
          "ilova kanali sozlanadiganlar ro'yxatida yo'q")


# ---------------------------------------------------------------------------
# 2. Sxema
# ---------------------------------------------------------------------------
def test_sxema():
    head("2. 27-patch sxemasi")
    check(X.schema27_ready(), "erp.notification.dedup_key ustuni bor")
    check(N.schema_ready(), "erp.notification_delivery jadvali bor")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.views "
        "WHERE table_schema = 'erp' AND table_name = 'v_notification_health'")),
        "erp.v_notification_health view'i bor")
    check(bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.columns "
        "WHERE table_schema='erp' AND table_name='chat_member' "
        "AND column_name='muted_at'")), "chat_member.muted_at ustuni bor")

    # DEDUP INDEKSI NOYOB bo'lishi SHART — usiz takror to'silmaydi.
    check(bool(db.query_one(
        "SELECT 1 AS x FROM pg_indexes WHERE schemaname='erp' "
        "AND indexname='notification_dedup_uk'")),
        "dedup noyob indeksi bor")


# ---------------------------------------------------------------------------
# 3. Qabul qiluvchi — munosabatdan
# ---------------------------------------------------------------------------
def test_qabul():
    head("3. Qabul qiluvchini aniqlash")
    b_masul = _broker(f"{MARK} Mas'ul")
    b_begona = _broker(f"{MARK} Begona")
    u_masul = _user(f"{PREFIX}_masul", "broker", b_masul)
    u_begona = _user(f"{PREFIX}_begona", "broker", b_begona)
    u_rahbar = _user(f"{PREFIX}_rahbar", "rahbar")

    eq("hodim -> uning faol hisobi", H.broker_hisobi(b_masul), u_masul)
    eq("hodimsiz -> None", H.broker_hisobi(None), None)

    # HISOBSIZ HODIM — xato emas, oddiy holat (omborchi, hujjatchi).
    b_hisobsiz = _broker(f"{MARK} Hisobsiz")
    eq("hisobsiz hodim -> None", H.broker_hisobi(b_hisobsiz), None)

    boshliqlar = H.boshliqlar()
    check(u_rahbar in boshliqlar or any(
        db.scalar("SELECT 1 FROM erp.app_user WHERE id=%(i)s AND role='menejer'",
                  {"i": i}) for i in boshliqlar),
        "boshliqlar: menejer, bo'lmasa rahbar")

    # ADMIN ISH XABARINI OLMAYDI (`erp_rollar.md` §3.6).
    u_admin = _user(f"{PREFIX}_admin", "admin")
    check(u_admin not in H.boshliqlar(), "admin boshliqlar ro'yxatida yo'q")
    return {"u_masul": u_masul, "u_begona": u_begona, "u_rahbar": u_rahbar,
            "b_masul": b_masul, "b_begona": b_begona, "u_admin": u_admin}


# ---------------------------------------------------------------------------
# 4. Chiqarish: o'z amali, takror, nishon
# ---------------------------------------------------------------------------
def test_chiqarish(ctx):
    head("4. Hodisa chiqarish")
    u1, u2 = ctx["u_masul"], ctx["u_begona"]

    # O'Z AMALI HAQIDA XABAR KELMAYDI (§13).
    r = H.chiqar("status", f"{MARK} o'z amalim", qabul=[u1, u2],
                 chiqaruvchi=u1)
    eq("chiqaruvchi ro'yxatdan olindi", r["kimga"], [u2])
    eq("faqat bittasiga yozildi", r["yozildi"], 1)

    # TAKROR (§17): bir xil dedup kaliti ikkinchi qator YOZMAYDI.
    kalit = f"{MARK}-takror"
    a = H.chiqar("vazifa", f"{MARK} birinchi", qabul=[u1], dedup=kalit,
                 kotar=False)
    b = H.chiqar("vazifa", f"{MARK} ikkinchi", qabul=[u1], dedup=kalit,
                 kotar=False)
    eq("birinchi yozildi", a["yozildi"], 1)
    eq("takror YOZILMADI", b["yozildi"], 0)
    n = db.scalar("SELECT count(*) FROM erp.notification "
                  "WHERE dedup_key = %(d)s", {"d": f"{kalit}:{u1}"})
    eq("bazada bitta qator", n, 1)
    matn = db.scalar("SELECT matn FROM erp.notification "
                     "WHERE dedup_key = %(d)s", {"d": f"{kalit}:{u1}"})
    check(matn.endswith("birinchi"),
          "kotar=False: mavjud xabar matni O'ZGARMADI")

    # KO'TARISH: yig'ma xabar (chat) — matn yangilanadi, o'qilgan
    # belgisi OLINADI, lekin YANGI qator yozilmaydi.
    kalit2 = f"{MARK}-kotar"
    H.chiqar("chat_yangi", f"{MARK} eski", qabul=[u1], dedup=kalit2)
    db.execute_returning("UPDATE erp.notification SET read_at = now() "
                         "WHERE dedup_key = %(d)s RETURNING id",
                         {"d": f"{kalit2}:{u1}"})
    H.chiqar("chat_yangi", f"{MARK} yangi", qabul=[u1], dedup=kalit2)
    row = db.query_one("SELECT matn, read_at FROM erp.notification "
                       "WHERE dedup_key = %(d)s", {"d": f"{kalit2}:{u1}"})
    check(row["matn"].endswith("yangi"), "ko'tarishda matn yangilandi")
    eq("ko'tarishda o'qilgan belgisi olindi", row["read_at"], None)
    eq("ko'tarishda ikkinchi qator yozilmadi",
       db.scalar("SELECT count(*) FROM erp.notification "
                 "WHERE dedup_key = %(d)s", {"d": f"{kalit2}:{u1}"}), 1)

    # HISOBSIZ HODIM: nol yozilgani XATO EMAS.
    r = H.chiqar("topshiriq", f"{MARK} hisobsiz",
                 broker_id=_broker(f"{MARK} Hisobsiz"))
    eq("hisobsiz hodimga nol yozildi (xato emas)", r["yozildi"], 0)


# ---------------------------------------------------------------------------
# 5. Chat -> bildirishnoma -> nishon
# ---------------------------------------------------------------------------
def test_chat_bildirishnoma(ctx):
    head("5. Chat xabari -> bildirishnoma")
    opp = FIX.ensure_opportunity()
    if not opp:
        print("  SKIP: public.tender bo'sh (ETL yurmagan)")
        return None
    oid = opp["id"]
    u1, u2 = ctx["u_masul"], ctx["u_begona"]

    chat_id = C.karta_chati_yarat(oid, f"{MARK} karta", None, u1)
    if not chat_id:
        chat_id = C.karta_chati(oid)
    check(bool(chat_id), "karta chati bor")
    for u in (u1, u2):
        if not db.query_one(C.AZOMI_SQL, {"chat": chat_id, "uid": u}):
            C.azo_qosh(chat_id, u1, u)

    # OLDINGI BO'LIM QOLDIG'INI tozalaymiz: 4-bo'lim `chat_yangi`
    # turidagi qator yozgan va u sanoqqa qo'shilib, "muallifga xabar
    # keldi" degan YOLG'ON xato berardi.
    X.oqildi(u1)
    X.oqildi(u2)
    oldin = _oqilmagan(u2, "chat_yangi")
    C.yoz(chat_id, u1, f"{MARK} birinchi xabar")
    keyin = _oqilmagan(u2, "chat_yangi")
    eq("a'zoga chat bildirishnomasi keldi", keyin, oldin + 1)
    eq("MUALLIFGA o'z xabari haqida bildirishnoma kelmadi",
       _oqilmagan(u1, "chat_yangi"), 0)

    # YIG'MA: yana ikkita xabar YANGI qator yozmaydi.
    C.yoz(chat_id, u1, f"{MARK} ikkinchi")
    C.yoz(chat_id, u1, f"{MARK} uchinchi")
    eq("uchta xabar — BITTA bildirishnoma", _oqilmagan(u2, "chat_yangi"), 1)
    row = db.query_one("SELECT matn, chat_id FROM erp.notification "
                       "WHERE app_user_id = %(u)s AND kind = 'chat_yangi' "
                       "ORDER BY id DESC LIMIT 1", {"u": u2})
    check("uchinchi" in (row["matn"] or ""), "yig'ma xabar OXIRGISINI ko'rsatadi")
    eq("nishon — CHAT (karta emas)", row["chat_id"], chat_id)

    # NISHON interfeysga to'g'ri shaklda beriladi (§15).
    r = X.royxat(u2, limit=50)
    n = next((i for i in r["items"] if i["kind"] == "chat_yangi"), None)
    check(n is not None, "bildirishnoma ro'yxatda bor")
    eq("nishon turi — chat", n["nishon"]["turi"], "chat")
    eq("nishon id — chat id", n["nishon"]["id"], chat_id)
    check(n["nishon"]["opportunity_id"] == oid,
          "nishonda karta ham bor (kontekst uchun)")

    # JIMLASH: bildirishnoma kelmaydi, lekin O'QILMAGAN hisoblagichi
    # ishlayveradi — jimlash "ko'rmayman" degani emas.
    X.oqildi(u2)
    C.jimla(chat_id, u2, True)
    C.yoz(chat_id, u1, f"{MARK} jimlangandan keyin")
    eq("jimlangan chatdan bildirishnoma kelmadi",
       _oqilmagan(u2, "chat_yangi"), 0)
    chatlar = C.chatlarim(u2)
    bu = next((c for c in chatlar if c["id"] == chat_id), None)
    check(bu and bu["oqilmagan"] > 0,
          "jimlanganda ham O'QILMAGAN hisoblagichi ishlayapti")
    C.jimla(chat_id, u2, False)

    # JIMLASH A'ZOLIK BERMAYDI: begona odam shu yo'l bilan chatga
    # kirib olmasin.
    u_begona2 = _user(f"{PREFIX}_tashqi", "broker")
    kod, _ = xato(C.jimla, chat_id, u_begona2, True)
    eq("a'zo bo'lmagan jimlay olmaydi", kod, 403)
    eq("jimlash a'zolik yaratmadi",
       db.scalar("SELECT count(*) FROM erp.chat_member "
                 "WHERE chat_id = %(c)s AND app_user_id = %(u)s",
                 {"c": chat_id, "u": u_begona2}), 0)
    return {"chat_id": chat_id, "oid": oid}


# ---------------------------------------------------------------------------
# 6. Lenta sahifalash — TUZATILGAN NUQSON
# ---------------------------------------------------------------------------
def test_sahifalash(ctx, chat_ctx):
    head("6. Lenta sahifalash (oxirgi sahifa)")
    if not chat_ctx:
        print("  SKIP: chat konteksti yo'q")
        return
    chat_id, u1 = chat_ctx["chat_id"], ctx["u_masul"]

    # NUQSON EDI: `ORDER BY id LIMIT 50` eng ESKI 50 tani qaytarardi.
    # 50 dan oshgan chatda odam birinchi kunning yozishmasini ko'rib
    # turardi va yangi xabarlarni UMUMAN ko'rmasdi.
    for i in range(12):
        C.yoz(chat_id, u1, f"{MARK} sahifa-{i:02d}")

    r = C.lenta(chat_id, u1, hammasi=True, limit=5)
    eq("beshta qaytdi", len(r["messages"]), 5)
    check(r["messages"][-1]["text"].endswith("sahifa-11"),
          "OXIRGI xabar lentada (eng eskisi emas)")
    check(r["messages"][0]["id"] < r["messages"][-1]["id"],
          "tartib o'sish bo'yicha (ekran uchun to'g'ri)")
    check(r["yana"], "eskiroqlari bor deb belgilandi")

    # ESKI TARIX: `before_id` bilan orqaga.
    eski = C.lenta(chat_id, u1, hammasi=True, limit=5,
                   before_id=r["eng_eski_id"])
    check(all(m["id"] < r["eng_eski_id"] for m in eski["messages"]),
          "before_id: faqat eskiroqlari qaytdi")
    check(eski["messages"][-1]["id"] < r["messages"][0]["id"],
          "sahifalar bir-birini takrorlamaydi")

    # SO'ROV (polling): `after_id` bilan yangilari.
    oxirgi = r["messages"][-1]["id"]
    bosh = C.lenta(chat_id, u1, hammasi=True, after_id=oxirgi)
    eq("yangi xabar yo'q — javob bo'sh", len(bosh["messages"]), 0)
    C.yoz(chat_id, u1, f"{MARK} polling")
    yangi = C.lenta(chat_id, u1, hammasi=True, after_id=oxirgi)
    eq("polling yangi xabarni topdi", len(yangi["messages"]), 1)

    # KONTEKST SARLAVHASI (§6).
    k = r["chat"]["kontekst"]
    check(k is not None, "karta chatida kontekst bor")
    eq("kontekstda karta id si", k["opportunity_id"], chat_ctx["oid"])
    check(k["status_label"], "kontekstda holat NOMI (kod emas)")
    check("status" in k and "deadline_at" in k and "masul" in k,
          "kontekstda holat, muddat va mas'ul bor")


# ---------------------------------------------------------------------------
# 7. Navbat: yetkazish, qayta urinish, terminal
# ---------------------------------------------------------------------------
def test_navbat(ctx):
    head("7. Yetkazish navbati")
    u1 = ctx["u_masul"]

    # TASHQI KANAL navbatga qo'yiladi.
    r = H.chiqar("muddat", f"{MARK} tashqi kanal sinovi", qabul=[u1],
                 dedup=f"{MARK}-navbat", kotar=False)
    eq("bildirishnoma yozildi", r["yozildi"], 1)
    check(H.TELEGRAM in r["tashqi"], "tashqi kanal navbatga qo'yildi")

    nid = db.scalar("SELECT id FROM erp.notification WHERE dedup_key = %(d)s",
                    {"d": f"{MARK}-navbat:{u1}"})
    qatorlar = db.query("SELECT kanal, holat, urinish FROM "
                        "erp.notification_delivery WHERE notification_id = %(n)s "
                        "ORDER BY kanal", {"n": nid})
    kanallar = {q["kanal"]: q for q in qatorlar}
    eq("ilova kanali darhol yetkazilgan", kanallar["inapp"]["holat"], "sent")
    eq("telegram navbatda", kanallar["telegram"]["holat"], "pending")
    eq("email navbatda", kanallar["email"]["holat"], "pending")

    # TASHQI KANAL BIR MARTA: ikki qabul qiluvchi = ikki bildirishnoma,
    # lekin KOMPANIYA kanaliga bitta xabar (moduldagi izoh).
    r2 = H.chiqar("muddat", f"{MARK} ikki odam", qabul=[u1, ctx["u_begona"]],
                  dedup=f"{MARK}-ikki", kotar=False)
    eq("ikkalasiga ham yozildi", r2["yozildi"], 2)
    n_tashqi = db.scalar(
        "SELECT count(*) FROM erp.notification_delivery d "
        "JOIN erp.notification n ON n.id = d.notification_id "
        "WHERE n.dedup_key LIKE %(p)s AND d.kanal <> 'inapp'",
        {"p": f"{MARK}-ikki:%"})
    eq("tashqi kanal BIR marta navbatga qo'yildi (guruhga takror yo'q)",
       n_tashqi, 2)   # bitta bildirishnoma x ikki kanal

    # QAYTA URINISH: tarmoq xatosi -> `failed`, keyingi urinish vaqti
    # KELAJAKDA (§19).
    import api.tenderai as TA
    asl = TA.notify
    TA.notify = lambda *a, **k: (_ for _ in ()).throw(
        TA.TenderAiUnavailable("Tender-AI javob bermadi: timed out"))
    try:
        res = N.yur(limit=10)
    finally:
        TA.notify = asl
    check(res["failed"] > 0, f"vaqtinchalik xato -> failed ({res['failed']} ta)")
    eq("hech biri yuborilmadi", res["sent"], 0)
    q = db.query_one("SELECT holat, urinish, last_error, next_try_at > now() "
                     "AS keyin FROM erp.notification_delivery "
                     "WHERE notification_id = %(n)s AND kanal = 'telegram'",
                     {"n": nid})
    eq("holat failed", q["holat"], "failed")
    eq("urinish sanaldi", q["urinish"], 1)
    check(q["keyin"], "keyingi urinish KELAJAKDA (orqaga chekinish)")
    check("timed out" in (q["last_error"] or ""), "xato sababi saqlandi")

    # BILDIRISHNOMANING O'ZI YO'QOLMADI (§22) — eng muhim tekshiruv.
    check(bool(db.query_one("SELECT 1 AS x FROM erp.notification "
                            "WHERE id = %(n)s", {"n": nid})),
          "tashqi kanal yiqilsa ham BILDIRISHNOMA joyida")
    eq("va u hali ham o'qilmagan (odam ilovada ko'radi)",
       db.scalar("SELECT read_at FROM erp.notification WHERE id = %(n)s",
                 {"n": nid}), None)

    # TERMINAL: tuzalmaydigan xato darhol tugatiladi.
    db.execute_returning("UPDATE erp.notification_delivery "
                         "SET next_try_at = now() - interval '1 minute' "
                         "WHERE notification_id = %(n)s RETURNING id",
                         {"n": nid})
    TA.notify = lambda *a, **k: (_ for _ in ()).throw(
        TA.TenderAiUnavailable("Tender-AI 404: Not Found"))
    try:
        res = N.yur(limit=10)
    finally:
        TA.notify = asl
    check(res["terminal"] > 0, f"tuzalmaydigan xato -> terminal")
    eq("terminal holati yozildi",
       db.scalar("SELECT holat FROM erp.notification_delivery "
                 "WHERE notification_id = %(n)s AND kanal = 'telegram'",
                 {"n": nid}), "terminal")
    # TERMINAL QATOR QAYTA OLINMAYDI — aks holda navbat cheksiz aylanardi.
    olindi = db.scalar(
        "SELECT count(*) FROM erp.notification_delivery "
        "WHERE holat IN ('pending','failed') AND notification_id = %(n)s "
        "AND kanal = 'telegram'", {"n": nid})
    eq("terminal qator navbatdan chiqdi", olindi, 0)

    # MUVAFFAQIYAT: `sent` + `yuborildi_at`.
    db.execute_returning("UPDATE erp.notification_delivery "
                         "SET holat = 'pending', next_try_at = now() "
                         "WHERE notification_id = %(n)s AND kanal = 'email' "
                         "RETURNING id", {"n": nid})
    TA.notify = lambda *a, **k: {"ok": True}
    try:
        res = N.yur(limit=10)
    finally:
        TA.notify = asl
    check(res["sent"] > 0, "yuborildi")
    q = db.query_one("SELECT holat, sent_at FROM erp.notification_delivery "
                     "WHERE notification_id = %(n)s AND kanal = 'email'",
                     {"n": nid})
    eq("email holati sent", q["holat"], "sent")
    check(q["sent_at"] is not None, "yuborilgan vaqt yozildi")
    check(db.scalar("SELECT yuborildi_at FROM erp.notification "
                    "WHERE id = %(n)s", {"n": nid}) is not None,
          "notification.yuborildi_at to'ldi (22-patchdan beri bo'sh edi)")

    # `delivered` HOLATI YO'Q (§18): dalil bo'lmagan narsa yozilmaydi.
    holatlar = {r["holat"] for r in db.query(
        "SELECT DISTINCT holat FROM erp.notification_delivery")}
    eq("'delivered' holati umuman ishlatilmaydi",
       holatlar & {"delivered", "read"}, set())

    # KUZATUV (§20).
    s = N.sogliq()
    check(s["ready"], "sog'liq ko'rsatkichi ishlayapti")
    kan = {k["kanal"] for k in s["kanallar"]}
    check({"inapp", "telegram", "email"} <= kan,
          "uch kanal ham kuzatuvda ko'rinadi")
    tg = next(k for k in s["kanallar"] if k["kanal"] == "telegram")
    check(tg["terminal"] > 0, "kuzatuvda terminal soni ko'rinadi")
    check("eng_eski_pending" in tg,
          "eng eski kutayotgan qator ko'rsatiladi (navbat to'xtaganini "
          "faqat shu ajratadi)")


# ---------------------------------------------------------------------------
# 8. O'qish: sahifalash, hammasini belgilash, begonaniki
# ---------------------------------------------------------------------------
def test_oqish(ctx):
    head("8. O'qish va o'qilgan belgisi")
    u1, u2 = ctx["u_masul"], ctx["u_begona"]

    for i in range(6):
        H.chiqar("status", f"{MARK} oqish-{i}", qabul=[u1],
                 dedup=f"{MARK}-oqish-{i}", kotar=False)

    r = X.royxat(u1, limit=3)
    eq("uchta qaytdi", len(r["items"]), 3)
    check(r["yana"], "yana bor deb belgilandi")
    eskisi = X.royxat(u1, limit=3, before_id=r["items"][-1]["id"])
    check(all(i["id"] < r["items"][-1]["id"] for i in eskisi["items"]),
          "before_id: faqat oldingilari")

    # BITTASINI belgilash.
    bir = r["items"][0]["id"]
    eq("bittasi belgilandi", X.oqildi(u1, [bir]), 1)
    eq("ikkinchi marta belgilanmaydi", X.oqildi(u1, [bir]), 0)

    # BEGONANIKI — hech narsa o'zgarmaydi (§28: cross-user izolyatsiya).
    begona = db.scalar("SELECT id FROM erp.notification "
                       "WHERE app_user_id = %(u)s AND read_at IS NULL "
                       "ORDER BY id DESC LIMIT 1", {"u": u2})
    if begona:
        eq("begona bildirishnomani o'qilgan qilib bo'lmaydi",
           X.oqildi(u1, [begona]), 0)
        eq("u hali ham o'qilmagan",
           db.scalar("SELECT read_at FROM erp.notification WHERE id=%(i)s",
                     {"i": begona}), None)
        # VA UNI KO'RIB HAM BO'LMAYDI.
        r2 = X.royxat(u1, limit=200)
        check(begona not in [i["id"] for i in r2["items"]],
              "begona bildirishnoma ro'yxatda YO'Q")

    # HAMMASINI belgilash.
    qolgan = _oqilmagan(u1)
    eq("hammasi belgilandi", X.oqildi(u1), qolgan)
    eq("o'qilmagan qolmadi", _oqilmagan(u1), 0)


# ---------------------------------------------------------------------------
# 9. Ish oqimi hodisalari
# ---------------------------------------------------------------------------
def test_oqim(ctx, chat_ctx):
    head("9. Ish oqimi hodisalari")
    if not chat_ctx:
        print("  SKIP: karta yo'q")
        return
    oid = chat_ctx["oid"]
    u1, u2 = ctx["u_masul"], ctx["u_begona"]
    X.oqildi(u1)
    X.oqildi(u2)

    # KARTA O'TKAZILDI: yangisiga "sizga", eskisiga "sizdan olindi".
    db.execute_returning("UPDATE erp.opportunity SET broker_id = %(b)s "
                         "WHERE id = %(i)s RETURNING id",
                         {"b": ctx["b_masul"], "i": oid})
    r = H.karta_otkazildi(ctx["b_begona"], ctx["b_masul"], oid, f"{MARK} karta")
    eq("ikki odamga xabar ketdi", r["yozildi"], 2)
    eq("yangi mas'ulga 'sizga o'tkazildi'", _oqilmagan(u2, "otkazildi"), 1)
    eq("eski mas'ulga 'sizdan olindi'",
       _oqilmagan(u1, "biriktirish_olib_tashlandi"), 1)

    # HOLAT O'ZGARDI: mas'ul va chat a'zolari, AMALNI BAJARGANDAN
    # TASHQARI.
    X.oqildi(u1)
    X.oqildi(u2)
    H.karta_holati(oid, f"{MARK} karta", "Yangi", "Tayyorlanmoqda",
                   "sinov", chiqaruvchi=u1)
    eq("amalni bajargan xabar OLMADI", _oqilmagan(u1, "status"), 0)
    check(_oqilmagan(u2, "status") >= 1, "aloqador hodim xabar oldi")

    # VAZIFA BIRIKTIRILDI + takror yo'q.
    from api.erp import tasks as T
    X.oqildi(u1)
    T.add(oid, {"title": f"{MARK} vazifa", "assignee_broker_id": ctx["b_masul"],
                "created_by": MARK})
    eq("vazifa biriktirilgani haqida xabar", _oqilmagan(u1, "vazifa"), 1)
    tid = db.scalar("SELECT id FROM erp.opportunity_task "
                    "WHERE title = %(t)s ORDER BY id DESC LIMIT 1",
                    {"t": f"{MARK} vazifa"})
    T.update(tid, {"title": f"{MARK} vazifa", "note": "izoh qo'shildi",
                   "assignee_broker_id": ctx["b_masul"]})
    eq("izoh o'zgarishi TAKROR xabar bermadi", _oqilmagan(u1, "vazifa"), 1)

    # QAROR KERAK -> boshliqqa.
    r = H.qaror_kerak(f"{MARK} qaror kerak", opp_id=oid)
    check(r["yozildi"] >= 1, "qaror so'rovi boshliqqa ketdi")

    # TIZIM NOSOZLIGI -> boshliqqa, takrorsiz.
    a = H.tizim_nosozligi(f"{MARK} nosozlik", dedup=f"{MARK}-nosoz")
    b = H.tizim_nosozligi(f"{MARK} nosozlik", dedup=f"{MARK}-nosoz")
    check(a["yozildi"] >= 1, "tizim nosozligi haqida xabar ketdi")
    eq("takrori yozilmadi", b["yozildi"], 0)


# ---------------------------------------------------------------------------
# 10. Sozlama
# ---------------------------------------------------------------------------
def test_sozlama(ctx):
    head("10. Kanal sozlamasi")
    u1 = ctx["u_masul"]
    s = H.sozlamalarim(u1)
    check("inapp" not in s["sozlanadigan"], "ilova kanali sozlanmaydi")
    kod, matn = xato(H.sozlama_qoy, u1, "*", "inapp", False)
    eq("ilova kanalini o'chirishga urinish rad etildi", kod, 400)

    H.sozlama_qoy(u1, "muddat", H.TELEGRAM, False)
    eq("o'chirilgan kanal tanlanmaydi",
       H.kanallar("muddat", u1, birinchi=True), [H.EMAIL])
    H.sozlama_qoy(u1, "muddat", H.TELEGRAM, True)
    check(H.TELEGRAM in H.kanallar("muddat", u1, birinchi=True),
          "qayta yoqilgach kanal qaytdi")

    # '*' UMUMIY qoida, hodisa nomi esa ANIQROQ va ustun turadi.
    H.sozlama_qoy(u1, "*", H.EMAIL, False)
    eq("umumiy qoida hamma hodisaga tegadi",
       H.kanallar("hujjat_muddat", u1, birinchi=True), [H.TELEGRAM])
    H.sozlama_qoy(u1, "hujjat_muddat", H.EMAIL, True)
    check(H.EMAIL in H.kanallar("hujjat_muddat", u1, birinchi=True),
          "aniqroq qoida umumiydan ustun")

    kod, _ = xato(H.sozlama_qoy, u1, "yoq_bunday_hodisa", H.EMAIL, True)
    eq("noma'lum hodisa turi rad etildi", kod, 400)


# ---------------------------------------------------------------------------
# 11. Tozalash
# ---------------------------------------------------------------------------
PUBLIC_SQL = """
SELECT (SELECT count(*) FROM public.tender)        AS t_n,
       (SELECT max(fetched_at) FROM public.tender) AS t_max
"""


def test_tozalash(before):
    head("11. Chegara va tozalash")
    after = db.query_one(PUBLIC_SQL)
    eq("public.tender soni tegilmadi", after["t_n"], before["t_n"])
    eq("public.tender yangilanmadi", after["t_max"], before["t_max"])

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('erp.audit_purge', 'on', false)")
            cur.execute(
                "DELETE FROM erp.chat_message_history WHERE message_id IN ("
                "  SELECT id FROM erp.chat_message WHERE text LIKE %(p)s)",
                {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.chat_message WHERE text LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute("DELETE FROM erp.opportunity_task "
                        "WHERE title LIKE %(p)s", {"p": "%" + MARK + "%"})
            # Navbat qatorlari CASCADE bilan ketadi.
            cur.execute(
                "DELETE FROM erp.notification WHERE app_user_id = ANY("
                "  SELECT id FROM erp.app_user WHERE username LIKE %(p)s)",
                {"p": PREFIX + "%"})
            cur.execute("DELETE FROM erp.notification WHERE matn LIKE %(p)s",
                        {"p": "%" + MARK + "%"})
            cur.execute(
                "DELETE FROM erp.notification_pref WHERE app_user_id = ANY("
                "  SELECT id FROM erp.app_user WHERE username LIKE %(p)s)",
                {"p": PREFIX + "%"})
            cur.execute(
                "DELETE FROM erp.chat_member WHERE app_user_id = ANY("
                "  SELECT id FROM erp.app_user WHERE username LIKE %(p)s)",
                {"p": PREFIX + "%"})
            cur.execute("UPDATE erp.app_user SET active = FALSE "
                        "WHERE username LIKE %(p)s", {"p": PREFIX + "%"})
        conn.commit()
    eq("sinov bildirishnomalari tozalandi",
       db.scalar("SELECT count(*) FROM erp.notification WHERE matn LIKE %(p)s",
                 {"p": "%" + MARK + "%"}), 0)
    # YETIM QATOR QOLMADI: `ON DELETE CASCADE` haqiqatan ishlayaptimi.
    eq("navbatda yetim qator yo'q",
       db.scalar("SELECT count(*) FROM erp.notification_delivery d "
                 "LEFT JOIN erp.notification n ON n.id = d.notification_id "
                 "WHERE n.id IS NULL"), 0)
    check(FIX.cleanup() >= 0, "fixture tozalandi")


if __name__ == "__main__":
    test_reyestr()
    try:
        db.init_pool()
    except Exception as e:                          # noqa: BLE001
        print(f"\n  DIQQAT: bazasiz sinov: {e}")
    else:
        before = db.query_one(PUBLIC_SQL)
        try:
            test_sxema()
            ctx = test_qabul()
            test_chiqarish(ctx)
            chat_ctx = test_chat_bildirishnoma(ctx)
            test_sahifalash(ctx, chat_ctx)
            test_navbat(ctx)
            test_oqish(ctx)
            test_oqim(ctx, chat_ctx)
            test_sozlama(ctx)
        finally:
            test_tozalash(before)
        db.close_pool()

    print("\n" + "=" * 50)
    print(f"NATIJA: {_pass} ta o'tdi, {_fail} ta xato")
    sys.exit(1 if _fail else 0)
