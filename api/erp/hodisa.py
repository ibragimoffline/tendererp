"""
HODISA — bildirishnomaning YAGONA quviri.

    from api.erp import hodisa
    hodisa.chiqar("vazifa", broker_id=7, matn="...", opportunity_id=12)
    hodisa.chat_xabar(chat_id, muallif_user_id, "Karimov: narx tayyor")

MUAMMO: bildirishnoma yuborish TO'RT modulga tarqalgan edi —
`topshiriq.py`, `opportunity.py`, `remind.py`, `chat.py`. Har biri
o'zicha qabul qiluvchi tanlardi va "kim nima oladi?" degan savolga
javob berish uchun to'rttasini birga o'qish kerak edi. Yangi hodisa
qo'shilganda esa kimdir albatta unutilardi.

YECHIM: hodisa — MA'LUMOT (`HODISALAR` jadvali), kod emas. Modul
"nima bo'ldi"ni aytadi; kimga borishi va qaysi kanaldan ketishi shu
faylda hal bo'ladi.

UCH QATLAM (ikkinchisi shu fayl):

    hodisa.py   NIMA bo'ldi -> KIMGA -> qaysi KANAL      <- shu fayl
    xabar.py    qanday SAQLANADI va O'QILADI
    navbat.py   tashqi kanalga qanday YETKAZILADI

QABUL QILUVCHI — MUNOSABATDAN, RO'YXATDAN EMAS
══════════════════════════════════════════════
Hech qayerda hisob id si qo'lda yozilmaydi. Har hodisa uchun
"kim aloqador" degan savol ERP ning O'Z bog'lanishlaridan chiqadi:
kartaning mas'uli (`opportunity.broker_id`), chat a'zolari
(`chat_member`), vazifa bajaruvchisi (`opportunity_task.
assignee_broker_id`). Shuning uchun hodim almashsa bildirishnoma
ham o'zi to'g'ri odamga ketadi.

O'Z AMALI HAQIDA XABAR KELMAYDI (§13)
═════════════════════════════════════
Har resolverda `chiqaruvchi` (amalni bajargan hisob) ro'yxatdan
olib tashlanadi. Istisno YO'Q: "o'zim yozgan xabarim haqida
bildirishnoma" bildirishnomalarga bo'lgan ishonchni yo'qotadigan
birinchi narsa.

TASHQI KANAL — KOMPANIYA DARAJASIDA, ODAM DARAJASIDA EMAS
═════════════════════════════════════════════════════════
Bu CHEKLOV, tanlov emas: Telegram bot tokeni va SMTP rekvizitlari
Tender-AI o'rnatmasida (`api/tenderai.py` -> `notify`) va u yerda
qabul qiluvchilar KOMPANIYA sozlamasi bo'lib turadi. ERP manzil
yubormaydi va yubora olmaydi.

Natijada: tashqi kanal hodisaga BIR MARTA qo'yiladi (birinchi qabul
qiluvchining qatoriga), har odamga emas — aks holda besh hodimga
tegishli bitta hodisa uchun guruhga BESH xabar ketardi.

Shuning uchun `HODISALAR` da tashqi kanal FAQAT butun kompaniyaga
tegishli hodisalarda bor. Chat u yerda YO'Q: yozishmani Telegram
guruhiga ko'chirish yozishmaning o'zini ma'nosiz qilardi.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from api import db
from api.erp import xabar

log = logging.getLogger("erp.hodisa")

#: Tashqi kanallar. `navbat.py` ularni yuboradi; bu yerda faqat NOM.
TELEGRAM = "telegram"
EMAIL = "email"

#: Kompaniya kanali — ikkalasi birga (Tender-AI `notify` ikkalasini
#: bitta chaqiruvda oladi, lekin holat AJRATIB yoziladi: email ketib,
#: Telegram yiqilishi mumkin).
KOMPANIYA = [TELEGRAM, EMAIL]


# =============================================================================
# REYESTR — qaysi hodisa, qanday kanal
# =============================================================================
# Har qator: hodisa turi -> (odam o'qiydigan nomi, tashqi kanallar).
#
# ILOVA KANALI RO'YXATDA YO'Q va bu ataylab: u HAR DOIM bor va uni
# o'chirib bo'lmaydi. Sababi — u yagona kanal bo'lib, tashqi xizmatga
# bog'liq emas va "o'qilganmi" degan holatni saqlaydi. Uni o'chirish
# imkoniyati "bildirishnoma yubordik, lekin hech qayerda yo'q" degan
# holatni yaratardi.
#
# TASHQI KANAL FAQAT SHOSHILINCH VA KOMPANIYAGA TEGISHLI hodisalarda:
# odam ERP ni ochmasa ham bilishi kerak bo'lgan narsalar. Qolganini
# qo'shish Telegram guruhini foydasiz shovqinga aylantirardi va bir
# hafta ichida hamma uni o'chirardi — shundan keyin HAQIQIY
# ogohlantirish ham yetib bormasdi.
HODISALAR: Dict[str, Any] = {
    "topshiriq":      ("Tender-AI'dan yangi karta", []),
    "taqsimlanmagan": ("Karta taqsimlanmagan", KOMPANIYA),
    "bekor":          ("Tender-AI'da qaror bekor qilindi", []),
    "otkazildi":      ("Karta o'tkazildi", []),
    "biriktirish_olib_tashlandi": ("Karta olib qo'yildi", []),
    "status":         ("Karta holati o'zgardi", []),
    "vazifa":         ("Vazifa biriktirildi", []),
    "muddat":         ("Muddat yaqinlashdi", KOMPANIYA),
    "hujjat_muddat":  ("Hujjat muddati tugayapti", KOMPANIYA),
    "qaror":          ("Qaror kerak", []),
    "tizim":          ("Tizim xatosi — aralashuv kerak", KOMPANIYA),
    "jamoa_qoshildi": ("Tender jamoasiga qo'shildingiz", []),
    "jamoa_chiqarildi": ("Tender jamoasidan chiqarildingiz", []),
    "jamoa_rol":      ("Tenderdagi mas'uliyat o'zgardi", []),
    "chat_yangi":     ("Yangi xabar", []),
    "chat_mention":   ("Chatda eslatish", []),
    "chat_qoshildi":  ("Chatga qo'shildi", []),
    "chat_ochirildi": ("Xabar o'chirildi", []),
}


def kanallar(kind: str, app_user_id: int, birinchi: bool) -> List[str]:
    """Shu hodisa shu odamga qaysi TASHQI kanallardan ketadi.

    Uch filtr:
      1. Reyestr (yuqorida) — hodisaning o'z tabiati;
      2. `birinchi` — tashqi kanal kompaniya darajasida, ya'ni bir
         hodisaga BIR marta (moduldagi katta izohga qarang);
      3. Hodimning sozlamasi (`erp.notification_pref`).

    Ilova kanali bu ro'yxatda YO'Q — u `xabar.yoz()` da har doim."""
    if not birinchi:
        return []
    tayin = HODISALAR.get(kind, (kind, []))[1]
    if not tayin:
        return []
    return [k for k in tayin if _yoqilgan(app_user_id, kind, k)]


PREF_SQL = """
SELECT yoqilgan FROM erp.notification_pref
WHERE app_user_id = %(u)s AND kanal = %(k)s AND kind = ANY(%(kinds)s)
-- Aniqroq qoida ustun: '*' umumiy, hodisa nomi esa aynan shu hodisa.
ORDER BY (kind = '*') LIMIT 1
"""


def _yoqilgan(app_user_id: int, kind: str, kanal: str) -> bool:
    """Sozlama. QATOR YO'Q = YOQILGAN (standart holat kodda)."""
    try:
        r = db.query_one(PREF_SQL, {"u": app_user_id, "k": kanal,
                                    "kinds": [kind, "*"]})
    except Exception:                               # noqa: BLE001
        # Sozlama jadvali yo'q (27-patch qo'llanmagan) — standart holat.
        return True
    return bool(r["yoqilgan"]) if r else True


# =============================================================================
# QABUL QILUVCHINI ANIQLASH — biznes munosabatidan
# =============================================================================
USER_BY_BROKER_SQL = ("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                      "AND active ORDER BY id LIMIT 1")


def broker_hisobi(broker_id: Optional[int]) -> Optional[int]:
    """Hodim -> uning FAOL hisobi.

    Hodim hisobsiz bo'lishi mumkin (omborchi, hujjatchi) — u holda
    `None` va bu XATO EMAS: u tizimga kirmaydi."""
    if not broker_id:
        return None
    return db.scalar(USER_BY_BROKER_SQL, {"b": broker_id})


def boshliqlar() -> List[int]:
    """Kundalik ishning EGALARI: menejer, bo'lmasa rahbar.

    NEGA ADMINGA EMAS: administrator tizimni sozlaydi, ish
    taqsimlamaydi (`erp_rollar.md` §3.6). Menejer yo'q bo'lsa rahbar
    oladi — xabar egasiz qolmasin."""
    rollar = ["menejer"]
    if not db.query_one("SELECT 1 AS x FROM erp.app_user "
                        "WHERE role = 'menejer' AND active LIMIT 1"):
        rollar = ["rahbar"]
    return [r["id"] for r in db.query(
        "SELECT id FROM erp.app_user WHERE role = ANY(%(r)s) AND active",
        {"r": rollar})]


#: Chat a'zolari. `umumiy` chatda a'zolik VIRTUAL — barcha faol
#: hisoblar (`api/erp/chat.py` dagi qoida bilan bir xil).
#:
#: JIMLANGAN chiqarib tashlanadi (`chat_member.muted_at`), lekin
#: O'QILMAGAN HISOBLAGICHI ishlayveradi: jimlash "bildirishnoma
#: kelmasin" degani, "ko'rmayman" degani emas.
CHAT_AZO_SQL = """
SELECT m.app_user_id
FROM erp.chat_member m
JOIN erp.app_user u ON u.id = m.app_user_id AND u.active
WHERE m.chat_id = %(c)s AND m.removed_at IS NULL AND m.muted_at IS NULL
"""

CHAT_UMUMIY_AZO_SQL = """
SELECT u.id AS app_user_id
FROM erp.app_user u
LEFT JOIN erp.chat_member m
       ON m.chat_id = %(c)s AND m.app_user_id = u.id
WHERE u.active
  -- Umumiy chatda `chat_member` qatori FAQAT jimlash uchun paydo
  -- bo'ladi (a'zolik baribir virtual), shuning uchun bu yerda u
  -- "chiqarilgan" emas, "jim" degan ma'noni beradi.
  AND m.muted_at IS NULL
  -- ADMIN YOZISHMADA QATNASHMAYDI (`erp_rollar.md`) — unga chat
  -- bildirishnomasi ham bormaydi.
  AND u.role <> 'admin'
"""


def chat_qabul(chat_id: int, chiqaruvchi: Optional[int] = None) -> List[int]:
    """Chatning bildirishnoma oladigan a'zolari — MUALLIFSIZ."""
    ch = db.query_one("SELECT turi FROM erp.chat WHERE id = %(c)s",
                      {"c": chat_id})
    if not ch:
        return []
    sql = CHAT_UMUMIY_AZO_SQL if ch["turi"] == "umumiy" else CHAT_AZO_SQL
    return [r["app_user_id"] for r in db.query(sql, {"c": chat_id})
            if r["app_user_id"] != chiqaruvchi]


# =============================================================================
# CHIQARISH
# =============================================================================
def chiqar(kind: str, matn: str,
           qabul: Optional[Sequence[Optional[int]]] = None,
           broker_id: Optional[int] = None,
           boshliqqa: bool = False,
           opportunity_id: Optional[int] = None,
           chat_id: Optional[int] = None,
           task_id: Optional[int] = None,
           chiqaruvchi: Optional[int] = None,
           dedup: Optional[str] = None,
           kotar: bool = True) -> Dict[str, Any]:
    """Hodisa -> bildirishnoma(lar). HECH QACHON YIQITMAYDI.

    Qabul qiluvchi uch yo'ldan biri bilan beriladi va ular birga
    ishlaydi:
        `qabul`      — tayyor hisob id lari (masalan chat a'zolari);
        `broker_id`  — hodim (uning faol hisobi topiladi);
        `boshliqqa`  — menejer(lar), bo'lmasa rahbar.

    `chiqaruvchi` — amalni bajargan hisob. U ro'yxatdan CHIQARILADI
    (§13): o'z amali haqida xabar olish bildirishnomalarga bo'lgan
    ishonchni yo'qotadi.

    Qaytadi: `{"yozildi": n, "kimga": [...], "tashqi": [...]}` —
    sinov va jurnal uchun. Nol yozilgani XATO EMAS: hisobsiz hodim
    yoki hamma jimlagan chat — normal holat."""
    kimga: List[int] = []
    for uid in (qabul or []):
        if uid and uid not in kimga:
            kimga.append(int(uid))
    if broker_id:
        u = broker_hisobi(broker_id)
        if u and u not in kimga:
            kimga.append(u)
    if boshliqqa:
        for u in boshliqlar():
            if u not in kimga:
                kimga.append(u)
    if chiqaruvchi:
        kimga = [u for u in kimga if u != chiqaruvchi]

    yozildi, tashqi_ketdi = 0, []
    for i, uid in enumerate(sorted(kimga)):
        # TASHQI kanal BIRINCHI qabul qiluvchida (moduldagi izoh):
        # u kompaniya darajasida ishlaydi va har odam uchun
        # takrorlansa guruhga bir xil xabar N marta ketardi.
        tashqi = kanallar(kind, uid, birinchi=(i == 0))
        r = xabar.yoz(uid, kind, matn, opportunity_id=opportunity_id,
                      chat_id=chat_id, task_id=task_id,
                      dedup_key=(f"{dedup}:{uid}" if dedup else None),
                      kotar=kotar, tashqi_kanallar=tashqi)
        if r:
            yozildi += 1
            if tashqi:
                tashqi_ketdi = tashqi
    return {"yozildi": yozildi, "kimga": sorted(kimga), "tashqi": tashqi_ketdi}


# =============================================================================
# TAYYOR HODISALAR — chaqiruvchi matn yozib o'tirmasin
# =============================================================================
# Matn SHU YERDA, chaqiruvchida emas: bir xil hodisa ikki joydan
# chiqarilsa (masalan karta o'tkazish — ekrandan ham, Tender-AI
# yo'naltirishidan ham) ikki xil matn chiqardi va odam ularni boshqa
# hodisa deb o'ylardi.
#
# QISQA VA AMALIY (§16): ichki id yozilmaydi, dasturchi atamasi yo'q.
def _nom(title: Optional[str], opp_id: Optional[int]) -> str:
    """Kartaning odam o'qiydigan nomi.

    Nom yo'q bo'lsa `#12` — bu YAGONA joyda id ko'rsatiladi va
    ataylab: nomsiz kartani boshqa yo'l bilan ajratib bo'lmaydi."""
    return (title or "").strip() or f"#{opp_id}"


def karta_biriktirildi(broker_id: Optional[int], opp_id: int,
                       title: Optional[str], kim: Optional[str],
                       manba: str = "Tender-AI") -> Dict[str, Any]:
    """Hodimga karta biriktirildi. Hodim yo'q bo'lsa — boshliqqa."""
    nom = _nom(title, opp_id)
    if broker_id:
        return chiqar("topshiriq", f"Yangi karta: {nom}"
                      + (f" (yo'naltirdi: {kim})" if kim else ""),
                      broker_id=broker_id, opportunity_id=opp_id)
    return chiqar(
        "taqsimlanmagan",
        f"Karta taqsimlanmagan: {nom}. {manba}'da hodim ko'rsatilmagan "
        f"yoki u ERP hodimiga xaritalanmagan"
        + (f" (yo'naltirdi: {kim})" if kim else "") + ".",
        boshliqqa=True, opportunity_id=opp_id)


def karta_otkazildi(yangi_broker: Optional[int], eski_broker: Optional[int],
                    opp_id: int, title: Optional[str],
                    chiqaruvchi: Optional[int] = None) -> Dict[str, Any]:
    """Mas'ul almashdi: YANGISIGA "sizga o'tkazildi", ESKISIGA
    "sizdan olindi".

    ESKISI HAM XABAR OLADI va bu ONGLI qaror: u karta ustida
    ishlayotgan bo'lishi mumkin va ish jimgina qo'lidan olinsa,
    buni faqat ro'yxatdan yo'qolganda sezardi."""
    nom = _nom(title, opp_id)
    r1 = chiqar("otkazildi", f"Karta sizga o'tkazildi: {nom}.",
                broker_id=yangi_broker, opportunity_id=opp_id,
                chiqaruvchi=chiqaruvchi)
    r2 = chiqar("biriktirish_olib_tashlandi",
                f"Karta sizdan boshqa hodimga o'tkazildi: {nom}.",
                broker_id=eski_broker, opportunity_id=opp_id,
                chiqaruvchi=chiqaruvchi)
    return {"yozildi": r1["yozildi"] + r2["yozildi"],
            "kimga": sorted(set(r1["kimga"]) | set(r2["kimga"])),
            "tashqi": r1["tashqi"] or r2["tashqi"]}


def karta_holati(opp_id: int, title: Optional[str], eski: str, yangi: str,
                 kim: Optional[str],
                 chiqaruvchi: Optional[int] = None) -> Dict[str, Any]:
    """Karta holati o'zgardi -> kartaning MAS'ULI va uning chati a'zolari.

    NEGA CHAT A'ZOLARI: chatga qo'shilgan odam — aynan shu karta
    bo'yicha ishlayotgan odam (`chat_member`). Alohida "kuzatuvchi"
    ro'yxati kiritilsa u a'zolik bilan ajralib ketardi.

    Amalni bajargan odam O'ZI xabar OLMAYDI (§13)."""
    nom = _nom(title, opp_id)
    o = db.query_one("SELECT broker_id FROM erp.opportunity WHERE id = %(i)s",
                     {"i": opp_id}) or {}
    chat_id = db.scalar("SELECT id FROM erp.chat WHERE opportunity_id = %(i)s",
                        {"i": opp_id})
    return chiqar("status", f"{nom}: {eski} -> {yangi}"
                  + (f" ({kim})" if kim else ""),
                  qabul=(chat_qabul(chat_id) if chat_id else []),
                  broker_id=o.get("broker_id"), opportunity_id=opp_id,
                  chiqaruvchi=chiqaruvchi)


def vazifa_biriktirildi(task_id: int, broker_id: Optional[int],
                        title: str, opp_id: Optional[int],
                        muddat: Optional[str] = None,
                        chiqaruvchi: Optional[int] = None) -> Dict[str, Any]:
    """Vazifa hodimga biriktirildi.

    KONTEKST MATNDA ko'rinadi: umumiy vazifa bilan tender vazifasini
    bildirishnomaning O'ZIDAN ajratib bo'lishi kerak, aks holda odam
    uni ochmasdan turib nima haqida ekanini bilmasdi."""
    return chiqar("vazifa", f"Sizga vazifa: {title}"
                  + (f" — muddat {muddat}" if muddat else ""),
                  broker_id=broker_id, opportunity_id=opp_id,
                  task_id=task_id, chiqaruvchi=chiqaruvchi,
                  # BIR VAZIFA BIR MARTA: vazifa tahrirlanganda
                  # (masalan izoh qo'shilganda) takror yubormaslik
                  # uchun. `kotar=False` — mavjudi tegilmaydi ham.
                  dedup=f"vazifa:{task_id}", kotar=False)


def chat_xabar(chat_id: int, muallif_user_id: Optional[int],
               muallif_nomi: str, matn: str,
               opportunity_id: Optional[int] = None,
               chat_nomi: Optional[str] = None) -> Dict[str, Any]:
    """Chatga yangi xabar -> a'zolarga (muallifdan tashqari).

    HAR XABARGA ALOHIDA QATOR YOZILMAYDI. Kalit `chat_yangi:{chat}`
    bo'lgani uchun bitta chatdagi ketma-ket xabarlar BITTA
    bildirishnomaga yig'iladi va u har safar KO'TARILADI (matn
    yangilanadi, o'qilgan belgisi olinadi).

    NEGA: 20 ta xabarlik suhbat 20 ta bildirishnoma bergan bo'lardi
    va odam ertasiga hammasini o'qimay yopishni odat qilardi —
    shundan keyin HAQIQIY xabar ham ko'rinmasdi. O'qilmaganlar
    hisoblagichi (chatning O'ZIDA) aniq sonni baribir ko'rsatadi."""
    qisqa = (matn or "").strip().replace("\n", " ")
    if len(qisqa) > 90:
        qisqa = qisqa[:89] + "…"
    joy = f" — {chat_nomi}" if chat_nomi else ""
    return chiqar("chat_yangi", f"{muallif_nomi}{joy}: {qisqa}",
                  qabul=chat_qabul(chat_id, muallif_user_id),
                  chat_id=chat_id, opportunity_id=opportunity_id,
                  chiqaruvchi=muallif_user_id,
                  dedup=f"chat_yangi:{chat_id}", kotar=True)


def hujjat_muddati(app_user_ids: Sequence[int], matn: str,
                   dedup: str) -> Dict[str, Any]:
    """Mijoz hujjatining muddati tugayapti (`erp.client_document`)."""
    return chiqar("hujjat_muddat", matn, qabul=app_user_ids, dedup=dedup,
                  kotar=False)


def qaror_kerak(matn: str, opp_id: Optional[int] = None,
                broker_id: Optional[int] = None,
                chiqaruvchi: Optional[int] = None) -> Dict[str, Any]:
    """Odam qaror qabul qilishi kerak: taklif tasdiqlash, qayta
    taqsimlash so'rovi, Go/No-Go."""
    return chiqar("qaror", matn, boshliqqa=True, broker_id=broker_id,
                  opportunity_id=opp_id, chiqaruvchi=chiqaruvchi)


def tizim_nosozligi(matn: str, dedup: Optional[str] = None) -> Dict[str, Any]:
    """ODAM ARALASHUVI kerak bo'lgan nosozlik.

    Har xatoga emas: faqat ish oqimi TO'XTAGAN va uni tizim o'zi
    tuzata olmaydigan holatlar (masalan Tender-AI yo'naltirishi
    kelgan, lekin karta ochilmagan). Har `try/except` shu yerga
    ulansa, bir hafta ichida bu bildirishnoma ham o'qilmay qolardi."""
    return chiqar("tizim", matn, boshliqqa=True, dedup=dedup, kotar=False)


# =============================================================================
# SOZLAMA — kim qaysi tashqi kanalni oladi
# =============================================================================
# ILOVA KANALI O'ZGARTIRILMAYDI va bu ONGLI cheklov: u yagona kanal
# bo'lib, tashqi xizmatga bog'liq emas va "o'qilganmi" holatini
# saqlaydi. O'chirish imkoniyati "bildirishnoma yubordik, lekin u
# hech qayerda yo'q" degan holatni yaratardi — foydalanuvchi uchun
# bu bildirishnomaning umuman yo'qligidan ham yomonroq, chunki
# tizim "xabar berdim" deb hisoblaydi.
SOZLANADIGAN = (TELEGRAM, EMAIL)

SOZLAMA_SQL = """
INSERT INTO erp.notification_pref (app_user_id, kind, kanal, yoqilgan)
VALUES (%(u)s, %(kind)s, %(kanal)s, %(y)s)
ON CONFLICT (app_user_id, kind, kanal) DO UPDATE SET yoqilgan = %(y)s
RETURNING kind, kanal, yoqilgan
"""


def sozlamalarim(app_user_id: int) -> Dict[str, Any]:
    """O'z sozlamalari + qaysi hodisa qaysi kanalga tegishli ekani.

    `hodisalar` ham qaytadi: aks holda interfeys o'z ro'yxatini
    tutardi va reyestr bilan ajralib ketardi (`perm.for_user()`
    bilan bir xil naqsh)."""
    try:
        rows = db.query(
            "SELECT kind, kanal, yoqilgan FROM erp.notification_pref "
            "WHERE app_user_id = %(u)s ORDER BY kind, kanal",
            {"u": app_user_id})
    except Exception:                               # noqa: BLE001
        rows = []
    return {
        "sozlanadigan": list(SOZLANADIGAN),
        "hodisalar": [{"kind": k, "label": v[0], "kanallar": v[1]}
                      for k, v in HODISALAR.items()],
        "prefs": [{"kind": r["kind"], "kanal": r["kanal"],
                   "yoqilgan": bool(r["yoqilgan"])} for r in rows],
    }


def sozlama_qoy(app_user_id: int, kind: str, kanal: str,
                yoqilgan: bool) -> Dict[str, Any]:
    """Bitta sozlama. Faqat TASHQI kanal, faqat mavjud hodisa turi."""
    from api.erp.opportunity import ErpError
    if kanal not in SOZLANADIGAN:
        raise ErpError(
            f"'{kanal}' kanali sozlanmaydi. Ilova bildirishnomasi "
            "har doim yoqiq — u yagona ishonchli kanal.")
    if kind != "*" and kind not in HODISALAR:
        raise ErpError(f"Noma'lum hodisa turi: {kind}")
    r = db.execute_returning(SOZLAMA_SQL, {
        "u": app_user_id, "kind": kind, "kanal": kanal, "y": bool(yoqilgan)})
    return {"kind": r["kind"], "kanal": r["kanal"],
            "yoqilgan": bool(r["yoqilgan"])}
