"""
O'LCHOV — inson halqasi hisoblagichlari.

    .venv/Scripts/python.exe olchov.py
    .venv/Scripts/python.exe olchov.py --saqlamasdan

NIMA UCHUN BOR
==============
Loyihaning o'z qoidasi: "yangi qatlam qo'shishdan OLDIN hisoblagichlarni
ko'ring". Lekin ko'radigan buyruq YO'Q edi — raqamlar har safar qo'lda
so'rov yozib olinardi (bir sessiyada ikki marta). Ya'ni qoida bajarib
bo'lmaydigan holatda turardi.

Bu asbob yangi qatlam EMAS: u qoidani bajarish uchun kerak bo'lgan
o'lchagich.

UCHTA QOIDA
===========
1. FAQAT O'QIYDI. Hech narsa yaratmaydi, tuzatmaydi, o'chirmaydi.
   Yagona yozuvi — o'z natijasini `_olchov/` ga (pastga qarang).
2. JAMI va ODAM ALOHIDA. Yig'ma raqam yolg'on tasalli beradi: karta
   tarixi 77 ta ko'rinadi, odam yozgani esa 9 ta. Har qatorda ikki
   ustun.
3. O'LCHANMAGAN NARSA NOL EMAS. Jadval yo'q, patch qo'llanmagan yoki
   ustun yo'q bo'lsa `—` yoziladi, `0` emas (`ochilgan_at` NULL
   qoidasi). Nol — o'lchandi va hech narsa topilmadi degani.

CHIROYLI RAQAM YO'Q: 0 bo'lsa 0 deb yoziladi.

MANBA BITTA
===========
`check_setup.py` faol rahbar/menejer sonini shu yerdan oladi
(`boshliq_soni()`), o'z so'rovini yozmaydi — aks holda bitta tuzatish
ikki joyda qilinishi kerak bo'lardi.

TARIX
=====
Natija `_olchov/YYYY-MM-DD.json` ga yoziladi va oxirgi OLDINGI yurish
bilan solishtiriladi (`+2`, `0`, `-1`). Jadval ham, jurnal ham kerak
emas — "ikki hafta ishlangandan keyin o'zgardimi" degan savolga javob
shundan chiqadi.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from api import db  # noqa: E402

#: Natijalar shu papkaga. `.gitignore` da — bu O'LCHOV, kod emas.
TARIX_DIR = os.path.join(ROOT, "_olchov")

#: Demo/sinov belgilari. `cleanup_demo.py` va `check_setup.py` bilan
#: bir xil ro'yxat bo'lishi kerak — bu yerda ODAM ni ajratish uchun.
BELGILAR = ["%DEMO%", "%ZZTEST%", "%ZZSMOKE%", "%ZZFIX%", "%ZZOQIM%"]

#: O'lchanmagan qiymat. `0` DAN FARQLI: nol — o'lchandi, hech narsa
#: topilmadi; bu esa umuman o'lcholmadi.
YOQ = None


def _jadval_bor(schema: str, tbl: str) -> bool:
    try:
        return bool(db.query_one(
            "SELECT 1 AS x FROM information_schema.tables "
            "WHERE table_schema = %(s)s AND table_name = %(t)s",
            {"s": schema, "t": tbl}))
    except Exception:                           # noqa: BLE001
        return False


def _son(sql: str, **p) -> Optional[int]:
    """So'rov natijasi yoki `None` (o'lchab bo'lmadi)."""
    try:
        r = db.query_one(sql, p)
        return int(list(r.values())[0]) if r else 0
    except Exception:                           # noqa: BLE001
        return YOQ


# ---------------------------------------------------------------------------
# YAGONA MANBA — `check_setup.py` ham shuni chaqiradi
# ---------------------------------------------------------------------------
def boshliq_soni() -> Optional[int]:
    """Faol rahbar/menejer soni.

    `check_setup.py` 3- va 9-bo'limlari shu funksiyani chaqiradi. Ikki
    joyda ikki so'rov bo'lsa, rol ro'yxati o'zgarganda bittasi
    yangilanib, ikkinchisi eskirib qolardi."""
    if not _jadval_bor("erp", "app_user"):
        return YOQ
    return _son("SELECT count(*) FROM erp.app_user WHERE active "
                "AND role IN ('rahbar', 'menejer')")


# ---------------------------------------------------------------------------
# Hisoblagichlar
# ---------------------------------------------------------------------------
#: (kalit, nomi, jami, odam, izoh)
#:
#: `odam` — ODAM YOZGANI. Tizim yozuvlari, demo va sinov belgilari
#: chiqarib tashlanadi. `YOQ` bo'lsa — bu qatorda "odam" tushunchasi
#: yo'q (masalan bildirishnomani har doim tizim yozadi).
def olcha() -> List[Dict[str, Any]]:
    bel = {"b": BELGILAR}
    qatorlar: List[Tuple[str, str, Optional[int], Optional[int], str]] = []

    # 1. Rollar ajratilganmi.
    faol = (_son("SELECT count(*) FROM erp.app_user WHERE active")
            if _jadval_bor("erp", "app_user") else YOQ)
    qatorlar.append((
        "hisoblar", "Faol hisoblar / rahbar-menejer", faol, boshliq_soni(),
        "0 bo'lsa rollar ajratilmagan: hamma ish admin hisobidan"))

    # 2. Karta tarixi — ish jarayoni yuritilyaptimi.
    if _jadval_bor("erp", "opportunity_history"):
        jami = _son("SELECT count(*) FROM erp.opportunity_history")
        odam = _son(
            "SELECT count(*) FROM erp.opportunity_history "
            "WHERE changed_by IS NOT NULL "
            "AND changed_by NOT ILIKE ALL(%(b)s::text[])", **bel)
    else:
        jami = odam = YOQ
    qatorlar.append((
        "karta_tarixi", "Karta status o'tishlari", jami, odam,
        "odam ustuni — workflow HAQIQATAN yuritilyaptimi"))

    # 3. Chat — qurildi, ishlatilyaptimi.
    if _jadval_bor("erp", "chat_message"):
        jami = _son("SELECT count(*) FROM erp.chat_message")
        # Tizim xabari `author_id IS NULL` — u muloqot emas, jurnal.
        odam = _son("SELECT count(*) FROM erp.chat_message "
                    "WHERE author_id IS NOT NULL "
                    "AND text NOT ILIKE ALL(%(b)s::text[])", **bel)
    else:
        jami = odam = YOQ
    qatorlar.append((
        "chat", "Chat xabarlari", jami, odam,
        "jami ichida tizim xabarlari ham bor"))

    # 4. Eslatish — chatning ichki funksiyasi ishlatilyaptimi.
    eslatish = (_son("SELECT count(*) FROM erp.notification "
                     "WHERE kind = 'chat_mention'")
                if _jadval_bor("erp", "notification") else YOQ)
    qatorlar.append((
        "eslatish", "Chatda @ism eslatishlari", eslatish, YOQ,
        "odam ustuni yo'q: bildirishnomani har doim tizim yozadi"))

    # 5. Sabab hujjati — 24-patch ishlatilyaptimi.
    if _jadval_bor("erp", "opportunity_file"):
        jami = _son("SELECT count(*) FROM erp.opportunity_file")
        odam = _son("SELECT count(*) FROM erp.opportunity_file "
                    "WHERE created_by IS NOT NULL "
                    "AND created_by NOT ILIKE ALL(%(b)s::text[])", **bel)
    else:
        jami = odam = YOQ
    qatorlar.append((
        "sabab_hujjati", "Sabab hujjatlari", jami, odam,
        "yopilgan kartada 'nega' hujjati biriktirilyaptimi"))

    # 6. Hujjat jurnali — pul hujjatlariga tegilyaptimi.
    if _jadval_bor("erp", "doc_audit"):
        jami = _son("SELECT count(*) FROM erp.doc_audit")
        odam = _son("SELECT count(*) FROM erp.doc_audit "
                    "WHERE actor IS NOT NULL "
                    "AND actor NOT ILIKE ALL(%(b)s::text[])", **bel)
    else:
        jami = odam = YOQ
    qatorlar.append((
        "hujjat_jurnali", "Hujjat o'zgarishlari", jami, odam,
        "`actor IS NULL` = ERP dan tashqarida o'zgartirilgan"))

    # 7. Tender-AI yo'naltirishi — navbat o'sadimi, qaror qabul
    #    qilinadimi. `public.*` — FAQAT O'QISH.
    if _jadval_bor("public", "tender_routing"):
        jami = _son("SELECT count(*) FROM public.tender_routing")
        odam = _son("SELECT count(inson_qaror) FROM public.tender_routing")
    else:
        jami = odam = YOQ
    qatorlar.append((
        "yonaltirish", "Tender-AI navbati / inson qarori", jami, odam,
        "jami o'sib, odam qotib qolsa — qatlam ishlatilmayapti"))

    return [{"kalit": k, "nomi": n, "jami": j, "odam": o, "izoh": i}
            for k, n, j, o, i in qatorlar]


# ---------------------------------------------------------------------------
# Tarix
# ---------------------------------------------------------------------------
def oldingi(bugun: str) -> Optional[Dict[str, Any]]:
    """Oxirgi OLDINGI yurish (bugungisi hisobga olinmaydi)."""
    if not os.path.isdir(TARIX_DIR):
        return None
    fayllar = sorted(f for f in os.listdir(TARIX_DIR)
                     if f.endswith(".json") and f[:-5] < bugun)
    if not fayllar:
        return None
    try:
        with open(os.path.join(TARIX_DIR, fayllar[-1]), encoding="utf-8") as f:
            d = json.load(f)
        d["_fayl"] = fayllar[-1]
        return d
    except Exception:                           # noqa: BLE001
        return None


def saqla(bugun: str, qatorlar: List[Dict[str, Any]]) -> str:
    os.makedirs(TARIX_DIR, exist_ok=True)
    yol = os.path.join(TARIX_DIR, f"{bugun}.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({"sana": bugun, "qatorlar": qatorlar}, f,
                  ensure_ascii=False, indent=2)
    return yol


def _k(v: Optional[int]) -> str:
    """Ko'rsatish: `None` -> `—` (o'lchanmadi), 0 -> `0`."""
    return "—" if v is None else str(v)


def _farq(hozir: Optional[int], oldin: Optional[int]) -> str:
    if hozir is None or oldin is None:
        return "—"
    d = hozir - oldin
    return f"+{d}" if d > 0 else str(d)


def main() -> int:
    ap = argparse.ArgumentParser(description="Inson halqasi hisoblagichlari.")
    ap.add_argument("--saqlamasdan", action="store_true",
                    help="natijani `_olchov/` ga YOZMAYDI")
    args = ap.parse_args()

    try:
        db.init_pool()
    except Exception as e:                      # noqa: BLE001
        print(f"Bazaga ulanib bo'lmadi: {e}")
        return 1

    bugun = dt.date.today().isoformat()
    qatorlar = olcha()
    eski = oldingi(bugun)
    eski_map = {q["kalit"]: q for q in (eski or {}).get("qatorlar", [])}

    print(f"\nINSON HALQASI — {bugun}")
    if eski:
        print(f"(farq: {eski['sana']} bilan)")
    else:
        print("(oldingi yurish yo'q — farq ustuni bo'sh)")
    print("=" * 74)
    print(f"{'':<34}{'JAMI':>8}{'':>6}{'ODAM':>8}{'':>6}")
    print("-" * 74)
    for q in qatorlar:
        e = eski_map.get(q["kalit"], {})
        print(f"{q['nomi']:<34}"
              f"{_k(q['jami']):>8}{_farq(q['jami'], e.get('jami')):>6}"
              f"{_k(q['odam']):>8}{_farq(q['odam'], e.get('odam')):>6}")
    print("-" * 74)
    for q in qatorlar:
        print(f"  {q['nomi']}: {q['izoh']}")

    if args.saqlamasdan:
        print("\n  (--saqlamasdan: natija yozilmadi)")
    else:
        print(f"\n  saqlandi: {os.path.relpath(saqla(bugun, qatorlar), ROOT)}")
    print("  Bu asbob FAQAT O'QIYDI — hech narsa tuzatmaydi.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
