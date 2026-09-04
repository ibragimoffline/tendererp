"""
Tender-AI ERP — Backend API (alohida ilova).

Bu ALOHIDA LOYIHA: o'z FastAPI ilovasi, o'z porti (8100), o'z frontendi.
Tender-AI bilan bog'lanish faqat ikki nuqtada — `api/tenderai.py` ga qarang.

Ishga tushirish:
    cp .env.example .env
    .venv/Scripts/python.exe -m pip install -r requirements.txt
    .venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8100
    # Swagger: http://localhost:8100/docs

Baza: tender-ai bilan BIR XIL PostgreSQL (XT_DB_DSN), lekin `erp` sxemasi.
`public.*` ga FAQAT O'QISH uchun tegiladi (opportunity snapshot) va hech
qachon yozilmaydi — sinov buni har yurishda tekshiradi.
"""
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import (Cookie, Depends, FastAPI, File, Header, HTTPException,
                     Query, Request, Response, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()  # .env ni import paytida yuklaymiz (pool DSN'ni ko'rishi uchun)

from urllib.parse import quote  # noqa: E402

from api import auth, db, tenderai  # noqa: E402
from api.erp import (act as erp_act, analytics as erp_analytics,  # noqa: E402
                     egalik,
                     clients as erp_clients, contracts as erp_contracts,
                     invoice as erp_invoice, invoice_export as erp_export,
                     audit as erp_audit, fayl as erp_fayl,
                     chat as erp_chat,
                     opportunity as erp_opp, perm, profit as erp_profit,
                     sozlama as erp_sozlama,
                     topshiriq as erp_topshiriq, xabar as erp_xabar,
                     staff as erp_staff,
                     stats as erp_stats, stock as erp_stock_mod,
                     submission as erp_sub, tasks as erp_tasks)


# =============================================================================
# JURNAL (log)
# =============================================================================
# MUAMMO: server yashirin oynada ishlaydi (`run_erp.ps1`), ya'ni xato
# bo'lsa u ekranga chiqadi va o'sha yerda YO'QOLADI. "Kecha ishlamadi"
# degan gapni tekshiradigan hech narsa yo'q edi.
#
# Yechim eng soddasi: FAYLGA yozish, aylanma (rotatsiya) bilan.
# Alohida xizmat (Sentry va sh.k.) qo'shilmaydi — ichki ERP uchun u
# ortiqcha va tashqariga ma'lumot chiqarardi.
#
# NIMA YOZILADI: uvicorn'ning kirish jurnali va ilova xatolari.
# PAROL, TOKEN va CSRF hech qachon jurnalga tushmaydi — ular so'rov
# tanasida, u esa yozilmaydi.
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "logs")
LOG_KEEP = int(os.environ.get("LOG_KEEP_FILES", "7"))
LOG_MAX_MB = int(os.environ.get("LOG_MAX_MB", "10"))


def _setup_logging() -> str:
    """Faylga yozishni yoqadi va fayl yo'lini qaytaradi."""
    import logging
    from logging.handlers import RotatingFileHandler

    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, "erp.log")

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    handler = RotatingFileHandler(path, maxBytes=LOG_MAX_MB * 1024 * 1024,
                                  backupCount=LOG_KEEP, encoding="utf-8")
    handler.setFormatter(fmt)

    root = logging.getLogger()
    # Ikki marta ulanib qolmasin (qayta yuklashda).
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(logging.INFO)

    # uvicorn o'z jurnalchilarini alohida yuritadi — ularni ham
    # shu faylga yo'naltiramiz.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        if not any(isinstance(h, RotatingFileHandler) for h in lg.handlers):
            lg.addHandler(handler)
    return path


LOG_FILE = _setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    db.init_pool()
    logging.getLogger("erp").info("ERP ishga tushdi | jurnal: %s", LOG_FILE)
    # TENDER-AI YO'NALTIRISHI. Tinglovchi FAQAT xarita qo'yilgan
    # bo'lsa ishga tushadi (`erp.own_company.tai_company_id`) —
    # sozlanmagan o'rnatma begona ijarachining topshirig'ini
    # o'ziniki deb qabul qilmasin. Yiqilsa ERP baribir ishlaydi:
    # yo'naltirish — qo'shimcha yo'l, yagona yo'l emas.
    try:
        if erp_topshiriq.tingla_boshla():
            logging.getLogger("erp").info(
                "Tender-AI topshiriq tinglovchisi yoqildi")
    except Exception:                           # noqa: BLE001
        logging.getLogger("erp").exception("tinglovchi ishga tushmadi")
    yield
    try:
        erp_topshiriq.tingla_toxta()
    except Exception:                           # noqa: BLE001
        pass
    logging.getLogger("erp").info("ERP to'xtadi")
    db.close_pool()


app = FastAPI(
    title="Tender-AI ERP API",
    description="Ishga olingan tenderlar, mijoz korxonalar, rahbar hisoboti.",
    version="2.0",
    lifespan=lifespan,
)

# ERP frontendi alohida domenda (5174) — CORS shuning uchun kerak.
# tender-ai'da bu kerak emas edi: u yerda Vite proksisi bitta domen beradi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# So'rov modellari
# ---------------------------------------------------------------------------
class OpportunityIn(BaseModel):
    """Xodim kiritadigan maydonlar. Snapshot (tender nomi, summasi, muddati)
    SERVERDA tenderdan olinadi — mijozdan qabul qilinmaydi."""
    broker_id: Optional[int] = None
    client_id: Optional[int] = None
    priority: str = "medium"               # low | medium | high
    win_probability: Optional[int] = None  # 0..100
    note: Optional[str] = None
    next_task: Optional[str] = None
    next_task_at: Optional[date] = None
    created_by: Optional[str] = None       # auth yo'q: tanlangan broker nomi


class OpportunityStatusIn(BaseModel):
    status: str
    changed_by: Optional[str] = None
    note: Optional[str] = None             # yakuniydan qaytishda MAJBURIY
    # Faqat 'lost' uchun; kod (`/erp/meta` -> lost_reasons). Keyingi tahlil
    # erkin matndan emas, shu koddan chiqadi.
    lost_reason: Optional[str] = None


class SettingIn(BaseModel):
    """Tizim sozlamasi — hozircha hammasi ha/yo'q (`api/erp/sozlama.py`)."""
    value: bool


class OwnCompanyIn(BaseModel):
    """Bizning kompaniya passporti. Shartnoma va hisob-faktura IKKI tomonning
    rekvizitlarini talab qiladi; tender-ai dagi `company_profile` esa qidiruv
    profili — unda INN ham, bank rekvizitlari ham yo'q."""
    name: str
    inn: Optional[str] = None
    oked: Optional[str] = None
    legal_form: Optional[str] = None
    tax_mode: Optional[str] = None
    address_legal: Optional[str] = None
    address_actual: Optional[str] = None
    bank_name: Optional[str] = None
    bank_mfo: Optional[str] = None
    bank_account: Optional[str] = None
    director_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class ContractIn(BaseModel):
    """Shartnoma. Summa va valyuta berilmasa taklifdan (yoki kartadagi
    snapshotdan) olinadi — bir xil raqam ikki marta yozilmasin."""
    submission_id: Optional[int] = None
    number: Optional[str] = None
    signed_at: Optional[date] = None
    starts_at: Optional[date] = None
    ends_at: Optional[date] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None            # default: draft
    note: Optional[str] = None
    created_by: Optional[str] = None


class SubmissionIn(BaseModel):
    """Topshirish. Narx berilmasa smetadan olinadi; cheklistda to'siq bo'lsa
    `confirmed` MAJBURIY (taqiq emas — tasdiq yozib qo'yiladi)."""
    price: Optional[float] = None
    currency: Optional[str] = None
    confirmed: bool = False
    confirmed_note: Optional[str] = None
    note: Optional[str] = None
    submitted_by: Optional[str] = None


class ChatMessageIn(BaseModel):
    """Chatga xabar. `mentions` — a'zolar ro'yxatidan TANLANGAN hisoblar.

    Matndan `@ism` ni QIDIRIB topmaymiz: bir xil ismli ikki hodim
    bo'lsa xabar noto'g'ri odamga ketardi, umuman topilmasa esa jim
    qolardi. Interfeys kimni eslatganini ANIQ aytadi."""
    text: str
    reply_to_id: Optional[int] = None
    mentions: Optional[List[int]] = None


class ChatDeleteIn(BaseModel):
    """Boshqaning xabarini o'chirishda `note` MAJBURIY (modulda
    tekshiriladi) — u muallifga bildirishnoma bo'lib boradi."""
    note: Optional[str] = None


class ChatMemberIn(BaseModel):
    """`app_user_id` berilmasa — CHAQIRUVCHINING O'ZI qo'shiladi.

    Bu eng ko'p uchraydigan holat: rahbar chatni a'zosiz o'qiydi va
    yozish uchun o'zini qo'shadi. Mijoz o'z id sini bilishi shart
    emas — u sessiyada allaqachon bor."""
    app_user_id: Optional[int] = None


class ChatReadIn(BaseModel):
    """Berilmasa — chatning oxirgi xabarigacha o'qilgan deb belgilanadi."""
    last_read_id: Optional[int] = None


class TaskIn(BaseModel):
    """Karta bo'yicha bitta ish. Mas'ul ko'rsatilmasa — kartaning brokeri."""
    title: str
    assignee_broker_id: Optional[int] = None
    due_at: Optional[date] = None
    note: Optional[str] = None
    created_by: Optional[str] = None


class StockMoveIn(BaseModel):
    """Ombor harakati. `qty` MUSBAT: ishorani server qo'yadi (chiqim
    manfiy bo'ladi). Istisno — `adjust`: u yerda ishora MA'NO tashiydi
    (kam chiqdi / ko'p chiqdi) va shuning uchun mijozdan keladi."""
    product_id: int
    kind: str                              # opening | in | out | adjust
    qty: float
    opportunity_id: Optional[int] = None   # qaysi karta uchun chiqdi
    doc_ref: Optional[str] = None          # nakladnoy / akt raqami
    note: Optional[str] = None


class InvoiceIn(BaseModel):
    """Faktura sarlavhasi. Rekvizitlar YOZILMAYDI — ular passportdan
    yaratilish paytida ko'chiriladi (snapshot)."""
    client_id: Optional[int] = None
    contract_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    number: Optional[str] = None
    issued_at: Optional[date] = None
    due_at: Optional[date] = None
    currency: Optional[str] = None
    note: Optional[str] = None


class InvoiceLineIn(BaseModel):
    """Faktura qatori. `vat_rate` berilmasa mijoz passportidan olinadi va
    qatorga NUSXA yoziladi."""
    name: str
    qty: float
    price: float
    vat_rate: Optional[float] = None
    unit: Optional[str] = None
    product_id: Optional[int] = None
    pos: Optional[int] = None
    note: Optional[str] = None


class InvoiceStatusIn(BaseModel):
    status: str


class ActIn(BaseModel):
    """Dalolatnoma. Rekvizitlar YOZILMAYDI — passportdan ko'chiriladi."""
    client_id: Optional[int] = None
    invoice_id: Optional[int] = None
    contract_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    number: Optional[str] = None
    act_date: Optional[date] = None
    #: Ish qaysi davr uchun (oylik xizmatlarda).
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    currency: Optional[str] = None
    note: Optional[str] = None


class ActStatusIn(BaseModel):
    status: str
    #: HUJJATDAGI imzo sanasi (tizim vaqtidan farqli).
    signed_at: Optional[date] = None


class PaymentIn(BaseModel):
    paid_at: date
    amount: float
    method: str = "bank"
    doc_ref: Optional[str] = None
    note: Optional[str] = None


class StockReserveIn(BaseModel):
    """Kartaga ajratilgan tovar. `qty` MUSBAT: rezerv ayirma emas,
    "ajratilgan miqdor"."""
    product_id: int
    qty: float
    note: Optional[str] = None


class BrokerIn(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    #: Faqat TAHRIRLASHDA (PUT). `None` — "tegilmasin": forma faqat
    #: telefonni yuborsa, hodim tasodifan faolsizlanib qolmasin.
    active: Optional[bool] = None


class ClientCompanyIn(BaseModel):
    """Mijoz korxona. `name` dan boshqa hamma maydon ixtiyoriy — karta
    passportsiz ham yaratiladi, passport keyin to'ldiriladi."""
    name: str
    inn: Optional[str] = None              # 9 raqam; takrorlanmaydi
    oked: Optional[str] = None
    legal_form: Optional[str] = None       # MCHJ / AJ / YaTT ...
    tax_mode: Optional[str] = None
    address_legal: Optional[str] = None
    address_actual: Optional[str] = None
    bank_name: Optional[str] = None
    bank_mfo: Optional[str] = None
    bank_account: Optional[str] = None
    director_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None
    active: bool = True
    #: QQS to'lovchimi. `None` = HALI SO'RALMAGAN (false bilan bir xil
    #: emas): faktura stavkasi shu javobga qarab hal bo'ladi.
    vat_payer: Optional[bool] = None
    #: Sukut stavka (%). Faktura QATORIGA nusxa ko'chiriladi.
    vat_rate: Optional[float] = None


class ClientContactIn(BaseModel):
    full_name: str
    position: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False
    note: Optional[str] = None


class ClientDocumentIn(BaseModel):
    """Mijoz hujjati. `doc_type` — tender-ai'dagi kanonik kod
    (`GET /erp/document-types` orqali olinadi)."""
    doc_type: str
    name: str
    number: Optional[str] = None
    issued_at: Optional[date] = None
    valid_until: Optional[date] = None     # NULL = muddatsiz
    file_name: Optional[str] = None
    file_ref: Optional[str] = None         # fayl yuklash yo'q: havola yoki yo'l
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# KIMLIK — barcha /erp/* endpointlari HIMOYALANGAN.
#
# HODIM hisoblari SHU YERDA (`erp.app_user`): ERP — kompaniyaning o'z
# tizimi va odam uning tushunchasi. Tender-AI esa KOMPANIYA hisobi bilan
# kiriladi va u alohida (`api/auth.py` dagi izohga qarang).
#
# ISTISNO YO'Q: `/erp/*` ning HAMMASI himoyalangan. Ochiq qolganlar
# faqat `/health`, `/erp/meta` (interfeys login OLDIDAN holatni
# ko'rsatadi) va `/erp/auth/*`.
#
# Auth-1 da bitta istisno bor edi — `GET /erp/tenders/{id}/opportunities`
# ni tender-ai interfeysi brauzerdan chaqirardi. Auth-3 da u yopildi:
# tender-ai `erp.v_tender_status` VIEW ini o'z backendida o'qiydi.
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    """Hodim hisobi. `password` faqat YARATISHDA majburiy."""
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    #: JORIY parol — O'ZINIKINI almashtirayotgan odam uchun MAJBURIY
    #: (auth-6). Admin boshqaning parolini tiklayotganda so'ralmaydi.
    current_password: Optional[str] = None
    role: str = "broker"
    #: `erp.broker.id` — hisob qaysi hodimga tegishli
    broker_id: Optional[int] = None
    email: Optional[str] = None
    active: bool = True


# --- COOKIE va CSRF (auth-4) -------------------------------------------------
# Sessiya tokeni endi `localStorage` da EMAS, `HttpOnly` cookie'da:
# XSS bo'lsa ham sahifadagi JavaScript uni O'QIY OLMAYDI.
#
# Buning narxi CSRF: cookie'ni brauzer HAR so'rovga o'zi qo'shadi, ya'ni
# boshqa sayt bizning nomimizdan so'rov yuborishi mumkin. Ikki qatlam:
#   1. `SameSite=Lax` — cookie boshqa saytdan kelgan POST/PUT/DELETE ga
#      QO'SHILMAYDI (brauzer darajasidagi to'siq);
#   2. `X-CSRF-Token` sarlavhasi — qiymati SESSIYADAGI bilan solishtiriladi.
#      Sarlavhani begona sayt qo'ya olmaydi (CORS preflight to'sadi).
#
# CSRF tokeni `HttpOnly BO'LMAGAN` cookie'da: sahifa uni o'qib sarlavhaga
# qo'yadi. U SIR EMAS va kirish huquqini bermaydi — faqat "so'rovni bizning
# sahifamiz yubordimi" degan savolga javob beradi.
SESSION_COOKIE = "erp_session"
CSRF_COOKIE = "erp_csrf"
CSRF_HEADER = "x-csrf-token"

#: `Secure` — cookie faqat HTTPS orqali yuboriladi. Brauzerlar `localhost`
#: ni ishonchli deb hisoblaydi, shuning uchun ishlab chiqishda ham yoqiq
#: qoladi. HTTP orqali BOSHQA domenda ishlatilsa `.env` da o'chiriladi.
COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "1") not in ("0", "false", "")

#: CSRF faqat O'ZGARTIRUVCHI metodlar uchun. GET/HEAD tekshirilmaydi:
#: ular ma'lumotni o'zgartirmaydi va javobini begona sayt baribir o'qiy
#: olmaydi (CORS).
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _set_auth_cookies(response: Response, token: str, csrf: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", max_age=auth.SESSION_DAYS * 86400, path="/")
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=COOKIE_SECURE,
        samesite="lax", max_age=auth.SESSION_DAYS * 86400, path="/")


def _clear_auth_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", samesite="lax",
                               secure=COOKIE_SECURE)


def _tok(authorization: Optional[str],
         cookie_token: Optional[str] = None) -> tuple:
    """Tokenni topadi. OSHKORA sarlavha USTUN, cookie — zaxira.

    `Authorization: Bearer` brauzer uchun emas — u API mijozlari uchun
    (skript, sinov, kelajakdagi integratsiya). Sarlavha ustun turadi,
    chunki u ATAYLAB qo'yiladi: cookie esa brauzer tomonidan avtomatik
    qo'shiladi va ikkalasi uchrashganda "qaysi biri haqiqiy niyat?"
    degan savolga oshkora qo'yilgani javob beradi.

    Qaysi yo'l ishlatilgani ham qaytariladi: CSRF FAQAT cookie uchun
    kerak — Bearer da "begona sayt bizning nomimizdan" holati yuzaga
    kelmaydi."""
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401,
                                detail="Token formati noto'g'ri.")
        return parts[1].strip(), False
    if cookie_token:
        return cookie_token, True
    raise HTTPException(status_code=401, detail="Kiring (token yo'q).")



# --- PROKSI ORQASIDA MANZIL (auth-5 davomi) ---------------------------------
# `X-Forwarded-For` ga ODATDA ISHONILMAYDI: uni mijozning o'zi yozib
# yuborishi mumkin, ya'ni parol tanlashdan himoyaning IP cheklovini
# bir qator matn bilan chetlab o'tish mumkin bo'lardi.
#
# Lekin ERP proksi (nginx/IIS) orqasiga qo'yilsa, `request.client` HAR
# DOIM proksining o'zini ko'rsatadi va hamma so'rov bitta manzildan
# kelayotgandek bo'ladi — IP kesimi ishlamay qoladi.
#
# Yechim — SOZLAMA, kod emas: `TRUST_PROXY=1`. Default O'CHIQ, ya'ni
# to'g'ridan-to'g'ri ishlayotgan o'rnatma xavfsiz holatda qoladi.
#
# NEGA OXIRGI manzil: sarlavha `mijoz, proksi1, proksi2` ko'rinishida
# bo'ladi va BOSHIDAGI qiymatlarni mijoz o'zi yozib yuborishi mumkin.
# Oxirgisini esa bizga eng yaqin (ishonchli) proksi qo'yadi — u
# haqiqatan ko'rgan manzil. Shuning uchun ro'yxatning oxiridan olinadi.
#
# DIQQAT: ikki yoki undan ko'p proksi bo'lsa bu joy qayta ko'rib
# chiqilishi kerak (o'shanda oxirgisi ichki proksi manzili bo'ladi).
TRUST_PROXY = (os.environ.get("TRUST_PROXY", "0").strip().lower()
               in ("1", "true", "yes", "on"))


def client_ip(request: Request) -> Optional[str]:
    """So'rov kelgan manzil. `TRUST_PROXY` o'chiq bo'lsa — faqat
    to'g'ridan-to'g'ri ulanish manzili."""
    if TRUST_PROXY:
        xff = request.headers.get("X-Forwarded-For") or ""
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else None


def _auth(fn, *a, **kw):
    """AuthError -> HTTP kodi (401/403/429/503).

    429 da `Retry-After` sarlavhasi ham qo'shiladi — bu standart yo'l
    bilan "qachon qayta urinish mumkin" degan savolga javob beradi va
    brauzerdan tashqari mijozlar ham tushunadi."""
    try:
        return fn(*a, **kw)
    except auth.AuthError as e:
        h = ({"Retry-After": str(int(getattr(e, "retry_after", 60)))}
             if e.code == 429 else None)
        raise HTTPException(status_code=e.code, detail=str(e), headers=h)


def _bilan_huquq(user: Dict[str, Any]) -> Dict[str, Any]:
    """Foydalanuvchi + uning HUQUQLAR KESIMI.

    Interfeys tugmani ko'rsatish yoki yashirishni shundan hal qiladi.
    Aks holda ekran o'z ro'yxatini tutardi ("brokerga bu tugma
    ko'rinmasin") va u serverdagi matritsadan ajralib ketardi — tugma
    ko'rinib turib, bosilganda 403 berardi."""
    return {**user, "perms": perm.for_user(user)}


def me(request: Request,
       authorization: Optional[str] = Header(None),
       erp_session: Optional[str] = Cookie(None)) -> Dict[str, Any]:
    """Himoyalangan endpointlar uchun bog'liqlik.

    Cookie bilan kelgan O'ZGARTIRUVCHI so'rovda CSRF sarlavhasi
    MAJBURIY (sabab yuqoridagi izohda)."""
    token, from_cookie = _tok(authorization, erp_session)
    user = _auth(auth.verify, token)
    if from_cookie and request.method in UNSAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER)
        if not sent or not secrets.compare_digest(sent, user.get("csrf") or ""):
            # 403 (401 emas): kim ekani MA'LUM, lekin so'rov bizning
            # sahifamizdan kelganiga ishonch yo'q.
            raise HTTPException(
                status_code=403,
                detail="CSRF tokeni mos kelmadi — sahifani yangilang.")
    return user


def _can(user: Dict[str, Any], action: str) -> Optional[str]:
    """HUQUQ tekshiruvi — bitta yo'l. Ruxsat bo'lmasa 403.

    Matritsa `api/erp/perm.py` da: endpoint FAQAT qaysi amal
    bajarilayotganini aytadi, KIM uni qila olishini emas. Avval bu yerda
    rol nomlari (`require_role(user, "menejer")`, `Depends(menejer)`)
    yozilardi va "broker fakturani chiqara oladimi?" degan savolga
    javob 90 ta endpointni o'qib topilardi.

    Qaytadi: daraja (`full` / `own` / `read`) — chaqiruvchi kerak
    bo'lsa ishlatadi (`own` -> ro'yxatni filtrlash).

    ATAYLAB TEKSHIRILMAYDIGANLAR (ro'yxat shu yerda tursin, aks holda
    "unutilganmi yoki shundaymi?" degan savol qoladi):
      /health, /erp/meta            — holat va LUG'ATLAR (status nomlari);
      /erp/auth/*                   — kirish, chiqish, "kim men", rollar;
      GET /erp/own-company          — rekvizitlar hujjat CHOP ETISHDA
                                      kerak, ya'ni har bir hodimga;
      GET/POST /erp/brokers         — hodim lug'ati va formadagi tez
                                      qo'shish (mijoz qo'shish bilan bir
                                      xil, `erp_add_broker` izohiga qarang);
      GET /erp/document-types       — tender-ai lug'ati."""
    return _auth(perm.require, user, action)


def _can_obj(user: Dict[str, Any], action: str, kind: str,
             obj_id: Any) -> Optional[str]:
    """Amal + EGALIK: "shu kartani/hujjatni" degan qism.

    Matritsa amalni biladi, obyektni bilmaydi (`api/erp/perm.py`).
    Daraja `own` bo'lsa — obyekt kimga tegishli ekani ham tekshiriladi
    (`api/erp/egalik.py`) va begonasi 403 beradi (404 EMAS: "yo'q"
    bilan "meniki emas"ni ajratish begona kartaning mavjudligini
    aytib qo'yardi)."""
    daraja = _can(user, action)
    if daraja == perm.OZ and perm.OZ_FILTRI_TAYYOR:
        _erp(egalik.talab, user, kind, obj_id)
    return daraja


def _oz_filtr(user: Dict[str, Any], action: str) -> Optional[int]:
    """RO'YXAT uchun egalik filtri: `own` bo'lsa — o'z hodim id si.

    Hisob hodimga bog'lanmagan bo'lsa `-1` qaytadi, ya'ni ro'yxat
    BO'SH keladi. Bu ataylab: aks holda sozlamadagi kamchilik
    ("hisob bog'lanmagan") hamma ma'lumotni ochib berardi. Interfeys
    sababini ochiq yozadi (`AuthUser.broker_id` null)."""
    if _can(user, action) == perm.OZ and perm.OZ_FILTRI_TAYYOR:
        return egalik.oz_broker_id(user) or -1
    return None


@app.post("/erp/auth/login")
def erp_login(body: LoginIn, request: Request, response: Response,
              user_agent: Optional[str] = Header(None)):
    """Hodimning kirishi.

    Sessiya tokeni JAVOB TANASIDA QAYTMAYDI — u `HttpOnly` cookie'ga
    qo'yiladi va sahifadagi JavaScript uni ko'rmaydi (auth-4). Javobda
    faqat foydalanuvchi va CSRF tokeni.

    Urinishlar JURNALGA yoziladi va ko'p xatodan keyin 429 qaytadi
    (`auth.guard_attempts`). Manzil `client_ip()` orqali olinadi:
    `X-Forwarded-For` ga faqat `TRUST_PROXY=1` bo'lganda ishoniladi
    (sababi o'sha funksiya ustidagi izohda)."""
    res = _auth(auth.login, body.username, body.password,
                user_agent=user_agent, ip=client_ip(request))
    _set_auth_cookies(response, res["token"], res["csrf"])
    response.headers["Cache-Control"] = "no-store"   # kirish javobi keshlanmasin
    return {"user": _bilan_huquq(res["user"]), "csrf": res["csrf"],
            "expires_at": res["expires_at"]}


@app.post("/erp/auth/logout")
def erp_logout(response: Response,
               authorization: Optional[str] = Header(None),
               erp_session: Optional[str] = Cookie(None)):
    """Chiqish. Cookie'lar HAR HOLDA tozalanadi — token yaroqsiz bo'lsa
    ham brauzerda osilib qolmasin.

    CSRF bu yerda TALAB QILINMAYDI: begona sayt bizni "chiqarib
    yuborishi" zarar keltirmaydi, ammo tokeni eskirgan foydalanuvchi
    chiqa olmay qolishi — keltiradi."""
    ok = False
    try:
        token, _ = _tok(authorization, erp_session)
        ok = _auth(auth.logout, token)
    except HTTPException:
        pass
    _clear_auth_cookies(response)
    return {"ok": ok}


@app.get("/erp/auth/me")
def erp_me(response: Response, user: Dict[str, Any] = Depends(me)):
    """Kim kirgan. Javobda CSRF tokeni ham bor: sahifa yangilanganda uni
    qayta login'siz tiklaydi."""
    response.headers["Cache-Control"] = "no-store"
    return _bilan_huquq(user)


class TaiXaritaIn(BaseModel):
    """Biz qaysi Tender-AI ijarachisimiz (`company_account.id`).

    `null` — bog'lanish uziladi va tinglovchi to'xtaydi."""
    tai_company_id: Optional[int] = None


class XabarOqishIn(BaseModel):
    """O'qilgan deb belgilash. `ids` berilmasa — HAMMASI."""
    ids: Optional[List[int]] = None


@app.get("/erp/notifications")
def erp_notifications(only_unread: bool = False,
                      limit: int = Query(50, ge=1, le=200),
                      user: Dict[str, Any] = Depends(me)):
    """O'Z bildirishnomalari.

    HUQUQ TEKSHIRILMAYDI va bu ataylab: bu o'zining ishi. Boshqaning
    xabarini o'qish YO'LI YO'Q — `app_user_id` sessiyadan olinadi,
    so'rovdan emas (parol almashtirish bilan bir xil qoida)."""
    return _erp(erp_xabar.royxat, user["id"], only_unread, limit)


@app.post("/erp/notifications/read")
def erp_notifications_read(body: XabarOqishIn,
                           user: Dict[str, Any] = Depends(me)):
    """O'qilgan deb belgilash (o'ziniki)."""
    n = _erp(erp_xabar.oqildi, user["id"], body.ids)
    return {"belgilandi": n, "unread": _erp(erp_xabar.sanoq, user["id"])}


@app.get("/erp/topshiriq/holat")
def erp_topshiriq_holat(user: Dict[str, Any] = Depends(me)):
    """Yo'naltirish oqimi: xarita bormi, tinglovchi tirikmi, nechta
    topshiriq kutyapti.

    Sozlanmagan holat ham JAVOBDA ochiq aytiladi (`sabab`) — "hech
    narsa kelmayapti" degan savolga javob shu yerdan topiladi."""
    _can(user, "tizim.tai_xarita")
    return _erp(erp_topshiriq.holat)


@app.put("/erp/topshiriq/xarita")
def erp_topshiriq_xarita(body: TaiXaritaIn,
                         user: Dict[str, Any] = Depends(me)):
    """Xaritani o'rnatish — OPERATOR qarori, taxmin emas."""
    _can(user, "tizim.tai_xarita")
    cid = _erp(erp_topshiriq.xarita_qoy, body.tai_company_id)
    # Xarita qo'yilgach tinglovchi darhol ishga tushadi: qayta
    # yuklashni kutish "ishlamayapti" degan taassurot qoldirardi.
    if cid:
        erp_topshiriq.tingla_boshla()
    return _erp(erp_topshiriq.holat)


@app.post("/erp/topshiriq/sync")
def erp_topshiriq_sync(user: Dict[str, Any] = Depends(me)):
    """Kutayotgan topshiriqlarni QO'LDA olib kelish.

    Tinglovchi bor, lekin bu tugma ham kerak: ulanish uzilgan yoki
    ERP o'chirilgan paytda kelgan topshiriqlarni odam kutib
    o'tirmasin."""
    _can(user, "tizim.tai_xarita")
    return _erp(erp_topshiriq.sync)


@app.get("/erp/settings")
def erp_settings(user: Dict[str, Any] = Depends(me)):
    """Tizim sozlamalari: qiymat, STANDART qiymat, nomi va izohi.

    Izoh ham beriladi — "yoqsam nima o'zgaradi" degan savolga javob
    bo'lmasa, sozlama tegilmay qoladi."""
    _can(user, "tizim.sozlama")
    if not erp_sozlama.schema_ready():
        return {"ready": False, "settings": []}
    return {"ready": True, "settings": _erp(erp_sozlama.hammasi)}


@app.put("/erp/settings/{key}")
def erp_set_setting(key: str, body: SettingIn,
                    user: Dict[str, Any] = Depends(me)):
    """Sozlamani o'zgartirish. Kim o'zgartirgani YOZILADI: sozlama
    huquqqa ta'sir qiladi va "kim yoqdi?" degan savol keyin beriladi."""
    _can(user, "tizim.sozlama")
    return _erp(erp_sozlama.saqla, key, body.value, auth.actor(user))


@app.get("/erp/auth/roles")
def erp_roles():
    return {"roles": [{"code": c, "label": l} for c, l in auth.ROLES],
            "schema_ready": auth.schema_ready()}


# --- hodim hisoblari (admin) -------------------------------------------------
# HODIM ro'yxati (`erp.broker`) va HISOB ro'yxati alohida: hodim tizimga
# kirmasligi ham mumkin (masalan omborchi), hisob esa hodimga bog'lanadi.
@app.get("/erp/users")
def erp_users(user: Dict[str, Any] = Depends(me)):
    _can(user, "tizim.hodim")
    return _auth(auth.users)


@app.get("/erp/auth/attempts")
def erp_login_attempts(hours: int = Query(24, ge=1, le=720),
                       limit: int = Query(100, ge=1, le=1000),
                       only_failed: bool = True,
                       user: Dict[str, Any] = Depends(me)):
    """Kirish urinishlari — "kim, qayerdan va qachon urindi".

    Faqat admin: bu ro'yxatda mavjud loginlar ko'rinadi va uni
    tarqatish hujumchiga ish beradi."""
    _can(user, "tizim.hodim")
    return _auth(auth.attempts, hours, limit, only_failed)


@app.post("/erp/users", status_code=201)
def erp_create_user(body: UserIn, user: Dict[str, Any] = Depends(me)):
    _can(user, "tizim.hodim")
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Login va parol majburiy.")
    return _auth(auth.create_user, body.username, body.full_name or body.username,
                 body.password, role=body.role, broker_id=body.broker_id,
                 email=body.email)


@app.put("/erp/users/{user_id}")
def erp_update_user(user_id: int, body: UserIn,
                    user: Dict[str, Any] = Depends(me)):
    _can(user, "tizim.hodim")
    return _auth(auth.update_user, user_id, body.model_dump())


@app.put("/erp/users/{user_id}/password")
def erp_set_password(user_id: int, body: UserIn,
                     authorization: Optional[str] = Header(None),
                     erp_session: Optional[str] = Cookie(None),
                     user: Dict[str, Any] = Depends(me)):
    """Admin boshqaning parolini TIKLAYDI; har kim O'ZINIKINI almashtiradi.

    Ikki holat ATAYLAB har xil (auth-6):

    * **O'ZINIKI** — `current_password` MAJBURIY. Ochiq qolgan
      kompyuter yoki o'g'irlangan sessiya bilan begona odam parolni
      o'zgartirib, hisobni butunlay egallab olmasin. Almashtirgandan
      keyin BOSHQA sessiyalar o'chadi, o'ziniki qoladi.
    * **BOSHQANIKI (admin)** — eski parol so'ralmaydi (u odatda
      "unutdim" holati), lekin o'sha hisobning HAMMA sessiyalari
      o'chadi: admin parolni tiklayotgan bo'lsa, hisobga ishonch yo'q."""
    own = user["id"] == user_id
    if not own:
        # BOSHQANING paroli — hodim boshqaruvi amali. O'ZINIKI esa
        # har kimga ochiq va rolga bog'liq emas.
        _can(user, "tizim.hodim")
    if not body.password:
        raise HTTPException(status_code=400, detail="Yangi parol berilmagan.")
    if own and not body.current_password:
        raise HTTPException(status_code=400,
                            detail="Joriy parolni kiriting.")
    # Hozirgi token faqat O'Z parolini almashtirishda saqlanadi.
    keep = None
    if own:
        try:
            keep = _tok(authorization, erp_session)[0]
        except HTTPException:
            keep = None
    return _auth(auth.set_password, user_id, body.password,
                 current=(body.current_password if own else None),
                 keep_token=keep)


def _erp(fn, *a, **kw):
    """ErpError -> HTTP kodi (400/404/409/503). 409 da mavjud yozuv id si ham
    qaytadi, shuning uchun detail obyekt bo'ladi."""
    try:
        return fn(*a, **kw)
    except erp_opp.ErpError as e:
        detail = {"message": str(e), **e.extra} if e.extra else str(e)
        raise HTTPException(status_code=e.code, detail=detail)


# ---------------------------------------------------------------------------
# Sog'liq va meta
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    """Baza va tender-ai holati. Interfeys buni ochiq ko'rsatadi — ERP
    tender-ai'siz ham ishlaydi (mavjud kartalar), lekin yangi karta ocha
    olmaydi."""
    ok_db = True
    try:
        db.scalar("SELECT 1")
    except Exception:                       # noqa: BLE001
        ok_db = False
    return {"ok": ok_db, "schema_ready": erp_opp.schema_ready() if ok_db else False,
            "clients_ready": erp_clients.schema_ready() if ok_db else False,
            "tender_ai": tenderai.API, "tender_ai_web": tenderai.WEB}


@app.get("/erp/meta")
def erp_meta():
    """Statuslar va ustuvorliklar — Kanban ustunlari va formalar shundan."""
    return {
        "schema_ready": erp_opp.schema_ready(),
        "clients_ready": erp_clients.schema_ready(),
        "statuses": [{"code": c, "label": l, "final": c in erp_opp.FINAL}
                     for c, l in erp_opp.STATUSES],
        "priorities": [{"code": c, "label": l} for c, l in erp_opp.PRIORITIES.items()],
        "lost_reasons": [{"code": c, "label": l} for c, l in erp_opp.LOST_REASONS],
        "tasks_ready": erp_tasks.schema_ready(),
        "submissions_ready": erp_sub.schema_ready(),
        "contracts_ready": erp_contracts.schema_ready(),
        "stock_ready": erp_stock_mod.schema_ready(),
        "invoice_ready": erp_invoice.schema_ready(),
        "act_ready": erp_act.schema_ready(),
        # Sabab hujjati (24-patch). Interfeys bloki shu bayroqqa qaraydi:
        # patch qo'llanmagan bazada blok UMUMAN ko'rsatilmaydi, "yuklash
        # ishlamadi" degan jim xato o'rniga.
        "fayl_ready": erp_fayl.schema_ready(),
        "fayl_holatlar": sorted(erp_fayl.YOPIQ_HOLATLAR),
        "fayl_turlar": sorted(erp_fayl.TURLAR),
        "fayl_max_hajm": erp_fayl.MAX_HAJM,
        # Ichki chat (25-patch). Patch qo'llanmagan bazada interfeys
        # "Muloqot" bo'limini UMUMAN ko'rsatmaydi — bo'sh ekran va
        # "yuklanmadi" degan jim xato o'rniga.
        "chat_ready": erp_chat.schema_ready(),
        "chat_max_matn": erp_chat.MAX_MATN,
        "act_statuses": [{"code": c, "label": l}
                         for c, l in erp_act.STATUSES],
        "invoice_statuses": [{"code": c, "label": l}
                             for c, l in erp_invoice.STATUSES],
        "payment_methods": [{"code": c, "label": l}
                            for c, l in erp_invoice.METHODS],
        "invoice_export_formats": erp_export.available(),
        "stock_kinds": [{"code": c, "label": l}
                        for c, l in erp_stock_mod.KINDS],
        "auth_ready": auth.schema_ready(),
        "contract_statuses": [{"code": c, "label": l}
                              for c, l in erp_contracts.CONTRACT_STATUSES],
        "tender_web": tenderai.WEB,
    }


# ---------------------------------------------------------------------------
# Opportunity pipeline (1-bosqich)
# ---------------------------------------------------------------------------
@app.get("/erp/opportunities")
def erp_list(status: Optional[str] = None, broker_id: Optional[int] = None,
             client_id: Optional[int] = None, q: Optional[str] = None,
             open_only: bool = False, unassigned: bool = False,
             user: Dict[str, Any] = Depends(me)):
    # EGALIK: broker uchun ro'yxat O'ZINIKIGA toraytiriladi — so'rovdagi
    # `broker_id` e'tiborga olinmaydi (aks holda uni almashtirib
    # begona kartalarni ko'rish mumkin bo'lardi).
    oz = _oz_filtr(user, "karta.korish")
    return _erp(erp_opp.list_, status, oz or broker_id, client_id, q, open_only,
                unassigned)


@app.get("/erp/opportunities/{opp_id}")
def erp_get(opp_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_opp.get, opp_id)


@app.put("/erp/opportunities/{opp_id}")
def erp_update(opp_id: int, body: OpportunityIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.tahrirlash", "opportunity", opp_id)
    # created_by kesiladi: karta kim tomonidan yaratilgani TAHRIRLANMAYDI.
    return _erp(erp_opp.update, opp_id, body.model_dump(exclude={"created_by"}))


@app.patch("/erp/opportunities/{opp_id}/status")
def erp_status(opp_id: int, body: OpportunityStatusIn, user: Dict[str, Any] = Depends(me)):
    # Yakuniy status (yutildi / yutqazildi / rad) — ALOHIDA amal: uni
    # brokerga berish sozlama bo'ladi, oddiy bosqich o'tishi esa uning
    # kundalik ishi. Yakuniydan QAYTARISH ham alohida amal, lekin u
    # kartaning HOZIRGI holatiga bog'liq va modulda tekshiriladi.
    _can_obj(user, "karta.yopish" if body.status in erp_opp.FINAL
             else "karta.status", "opportunity", opp_id)
    return _erp(erp_opp.set_status, opp_id, body.status, auth.actor(user),
                body.note, body.lost_reason)


# --- bizning kompaniya va shartnomalar (5A-1) --------------------------------
@app.get("/erp/own-company")
def erp_own_company(user: Dict[str, Any] = Depends(me)):
    """Bizning rekvizitlar. `missing` — shartnoma uchun yetishmayotganlari."""
    return _erp(erp_contracts.own_get)


@app.put("/erp/own-company")
def erp_save_own_company(body: OwnCompanyIn, user: Dict[str, Any] = Depends(me)):
    _can(user, "tizim.kompaniya")
    return _erp(erp_contracts.own_save, body.model_dump())


@app.get("/erp/contracts")
def erp_contract_list(status: Optional[str] = None, client_id: Optional[int] = None,
                      open_only: bool = False,
                      user: Dict[str, Any] = Depends(me)):
    """Barcha shartnomalar + karta konteksti (rahbar ko'rinishi)."""
    return _erp(erp_contracts.list_, status, client_id, open_only,
                owner_broker_id=_oz_filtr(user, "karta.korish"))


@app.get("/erp/contracts/stats")
def erp_contract_stats(user: Dict[str, Any] = Depends(me)):
    _can(user, "hisobot.kompaniya")
    return _erp(erp_contracts.stats)


@app.get("/erp/opportunities/{opp_id}/contracts")
def erp_opp_contracts(opp_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_contracts.list_for, opp_id)


@app.post("/erp/opportunities/{opp_id}/contracts", status_code=201)
def erp_add_contract(opp_id: int, body: ContractIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "shartnoma.tahrirlash", "opportunity", opp_id)
    return _erp(erp_contracts.create, opp_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.put("/erp/contracts/{contract_id}")
def erp_update_contract(contract_id: int, body: ContractIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "shartnoma.tahrirlash", "contract", contract_id)
    return _erp(erp_contracts.update, contract_id, body.model_dump())


@app.patch("/erp/contracts/{contract_id}/status")
def erp_contract_status(contract_id: int, status: str = Query(...),
                        user: Dict[str, Any] = Depends(me)):
    """Shartnoma O'CHIRILMAYDI — noto'g'risi 'terminated' ga o'tkaziladi."""
    _can_obj(user, "shartnoma.tahrirlash", "contract", contract_id)
    return _erp(erp_contracts.set_status, contract_id, status)


# --- taklif va topshirish (4-bosqich) ----------------------------------------
@app.get("/erp/opportunities/{opp_id}/submission")
def erp_submission_package(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Taklif paketi: narx hisobi, cheklist, mijoz hujjatlari va tenderning
    manbadagi statusi — BITTA ekranda, topshirishdan oldin ko'rish uchun.

    Tender-AI javob bermasa ham paket qaytadi: yiqilgan qismlar null va
    `warnings` da sababi. "Hozir topshirsam bo'ladimi?" degan savolga
    baribir javob berish kerak."""
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_sub.package, opp_id)


@app.post("/erp/opportunities/{opp_id}/submission", status_code=201)
def erp_submit(opp_id: int, body: SubmissionIn, user: Dict[str, Any] = Depends(me)):
    """Taklifni MUZLATADI (yangi versiya) va kartani 'submitted' ga
    o'tkazadi. Cheklistdagi to'siq TAQIQ EMAS — tasdiq so'raladi va u
    tarixga yoziladi."""
    _can_obj(user, "karta.status", "opportunity", opp_id)
    return _erp(erp_sub.submit, opp_id,
                {**body.model_dump(), "submitted_by": auth.actor(user)})


@app.get("/erp/opportunities/{opp_id}/submissions")
def erp_submissions(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Topshirilgan versiyalar — o'zgarmas tarix."""
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_sub.list_, opp_id)


# --- vazifalar (3-bosqich) ---------------------------------------------------
# Javob har doim kartaning BUTUN ro'yxati: bitta so'rov, interfeys qayta
# so'ramaydi va ro'yxat sakramaydi.
@app.get("/erp/opportunities/{opp_id}/tasks")
def erp_tasks_list(opp_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_tasks.list_, opp_id)


@app.post("/erp/opportunities/{opp_id}/tasks", status_code=201)
def erp_task_add(opp_id: int, body: TaskIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.tahrirlash", "opportunity", opp_id)
    return _erp(erp_tasks.add, opp_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.put("/erp/tasks/{task_id}")
def erp_task_update(task_id: int, body: TaskIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.tahrirlash", "task", task_id)
    return _erp(erp_tasks.update, task_id, body.model_dump())


@app.patch("/erp/tasks/{task_id}/done")
def erp_task_done(task_id: int, done: bool = Query(True),
                  user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "karta.tahrirlash", "task", task_id)
    return _erp(erp_tasks.set_done, task_id, done)


@app.delete("/erp/tasks/{task_id}")
def erp_task_delete(task_id: int, user: Dict[str, Any] = Depends(me)):
    """Vazifa O'CHIRILADI (kartadan farqli): u ish rejasi, tarix emas."""
    _can_obj(user, "karta.tahrirlash", "task", task_id)
    return _erp(erp_tasks.delete, task_id)


@app.get("/erp/my-tasks")
def erp_my_tasks(broker_id: Optional[int] = None,
                 days: int = Query(0, ge=0, le=90),
                 everyone: bool = False,
                 user: Dict[str, Any] = Depends(me)):
    """"Mening bugungi ishlarim": kechikkanlar, bugungilar va keyingilar.

    KIMNIKI (auth-2): hisob hodimga bog'langan bo'lsa — SUKUT BO'YICHA
    o'shaniki. Ekranning nomi "MENING ishlarim": har ochilganda ro'yxatdan
    o'zini qidirib topish kerak emas.

    - `everyone=true` — hammaniki (rahbar ko'rinishi);
    - `broker_id=N` — aniq hodimniki (ikkalasi ham ochiq: vazifalar
      allaqachon hammaga ko'rinadi, bu maxfiylik chegarasi emas).
    """
    _can(user, "hisobot.deadline")
    if _oz_filtr(user, "hisobot.deadline") is not None:
        # EGALIK: brokerga faqat O'ZINIKI. `everyone=true` va begona
        # `broker_id` e'tiborga olinmaydi — ekranda ham bu filtrlar
        # ko'rsatilmaydi.
        broker_id, everyone = user.get("broker_id") or -1, False
    if broker_id is None and not everyone:
        broker_id = user.get("broker_id")
    res = _erp(erp_tasks.my_tasks, broker_id, days)
    # Interfeys "sukut bo'yicha o'zimniki" ekanini bilishi kerak: filtr
    # tanlovi shunga qarab ko'rsatiladi.
    res["self_broker_id"] = user.get("broker_id")
    return res


@app.get("/erp/reminders")
def erp_reminders(days: int = Query(1, ge=0, le=30),
                  deadline_days: int = Query(3, ge=0, le=30),
                  user: Dict[str, Any] = Depends(me)):
    """Eslatilishi kerak bo'lganlar ro'yxati. HECH NARSA YUBORMAYDI —
    yuborish `api/erp/remind.py` da (jadval bo'yicha yuriladi). Bu endpoint
    "bugun kimga nima ketardi?" degan savolga javob berish uchun."""
    _can(user, "hisobot.deadline")
    return _erp(erp_tasks.due_reminders, days, deadline_days,
                _oz_filtr(user, "hisobot.deadline"))


@app.get("/erp/opportunities/{opp_id}/tender-diff")
def erp_tender_diff(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Kartadagi snapshot jonli tenderdan farq qiladimi.

    Snapshot O'ZGARTIRILMAYDI — u ataylab muzlatilgan. Bu endpoint faqat
    xabar beradi: "tenderda 2 maydon o'zgargan" yoki "tender manbada yo'q".
    Qaysi qiymat to'g'ri ekanini odam hal qiladi."""
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_opp.diff_with_tender, opp_id)


# --- sabab hujjati (24-patch) -----------------------------------------------
# "Nega yutqazdik / to'xtatdik / ulgurmadik" tafsiloti. `lost_reason`
# kodining O'RNINI BOSMAYDI — u tasniflash uchun, bu tafsilot uchun.
@app.get("/erp/opportunities/{opp_id}/files")
def erp_files_list(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Kartaning fayllari — metadata, baytlarsiz."""
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_fayl.royxat, opp_id)


@app.post("/erp/opportunities/{opp_id}/files", status_code=201)
def erp_file_add(
    opp_id: int,
    file: UploadFile = File(..., description="Sabab hujjati (pdf/docx/xlsx/jpg/png)."),
    izoh: Optional[str] = Query(None, description="Bir qatorlik izoh."),
    user: Dict[str, Any] = Depends(me),
):
    """Fayl biriktiradi. IXTIYORIY — kartani yopish uchun shart emas.

    Hajm ikki joyda tekshiriladi: bu yerda (o'qishdan oldin `413`) va
    modulda (bazadagi CHECK bilan bir xil chegara). Ikkinchisi ilova
    chetlab o'tilsa ham ishlaydi."""
    _can_obj(user, "karta.fayl", "opportunity", opp_id)
    data = file.file.read()
    if len(data) > erp_fayl.MAX_HAJM:
        raise HTTPException(
            status_code=413,
            detail=f"Fayl {erp_fayl.MAX_HAJM // 1048576} MB dan katta.")
    return _erp(erp_fayl.qosh, opp_id, file.filename or "", data, izoh,
                auth.actor(user))


# TARTIB MUHIM: `qamrov` `{file_id}` dan OLDIN turishi shart. FastAPI
# marshrutlarni E'LON TARTIBIDA solishtiradi — teskarisi bo'lsa "qamrov"
# satri `int` ga aylantirilmay `422` berardi va sabab ko'rinmasdi.
@app.get("/erp/files/qamrov")
def erp_files_qamrov(user: Dict[str, Any] = Depends(me)):
    """"Yopilgan N kartadan M tasida sabab hujjati bor" — funksiya
    ishlatilyaptimi degan savolga RAQAM bilan javob."""
    _can(user, "hisobot.kompaniya")
    return _erp(erp_fayl.qamrov)


@app.get("/erp/files/{file_id}")
def erp_file_download(file_id: int, user: Dict[str, Any] = Depends(me)):
    """Faylni yuklab olish."""
    _can_obj(user, "karta.korish", "opportunity_file", file_id)
    f = _erp(erp_fayl.baytlar_olish, file_id)
    # `filename*=UTF-8''...` — nomda kirill yoki o'zbekcha belgi bo'lsa
    # brauzer uni to'g'ri o'qisin. Oddiy `filename=` ASCII bilan cheklangan.
    nom = quote(f["fayl_nom"])
    return Response(content=f["baytlar"], media_type=f["mime"],
                    headers={"Content-Disposition":
                             f"attachment; filename*=UTF-8''{nom}"})


@app.delete("/erp/files/{file_id}")
def erp_file_delete(file_id: int, user: Dict[str, Any] = Depends(me)):
    """O'chiradi. IZ QOLADI: `erp.doc_audit` ga kim/qachon/qaysi fayl
    yoziladi va u jurnal o'zgartirilmaydi."""
    _can_obj(user, "karta.fayl", "opportunity_file", file_id)
    return _erp(erp_fayl.ochir, file_id, auth.actor(user))


# ---------------------------------------------------------------------------
# ICHKI CHAT (25-patch) — `docs/erp_chat.md`
# ---------------------------------------------------------------------------
# BU TENDER-AI DAGI AI CHATI EMAS: bu odam bilan odam yozishmasi.
#
# IKKI TEKSHIRUV har endpointda va ular BOSHQA savolga javob beradi:
#   `_can(user, "chat.*")`    — bu ROLDA umuman shunday amal bormi;
#   `erp_chat.*_talab(...)`   — shu CHATga bu odamning aloqasi bormi.
# Ikkinchisi modulda, chunki u a'zolikka bog'liq va SQL talab qiladi.


def _chat_hammasi(user: Dict[str, Any]) -> bool:
    """Rahbar/menejer barcha karta chatlarini KO'RADI (yozish emas).

    `_can` emas, `perm.can`: huquq yo'qligi bu yerda XATO emas —
    broker uchun oddiy holat, u faqat o'z chatlarini ko'radi."""
    return perm.can(user, "chat.hammasi") is not None


@app.get("/erp/chats")
def erp_chats(user: Dict[str, Any] = Depends(me)):
    """Mening chatlarim + o'qilmagan soni. `umumiy` har doim birinchi."""
    _can(user, "chat.korish")
    return _erp(erp_chat.chatlarim, auth.user_id(user), _chat_hammasi(user))


@app.get("/erp/chats/{chat_id}/messages")
def erp_chat_messages(chat_id: int, after_id: Optional[int] = None,
                      limit: int = Query(erp_chat.LIMIT_DEFAULT),
                      q: Optional[str] = None,
                      user: Dict[str, Any] = Depends(me)):
    """Lenta. Sahifalash `after_id` bo'yicha; `q` — chat ichida qidiruv.

    YANGILANISH — SO'ROV (polling) bilan, 5 soniyada: `after_id` bilan
    so'ralganda javob odatda bo'sh va arzon. WebSocket ataylab yo'q
    (`docs/erp_chat.md` §5): 5-15 hodimlik kompaniyada 5 s kechikish
    muammo emas, WebSocket esa joylashtirishga alohida talab qo'yadi."""
    _can(user, "chat.korish")
    return _erp(erp_chat.lenta, chat_id, auth.user_id(user),
                _chat_hammasi(user), after_id, limit, q,
                perm.can(user, "chat.tarix") is not None)


@app.post("/erp/chats/{chat_id}/messages", status_code=201)
def erp_chat_send(chat_id: int, body: ChatMessageIn,
                  user: Dict[str, Any] = Depends(me)):
    _can(user, "chat.yozish")
    uid = auth.user_id(user)
    msg = _erp(erp_chat.yoz, chat_id, uid, body.text, body.reply_to_id)
    # ESLATISH — xabar yozilgandan KEYIN: bildirishnoma yiqilsa ham
    # xabarning o'zi yo'qolmasin (`xabar.yoz()` ning o'zi ham
    # chaqiruvchini yiqitmaydi).
    if body.mentions:
        _erp(erp_chat.eslat, chat_id, uid, msg["id"], body.mentions)
    return msg


@app.put("/erp/chats/{chat_id}/messages/{mid}")
def erp_chat_edit(chat_id: int, mid: int, body: ChatMessageIn,
                  user: Dict[str, Any] = Depends(me)):
    """FAQAT o'z xabari. Eski matn tarixga yoziladi.

    ESLATISH TAHRIRDA HAM ISHLAYDI: "eslatishni unutdim, tahrirlab
    qo'shdim" — haqiqiy holat. Lekin faqat YANGI id larga yuboriladi
    (`chat_message.eslatilgan`), aks holda har tahrirda hammaga takror
    ketardi va odam bildirishnomalarni o'qimay yopishni odat qilardi."""
    _can(user, "chat.yozish")
    uid = auth.user_id(user)
    msg = _erp(erp_chat.tahrir, mid, uid, body.text)
    if body.mentions:
        _erp(erp_chat.eslat, chat_id, uid, mid, body.mentions)
    return msg


@app.delete("/erp/chats/{chat_id}/messages/{mid}")
def erp_chat_delete(chat_id: int, mid: int,
                    body: Optional[ChatDeleteIn] = None,
                    user: Dict[str, Any] = Depends(me)):
    """Yumshoq o'chirish. Boshqaning xabari — `chat.moderatsiya` va
    izoh MAJBURIY (u muallifga bildirishnoma bo'lib boradi)."""
    _can(user, "chat.yozish")
    return _erp(erp_chat.ochir, mid, auth.user_id(user),
                perm.can(user, "chat.moderatsiya") is not None,
                (body.note if body else None))


@app.get("/erp/chats/{chat_id}/messages/{mid}/history")
def erp_chat_history(chat_id: int, mid: int,
                     user: Dict[str, Any] = Depends(me)):
    """Tahrir va o'chirish tarixi — rahbar va admin uchun.

    ADMIN uchun YAGONA chat endpointi: u yozishmada qatnashmaydi,
    lekin NAZORAT jurnalini ko'radi (`docs/erp_chat.md` §2)."""
    _can(user, "chat.tarix")
    return _erp(erp_chat.tarix, mid)


@app.get("/erp/chats/{chat_id}/members")
def erp_chat_members(chat_id: int, user: Dict[str, Any] = Depends(me)):
    _can(user, "chat.korish")
    return _erp(erp_chat.azolar, chat_id, auth.user_id(user),
                _chat_hammasi(user))


@app.post("/erp/chats/{chat_id}/members", status_code=201)
def erp_chat_member_add(chat_id: int, body: ChatMemberIn,
                        user: Dict[str, Any] = Depends(me)):
    """Qo'shish. Broker buni FAQAT o'z kartasining chatida qiladi —
    egalik `opportunity` orqali tekshiriladi."""
    _can(user, "chat.azo_qosh")
    _erp(erp_chat.egalik_talab, chat_id, user, "chat.azo_qosh")
    return _erp(erp_chat.azo_qosh, chat_id, auth.user_id(user),
                body.app_user_id or auth.user_id(user))


@app.delete("/erp/chats/{chat_id}/members/{uid}")
def erp_chat_member_remove(chat_id: int, uid: int,
                           user: Dict[str, Any] = Depends(me)):
    """Chiqarish. Kartaning MAS'ULINI chiqarib bo'lmaydi (modulda)."""
    _can(user, "chat.azo_chiqar")
    return _erp(erp_chat.azo_chiqar, chat_id, auth.user_id(user), uid)


@app.put("/erp/chats/{chat_id}/read")
def erp_chat_read(chat_id: int, body: Optional[ChatReadIn] = None,
                  user: Dict[str, Any] = Depends(me)):
    _can(user, "chat.korish")
    return _erp(erp_chat.oqildi, chat_id, auth.user_id(user),
                body.last_read_id if body else None)


@app.get("/erp/opportunities/{opp_id}/chat")
def erp_opportunity_chat(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Karta chatiga o'tish. Chat yo'q bo'lsa (patchdan oldin ochilgan
    karta) SHU YERDA ochiladi — kartani chatsiz qoldirmaymiz."""
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    return _erp(erp_chat.karta_chati_id, opp_id, auth.user_id(user))


@app.get("/erp/tenders/{tender_id}/opportunities")
def tender_opportunities(tender_id: int, user: Dict[str, Any] = Depends(me)):
    """Shu tender ishga olinganmi va qaysi mijozlar uchun.

    AVVAL OCHIQ EDI — uni tender-ai interfeysi brauzerdan chaqirardi.
    Auth-3 da yopildi: tender-ai endi `erp.v_tender_status` VIEW ini o'z
    backendida o'qiydi (`schema_patch_erp_7.sql`), ya'ni bu endpointga
    tashqaridan murojaat qilinmaydi. ERP interfeysining o'zi ishlatadi."""
    _can(user, "karta.korish")
    return _erp(erp_opp.by_tender, tender_id)


@app.post("/erp/tenders/{tender_id}/take", status_code=201)
def tender_take(tender_id: int, body: OpportunityIn, user: Dict[str, Any] = Depends(me)):
    """"ISHGA OLISH" — tender ro'yxatdan ichki ish kartasiga aylanadi."""
    _can(user, "karta.yaratish")
    # `created_by` — ISM (yozuvlarda ko'rinadi), `created_by_user_id` —
    # HISOB id si (chat a'zoligi hisobga bog'lanadi, ismga emas).
    return _erp(erp_opp.take, tender_id,
                {**body.model_dump(), "created_by": auth.actor(user),
                 "created_by_user_id": auth.user_id(user)})


@app.get("/erp/brokers")
def erp_brokers(user: Dict[str, Any] = Depends(me)):
    return _erp(erp_opp.brokers)


@app.post("/erp/brokers", status_code=201)
def erp_add_broker(b: BrokerIn, user: Dict[str, Any] = Depends(me)):
    """Yangi hodim. ATAYLAB adminga cheklanmagan: bu "Ishga olish"
    formasidagi tez qo'shish (mijoz qo'shish bilan bir xil). Tahrirlash va
    faolsizlantirish esa admin ishi — pastga qarang."""
    return _erp(erp_opp.add_broker, b.full_name, b.email, b.phone)


@app.put("/erp/brokers/{broker_id}")
def erp_update_broker(broker_id: int, b: BrokerIn,
                      user: Dict[str, Any] = Depends(me)):
    _can(user, "tizim.hodim")
    return _erp(erp_staff.update_broker, broker_id, b.model_dump())


@app.get("/erp/staff")
def erp_staff_list(user: Dict[str, Any] = Depends(me)):
    """HODIMLAR ekrani: hodim + unga bog'langan hisob BITTA ro'yxatda.

    Ikkisini alohida ko'rsatsak "bu odamga hisob ochilganmi?" degan
    savolga javob ikki ro'yxatni solishtirib topilardi."""
    _can(user, "tizim.hodim")
    return {"staff": _erp(erp_staff.staff),
            # Hodimga bog'lanmagan hisoblar (masalan tizim administratori):
            # ular hech qaysi hodim qatorida ko'rinmaydi, yo'qolib
            # qolmasligi uchun alohida qaytariladi.
            "unlinked_users": [u for u in _auth(auth.users)
                               if not u.get("broker_id")]}


# --- OMBOR (5B-1) ------------------------------------------------------------
# Qoldiqning EGASI — ERP: jurnal shu yerda, tender-ai esa `v_stock_balance`
# view idan O'QIYDI (`erp_arxitektura_3.md` 6.1, "A1" yo'li).
@app.get("/erp/stock")
def erp_stock(include_empty: bool = True,
              user: Dict[str, Any] = Depends(me)):
    """Qoldiqlar. `include_empty` — harakati yo'q mahsulotlar ham
    ko'rsatiladi ("qoldiq kiritilmagan" ham ma'lumot)."""
    _can(user, "ombor.korish")
    return _erp(erp_stock_mod.balances, include_empty=include_empty)


@app.get("/erp/stock/moves")
def erp_stock_moves(product_id: Optional[int] = None,
                    opportunity_id: Optional[int] = None,
                    limit: int = Query(200, ge=1, le=1000),
                    user: Dict[str, Any] = Depends(me)):
    _can(user, "ombor.korish")
    return _erp(erp_stock_mod.moves, product_id=product_id,
                opportunity_id=opportunity_id, limit=limit)


@app.post("/erp/stock/moves", status_code=201)
def erp_stock_add(body: StockMoveIn, user: Dict[str, Any] = Depends(me)):
    """Yangi harakat. Manfiy qoldiq TAQIQ EMAS — javobda `warning`
    qaytadi (sabab: `api/erp/stock.py` boshidagi izoh)."""
    _can(user, "ombor.harakat")
    return _erp(erp_stock_mod.add_move,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.post("/erp/stock/seed-opening")
def erp_stock_seed(user: Dict[str, Any] = Depends(me)):
    """Tender-AI ga import qilingan qoldiqlarni boshlang'ich harakatga
    ko'chiradi (bir martalik, idempotent). Ombor nol qoldiqdan
    boshlanmasin."""
    _can(user, "ombor.harakat")
    return _erp(erp_stock_mod.seed_opening, auth.actor(user))


# --- REZERV ------------------------------------------------------------------
# Rezerv qoldiqni KAMAYTIRMAYDI, MAVJUD miqdorni kamaytiradi. U kartaning
# statusiga bog'langan: yutilganda sarflanadi, yutqazilganda bo'shaydi
# (`api/erp/stock.py` -> `on_status_change`).
@app.get("/erp/reserves")
def erp_reserves(opportunity_id: Optional[int] = None,
                 product_id: Optional[int] = None,
                 only_held: bool = False,
                 user: Dict[str, Any] = Depends(me)):
    # Rezerv KARTAGA qo'yiladi, ya'ni u qoldiq emas — kartaning ishi.
    # Shuning uchun filtr `karta.korish` bo'yicha: broker qoldiqni
    # to'liq ko'radi, lekin begona kartaning bandini emas.
    _can(user, "ombor.korish")
    return _erp(erp_stock_mod.reserves, opportunity_id=opportunity_id,
                product_id=product_id, only_held=only_held,
                owner_broker_id=_oz_filtr(user, "karta.korish"))


@app.post("/erp/opportunities/{opp_id}/reserves", status_code=201)
def erp_add_reserve(opp_id: int, body: StockReserveIn,
                    user: Dict[str, Any] = Depends(me)):
    """Kartaga tovar ajratish. Mavjuddan oshsa TAQIQ EMAS — javobda
    `warning` qaytadi (chiqimdagi bilan bir xil sabab)."""
    _can_obj(user, "ombor.rezerv", "opportunity", opp_id)
    return _erp(erp_stock_mod.add_reserve, opp_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.get("/erp/opportunities/{opp_id}/reserve-suggestions")
def erp_reserve_suggest(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Tender pozitsiyalaridan REZERV TAKLIFI.

    Moslashtirish tender-ai da (qoidalar u yerda), yozish esa BU YERDA va
    faqat ODAM TASDIG'I bilan: moslashuv nom bo'yicha ishlaydi va har
    doim ham to'g'ri emas."""
    _can_obj(user, "ombor.korish", "opportunity", opp_id)
    return _erp(erp_stock_mod.suggest, opp_id)


@app.post("/erp/opportunities/{opp_id}/reserves/bulk", status_code=201)
def erp_reserve_bulk(opp_id: int, body: List[StockReserveIn],
                     user: Dict[str, Any] = Depends(me)):
    """Tasdiqlangan takliflarni rezervga aylantirish. Bir qator o'tmasa
    qolganlari yoziladi — xatolar ro'yxatda qaytadi."""
    _can_obj(user, "ombor.rezerv", "opportunity", opp_id)
    return _erp(erp_stock_mod.add_reserves, opp_id,
                [b.model_dump() for b in body], auth.actor(user))


@app.delete("/erp/reserves/{reserve_id}")
def erp_release_reserve(reserve_id: int, user: Dict[str, Any] = Depends(me)):
    """Rezervni qo'lda bo'shatish. Yozuv O'CHIRILMAYDI — `released`
    bo'ladi: "nega band edi va nega bo'shadi" tarixda qolsin."""
    _can_obj(user, "ombor.rezerv", "reserve", reserve_id)
    return _erp(erp_stock_mod.release_reserve, reserve_id, auth.actor(user))


@app.get("/erp/stock/{product_id}")
def erp_stock_product(product_id: int, user: Dict[str, Any] = Depends(me)):
    """Bitta mahsulot: qoldiq + harakatlar tarixi."""
    _can(user, "ombor.korish")
    return _erp(erp_stock_mod.product, product_id)


# --- HISOB-FAKTURA (5B-2) ----------------------------------------------------
# ERP fakturani O'ZI chiqaradi. Summalar SAQLANMAYDI — qatorlardan
# hisoblanadi; QQS stavkasi HAR QATORDA (mijoz passportidan sukut).
# Eksport qatlami ATAYLAB bo'sh: `api/erp/invoice_export.py`.
@app.get("/erp/invoices")
def erp_invoices(status: Optional[str] = None,
                 client_id: Optional[int] = None,
                 opportunity_id: Optional[int] = None,
                 user: Dict[str, Any] = Depends(me)):
    return _erp(erp_invoice.list_, status, client_id, opportunity_id,
                owner_broker_id=_oz_filtr(user, "hujjat.korish"))


@app.get("/erp/invoices/stats")
def erp_invoice_stats(user: Dict[str, Any] = Depends(me)):
    """Holat bo'yicha soni/summasi va QARZ (chiqarilgan, to'lanmagan).
    Rahbar ko'rinishi — pul haqidagi ko'rsatkich har kimga emas."""
    _can(user, "hisobot.kompaniya")
    return _erp(erp_invoice.stats)


@app.get("/erp/invoices/export-formats")
def erp_invoice_formats(user: Dict[str, Any] = Depends(me)):
    """Sozlangan eksport formatlari. BO'SH bo'lsa interfeys tugmani
    umuman ko'rsatmaydi — ishlamaydigan tugma yolg'on va'da."""
    _can(user, "hujjat.korish")
    return {"formats": erp_export.available()}


@app.post("/erp/invoices", status_code=201)
def erp_create_invoice(body: InvoiceIn, user: Dict[str, Any] = Depends(me)):
    """Yangi faktura (qoralama). Ikkala tomonning rekvizitlari SHU PAYTDA
    ko'chiriladi va keyin o'zgarmaydi."""
    _can(user, "hujjat.qoralama")
    return _erp(erp_invoice.create,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.post("/erp/opportunities/{opp_id}/invoice", status_code=201)
def erp_invoice_from_opp(opp_id: int, body: InvoiceIn,
                         user: Dict[str, Any] = Depends(me)):
    """Kartadan faktura chiqarish: taklif -> shartnoma -> FAKTURA -> to'lov.

    Qatorlar kartaga AJRATILGAN tovarlardan olinadi (miqdor haqiqiy,
    narx katalogdan). Javobdagi `filled` nima qayerdan kelganini aytadi."""
    _can_obj(user, "hujjat.qoralama", "opportunity", opp_id)
    return _erp(erp_invoice.from_opportunity, opp_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.get("/erp/invoices/{invoice_id}")
def erp_invoice_get(invoice_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.korish", "invoice", invoice_id)
    return _erp(erp_invoice.get, invoice_id)


@app.put("/erp/invoices/{invoice_id}")
def erp_invoice_update(invoice_id: int, body: InvoiceIn,
                       user: Dict[str, Any] = Depends(me)):
    """Faqat QORALAMA tahrirlanadi. Chiqarilgan hujjat muzlatilgan."""
    _can_obj(user, "hujjat.qoralama", "invoice", invoice_id)
    return _erp(erp_invoice.update, invoice_id, body.model_dump(),
                auth.actor(user))


@app.put("/erp/invoices/{invoice_id}/status")
def erp_invoice_status(invoice_id: int, body: InvoiceStatusIn,
                       user: Dict[str, Any] = Depends(me)):
    """Qoralamadan CHIQARISHGA o'tish — raqam beriladi va hujjat
    muzlaydi; bekor qilish esa chiqarilgan hujjatga tegish. Ikkalasi
    ham brokerning ishi emas (`erp_rollar.md` §3.4)."""
    _can_obj(user, "hujjat.bekor" if body.status == "cancelled"
             else "hujjat.chiqarish", "invoice", invoice_id)
    return _erp(erp_invoice.set_status, invoice_id, body.status,
                auth.actor(user))


@app.post("/erp/invoices/{invoice_id}/lines", status_code=201)
def erp_invoice_add_line(invoice_id: int, body: InvoiceLineIn,
                         user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.qoralama", "invoice", invoice_id)
    return _erp(erp_invoice.add_line, invoice_id, body.model_dump(),
                auth.actor(user))


@app.delete("/erp/invoices/{invoice_id}/lines/{line_id}")
def erp_invoice_del_line(invoice_id: int, line_id: int,
                         user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.qoralama", "invoice", invoice_id)
    return _erp(erp_invoice.delete_line, invoice_id, line_id,
                auth.actor(user))


@app.post("/erp/invoices/{invoice_id}/payments", status_code=201)
def erp_invoice_pay(invoice_id: int, body: PaymentIn,
                    user: Dict[str, Any] = Depends(me)):
    """To'lov qaydi. To'liq to'langanda status AVTOMATIK 'paid' bo'ladi."""
    _can_obj(user, "hujjat.tolov", "invoice", invoice_id)
    return _erp(erp_invoice.add_payment, invoice_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.delete("/erp/payments/{payment_id}")
def erp_invoice_unpay(payment_id: int, user: Dict[str, Any] = Depends(me)):
    """Xato kiritilgan to'lovni o'chirish. Faktura 'paid' edi va endi
    yetmay qolsa — status 'issued' ga qaytariladi."""
    _can(user, "hujjat.tolov")
    return _erp(erp_invoice.delete_payment, payment_id, auth.actor(user))


@app.get("/erp/invoices/{invoice_id}/export")
def erp_invoice_export(invoice_id: int, fmt: str = Query(...),
                       user: Dict[str, Any] = Depends(me)):
    """Eksport. HOZIRCHA HECH QANDAY FORMAT SOZLANMAGAN — 501 va sababi
    ochiq aytiladi (`api/erp/invoice_export.py`)."""
    _can_obj(user, "hujjat.eksport", "invoice", invoice_id)
    inv = _erp(erp_invoice.get, invoice_id)
    return _erp(erp_export.build, inv, fmt)


# --- DALOLATNOMA (akt) -------------------------------------------------------
# Faktura "qancha to'lash kerak" deydi, akt "bajarildi" deydi. Hisob-kitob
# fakturaniki bilan BIR XIL kod (`invoice.line_totals`) — ikki xil
# yaxlitlash ikki xil summa degani bo'lardi.
@app.get("/erp/acts")
def erp_acts(status: Optional[str] = None, client_id: Optional[int] = None,
             invoice_id: Optional[int] = None,
             opportunity_id: Optional[int] = None,
             user: Dict[str, Any] = Depends(me)):
    return _erp(erp_act.list_, status, client_id, invoice_id, opportunity_id,
                owner_broker_id=_oz_filtr(user, "hujjat.korish"))


@app.post("/erp/acts", status_code=201)
def erp_create_act(body: ActIn, user: Dict[str, Any] = Depends(me)):
    _can(user, "hujjat.qoralama")
    return _erp(erp_act.create,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.post("/erp/invoices/{invoice_id}/act", status_code=201)
def erp_act_from_invoice(invoice_id: int, body: ActIn,
                         user: Dict[str, Any] = Depends(me)):
    """Fakturadan dalolatnoma: qatorlar KO'CHIRILADI (bog'lanmaydi).

    Sabab: faktura keyin bekor qilinishi mumkin, dalolatnoma esa
    bajarilgan ishning dalili va o'z holicha turishi kerak."""
    _can_obj(user, "hujjat.qoralama", "invoice", invoice_id)
    return _erp(erp_act.from_invoice, invoice_id,
                {**body.model_dump(), "created_by": auth.actor(user)})


@app.get("/erp/acts/{act_id}")
def erp_act_get(act_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.korish", "act", act_id)
    return _erp(erp_act.get, act_id)


@app.put("/erp/acts/{act_id}")
def erp_act_update(act_id: int, body: ActIn,
                   user: Dict[str, Any] = Depends(me)):
    """Faqat QORALAMA tahrirlanadi."""
    _can_obj(user, "hujjat.qoralama", "act", act_id)
    return _erp(erp_act.update, act_id, body.model_dump(),
                auth.actor(user))


@app.put("/erp/acts/{act_id}/status")
def erp_act_status(act_id: int, body: ActStatusIn,
                   user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.bekor" if body.status == "cancelled"
             else "hujjat.chiqarish", "act", act_id)
    return _erp(erp_act.set_status, act_id, body.status, body.signed_at,
                auth.actor(user))


@app.post("/erp/acts/{act_id}/lines", status_code=201)
def erp_act_add_line(act_id: int, body: InvoiceLineIn,
                     user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.qoralama", "act", act_id)
    return _erp(erp_act.add_line, act_id, body.model_dump(),
                auth.actor(user))


@app.delete("/erp/acts/{act_id}/lines/{line_id}")
def erp_act_del_line(act_id: int, line_id: int,
                     user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "hujjat.qoralama", "act", act_id)
    return _erp(erp_act.delete_line, act_id, line_id, auth.actor(user))


@app.get("/erp/contracts/{contract_id}/specification")
def erp_contract_spec(contract_id: int, user: Dict[str, Any] = Depends(me)):
    """Shartnoma ILOVASI (spetsifikatsiya) uchun ma'lumot.

    ERP shartnoma MATNINI yozmaydi — huquqiy matn yurist ishi. Bu yerda
    faqat ilova: tomonlar, tovar/xizmat ro'yxati va jami. Ma'lumot
    fakturadan (muzlatilgan) yoki rezervlardan olinadi; javobdagi
    `source` qaysi biri ekanini aytadi."""
    _can_obj(user, "karta.korish", "contract", contract_id)
    return _erp(erp_contracts.specification, contract_id)


# --- O'ZGARISHLAR JURNALI (audit) --------------------------------------------
# "Kim, qachon va nimani o'zgartirdi?" Yozishni TRIGGER bajaradi, bu
# yerda faqat o'qish. Eng muhim savol — chiqarilgan fakturaga
# tegilganmi (`after_issue`) va u ERP dan tashqarida qilinganmi
# (`outside_erp`).
@app.get("/erp/audit")
def erp_audit_recent(days: int = Query(30, ge=1, le=3650),
                     limit: int = Query(200, ge=1, le=2000),
                     doc_type: Optional[str] = None,
                     only_frozen: bool = False,
                     only_outside: bool = False,
                     user: Dict[str, Any] = Depends(me)):
    """Oxirgi o'zgarishlar va yig'ma javob. Faqat rahbar: jurnalda pul
    hujjatlarining ichki tarixi bor."""
    _can(user, "hujjat.jurnal")
    return _erp(erp_audit.recent, days, limit, doc_type,
                only_frozen, only_outside)


@app.get("/erp/audit/{doc_type}/{doc_id}")
def erp_audit_doc(doc_type: str, doc_id: int,
                  user: Dict[str, Any] = Depends(me)):
    """Bitta hujjatning butun tarixi (`invoice` yoki `act`)."""
    _can(user, "hujjat.jurnal")
    return _erp(erp_audit.for_document, doc_type, doc_id)


# --- FOYDA -------------------------------------------------------------------
# "Bu tenderdan qancha ishladik?" Daromad — fakturaning QQS SIZ summasi
# (QQS davlatniki), tannarx — ombor harakatida MUZLATILGAN narx.
# Hisob to'liq bo'lmasa javob buni ochiq aytadi.
@app.get("/erp/profit")
def erp_profit_report(status: Optional[str] = None,
                      limit: int = Query(200, ge=1, le=1000),
                      user: Dict[str, Any] = Depends(me)):
    """Rahbar ko'rinishi: kartalar bo'yicha foyda va umumiy yig'indi.
    Pul haqidagi umumiy ko'rsatkich har kimga emas."""
    _can(user, "hisobot.foyda")
    return _erp(erp_profit.report, status, limit)


@app.get("/erp/opportunities/{opp_id}/profit")
def erp_profit_card(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Bitta kartaning foydasi. Karta ustida ishlayotgan odam o'z
    natijasini ko'rishi kerak, shuning uchun bu rahbarga cheklanmagan."""
    _can_obj(user, "karta.foyda", "opportunity", opp_id)
    return _erp(erp_profit.for_opportunity, opp_id)


@app.get("/erp/analytics")
def erp_analytics_view(stuck_days: int = Query(14, ge=1, le=180),
                       user: Dict[str, Any] = Depends(me)):
    """Rahbar tahlili: bosqichda o'tgan vaqt, voronka, broker sikli,
    qotib qolgan kartalar, yutqazish sabablari.

    YANGI JADVAL YO'Q — hammasi `opportunity_history` dan hisoblanadi
    (u 1-bosqichdan beri har o'tishni yozib boradi)."""
    _can(user, "hisobot.kompaniya")
    return _erp(erp_analytics.build, stuck_days)


@app.get("/erp/stats")
def erp_stats_view(days: int = Query(7, ge=1, le=90),
                   user: Dict[str, Any] = Depends(me)):
    """Rahbar paneli: qancha ishga olingan / topshirilgan / yutilgan /
    yutqazilgan / rad etilgan; broker va mijoz bo'yicha; yaqin deadline'lar."""
    _can(user, "hisobot.kompaniya")
    return _erp(erp_stats.build, days)


# ---------------------------------------------------------------------------
# Mijoz korxonalar (2-bosqich)
# ---------------------------------------------------------------------------
@app.get("/erp/clients")
def erp_client_list(q: Optional[str] = None, active_only: bool = False, user: Dict[str, Any] = Depends(me)):
    """2-bosqich patchi qo'llangan bo'lsa — passport va natijalar bilan;
    bo'lmasa 1-bosqichdagi qisqa ro'yxat (id, nom, faol)."""
    _can(user, "mijoz.korish")
    if not erp_clients.schema_ready():
        return _erp(erp_opp.clients)
    return _erp(erp_clients.list_, q, active_only,
                owner_broker_id=_oz_filtr(user, "mijoz.korish"))


@app.post("/erp/clients", status_code=201)
def erp_add_client(c: ClientCompanyIn, user: Dict[str, Any] = Depends(me)):
    _can(user, "mijoz.tahrirlash")
    # Passport jadvallari yo'q bo'lsa "+ yangi" tugmasi ishlayversin —
    # 1-bosqichdagi oddiy yaratishga tushib qolamiz.
    if not erp_clients.schema_ready():
        return _erp(erp_opp.add_client, c.name)
    return _erp(erp_clients.create, c.model_dump())


@app.get("/erp/clients/{client_id}")
def erp_client(client_id: int, user: Dict[str, Any] = Depends(me)):
    """Passport + aloqa shaxslari + hujjatlar + shu mijozning kartalari."""
    _can_obj(user, "mijoz.korish", "client", client_id)
    return _erp(erp_clients.get, client_id)


@app.put("/erp/clients/{client_id}")
def erp_update_client(client_id: int, c: ClientCompanyIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.tahrirlash", "client", client_id)
    return _erp(erp_clients.update, client_id, c.model_dump())


@app.post("/erp/clients/{client_id}/contacts", status_code=201)
def erp_add_contact(client_id: int, c: ClientContactIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.aloqa", "client", client_id)
    return _erp(erp_clients.add_contact, client_id, c.model_dump())


@app.put("/erp/client-contacts/{contact_id}")
def erp_update_contact(contact_id: int, c: ClientContactIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.aloqa", "client_contact", contact_id)
    return _erp(erp_clients.update_contact, contact_id, c.model_dump())


@app.delete("/erp/client-contacts/{contact_id}")
def erp_delete_contact(contact_id: int, user: Dict[str, Any] = Depends(me)):
    """Javob — yangilangan MIJOZ kartasi (204 emas): interfeys ro'yxatni
    qayta so'ramasin."""
    _can_obj(user, "mijoz.aloqa", "client_contact", contact_id)
    return _erp(erp_clients.delete_contact, contact_id)


@app.get("/erp/clients/{client_id}/documents")
def erp_client_documents(client_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.korish", "client", client_id)
    return _erp(erp_clients.documents, client_id)


@app.post("/erp/clients/{client_id}/documents", status_code=201)
def erp_add_client_document(client_id: int, d: ClientDocumentIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.hujjat", "client", client_id)
    return _erp(erp_clients.add_document, client_id, d.model_dump())


@app.put("/erp/client-documents/{doc_id}")
def erp_update_client_document(doc_id: int, d: ClientDocumentIn, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.hujjat", "client_document", doc_id)
    return _erp(erp_clients.update_document, doc_id, d.model_dump())


@app.delete("/erp/client-documents/{doc_id}", status_code=204)
def erp_delete_client_document(doc_id: int, user: Dict[str, Any] = Depends(me)):
    _can_obj(user, "mijoz.hujjat", "client_document", doc_id)
    _erp(erp_clients.delete_document, doc_id)
    return Response(status_code=204)


# --- mijoz hujjatlari: shablon va import ------------------------------------
# Shablonni tender-ai yasaydi, faylni u tekshiradi, YOZISH esa ERP'da —
# qoidalar bir joyda, ma'lumot o'z bazasida (api/tenderai.py ga qarang).
MAX_IMPORT_MB = int(os.environ.get("MAX_IMPORT_MB", "5"))


@app.get("/erp/clients/{client_id}/documents/template")
def erp_client_document_template(fmt: str = Query("xlsx", pattern="^(xlsx|csv)$"),
                                 user: Dict[str, Any] = Depends(me)):
    """Talab etiladigan hujjatlar ro'yxati bilan OLDINDAN TO'LDIRILGAN fayl.
    Broker raqam va sanalarni yozadi, so'ng import qiladi."""
    _can(user, "mijoz.korish")
    try:
        data, ctype = tenderai.template(fmt)
    except tenderai.TenderAiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    name = f"mijoz_hujjatlari_shablon.{fmt}"
    return Response(content=data, media_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/erp/clients/{client_id}/documents/import")
def erp_client_documents_import(
    client_id: int,
    file: UploadFile = File(..., description="To'ldirilgan shablon (.xlsx / .csv)."),
    dry_run: bool = Query(True, description="TRUE — faqat tekshirish, bazaga yozilmaydi."),
    user: Dict[str, Any] = Depends(me),
):
    """To'ldirilgan shablonni yuklaydi.

    Shartnoma katalog importi (P0-4) bilan bir xil: xato BITTA QATORNI
    to'xtatadi, importni emas; `dry_run=true` (default) bazaga umuman
    tegmaydi va "nechtasi qo'shiladi / yangilanadi" ni oldindan aytadi."""
    _can_obj(user, "mijoz.hujjat", "client", client_id)
    data = file.file.read()
    if len(data) > MAX_IMPORT_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Fayl {MAX_IMPORT_MB} MB dan katta.")
    try:
        parsed = tenderai.parse_documents(data, file.filename or "")
    except ValueError as e:                     # format yaroqsiz — foydalanuvchi xatosi
        raise HTTPException(status_code=422, detail=str(e))
    except tenderai.TenderAiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    counts = _erp(erp_clients.import_documents, client_id,
                  parsed.get("rows") or [], dry_run)
    return {**parsed, "dry_run": dry_run, "client_id": client_id, **counts}


# ---------------------------------------------------------------------------
# Tender-AI bilan integratsiya
# ---------------------------------------------------------------------------
@app.get("/erp/document-types")
def erp_document_types(user: Dict[str, Any] = Depends(me)) -> List[Dict[str, Any]]:
    """Kanonik hujjat turlari — tender-ai'dan. Ro'yxat U YERDA yashaydi
    (`compliance.DOC_TYPES`), ERP nusxa saqlamaydi: ikki ro'yxat vaqt o'tib
    ajralib ketardi va cheklist mijoz hujjatini tanimay qolardi."""
    try:
        return tenderai.document_types()
    except tenderai.TenderAiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


class TaqsimlashSorovIn(BaseModel):
    """Qayta taqsimlash so'rovi. Sabab MAJBURIY."""
    izoh: str


@app.post("/erp/opportunities/{opp_id}/taqsimlash-sorovi")
def erp_taqsimlash_sorovi(opp_id: int, body: TaqsimlashSorovIn,
                          user: Dict[str, Any] = Depends(me)):
    """"Bu ish menga to'g'ri kelmadi" — menejerga so'rov.

    Broker kartani O'ZI o'tkazolmaydi (huquqlar matritsasi), lekin
    so'rovi TARIXDA qoladi va menejerga xabar boradi."""
    _can_obj(user, "karta.taqsimlash_sorovi", "opportunity", opp_id)
    return _erp(erp_opp.taqsimlash_sorovi, opp_id, body.izoh,
                auth.actor(user))


@app.get("/erp/opportunities/{opp_id}/tahlil")
def erp_opportunity_tahlil(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Tender-AI TAHLILI — qaror paytidagi SNAPSHOT.

    ERP uni qayta hisoblamaydi (qoidalar Tender-AI da). Eng yangisi
    birinchi; eskilari tarixda qoladi — broker qaysi ma'lumotga
    qarab ish qilganini keyin tekshirish mumkin bo'lsin."""
    _can_obj(user, "karta.tahlil", "opportunity", opp_id)
    return {"items": _erp(erp_topshiriq.tahlil, opp_id)}


@app.get("/erp/opportunities/{opp_id}/compliance")
def erp_opportunity_compliance(opp_id: int, user: Dict[str, Any] = Depends(me)):
    """Kartaning MIJOZI hujjatlariga qarab cheklist.

    Qoidalar tender-ai'da (1400 qator, DOC_TYPES va matndan talab aniqlash) —
    ERP ularni takrorlamaydi. Mijoz hujjatlari ERP'da, shuning uchun ular
    tender-ai'ga YUBORILADI va tayyor natija qaytadi.
    """
    _can_obj(user, "karta.korish", "opportunity", opp_id)
    opp = _erp(erp_opp.get, opp_id)
    client = opp.get("client")
    docs = _erp(erp_clients.docs_for_compliance, client["id"]) if client else None
    try:
        res = tenderai.compliance(opp["tender_id"], docs)
    except tenderai.TenderAiUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    res["client"] = client
    res["doc_source"] = "client" if client else "company"
    return res


# =============================================================================
# ISHLAB CHIQARISH REJIMI — interfeysni SHU SERVER uzatadi
# =============================================================================
# Ishlab chiqishda ikki jarayon bor: Vite (:5174) sahifani beradi va
# `/api` ni backendga uzatadi. Ishlab chiqarishda esa Vite dev serverini
# qoldirish MUMKIN EMAS — u qayta yig'ish uchun mo'ljallangan, sekin va
# himoyalanmagan.
#
# Yechim eng soddasi: qurilgan `frontend/dist` ni SHU FastAPI uzatadi.
# Bitta jarayon, bitta port, CORS ham, proksi ham kerak emas.
#
# NEGA nginx EMAS: ichki ERP uchun yana bitta xizmatni o'rnatish,
# sozlash va yangilash — foydasidan ko'ra ko'proq ish. Kompaniya
# tashqariga chiqarmoqchi bo'lsa, o'shanda nginx qo'shiladi va bu joy
# o'zgarishsiz qolaveradi.
#
# `/api` PREFIKSI: mijoz kodi doim `/api/...` ga murojaat qiladi
# (Vite proksisi shunga sozlangan). Ishlab chiqarishda proksi yo'q,
# shuning uchun prefiksni SERVER kesadi — bitta build ikkala rejimda
# ham ishlaydi va "prod uchun boshqa build" degan xatolik manbai
# yo'qoladi.
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "frontend", "dist")


@app.middleware("http")
async def strip_api_prefix(request: Request, call_next):
    """`/api/erp/...` -> `/erp/...`. Mijoz kodi o'zgarmaydi."""
    p = request.scope.get("path", "")
    if p.startswith("/api/"):
        request.scope["path"] = p[4:]
    elif p == "/api":
        request.scope["path"] = "/"
    return await call_next(request)


def _mount_ui() -> bool:
    """Qurilgan interfeysni ulash. `dist` yo'q bo'lsa — JIM o'tkazamiz:
    ishlab chiqishda u kerak emas va uning yo'qligi xato emas."""
    index = os.path.join(UI_DIR, "index.html")
    if not os.path.isfile(index):
        return False

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Statik fayllar (`/assets/...`) — o'z yo'lida.
    app.mount("/assets", StaticFiles(directory=os.path.join(UI_DIR, "assets")),
              name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """SPA: manzilni brauzer emas, ilova hal qiladi.

        API yo'llari BU YERGA YETIB KELMAYDI — ular yuqorida
        ro'yxatdan o'tgan va Starlette tartib bo'yicha moslashtiradi.
        Noma'lum `/erp/...` esa 404 bo'lishi kerak, `index.html` emas:
        aks holda sinov ham, mijoz kodi ham xatoni sezmay qolardi."""
        if full_path.startswith(("erp/", "health", "docs", "openapi")):
            raise HTTPException(status_code=404, detail="Topilmadi.")
        f = os.path.join(UI_DIR, full_path)
        if full_path and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(index)

    return True


#: Interfeys ulandimi — `/health` shuni aytadi (joylashtirishda kerak).
UI_MOUNTED = _mount_ui()
