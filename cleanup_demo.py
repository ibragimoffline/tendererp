"""
DEMO va SINOV ma'lumotlarini tozalash — buyruq qatoridan.

    .venv/Scripts/python.exe cleanup_demo.py            # FAQAT KO'RSATADI
    .venv/Scripts/python.exe cleanup_demo.py --yes      # o'chiradi
    .venv/Scripts/python.exe cleanup_demo.py --marker DEMO --yes

NEGA KERAK: ishlab chiqish davomida bazaga demo kartalar, sinov
foydalanuvchilari va qoldiqlari yig'ilib qoladi. Real ishga o'tishdan
oldin ularni ajratish kerak, lekin "hammasini o'chirish" ham xavfli:
haqiqiy ma'lumot allaqachon kiritilgan bo'lishi mumkin.

QANDAY AJRATADI: BELGI bo'yicha. Demo va sinov yozuvlari ataylab
prefiks bilan yaratilgan:

    DEMO      — namoyish ma'lumotlari (`DEMO A. Karimov`)
    ZZTEST    — sinov to'plamlari (`_tests/*.py`)
    ZZSMOKE   — qo'lda tekshiruv skriptlari

Belgisi yo'q yozuv TEGILMAYDI. Ya'ni skript "hammasini tozalash"
vositasi emas — u faqat O'ZIMIZ QO'YGAN belgilarni oladi.

IKKI QOIDA:

1. SUKUT BO'YICHA HECH NARSA O'CHIRILMAYDI. `--yes` berilmasa faqat
   ro'yxat chiqadi. O'chirish qaytarib bo'lmaydigan amal va uni
   tasodifan bajarib qo'yish juda oson.

2. FAQAT `erp` SXEMASI. `public.*` — tender-ai niki va ERP unga
   YOZMAYDI (loyihaning asosiy chegara qoidasi). Tender-ai dagi demo
   ma'lumot bo'lsa, u o'sha yerdan tozalanadi.

O'CHIRISH TARTIBI: bolalardan boshlab. Ko'p bog'lanishlar `CASCADE`,
lekin hammasi emas (`erp.invoice.client_id` da `CASCADE` yo'q — faktura
mijozsiz qolmasligi kerak), shuning uchun tartib QO'LDA yozilgan.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):            # pragma: no cover
    pass

from dotenv import load_dotenv

load_dotenv()

from api import db  # noqa: E402

#: Belgilar. Katta-kichik harf farqlanmaydi (`ILIKE`).
MARKERS = ("DEMO", "ZZTEST", "ZZSMOKE")

# Qadamlar: (nomi, SQL). Har biri `%(pat)s` shablonini oladi.
#
# TARTIB MUHIM va u bog'lanishlardan kelib chiqadi:
#   0) DALOLATNOMALAR — ular ham mijozga, ham fakturaga bog'langan,
#      ya'ni ikkalasidan OLDIN ketishi kerak. (Akt keyinroq qo'shilgan
#      va bu qadam o'shanda tushib qolgan edi: demo tozalash "act
#      jadvalidan bog'liqlik bor" xatosi bilan to'xtardi.)
#   1) fakturalar — ular mijozga `CASCADE`siz bog'langan, ya'ni mijozdan
#      OLDIN ketishi kerak;
#   2) ombor yozuvlari — kartaga bog'langan, lekin belgisi o'zida;
#   3) kartalar — ularning tarixi, vazifalari, takliflari va
#      shartnomalari `CASCADE` bilan o'zi ketadi;
#   4) lug'atlar (mijoz, hodim) — oxirida, chunki kartalar ularga
#      tayanadi.
STEPS = [
    ("dalolatnomalar (qatorlari bilan)", """
        DELETE FROM erp.act a
        WHERE a.number ILIKE %(pat)s OR a.note ILIKE %(pat)s
           OR a.created_by ILIKE %(pat)s
           OR a.client_name ILIKE %(pat)s
           OR EXISTS (SELECT 1 FROM erp.client_company c
                      WHERE c.id = a.client_id AND c.name ILIKE %(pat)s)
           OR EXISTS (SELECT 1 FROM erp.opportunity o
                      WHERE o.id = a.opportunity_id
                        AND o.created_by ILIKE %(pat)s)
        RETURNING a.id
    """),
    ("fakturalar (qatorlari va to'lovlari bilan)", """
        DELETE FROM erp.invoice i
        WHERE i.number ILIKE %(pat)s OR i.note ILIKE %(pat)s
           OR i.created_by ILIKE %(pat)s
           OR i.client_name ILIKE %(pat)s
           OR EXISTS (SELECT 1 FROM erp.client_company c
                      WHERE c.id = i.client_id AND c.name ILIKE %(pat)s)
           OR EXISTS (SELECT 1 FROM erp.opportunity o
                      WHERE o.id = i.opportunity_id
                        AND o.created_by ILIKE %(pat)s)
        RETURNING i.id
    """),
    ("ombor rezervlari", """
        DELETE FROM erp.stock_reserve r
        WHERE r.created_by ILIKE %(pat)s OR r.note ILIKE %(pat)s
           OR r.product_name ILIKE %(pat)s
           OR EXISTS (SELECT 1 FROM erp.opportunity o
                      WHERE o.id = r.opportunity_id
                        AND o.created_by ILIKE %(pat)s)
        RETURNING r.id
    """),
    ("ombor harakatlari", """
        DELETE FROM erp.stock_move m
        WHERE m.created_by ILIKE %(pat)s OR m.note ILIKE %(pat)s
           OR m.product_name ILIKE %(pat)s OR m.doc_ref ILIKE %(pat)s
        RETURNING m.id
    """),
    ("kartalar (tarix, vazifa, taklif, shartnoma bilan)", """
        DELETE FROM erp.opportunity o
        WHERE o.created_by ILIKE %(pat)s
           OR EXISTS (SELECT 1 FROM erp.broker b
                      WHERE b.id = o.broker_id AND b.full_name ILIKE %(pat)s)
           OR EXISTS (SELECT 1 FROM erp.client_company c
                      WHERE c.id = o.client_id AND c.name ILIKE %(pat)s)
        RETURNING o.id
    """),
    ("mijoz korxonalar (aloqa va hujjatlari bilan)", """
        DELETE FROM erp.client_company c
        WHERE c.name ILIKE %(pat)s
        RETURNING c.id
    """),
    ("hodimlar", """
        DELETE FROM erp.broker b
        WHERE b.full_name ILIKE %(pat)s
        RETURNING b.id
    """),
    ("hodim hisoblari (sessiyalari bilan)", """
        DELETE FROM erp.app_user u
        WHERE u.username ILIKE %(pat)s OR u.full_name ILIKE %(pat)s
        RETURNING u.id
    """),
]

#: Ko'rsatish uchun: nima o'chirilishini OLDINDAN sanaymiz. `DELETE` ni
#: `SELECT count(*)` ga aylantirish uchun shablon.
COUNT_TEMPLATE = "SELECT count(*) AS n FROM ({body}) x"


def _count_sql(delete_sql: str) -> str:
    """`DELETE ... RETURNING id` -> `SELECT count(*)`.

    `DELETE` ni ishlatmasdan sanash uchun uni `SELECT` ga aylantiramiz:
    shart qismi bir xil qoladi, ya'ni ro'yxat va o'chirish AYNAN bir xil
    yozuvlarni ko'radi."""
    s = delete_sql.strip()
    head, _, rest = s.partition("WHERE")
    table = head.replace("DELETE FROM", "").strip()
    body = rest.rsplit("RETURNING", 1)[0]
    return COUNT_TEMPLATE.format(body=f"SELECT 1 FROM {table} WHERE {body}")


def _purge_audit(really: bool) -> int:
    """Hujjati o'chirilgan audit yozuvlari.

    Jurnal hujjatga FK bilan bog'lanmagan — bu ataylab (hujjatni
    o'chirish tarixni ham o'chirmasin). Demo tozalashda esa o'sha
    hujjatlarning o'zi ketadi va yozuvlar egasiz qoladi."""
    if not db.query_one("SELECT 1 AS x FROM information_schema.tables "
                        "WHERE table_schema='erp' AND table_name='doc_audit'"):
        return 0
    sql = """
        SELECT count(*) AS n FROM erp.doc_audit a
        WHERE (a.doc_type = 'invoice'
               AND NOT EXISTS (SELECT 1 FROM erp.invoice i WHERE i.id = a.doc_id))
           OR (a.doc_type = 'act'
               AND NOT EXISTS (SELECT 1 FROM erp.act t WHERE t.id = a.doc_id))
    """
    n = db.scalar(sql) or 0
    if n and really:
        with db.get_conn() as cn:
            with cn.cursor() as cur:
                cur.execute("SET LOCAL erp.audit_purge = 'on'")
                cur.execute("""
                    DELETE FROM erp.doc_audit a
                    WHERE (a.doc_type = 'invoice' AND NOT EXISTS
                           (SELECT 1 FROM erp.invoice i WHERE i.id = a.doc_id))
                       OR (a.doc_type = 'act' AND NOT EXISTS
                           (SELECT 1 FROM erp.act t WHERE t.id = a.doc_id))
                """)
            cn.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Demo va sinov ma'lumotlarini tozalash (erp sxemasi)")
    ap.add_argument("--yes", action="store_true",
                    help="haqiqatan o'chirish (bo'lmasa faqat ko'rsatadi)")
    ap.add_argument("--marker", action="append", default=None,
                    help=f"belgi (bir nechta bo'lishi mumkin). "
                         f"Sukut: {', '.join(MARKERS)}")
    a = ap.parse_args()

    markers = a.marker or list(MARKERS)

    db.init_pool()
    try:
        if not db.query_one("SELECT 1 AS x FROM information_schema.schemata "
                            "WHERE schema_name = 'erp'"):
            print("`erp` sxemasi yo'q — tozalanadigan narsa ham yo'q.")
            return 0

        print(f"Belgilar: {', '.join(markers)}")
        rejim = "O'CHIRISH" if a.yes else "FAQAT KO'RSATISH"
        print("Rejim:    " + rejim)
        print()

        total = 0
        for label, sql in STEPS:
            step_n = 0
            for m in markers:
                pat = f"%{m}%"
                n = db.scalar(_count_sql(sql), {"pat": pat}) or 0
                if not n:
                    continue
                if a.yes:
                    # `execute_returning` bitta qator qaytaradi, shuning
                    # uchun sonni OLDIN olib qo'ydik.
                    db.execute_returning(sql, {"pat": pat})
                step_n += n
            if step_n:
                mark = "o'chirildi" if a.yes else "o'chiriladi"
                print(f"  {step_n:>4} {label} — {mark}")
                total += step_n

        # AUDIT JURNALI hujjat bilan birga ketmaydi (FK ataylab yo'q,
        # `erp_audit.md` 7). Belgili hujjatlar o'chgach uning yozuvlari
        # osilib qoladi — ularni ALOHIDA olamiz.
        #
        # `erp.audit_purge` bayrog'i ATAYLAB yoqiladi: jurnalni tasodifan
        # o'chirib bo'lmasligi kerak va bu yerda bu ONGLI qaror.
        orphan = _purge_audit(a.yes)
        if orphan:
            mark = "o'chirildi" if a.yes else "o'chiriladi"
            print(f"  {orphan:>4} audit jurnali yozuvi (hujjati yo'q) — {mark}")
            total += orphan

        if not total:
            print("  Belgili yozuv topilmadi — baza toza.")
        else:
            print(f"\nJami: {total} ta yozuv.")
            if not a.yes:
                print("Hech narsa o'chirilmadi. Bajarish uchun: --yes")

        # Tender-AI dagi demo ma'lumot BU YERDAN tozalanmaydi — chegara
        # qoidasi (`public.*` ga tegilmaydi). Faqat eslatib qo'yamiz.
        pub = db.scalar(
            "SELECT count(*) FROM public.catalog_product "
            "WHERE name ILIKE ANY(%(pats)s)",
            {"pats": [f"%{m}%" for m in markers]}) or 0
        if pub:
            print(f"\nDIQQAT: tender-ai katalogida ham {pub} ta belgili "
                  f"yozuv bor.\nUlar BU SKRIPT BILAN o'chirilmaydi "
                  f"(`public.*` ERP niki emas) — tender-ai interfeysidan "
                  f"yoki o'sha loyihadan tozalang.")
        return 0
    finally:
        db.close_pool()


if __name__ == "__main__":
    sys.exit(main())
