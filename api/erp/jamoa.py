"""
KARTA JAMOASI — bitta tenderda bir nechta hodim.

    from api.erp import jamoa
    jamoa.royxat(opp_id)                      # asosiy + qolganlari
    jamoa.qosh(opp_id, broker_id, "narx", kim_user_id, kim_ismi)
    jamoa.asosiy_qil(opp_id, broker_id, ...)  # mas'ulni almashtirish
    jamoa.chiqar(opp_id, broker_id, ...)

MUAMMO: kartada YAKKA mas'ul bor edi (`opportunity.broker_id`). Amalda
esa bitta tenderda uch odam ishlaydi — narxni biri hisoblaydi, hujjatni
ikkinchisi yig'adi, texnik qismni uchinchisi yozadi. Ular kartani
KO'RA OLMASDI ham: egalik zanjiri (`api/erp/egalik.py`) `broker_id` ga
tayanadi. Ya'ni ishlash uchun mas'ulning hisobidan kirish kerak
bo'lardi — bu esa auditning oxiri: har o'zgarish bitta odam nomidan
yozilardi.

ASOSIY MAS'UL QAYERDA
═════════════════════
`erp.opportunity.broker_id` da QOLADI. Bu jadval faqat QOLGAN a'zolarni
saqlaydi (`schema_patch_erp_28.sql` sarlavhasidagi sabab):

  * bitta ustun = "ko'pi bilan bitta asosiy" invarianti tuzilma
    darajasida — qisman noyob indeks bilan qo'riqlanadigan `asosiy`
    bayrog'i kerak emas;
  * yigirmaga yaqin joy `broker_id` ga tayanadi va ular tegilmadi.

Shuning uchun `royxat()` IKKI manbadan yig'adi va bu takrorlanish
emas: ular BOSHQA-BOSHQA faktni saqlaydi.

JAMOA — HUQUQ HAM
═════════════════
A'zolik uchta narsani ochadi va ular BIR JOYDAN kelib chiqadi:
  1. kartani ko'rish/tahrirlash (`egalik.py` zanjiri kengaytirildi);
  2. karta chatiga kirish (`chat_member` ga qo'shiladi);
  3. karta vazifalarini olish (`tasks.royxat` egalik filtri).

Ya'ni "jamoaga qo'shish" — yagona amal, uchta joyda alohida sozlash
emas. Aks holda biri unutilardi va odam kartani ko'rib, chatini
ko'rmasdi.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError, _iso, _need_schema

log = logging.getLogger("erp.jamoa")

#: MAS'ULIYAT ROLLARI. Ro'yxat KODDA va QISQA (§12): o'ntadan ortiq rol
#: kiritilsa, ular tanlanmay qolardi va hamma "kuzatuvchi" ni bosardi.
#:
#: `masul` bu yerda YO'Q — asosiy mas'ul jadvalda emas, kartada
#: (`opportunity.broker_id`). U `royxat()` da hosil qilinadi.
ROLLAR = {
    "narx":       "Narx va hisob-kitob",
    "hujjat":     "Hujjatlar",
    "texnik":     "Texnik qism",
    "yuridik":    "Yuridik",
    "kuzatuvchi": "Kuzatuvchi",
}

#: Asosiy mas'ulning roli — hosil qilinadi, saqlanmaydi.
ASOSIY_ROL = "masul"
ASOSIY_LABEL = "Mas'ul"


def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = 'erp' AND table_name = 'opportunity_assignee'"))


def _need_schema28() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Jamoa jadvali yo'q: schema_patch_erp_28.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
AZOLAR_SQL = """
SELECT a.id, a.broker_id, a.rol, a.izoh, a.added_at, a.removed_at,
       b.full_name, b.active, b.email, b.phone,
       ab.full_name AS added_by_name,
       u.id AS app_user_id
FROM erp.opportunity_assignee a
JOIN erp.broker b ON b.id = a.broker_id
LEFT JOIN erp.app_user ab ON ab.id = a.added_by
LEFT JOIN erp.app_user u  ON u.broker_id = a.broker_id AND u.active
WHERE a.opportunity_id = %(opp)s
  AND (%(tarix)s::bool IS TRUE OR a.removed_at IS NULL)
ORDER BY a.removed_at NULLS FIRST, a.added_at, a.id
"""

ASOSIY_SQL = """
SELECT o.id, o.broker_id, o.title, o.status,
       b.full_name, b.active, b.email, b.phone,
       u.id AS app_user_id
FROM erp.opportunity o
LEFT JOIN erp.broker b   ON b.id = o.broker_id
LEFT JOIN erp.app_user u ON u.broker_id = o.broker_id AND u.active
WHERE o.id = %(opp)s
"""

FAOL_AZO_SQL = """
SELECT id, rol FROM erp.opportunity_assignee
WHERE opportunity_id = %(opp)s AND broker_id = %(b)s AND removed_at IS NULL
"""

QOSH_SQL = """
INSERT INTO erp.opportunity_assignee
    (opportunity_id, broker_id, rol, izoh, added_by)
VALUES (%(opp)s, %(b)s, %(rol)s, %(izoh)s, %(kim)s)
RETURNING id
"""

# QAYTA QO'SHISH — YANGI QATOR, eskisini tiriltirish emas.
#
# Sabab: "qachon jamoada edi" degan savolga javob har davr uchun
# alohida bo'lishi kerak. Eski qatorni tiriltirsak, chiqarilgan va
# qayta qo'shilgan davrlar bitta qatorga qo'shilib ketardi va
# oradagi tanaffus izsiz yo'qolardi.
ROL_SQL = """
UPDATE erp.opportunity_assignee SET rol = %(rol)s, izoh = %(izoh)s
WHERE id = %(id)s RETURNING id, rol
"""

CHIQAR_SQL = """
UPDATE erp.opportunity_assignee
SET removed_at = now(), removed_by = %(kim)s
WHERE opportunity_id = %(opp)s AND broker_id = %(b)s AND removed_at IS NULL
RETURNING id
"""

OPP_BROKER_SQL = ("UPDATE erp.opportunity SET broker_id = %(b)s "
                  "WHERE id = %(id)s RETURNING id, broker_id")


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------
def _shape(r: Dict[str, Any], asosiy: bool = False) -> Dict[str, Any]:
    rol = ASOSIY_ROL if asosiy else r.get("rol")
    return {
        "broker_id": r["broker_id"], "full_name": r["full_name"],
        "active": r["active"],
        "app_user_id": r.get("app_user_id"),
        "rol": rol,
        "rol_label": ASOSIY_LABEL if asosiy else ROLLAR.get(rol, rol),
        "asosiy": asosiy,
        "izoh": None if asosiy else r.get("izoh"),
        "added_at": None if asosiy else _iso(r.get("added_at")),
        "added_by_name": None if asosiy else r.get("added_by_name"),
        "removed_at": None if asosiy else _iso(r.get("removed_at")),
    }


def royxat(opp_id: int, tarix: bool = False) -> Dict[str, Any]:
    """Kartaning jamoasi: ASOSIY + qolganlari.

    `tarix=True` — chiqarilganlar ham (kim qachon jamoada edi).

    Asosiy mas'ul BIRINCHI va u har doim alohida belgilangan
    (`asosiy: true`): ekranda "Mas'ul: Karimov" bilan "Jamoa: ..."
    ni ajratish kerak, aks holda kim javobgar ekani yo'qolardi."""
    _need_schema28()
    o = db.query_one(ASOSIY_SQL, {"opp": opp_id})
    if not o:
        raise ErpError("Karta topilmadi.", 404)
    azolar: List[Dict[str, Any]] = []
    if o["broker_id"]:
        azolar.append(_shape(o, asosiy=True))
    for r in db.query(AZOLAR_SQL, {"opp": opp_id, "tarix": bool(tarix)}):
        # ASOSIY MAS'ULNING jamoa qatori TASHLANADI — u yuqorida
        # allaqachon qo'shilgan.
        #
        # NEGA KERAK: `asosiy_qil()` bunday qatorni o'zi olib
        # tashlaydi, lekin mas'ul BOSHQA yo'l bilan ham o'zgaradi —
        # `PUT /erp/opportunities/{id}` `broker_id` ni to'g'ridan-
        # to'g'ri yozadi (kartani tahrirlash formasi). U holda
        # jamoada bo'lgan odam mas'ul qilinsa, ro'yxatda IKKI
        # MARTA ko'rinardi: bir marta "Mas'ul", bir marta "Narx".
        #
        # Tekshiruv SHU YERDA, chunki bu ko'rinishning invarianti:
        # qaysi yo'l bilan kelishidan qat'i nazar, bir odam
        # ro'yxatda BIR marta turishi kerak. Yozish tomonida
        # qo'yilsa, har yangi yo'lda u qaytadan unutilardi.
        if r["broker_id"] == o["broker_id"] and not r["removed_at"]:
            continue
        azolar.append(_shape(r))
    return {
        "opportunity_id": opp_id,
        "asosiy_broker_id": o["broker_id"],
        "azolar": azolar,
        # Faol a'zolar soni — kanban kartasi uchun ("Karimov +2").
        "soni": len([a for a in azolar if not a["removed_at"]]),
        "rollar": [{"kod": k, "label": v} for k, v in ROLLAR.items()],
    }


def azomi(opp_id: int, broker_id: Optional[int]) -> bool:
    """Shu hodim shu kartada ishlayaptimi (asosiy YOKI jamoada).

    `egalik.py` va `chat.py` shu savolni beradi. Javob BITTA joyda
    bo'lishi kerak, aks holda ular ajralib ketardi: odam kartani
    ko'rib, chatini ko'rmasdi."""
    if not broker_id:
        return False
    return bool(db.scalar(
        "SELECT EXISTS (SELECT 1 FROM erp.opportunity o "
        "                WHERE o.id = %(opp)s AND o.broker_id = %(b)s) "
        "    OR EXISTS (SELECT 1 FROM erp.opportunity_assignee a "
        "                WHERE a.opportunity_id = %(opp)s "
        "                  AND a.broker_id = %(b)s "
        "                  AND a.removed_at IS NULL) AS ok",
        {"opp": opp_id, "b": broker_id}))


# ---------------------------------------------------------------------------
# O'zgartirish
# ---------------------------------------------------------------------------
def _karta(opp_id: int) -> Dict[str, Any]:
    o = db.query_one("SELECT id, title, broker_id, status FROM erp.opportunity "
                     "WHERE id = %(id)s", {"id": opp_id})
    if not o:
        raise ErpError("Karta topilmadi.", 404)
    return o


def _hodim(broker_id: int) -> Dict[str, Any]:
    b = db.query_one("SELECT id, full_name, active FROM erp.broker "
                     "WHERE id = %(b)s", {"b": broker_id})
    if not b:
        raise ErpError("Hodim topilmadi.", 404)
    if not b["active"]:
        raise ErpError("Faolsizlantirilgan hodim jamoaga qo'shilmaydi.")
    return b


def qosh(opp_id: int, broker_id: int, rol: str,
         kim_user_id: Optional[int] = None,
         kim_ismi: Optional[str] = None,
         izoh: Optional[str] = None) -> Dict[str, Any]:
    """Jamoaga hodim qo'shish.

    Uchta natija BIRGA (moduldagi izohga qarang): karta ko'rinadi,
    chat ochiladi, bildirishnoma ketadi."""
    _need_schema28()
    o = _karta(opp_id)
    b = _hodim(broker_id)
    if rol not in ROLLAR:
        raise ErpError(f"Noma'lum rol: {rol}. Mumkin: "
                       + ", ".join(ROLLAR))
    if o["broker_id"] == broker_id:
        # ASOSIY MAS'ULNI jamoaga qo'shib bo'lmaydi: u allaqachon
        # jamoada va ikkinchi qator uni ro'yxatda IKKI marta
        # ko'rsatardi.
        raise ErpError(f"{b['full_name']} — kartaning asosiy mas'uli, "
                       "u allaqachon jamoada.", 409)
    if db.query_one(FAOL_AZO_SQL, {"opp": opp_id, "b": broker_id}):
        raise ErpError(f"{b['full_name']} allaqachon jamoada.", 409)

    db.execute_returning(QOSH_SQL, {
        "opp": opp_id, "b": broker_id, "rol": rol,
        "izoh": (izoh or "").strip() or None, "kim": kim_user_id},
        actor=kim_ismi)
    _chatga_qosh(opp_id, broker_id, kim_user_id)
    _tarixga(opp_id, o["status"], kim_ismi,
             f"Jamoaga qo'shildi: {b['full_name']} — {ROLLAR[rol]}")
    _xabar(opp_id, broker_id, o,
           f"Sizni tender jamoasiga qo'shishdi: {o['title'] or f'#{opp_id}'} "
           f"({ROLLAR[rol]}).", "jamoa_qoshildi", kim_user_id)
    return royxat(opp_id)


def rol_ozgart(opp_id: int, broker_id: int, rol: str,
               kim_user_id: Optional[int] = None,
               kim_ismi: Optional[str] = None,
               izoh: Optional[str] = None) -> Dict[str, Any]:
    """Mas'uliyatni almashtirish (narx -> hujjat va h.k.)."""
    _need_schema28()
    o = _karta(opp_id)
    b = _hodim(broker_id)
    if rol not in ROLLAR:
        raise ErpError(f"Noma'lum rol: {rol}")
    cur = db.query_one(FAOL_AZO_SQL, {"opp": opp_id, "b": broker_id})
    if not cur:
        raise ErpError(f"{b['full_name']} bu kartaning jamoasida emas.", 404)
    if cur["rol"] == rol and not izoh:
        return royxat(opp_id)
    eski = ROLLAR.get(cur["rol"], cur["rol"])
    db.execute_returning(ROL_SQL, {
        "id": cur["id"], "rol": rol,
        "izoh": (izoh or "").strip() or None}, actor=kim_ismi)
    _tarixga(opp_id, o["status"], kim_ismi,
             f"Jamoa roli o'zgardi: {b['full_name']}: {eski} -> {ROLLAR[rol]}")
    _xabar(opp_id, broker_id, o,
           f"Tenderdagi mas'uliyatingiz o'zgardi: "
           f"{o['title'] or f'#{opp_id}'} — {ROLLAR[rol]}.",
           "jamoa_rol", kim_user_id)
    return royxat(opp_id)


def chiqar(opp_id: int, broker_id: int,
           kim_user_id: Optional[int] = None,
           kim_ismi: Optional[str] = None) -> Dict[str, Any]:
    """Jamoadan chiqarish — YUMSHOQ (§26).

    ASOSIY MAS'ULNI bu yo'l bilan chiqarib bo'lmaydi: avval boshqa
    odam mas'ul qilinadi (`asosiy_qil`), aks holda karta egasiz
    qolardi va uni hech kim ko'rmasdi.

    CHATDAN HAM chiqariladi: odam jamoada emas ekan, yozishmani
    o'qishda davom etishi maxfiylik teshigi bo'lardi. YOZGANLARI
    esa lentada QOLADI (chat moduli qoidasi)."""
    _need_schema28()
    o = _karta(opp_id)
    b = db.query_one("SELECT id, full_name FROM erp.broker WHERE id = %(b)s",
                     {"b": broker_id}) or {"full_name": "hodim"}
    if o["broker_id"] == broker_id:
        raise ErpError(
            "Kartaning asosiy mas'ulini jamoadan chiqarib bo'lmaydi — "
            "avval boshqa hodimni mas'ul qiling.")
    if not db.execute_returning(CHIQAR_SQL, {
            "opp": opp_id, "b": broker_id, "kim": kim_user_id},
            actor=kim_ismi):
        raise ErpError(f"{b['full_name']} bu kartaning jamoasida emas.", 404)
    _chatdan_chiqar(opp_id, broker_id, kim_user_id)
    _tarixga(opp_id, o["status"], kim_ismi,
             f"Jamoadan chiqarildi: {b['full_name']}")
    _xabar(opp_id, broker_id, o,
           f"Sizni tender jamoasidan chiqarishdi: "
           f"{o['title'] or f'#{opp_id}'}.",
           "jamoa_chiqarildi", kim_user_id)
    return royxat(opp_id)


def asosiy_qil(opp_id: int, broker_id: int,
               kim_user_id: Optional[int] = None,
               kim_ismi: Optional[str] = None) -> Dict[str, Any]:
    """ASOSIY MAS'ULNI almashtirish.

    ESKI MAS'UL JAMOADA QOLADI (`kuzatuvchi` bo'lib): u karta ustida
    ishlagan va konteksti kerak bo'lishi mumkin. Uni butunlay
    chiqarish — ALOHIDA, ONGLI amal (`chiqar`), avtomatik emas. Bu
    chat moduli bilan bir xil qoida (`_chat_masul_almashdi`).

    Yangi mas'ul jamoa qatoridan CHIQARILADI: u endi asosiy va
    ikkita qator uni ro'yxatda ikki marta ko'rsatardi."""
    _need_schema28()
    o = _karta(opp_id)
    b = _hodim(broker_id)
    if o["broker_id"] == broker_id:
        return royxat(opp_id)
    eski = o["broker_id"]

    db.execute_returning(OPP_BROKER_SQL, {"id": opp_id, "b": broker_id},
                         actor=kim_ismi)
    # Yangisi jamoa ro'yxatidan chiqadi (endi u asosiy).
    db.execute_returning(CHIQAR_SQL, {"opp": opp_id, "b": broker_id,
                                      "kim": kim_user_id}, actor=kim_ismi)
    if eski:
        # Eskisi jamoada qoladi — yuqoridagi izoh.
        if not db.query_one(FAOL_AZO_SQL, {"opp": opp_id, "b": eski}):
            db.execute_returning(QOSH_SQL, {
                "opp": opp_id, "b": eski, "rol": "kuzatuvchi",
                "izoh": "Avvalgi mas'ul", "kim": kim_user_id},
                actor=kim_ismi)
    _chatga_qosh(opp_id, broker_id, kim_user_id)
    eski_nom = db.scalar("SELECT full_name FROM erp.broker WHERE id = %(b)s",
                         {"b": eski}) if eski else None
    _tarixga(opp_id, o["status"], kim_ismi,
             f"Asosiy mas'ul o'zgardi: {eski_nom or '—'} -> {b['full_name']}")
    # Bildirishnoma — MAVJUD hodisa orqali: "karta o'tkazildi" allaqachon
    # bor va u eskisiga ham, yangisiga ham xabar beradi.
    try:
        from api.erp import hodisa
        hodisa.karta_otkazildi(broker_id, eski, opp_id, o["title"],
                               chiqaruvchi=kim_user_id)
    except Exception:                               # noqa: BLE001
        log.exception("mas'ul almashish xabari yozilmadi (karta %s)", opp_id)
    return royxat(opp_id)


# ---------------------------------------------------------------------------
# Yon ta'sirlar — hech biri asosiy amalni YIQITMAYDI
# ---------------------------------------------------------------------------
def _chatga_qosh(opp_id: int, broker_id: int,
                 kim_user_id: Optional[int]) -> None:
    """Jamoa a'zosi karta chatiga qo'shiladi.

    Aks holda unga ish berilardi-yu, u haqidagi butun yozishma
    ko'rinmasdi — eng kerakli paytda, ishni qabul qilib olayotganda."""
    try:
        from api.erp import chat as _chat
        chat_id = _chat.karta_chati(opp_id)
        if not chat_id:
            return
        u = db.query_one("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                         "AND active ORDER BY id LIMIT 1", {"b": broker_id})
        if not u:
            return                      # hisobsiz hodim — normal holat
        if db.query_one(_chat.AZOMI_SQL, {"chat": chat_id, "uid": u["id"]}):
            return
        _chat.azo_qosh(chat_id, kim_user_id or u["id"], u["id"])
    except Exception:                               # noqa: BLE001
        log.exception("jamoa a'zosi chatga qo'shilmadi (karta %s)", opp_id)


def _chatdan_chiqar(opp_id: int, broker_id: int,
                    kim_user_id: Optional[int]) -> None:
    """Jamoadan chiqarilgan odam chatdan ham chiqadi."""
    try:
        from api.erp import chat as _chat
        chat_id = _chat.karta_chati(opp_id)
        if not chat_id:
            return
        u = db.query_one("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                         "AND active ORDER BY id LIMIT 1", {"b": broker_id})
        if not u or not db.query_one(_chat.AZOMI_SQL,
                                     {"chat": chat_id, "uid": u["id"]}):
            return
        _chat.azo_chiqar(chat_id, kim_user_id or u["id"], u["id"])
    except ErpError:
        # Kartaning mas'ulini chatdan chiqarib bo'lmaydi — bu yerga
        # yetib kelmasligi kerak (yuqorida tekshirilgan), lekin
        # yetib kelsa ham jamoadan chiqarish BEKOR BO'LMAYDI.
        log.info("chatdan chiqarilmadi (karta %s, hodim %s)", opp_id, broker_id)
    except Exception:                               # noqa: BLE001
        log.exception("jamoa a'zosi chatdan chiqarilmadi (karta %s)", opp_id)


def _tarixga(opp_id: int, status: str, kim: Optional[str],
             matn: str) -> None:
    """Karta tarixiga yozuv.

    MAVJUD jadval (`erp.opportunity_history`) ishlatiladi — u aynan
    "kartada nima bo'ldi" degan savolga javob beradi va ekranda
    allaqachon ko'rsatiladi. Status o'zgarmagani uchun `from` va `to`
    bir xil: bu naqsh "qayta taqsimlash so'rovi" da ham ishlatiladi
    (`opportunity.taqsimlash_sorovi`).

    Chat lentasiga ham yoziladi: jamoa o'zgarishi yozishmani
    o'qiyotgan odamga ham ko'rinishi kerak."""
    try:
        from api.erp.opportunity import HISTORY_INSERT_SQL
        db.execute_returning(HISTORY_INSERT_SQL, {
            "opportunity_id": opp_id, "from_status": status,
            "to_status": status, "changed_by": kim, "note": matn})
        from api.erp import chat as _chat
        _chat.tizim_xabari(_chat.karta_chati(opp_id), matn)
    except Exception:                               # noqa: BLE001
        log.exception("jamoa o'zgarishi tarixga yozilmadi (karta %s)", opp_id)


def _xabar(opp_id: int, broker_id: int, o: Dict[str, Any], matn: str,
           kind: str, kim_user_id: Optional[int]) -> None:
    """Bildirishnoma — MAVJUD quvur orqali (`api/erp/hodisa.py`).

    To'g'ridan-to'g'ri `xabar.yoz()` chaqirilmaydi: qabul qiluvchini
    va kanalni hal qilish o'sha modulning ishi (27-patch qoidasi)."""
    try:
        from api.erp import hodisa
        hodisa.chiqar(kind, matn, broker_id=broker_id,
                      opportunity_id=opp_id, chiqaruvchi=kim_user_id)
    except Exception:                               # noqa: BLE001
        log.exception("jamoa bildirishnomasi yozilmadi (karta %s)", opp_id)
