"""ERP 3-bosqich: deadline va vazifa ESLATMALARI.

Ishga tushirish (jadval bo'yicha, kuniga bir marta):
    .venv/Scripts/python.exe -m api.erp.remind
    .venv/Scripts/python.exe -m api.erp.remind --dry-run    # yubormaydi
    .venv/Scripts/python.exe -m api.erp.remind --days 2 --deadline-days 5

Jadvalga qo'yish: `register_erp_task.ps1` (Windows Task Scheduler).

QARORLAR:
  - TRANSPORT ERP'DA EMAS. Xabar tender-ai orqali ketadi
    (`api/tenderai.py` -> `POST /notify/send`): SMTP rekvizitlari va Telegram
    bot tokeni o'sha o'rnatmada qoladi, ERP'ga sir ko'chirilmaydi.
  - TAKROR YUBORILMAYDI: yuborilgach `reminded_at` / `deadline_reminded_at`
    belgilanadi. Vazifa muddati o'zgarsa belgi tozalanadi (SQL'da) va
    eslatma qaytadan ketadi — ko'chirilgan muddat jimgina o'tib ketmasin.
  - YUBORILMASA BELGILANMAYDI: tender-ai javob bermasa yozuvlar
    belgilanmaydi va keyingi yurishda qayta uriniladi.
  - BITTA XABAR: hamma eslatma bitta matnga yig'iladi. Har vazifa uchun
    alohida xabar yuborilsa kun boshida 15 ta bildirishnoma kelardi va
    ularni hech kim o'qimasdi.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Any, Dict, List

# `python -m api.erp.remind` bilan ham, to'g'ridan-to'g'ri ham ishlasin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

try:                                            # Windows konsoli uchun
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), ".env"))

from api import db, tenderai            # noqa: E402
from api.erp import tasks as erp_tasks  # noqa: E402

#: Eslatmada ko'rsatiladigan kechikkan kartalar soni. Qolgani "va yana
#: N ta" bo'lib yig'iladi: 40 qatorlik ro'yxatni hech kim o'qimaydi va
#: u bilan birga o'qiladigan qismi ham yo'qoladi.
MAX_KECHIKKAN = 10


def build_message(data: Dict[str, Any]) -> str:
    """Eslatma matni. Telegram HTML'ni qo'llaydi, email esa oddiy matnni —
    shuning uchun teg ishlatilmaydi: bitta matn ikkala kanalga ham to'g'ri
    ko'rinadi."""
    lines: List[str] = ["Tender ERP — eslatma", ""]

    overdue = [t for t in data["tasks"] if t["overdue"]]
    today = [t for t in data["tasks"] if not t["overdue"]]

    if overdue:
        lines.append(f"KECHIKKAN VAZIFALAR ({len(overdue)}):")
        for t in overdue:
            lines.append(f"  • {t['title']} — {_when(t['due_at'])}"
                         f"{_who(t)}{_about(t)}")
        lines.append("")
    if today:
        lines.append(f"MUDDATI KELGAN VAZIFALAR ({len(today)}):")
        for t in today:
            lines.append(f"  • {t['title']} — {_when(t['due_at'])}"
                         f"{_who(t)}{_about(t)}")
        lines.append("")
    if data["deadlines"]:
        lines.append(f"TENDER MUDDATI YAQIN ({len(data['deadlines'])}):")
        for o in data["deadlines"]:
            who = f" · {o['broker_name']}" if o["broker_name"] else ""
            cl = f" · {o['client_name']}" if o["client_name"] else ""
            lines.append(f"  • {(o['title'] or '')[:70]} — {_when(o['deadline_at'])}"
                         f"{who}{cl}")
        lines.append("")

    # ESKALATSIYA — eng tepada emas, oxirida: bu "bugun nima qilaman"
    # emas, "ochiq qarz" ro'yxati. Lekin U KO'RSATILADI, chunki tizim
    # kartani o'zi yopmaydi (`opportunity.TIZIM_QOYADI` bo'sh) va
    # yopilmagan karta voronkani jimgina shishiradi.
    kech = data.get("kechikkan") or []
    if kech:
        lines.append(f"MUDDATI O'TGAN, YOPILMAGAN ({len(kech)}) — "
                     "kartani yoping:")
        for o in kech[:MAX_KECHIKKAN]:
            who = f" · {o['broker_name']}" if o.get("broker_name") else ""
            lines.append(f"  • {(o['title'] or '')[:70]} — "
                         f"{o['kun']} kun oldin tugagan{who}")
        if len(kech) > MAX_KECHIKKAN:
            lines.append(f"  ... va yana {len(kech) - MAX_KECHIKKAN} ta")
        lines.append("  Holat: yutqazildi / rad etildi / ulgurmadik.")
        lines.append("")

    lines.append(f"ERP: {os.environ.get('ERP_WEB', 'http://localhost:5174')}")
    return "\n".join(lines)


def _when(iso: Any) -> str:
    """ISO -> "21.08.2026 07:43". Xabarni ODAM o'qiydi: `2026-08-21T07:43:00+05:00`
    ko'rinishi vaqtni bir qarashda anglatmaydi."""
    if not iso:
        return "—"
    s = str(iso)
    d, _, rest = s.partition("T")
    try:
        y, m, dd = d.split("-")
    except ValueError:
        return s
    out = f"{dd}.{m}.{y}"
    return f"{out} {rest[:5]}" if rest else out


def _who(t: Dict[str, Any]) -> str:
    return f" · {t['assignee']}" if t.get("assignee") else ""


def _about(t: Dict[str, Any]) -> str:
    parts = [p for p in ((t.get("opp_title") or "")[:60], t.get("client_name")) if p]
    return f" ({' · '.join(parts)})" if parts else ""


def _hodimlarga(data: Dict[str, Any]) -> int:
    """HAR HODIMGA o'z ishlari haqida xabar (`api/erp/xabar.py`).

    NEGA KOMPANIYA XABARIDAN TASHQARI: Telegram guruhiga tushgan
    umumiy ro'yxatda odam o'zinikini qidirib topishi kerak — va
    ko'pincha topmaydi. Bu yerda har kim faqat O'ZINIKINI oladi.

    Menejer esa umumiy sonni oladi: kimdir kechikayotganini bilishi
    kerak, lekin har vazifa uchun alohida xabar olishi shart emas."""
    from api.erp import hodisa

    yuborildi = 0
    #: broker_id -> [matn]
    kimga: Dict[Any, list] = {}
    for t in data["tasks"]:
        if not t.get("broker_id"):
            continue
        kech = "KECHIKKAN: " if t.get("overdue") else ""
        kimga.setdefault(t["broker_id"], []).append(
            (t.get("opportunity_id"),
             f"{kech}vazifa muddati: {t['title']}{_about(t)}"))
    for o in data["deadlines"]:
        if not o.get("broker_id"):
            continue
        kimga.setdefault(o["broker_id"], []).append(
            (o["id"], f"Tender muddati yaqin: {(o.get('title') or '')[:60]} "
                      f"({_when(o.get('deadline_at'))})"))

    for broker_id, qatorlar in kimga.items():
        for opp_id, matn in qatorlar:
            # DEDUP KUN BO'YICHA: eslatma skripti kuniga bir marta
            # yuriydi, lekin qo'lda ham ishga tushiriladi (va CI da
            # ikki marta ham). Bir kunda bir xil vazifa uchun ikkita
            # bildirishnoma chiqmasin (§17).
            if hodisa.chiqar("muddat", matn, broker_id=broker_id,
                             opportunity_id=opp_id,
                             dedup=f"muddat:{_bugun()}:{opp_id}:{matn[:40]}",
                             kotar=False)["yozildi"]:
                yuborildi += 1

    # KECHIKKANLAR — har karta uchun alohida emas, BITTA yig'ma xabar.
    #
    # Sabab: bu ro'yxat karta yopilmaguncha HAR KUNI qaytadi. Har
    # kartaga alohida xabar yuborilsa, bir hafta ichida bildirishnoma
    # qutisi shu bitta narsadan to'lardi va odam hammasini o'qimay
    # yopishni odat qilardi — shundan keyin HAQIQIY xabar ham
    # ko'rinmay qolardi.
    kech_kimga: Dict[Any, int] = {}
    for o in data.get("kechikkan") or []:
        if o.get("broker_id"):
            kech_kimga[o["broker_id"]] = kech_kimga.get(o["broker_id"], 0) + 1
    for broker_id, n_kech in kech_kimga.items():
        if hodisa.chiqar(
                "muddat",
                f"{n_kech} ta kartaning muddati o'tgan, lekin yopilmagan. "
                "Holatni qo'ying: yutqazildi / rad etildi / ulgurmadik.",
                broker_id=broker_id,
                dedup=f"kechikkan:{_bugun()}:{broker_id}",
                kotar=True)["yozildi"]:
            yuborildi += 1

    # Egasiz qatorlar ham bor (karta hech kimga biriktirilmagan) —
    # ular menejerga ketadi, aks holda hech kim ko'rmaydi.
    egasiz = ([t for t in data["tasks"] if not t.get("broker_id")]
              + [o for o in data["deadlines"] if not o.get("broker_id")]
              + [o for o in (data.get("kechikkan") or [])
                 if not o.get("broker_id")])
    if egasiz:
        hodisa.chiqar(
            "muddat", f"Mas'uli yo'q {len(egasiz)} ta muddat yaqinlashdi — "
            "kartalarni taqsimlash kerak.", boshliqqa=True,
            dedup=f"egasiz:{_bugun()}", kotar=True)
    return yuborildi


#: Hujjat muddati necha kun oldin ogohlantiriladi. 30 kun ataylab:
#: litsenziya yoki sertifikatni yangilash bir kunlik ish emas, va
#: "ertaga tugaydi" degan xabar allaqachon kech.
HUJJAT_KUN = int(os.environ.get("ERP_HUJJAT_OGOH_KUN", "30"))

HUJJAT_SQL = """
SELECT d.id, d.name, d.doc_type, d.valid_until, c.name AS mijoz
FROM erp.client_document d
JOIN erp.client_company c ON c.id = d.client_id
WHERE d.valid_until IS NOT NULL
  AND d.valid_until >= current_date
  AND d.valid_until <= current_date + make_interval(days => %(kun)s)
-- FAQAT ISHLAYOTGAN MIJOZLAR: yopilmagan kartasi bor korxonalar.
-- Aks holda bir marta ishlagan va unutilgan yuzta mijozning
-- hujjatlari har oy eslatib turardi va ro'yxat foydasiz bo'lardi.
  AND EXISTS (SELECT 1 FROM erp.opportunity o
               WHERE o.client_id = c.id
                 AND o.status NOT IN ('won', 'lost', 'rejected', 'ulgurmadik'))
ORDER BY d.valid_until, d.id
"""


def _hujjat_muddati() -> int:
    """Mijoz hujjatining muddati tugayapti -> boshliqqa.

    NEGA BROKERGA EMAS: hujjat MIJOZNIKI, kartaniki emas. Bitta
    litsenziya o'nta kartada ishlatiladi va o'nta brokerga bir xil
    xabar yuborish shovqin bo'lardi. Yangilash esa baribir
    menejerning ishi."""
    from api.erp import hodisa
    rows = db.query(HUJJAT_SQL, {"kun": HUJJAT_KUN})
    if not rows:
        return 0
    kimga = hodisa.boshliqlar()
    n = 0
    for d in rows:
        qoldi = (d["valid_until"] - dt.date.today()).days
        r = hodisa.hujjat_muddati(
            kimga,
            f"{d['mijoz']}: \"{d['name']}\" hujjati {qoldi} kundan keyin "
            f"tugaydi ({_when(d['valid_until'])}).",
            # BIR HUJJAT BIR MARTA: kalitda sana YO'Q, ya'ni
            # ogohlantirish 30 kun davomida HAR KUNI takrorlanmaydi.
            # Muddat uzaytirilsa kalit o'zgaradi va yangi xabar ketadi.
            dedup=f"hujjat:{d['id']}:{d['valid_until']}")
        n += r["yozildi"]
    return n


def _bugun() -> str:
    """Dedup kaliti uchun sana. Vaqt EMAS: kalit kun bo'yicha
    bo'lishi kerak, aks holda har yurishda yangi kalit chiqib
    takrorlanishdan himoya ishlamay qolardi."""
    import datetime as _dt
    return _dt.date.today().isoformat()


def run(days: int = 1, deadline_days: int = 3, dry_run: bool = False) -> Dict[str, Any]:
    """Eslatilishi kerak bo'lganlarni topadi, xabar beradi va
    yuborilganlarni belgilaydi.

    IKKI KANAL, IKKI ISHONCHLILIK (2026-09-02 da o'zgardi):

      * ERP ICHIDAGI bildirishnoma — ASOSIY. U ERP ning o'z
        jadvalida (`erp.notification`) va tashqi xizmatga bog'liq
        emas. Belgilash (`mark_reminded`) shunga qarab qilinadi.
      * Tender-AI orqali Telegram/email — QO'SHIMCHA. U yiqilsa
        eslatma baribir odamga yetadi; xato javobda ochiq qaytadi.

    Ilgari belgilash TASHQI kanalga bog'liq edi: Tender-AI o'chgan
    bo'lsa hech kim hech narsa olmasdi. Endi ERP o'z ishini o'zi
    bajaradi."""
    data = erp_tasks.due_reminders(days=days, deadline_days=deadline_days)
    kech = data.get("kechikkan") or []
    # Kechikkanlar ham SANALADI: faqat shular qolgan kunda "eslatadigan
    # narsa yo'q" deb chiqib ketish aynan eslatish kerak bo'lgan holatni
    # jim qoldirardi.
    n = len(data["tasks"]) + len(data["deadlines"]) + len(kech)
    out: Dict[str, Any] = {"tasks": len(data["tasks"]),
                           "deadlines": len(data["deadlines"]),
                           "kechikkan": len(kech),
                           "dry_run": dry_run, "sent": False}
    # HUJJAT MUDDATI — ALOHIDA va ERTAROQ: u vazifa/deadline
    # ro'yxatiga bog'liq emas. Ilgari bu qator pastda edi va
    # "eslatadigan narsa yo'q" degan erta qaytish uni butunlay
    # chetlab o'tardi — ya'ni vazifasi yo'q kunda hujjat muddati
    # HECH QACHON eslatilmasdi.
    out["hujjat"] = 0 if dry_run else _hujjat_muddati()
    if not n:
        out["message"] = ("Eslatadigan narsa yo'q."
                          if not out["hujjat"] else
                          f"Faqat hujjat muddati: {out['hujjat']}")
        return out

    text = build_message(data)
    out["text"] = text
    if dry_run:
        out["message"] = "Quruq yurish — yuborilmadi, belgilanmadi."
        return out

    # 1. ASOSIY KANAL — ERP ichidagi bildirishnoma.
    out["xabarlar"] = _hodimlarga(data)

    # 2. QO'SHIMCHA — kompaniya kanali (Telegram/email) Tender-AI orqali.
    try:
        res = tenderai.notify("Tender ERP — eslatma", text)
        out["sent"] = bool(res.get("ok"))
        out["channels"] = {k: v for k, v in res.items() if k != "ok"}
    except tenderai.TenderAiUnavailable as e:
        # YIQILSA HAM eslatma odamga YETDI (1-qadam). Xato
        # yashirilmaydi, lekin belgilashni to'xtatmaydi — aks holda
        # ertaga hamma xabar TAKRORLANARDI.
        out["error"] = str(e)

    out["marked"] = erp_tasks.mark_reminded(
        [t["id"] for t in data["tasks"]],
        [o["id"] for o in data["deadlines"]])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="ERP eslatmalari")
    ap.add_argument("--days", type=int, default=1,
                    help="vazifa muddati necha kun ichida (default 1)")
    ap.add_argument("--deadline-days", type=int, default=3,
                    help="tender muddati necha kun ichida (default 3)")
    ap.add_argument("--dry-run", action="store_true",
                    help="topilganini ko'rsatadi, yubormaydi va belgilamaydi")
    a = ap.parse_args()

    db.init_pool()
    try:
        res = run(days=a.days, deadline_days=a.deadline_days, dry_run=a.dry_run)
    finally:
        db.close_pool()

    print(f"vazifa: {res['tasks']}  deadline: {res['deadlines']}  "
          f"kechikkan: {res.get('kechikkan', 0)}  "
          f"yuborildi: {res['sent']}")
    if res.get("text"):
        print("-" * 60)
        print(res["text"])
        print("-" * 60)
    if res.get("error"):
        print(f"XATO: {res['error']}")
        return 1
    if res.get("marked"):
        print(f"belgilandi: {res['marked']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
