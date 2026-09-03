"""
EGALIK — "o'z kartalari" degan huquq darajasining ma'nosi.

    from api.erp import egalik
    egalik.oz_broker_id(user)              # kim (erp.broker.id) yoki None
    egalik.tegishli(user, "invoice", 12)   # shu hujjat shu odamnikimi

MUAMMO: huquqlar matritsasida (`api/erp/perm.py`) broker uchun ko'p
qatorda `own` turadi — "faqat o'ziga biriktirilgani". Lekin matritsa
faqat AMALNI biladi, OBYEKTNI bilmaydi: "kartani tahrirlash mumkin"
deydi, "shu kartani" demaydi. Filtr kiritilmaguncha `own` amalda
`full` kabi ishlardi va broker begona kartani ham ocha olardi.

YECHIM: egalik zanjiri BITTA joyda. Har bir obyekt uchun "bu kimniki"
degan savol bitta `EXISTS` so'roviga aylanadi va javob KARTAGA borib
taqaladi — chunki ERP da ishning egasi karta orqali belgilanadi.

EGALIK QANDAY ANIQLANADI:

    erp.app_user.broker_id  ->  erp.broker.id  ->  erp.opportunity.broker_id

Ya'ni HISOB hodimga bog'langan bo'lsa, o'sha hodimga biriktirilgan
kartalar — "o'ziniki". Bu zanjir yangi ustun talab qilmaydi: u
1-bosqichdan beri bor va hamma kartada to'ldirilgan.

    (`assignee_id` — Tender-AI yo'naltirishi bilan keladi va o'shanda
    `app_user` ga to'g'ridan-to'g'ri bog'lanadi. Hozir uni qo'shish
    ikkita "ega" ustuni degani bo'lardi va ular ajralib ketardi.)

HISOB HODIMGA BOG'LANMAGAN BO'LSA (`broker_id IS NULL`) — "o'ziniki"
BO'SH to'plam: ro'yxatlar bo'sh keladi, obyektlar 403 beradi. Bu
ATAYLAB va JIM EMAS: interfeys "hisobingiz hodimga bog'lanmagan" deb
ochiq aytadi (`erp.app_user` da `broker_id` ni administrator qo'yadi).
Muqobili — bunday hisobga HAMMASINI ko'rsatish bo'lardi, ya'ni
sozlamadagi kamchilik maxfiylik teshigiga aylanardi.

FAKTURA VA AKTDA karta bo'lmasligi mumkin (mijozdan to'g'ridan-to'g'ri
chiqarilgan). U holda egalik MIJOZ orqali: "shu mijoz bilan mening
kartam bormi". Aks holda broker o'zi yaratgan fakturani o'zi ko'ra
olmay qolardi.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from api import db
from api.erp.opportunity import ErpError

#: Obyekt turi -> "shu obyekt shu hodimniki" so'rovi.
#:
#: Har biri `%(id)s` (obyekt) va `%(b)s` (hodim) oladi va bitta `ok`
#: ustunini qaytaradi. So'rovlar ATAYLAB `EXISTS` bilan: "topilmadi" va
#: "meniki emas" farqi bu qatlamda kerak emas — ikkalasi ham "yo'q".
TEGISHLI_SQL: Dict[str, str] = {
    "opportunity": """
        SELECT EXISTS (SELECT 1 FROM erp.opportunity o
                        WHERE o.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    "task": """
        SELECT EXISTS (SELECT 1 FROM erp.opportunity_task t
                         JOIN erp.opportunity o ON o.id = t.opportunity_id
                        WHERE t.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    "contract": """
        SELECT EXISTS (SELECT 1 FROM erp.contract k
                         JOIN erp.opportunity o ON o.id = k.opportunity_id
                        WHERE k.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    "reserve": """
        SELECT EXISTS (SELECT 1 FROM erp.stock_reserve r
                         JOIN erp.opportunity o ON o.id = r.opportunity_id
                        WHERE r.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    # Karta bo'lmasa — mijoz orqali (yuqoridagi izoh).
    "invoice": """
        SELECT EXISTS (
            SELECT 1 FROM erp.invoice i
             WHERE i.id = %(id)s
               AND (EXISTS (SELECT 1 FROM erp.opportunity o
                             WHERE o.id = i.opportunity_id AND o.broker_id = %(b)s)
                OR (i.opportunity_id IS NULL AND EXISTS (
                        SELECT 1 FROM erp.opportunity o
                         WHERE o.client_id = i.client_id AND o.broker_id = %(b)s)))
        ) AS ok""",
    "payment": """
        SELECT EXISTS (
            SELECT 1 FROM erp.invoice_payment p
              JOIN erp.invoice i ON i.id = p.invoice_id
             WHERE p.id = %(id)s
               AND (EXISTS (SELECT 1 FROM erp.opportunity o
                             WHERE o.id = i.opportunity_id AND o.broker_id = %(b)s)
                OR (i.opportunity_id IS NULL AND EXISTS (
                        SELECT 1 FROM erp.opportunity o
                         WHERE o.client_id = i.client_id AND o.broker_id = %(b)s)))
        ) AS ok""",
    "act": """
        SELECT EXISTS (
            SELECT 1 FROM erp.act a
             WHERE a.id = %(id)s
               AND (EXISTS (SELECT 1 FROM erp.opportunity o
                             WHERE o.id = a.opportunity_id AND o.broker_id = %(b)s)
                OR (a.opportunity_id IS NULL AND EXISTS (
                        SELECT 1 FROM erp.opportunity o
                         WHERE o.client_id = a.client_id AND o.broker_id = %(b)s)))
        ) AS ok""",
    # Sabab hujjati — kartasi orqali (24-patch).
    "opportunity_file": """
        SELECT EXISTS (SELECT 1 FROM erp.opportunity_file f
                         JOIN erp.opportunity o ON o.id = f.opportunity_id
                        WHERE f.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    # Mijoz "meniki" — u bilan kartam bo'lsa.
    "client": """
        SELECT EXISTS (SELECT 1 FROM erp.opportunity o
                        WHERE o.client_id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    "client_contact": """
        SELECT EXISTS (SELECT 1 FROM erp.client_contact k
                         JOIN erp.opportunity o ON o.client_id = k.client_id
                        WHERE k.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
    "client_document": """
        SELECT EXISTS (SELECT 1 FROM erp.client_document d
                         JOIN erp.opportunity o ON o.client_id = d.client_id
                        WHERE d.id = %(id)s AND o.broker_id = %(b)s) AS ok""",
}

#: Xato matnida obyekt turi odam tilida chiqsin.
NOMI = {
    "opportunity": "karta", "task": "vazifa", "contract": "shartnoma",
    "reserve": "rezerv", "invoice": "faktura", "payment": "to'lov",
    "act": "dalolatnoma", "client": "mijoz",
    "client_contact": "aloqa shaxsi", "client_document": "mijoz hujjati",
    "opportunity_file": "sabab hujjati",
}

BOGLANMAGAN = ("Hisobingiz hodimga bog'lanmagan, shuning uchun "
               "\"o'z ishlarim\" bo'sh. Administrator hisobni hodimga "
               "bog'lashi kerak (Hodimlar ekrani).")


def oz_broker_id(user: Dict[str, Any]) -> Optional[int]:
    """Kirgan odamning HODIM yozuvi (`erp.broker.id`) yoki `None`."""
    return (user or {}).get("broker_id")


def tegishli(user: Dict[str, Any], kind: str, obj_id: Any) -> bool:
    """Shu obyekt shu odamnikimi.

    Noma'lum tur — DASTURCHI xatosi (`perm.can` dagi bilan bir xil
    sabab): jimgina "yo'q" desak, yangi obyekt turi qo'shilganda u
    hech kimga ko'rinmay qolardi va sababi topilmasdi."""
    if kind not in TEGISHLI_SQL:
        raise KeyError(f"Noma'lum obyekt turi: {kind!r} (api/erp/egalik.py)")
    b = oz_broker_id(user)
    if not b or obj_id is None:
        return False
    return bool(db.scalar(TEGISHLI_SQL[kind], {"id": obj_id, "b": b}))


def talab(user: Dict[str, Any], kind: str, obj_id: Any) -> None:
    """Tegishli bo'lmasa 403 — sabab bilan.

    404 EMAS: "yo'q" bilan "meniki emas" ni ajratib ko'rsatish begona
    kartaning MAVJUDLIGINI aytib qo'yardi. Ikkalasi ham bir xil javob
    beradi."""
    if tegishli(user, kind, obj_id):
        return
    if not oz_broker_id(user):
        raise ErpError(BOGLANMAGAN, 403)
    raise ErpError(f"Bu {NOMI.get(kind, kind)} sizga biriktirilmagan.", 403)
