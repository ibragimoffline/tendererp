# INTEGRATSIYA — tender-ai tomonida nima o'zgaradi

ERP alohida loyiha (`erp_arxitektura_2.md`). Tender-AI tomonida
**uchta kichik o'zgarish** bor, boshqa hech narsa. Hammasi allaqachon
qo'llangan va sinovdan o'tgan; bu hujjat — boshqa nusxaga ko'chirish uchun.

Umumiy hajm: bitta yangi komponent (85 qator), UCH yangi endpoint
(cheklist, shablon parseri, xabar yuborish), ikki `.env` o'zgaruvchisi.
Kimlik esa baham ko'rilmaydi — 9-bo'limga qarang; parol tanlashdan
himoya ikkala tomonda alohida quriladi — 12-bo'lim.

---

## 1. `frontend/src/components/ErpLink.tsx` (yangi fayl)

Tender panelidagi ERP bloki: "ishga olinganmi?" degan savol, nishon va ikki
havola. Manzil berilmagan yoki ERP javob bermasa — **umuman ko'rinmaydi**.

Faylning o'zi ERP paketidagi nusxadan olinadi:
`tender erp/integratsiya/ErpLink.tsx`.

## 2. `frontend/src/components/TenderDrawer.tsx` (3 qator)

```tsx
import ErpLink from './ErpLink'
```

"Manbada ochish" havolasidan keyin:

```tsx
              {/* ERP (alohida loyiha) bilan yagona ulanish nuqtasi:
                  "ishga olinganmi?" degan savol va ERP interfeysiga havola. */}
              <ErpLink tenderId={t.id} />
```

## 3. `frontend/.env` (va `.env.example`)

```
# ERP (alohida loyiha) manzillari. Berilmasa tender panelidagi ERP bloki
# UMUMAN korinmaydi va ilova avvalgidek ishlayveradi.
VITE_ERP_WEB=http://localhost:5174
VITE_ERP_API=http://127.0.0.1:8100
```

> Vite `.env` ni **ishga tushish paytida** o'qiydi — o'zgartirgach dev
> serverni qayta ko'tarish kerak.

## 4. `api/main.py` — cheklist xizmati (yangi endpoint)

ERP mijoz korxonalarning hujjatlarini o'zi saqlaydi, qoidalar esa shu yerda.
Qoidalarning ikkinchi nusxasi bo'lmasligi uchun tender-ai ularni xizmat
sifatida beradi:

```python
class ComplianceDocsIn(BaseModel):
    """Tashqi tizim (ERP) yuboradigan hujjatlar. Maydonlari
    `company_document` bilan bir xil; `documents=None` bo'lsa shu
    kompaniyaning bazasi ishlatiladi."""
    documents: Optional[List[Dict[str, Any]]] = None


@app.post("/tenders/{tender_id}/compliance")
def tender_compliance_for(tender_id: int, body: ComplianceDocsIn):
    """CHEKLIST XIZMAT SIFATIDA — qoidalar shu yerda, hujjatlar chaqiruvchida.
    Bu yerda erp sxemasi haqida hech narsa bilinmaydi: kirish — oddiy
    ro'yxat, bog'liqlik bir tomonlama."""
    if not db.query_one("SELECT 1 AS x FROM tender WHERE id = %(id)s",
                        {"id": tender_id}):
        raise HTTPException(status_code=404, detail="Tender topilmadi.")
    res = compliance.check(tender_id, docs=body.documents)
    res["doc_source"] = "external" if body.documents is not None else "company"
    return res
```

`from typing import Any, Dict, List, Optional` — `Any` va `Dict` qo'shiladi.

## 5. `api/compliance.py` — `check()` ga bitta ixtiyoriy parametr

```python
def check(tender_id: int,
          docs: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """...
    NEGA `docs`, `client_id` EMAS: shunda bu modul erp sxemasi haqida hech
    narsa bilmaydi va `api.erp` ni import qilmaydi — bog'liqlik bir tomonlama.
    """
    from api import db

    texts = tender_texts(tender_id)
    if docs is None:
        docs = db.query(DOCS_LIST_SQL)
    ...
```

Parametr berilmasa xatti-harakat **o'zgarmaydi**: `GET /tenders/{id}/compliance`
avvalgidek kompaniya hujjatlariga qaraydi.

---

## 6. `api/main.py` — shablon parseri (yangi endpoint)

Mijoz hujjatlarini shablon bilan kiritish uchun ERP faylni o'qishi kerak,
lekin shablon qoidalari (ustun sarlavhalarini tanish, sana formatlari,
hujjat turini o'zbekcha/ruscha nomdan aniqlash) tender-ai'da va ular
**ikkinchi marta yozilmasligi** kerak:

```python
@app.post("/company/documents/parse")
def company_documents_parse(
    file: UploadFile = File(..., description="To'ldirilgan shablon (.xlsx / .csv)."),
):
    """SHABLON PARSERI XIZMAT SIFATIDA — faylni o'qiydi va tekshiradi,
    BAZAGA UMUMAN TEGMAYDI. ... Javobdagi `rows` — tozalangan qatorlar
    (sanalar ISO satr ko'rinishida), chaqiruvchi ularni o'zi saqlaydi."""
    data = file.file.read()
    if len(data) > MAX_IMPORT_MB * 1024 * 1024:
        raise HTTPException(status_code=413,
                            detail=f"Fayl {MAX_IMPORT_MB} MB dan katta.")
    try:
        ok, report = compliance.parse_document_file(data, file.filename or "")
    except importer.ImportFormatError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {**report, "rows": compliance.rows_json(ok)}
```

## 7. `api/compliance.py` — parser yozishdan ajratildi

`import_documents()` ichidagi O'QISH qismi `parse_document_file()` ga
chiqarildi; `import_documents()` endi shuni chaqirib, natijani
`company_document` ga yozadi. **Xatti-harakat o'zgarmadi** — mavjud
`POST /company/documents/import` avvalgidek ishlaydi (sinov: 113 ta
tekshiruv, yangi xato yo'q).

```python
def parse_document_file(data: bytes, filename: str) -> Tuple[List[Dict], Dict]:
    """To'ldirilgan shablonni O'QIYDI va tekshiradi — BAZAGA TEGMAYDI.
    NEGA ALOHIDA: natijani KIM saqlashi har xil bo'lishi mumkin — kompaniya
    hujjatlari yoki tashqi tizim (ERP mijoz korxonalari)."""

def rows_json(ok: List[Dict]) -> List[Dict]:
    """Tozalangan qatorlar -> JSON (sanalar ISO satr)."""
```

---

## 8. `api/main.py` — xabar yuborish xizmati (yangi endpoint)

ERP eslatma yuboradi (deadline va vazifa muddatlari), lekin TRANSPORT shu
o'rnatmada: SMTP rekvizitlari `.env` da, Telegram bot tokeni ham. Sirlarni
ikkinchi loyihaga nusxalash o'rniga tender-ai yuborishni xizmat sifatida
beradi.

```python
class NotifySendIn(BaseModel):
    """Tashqi tizim (ERP) yuboradigan xabar.

    QABUL QILUVCHI YO'Q: manzil qabul qilinmaydi va xabar FAQAT shu
    o'rnatmaning sozlangan manzillariga ketadi (bildirishnoma sozlamasidagi
    email va yoqilgan Telegram obunachilari). Shu tufayli endpoint ochiq
    relay bo'la olmaydi."""
    subject: str
    text: str
    html: Optional[str] = None
    channels: List[str] = ["telegram", "email"]


@app.post("/notify/send")
def notify_send(body: NotifySendIn):
    """... Kanal ishlamasa (masalan SMTP sozlanmagan) — xato butun so'rovni
    yiqitmaydi: natijada har kanal alohida hisobot beradi."""
```

Javob: `{"ok": bool, "email": {...} | null, "telegram": {...} | null}`.
Har kanal alohida hisobot beradi — biri ishlamasa ikkinchisi ketaveradi.

ERP tomonida bu `api/tenderai.py` -> `notify()` orqali chaqiriladi va
faqat `api/erp/remind.py` ishlatadi.

---

## 9. KIMLIK (auth) — KOMPANIYA hisobi

Bu integratsiya nuqtasi EMAS: kimlik baham ko'rilmaydi. Har bir tomon
o'zinikini tekshiradi.

- **Tender-AI** — KOMPANIYA hisobi bilan kiriladi. U tomonda qo'shiladi:
  `schema_patch_auth_2.sql` (`company_account`, `company_session`),
  `api/auth.py` (PBKDF2, sessiya, **rolsiz**), 6 endpoint
  (`/auth/login|logout|me`, `/auth/account` GET+PUT, `/auth/password`),
  `create_company.py` CLI.
- **ERP** — HODIM hisoblari (`erp.app_user`, FK `erp.broker` ga), rollar
  `broker < menejer < rahbar < admin`, `create_user.py` CLI.

Sabab: odam — ERP ning tushunchasi, kompaniya esa tender-ai niki.
Auth-1 da teskarisi qilingan edi va tuzatildi (`docs/erp_auth.md` 1-bo'lim);
`public.app_user` hisoblari `erp.app_user` ga parol xeshi bilan ko'chdi.

**Patch tartibi muhim:** avval ERP ning `schema_patch_erp_6.sql`,
keyin tender-ai ning `schema_patch_auth_2.sql` (u ko'chirish
bajarilganini tekshirib, eski jadvallarni olib tashlaydi).

### SERVICE kaliti (auth-2)

Tender-AI endpointlari endi YOPIQ. ERP u yerga odam nomidan bormaydi —
`X-Service-Key` sarlavhasi bilan boradi:

- `.env` da `ERP_SERVICE_KEY` — **ikkala loyihada bir xil**;
- kalit faqat ERP ishlatadigan 7 endpointni ochadi, qolganiga 403
  (oxirgisi — `GET /tenders/{id}/stock-check`: rezerv taklifi uchun);
- kalit serverda qoladi, brauzerga yuborilmaydi;
- **auth-4 unga tegmadi**: kalit cookie emas, alohida sarlavha —
  brauzer uni avtomatik qo'shmaydi, ya'ni CSRF xavfi yo'q va CSRF
  sarlavhasi talab qilinmaydi.

Yangisini yaratish:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Kalit sozlanmasa ERP cheklist va xabar yuborishni yo'qotadi (interfeys
buni ochiq aytadi), qolgan hamma narsa ishlayveradi.

### ERP holati — VIEW orqali (auth-3)

Tender-AI tomonida yana bitta fayl qo'shiladi: `api/erp_status.py` —
`erp.v_tender_status` view ini o'qiydi va `GET /tenders/{id}/erp-status`
ni beradi. `ErpLink.tsx` endi ERP backendiga EMAS, o'z backendiga
murojaat qiladi; `frontend/.env` dagi `VITE_ERP_API` kerak emas
(faqat `VITE_ERP_WEB` — havola uchun).

View ERP tomonida yaratiladi: `schema_patch_erp_7.sql`.

### Ombor qoldig'i — VIEW orqali (5B-1)

Yana bitta fayl: `api/erp_stock.py` — `erp.v_stock_balance` view ini
o'qiydi (faqat o'qish). U tender-ai ning IKKI joyiga ulanadi va yangi
endpoint qo'shmaydi:

- `GET /catalog` — har qatorda qoldiq ERP jurnalidan, `stock_source`
  bilan;
- `GET /tenders/{id}/stock-check` — javobda `stock.source`.

**REZERV bilan:** `stock_qty` endi **mavjud** miqdor
(`qoldiq - rezerv`), yoniga `stock_physical` va `stock_reserved`
qo'shiladi. Ya'ni boshqa tenderga ajratilgan tovar "yetadi" deb
ko'rsatilmaydi.

Qoldiqning egasi endi ERP: bu yerdagi `catalog_product.stock_qty` Excel
importidan qolgan surat. **Ombor bo'sh ekan** (jurnalda harakat yo'q)
eski xatti-harakat saqlanadi — o'rnatmani buzmaslik uchun.

View ERP tomonida yaratiladi: `schema_patch_erp_8.sql`.
Tafsilot: `docs/erp_ombor.md`.

Tafsilot: `docs/erp_auth.md` 8-bo'lim.

---

## 12. PAROL TANLASHDAN HIMOYA (auth-5) — IKKALA TOMONDA

Bu ham integratsiya nuqtasi emas: **har tizim o'z eshigini o'zi
qo'riqlaydi.** Lekin qatlam ikkalasida ham bir xil, shuning uchun shu
yerda yozilgan.

Tender-AI tomonida qo'shiladi:

- `schema_patch_auth_4.sql` — `public.login_attempt` (login, manzil,
  natija, vaqt; parol YO'Q);
- `api/auth.py` — `guard_attempts` / `record_attempt` / `attempts`,
  `login()` ga `ip` parametri;
- `api/main.py` — `_auth` da `429` uchun `Retry-After`, `/auth/login`
  da manzil, yangi `GET /auth/attempts`;
- `frontend`: `ApiError.retryAfter`, `LoginPage` da 429 xabari va
  `auth.tooManyAttempts` kaliti (uz/ru/en).

**Jadval ATAYLAB alohida.** `erp.login_attempt` ni ishlatish chegara
qoidasini buzardi (tender-ai `erp.*` ga yozmaydi) va "kim kimning
ma'lumotini yozdi" degan savolni tug'dirardi. Sinov buni tekshiradi:
tender-ai dagi urinishdan keyin `erp.login_attempt` soni **o'zgarmaydi**.

Cheklov raqamlari ikkala tomonda **bir xil** (`.env`:
`AUTH_MAX_ATTEMPTS`, `AUTH_MAX_ATTEMPTS_IP`,
`AUTH_ATTEMPT_WINDOW_MIN`) — aks holda "qaysi eshik qancha ruxsat
beradi" degan javobsiz savol paydo bo'lardi.

Qarorlar (ikkala tomonda bir xil, sabablari bilan):
`docs/erp_auth.md` 10-bo'lim.

---

## 13. PAROLNI XAVFSIZ ALMASHTIRISH (auth-6) — IKKALA TOMONDA

Yana bir "har tizim o'zi qiladi" qatlami, lekin qoida bir xil.
Tender-AI tomonida qo'shiladi:

- `api/auth.py` — `check_password()`, `set_password(..., current=,
  keep_token=)`, `PASSWORD_MIN` (`.env`);
- `api/main.py` — `PUT /auth/password` da joriy parol MAJBURIY;
- `frontend`: `PasswordPanel.tsx`, akkaunt sozlamalarida
  **"Xavfsizlik"** bo'limi, `pwd.*` kalitlari (uz/ru/en).

Sxema patchi KERAK EMAS — yangi jadval yo'q.

Farqi bittagina: tender-ai da hisob **bitta** va rol yo'q, ya'ni
"admin boshqaning parolini tiklaydi" holati umuman yo'q — tiklash
faqat serverdagi CLI (`create_company.py`) orqali.

Qarorlar va sabablari: `docs/erp_auth.md` 11-bo'lim.

---

## 14. SHARTNOMA-VIEW'LAR — ERP dan o'qiladigan yuza

`schema_patch_erp_19.sql` (ERP tomonida) to'rt view chop etadi va
`tai_app` ga faqat ularga `SELECT` beradi:

| View | Nima beradi |
|---|---|
| `erp.v_tender_status` | karta holati + `assignee_full_name` (YANGI ustun, oxirida) |
| `erp.v_tai_actor` | ERP hodimlari: `erp_user_id, full_name, rol, faol, erp_broker_id` |
| `erp.v_stock` | ombor qoldig'i (`v_stock_balance` ning shartnoma yuzasi) |
| `erp.v_client_document` | mijoz hujjatlari cheklist uchun (`expired` hisoblangan) |

Tender-AI tomonida bajariladigan ish: `actor` xaritasini
`v_tai_actor` dan to'ldirish, cheklistni `v_client_document` ga
o'tkazish (hozir ERP ularni HTTP orqali yuboradi — ro'yxat AYNAN bir
xil), `aktor_majburiy` ni xaritadan KEYIN yoqish.

Ustun faqat OXIRIGA qo'shiladi; shakl ERP sinovida qulflangan
(`_tests/erp15_test.py`). Batafsil: `docs/erp_integratsiya_6.md`.

---

## 15. YO'NALTIRISH OQIMI — "Olindi" ERP kartasiga aylanadi

Tender-AI tomonida (batafsil: `docs/erp_integratsiya_7.md`):

| Nima | Fayl |
|---|---|
| `tender_topshiriq` jadvali + `v_erp_topshiriq` view + `pg_notify` triggeri | `schema_patch_topshiriq.sql` (yangi) |
| Tahlil SNAPSHOTINI yig'ish va topshiriq yozish/bekor qilish | `api/topshiriq.py` (yangi, ~330 qator) |
| `POST /routing/{id}/decision` — tanaga `hodim_actor_id`, `ustuvorlik`, `muddat`; javobga `topshiriq` | `api/main.py` |
| `GET /routing/{id}/topshiriq` | `api/main.py` |
| Navbatda hodim/ustuvorlik/muddat tanlash va ERP natijasini ko'rsatish | `frontend/src/components/BrokerQueue.tsx`, `api.ts`, `locales/*.ts` |
| Sinov (37 tekshiruv): chegara, izolyatsiya, tahlil, takrorlanmaslik, `pg_notify` | `_tests/topshiriq_test.py` (yangi) |

ERP tomonida: `schema_patch_erp_21.sql`, `api/erp/topshiriq.py`
(`LISTEN` + zaxira so'rov), `PUT /erp/topshiriq/xarita`,
`POST /erp/topshiriq/sync`.

**Chegara buzilmadi:** Tender-AI `erp.*` ga yozmaydi (faqat 4 ta
shartnoma-view ni o'qiydi), ERP `public.*` ga yozmaydi (faqat
`v_erp_topshiriq` va `tender` ni o'qiydi).

---

## Nima QILINMAYDI (tender-ai tomonida)

- ERP JADVALLARIGA murojaat yo'q — na `api/`, na SQL, na migratsiya.
  O'qiladigan yagona narsa — 14-bo'limdagi shartnoma-view'lar.
- ERP status ro'yxati, formasi, sahifasi yo'q.
- `api/erp/` paketi yo'q (ajratishda o'chirildi).
- `components/erp/` yo'q; `types.ts` va `api.ts` da ERP turlari yo'q.

Tender-AI ERP haqida biladigan yagona narsa — `.env` dagi ikki manzil.

---

## Tekshirish

```
# tender-ai
.venv\Scripts\python.exe -c "from api.main import app; print(len(app.routes))"
cd frontend && npm run build

# ERP (alohida)
.venv\Scripts\python.exe _tests\erp_test.py     # 83 tekshiruv
.venv\Scripts\python.exe _tests\erp2_test.py    # 59 tekshiruv (tender-ai kerak)
cd frontend && npm run build
```
