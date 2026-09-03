"""
HUQUQLAR — kim nima qila oladi. YAGONA joy.

    from api.erp import perm
    perm.require(user, "hujjat.chiqarish")     # ruxsat bo'lmasa 403
    perm.can(user, "karta.korish")             # 'full' | 'own' | 'read' | None

MUAMMO: huquq tekshiruvi endpointlar bo'ylab tarqalgan edi —
`require_role(user, "menejer")` bir joyda, `Depends(menejer)` boshqasida,
qolgan yuzlab endpointda esa umuman yo'q. "Broker fakturani chiqara
oladimi?" degan savolga javob berish uchun `main.py` ni boshdan-oxir
o'qish kerak edi va javob HAR SAFAR boshqacha chiqardi.

YECHIM: matritsa — MA'LUMOT, kod emas. Pastdagi jadval `erp_rollar.md`
§3 ning aynan o'zi. Endpoint ichida `if rol == ...` YOZILMAYDI: u yerda
faqat bitta qator qoladi — qaysi AMAL bajarilayotgani.

NEGA AMAL NOMI, ROL NOMI EMAS: endpoint "menejer kerak" desa, rol
qo'shilganda yoki huquq ko'chganda hamma endpointni qayta o'qish kerak
bo'lardi. "hujjat.chiqarish" esa o'zgarmaydi — o'zgaradigani KIM shuni
qila olishi, va u faqat shu fayldagi jadvalda.

DARAJALAR:
    TOLIQ ('full') — hammasi;
    OZ    ('own')  — faqat o'ziga biriktirilgani;
    KOR   ('read') — faqat o'qish;
    None           — yo'q (403).

`OZ` NIMA EKANI shu modulda EMAS: bu jadval amalni biladi, obyektni
bilmaydi ("kartani tahrirlash mumkin" deydi, "shu kartani" demaydi).
Egalik zanjiri — `api/erp/egalik.py` da (hisob -> hodim -> karta), va
uni endpointlar `_can_obj()` orqali chaqiradi. Shuning uchun `can()`
DARAJANI qaytaradi: chaqiruvchi uni ro'yxat filtriga yoki obyekt
tekshiruviga aylantiradi.

KOMPANIYAGA BOG'LIQ UCH QATOR jadvalda emas, SOZLAMADA
(`api/erp/sozlama.py`, `erp.setting`): "broker kartani o'zi
yakunlaydimi", "menejer foydani ko'radimi" va "admin biznes
ma'lumotni faqat ko'radimi". Ular kompaniyadan kompaniyaga
o'zgaradi, ya'ni ular KOD emas — sozlama. Jadval ularning eng
keng holatini ko'rsatadi, sozlama esa toraytiradi
(`SOZLAMAGA_BOGLIQ`).

ADMIN HAQIDA. Hujjat bo'yicha admin biznes ma'lumotni KO'RADI, lekin
O'ZGARTIRMAYDI (tizim sozlovchi va pul hujjati o'zgartiruvchi bitta
odam bo'lmasin). Standart holatda bu O'CHIQ: o'rnatmada bitta admin
bor va u aynan ishni yuritayotgan odam. Yoqishdan OLDIN `rahbar`
hisobi ochilishi kerak, aks holda kompaniya o'z ERP siga yozolmay
qoladi. Yoqilganda admin uchun jadvaldagi qiymatlar ishlaydi.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from api import auth
from api.erp import sozlama

TOLIQ = "full"
OZ = "own"
KOR = "read"

#: (amal, rol) -> sozlama kaliti. Sozlama O'CHIQ bo'lsa — huquq YO'Q.
#:
#: Jadvalning O'ZIGA yozib bo'lmaydi: u "kim nima qila oladi"ni
#: ko'rsatadi va o'zgarmas bo'lishi kerak. Bu esa kompaniyaning
#: qarori — qiymati bazada (`erp.setting`).
SOZLAMAGA_BOGLIQ = {
    ("karta.yopish", "broker"): "broker_can_close",
    ("hisobot.foyda", "menejer"): "menejer_foyda",
}

#: `OZ` obyekt darajasida filtrlanadimi (`api/erp/egalik.py`).
#:
#: Bayroq SAQLANDI (o'chirilmadi): egalik zanjiri `erp.opportunity.
#: broker_id` ga tayanadi va u hamma kartada to'ldirilgan bo'lishi
#: kerak. Ma'lumot ko'chirishda (masalan Tender-AI yo'naltirishi
#: kiritilganda) zanjir vaqtincha uzilsa, filtrni bir joydan
#: o'chirib turish "hamma narsa yo'qoldi" holatidan chiqaradi.
OZ_FILTRI_TAYYOR = True

# =============================================================================
# MATRITSA — erp_rollar.md §3
# =============================================================================
# Har qator: amal -> (odam o'qiydigan nomi, {rol: daraja}).
#
# Nomi XATO MATNIDA ishlatiladi: "Huquq yo'q: Fakturani chiqarish
# (Broker)" — odam nima qilolmaganini va nima uchun ekanini biladi.
#
# ANIQLASHTIRILSIN deb belgilangan qatorlar: manba hujjatdagi jadvalda
# ✓ va — belgilari kodlash buzilgani uchun ajratib bo'lmadi. Ular
# ehtiyotkorlik tomoniga o'girilgan (kamroq huquq) va tasdiqlanishi
# kerak.
AMALLAR: Dict[str, Any] = {
    # --- ish kartalari (§3.1) ------------------------------------------
    "karta.korish": ("Kartalarni ko'rish", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "karta.yaratish": ("Karta yaratish (ishga olish)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "karta.tahrirlash": ("Kartani tahrirlash (ustuvorlik, izoh, vazifa)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "karta.biriktirish": ("Kartani boshqa hodimga o'tkazish", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    # Broker kartani O'ZI o'tkaza olmaydi (yuqoridagi qator), lekin
    # "menga bu ish to'g'ri kelmadi" deyishi kerak — aks holda u
    # menejerni og'zaki qidiradi va iz qolmaydi.
    "karta.taqsimlash_sorovi": ("Qayta taqsimlashni so'rash", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "karta.status": ("Karta statusini o'zgartirish", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    # Yakuniy status — alohida amal: brokerga ruxsat berish/bermaslik
    # sozlama bo'ladi (`broker_can_close`, hozir "ha").
    "karta.yopish": ("Kartani yakunlash (yutildi / yutqazildi / rad / "
                     "ulgurmadik)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    # Sabab hujjati (24-patch). Daraja `karta.yopish` bilan bir xil: kim
    # kartani yopa oladi, o'sha "nega yopdim" hujjatini ham biriktiradi
    # va xato yuklaganini o'chiradi. O'chirish izi `doc_audit` da qoladi,
    # shuning uchun alohida, torroq amal qilishning ma'nosi yo'q.
    "karta.fayl": ("Kartaga sabab hujjatini biriktirish / o'chirish", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "karta.qaytarish": ("Yakuniy statusdan qaytarish", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "karta.tahlil": ("Tender-AI tahlilini ko'rish", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "karta.foyda": ("Bitta kartaning foydasi", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),

    # --- mijoz korxonalar (§3.2) ---------------------------------------
    "mijoz.korish": ("Mijoz passportini ko'rish", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "mijoz.tahrirlash": ("Mijoz yaratish / tahrirlash", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "mijoz.aloqa": ("Aloqa shaxslari", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "mijoz.hujjat": ("Mijoz hujjatlari (litsenziya, sertifikat)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),

    # --- ombor (§3.3) ---------------------------------------------------
    "ombor.korish": ("Ombor qoldig'i", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": KOR}),
    # Kirim ham, chiqim ham BITTA amal: ikkalasi ham `erp.stock_move` ga
    # yozadi va hujjatda ikkalasining huquqi bir xil (rahbar-menejer).
    "ombor.harakat": ("Ombor kirimi / chiqimi", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "ombor.rezerv": ("Kartaga tovar ajratish (rezerv)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),

    # --- pul hujjatlari: faktura va akt (§3.4) --------------------------
    "hujjat.korish": ("Pul hujjatlarini ko'rish", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "hujjat.qoralama": ("Qoralama hujjat (yaratish, qatorlar)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),
    "hujjat.chiqarish": ("Hujjatni chiqarish (raqam beriladi)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "hujjat.bekor": ("Hujjatni bekor qilish / storno", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "hujjat.tolov": ("To'lov qaydi", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "hujjat.eksport": ("Hujjat eksporti", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "hujjat.jurnal": ("O'zgarishlar jurnali (audit)", {
        "admin": None, "rahbar": TOLIQ, "menejer": KOR, "broker": None}),
    # Shartnoma hujjatda alohida qator sifatida yo'q. U KARTANING ishi
    # (taklif -> shartnoma -> faktura), shuning uchun karta bilan bir xil
    # huquq oladi va broker o'znikini yuritaveradi.
    "shartnoma.tahrirlash": ("Shartnoma yozuvi", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),

    # --- hisobotlar (§3.5) ----------------------------------------------
    # KOMPANIYA bo'yicha ko'rsatkich: voronka, hodimlar kesimi, qarzdorlik.
    # Brokerga YO'Q — bu odamlar haqidagi ko'rsatkich ham. Uning o'z
    # kartalari bo'yicha kesimi alohida ekranda (`/erp/my-tasks`,
    # kartalar ro'yxati) va u ochiq.
    "hisobot.kompaniya": ("Kompaniya ko'rsatkichlari", {
        "admin": TOLIQ, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    # Menejer uchun hujjatda "sozlanadi" deyilgan — sozlama kiritilguncha
    # ochiq (u kundalik ishni yuritadi va marjani ko'rmasa narx haqida
    # qaror qabul qila olmaydi).
    "hisobot.foyda": ("Foyda hisoboti (kompaniya bo'yicha)", {
        "admin": None, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": None}),
    "hisobot.deadline": ("Muddatlar va eslatmalar", {
        "admin": KOR, "rahbar": TOLIQ, "menejer": TOLIQ, "broker": OZ}),

    # --- tizim (§3.6) ---------------------------------------------------
    # ANIQLASHTIRILSIN: hujjatda rahbar ham hodim yarata oladi ("admin'dan
    # tashqari"). Bu OBYEKT darajasidagi shart (qaysi hisobga tegilyapti)
    # va u `OZ` filtri bilan birga keladi; shu paytgacha faqat admin.
    "tizim.hodim": ("Hodim va hisoblarni boshqarish", {
        "admin": TOLIQ, "rahbar": None, "menejer": None, "broker": None}),
    # ANIQLASHTIRILSIN: kompaniya passporti — rekvizit, ya'ni fakturaning
    # yarmi. Direktorga ochiq, qolganlarga yo'q.
    "tizim.kompaniya": ("Kompaniya passporti (rekvizitlar)", {
        "admin": TOLIQ, "rahbar": TOLIQ, "menejer": None, "broker": None}),
    "tizim.sozlama": ("Tizim sozlamalari", {
        "admin": TOLIQ, "rahbar": None, "menejer": None, "broker": None}),
    "tizim.tai_xarita": ("Tender-AI xaritasi", {
        "admin": TOLIQ, "rahbar": None, "menejer": None, "broker": None}),
}


def label(action: str) -> str:
    """Amalning odam o'qiydigan nomi."""
    return AMALLAR[action][0]


def can(user: Dict[str, Any], action: str) -> Optional[str]:
    """Daraja: `TOLIQ` / `OZ` / `KOR` / `None`.

    Noma'lum amal — DASTURCHI xatosi (chop etilmagan amal nomi), shuning
    uchun jimgina `None` emas, `KeyError`: u sinovda darhol ko'rinadi.
    Jimgina rad etish esa ishlaydigan ekranni sababsiz yopardi."""
    if action not in AMALLAR:
        raise KeyError(f"Noma'lum amal: {action!r} (api/erp/perm.py)")
    rol = (user or {}).get("role")
    if rol == "admin" and not sozlama.yoq("admin_faqat_koradi"):
        return TOLIQ
    daraja = AMALLAR[action][1].get(rol)
    kalit = SOZLAMAGA_BOGLIQ.get((action, rol))
    if daraja and kalit and not sozlama.yoq(kalit):
        # Kompaniya bu huquqni o'chirib qo'ygan (masalan yakuniy
        # qarorni faqat rahbar qo'yadi).
        return None
    return daraja


def require(user: Dict[str, Any], action: str) -> Optional[str]:
    """Ruxsat bo'lmasa 403. Bo'lsa — DARAJANI qaytaradi.

    Chaqiruvchi darajani ishlatishi mumkin (`OZ` bo'lsa ro'yxatni
    filtrlash). Hozircha ko'pchilik joyda e'tiborsiz qoldiriladi —
    yuqoridagi izohga qarang."""
    daraja = can(user, action)
    if not daraja:
        rol = (user or {}).get("role")
        raise auth.AuthError(
            f"Huquq yo'q: {label(action)} "
            f"({auth.ROLE_LABEL.get(rol, rol or 'noma’lum')}).", 403)
    return daraja


def require_write(user: Dict[str, Any], action: str) -> Optional[str]:
    """`KOR` (faqat o'qish) ham RAD etiladigan tekshiruv.

    Kerak bo'ladi: admin biznes ma'lumotni ko'radi, lekin yozmaydi —
    ya'ni "ruxsat bor" bilan "o'zgartira oladi" bir xil emas."""
    daraja = require(user, action)
    if daraja == KOR:
        rol = (user or {}).get("role")
        raise auth.AuthError(
            f"Faqat ko'rish mumkin: {label(action)} "
            f"({auth.ROLE_LABEL.get(rol, rol or 'noma’lum')}).", 403)
    return daraja


def for_user(user: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Butun matritsaning SHU odam uchun kesimi — interfeys uchun.

    NEGA INTERFEYSGA BERILADI: aks holda ekran o'z ro'yxatini tutardi
    ("brokerga bu tugma ko'rinmasin") va u jadval bilan ajralib ketardi.
    Tugma bosilib 403 olish esa eng yomon variant: odam nima qilib
    bo'lmasligini FAQAT urinib ko'rgandan keyin bilardi.

    Bu HIMOYA EMAS — himoya serverda. Bu KO'RINISH qoidasi."""
    return {a: can(user, a) for a in AMALLAR}
