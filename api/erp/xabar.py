"""
BILDIRISHNOMA — hodimga, kompaniyaga emas.

    from api.erp import xabar
    xabar.yoz(user_id, "topshiriq", "Sizga yangi karta biriktirildi", opp_id)
    xabar.brokerga(broker_id, "topshiriq", matn, opp_id)
    xabar.menejerlarga("taqsimlanmagan", matn, opp_id)

MUAMMO: ERP da odamga qaratilgan xabar YO'Q edi. Bor narsa —
Tender-AI orqali yuboriladigan eslatma (`api/erp/remind.py`), lekin u
KOMPANIYA darajasida: bitta Telegram guruhi, bitta email ro'yxati.
"Sizga karta biriktirildi" degan gap esa ODAMGA tegishli.

Natijada yo'naltirish oqimi jim ishlardi: karta ochiladi, hodim esa
buni faqat ekranni ochganda ko'radi.

QAYERDA CHEGARA: bu modul FAQAT yozadi va o'qiydi. Kimga xabar
yuborish kerakligini HODISA egasi biladi (masalan
`api/erp/topshiriq.py`), shuning uchun qaror u yerda qoladi va bu
yerda faqat "kimga, nima va qaysi karta" saqlanadi.

XABAR YOZILMASA ISH TO'XTAMAYDI
═══════════════════════════════
`yoz()` hech qachon chaqiruvchini yiqitmaydi: karta ochilishi
xabardan MUHIMROQ. Xato jurnalga yoziladi va `None` qaytadi —
ya'ni yo'qolgani ham ko'rinadi, lekin oqim davom etadi.

HAVOLA: `localhost` YOZILMAYDI
══════════════════════════════
`ERP_WEB` mahalliy manzil bo'lsa havola umuman qo'yilmaydi. Boshqa
kompyuterda ochilmaydigan havola — buzuq havola, va "havola bor,
lekin ishlamaydi" eng yomon variant (`ommaviy_url` qoidasi bilan bir
xil, `erp_rollar.md` §8).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from api import db

log = logging.getLogger("erp.xabar")

#: Hodisa turlari. Interfeys shunga qarab nishon tanlaydi; ro'yxat
#: sinovda tekshiriladi (yangi tur qo'shilsa ekran ham bilsin).
TURLAR = {
    "topshiriq":      "Tender-AI'dan yangi karta",
    "taqsimlanmagan": "Karta taqsimlanmagan",
    "bekor":          "Tender-AI'da qaror bekor qilindi",
    "otkazildi":      "Karta sizga o'tkazildi",
    "muddat":         "Muddat yaqinlashdi",
    # Chat (25-patch). HAR XABARGA bildirishnoma YO'Q — o'qilmaganlar
    # hisoblagichi yetadi, aks holda kun bo'yi shovqin bo'lardi.
    # Faqat uchta hodisa: sizni qo'shishdi, sizni eslatishdi,
    # xabaringiz moderatsiyada o'chirildi.
    "chat_qoshildi":  "Chatga qo'shildingiz",
    "chat_mention":   "Chatda sizni eslatishdi",
    "chat_ochirildi": "Xabaringiz o'chirildi",
}

#: Mahalliy deb hisoblanadigan xostlar (havola yozilmaydi).
MAHALLIY = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = 'erp' AND table_name = 'notification'"))


def havola(opportunity_id: Optional[int] = None) -> Optional[str]:
    """Karta havolasi — FAQAT ommaviy manzil bo'lsa.

    `ERP_WEB` sozlanmagan yoki `localhost` bo'lsa `None`: xabarda
    ishlamaydigan havola bo'lgandan ko'ra havola bo'lmagani yaxshi."""
    base = (os.environ.get("ERP_WEB") or "").strip().rstrip("/")
    if not base:
        return None
    try:
        host = (urlparse(base).hostname or "").lower()
    except ValueError:
        return None
    if host in MAHALLIY:
        return None
    return f"{base}/?opportunity={opportunity_id}" if opportunity_id else base


YOZ_SQL = """
INSERT INTO erp.notification (app_user_id, kind, matn, opportunity_id, havola)
VALUES (%(u)s, %(k)s, %(m)s, %(o)s, %(h)s)
RETURNING id, app_user_id, kind, matn, opportunity_id, havola, created_at
"""


def yoz(app_user_id: Optional[int], kind: str, matn: str,
        opportunity_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Bitta xabar. Hech qachon chaqiruvchini yiqitmaydi."""
    if not app_user_id or not matn:
        return None
    try:
        if not schema_ready():
            return None
        return db.execute_returning(YOZ_SQL, {
            "u": app_user_id, "k": kind if kind in TURLAR else "topshiriq",
            "m": matn[:2000], "o": opportunity_id,
            "h": havola(opportunity_id)})
    except Exception:                           # noqa: BLE001
        # Xabar yozilmagani ISHNI to'xtatmaydi, lekin JIM ham
        # qolmaydi: jurnalda sabab qoladi.
        log.exception("bildirishnoma yozilmadi (user=%s kind=%s)",
                      app_user_id, kind)
        return None


def brokerga(broker_id: Optional[int], kind: str, matn: str,
             opportunity_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """HODIMGA (uning hisobiga) xabar.

    Hodim hisobsiz bo'lishi mumkin (omborchi, hujjatchi) — u holda
    xabar yozilmaydi va bu xato emas: u tizimga kirmaydi."""
    if not broker_id:
        return None
    uid = db.scalar("SELECT id FROM erp.app_user WHERE broker_id = %(b)s "
                    "AND active ORDER BY id LIMIT 1", {"b": broker_id})
    return yoz(uid, kind, matn, opportunity_id)


def menejerlarga(kind: str, matn: str,
                 opportunity_id: Optional[int] = None) -> int:
    """Kundalik ishning EGALARIGA: menejer, bo'lmasa rahbar.

    NEGA ADMINGA EMAS: administrator tizimni sozlaydi, ish
    taqsimlamaydi (`erp_rollar.md` §3.6). Menejer yo'q bo'lsa rahbar
    oladi — xabar egasiz qolmasin."""
    rollar = ["menejer"]
    if not db.query_one("SELECT 1 AS x FROM erp.app_user "
                        "WHERE role = 'menejer' AND active LIMIT 1"):
        rollar = ["rahbar"]
    n = 0
    for r in db.query("SELECT id FROM erp.app_user WHERE role = ANY(%(r)s) "
                      "AND active", {"r": rollar}):
        if yoz(r["id"], kind, matn, opportunity_id):
            n += 1
    return n


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------
ROYXAT_SQL = """
SELECT n.id, n.kind, n.matn, n.opportunity_id, n.havola, n.created_at,
       n.read_at, o.title AS opportunity_title
FROM erp.notification n
LEFT JOIN erp.opportunity o ON o.id = n.opportunity_id
WHERE n.app_user_id = %(u)s
  AND (%(faqat)s::bool IS NOT TRUE OR n.read_at IS NULL)
ORDER BY n.created_at DESC, n.id DESC
LIMIT %(l)s
"""


def _shape(r: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": r["id"], "kind": r["kind"],
            "kind_label": TURLAR.get(r["kind"], r["kind"]),
            "matn": r["matn"], "opportunity_id": r["opportunity_id"],
            "opportunity_title": r.get("opportunity_title"),
            "havola": r["havola"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "read_at": r["read_at"].isoformat() if r["read_at"] else None}


def royxat(app_user_id: int, faqat_oqilmagan: bool = False,
           limit: int = 50) -> Dict[str, Any]:
    """O'z xabarlari. HUQUQ TEKSHIRILMAYDI — bu o'zining ishi.

    (Boshqaning xabarini o'qish yo'li umuman yo'q: `app_user_id`
    sessiyadan keladi, so'rovdan emas.)"""
    if not schema_ready():
        return {"ready": False, "items": [], "unread": 0}
    rows = db.query(ROYXAT_SQL, {"u": app_user_id, "faqat": bool(faqat_oqilmagan),
                                 "l": max(1, min(limit, 200))})
    return {"ready": True, "items": [_shape(r) for r in rows],
            "unread": sanoq(app_user_id)}


def sanoq(app_user_id: int) -> int:
    """O'qilmaganlar soni — ekrandagi hisoblagich."""
    if not schema_ready():
        return 0
    return db.scalar("SELECT count(*) FROM erp.notification "
                     "WHERE app_user_id = %(u)s AND read_at IS NULL",
                     {"u": app_user_id}) or 0


def oqildi(app_user_id: int, ids: Optional[List[int]] = None) -> int:
    """Belgilangan (yoki hammasi) xabarni o'qilgan deb belgilaydi.

    Faqat O'ZINIKI: `app_user_id` shartda ham bor, ya'ni begona id
    yuborilsa hech narsa o'zgarmaydi."""
    if not schema_ready():
        return 0
    # `db.query()` FAQAT O'QISH uchun: u tranzaksiyani `rollback`
    # qiladi va yozuv YO'QOLARDI. Yozish `execute_returning` dan
    # o'tishi SHART, u esa BITTA qator qaytaradi — shuning uchun
    # sanoq CTE ichida hisoblanadi.
    shart = ("AND id = ANY(%(i)s) " if ids else "")
    r = db.execute_returning(
        "WITH x AS (UPDATE erp.notification SET read_at = now() "
        f"WHERE app_user_id = %(u)s {shart}AND read_at IS NULL "
        "RETURNING id) SELECT count(*) AS n FROM x",
        {"u": app_user_id, "i": list(ids or [])})
    return int((r or {}).get("n") or 0)
