"""ERP 4-bosqich: TAKLIF paketi va TOPSHIRISH.

Chegara:
  - Narx hisobi FORMULASI va cheklist QOIDALARI tender-ai'da qoladi. ERP
    ularni O'QIYDI (`api/tenderai.py`) va qayta hisoblamaydi — ikkinchi
    formula ikkinchi haqiqat manbai bo'lardi.
  - Topshirilgan taklif MUZLATILADI: `erp.submission` yozuvi o'chirilmaydi
    va tahrirlanmaydi. Xato bo'lsa yangi versiya qo'shiladi.
  - public.* ga yozilmaydi.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from api import db, tenderai
from api.erp import clients as erp_clients
from api.erp.opportunity import ErpError, _iso, _need_schema, _num
from api.erp.opportunity import get as opp_get

# Manbadagi YAKUNIY statuslar (public.dim_status -> is_terminal). Ular
# "tender yopilgan" degani, "biz yutdik/yutqazdik" degani EMAS: manba
# g'olibni ochiq bermaydi (bazada `winner` ustuni yo'q).
SOURCE_CLOSED = {"close", "cancel", "expired", "not_realized"}


# ---------------------------------------------------------------------------
# Sxema tayyorligi
# ---------------------------------------------------------------------------
_SCHEMA4_READY = False

SCHEMA4_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'submission'
"""


def schema_ready() -> bool:
    global _SCHEMA4_READY
    if _SCHEMA4_READY:
        return True
    _SCHEMA4_READY = bool(db.query_one(SCHEMA4_CHECK_SQL))
    return _SCHEMA4_READY


def _need_schema4() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Takliflar jadvali yo'q: schema_patch_erp_4.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_SUB_COLS = ("id, opportunity_id, version, submitted_at, submitted_by, price, "
             "currency, pricing, compliance, documents, blocking_count, "
             "confirmed_note, note, created_at")

SUBS_SQL = (f"SELECT {_SUB_COLS} FROM erp.submission "
            "WHERE opportunity_id = %(id)s ORDER BY version DESC")

NEXT_VERSION_SQL = ("SELECT coalesce(max(version), 0) + 1 AS v "
                    "FROM erp.submission WHERE opportunity_id = %(id)s")

SUB_INSERT_SQL = f"""
INSERT INTO erp.submission
    (opportunity_id, version, submitted_by, price, currency, pricing,
     compliance, documents, blocking_count, confirmed_note, note)
VALUES (%(opportunity_id)s, %(version)s, %(submitted_by)s, %(price)s,
        %(currency)s, %(pricing)s, %(compliance)s, %(documents)s,
        %(blocking_count)s, %(confirmed_note)s, %(note)s)
RETURNING {_SUB_COLS}
"""


def shape(r: dict) -> dict:
    return {
        "id": r["id"], "opportunity_id": r["opportunity_id"],
        "version": r["version"], "submitted_at": _iso(r["submitted_at"]),
        "submitted_by": r["submitted_by"], "price": _num(r["price"]),
        "currency": r["currency"], "pricing": r["pricing"],
        "compliance": r["compliance"], "documents": r["documents"],
        "blocking_count": r["blocking_count"],
        "confirmed_note": r["confirmed_note"], "note": r["note"],
    }


# ---------------------------------------------------------------------------
# Taklif paketi
# ---------------------------------------------------------------------------
def package(opp_id: int) -> Dict[str, Any]:
    """Topshirishdan oldin ko'riladigan JONLI holat: narx hisobi, cheklist,
    hujjatlar va tenderning manbadagi statusi — bitta ekranda.

    Tender-AI javob bermasa ham paket QAYTADI: yiqilgan qismlar `null`
    bo'ladi va `warnings` da sababi yoziladi. Broker "hozir topshirsam
    bo'ladimi?" degan savolga baribir javob olishi kerak.
    """
    _need_schema4()
    opp = opp_get(opp_id)
    warnings: List[str] = []

    pricing = None
    try:
        pricing = tenderai.pricing(opp["tender_id"])
    except tenderai.TenderAiUnavailable as e:
        warnings.append(f"Narx hisobi olinmadi: {e}")
    if pricing is None and not warnings:
        warnings.append("Narx hisobi qilinmagan — taklif narxi qo'lda kiritiladi.")

    compliance = None
    client = opp.get("client")
    try:
        docs = erp_clients.docs_for_compliance(client["id"]) if client else None
        compliance = tenderai.compliance(opp["tender_id"], docs)
    except tenderai.TenderAiUnavailable as e:
        warnings.append(f"Cheklist olinmadi: {e}")
    except ErpError as e:
        warnings.append(f"Cheklist olinmadi: {e}")

    blocking = int((compliance or {}).get("summary", {}).get("blocking") or 0)
    if blocking:
        # OGOHLANTIRISH, taqiq emas: hujjat topshirish paytida tayyor
        # bo'lishi mumkin va qaror odamniki (erp_bosqichlar.md 4-bosqich).
        warnings.append(f"Cheklistda {blocking} ta to'siq bor — topshirish "
                        "mumkin, lekin tasdiqlash so'raladi.")

    client_docs = []
    if client:
        try:
            client_docs = erp_clients.documents(client["id"])
        except ErpError as e:
            warnings.append(f"Mijoz hujjatlari olinmadi: {e}")

    source_status = None
    try:
        t = tenderai.tender(opp["tender_id"])
        source_status = {"status": t.get("status"), "name": t.get("status_name"),
                         "closed": t.get("status") in SOURCE_CLOSED}
        if source_status["closed"]:
            warnings.append("Tender manbada yopilgan — topshirish muddati "
                            "o'tgan bo'lishi mumkin.")
    except tenderai.TenderAiUnavailable:
        pass                                    # ma'lumot yo'q — jim o'tamiz

    return {
        "opportunity": opp,
        "pricing": pricing,
        "compliance": compliance,
        "blocking": blocking,
        "documents": client_docs,
        "source": source_status,
        "warnings": warnings,
        "submissions": [shape(r) for r in db.query(SUBS_SQL, {"id": opp_id})],
        "suggested_price": _suggested_price(pricing),
        "currency": (pricing or {}).get("currency") or opp["tender"]["currency"],
    }


def _suggested_price(pricing: Optional[dict]) -> Optional[float]:
    """Smetadan taklif narxi. Qo'lda kiritilgan narx ustun turadi — u
    xodimning YAKUNIY qarori, hisob esa tavsiya."""
    if not pricing:
        return None
    if pricing.get("manual_price") is not None:
        return float(pricing["manual_price"])
    res = pricing.get("result") or {}
    totals = res.get("totals") or {}
    for key in ("offer_price", "price", "total_with_vat", "total"):
        v = totals.get(key)
        if v is not None:
            return float(v)
    return None


def list_(opp_id: int) -> List[dict]:
    _need_schema4()
    return [shape(r) for r in db.query(SUBS_SQL, {"id": opp_id})]


def submit(opp_id: int, data: dict) -> Dict[str, Any]:
    """Taklifni MUZLATADI va kartani 'submitted' ga o'tkazadi.

    Cheklistda to'siq bo'lsa `confirmed` majburiy — ogohlantirish
    ko'rsatilgani va tasdiqlangani yozib qo'yiladi (taqiq emas, dalil).
    """
    _need_schema4()
    pkg = package(opp_id)
    blocking = pkg["blocking"]
    if blocking and not data.get("confirmed"):
        raise ErpError(
            f"Cheklistda {blocking} ta to'siq bor. Topshirishni tasdiqlang "
            "(tasdiq tarixga yoziladi).", 400, blocking=blocking)

    price = data.get("price")
    if price is None:
        price = pkg["suggested_price"]
    if price is None:
        raise ErpError("Taklif narxi ko'rsatilmagan (smeta ham yo'q).")

    version = db.query_one(NEXT_VERSION_SQL, {"id": opp_id})["v"]
    row = db.execute_returning(SUB_INSERT_SQL, {
        "opportunity_id": opp_id, "version": version,
        "submitted_by": data.get("submitted_by"),
        "price": price, "currency": data.get("currency") or pkg["currency"],
        # JSONB — nusxa O'SHA PAYTDAGI shaklda qoladi
        "pricing": json.dumps(pkg["pricing"], ensure_ascii=False) if pkg["pricing"] else None,
        "compliance": json.dumps(_compliance_snapshot(pkg["compliance"]),
                                 ensure_ascii=False) if pkg["compliance"] else None,
        "documents": json.dumps(pkg["documents"], ensure_ascii=False) if pkg["documents"] else None,
        "blocking_count": blocking,
        "confirmed_note": data.get("confirmed_note"),
        "note": data.get("note")})

    # Status o'tishi — opportunity.set_status orqali: tarix o'sha yerda
    # yoziladi va qoidalar bitta joyda qoladi.
    from api.erp.opportunity import set_status
    note = f"Taklif topshirildi (v{version})"
    if blocking:
        note += f"; cheklistda {blocking} ta to'siq tasdiqlangan"
    opp = set_status(opp_id, "submitted", data.get("submitted_by"), note)
    return {"submission": shape(row), "opportunity": opp}


def _compliance_snapshot(c: Optional[dict]) -> Optional[dict]:
    """Cheklistdan MUZLATILADIGAN qism: xulosa va bandlar holati. To'liq
    javobda dalil matnlari (`evidence`) ham bor — ular uzun va taklif
    tarixida kerak emas."""
    if not c:
        return None
    return {
        "summary": c.get("summary"),
        "doc_source": c.get("doc_source"),
        "items": [{"doc_type": i["doc_type"], "label": i["label"],
                   "status": i["status"], "in_base": i["in_base"],
                   "valid_until": (i.get("document") or {}).get("valid_until")}
                  for i in (c.get("items") or [])],
    }
