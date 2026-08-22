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


def run(days: int = 1, deadline_days: int = 3, dry_run: bool = False) -> Dict[str, Any]:
    """Eslatilishi kerak bo'lganlarni topadi, bitta xabar yuboradi va
    yuborilganlarni belgilaydi."""
    data = erp_tasks.due_reminders(days=days, deadline_days=deadline_days)
    n = len(data["tasks"]) + len(data["deadlines"])
    out: Dict[str, Any] = {"tasks": len(data["tasks"]),
                           "deadlines": len(data["deadlines"]),
                           "dry_run": dry_run, "sent": False}
    if not n:
        out["message"] = "Eslatadigan narsa yo'q."
        return out

    text = build_message(data)
    out["text"] = text
    if dry_run:
        out["message"] = "Quruq yurish — yuborilmadi, belgilanmadi."
        return out

    try:
        res = tenderai.notify("Tender ERP — eslatma", text)
    except tenderai.TenderAiUnavailable as e:
        # Yuborilmadi -> BELGILANMAYDI. Keyingi yurishda qayta uriniladi.
        out["error"] = str(e)
        return out

    out["sent"] = bool(res.get("ok"))
    out["channels"] = {k: v for k, v in res.items() if k != "ok"}
    if out["sent"]:
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
