"""
FAKTURA EKSPORTI — ATAYLAB BO'SH QATLAM.

NEGA BO'SH: O'zbekistonda hisob-faktura yuridik kuchga ega bo'lishi uchun
ELEKTRON shaklda (EHF), operator orqali yuboriladi — `didox`,
`faktura.uz`, soliq portali. ERP bosib chiqargan PDF soliq uchun hujjat
EMAS.

Ya'ni eksport formati texnik tanlov emas: u mijozning buxgalteri qaysi
tizimda ishlashiga bog'liq. Javob olinmaguncha kod yozish — taxminga
qurish, keyin esa uni tashlab yuborish degani.

BUGUNGI HOLAT: ERP fakturaning MA'LUMOTINI saqlaydi va ko'rsatadi
(`api/erp/invoice.py`). Yuborishni operator yoki 1C qiladi.

QACHON TO'LDIRILADI: mijozdan ikki javob olingach —
  1. qaysi operator/tizim (didox / faktura.uz / 1C);
  2. u qanday format kutadi (operator JSON API'si yoki 1C CommerceML/XML).

SHU YERGA NIMA QO'SHILADI: har format uchun bitta funksiya —
`build(invoice) -> bytes` va (kerak bo'lsa) `send(invoice) -> ticket`.
`api/erp/invoice.py` ga TEGILMAYDI: ma'lumot modeli formatdan mustaqil
qurilgan, aynan shuning uchun.

MUHIM: bu modul faktura MA'LUMOTINI o'zgartirmaydi. Eksport — o'qish
amali; chiqarilgan hujjat esa muzlatilgan (`invoice.py` dagi izohga
qarang).
"""
from __future__ import annotations

from typing import Any, Dict, List

from api.erp.opportunity import ErpError

#: Mavjud formatlar. BO'SH — yuqoridagi izohga qarang. Format qo'shilganda
#: bu yerga `("didox", "Didox (EHF)")` kabi juftlik qo'shiladi va
#: interfeys tugmani O'ZI ko'rsatadi.
FORMATS: List[tuple] = []

FORMAT_LABEL = dict(FORMATS)


def available() -> List[Dict[str, str]]:
    """Interfeys uchun: qaysi formatlar sozlangan.

    Bo'sh ro'yxat — interfeys eksport tugmasini UMUMAN ko'rsatmaydi.
    Ishlamaydigan tugma turgani yolg'on va'da bo'lardi (ERP dagi
    `ErpLink` bilan bir xil qoida)."""
    return [{"code": c, "label": l} for c, l in FORMATS]


def build(invoice: Dict[str, Any], fmt: str) -> bytes:
    """Fakturani tashqi formatga aylantirish.

    Hozircha HECH QANDAY format sozlanmagan — chaqiruvchi buni 501 ga
    aylantiradi va interfeys sababini ochiq aytadi."""
    raise ErpError(
        "Faktura eksporti hali sozlanmagan. Format mijozning buxgalteri "
        "qaysi tizimda ishlashiga bog'liq (didox / faktura.uz / 1C) — "
        "javob olingach shu yerga qo'shiladi.", 501)
