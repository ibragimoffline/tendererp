"""
MUHIT — bu o'rnatma qaysi: ishlab chiqarish, staging yoki ishlab chiqish.

    from api import muhit
    muhit.nomi()        # 'prod' | 'staging' | 'dev' | None
    muhit.prodmi()      # True bo'lsa - HAQIQIY ma'lumot

MUAMMO: `.env` da bitta `XT_DB_DSN` bor va u qaysi bazani ko'rsatayotgani
FAQAT satrning o'zidan ko'rinadi. Staging qo'shilganda ikkita fayl
paydo bo'ladi (`.env`, `.env.staging`) va ular ALMASHIB KETISHI
mumkin: nusxa olinadi, tahrirlanadi, biri ikkinchisining ustiga
yoziladi. Natija — sinov skripti ishlab chiqarish bazasiga yozadi.

Bu xato JIM: sinov o'zidan keyin tozalaydi va ekranda hech narsa
ko'rinmaydi. Lekin `erp.doc_audit` — faqat qo'shiladigan jurnal
(`doc_audit_guard`), ya'ni u yerdagi iz QAYTARILMAYDI. Ya'ni
"tozaladim" degani "izsiz" degani emas.

YECHIM: muhit O'ZINI NOM BILAN aytadi (`ERP_MUHIT`), DSN satridan
taxmin qilinmaydi. Baza nomi o'zgarishi mumkin, nom esa qaror.

QULF QANDAY ISHLAYDI
════════════════════
`db.init_pool()` chaqirilganda tekshiriladi: agar muhit `prod` bo'lsa
va ishga tushirilgan skript SINOV bo'lsa — ulanish RAD ETILADI.

Sinov ekani FAYL NOMIDAN aniqlanadi (`*_test.py` yoki `_tests/`
ichidan). Nega shunday: qulfni har sinov faylida qo'lda chaqirish
kerak bo'lsa, u ertami-kechmi UNUTILADI — va aynan unutilgan
faylda ishlab chiqarish bazasiga yoziladi. Bu yerda esa yangi
sinov fayli qulfni AVTOMATIK oladi.

BAYROQ BILAN CHETLAB O'TIB BO'LMAYDI va bu ataylab: `--tasdiq`
kabi bayroq bir marta yozilgach odat bo'lib qoladi. Haqiqatan
kerak bo'lsa `ERP_MUHIT` o'zgartiriladi — bu ancha ongli amal.

NOM QO'YILMAGAN BO'LSA
══════════════════════
Qulf ISHLAMAYDI, lekin ogohlantirish chiqadi va `check_setup.py`
buni kamchilik sifatida ko'rsatadi.

Nega qattiq to'silmaydi: bugungi barcha o'rnatmalarda `ERP_MUHIT`
yo'q va uni majburiy qilish hamma sinovni bir zarbada to'xtatardi —
shundan keyin birinchi qilinadigan ish qulfni o'chirish bo'lardi.
Xavfsizlik chorasi ishlashga xalaqit bersa, u o'chiriladi; shuning
uchun u bosqichma-bosqich kiritiladi.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

#: `ERP_MUHIT` uchun tanilgan qiymatlar. Boshqasi — nom qo'yilmagan
#: deb hisoblanadi (xato emas, lekin qulf ham ishlamaydi).
PROD = "prod"
STAGING = "staging"
DEV = "dev"

#: Bir xil ma'noli yozilishlar. Odam `production` deb yozishi mumkin
#: va u `prod` bilan bir xil narsa — buni tanimaslik qulfni jimgina
#: o'chirib qo'yardi.
NOMLAR = {
    "prod": PROD, "production": PROD, "ishlab_chiqarish": PROD,
    "staging": STAGING, "stage": STAGING, "sinov_muhiti": STAGING,
    "dev": DEV, "development": DEV, "local": DEV, "ishlab_chiqish": DEV,
}

_ogohlantirildi = False


def nomi() -> Optional[str]:
    """`prod` / `staging` / `dev`, yoki nom qo'yilmagan bo'lsa `None`."""
    xom = (os.environ.get("ERP_MUHIT") or "").strip().lower()
    return NOMLAR.get(xom)


def prodmi() -> bool:
    """ISHLAB CHIQARISH ekani ANIQ aytilganmi.

    Nom qo'yilmagan bo'lsa `False`: taxmin qilinmaydi. Taxmin
    ikki tomonga ham xato bo'lardi — ishlab chiqishni to'sib
    qo'yish yoki ishlab chiqarishni ochiq qoldirish."""
    return nomi() == PROD


def tavsif() -> str:
    """Ekranda ko'rsatish uchun: muhit + baza nomi.

    Baza nomi ham qo'shiladi, chunki eng ko'p uchraydigan xato
    aynan shu ikkisining mos kelmasligi: `.env` da `staging`
    yozilgan, DSN esa ishlab chiqarish bazasini ko'rsatadi."""
    m = nomi() or "noma'lum"
    return f"{m} (baza: {baza_nomi() or '—'})"


def baza_nomi() -> Optional[str]:
    """DSN dagi `dbname`. Faqat KO'RSATISH uchun — qaror uchun emas."""
    for qism in (os.environ.get("XT_DB_DSN") or "").split():
        if qism.startswith("dbname="):
            return qism.split("=", 1)[1]
    return None


# ---------------------------------------------------------------------------
# Qulf
# ---------------------------------------------------------------------------
class ProdQulfi(SystemExit):
    """Ishlab chiqarish bazasiga sinov ulanmoqchi bo'ldi.

    `SystemExit` DAN meros va bu ONGLI qaror: sinov fayllari
    `db.init_pool()` ni `except Exception` bilan o'rab oladi
    ("bazasiz sinov" holati uchun). Oddiy `RuntimeError` bo'lsa,
    qulf ishga tushardi-yu, sinov uni YUTIB YUBORARDI va ekranda
    "0 ta xato" deb chiqardi — ya'ni darvoza MUVAFFAQIYAT deb
    hisoblanardi, aslida hech narsa tekshirilmagan holda.

    Bu loyihaning o'z saboqi (`_tests/fixture.py` sarlavhasi):
    "sinov 'hammasi joyida' deydi, lekin aslida yarmini
    tekshirmayapti" — eng yomon holat.

    `SystemExit` ni `except Exception` USHLAMAYDI, ya'ni jarayon
    nolinchi bo'lmagan kod bilan tugaydi va skript buni ko'radi."""


def sinovmi() -> bool:
    """Ishga tushirilgan skript SINOVMI.

    Fayl nomidan aniqlanadi: `*_test.py` yoki `_tests/` ichidagi
    istalgan skript. Moduldagi izohga qarang — nega qo'lda emas."""
    yol = os.path.abspath(sys.argv[0] if sys.argv else "")
    if not yol:
        return False
    nom = os.path.basename(yol)
    if nom.endswith("_test.py"):
        return True
    return os.path.basename(os.path.dirname(yol)) == "_tests"


def qulf_tekshir() -> None:
    """Ishlab chiqarishda sinov ulanishini RAD etadi.

    `db.init_pool()` dan chaqiriladi — ya'ni har qanday sinov,
    shu jumladan hali yozilmagani ham, shu qulfdan o'tadi."""
    global _ogohlantirildi
    if not sinovmi():
        return
    if prodmi():
        # Sabab `stderr` ga ALOHIDA yoziladi: `SystemExit` matni
        # ba'zi qobiqlarda ko'rinmay qolishi mumkin, sabab esa
        # KO'RINISHI shart.
        print(f"\nTO'XTATILDI: ISHLAB CHIQARISH muhiti "
              f"({tavsif()}) — sinov yuritilmaydi.",
              file=sys.stderr)
        raise ProdQulfi(
            f"TO'XTATILDI: bu ISHLAB CHIQARISH muhiti ({tavsif()}).\n"
            "Sinovlar haqiqiy yozuv yaratadi va `erp.doc_audit`\n"
            "jurnalida QAYTARIB BO'LMAYDIGAN iz qoldiradi\n"
            "(tozalash ishlagan taqdirda ham).\n\n"
            "Sinovni staging'da yuriting:\n"
            "  $env:XT_DB_DSN = '...dbname=xtxarid_staging...'\n"
            "  $env:ERP_MUHIT = 'staging'\n\n"
            "Bayroq bilan chetlab o'tib bo'lmaydi — `ERP_MUHIT`\n"
            "o'zgartirilishi kerak (api/muhit.py dagi izoh).")
    if nomi() is None and not _ogohlantirildi:
        _ogohlantirildi = True
        print(f"  DIQQAT: ERP_MUHIT qo'yilmagan (baza: {baza_nomi() or '—'}).\n"
              "          Ishlab chiqarish qulfi ISHLAMAYDI. `.env` ga\n"
              "          ERP_MUHIT=dev yoki staging yozing.",
              file=sys.stderr)
