"""
NAVBAT — bildirishnomani TASHQI kanalga yetkazish (outbox).

Ishga tushirish (jadval bo'yicha, masalan 5 daqiqada bir):
    .venv/Scripts/python.exe -m api.erp.navbat
    .venv/Scripts/python.exe -m api.erp.navbat --dry-run
    .venv/Scripts/python.exe -m api.erp.navbat --limit 20

MUAMMO: 22-patch bildirishnomani SAQLADI va `yuborildi_at` ustunini
qoldirdi, lekin uni to'ldiradigan kod hech qachon yozilmadi. Ya'ni
jadval "yuborilmagan" deb turardi va hech kim yubormasdi.

IKKI ISHONCHLILIK CHEGARASI (§22, §23)
══════════════════════════════════════
    Xabar/hodisa yozilishi   — ASOSIY. Bazada, tranzaksiyada.
    Tashqi kanalga yetkazish — QO'SHIMCHA. Keyin, alohida, qayta
                               urinish bilan.

Chat xabari Telegram yiqilgani uchun YO'QOLMASLIGI kerak. Shuning
uchun yuborish yozuv tranzaksiyasidan TASHQARIDA: tashqi xizmatning
sekinligi ERP ni ushlab turmaydi, xatosi esa yozuvni orqaga
qaytarmaydi.

KANAL — KOMPANIYA DARAJASIDA
════════════════════════════
Telegram bot tokeni va SMTP rekvizitlari Tender-AI o'rnatmasida
(`api/tenderai.py` -> `notify`), qabul qiluvchilar ham o'sha yerda
sozlangan. ERP manzil yubormaydi va YUBORA OLMAYDI. Ya'ni "Karimovga
email ketdi" degan gap bu arxitekturada YOLG'ON bo'lardi — ketgani
KOMPANIYA kanaliga ketadi.

Shuning uchun `hodisa.chiqar()` tashqi kanalni hodisaga BIR MARTA
qo'yadi (`api/erp/hodisa.py` dagi izoh).

`delivered` HOLATI YO'Q (§18)
═════════════════════════════
Tender-AI `notify` "yubordim" deb javob beradi, "yetib bordi" demaydi.
Yetkazilganiga DALIL yo'q ekan, uni holat sifatida yozish kuzatuvni
yolg'on qilardi. Bor holatlar: `pending` -> `sent` | `failed` ->
(qayta urinish) -> `sent` | `terminal`.

O'QILGANLIK bu yerda YO'Q: u bildirishnomaning O'ZIDA (`read_at`) va
kanalga bog'liq emas — odam ilovada o'qiydi, Telegram'da emas.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

try:                                            # Windows konsoli uchun
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from api import db, tenderai                    # noqa: E402

log = logging.getLogger("erp.navbat")

#: Yuboriladigan kanallar. Ilova kanali (`inapp`) BU YERDA YO'Q:
#: u jadvalning o'zi va yozilgan zahoti `sent` bo'ladi.
KANALLAR = ("telegram", "email")

#: Nechta urinishdan keyin TERMINAL. Kichik son ataylab: bir kunlik
#: eslatma uch kun urinishdan keyin yuborilsa, u allaqachon foydasiz.
MAX_URINISH = 5

#: Orqaga chekinish (daqiqa): 1, 5, 15, 60, 240. Ro'yxat `MAX_URINISH`
#: bilan bir xil uzunlikda bo'lishi shart — sinov tekshiradi.
KECHIKISH_DAQ = (1, 5, 15, 60, 240)

#: TERMINAL xato belgilari. Bularni qayta urinish TUZATMAYDI (§19):
#: noto'g'ri chat id, o'chirilgan bot, tanilmagan manzil. Cheksiz
#: urinish navbatni to'ldirardi va HAQIQIY vaqtinchalik nosozlik
#: ularning orasida ko'rinmay qolardi.
TERMINAL_BELGILAR = ("400", "401", "403", "404", "422",
                     "chat not found", "bot was blocked",
                     "invalid recipient", "unauthorized")


def _terminalmi(xato: str) -> bool:
    s = (xato or "").lower()
    return any(b in s for b in TERMINAL_BELGILAR)


NAVBAT_SQL = """
SELECT d.id, d.notification_id, d.kanal, d.urinish,
       n.kind, n.matn, n.havola, n.app_user_id,
       u.full_name AS kimga_nom
FROM erp.notification_delivery d
JOIN erp.notification n ON n.id = d.notification_id
LEFT JOIN erp.app_user u ON u.id = n.app_user_id
WHERE d.kanal = ANY(%(kanallar)s)
  AND d.holat IN ('pending', 'failed')
  AND d.next_try_at <= now()
ORDER BY d.next_try_at, d.id
LIMIT %(l)s
"""

OK_SQL = """
UPDATE erp.notification_delivery
SET holat = 'sent', urinish = urinish + 1, sent_at = now(), last_error = NULL
WHERE id = %(id)s RETURNING id
"""

# Bildirishnomaning O'ZIDA "kamida bitta tashqi kanal ketdi" belgisi.
# 22-patchdagi `yuborildi_at` ustuni AYNAN SHU uchun qo'yilgan edi.
YUBORILDI_SQL = """
UPDATE erp.notification SET yuborildi_at = coalesce(yuborildi_at, now())
WHERE id = %(id)s RETURNING id
"""

XATO_SQL = """
UPDATE erp.notification_delivery
SET holat = %(holat)s, urinish = urinish + 1, last_error = %(xato)s,
    next_try_at = now() + make_interval(mins => %(daq)s)
WHERE id = %(id)s RETURNING id, holat, urinish
"""


def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = 'erp' AND table_name = 'notification_delivery'"))


def _yubor(qator: Dict[str, Any]) -> None:
    """Bitta qatorni kanalga uzatadi. Xato bo'lsa KO'TARADI.

    Mavzu QISQA (§16): odam bildirishnoma ro'yxatini emas, bitta
    qatorni ko'radi."""
    matn = qator["matn"]
    if qator.get("havola"):
        matn = f"{matn}\n{qator['havola']}"
    tenderai.notify("Tender ERP", matn, channels=[qator["kanal"]])


def yur(limit: int = 50, dry_run: bool = False) -> Dict[str, Any]:
    """Navbatning vaqti kelgan qismini yuboradi.

    Qaytadi: nima bo'lganining SONI — `sent`, `failed`, `terminal`.
    Nol yuborilgani XATO EMAS: bo'sh navbat normal holat."""
    if not schema_ready():
        return {"ready": False, "olindi": 0, "sent": 0, "failed": 0,
                "terminal": 0}
    rows = db.query(NAVBAT_SQL, {"kanallar": list(KANALLAR),
                                 "l": max(1, min(limit, 500))})
    out = {"ready": True, "olindi": len(rows), "sent": 0, "failed": 0,
           "terminal": 0, "dry_run": dry_run, "xatolar": []}
    for r in rows:
        if dry_run:
            continue
        try:
            _yubor(r)
        except Exception as e:                      # noqa: BLE001
            xato = str(e)[:500]
            urinish = int(r["urinish"]) + 1
            # TERMINAL ikki yo'l bilan: xatoning O'ZI tuzalmaydigan
            # bo'lsa, yoki urinishlar tugagan bo'lsa.
            terminal = _terminalmi(xato) or urinish >= MAX_URINISH
            daq = KECHIKISH_DAQ[min(urinish, len(KECHIKISH_DAQ)) - 1]
            db.execute_returning(XATO_SQL, {
                "id": r["id"], "xato": xato,
                "holat": "terminal" if terminal else "failed",
                # Terminal qatorda vaqt ma'nosiz, lekin YOZILADI:
                # "qachon taslim bo'ldik" degan savol qoladi.
                "daq": daq})
            out["terminal" if terminal else "failed"] += 1
            out["xatolar"].append({"id": r["id"], "kanal": r["kanal"],
                                   "xato": xato, "terminal": terminal})
            log.warning("yetkazilmadi (id=%s kanal=%s urinish=%s): %s",
                        r["id"], r["kanal"], urinish, xato)
            continue
        db.execute_returning(OK_SQL, {"id": r["id"]})
        db.execute_returning(YUBORILDI_SQL, {"id": r["notification_id"]})
        out["sent"] += 1
    return out


# ---------------------------------------------------------------------------
# Kuzatuv (§20)
# ---------------------------------------------------------------------------
SOGLIQ_SQL = "SELECT * FROM erp.v_notification_health ORDER BY kanal"

UMUMIY_SQL = """
SELECT count(*)                                        AS jami,
       count(*) FILTER (WHERE read_at IS NULL)         AS oqilmagan,
       count(*) FILTER (WHERE created_at > now() - interval '24 hours')
                                                       AS sutkada
FROM erp.notification
"""


def sogliq() -> Dict[str, Any]:
    """"Bildirishnoma jim yo'qolmayaptimi" — bitta ekranda.

    `eng_eski_pending` ENG MUHIM raqam: navbat BOR bilan navbat
    TO'XTAB QOLGAN ni faqat u ajratadi. Nol pending — navbat bo'sh,
    lekin bir soatlik pending — yuboruvchi ishlamayapti."""
    if not schema_ready():
        return {"ready": False, "kanallar": [], "jami": 0}
    kanallar = []
    for r in db.query(SOGLIQ_SQL):
        kanallar.append({
            "kanal": r["kanal"], "jami": int(r["jami"]),
            "pending": int(r["pending"]), "sent": int(r["sent"]),
            "failed": int(r["failed"]), "terminal": int(r["terminal"]),
            "eng_eski_pending": (r["eng_eski_pending"].isoformat()
                                 if r["eng_eski_pending"] else None),
            "oxirgi_yuborilgan": (r["oxirgi_yuborilgan"].isoformat()
                                  if r["oxirgi_yuborilgan"] else None),
            "nosozlik_foiz": (int(r["nosozlik_foiz"])
                              if r["nosozlik_foiz"] is not None else None)})
    u = db.query_one(UMUMIY_SQL) or {}
    return {"ready": True, "kanallar": kanallar,
            "jami": int(u.get("jami") or 0),
            "oqilmagan": int(u.get("oqilmagan") or 0),
            "sutkada": int(u.get("sutkada") or 0),
            "max_urinish": MAX_URINISH}


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), ".env"))
    ap = argparse.ArgumentParser(description="Bildirishnoma navbati")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true",
                    help="navbatni ko'rsatadi, yubormaydi")
    a = ap.parse_args()

    db.init_pool()
    try:
        res = yur(limit=a.limit, dry_run=a.dry_run)
        s = sogliq()
    finally:
        db.close_pool()

    print(f"olindi: {res['olindi']}  yuborildi: {res['sent']}  "
          f"xato: {res['failed']}  terminal: {res['terminal']}")
    for k in s.get("kanallar", []):
        print(f"  {k['kanal']:9} pending={k['pending']:<4} sent={k['sent']:<5} "
              f"failed={k['failed']:<4} terminal={k['terminal']:<4} "
              f"eng_eski={k['eng_eski_pending'] or '—'}")
    for x in res.get("xatolar", []):
        print(f"  XATO {x['kanal']}: {x['xato']}"
              + ("  [TERMINAL]" if x["terminal"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
