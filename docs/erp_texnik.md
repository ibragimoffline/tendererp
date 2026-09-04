# Tender-AI ERP — TEXNIK HUJJAT (FastAPI steki bo'yicha)

Bu hujjat ERP modulining **texnik qurilishini** Tender-AI'da allaqachon
ishlayotgan stek va kelishuvlarga bog'laydi. Maqsad: ERP kodi loyihaning
qolgan qismidan **ajralib turmasin** — xuddi `compliance.py` yoki
`pricing.py` kabi o'qilsin, sinalsin, yurgizilsin.

Bog'liq hujjatlar: `erp_arxitektura.md` (qaror va chegaralar),
`erp_bosqichlar.md` (reja), `erp_integratsiya.md` (1-bosqich kodi).

---

## 1. Stek — nima bor, ERP nimadan foydalanadi

| Qatlam | Tender-AI'da | ERP'da |
|---|---|---|
| API | FastAPI, bitta `api/main.py`, `uvicorn` | o'sha ilova, endpointlar `/erp/*` prefiksi bilan |
| Validatsiya | Pydantic `BaseModel` (`...In` modellari) | `OpportunityIn`, `OpportunityStatusIn`, `BrokerIn`, `ClientCompanyIn` |
| Baza | PostgreSQL, `psycopg2`, `api/db.py` (`query`, `query_one`, `execute_returning`) | o'sha yordamchilar; `erp` sxemasi |
| SQL | matn konstantalari, `%(name)s` parametrlari | modul ichida (`api/erp/*.py`), `queries.py` ga qo'shilmaydi |
| Sozlama | `.env` + `python-dotenv` (`load_dotenv` importdan oldin) | yangi o'zgaruvchi **yo'q** (1-bosqich) |
| Frontend | React + Vite, `frontend/src/api.js` (`request()`, `apiUrl()`), CSS fayllar | `components/erp/*.jsx`, `styles/erp.css` |
| ETL/jadval | `run_etl.py` post-qadamlar, Windows Task Scheduler (`register_task.ps1`) | 1-bosqichda yo'q; 3-bosqichda eslatma post-qadami |
| Sinov | `_tests/*.py`, `fastapi.testclient.TestClient`, `ZZTEST ` prefiksli yozuvlar | `_tests/erp_test.py`, xuddi shu uslub |
| Migratsiya | `schema_patch_*.sql`, idempotent, `psql -f` | `schema_patch_erp_N.sql` |

Yangi kutubxona kerak emas. `requirements-api.txt` o'zgarmaydi.

---

## 2. Loyiha tuzilmasi (ERP qo'shilgandan keyin)

```
tender-ai/
├── api/
│   ├── main.py                 # FastAPI ilovasi; ERP bloki fayl oxirida
│   ├── db.py                   # query / query_one / execute_returning
│   ├── queries.py              # Tender-AI SQL (ERP tegmaydi)
│   ├── compliance.py, pricing.py, stock.py, notify.py, ...
│   └── erp/                    # ◀ YANGI paket
│       ├── __init__.py
│       ├── opportunity.py      # 1-bosqich
│       ├── stats.py            # 1-bosqich
│       ├── clients.py          # 2-bosqich
│       └── remind.py           # 3-bosqich (run_etl post-qadami)
├── frontend/src/
│   ├── api.js                  # + erp* chaqiruvlari
│   ├── App.jsx, components/Sidebar.jsx, components/TenderDrawer.jsx
│   ├── components/erp/         # ◀ YANGI
│   │   ├── OpportunitiesPage.jsx
│   │   ├── OpportunityBoard.jsx
│   │   ├── OpportunityTable.jsx
│   │   ├── OpportunityCard.jsx
│   │   ├── OpportunityStats.jsx
│   │   └── TakeTenderDialog.jsx
│   └── styles/erp.css
├── _tests/erp_test.py
├── schema_patch_erp_1.sql
└── erp_*.md                    # shu hujjatlar
```

---

## 3. Baza qatlami

### 3.1. `api/db.py` dan foydalanish

Loyihada uchta yordamchi bor va ERP faqat shularni ishlatadi:

```python
db.query(sql, params) -> list[dict]        # SELECT ko'p qator
db.query_one(sql, params) -> dict | None   # bitta qator
db.execute_returning(sql, params) -> dict | None   # INSERT/UPDATE/DELETE ... RETURNING
```

Qoidalar:
- Har SQL **`RETURNING`** bilan tugaydi — `execute_returning` natijani qaytarishi
  uchun (`compliance.md` dagi `DOC_UPDATE_SQL` uslubi). `RETURNING` siz
  UPDATE qilmang — "topilmadi" (404) ni ajratib bo'lmaydi.
- Parametrlar faqat `%(name)s`; satr birlashtirish (f-string bilan qiymat)
  **taqiq**. f-string faqat ustun ro'yxati (`_OPP_COLS`) uchun.
- `NUMERIC` → `Decimal` qaytadi, JSON uni bilmaydi → `_num()` (`pricing.md`
  dagi `_pnum` bilan bir xil). `TIMESTAMPTZ`/`DATE` → `_iso()`.
- Tranzaksiya: `db.py` har chaqiruvni o'zi commit qiladi (loyiha
  kelishuvi). Ikki yozuv birga bo'lishi shart bo'lgan joy bitta —
  `take()` dagi `INSERT opportunity` + `INSERT history`. 1-bosqichda bu
  qabul qilinadi: ikkinchisi yiqilsa karta tarixsiz qoladi, ma'lumot
  yo'qolmaydi. Agar `db.py` da `transaction()` kontekst-menejeri bo'lsa —
  ishlating; bo'lmasa qo'shmang (umumiy fayl).

### 3.2. Sxema qoidalari

- Hamma narsa `erp` sxemasida; SQL'da **har doim** `erp.` prefiksi
  (`search_path` ga tayanmang — `psql` va ilova ulanishi farq qilishi mumkin).
- `public.*` ga FK **yo'q** (sabab `erp_arxitektura.md` 2.1).
- `CHECK` cheklovlari statuslar va ustuvorlik uchun bazada ham, kodda ham
  (`STATUSES`, `PRIORITIES`) — ikkalasi bir xil ro'yxat; sinov buni tekshiradi.
- Patch idempotent: `CREATE ... IF NOT EXISTS`; ustun qo'shish —
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`; `CHECK` ni o'zgartirish kerak
  bo'lsa — `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT` (statuslar ro'yxati
  kengayganda aynan shu kerak bo'ladi, patch ichida izoh bilan).
- Bazaga qo'llash:
  ```
  psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_1.sql
  ```
  Boshqa muhitda ham shu buyruq — ilova patchni o'zi qo'llamaydi
  (loyiha kelishuvi: migratsiya — operator qadami).

### 3.3. Patch qo'llanmagan baza

`notify_lang.md` uslubi: ilova **yiqilmaydi**. `api/erp/opportunity.py` da:

```python
def schema_ready() -> bool:
    return bool(db.query_one(
        "SELECT 1 AS x FROM information_schema.tables "
        "WHERE table_schema='erp' AND table_name='opportunity'"))
```

`GET /erp/meta` javobida `"schema_ready": false` — interfeys
"`schema_patch_erp_1.sql` qo'llanmagan" deb ochiq aytadi, "Ishga olish"
tugmasi o'chiq turadi. Boshqa `/erp/*` endpointlar `schema_ready()` yolg'on
bo'lsa 503 qaytaradi (`ErpError(..., 503)`).

---

## 4. API qatlami

### 4.1. Endpoint joylashuvi

Loyihada router yo'q — hamma endpoint `api/main.py` da. ERP ham shu
kelishuvga bo'ysunadi: **bitta izohli blok**, fayl oxirida, mantiq esa
`api/erp/` da. `APIRouter` joriy qilish umumiy faylga tegadi va boshqa
modullardan farqlaydi — 1-bosqichda qilinmaydi. Endpointlar soni 20 dan
oshsa (2–3-bosqich) `APIRouter` ga o'tish mumkin, o'shanda `include_router`
bitta qator bo'ladi.

### 4.2. Xato kodlari (loyiha bo'yicha bir xil)

| Holat | Kod | Misol |
|---|---|---|
| Yozuv topilmadi | 404 | karta / tender / broker yo'q |
| Foydalanuvchi tuzata oladigan xato | 400 | izohsiz yakuniydan qaytish, noto'g'ri ustuvorlik |
| Takror | 409 | tender + mijoz allaqachon bor (`detail.opportunity_id` bilan) |
| Pydantic validatsiya | 422 | FastAPI o'zi |
| Sxema qo'llanmagan | 503 | `schema_patch_erp_1.sql` yo'q |

`detail` — **o'zbekcha, foydalanuvchiga ko'rsatiladigan** matn (loyiha
kelishuvi: "Tender topilmadi.", "Hujjat topilmadi."). 409 da `detail`
obyekt: `{"message": "...", "opportunity_id": 12}` — frontend havola quradi.

`ErpError` → HTTP ko'chirish `main.py` dagi `_erp()` yordamchisi orqali
(`erp_integratsiya.md` 3.3). Modul `HTTPException` ni **import qilmaydi** —
u FastAPI'dan mustaqil sinaladi (`pricing.py` kabi).

### 4.3. Pydantic modellari

- `...In` nomi (loyiha kelishuvi), `model_dump()` bilan dict ga.
- Sana maydonlari `date`/`datetime` — Pydantic ISO satrni o'zi parse qiladi.
- Javob modellari yozilmaydi (loyihada ham yo'q) — `shape()` funksiyalari
  dict qaytaradi. Javob shakli integratsiya hujjatida `jsonc` bilan hujjatlanadi.
- `exclude={...}` — mijozga ishonilmaydigan maydonlarni kesish uchun
  (`pricing.md` dagi "byudjetni mijozdan olmaymiz" tamoyili): `PUT` da
  `created_by` o'zgarmaydi, snapshot maydonlari umuman qabul qilinmaydi.

### 4.4. Parametrlar

- Filtrlar query-param, hammasi ixtiyoriy, SQL'da `%(x)s::type IS NULL OR ...`
  naqshi — bitta so'rov, shartli qatorlar yig'ish yo'q.
- `Query(7, ge=1, le=90)` — chegaralar FastAPI'da (`doctext.md` dagi
  `preview_chars` uslubi).

---

## 5. Frontend qatlami

### 5.1. So'rovlar

- Barcha chaqiruvlar `api.js` dagi `api` obyekti orqali (`erp*`). Fayl
  yuklash yo'q, shuning uchun `fetch`/`FormData` istisnosi (`import.md`)
  kerak emas.
- `request()` xatoda `detail` ni throw qiladi (loyiha kelishuvi) —
  komponentlar `err.message`/`err.detail` ni qizil matn bilan ko'rsatadi,
  jimgina yutmaydi.

### 5.2. Holat

- Sahifa holati `App.jsx` dagi `view` bilan (`'opportunities'`), tashqi
  router yo'q (loyihada ham yo'q).
- Kanban holati komponent ichida (`useState`); drag-and-drop optimistik:
  karta darhol ko'chadi, so'rov yiqilsa qaytadi va xato ko'rsatiladi.
- Lug'atlar (`statuses`, `priorities`, brokerlar, mijozlar) sahifa
  ochilganda bir marta yuklanadi va `props` bilan pastga uzatiladi.

### 5.3. Uslub

- `styles/erp.css` — komponentlar o'zi import qiladi; `styles.css` ga
  tegilmaydi (`import.md`, `compliance.md` kelishuvi).
- Mavjud klasslar qayta ishlatiladi: `btn btn--primary`, `btn--ghost`,
  `badge`, `drawer__section`, `muted-cell`, `num`. Yangi klasslar `erp-`
  prefiksi bilan — to'qnashuv yo'q.
- Ikonlar `Icon.jsx` dan mavjudlari; yangi ikon qo'shilmaydi.
- Kutubxona qo'shilmaydi: drag-and-drop — HTML5 `draggable`; grafiklar —
  CSS chiziqlar.

### 5.4. Mavjud panellarni qayta ishlatish

Karta tablari mavjud komponentlarni `tenderId` bilan chaqiradi —
`CompliancePanel`, `PricingPanel`, `StockCheck`. Ular `api.tender(id)`
javobiga tayanadi (`pricing.md` 3-bo'lim), shuning uchun karta ochilganda
`api.tender(tender_id)` bir marta so'raladi va `tender` obyekti tablarga
beriladi. Tender manbadan o'chirilgan bo'lsa (404) — tablar "Tender
manbada yo'q" deb ko'rsatadi, snapshot esa o'z joyida qoladi.

---

## 6. Sinov

```
.venv/Scripts/python.exe _tests/erp_test.py
```

- `TestClient(app)` — uvicorn yo'q (`import.md`, `pricing.md`).
- Haqiqiy baza (`.env` dan), vaqtinchalik yozuvlar `ZZTEST ` prefiksi bilan,
  `finally` da tozalash + tozalanganini tekshirish (`compliance.md` 8).
- `api/erp/opportunity.py` dagi sof funksiyalar (`shape`, status qoidalari)
  bazasiz ham sinaladi — bitta sinov fayli ikkala turni ham o'z ichiga oladi.
- **Chegara sinovi majburiy:** `public.*` asosiy jadvallarining qator soni
  va `max(updated_at)` sinovdan oldin va keyin bir xil.
- **BEGONA yozuvni o'zgartirsa — TIKLASIN.** `ZZTEST` prefiksi sinov
  YARATGAN yozuvni himoya qiladi, lekin sinov MAVJUD qatorni ham
  o'zgartirishi mumkin. Xavfli shakl — `WHERE` da toifa (`role IN
  (...)`, `WHERE active`), xavfsizi — sinovning O'Z id si.
  Toifa bo'yicha o'zgartirish kerak bo'lsa: id larni yozib oling,
  `finally` da tiklang va tiklanganini OCHIQ ayting.

  Bir marta buzilgan: `erp14_test.py` shartni sinash uchun BARCHA
  rahbar/menejer hisoblarini faolsizlantirardi va qaytarmasdi — ya'ni
  sinov to'plamini yurgizish kompaniyaning rahbar hisobini o'chirib
  qo'yardi, JIMGINA. Oqibati faqat keyingi `check_setup` javobida
  ko'rinardi. Butun `_tests/` ko'rib chiqildi (2026-09-04): boshqa
  hech qayerda bu shakl yo'q — qolgan `UPDATE`/`DELETE` lar o'z id si
  yoki `ZZ` belgisi bo'yicha tanlaydi.
- Bazadagi haqiqiy tender kerak (`take` uchun): `SELECT id FROM tender LIMIT 1`;
  baza bo'sh bo'lsa sinov shu qismini `SKIP` deb belgilaydi, yiqilmaydi.

### 6.1 Ikki qoida — uch marta takrorlangan xatodan keyin

Quyidagi ikki qoida 2026-09-04 da qo'shildi. Sabab: bitta xato sinfi
**uch marta** takrorlandi va uchinchisidan keyin bu tasodif emas,
arxitektura bo'shlig'i deb qabul qilindi.

**1. Tekshiruv MAVJUDLIKNI emas, YAROQLILIKNI o'lchasin.**

Uchala holat ham bir shaklda edi: obyekt bor -> "OK", lekin u to'g'ri
shaklda / to'g'ri rolda / to'g'ri patchdan ekani so'ralmasdi.

| Qayerda | Nimani o'lchardi | Nimani o'lchashi kerak edi |
|---|---|---|
| `check_setup` 26-patch | `chat_message` jadvali bor | `eslatilgan` USTUNI bor |
| `check_setup` 2-patch | `client_company` bor | `client_document` bor (2-patch qo'shadigani) |
| `check_setup` 20-patch | umuman tekshirilmasdi | `v_tai_actor.token_hash` (ikki SHAKLNI ajratadi) |
| `check_setup` hisoblar | 3 ta hisob bor | kamida bittasi RAHBAR/MENEJER |
| `check_setup` rekvizit | maydon bo'sh emas | INN 9 / MFO 5 / hisob 20 RAQAM |
| `check_setup` demo | 3 jadvalda 23 ta | 8 jadvalda 67 ta |
| `check_setup` service key | tender-ai javob berdi | kalit QABUL QILINDI — **hali yopilmagan**, pastga qarang |

Yangi tekshiruv yozganda savol bitta: **u nimani isbotlaydi va nimani
isbotlamaydi.**

Ikkinchisiga javob IZOH sifatida yoziladi — va agar tuzatib bo'lmasa,
IZOHDA QOLADI. Jadvaldagi oxirgi qator shunday: `ERP_SERVICE_KEY`
tekshiruvini bir tomonlama yopib bo'lmaydi, chunki kalit QABUL
QILINGANINI faqat tender-ai tomonidan 401 qaytishi isbotlaydi.
"Tuzatildi" deb belgilash yomonroq bo'lardi — o'sha paytdan boshlab
hech kim uni qayta ko'rmasdi. Ochiq qarz sifatida `REJA.md` da.

**2. Tekshiruv YIQILISHINI ko'rsatmasdan qabul qilinmaydi.**

Yashil rang tekshiruv ishlayotganini isbotlamaydi — u faqat "hozir
xato yo'q" deydi. Har yangi tekshiruv uchun uning YIQILGAN holati ham
ko'rsatilishi kerak: shartni vaqtincha buzib, xato berishini
tasdiqlash.

Amalda qo'llanilgani:

- `_tests/patch_test.py` — eski nuqsonli qatorlar qaytarilganda 2 ta
  XATO berishi tekshirildi;
- `check_setup` 26-patch — ustun vaqtincha o'chirilib, "qo'llanmagan"
  deb topishi tasdiqlandi;
- rekvizit shakli — `-` / `keyin` / `123` qo'yilib, ogohlantirish
  chiqishi ko'rildi;
- `run_erp.ps1` xavfsizlik qulfi — to'rtala holat (tarmoq+ochiq,
  localhost+ochiq, ongli chetlab o'tish, HTTPS) alohida yurgizildi.

Bu qoida sinovlarga ham tegishli: `patch_test.py` da izohlardagi
`CREATE TABLE` obyekt deb sanalmasligi ALOHIDA tekshiriladi — aks
holda tekshiruvni tekshiruvchining o'zi yolg'on "OK" bergan bo'lardi.

### 6.2 O'lchov — `olchov.py`

```
.venv/Scripts/python.exe olchov.py
.venv/Scripts/python.exe olchov.py --saqlamasdan
```

Loyihaning qoidasi — "yangi qatlam qo'shishdan OLDIN hisoblagichlarni
ko'ring" — bajarib bo'lmaydigan holatda edi: ko'radigan buyruq yo'q,
raqamlar har safar qo'lda so'rov yozib olinardi. Bu asbob o'sha
bo'shliqni yopadi. **Yangi qatlam emas — qoidani bajarish uchun
kerak bo'lgan o'lchagich.**

Uchta va'da (`_tests/olchov_test.py` qo'riqlaydi):

1. **Faqat o'qiydi.** Bazaga hech narsa yozmaydi; yagona yozuvi —
   o'z natijasi (`_olchov/YYYY-MM-DD.json`, `.gitignore` da).
2. **JAMI va ODAM alohida.** Yig'ma raqam yolg'on tasalli beradi:
   karta tarixi 77 ta ko'rinadi, odam yozgani 9 ta.
3. **O'lchanmagan narsa NOL EMAS.** Jadval yo'q bo'lsa `—`, `0`
   emas. Nol — o'lchandi va hech narsa topilmadi degani.

Chiqishda oxirgi oldingi yurish bilan farq ham bor (`+2`, `0`), ya'ni
"ikki hafta ishlangandan keyin o'zgardimi" degan savolga javob o'zi
keladi. Jadval ham, jurnal ham kerak emas.

**Manba bitta:** `check_setup.py` faol rahbar/menejer sonini
`olchov.boshliq_soni()` dan oladi va o'z SQL so'rovini yozmaydi.
Sinov buni tekshiradi (`check_setup` da qo'lda rol so'rovi qolmagan).

---

## 7. Yurgizish va muhit

Hech narsa o'zgarmaydi:

```
# API
.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000
# Frontend
cd frontend && npm run dev        # http://localhost:5173
```

- `.env` ga yangi o'zgaruvchi yo'q (1-bosqich).
- Soatlik ETL (`run_etl.py`, `register_task.ps1`) ERP'ga tegmaydi.
  3-bosqichda `api/erp/remind.py` `run_etl.py` ga **post-qadam** sifatida
  `etl.md` 4-bo'limdagi `run_script()` bilan qo'shiladi (UTF-8 chiqish
  uchun — o'z `subprocess` yozilmaydi).
- Windows: barcha yangi `.py` fayllar UTF-8, `print` da kirill/o'zbek
  matni bor — `PYTHONIOENCODING=utf-8` `run_script` beradi; to'g'ridan-to'g'ri
  yurgizishda `.venv` aktivlashtirilgan terminalda `chcp 65001`.

---

## 8. Kod kelishuvlari (loyihadagi bilan bir xil)

- Izohlar va `detail` matnlari — **o'zbekcha**; kodda "nega" izohi
  "nima" izohidan muhim (mavjud fayllardagi uslub).
- Har modul boshida docstring: vazifasi va **chegarasi** (nimaga tegmaydi).
- Konstantalar (`STATUSES`, `FINAL`, `PRIORITIES`) bitta joyda,
  `/erp/meta` orqali frontendga beriladi — frontendda takrorlanmaydi.
- Funksiya nomlari: modul darajasida `list_`, `get`, `take`, `update`,
  `set_status` — endpoint nomlari esa `erp_*` prefiksi bilan (`main.py`
  da boshqa endpointlar bilan to'qnashmasligi uchun).
- `queries.py`, `compliance.py`, `pricing.py`, `stock.py`, `notify.py` —
  **o'zgarmaydi**. 2-bosqichdagi `compliance.check(tender_id, client_id=None)`
  — yagona rejalashtirilgan istisno, ixtiyoriy parametr ko'rinishida.

---

## 9. Xavfsizlik va ma'lumot (hozirgi holatga mos)

- ~~Tizimda auth yo'q~~ — **ESKIRGAN (2026-09-02)**. Endi ikkala
  tomonda ham kimlik bor va ular **mustaqil**:
  * **ERP** — HODIM kiradi (`erp.app_user`, `docs/erp_auth.md`):
    login/parol, sessiya cookie, CSRF, to'rt rol va huquqlar
    matritsasi (`docs/erp_huquqlar.md`).
  * **Tender-AI** — KOMPANIYA kiradi (`company_account`), odam esa
    "aktor" sifatida e'lon qilinadi. ERP sessiyasi
    `erp.v_tai_actor` orqali ISBOTLANISHI mumkin — o'shanda ishonch
    darajasi `erp_sessiya` bo'ladi.
  * **SSO YO'Q va rejalashtirilmagan**: ikki tizim, ikki auditoriya.
  `created_by`/`changed_by` endi SESSIYADAN oladi (mijoz yuborgan
  ism e'tiborga olinmaydi), matn ustunlari esa saqlanib qoldi —
  tarixdagi eski yozuvlar yo'qolmasin.
- Sir saqlanadi: parol `pbkdf2_sha256` xeshi, sessiya tokeni esa
  faqat `sha256` xeshi ko'rinishida (`erp.app_session`). Xom token
  bazada YO'Q.
- Opportunity o'chirilmaydi — tarix rahbar uchun ma'lumot; noto'g'ri karta
  `rejected` + izoh.
- Mijoz ma'lumotlari (2-bosqich: INN, bank rekvizitlari) — baza dumpi
  ko'p qo'ldan o'tishini hisobga olib, passport maydonlari **bitta
  jadvalda** (`erp.client_company`) saqlanadi, keyin kirish cheklovi
  qo'yish oson bo'lsin.

---

## 10. Ishga tushirish tartibi (1-bosqich)

1. `schema_patch_erp_1.sql` → bazaga.
2. `api/erp/` fayllari → joyiga; `main.py` ga `erp_integratsiya.md` 3-bo'lim.
3. `TENDER_SNAPSHOT_SQL` dagi ustun nomlarini `queries.py` ga moslash.
4. `_tests/erp_test.py` → o'tishi.
5. `api.js`, `Sidebar.jsx`, `App.jsx`, `TenderDrawer.jsx` → 4–7-bo'limlar.
6. `components/erp/*` → joyiga; `npm run dev` → "Ishdagi tenderlar" bo'limi.
7. Qabul mezonlari — `erp_bosqichlar.md` 1-bosqich ro'yxati bo'yicha.
