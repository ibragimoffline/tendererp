"""ERP 24-patch: kartaga SABAB HUJJATINI biriktirish.

Nima uchun bor: `lost_reason` — ro'yxatdan bitta kod (narx, muddat,
hujjat...). U tasniflash uchun yetarli, lekin "aynan nima bo'ldi" degan
savolga javob bermaydi. Tafsilot esa odatda hujjatda bo'ladi: buyurtmachi
xati, raqobatchi narxi, ichki xizmat yozuvi.

CHEGARALAR — grill sessiyasida (2026-09-04) qulflangan:

  * Fayl BAZADA (`bytea`), diskda emas. `backup_erp.ps1` faqat `pg_dump`
    qiladi va diskdagi papkani ZAXIRALAMAYDI — fayl jimgina yo'qolardi.
  * Fayl IXTIYORIY. Majburiy qilinsa broker bo'sh fayl yuklab o'tib
    ketadi; "hujjat bor" degan YOLG'ON ko'rsatkich hujjat umuman
    bo'lmaganidan yomonroq. Yo'qligi ekranda ochiq yoziladi, qamrovi
    esa `qamrov()` bilan sanaladi.
  * Fayl `lost_reason` ning O'RNINI BOSMAYDI: kod tasniflash uchun,
    fayl tafsilot uchun. Faylni `GROUP BY` qilib bo'lmaydi, ya'ni sabab
    faylga ko'chsa `analytics.py` dagi statistika o'lardi.
  * O'chirish MUMKIN (xato yuklashni tuzatish kerak), lekin iz o'chmaydi:
    `erp.doc_audit` ga trigger yozadi va u jurnal O'ZGARMAYDI.

Bu modul `public.*` ga na yozadi, na o'qiydi.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import (SABAB_HOLATLARI, STATUS_LABEL, ErpError,
                                 _iso, _need_schema)

#: Bir fayl uchun eng katta hajm. Bazada ham CHECK bor (24-patch) —
#: ilova chetlab o'tilsa chegara baribir ishlaydi.
MAX_HAJM = 10 * 1024 * 1024

#: Ruxsat etilgan turlar: kengaytma -> mime.
#:
#: OQ RO'YXAT, qora emas. Qora ro'yxat "nimani unutdik" degan savolni
#: har doim ochiq qoldiradi; oq ro'yxatda esa yangi tur SO'RALGANDA
#: qo'shiladi va bu ko'rinadigan qaror bo'ladi.
TURLAR: Dict[str, str] = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument."
             "wordprocessingml.document",
    ".xls":  "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}

#: Fayl BIRIKTIRILADIGAN holatlar. Funksiya "nega yakunlanmadi" degan
#: savolga javob uchun so'ralgan, ya'ni ochiq kartada uning ma'nosi yo'q.
#:
#: Ro'yxat `opportunity.SABAB_HOLATLARI` dan KELADI, bu yerda
#: takrorlanmaydi: `lost_reason` kodi va sabab hujjati bir xil uchta
#: holatga tegishli va ular ajralib ketmasligi kerak.
#:
#: O'CHIRISH esa har qanday holatda mumkin: karta qayta ochilgan bo'lsa
#: ham xato yuklangan fayl ushlanib qolmasligi kerak.
YOPIQ_HOLATLAR = SABAB_HOLATLARI


# ---------------------------------------------------------------------------
# Sxema tayyorligi (24-patch alohida qo'llanadi)
# ---------------------------------------------------------------------------
_SCHEMA24_READY = False

SCHEMA24_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'opportunity_file'
"""


def schema_ready() -> bool:
    global _SCHEMA24_READY
    if _SCHEMA24_READY:
        return True
    _SCHEMA24_READY = bool(db.query_one(SCHEMA24_CHECK_SQL))
    return _SCHEMA24_READY


def _need_schema24() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Karta fayllari jadvali yo'q: schema_patch_erp_24.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# So'rovlar — `baytlar` ATAYLAB ro'yxatda yo'q
# ---------------------------------------------------------------------------
# `SELECT *` hech qayerda ishlatilmaydi: 10 MB lik ustun tasodifan
# ro'yxat javobiga tushsa, interfeys sekinlashgani ham sezilmasdi.
META_COLS = ("id, opportunity_id, fayl_nom, mime, hajm, sha256, izoh, "
             "created_by, created_at")

LIST_SQL = f"""
SELECT {META_COLS} FROM erp.opportunity_file
WHERE opportunity_id = %(opp)s
ORDER BY created_at DESC, id DESC
"""

ONE_SQL = f"SELECT {META_COLS} FROM erp.opportunity_file WHERE id = %(id)s"

BYTES_SQL = ("SELECT fayl_nom, mime, hajm, baytlar FROM erp.opportunity_file "
             "WHERE id = %(id)s")

INSERT_SQL = """
INSERT INTO erp.opportunity_file
    (opportunity_id, fayl_nom, mime, hajm, sha256, izoh, baytlar, created_by)
VALUES (%(opp)s, %(nom)s, %(mime)s, %(hajm)s, %(sha)s, %(izoh)s,
        %(baytlar)s, %(kim)s)
RETURNING id
"""

DELETE_SQL = "DELETE FROM erp.opportunity_file WHERE id = %(id)s RETURNING id"

OPP_STATUS_SQL = "SELECT id, status FROM erp.opportunity WHERE id = %(id)s"

# Qamrov: YOPILGAN kartalarning nechtasida sabab hujjati bor.
#
# Maxrajda faqat `YOPIQ_HOLATLAR`: `won` da sabab hujjati kutilmaydi,
# uni maxrajga qo'shish foizni sun'iy pasaytirardi.
QAMROV_SQL = """
SELECT count(*)                                        AS yopiq_n,
       count(*) FILTER (WHERE f.n > 0)                 AS fayli_bor_n
FROM erp.opportunity o
LEFT JOIN LATERAL (
    SELECT count(*) AS n FROM erp.opportunity_file x
    WHERE x.opportunity_id = o.id
) f ON true
WHERE o.status = ANY(%(holatlar)s)
"""


def _shape(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"],
        "fayl_nom": r["fayl_nom"], "mime": r["mime"], "hajm": r["hajm"],
        "sha256": r["sha256"], "izoh": r["izoh"],
        "created_by": r["created_by"], "created_at": _iso(r["created_at"]),
    }


def kengaytma(nom: str) -> str:
    return os.path.splitext(nom or "")[1].lower()


# ---------------------------------------------------------------------------
# Amallar
# ---------------------------------------------------------------------------
def royxat(opp_id: int) -> List[Dict[str, Any]]:
    """Kartaning fayllari — FAQAT metadata, baytlarsiz."""
    _need_schema24()
    return [_shape(r) for r in db.query(LIST_SQL, {"opp": opp_id})]


def qosh(opp_id: int, fayl_nom: str, baytlar: bytes,
         izoh: Optional[str] = None, kim: Optional[str] = None) -> Dict[str, Any]:
    """Fayl biriktiradi.

    Har rad etish SABAB bilan qaytadi: "yaroqsiz fayl" degan xabar
    foydalanuvchiga nima qilishni aytmaydi."""
    _need_schema24()

    opp = db.query_one(OPP_STATUS_SQL, {"id": opp_id})
    if not opp:
        raise ErpError("Karta topilmadi.", 404)
    if opp["status"] not in YOPIQ_HOLATLAR:
        nomlar = ", ".join(sorted(STATUS_LABEL[s] for s in YOPIQ_HOLATLAR))
        raise ErpError(
            f"Sabab hujjati faqat yakunlanmagan kartaga biriktiriladi "
            f"({nomlar}). Hozirgi holat: '{STATUS_LABEL[opp['status']]}'.", 409)

    nom = (fayl_nom or "").strip()
    if not nom:
        raise ErpError("Fayl nomi bo'sh.")
    kengay = kengaytma(nom)
    if kengay not in TURLAR:
        raise ErpError(
            f"'{kengay or nom}' turi qabul qilinmaydi. Ruxsat etilgan: "
            + ", ".join(sorted(TURLAR)))
    if not baytlar:
        raise ErpError("Fayl bo'sh (0 bayt).")
    if len(baytlar) > MAX_HAJM:
        raise ErpError(
            f"Fayl {len(baytlar) / 1048576:.1f} MB — chegara "
            f"{MAX_HAJM // 1048576} MB.")

    sha = hashlib.sha256(baytlar).hexdigest()
    # Takror yuklash — deyarli har doim ikki marta bosilgan tugma.
    # Bazada UNIQUE bor; bu yerda uni OLDINDAN ushlaymiz, chunki
    # 500 emas, tushunarli xabar qaytishi kerak.
    for mavjud in db.query(LIST_SQL, {"opp": opp_id}):
        if mavjud["sha256"] == sha:
            raise ErpError(
                f"Bu fayl allaqachon biriktirilgan: '{mavjud['fayl_nom']}'.",
                409, mavjud_id=mavjud["id"])

    # `actor` SHART: usiz `doc_audit` da `actor IS NULL` qoladi va u
    # "ERP dan tashqarida o'zgartirilgan" degan MA'NONI bildiradi
    # (`api/db.py`). Ya'ni o'z yozuvimizni begona qilib ko'rsatardik.
    row = db.execute_returning(INSERT_SQL, {
        "opp": opp_id, "nom": nom, "mime": TURLAR[kengay], "hajm": len(baytlar),
        "sha": sha, "izoh": (izoh or "").strip() or None,
        "baytlar": baytlar, "kim": kim}, actor=kim)
    return _shape(db.query_one(ONE_SQL, {"id": row["id"]}))


def baytlar_olish(file_id: int) -> Dict[str, Any]:
    """Yuklab olish uchun: nom, mime va faylning O'ZI."""
    _need_schema24()
    r = db.query_one(BYTES_SQL, {"id": file_id})
    if not r:
        raise ErpError("Fayl topilmadi.", 404)
    return {"fayl_nom": r["fayl_nom"], "mime": r["mime"], "hajm": r["hajm"],
            "baytlar": bytes(r["baytlar"])}


def ochir(file_id: int, kim: Optional[str] = None) -> Dict[str, Any]:
    """O'chiradi. IZ QOLADI: `doc_audit` triggeri kim/qachon/qaysi faylni
    yozadi va u jurnal o'zgartirilmaydi (`doc_audit_guard`).

    Karta holati TEKSHIRILMAYDI: qayta ochilgan kartada ham xato
    yuklangan fayl ushlanib qolmasligi kerak."""
    _need_schema24()
    meta = db.query_one(ONE_SQL, {"id": file_id})
    if not meta:
        raise ErpError("Fayl topilmadi.", 404)
    db.execute_returning(DELETE_SQL, {"id": file_id}, actor=kim)
    return {"ochirildi": True, "id": file_id,
            "fayl_nom": meta["fayl_nom"], "opportunity_id": meta["opportunity_id"]}


def qamrov() -> Dict[str, Any]:
    """"Yopilgan N kartadan M tasida sabab hujjati bor."

    `UPDATED.md` §18 naqshi: funksiya ishlatilyaptimi degan savolga
    RAQAM bilan javob. Foiz MINIMAL NAMUNAsiz chiqmaydi — 2 ta yopiq
    kartada "50%" ma'nosiz raqam, u "1/2" bo'lib ko'rinishi kerak."""
    _need_schema24()
    r = db.query_one(QAMROV_SQL, {"holatlar": sorted(YOPIQ_HOLATLAR)})
    yopiq = int(r["yopiq_n"] or 0)
    bor = int(r["fayli_bor_n"] or 0)
    return {
        "yopiq_n": yopiq, "fayli_bor_n": bor,
        # 10 dan kam bo'lsa foiz BERILMAYDI: `MOSLIK_MIN` bilan bir qoida.
        "foiz": round(100.0 * bor / yopiq, 1) if yopiq >= 10 else None,
        "min_namuna": 10,
    }
