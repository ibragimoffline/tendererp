"""
SINOV FIXTURE'i — sinovlar bazadagi ma'lumotga TAYANMASIN.

MUAMMO: sinovlarning bir qismi "bazada mijoz bormi, karta bormi" deb
qarab, bo'lmasa SKIP qilardi. Demo ma'lumot tozalanganda qamrov
JIMGINA tushib ketdi: 863 tekshiruvdan 582 tasi qoldi va hech bir
sinov yiqilmadi. Bu eng yomon holat — sinov "hammasi joyida" deydi,
lekin aslida yarmini tekshirmayapti.

YECHIM: kerakli minimal ma'lumotni sinovning O'ZI yaratadi.

BELGI: `ZZFIX`. `cleanup_demo.py` uni ham oladi (`ZZ` bilan boshlangan
belgilar ro'yxati u yerda), lekin fixture har yurishda qayta yaratadi.

NIMA YARATILADI (faqat `erp` sxemasida):
    hodim, mijoz korxona va bitta ish kartasi.

NIMA YARATILMAYDI: tender-ai KATALOGIDAGI mahsulot (`public.catalog_product`).
ERP `public.*` ga yozmaydi va bu qoida SINOVGA HAM tegishli — aks holda
sinov ilovaga taqiqlangan narsani qilib, chegara qoidasini o'zi buzardi.
Ombor sinovlari mahsulotsiz SKIP bo'ladi va buni OCHIQ aytadi.
"""
from typing import Any, Dict, Optional

from api import db

MARK = "ZZFIX"


def ensure_broker() -> Dict[str, Any]:
    r = db.query_one("SELECT id, full_name FROM erp.broker "
                     "WHERE full_name = %(n)s", {"n": f"{MARK} Hodim"})
    if r:
        return r
    return db.execute_returning(
        "INSERT INTO erp.broker (full_name) VALUES (%(n)s) "
        "RETURNING id, full_name", {"n": f"{MARK} Hodim"})


def ensure_client() -> Dict[str, Any]:
    """Mijoz passporti TO'LIQ: faktura va shartnoma uchun rekvizitlar
    kerak, aks holda sinov "yetishmayapti" xatosiga urilardi."""
    r = db.query_one("SELECT id, name FROM erp.client_company "
                     "WHERE name = %(n)s", {"n": f"{MARK} Mijoz"})
    if r:
        return r
    return db.execute_returning("""
        INSERT INTO erp.client_company
            (name, inn, legal_form, address_legal, bank_name, bank_mfo,
             bank_account, director_name, phone)
        VALUES (%(n)s, '123456789', 'MCHJ', 'Toshkent sh.', 'Bank',
                '00123', '20208000000000000001', 'ZZFIX Rahbar',
                '+998900000000')
        RETURNING id, name""", {"n": f"{MARK} Mijoz"})


def ensure_opportunity(status: str = "new") -> Optional[Dict[str, Any]]:
    """Bitta ish kartasi. Tender `public.tender` dan O'QILADI (yozilmaydi).

    Bazada tender bo'lmasa `None` — bunda sinov SKIP qiladi va sababini
    aytadi (ETL yurmagan bo'sh o'rnatmada shunday bo'ladi)."""
    r = db.query_one("SELECT id, status, client_id, broker_id, tender_id "
                     "FROM erp.opportunity WHERE created_by = %(m)s "
                     "ORDER BY id LIMIT 1", {"m": MARK})
    if r:
        return r

    t = db.query_one("SELECT id FROM public.tender ORDER BY id LIMIT 1")
    if not t:
        return None

    from api.erp import opportunity as O
    b, c = ensure_broker(), ensure_client()
    O.take(t["id"], {"broker_id": b["id"], "client_id": c["id"],
                     "priority": "medium", "created_by": MARK})
    return db.query_one("SELECT id, status, client_id, broker_id, tender_id "
                        "FROM erp.opportunity WHERE created_by = %(m)s "
                        "ORDER BY id LIMIT 1", {"m": MARK})


def cleanup() -> int:
    """Fixture yozuvlarini o'chiradi. Sinovlar OXIRIDA chaqiradi.

    Tartib `cleanup_demo.py` dagidek: fakturalar mijozdan oldin (ular
    `CASCADE`siz bog'langan)."""
    p = {"m": MARK, "pat": f"%{MARK}%"}
    n = 0
    for sql in (
        "DELETE FROM erp.invoice WHERE created_by = %(m)s "
        "OR client_name LIKE %(pat)s RETURNING id",
        "DELETE FROM erp.act WHERE created_by = %(m)s "
        "OR client_name LIKE %(pat)s RETURNING id",
        "DELETE FROM erp.stock_reserve WHERE created_by = %(m)s RETURNING id",
        "DELETE FROM erp.stock_move WHERE created_by = %(m)s RETURNING id",
        "DELETE FROM erp.opportunity WHERE created_by = %(m)s RETURNING id",
        "DELETE FROM erp.client_company WHERE name LIKE %(pat)s RETURNING id",
        "DELETE FROM erp.broker WHERE full_name LIKE %(pat)s RETURNING id",
    ):
        count_sql = ("SELECT count(*) " + sql.split("DELETE", 1)[1]
                     .replace("FROM", "FROM", 1).rsplit("RETURNING", 1)[0])
        c = db.scalar(count_sql, p) or 0
        if c:
            db.execute_returning(sql, p)
        n += c
    return n
