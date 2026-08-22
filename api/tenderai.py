"""Tender-AI bilan integratsiya — ERP'ning tashqi dunyoga YAGONA ko'prigi.

ERP alohida loyiha. U tender-ai'ning kodini import QILMAYDI va uning
jadvallariga YOZMAYDI. Ikki turdagi bog'lanish bor va ikkalasi ham shu
faylda, boshqa hech qayerda:

  1. O'QISH — `public.tender` dan snapshot uchun 9 maydon. Baza baham
     ko'rilgani uchun bu to'g'ridan-to'g'ri SQL (`opportunity.py` dagi
     TENDER_SNAPSHOT_SQL). Kelajakda alohida bazaga o'tilsa — shu bitta
     so'rov HTTP chaqiruviga almashadi.
  2. QOIDALAR — hujjatlar cheklisti. Qoidalar (DOC_TYPES, matndan talab
     aniqlash) tender-ai'da, ular 1400 qator va IKKINCHI NUSXASI BO'LMASLIGI
     kerak. Shuning uchun ERP mijozning hujjatlarini tender-ai'ga YUBORADI
     va tayyor cheklistni oladi: `POST /tenders/{id}/compliance`.

Ikkinchi yo'nalish (tender-ai -> ERP) YO'Q: tender-ai ERP haqida faqat
bitta narsani biladi — "Ishga olish" tugmasining URL manzili.

AUTH-2 dan boshlab tender-ai endpointlari yopiq: bu yerdagi har bir
so'rov `X-Service-Key` sarlavhasini olib boradi (pastga qarang).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

#: Tender-AI backendi. .env: TENDER_AI_API=http://127.0.0.1:8000
API = os.environ.get("TENDER_AI_API", "http://127.0.0.1:8000").rstrip("/")
#: Tender-AI interfeysi — kartadagi "Tender panelini ochish" havolasi uchun.
WEB = os.environ.get("TENDER_AI_WEB", "http://localhost:5173").rstrip("/")
TIMEOUT = float(os.environ.get("TENDER_AI_TIMEOUT", "20"))

# --- SERVER-SERVER kaliti ----------------------------------------------------
# Tender-AI endpointlari auth-2 dan boshlab YOPIQ. ERP u yerga ODAM
# nomidan bormaydi: cheklist qoidasi, hujjat shabloni va xabar yuborish —
# ERP ning O'Z ishi va u fonda ham bajariladi (masalan tungi eslatma
# skriptida, hech kim kirmagan paytda). Shuning uchun kompaniya sessiyasi
# emas, alohida kalit ishlatiladi.
#
# Kalit SERVERDA qoladi: brauzerga hech qachon yuborilmaydi.
SERVICE_KEY = os.environ.get("ERP_SERVICE_KEY", "").strip()


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = dict(extra or {})
    if SERVICE_KEY:
        h["X-Service-Key"] = SERVICE_KEY
    return h


class TenderAiUnavailable(RuntimeError):
    """Tender-AI javob bermadi. ERP YIQILMAYDI — chaqiruvchi buni 503 ga
    aylantiradi va interfeys "cheklist hozir mavjud emas" deb ochiq aytadi."""


def tender_web_url(tender_id: int) -> str:
    """Tender-AI dagi tender kartasi. Bildirishnoma havolasi bilan bir xil
    naqsh (`/?tender=<id>`) — tender-ai uni o'zi ochadi."""
    return f"{WEB}/?tender={tender_id}"


def _get(path: str) -> Any:
    req = urllib.request.Request(f"{API}{path}", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise TenderAiUnavailable(f"Tender-AI {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TenderAiUnavailable(f"Tender-AI javob bermadi: {e}") from e


def document_types() -> List[Dict[str, Any]]:
    """Kanonik hujjat turlari (`compliance.DOC_TYPES`). ERP nusxa saqlamaydi:
    ikki ro'yxat vaqt o'tib ajralib ketardi va cheklist mijoz hujjatini
    tanimay qolardi."""
    return _get("/company/document-types")


def _post(path: str, body: Dict[str, Any]) -> Any:
    req = urllib.request.Request(
        f"{API}{path}", data=json.dumps(body).encode("utf-8"), method="POST",
        headers=_headers({"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        # 404 — tender manbada yo'q (ETL o'chirgan bo'lishi mumkin). Buni
        # chaqiruvchi ajrata olishi uchun kod bilan qaytaramiz.
        raise TenderAiUnavailable(f"Tender-AI {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TenderAiUnavailable(f"Tender-AI javob bermadi: {e}") from e


def compliance(tender_id: int, docs: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Cheklistni tender-ai'dan oladi. `docs` — MIJOZNING hujjatlari
    (`erp.client_document` qatorlari); bo'sh ro'yxat ham to'g'ri javob beradi
    ("hammasi yetishmayapti"). None berilsa tender-ai o'z kompaniyasining
    hujjatlariga qaraydi — ERP'da bunga ehtiyoj yo'q, lekin API shuni beradi.

    Sanalar ISO satrga aylantiriladi: JSON `date` turini bilmaydi."""
    payload = {"documents": [_json_doc(d) for d in docs] if docs is not None else None}
    return _post(f"/tenders/{tender_id}/compliance", payload)


def template(fmt: str = "xlsx") -> tuple[bytes, str]:
    """Hujjatlar shabloni (.xlsx / .csv) — tender-ai yasaydi.

    Shablon TALAB ETILADIGAN HUJJATLAR RO'YXATI bilan oldindan to'ldirilgan
    keladi va u `compliance.DOC_TYPES` dan olinadi. ERP o'z shablonini
    yasamaydi: ikkita shablon bo'lsa ustunlar va turlar ro'yxati vaqt o'tib
    ajralib ketardi."""
    path = f"/company/documents/template?fmt={fmt}"
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=TIMEOUT) as r:
            return r.read(), r.headers.get("Content-Type", "application/octet-stream")
    except urllib.error.HTTPError as e:
        raise TenderAiUnavailable(f"Tender-AI {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TenderAiUnavailable(f"Tender-AI javob bermadi: {e}") from e


def parse_documents(data: bytes, filename: str) -> Dict[str, Any]:
    """To'ldirilgan shablonni tender-ai'ga TEKSHIRTIRADI va tozalangan
    qatorlarni oladi (`POST /company/documents/parse`). Bazaga hech kim
    yozmaydi — yozishni ERP o'zi, o'z jadvaliga qiladi.

    Parser (sarlavhalarni tanish, sana formatlari, hujjat turini aniqlash)
    tender-ai'da qoladi — ERP'da ikkinchi nusxasi bo'lmaydi."""
    body, ctype = _multipart(filename, data)
    req = urllib.request.Request(f"{API}/company/documents/parse", data=body,
                                 method="POST",
                                 headers=_headers({"Content-Type": ctype}))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 422 — fayl formati yaroqsiz. Bu FOYDALANUVCHI xatosi, tender-ai
        # nosozligi emas: matnini o'zgarishsiz yuqoriga uzatamiz.
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail") or ""
        except Exception:                       # noqa: BLE001
            pass
        if e.code in (413, 422):
            raise ValueError(detail or f"Fayl qabul qilinmadi ({e.code}).") from e
        raise TenderAiUnavailable(f"Tender-AI {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TenderAiUnavailable(f"Tender-AI javob bermadi: {e}") from e


def stock_check(tender_id: int) -> Dict[str, Any]:
    """Tender pozitsiyalari <-> katalog moslashuvi (tender-ai da).

    NEGA U YERDA: moslashtirish qoidalari (nom/kalit so'z bo'yicha,
    alifbodan qat'i nazar) `api/stock.py` da, 400 qator. Cheklist bilan
    bir xil sabab — IKKINCHI NUSXASI BO'LMASLIGI kerak.

    ERP bu javobdan REZERV TAKLIFINI quradi: "shu tenderga 7 dona nasos
    kerak, omboringizda bor — ajratasizmi?" Tasdiqni ODAM beradi:
    moslashuv har doim ham to'g'ri emas va tasdiqsiz rezerv omborni
    ifloslantirardi."""
    return _get(f"/tenders/{tender_id}/stock-check")


def pricing(tender_id: int) -> Optional[Dict[str, Any]]:
    """Tenderning SAQLANGAN smetasi (tender-ai `tender_pricing`).

    Hisoblanmagan bo'lsa None — bu xato emas. Formula tender-ai'da
    (`pricing.py`) va ERP uni qayta hisoblamaydi: taklif paketiga
    natijaning NUSXASI qo'yiladi."""
    return _get(f"/tenders/{tender_id}/pricing")


def tender(tender_id: int) -> Dict[str, Any]:
    """Jonli tender: hujjatlar ro'yxati va manbadagi hozirgi status."""
    return _get(f"/tenders/{tender_id}")


def notify(subject: str, text: str,
           channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Xabarni tender-ai orqali yuboradi (`POST /notify/send`).

    NEGA U YERDAN: SMTP rekvizitlari va Telegram bot tokeni tender-ai
    o'rnatmasida. Ularni ERP'ga nusxalash — sirni ikkinchi joyda saqlash
    demakdir; buning o'rniga ERP tayyor matnni beradi. Qabul qiluvchilar ham
    o'sha yerda sozlangan: ERP manzil yubormaydi va yubora olmaydi.
    """
    return _post("/notify/send", {
        "subject": subject, "text": text,
        "channels": channels or ["telegram", "email"]})


def _multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    """multipart/form-data tanasi — bitta `file` maydoni.

    NEGA QO'LDA: ERP bog'liqliklari ataylab kam (fastapi, uvicorn, psycopg2,
    dotenv). Faqat bitta fayl yuborish uchun `requests` yoki `httpx` ni
    o'rnatish — 20 qator kod evaziga butun kutubxona. Chegara oddiy va
    o'zgarmas, shuning uchun bu yerda o'zimiz yozamiz."""
    boundary = "----erp-boundary-7f3a9c1e"
    safe = (filename or "shablon.xlsx").replace('"', "")
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{safe}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _json_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k in ("doc_type", "name", "number", "file_name", "file_ref", "note"):
        out[k] = d.get(k)
    for k in ("issued_at", "valid_until"):
        v = d.get(k)
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out
