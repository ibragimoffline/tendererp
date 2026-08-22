"""
HODIM hisobini yaratish / parolini almashtirish — buyruq qatoridan.

    .venv/Scripts/python.exe create_user.py admin "Bosh administrator" --role admin
    .venv/Scripts/python.exe create_user.py karimov "A. Karimov" --broker-id 2
    .venv/Scripts/python.exe create_user.py admin --password    # parolni almashtirish
    .venv/Scripts/python.exe create_user.py --list
    .venv/Scripts/python.exe create_user.py --brokers   # hodimlar ro'yxati

NEGA BU YERDA: hodim — ERP ning tushunchasi. Tender-AI esa KOMPANIYA
hisobi bilan kiriladi va uning o'z skripti bor
(`tender-ai/create_company.py`). Auth-1 da bu skript tender-ai da edi —
xato, chunki u yerda odam yo'q.

NEGA SKRIPT, "birinchi foydalanuvchini yaratish" endpointi EMAS:
har qanday bunday endpoint — ochiq eshik. U "foydalanuvchi yo'q bo'lsa
ishlaydi" degan shart bilan yopilsa ham, baza tozalangan paytda yana
ochiladi. Serverga kira oladigan odam esa allaqachon eng katta huquqqa ega,
shuning uchun birinchi admin SHU YERDAN yaratiladi.

Parol terilganda EKRANDA KO'RINMAYDI (`getpass`) va buyruq tarixiga
tushmaydi.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api import auth, db  # noqa: E402

BROKERS_SQL = """
SELECT b.id, b.full_name, b.active,
       u.username
FROM erp.broker b
LEFT JOIN erp.app_user u ON u.broker_id = b.id
ORDER BY b.active DESC, b.full_name
"""


def _ask_password() -> str:
    p1 = getpass.getpass("Parol: ")
    p2 = getpass.getpass("Yana bir marta: ")
    if p1 != p2:
        print("Parollar mos kelmadi.")
        raise SystemExit(1)
    return p1


def main() -> int:
    ap = argparse.ArgumentParser(description="ERP hodim hisobini yaratish")
    ap.add_argument("username", nargs="?", help="kirish nomi")
    ap.add_argument("full_name", nargs="?", help="to'liq ism")
    ap.add_argument("--role", default="broker",
                    choices=[c for c, _ in auth.ROLES])
    ap.add_argument("--broker-id", type=int, default=None,
                    help="erp.broker.id bilan bog'lash (--brokers ga qarang)")
    ap.add_argument("--email", default=None)
    ap.add_argument("--password", action="store_true",
                    help="mavjud hisobning parolini almashtirish")
    ap.add_argument("--list", action="store_true", help="hisoblar ro'yxati")
    ap.add_argument("--brokers", action="store_true",
                    help="hodimlar ro'yxati va ularning hisoblari")
    a = ap.parse_args()

    db.init_pool()
    try:
        if not auth.schema_ready():
            print("Auth jadvallari yo'q. Avval:")
            print('  psql "dbname=xtxarid user=postgres host=localhost" '
                  "-f schema_patch_erp_6.sql")
            return 1

        if a.brokers:
            for b in db.query(BROKERS_SQL):
                flag = "" if b["active"] else "  (faol emas)"
                acc = f"  -> {b['username']}" if b["username"] else "  (hisobsiz)"
                print(f"  #{b['id']:<4} {b['full_name']}{acc}{flag}")
            return 0

        if a.list:
            rows = auth.users()
            if not rows:
                print("Hisob yo'q.")
            for u in rows:
                flag = "" if u["active"] else "  (faol emas)"
                brk = f"  hodim: {u['broker_name']}" if u.get("broker_name") else ""
                print(f"  {u['username']:<16} {u['role']:<8} {u['full_name']}{brk}{flag}")
            return 0

        if not a.username:
            ap.print_help()
            return 1

        if a.password:
            cur = db.query_one(auth.USER_BY_NAME_SQL,
                               {"username": a.username.strip().lower()})
            if not cur:
                print(f"'{a.username}' topilmadi.")
                return 1
            auth.set_password(cur["id"], _ask_password())
            print(f"'{a.username}' paroli almashtirildi.")
            return 0

        u = auth.create_user(a.username, a.full_name or a.username,
                             _ask_password(), role=a.role,
                             broker_id=a.broker_id, email=a.email)
        print(f"Yaratildi: {u['username']} ({u['role_label']})")
        return 0
    except auth.AuthError as e:
        print(f"XATO: {e}")
        return 1
    finally:
        db.close_pool()


if __name__ == "__main__":
    sys.exit(main())
