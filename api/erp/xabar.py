"""
BILDIRISHNOMA — SAQLASH va O'QISH qatlami.

    from api.erp import xabar
    xabar.yoz(user_id, "topshiriq", "Sizga yangi karta biriktirildi",
              opportunity_id=12)
    xabar.royxat(user_id)            # "menga nima keldi"
    xabar.oqildi(user_id, [3, 4])    # o'qilgan deb belgilash

QAYERDA CHEGARA. Bu modul BITTA savolga javob beradi: "shu odamga shu
xabar qanday saqlanadi va qaytariladi". "KIMGA yuborish kerak" degan
savol bu yerda YO'Q — u biznes munosabatidan chiqadi va
`api/erp/hodisa.py` da (hodisa reyestri). Ilgari ikkalasi shu faylda
edi va natijada har modul o'zicha qabul qiluvchi tanlardi.

    hodisa.py   — NIMA bo'ldi, KIMGA tegishli, qaysi KANAL
    xabar.py    — qanday SAQLANADI va O'QILADI   <- shu fayl
    navbat.py   — tashqi kanalga qanday YETKAZILADI

XABAR YOZILMASA ISH TO'XTAMAYDI
═══════════════════════════════
`yoz()` hech qachon chaqiruvchini yiqitmaydi: karta ochilishi yoki chat
xabari yozilishi bildirishnomadan MUHIMROQ. Xato jurnalga yoziladi va
`None` qaytadi — ya'ni yo'qolgani ham ko'rinadi, lekin oqim davom etadi.

BILDIRISHNOMA VA NAVBAT — BITTA TRANZAKSIYA
═══════════════════════════════════════════
Qator yozilib, yetkazish navbati (`erp.notification_delivery`)
yozilmasa, u hech qachon yuborilmasdi va buni HECH NARSA
ko'rsatmasdi: jadvalda "bor" bo'lib turardi. Shuning uchun ikkalasi
`db.tx()` ichida (`schema_patch_erp_27.sql` §2).

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
#:
#: MA'NOSI shu yerda, QABUL QILUVCHISI `api/erp/hodisa.py` da: bu
#: jadval "xabar qanday ko'rinadi" ni biladi, "kimga boradi" ni emas.
TURLAR = {
    "topshiriq":      "Tender-AI'dan yangi karta",
    "taqsimlanmagan": "Karta taqsimlanmagan",
    "bekor":          "Tender-AI'da qaror bekor qilindi",
    "otkazildi":      "Karta sizga o'tkazildi",
    "muddat":         "Muddat yaqinlashdi",
    # Chat (25-patch). HAR XABARGA alohida bildirishnoma YO'Q — ular
    # BITTA qatorga yig'iladi (`hodisa.chat_xabar`), aks holda kun
    # bo'yi shovqin bo'lardi.
    "chat_qoshildi":  "Chatga qo'shildingiz",
    "chat_mention":   "Chatda sizni eslatishdi",
    "chat_ochirildi": "Xabaringiz o'chirildi",
    "chat_yangi":     "Yangi xabar",
    # 27-patch: ish oqimining qolgan hodisalari.
    "status":         "Karta holati o'zgardi",
    "vazifa":         "Sizga vazifa biriktirildi",
    "biriktirish_olib_tashlandi": "Karta sizdan olindi",
    "hujjat_muddat":  "Hujjat muddati tugayapti",
    "qaror":          "Qaror kerak",
    "tizim":          "Tizim xatosi — aralashuv kerak",
}

#: Mahalliy deb hisoblanadigan xostlar (havola yozilmaydi).
MAHALLIY = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}

#: Bildirishnomaning ILOVA ichidagi kanali. U jadvalning O'ZI — ya'ni
#: qator yozilgani "yetkazildi" degani, shuning uchun navbatda darhol
#: `sent` bo'ladi. Tashqi kanallar `api/erp/navbat.py` da.
KANAL_ILOVA = "inapp"


def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = 'erp' AND table_name = 'notification'"))


_SCHEMA27: Optional[bool] = None


def schema27_ready() -> bool:
    """27-patch (nishon, dedup, navbat) qo'llanganmi.

    Qo'llanmagan bo'lsa modul ESKI shaklda ishlaydi: bildirishnoma
    yoziladi, navbat va dedup ishlamaydi. Bu ataylab — yarim
    yangilangan o'rnatmada xabar YO'QOLMASLIGI kerak."""
    global _SCHEMA27
    if _SCHEMA27 is None:
        _SCHEMA27 = bool(db.query_one(
            "SELECT 1 AS x FROM information_schema.columns "
            "WHERE table_schema = 'erp' AND table_name = 'notification' "
            "AND column_name = 'dedup_key'"))
    return _SCHEMA27


def havola(opportunity_id: Optional[int] = None,
           chat_id: Optional[int] = None) -> Optional[str]:
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
    if opportunity_id:
        return f"{base}/?opportunity={opportunity_id}"
    if chat_id:
        return f"{base}/?chat={chat_id}"
    return base


# ---------------------------------------------------------------------------
# Yozish
# ---------------------------------------------------------------------------
YOZ_SQL = """
INSERT INTO erp.notification
    (app_user_id, kind, matn, opportunity_id, chat_id, task_id,
     havola, dedup_key, updated_at)
VALUES (%(u)s, %(k)s, %(m)s, %(o)s, %(c)s, %(t)s, %(h)s, %(d)s, now())
RETURNING id, app_user_id, kind, matn, opportunity_id, chat_id, task_id,
          havola, created_at
"""

#: Dedup kaliti bor va qator ALLAQACHON bo'lsa — YANGISI yozilmaydi,
#: MAVJUDI ko'tariladi: matn yangilanadi, `read_at` tozalanadi va
#: `updated_at` suriladi.
#:
#: NEGA `read_at` TOZALANADI: "chatda 3 ta yangi xabar" bildirishnomasi
#: o'qilgandan keyin to'rtinchi xabar kelsa, u YANGI hodisa. Tozalamasak
#: hisoblagich jim qolardi va odam yangi xabarni ko'rmasdi.
YOZ_DEDUP_SQL = """
INSERT INTO erp.notification
    (app_user_id, kind, matn, opportunity_id, chat_id, task_id,
     havola, dedup_key, updated_at)
VALUES (%(u)s, %(k)s, %(m)s, %(o)s, %(c)s, %(t)s, %(h)s, %(d)s, now())
ON CONFLICT (dedup_key) WHERE dedup_key IS NOT NULL DO UPDATE
    SET matn = CASE WHEN %(kotar)s THEN EXCLUDED.matn
                    ELSE erp.notification.matn END,
        read_at = CASE WHEN %(kotar)s THEN NULL
                       ELSE erp.notification.read_at END,
        updated_at = now()
RETURNING id, app_user_id, kind, matn, opportunity_id, chat_id, task_id,
          havola, created_at,
          (xmax <> 0) AS mavjud_edi
"""

NAVBAT_SQL = """
INSERT INTO erp.notification_delivery
    (notification_id, kanal, holat, urinish, sent_at)
VALUES (%(n)s, %(kanal)s, %(holat)s, %(urinish)s, %(sent)s)
ON CONFLICT (notification_id, kanal) DO NOTHING
RETURNING id
"""


def yoz(app_user_id: Optional[int], kind: str, matn: str,
        opportunity_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        task_id: Optional[int] = None,
        dedup_key: Optional[str] = None,
        kotar: bool = True,
        tashqi_kanallar: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Bitta bildirishnoma + uning yetkazish navbati. BITTA tranzaksiya.

    `dedup_key` — berilsa, shu kalitli qator IKKINCHI MARTA
    yozilmaydi (§17). `kotar=True` bo'lsa mavjud qator ko'tariladi
    (matn yangilanadi, o'qilgan belgisi olinadi) — yig'ma xabar uchun;
    `kotar=False` — takror butunlay e'tiborsiz qoldiriladi.

    `tashqi_kanallar` — ilovadan TASHQARI kanallar navbatga qo'yiladi.
    Ular KOMPANIYA darajasida ishlaydi (`api/erp/navbat.py` ga qarang),
    shuning uchun ularni chaqiruvchi hodisaga BIR MARTA beradi.

    HECH QACHON CHAQIRUVCHINI YIQITMAYDI."""
    if not app_user_id or not matn:
        return None
    try:
        if not schema_ready():
            return None
        k = kind if kind in TURLAR else "topshiriq"
        p = {"u": app_user_id, "k": k, "m": matn[:2000],
             "o": opportunity_id, "c": chat_id, "t": task_id,
             "h": havola(opportunity_id, chat_id), "d": dedup_key}
        if not schema27_ready():
            # 27-patch yo'q: eski shakl. Nishon va navbat yo'q, lekin
            # xabar YO'QOLMAYDI.
            return db.execute_returning(
                "INSERT INTO erp.notification "
                "(app_user_id, kind, matn, opportunity_id, havola) "
                "VALUES (%(u)s, %(k)s, %(m)s, %(o)s, %(h)s) "
                "RETURNING id, app_user_id, kind, matn, opportunity_id, "
                "havola, created_at", p)
        with db.tx() as t:
            if dedup_key:
                row = t.one(YOZ_DEDUP_SQL, {**p, "kotar": bool(kotar)})
                if row and row.get("mavjud_edi") and not kotar:
                    # Takror: yangi navbat qatori ham QO'YILMAYDI, aks
                    # holda bir xil xabar ikki marta yuborilardi (§17).
                    return None
            else:
                row = t.one(YOZ_SQL, p)
            if not row:
                return None
            # ILOVA kanali — jadvalning O'ZI, ya'ni yetkazildi.
            t.one(NAVBAT_SQL, {"n": row["id"], "kanal": KANAL_ILOVA,
                               "holat": "sent", "urinish": 1,
                               "sent": None})
            for kanal in (tashqi_kanallar or []):
                t.one(NAVBAT_SQL, {"n": row["id"], "kanal": kanal,
                                   "holat": "pending", "urinish": 0,
                                   "sent": None})
        return row
    except Exception:                           # noqa: BLE001
        # Xabar yozilmagani ISHNI to'xtatmaydi, lekin JIM ham
        # qolmaydi: jurnalda sabab qoladi.
        log.exception("bildirishnoma yozilmadi (user=%s kind=%s)",
                      app_user_id, kind)
        return None


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------
ROYXAT_SQL = """
SELECT n.id, n.kind, n.matn, n.opportunity_id, n.chat_id, n.task_id,
       n.havola, n.created_at, n.read_at, o.title AS opportunity_title,
       c.turi AS chat_turi, c.title AS chat_title,
       coalesce(n.updated_at, n.created_at) AS tartib_at
FROM erp.notification n
LEFT JOIN erp.opportunity o ON o.id = n.opportunity_id
LEFT JOIN erp.chat c        ON c.id = n.chat_id
WHERE n.app_user_id = %(u)s
  AND (%(faqat)s::bool IS NOT TRUE OR n.read_at IS NULL)
  -- SAHIFALASH: oldingi sahifadan KEYINGILARI. `id` bo'yicha, chunki
  -- vaqt bo'yicha sahifalashda bir vaqtda yozilgan ikki qator
  -- chegarada takrorlanardi yoki tushib qolardi.
  AND (%(before_id)s::int IS NULL OR n.id < %(before_id)s)
ORDER BY coalesce(n.updated_at, n.created_at) DESC, n.id DESC
LIMIT %(l)s
"""

#: 27-patchgacha bo'lgan shakl (nishon ustunlari yo'q).
ROYXAT_ESKI_SQL = """
SELECT n.id, n.kind, n.matn, n.opportunity_id,
       NULL::int AS chat_id, NULL::int AS task_id,
       n.havola, n.created_at, n.read_at, o.title AS opportunity_title,
       NULL::text AS chat_turi, NULL::text AS chat_title,
       n.created_at AS tartib_at
FROM erp.notification n
LEFT JOIN erp.opportunity o ON o.id = n.opportunity_id
WHERE n.app_user_id = %(u)s
  AND (%(faqat)s::bool IS NOT TRUE OR n.read_at IS NULL)
  AND (%(before_id)s::int IS NULL OR n.id < %(before_id)s)
ORDER BY n.created_at DESC, n.id DESC
LIMIT %(l)s
"""


def _nishon(r: Dict[str, Any]) -> Dict[str, Any]:
    """KLIK MANZILI — interfeys shuni ochadi.

    UMUMIY PANELGA HECH QACHON OLIB BORMAYDI (§15): aniq kontekst
    bor bo'lsa, odam uni qaytadan qidirmasligi kerak. Tartib muhim —
    chat bildirishnomasi kartaga emas, CHATga olib boradi."""
    if r.get("chat_id"):
        return {"turi": "chat", "id": r["chat_id"],
                "opportunity_id": r.get("opportunity_id")}
    if r.get("task_id"):
        return {"turi": "task", "id": r["task_id"],
                "opportunity_id": r.get("opportunity_id")}
    if r.get("opportunity_id"):
        return {"turi": "opportunity", "id": r["opportunity_id"],
                "opportunity_id": r["opportunity_id"]}
    return {"turi": None, "id": None, "opportunity_id": None}


def _shape(r: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": r["id"], "kind": r["kind"],
            "kind_label": TURLAR.get(r["kind"], r["kind"]),
            "matn": r["matn"], "opportunity_id": r["opportunity_id"],
            "opportunity_title": r.get("opportunity_title"),
            "chat_id": r.get("chat_id"), "task_id": r.get("task_id"),
            "chat_title": r.get("chat_title"),
            "nishon": _nishon(r),
            "havola": r["havola"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "read_at": r["read_at"].isoformat() if r["read_at"] else None}


def royxat(app_user_id: int, faqat_oqilmagan: bool = False,
           limit: int = 50, before_id: Optional[int] = None) -> Dict[str, Any]:
    """O'z xabarlari. HUQUQ TEKSHIRILMAYDI — bu o'zining ishi.

    (Boshqaning xabarini o'qish yo'li umuman yo'q: `app_user_id`
    sessiyadan keladi, so'rovdan emas.)

    `before_id` — "yana yuklash": shu id dan OLDINGILARI."""
    if not schema_ready():
        return {"ready": False, "items": [], "unread": 0, "yana": False}
    lim = max(1, min(limit, 200))
    sql = ROYXAT_SQL if schema27_ready() else ROYXAT_ESKI_SQL
    rows = db.query(sql, {"u": app_user_id, "faqat": bool(faqat_oqilmagan),
                          "l": lim, "before_id": before_id})
    return {"ready": True, "items": [_shape(r) for r in rows],
            "unread": sanoq(app_user_id),
            # "Yana bormi" — mijoz shunga qarab keyingi sahifani so'raydi.
            "yana": len(rows) == lim}


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
    yuborilsa hech narsa o'zgarmaydi.

    `ids` BERILMASA — HAMMASI ("hammasini o'qildi" tugmasi). Bu
    ATAYLAB alohida amal: ro'yxat ochilgani o'qilgan degani EMAS
    (§10), shuning uchun interfeys buni O'ZI chaqirmaydi."""
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
