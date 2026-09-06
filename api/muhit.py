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

IKKI MANBA, CHUNKI `.env` NING O'ZI ALMASHIB KETADI
═══════════════════════════════════════════════════
`ERP_MUHIT` — `.env` da. Lekin qo'riqlanayotgan xavf AYNAN o'sha
faylning almashib ketishi: agar `.env` yolg'on gapirsa, faqat unga
qaragan qulf ham aldanadi. Ya'ni bir manba yetarli emas.

Shuning uchun ikkinchi manba — BAZANING O'ZI: `erp.setting` da
`muhit` kaliti. U ma'lumot bilan BIRGA yuradi va `.env` bilan
alohida sayohat qiladi.

    .env  aytadi:  staging          <- almashib ketishi mumkin
    baza  aytadi:  prod             <- ma'lumot bilan birga

Ikkisi ZID bo'lsa — bu aniq xato va u to'xtatiladi. Bittasi
ikkinchisini "tasdiqlaydi" degan holat yo'q: mos kelmaslik
o'zi javob.

ZAXIRADAN TIKLASHDA belgi HAM KO'CHADI: ishlab chiqarish nusxasi
staging'ga tiklansa, baza hamon "prod" deb turadi. Bu NUQSON EMAS,
xususiyat: `staging_setup.ps1` uni qayta belgilaydi va belgilashni
unutgan staging DARHOL to'xtaydi (xavfsiz tomonga xato).

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


#: Bazadagi belgi qayerda turadi. `erp.setting` — MAVJUD jadval
#: (18-patch) va u aynan "shu o'rnatmaning qarori" uchun. Yangi
#: jadval ochish ikkinchi haqiqat manbai bo'lardi.
#:
#: `sozlama.py` bu kalitni BILMAYDI va bu xavfsiz: u noma'lum
#: kalitni jimgina e'tiborsiz qoldiradi (18-patch izohi). Kalit
#: u yerga qo'shilmadi, chunki `sozlama.py` qiymatlarni BOOLEAN
#: deb o'qiydi, bu esa matn.
BAZA_KALIT = "muhit"

BAZA_OQISH_SQL = ("SELECT value FROM erp.setting WHERE key = %(k)s")
BAZA_YOZISH_SQL = """
INSERT INTO erp.setting (key, value, updated_by)
VALUES (%(k)s, %(v)s, %(kim)s)
ON CONFLICT (key) DO UPDATE
    SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
        updated_at = now()
RETURNING key, value
"""


def baza_muhiti() -> Optional[str]:
    """BAZANING O'ZI nima deydi. Belgilanmagan bo'lsa `None`.

    HECH QACHON YIQITMAYDI: jadval yo'q (18-patch qo'llanmagan),
    ulanish yo'q yoki huquq yetmaydi — hammasi `None`. Belgi
    yo'qligi ishni to'xtatmaydi, u faqat qulfni ochiq qoldiradi
    va buni `check_setup.py` ko'rsatadi."""
    try:
        from api import db
        r = db.query_one(BAZA_OQISH_SQL, {"k": BAZA_KALIT})
    except Exception:                               # noqa: BLE001
        return None
    if not r:
        return None
    return NOMLAR.get((r["value"] or "").strip().lower())


def baza_belgila(nom: str, kim: Optional[str] = None) -> str:
    """Bazani belgilaydi. Qaytadi: normallashtirilgan nom.

    Buyruq satridan:  python -m api.muhit --belgila prod"""
    tozalangan = NOMLAR.get((nom or "").strip().lower())
    if not tozalangan:
        raise ValueError(
            f"Noma'lum muhit: {nom!r}. Mumkin: prod, staging, dev")
    from api import db
    db.execute_returning(BAZA_YOZISH_SQL,
                         {"k": BAZA_KALIT, "v": tozalangan,
                          "kim": kim or "muhit CLI"})
    return tozalangan


def moslik() -> tuple:
    """`.env` va BAZA bir narsani aytyaptimi.

    Qaytadi: `(holat, xabar)`, holat —
        'ok'        ikkalasi bor va mos;
        'zid'       ikkalasi bor, LEKIN mos emas -> to'xtatish;
        'env_yoq'   `.env` da nom yo'q;
        'baza_yoq'  bazada belgi yo'q.

    Qaror QABUL QILMAYDI — faqat holatni aytadi. Nima qilish
    kerakligini chaqiruvchi hal qiladi (`check_setup.py` da
    ishlab chiqarish uchun XATO, ishlab chiqish uchun ogohlantirish)."""
    e, b = nomi(), baza_muhiti()
    if e and b and e != b:
        return ("zid",
                f".env '{e}' deydi, baza '{b}' deydi "
                f"(baza: {baza_nomi() or '—'})")
    if not e:
        return ("env_yoq", f"ERP_MUHIT qo'yilmagan "
                           f"(baza: {baza_nomi() or '—'})")
    if not b:
        return ("baza_yoq", f".env '{e}' deydi, baza belgilanmagan")
    return ("ok", f"{e} (baza: {baza_nomi() or '—'})")


def darvoza(kutilgan: str) -> tuple:
    """DEPLOY DARVOZASI: muhit AYNAN kutilganidekmi.

        muhit.darvoza("prod")     # ishlab chiqarishga chiqishdan oldin
        muhit.darvoza("staging")  # staging'ga chiqishdan oldin

    Qaytadi: `(holat, xabar)`, holat `'ok'` yoki `'mos_emas'`.

    NEGA `moslik()` YETARLI EMAS: u faqat ikki manba BIR-BIRIGA
    mos ekanini aytadi. Lekin ikkalasi ham `staging` bo'lgan
    o'rnatmaga "ishlab chiqarish deploy" qilish ham xato — mos,
    lekin NOTO'G'RI muhit. Darvoza esa "qaysi muhitga chiqyapmiz"
    degan NIYATNI ham hisobga oladi.

    Amalda bu noto'g'ri DSN bilan deploy qilishni to'sadi: skript
    `--kutilgan prod` bilan yuritiladi, `.env` esa staging bazasini
    ko'rsatib turadi — darvoza o'tkazmaydi.

    IKKALASI HAM TEKSHIRILADI. "Yo'q" ham mos kelmaslik sanaladi:
    belgisiz muhitga deploy qilish — qulfning ikkinchi qavatisiz
    deploy qilish demakdir."""
    k = NOMLAR.get((kutilgan or "").strip().lower())
    if not k:
        return ("mos_emas",
                f"Noma'lum kutilgan muhit: {kutilgan!r}. "
                f"Mumkin: prod, staging, dev")
    e, b = nomi(), baza_muhiti()
    if e == k and b == k:
        return ("ok", f"{k} (baza: {baza_nomi() or '—'})")
    kamchilik = []
    if e != k:
        kamchilik.append(f".env '{e or 'yo`q'}' (kutilgan: '{k}')")
    if b != k:
        kamchilik.append(f"baza '{b or 'belgilanmagan'}' (kutilgan: '{k}')")
    return ("mos_emas", "; ".join(kamchilik))


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


def qulf_tekshir_baza() -> None:
    """BAZANING O'ZI aytgan narsaga qarab qulf. Ulanishdan KEYIN.

    `qulf_tekshir()` `.env` ni o'qiydi — lekin qo'riqlanayotgan
    xavf aynan `.env` ning almashib ketishi. Ya'ni u yolg'on
    gapirsa, birinchi qulf o'tkazib yuboradi.

    Bu ikkinchi qulf esa bazadan so'raydi: "sen kimsan?". Ishlab
    chiqarish bazasi o'zini o'zi himoya qiladi va `.env` da nima
    yozilganidan qat'i nazar sinovni ichkariga kiritmaydi.

    Ulanish OCHILGANDAN keyin chaqiriladi (`api/db.py`) — belgini
    o'qish uchun ulanish kerak. Qulf ishga tushsa, pool YOPILADI:
    ochiq qolgan ulanish "ruxsat berildi" degan taassurot berardi."""
    if not sinovmi():
        return
    if baza_muhiti() != PROD:
        return
    from api import db
    db.close_pool()
    print(f"\nTO'XTATILDI: BAZANING O'ZI ishlab chiqarish deb "
          f"belgilangan (baza: {baza_nomi() or '—'}).",
          file=sys.stderr)
    raise ProdQulfi(
        f"TO'XTATILDI: baza '{baza_nomi() or '—'}' ISHLAB CHIQARISH "
        f"deb belgilangan (erp.setting.muhit = 'prod').\n"
        f".env esa '{nomi() or 'nomsiz'}' deydi — ular ZID.\n\n"
        "Bu odatda noto'g'ri `.env` bilan ishga tushirishdan bo'ladi.\n"
        "Staging DSN sini tekshiring, yoki baza haqiqatan staging\n"
        "bo'lsa uni qayta belgilang:\n"
        "  python -m api.muhit --belgila staging")


def main() -> int:
    """CLI: bazani belgilash va holatni ko'rish.

        python -m api.muhit                 # holat
        python -m api.muhit --belgila prod  # bazani belgilash
    """
    import argparse
    # `.env` YUKLANADI: bu CLI mustaqil ishga tushiriladi va
    # `uvicorn` kabi uni o'zi o'qiydigan muhit yo'q.
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env"))
    ap = argparse.ArgumentParser(description="ERP muhiti")
    ap.add_argument("--belgila", metavar="MUHIT",
                    help="bazani belgilash: prod | staging | dev")
    ap.add_argument("--kutilgan", metavar="MUHIT",
                    help="deploy darvozasi: ikkalasi AYNAN shu bo'lsin")
    a = ap.parse_args()

    from api import db
    db.init_pool()
    try:
        if a.belgila:
            # OGOHLANTIRISH: `prod` deb belgilash — sinovlarni shu
            # bazada butunlay to'xtatadi. Bu ataylab qaytarib
            # bo'ladigan amal (qayta belgilash), lekin u ONGLI
            # bo'lishi kerak.
            yangi = baza_belgila(a.belgila)
            # QAYTA O'QIYMIZ, yozganimizga ishonmaymiz: huquq
            # yetmasligi, boshqa bazaga ulanish yoki tranzaksiya
            # orqaga qaytishi mumkin. "Belgiladim" deb yolg'on
            # aytish — qulfni ochiq qoldirishning eng oson yo'li.
            tasdiq = baza_muhiti()
            if tasdiq != yangi:
                print(f"XATO: belgi yozilmadi (o'qildi: "
                      f"{tasdiq or 'belgilanmagan'}).", file=sys.stderr)
                return 1
            print(f"Baza belgilandi va tasdiqlandi: "
                  f"{baza_nomi() or '—'} -> {tasdiq}")
            if tasdiq == PROD:
                print("DIQQAT: bu bazada endi SINOVLAR ishlamaydi "
                      "(api/muhit.py qulfi).")

        print(f".env:  {nomi() or '(qo`yilmagan)'}")
        print(f"baza:  {baza_muhiti() or '(belgilanmagan)'} "
              f"({baza_nomi() or '—'})")

        if a.kutilgan:
            holat, xabar = darvoza(a.kutilgan)
            print(f"darvoza ({a.kutilgan}): {holat} — {xabar}")
            return 0 if holat == "ok" else 1
        holat, xabar = moslik()
        print(f"holat: {holat} — {xabar}")
        return 1 if holat == "zid" else 0
    finally:
        db.close_pool()


if __name__ == "__main__":
    sys.exit(main())
