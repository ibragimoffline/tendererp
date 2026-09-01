"""
TIZIM SOZLAMALARI — kompaniyaga bog'liq qarorlar.

    from api.erp import sozlama
    sozlama.yoq("broker_can_close")     # True / False
    sozlama.hammasi()                   # interfeys uchun ro'yxat
    sozlama.saqla("broker_can_close", False, actor="D. Rashidova")

MUAMMO: huquqlar matritsasidagi (`api/erp/perm.py`) uch qator har
kompaniyada bir xil emas — "broker kartani o'zi yakunlaydimi",
"menejer foydani ko'radimi", "admin faqat ko'radimi". Ular kodda
o'zgarmas edi, ya'ni o'zgartirish uchun DASTURCHI kerak edi.

YECHIM: qiymat bazada (`erp.setting`), TA'RIFI esa kodda — pastdagi
`SOZLAMALAR` lug'ati. Bazada faqat O'ZGARTIRILGANLARI yotadi; qolgani
standart qiymatda ishlaydi. Shuning uchun yangi o'rnatmada hech narsa
to'ldirmasa ham tizim to'g'ri ishlaydi.

NEGA KESH: `perm.can()` har so'rovda bir necha marta chaqiriladi va
har chaqiruv uchun bazaga borish — bekorga yuk. Kesh QISQA muddatli
(`TTL`): sozlama yozilganda kesh darhol tozalanadi, boshqa jarayon
o'zgartirsa esa eng ko'pi bilan `TTL` ichida yetib boradi. Uzoq kesh
"yoqdim, lekin ishlamayapti" degan holatni yaratardi.

BAZA JAVOB BERMASA — STANDART qiymat ishlatiladi va xato YUTILMAYDI,
faqat sozlama qatlami yiqilmaydi: baza yo'q bo'lsa endpointning o'zi
baribir 503 beradi. Ya'ni bu yerda "xavfsiz tomonga" og'ish emas,
"o'rnatmadagi holatga" qaytish: standart qiymatlar bugungi xatti-
harakat bilan bir xil.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import ErpError

#: kalit -> (standart, nomi, izohi)
#:
#: Izoh interfeysda KO'RSATILADI: sozlamaning nomi "nima" degan
#: savolga javob beradi, izoh esa "yoqsam nima o'zgaradi" degan
#: savolga. Ikkinchisi bo'lmasa sozlama tegilmay qoladi.
SOZLAMALAR: Dict[str, Any] = {
    "broker_can_close": (
        True,
        "Broker kartani o'zi yakunlaydi",
        "Yoqilgan: broker o'z kartasini 'yutildi', 'yutqazildi' yoki "
        "'rad etildi' holatiga o'tkaza oladi. O'chirilgan: yakuniy "
        "qarorni faqat rahbar yoki menejer qo'yadi (broker uni "
        "'topshirildi' gacha olib boradi)."),
    "menejer_foyda": (
        True,
        "Menejer kompaniya foydasini ko'radi",
        "Yoqilgan: menejer 'Foyda' hisobotini ochadi — narx va marja "
        "haqida qaror qabul qilishi uchun kerak. O'chirilgan: foyda "
        "faqat rahbar va administratorga."),
    "admin_faqat_koradi": (
        False,
        "Administrator biznes ma'lumotni faqat ko'radi",
        "Yoqilgan: administrator karta, mijoz, ombor va pul hujjatini "
        "O'ZGARTIRA olmaydi (ko'radi). Tizim sozlovchi va pul hujjati "
        "o'zgartiruvchi bitta odam bo'lmasligi uchun. DIQQAT: yoqishdan "
        "oldin rahbar hisobi ochilgan bo'lsin, aks holda kompaniya o'z "
        "ERP siga yozolmay qoladi."),
}

#: Kesh muddati (soniya). Qisqa: sozlama kamdan-kam o'zgaradi, lekin
#: o'zgargani darhol sezilishi kerak.
TTL = 15.0

_kesh: Dict[str, str] = {}
_kesh_vaqti = 0.0

GET_SQL = "SELECT key, value FROM erp.setting"
SET_SQL = """
INSERT INTO erp.setting (key, value, updated_by, updated_at)
VALUES (%(k)s, %(v)s, %(a)s, now())
ON CONFLICT (key) DO UPDATE
   SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
       updated_at = now()
RETURNING key, value, updated_by, updated_at
"""
ROW_SQL = ("SELECT key, value, updated_by, updated_at FROM erp.setting "
           "WHERE key = %(k)s")


def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema = 'erp' AND table_name = 'setting'"))


def _yukla() -> Dict[str, str]:
    """Bazadagi qiymatlar (keshdan). Xato bo'lsa — bo'sh lug'at."""
    global _kesh, _kesh_vaqti
    if _kesh_vaqti and (time.monotonic() - _kesh_vaqti) < TTL:
        return _kesh
    try:
        _kesh = {r["key"]: r["value"] for r in db.query(GET_SQL)}
    except Exception:                           # noqa: BLE001
        # Jadval yo'q yoki baza javob bermadi -> standart qiymatlar.
        _kesh = {}
    _kesh_vaqti = time.monotonic()
    return _kesh


def kesh_tozala() -> None:
    """Keshni bekor qilish (yozgandan keyin va sinovlarda)."""
    global _kesh_vaqti
    _kesh_vaqti = 0.0


def standart(key: str) -> bool:
    if key not in SOZLAMALAR:
        raise KeyError(f"Noma'lum sozlama: {key!r} (api/erp/sozlama.py)")
    return bool(SOZLAMALAR[key][0])


def yoq(key: str) -> bool:
    """Sozlama yoqilganmi. Noma'lum kalit — dasturchi xatosi."""
    xom = _yukla().get(key)
    if xom is None:
        return standart(key)
    return xom == "true"


def hammasi() -> List[Dict[str, Any]]:
    """Interfeys uchun: qiymat, standart, nomi, izohi, kim/qachon."""
    xom = _yukla()
    out = []
    for key, (std, nomi, izoh) in SOZLAMALAR.items():
        r = None
        try:
            r = db.query_one(ROW_SQL, {"k": key}) if key in xom else None
        except Exception:                       # noqa: BLE001
            r = None
        out.append({
            "key": key, "value": yoq(key), "default": bool(std),
            "label": nomi, "help": izoh,
            "changed": key in xom,
            "updated_by": r["updated_by"] if r else None,
            "updated_at": (r["updated_at"].isoformat()
                           if r and r["updated_at"] else None),
        })
    return out


def saqla(key: str, value: bool, actor: Optional[str] = None) -> Dict[str, Any]:
    """Sozlamani yozish. Faqat e'lon qilingan kalitlar."""
    if key not in SOZLAMALAR:
        raise ErpError("Noma'lum sozlama.", 400)
    if not isinstance(value, bool):
        raise ErpError("Sozlama qiymati ha/yo'q bo'lishi kerak.", 400)
    if not schema_ready():
        raise ErpError("schema_patch_erp_18.sql qo'llanmagan.", 503)
    db.execute_returning(SET_SQL, {"k": key, "v": "true" if value else "false",
                                   "a": actor}, actor=actor)
    kesh_tozala()
    return next(x for x in hammasi() if x["key"] == key)
