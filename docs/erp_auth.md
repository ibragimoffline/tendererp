# AUTH — kimlik, sessiya va rollar

`erp_arxitektura_3.md` 3-bo'limi auth'ni 5B ning **sharti** deb belgilagan
edi: pul (hisob-faktura) va moddiy qiymat (ombor) bilan ishlaganda "kim
yozdi?" degan savolga "dropdown'dan tanlangan ism" javob emas.

Bu hujjat — auth'ning bajarilgan holati. **Auth-1 da kimlik NOTO'G'RI
TOMONDA edi va u tuzatildi**; tuzatish sababi 1-bo'limda.

---

## 1. Qaror: KIM QAYERDA — ODAM ERP DA, KOMPANIYA TENDER-AI DA

Domen modeli quyidagicha:

- **Tender-AI** — tender agregatori. Unga **KOMPANIYA hisobi** bilan
  kiriladi. U yerda "hodim" degan tushuncha yo'q.
- **Tender ERP** — kompaniyaning **o'z ERP tizimi**. Odam — uning
  tushunchasi: kim tenderni oldi, kim mas'ul, kim shartnoma imzoladi.
- Tender-AI da tender olish **ERP dan kelayotgan hodimga** biriktiriladi,
  ya'ni ism ERP dan keladi.

```
  tender-ai (:8000)                 ERP (:8100)
  KOMPANIYA hisobi                  HODIM hisoblari
  ├─ company_account                ├─ erp.app_user  ──FK──> erp.broker
  ├─ company_session                ├─ erp.app_session
  └─ POST /auth/login               └─ POST /erp/auth/login

  Ikkalasi MUSTAQIL. Token uchun bir-biriga murojaat qilinmaydi.
```

### Nima xato edi (auth-1)

Auth-1 "bitta kimlik manbai" qoidasini cheklist va xabar yuborishdan
ko'chirgan edi: hodim hisoblari **tender-ai da** (`public.app_user`)
yotardi, ERP esa har so'rovda `GET /auth/me` ga borib tokenni
tekshirardi (60 soniya kesh bilan).

Qoida noto'g'ri ko'chirilgan. Cheklist qoidasi va SMTP siri haqiqatan
tender-ai niki. Hodim esa emas: u ERP ning eng markaziy tushunchasi va
`erp.broker` bilan bir jadvalda turishi kerak.

Xatoning amaliy oqibatlari:

| Auth-1 (xato) | Tuzatilgandan keyin |
|---|---|
| `broker_id` — oddiy son, FK yo'q (boshqa sxema) | **haqiqiy FK** `erp.broker(id)` ga |
| tender-ai yiqilsa ERP ga **kirib bo'lmasdi** | ERP mustaqil ishlaydi |
| har so'rovda tarmoq (kesh bilan ham) | bitta SQL so'rov |
| kompaniya hisobida rol va odam ismi aralash | har biri o'z joyida |

### Tuzatish qanday bajarildi (ma'lumot yo'qolmasdan)

1. `tender erp/schema_patch_erp_6.sql` — `erp.app_user`, `erp.app_session`
   yaratadi va `public.app_user` dagi hisoblarni **parol xeshi bilan
   birga** ko'chiradi. Idempotent: qayta yurganda 0 qator qo'shadi.
2. `tender-ai/schema_patch_auth_2.sql` — `company_account`,
   `company_session` yaratadi va **faqat ko'chirish amalga oshgan bo'lsa**
   `public.app_user` / `public.app_session` ni olib tashlaydi. Aks holda
   jadvallar joyida qoladi va operator ogohlantiriladi.

**Tartib muhim:** avval ERP patchi, keyin tender-ai patchi.

Sessiyalar ko'chirilmagan — hamma qaytadan kiradi.

---

## 2. Nima qilingan

**ERP (hodimlar va kimlik)**
- `schema_patch_erp_6.sql` — `erp.app_user` (FK `broker_id`),
  `erp.app_session`.
- `api/auth.py` — parol xeshi, sessiya, rollar, `actor()`.
- **56 endpointdan 51 tasi himoyalangan** (ochiq: `/health`, `/erp/meta`,
  `/erp/auth/*`); 3 tasi rahbar huquqini (`/erp/analytics`, `/erp/stats`,
  `/erp/contracts/stats`), 6 tasi admin huquqini (`/erp/users*`,
  `/erp/staff`, `PUT /erp/brokers/{id}`) talab qiladi.
- Kirish: `/erp/auth/login|logout|me|roles`.
- Hodim hisoblari (admin): `/erp/users` (GET, POST), `/erp/users/{id}`
  (PUT), `/erp/users/{id}/password` (PUT).
- `create_user.py` — birinchi adminni yaratish uchun CLI (`--brokers`
  bilan hodimlar ro'yxatini ko'rsatadi).
- **Hodimlar ekrani** (`/erp/staff`, `api/erp/staff.py`,
  `StaffPage.tsx`) — 9-bo'limga qarang.
- Kirish ekrani, `localStorage` da token, 401 da avtomatik chiqish.

**Tender-AI (kompaniya hisobi)**
- `schema_patch_auth_2.sql` — `company_account`, `company_session`.
- `api/auth.py` — o'sha parol/sessiya mexanizmi, **rolsiz**.
- 6 endpoint: `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/account`
  (GET, PUT), `/auth/password`.
- `create_company.py` — kompaniya hisobini yaratish CLI.

---

## 3. Qarorlar va sabablari

### 3.1. Parol xeshi — PBKDF2 (stdlib), `bcrypt` emas

`hashlib.pbkdf2_hmac('sha256', ..., 240_000)`. Yangi bog'liqlik yo'q
(`bcrypt` — C-kengaytma, Windows'da o'rnatish muammosi). Format ustunda
saqlanadi: `pbkdf2_sha256$<iterations>$<salt>$<hash>` — kuchliroq
algoritmga o'tish migratsiyasiz mumkin.

Ikkala tomonda **bir xil** mexanizm — atayin: kod takrorlangan, lekin
`api/db.py` dagi bilan bir xil sabab bo'yicha (`erp_arxitektura_2.md`).
Umumiy kutubxona ikki loyihani yana bir-biriga bog'lab qo'yardi.

### 3.2. Token bazada XESH ko'rinishida

`token_hash` — sha256. Baza dumpi qo'lga tushsa ham sessiyalarni tiklab
bo'lmaydi. Xom token faqat brauzerda. Sinov buni ham tekshiradi.

### 3.3. "Login yoki parol noto'g'ri" — bitta matn

Qaysi biri xato ekanini aytish mavjud loginlarni topishga yo'l ochadi.
Hisob topilmaganda ham parol **tekshiriladi** (soxta xesh bilan): aks
holda javob vaqti "bunday login bormi?" degan savolga javob berardi.

### 3.4. `created_by` SESSIYADAN

Ilgari bu maydon brauzerdan kelardi. Endi 5 joyda (ishga olish, status
o'zgarishi, vazifa, taklif, shartnoma) u **e'tiborga olinmaydi** va
sessiyadagi ism yoziladi. Bu auth'ning eng ko'p qiymat beradigan qismi.

Hisob hodimga bog'langan bo'lsa **hodim ismi ustun** (`actor()`):
kartalarda va tarixda bitta ism ko'rinsin.

### 3.5. Bitta hodimga bitta hisob

`app_user_broker_uq` — qisman UNIQUE indeks (`WHERE broker_id IS NOT NULL`).
Aks holda "mening ishlarim" filtri ikki xil javob berardi va tarixda ikki
xil ism paydo bo'lardi.

### 3.6. ~~Token `localStorage` da~~ → COOKIE (auth-4 da o'zgardi)

Dastlab token `localStorage` da edi: tender-ai interfeysi ERP API'siga
to'g'ridan-to'g'ri murojaat qilardi va cookie cross-site bo'lib qolardi.
Auth-3 da bu murojaat yo'qoldi (`ErpLink` endi o'z backendiga boradi),
ya'ni to'siq ham yo'qoldi.

Auth-4 da token **`HttpOnly` cookie**'ga ko'chdi — 9-bo'limga qarang.

### 3.7. Hisob O'CHIRILMAYDI

`active=false`. Uning ismi `created_by` / `changed_by` da tarixda qolgan.
`broker_id` esa bo'shatiladi — hodimga yangi hisob ochish mumkin bo'lsin.

### 3.8. Birinchi hisob — CLI, endpoint emas

"Foydalanuvchi yo'q bo'lsa ishlaydi" degan bootstrap endpointi — ochiq
eshik: baza tozalanganda yana ochiladi. Serverga kira oladigan odam esa
allaqachon eng katta huquqqa ega:

```
# ERP — hodim
cd 'D:\MVP projects\tender erp'
.venv/Scripts/python.exe create_user.py admin "Bosh administrator" --role admin
.venv/Scripts/python.exe create_user.py --brokers          # hodimlar ro'yxati
.venv/Scripts/python.exe create_user.py karimov "A. Karimov" --broker-id 10

# Tender-AI — kompaniya
cd 'D:\MVP projects\tender-ai'
.venv/Scripts/python.exe create_company.py alfa "Alfa Savdo MChJ"
```

---

## 4. Ataylab ochiq qolgan uch nuqta

| Nuqta | Sabab | Qachon yopiladi |
|---|---|---|
| `/health`, `/erp/meta` | interfeys login OLDIDAN holatni ko'rsatadi (sxema qo'llanganmi) | ochiq qoladi |
| ~~`GET /erp/tenders/{id}/opportunities`~~ | ~~tender-ai dagi `ErpLink`~~ | **auth-3 da YOPILDI** (8.4) |
| ~~Tender-AI ning boshqa endpointlari~~ | — | **auth-2 da YOPILDI** (8.1) |

Endi ochiq qolgani faqat birinchi qator: `/health` va `/erp/meta`.
Ular login OLDIDAN kerak — interfeys "baza tirikmi, sxema qo'llanganmi"
deb ko'rsatadi.

---

## 5. Rollar — faqat ERP da

`broker < menejer < rahbar < admin` (ierarxiya: yuqoridagi
quyidagining hamma huquqini oladi).

- **broker** — kartalar, mijozlar, vazifalar, shartnomalar.
- **menejer** — qo'shimcha: `/erp/analytics`, `/erp/stats`,
  `/erp/contracts/stats`, `/erp/profit`, `/erp/audit`. Bular **odamlar
  haqidagi** ko'rsatkichni ham beradi (kim necha kunda topshiradi),
  shuning uchun har kimga emas.
- **rahbar** — menejer huquqlari + kompaniya passporti
  (`tizim.kompaniya`). Farq huquqlar MATRITSASIDA
  (`api/erp/perm.py`, `erp_huquqlar.md`): menejer kundalik ishni
  yuritadi (taqsimlash, muddat), rahbar qaror va tasdiq beradi.
- **admin** — qo'shimcha: hodim hisoblarini boshqarish (`/erp/users`).

**Rol endi endpointda tekshirilmaydi.** Ierarxiya (`ROLE_RANK`) —
faqat quyi qatlam; haqiqiy qoida AMALLAR matritsasida
(`api/erp/perm.py`): endpoint "menejer kerak" demaydi, "bu amal —
`hujjat.chiqarish`" deydi. Batafsil: `erp_huquqlar.md`.

Rol ro'yxati UCH joyda: bazadagi `CHECK` (`schema_patch_erp_17.sql`),
`api/auth.py` (`ROLES`, `ROLE_RANK`) va interfeys turlari. Ular
ajralib ketmasligini `_tests/erp11_test.py` tekshiradi.

Avval rol uchta edi (`broker < manager < admin`) va `manager` ikki xil
odamni — direktorni va tender bo'limi boshlig'ini — bitta nom ostiga
qo'yardi. Sabab va ko'chirish: `schema_patch_erp_17.sql` sarlavhasi.

Kompaniya hisobida rol **yo'q**: huquq taqsimoti odamlar orasida bo'ladi,
odamlar esa ERP da. Tender-AI sinovi buni tekshiradi (`role` ustuni
bo'lmasligi kerak).

---

## 6. Sinov

```
# ERP — hodim kimligi
.venv/Scripts/python.exe _tests/erp6_test.py       # 104 tekshiruv

# Tender-AI — kompaniya hisobi
.venv/Scripts/python.exe _tests/auth_test.py       # 80 tekshiruv
```

Boshqa ERP sinovlaridan farqi: bu yerda **haqiqiy login** qilinadi.
Qolgan sinovlar (`erp_test` … `erp5_test`) FastAPI ning
`dependency_overrides` mexanizmi bilan kimlikni almashtiradi.

`erp6_test.py` endi **tender-ai'ga bog'liq emas** (auth-1 da u ishlamasa
sinov SKIP bo'lardi): hisoblar ERP ning o'z jadvalida.

Qamrov: tokensiz 401, yaroqsiz token 401, noto'g'ri parol 401 va **xato
matni qaysi biri xato ekanini aytmasligi**, xom tokenning bazada
saqlanmasligi, javobda parol/xesh yo'qligi, rollar (broker 403 / admin
200), hodim hisoblari CRUD (409 band login, 409 band hodim, 400 noma'lum
rol, 404), hodimlar ekrani (hodim + hisob bir qatorda, ochiq ishi borni
faolsizlantirib bo'lmasligi), chiqishdan keyin 401, faolsizlantirilgan
hisob kira olmasligi
va **`created_by` ning sessiyadan olinishi** (mijoz yolg'on ism yuboradi —
e'tiborga olinmaydi).

Chegara **ikki tomonlama** tekshiriladi: ERP `public.*` ga (jumladan
`company_account` ga) yozmaydi; tender-ai `erp.*` ga yozmaydi.

---

## 7. Hodimlar ekrani (admin)

Yon paneldagi **"Hodimlar"** bo'limi faqat administratorga ko'rinadi.

### 7.1. Nega bitta ekranda

Bu yerda ikki tushuncha uchrashadi va ular bir-biriga majburiy emas:

| | HODIM (`erp.broker`) | HISOB (`erp.app_user`) |
|---|---|---|
| Nima uchun | kartaga mas'ul, vazifa bajaruvchisi, tarixdagi ism | login, parol, rol |
| Bo'lmasligi mumkinmi | hisobsiz hodim — ha (omborchi tizimga kirmaydi) | hodimsiz hisob — ha (tizim administratori) |

Ikkalasini alohida ro'yxatda ko'rsatsak, "Karimovga hisob ochilganmi?"
degan savolga javob ikki ro'yxatni solishtirib topilardi. Shuning uchun
har bir hodim qatorida uning hisobi ham ko'rinadi, hodimga bog'lanmagan
hisoblar esa pastda alohida — ular hech qaysi qatorga tushmaydi va
ko'zdan yo'qolmasligi kerak.

### 7.2. Nima qilinadi

- hodim qo'shish (tez qo'shish "Ishga olish" formasida ham bor),
  tahrirlash, faolsizlantirish;
- hodimga **hisob ochish** (login + parol + rol) — hisob avtomatik shu
  hodimga bog'lanadi;
- rolni almashtirish, hisobni yopish/yoqish, parolni tiklash.

### 7.3. Ikki tanlov va sabablari

**Hodim qo'shish adminga cheklanmagan, tahrirlash — cheklangan.**
Qo'shish "Ishga olish" formasidagi tez qo'shish (mijoz qo'shish bilan bir
xil): karta ochayotgan broker ro'yxatda o'zini topmasa ish to'xtab
qolardi. Tahrirlash va faolsizlantirish esa boshqalarga ta'sir qiladi —
bu admin ishi.

**Ochiq ishi bor hodimni faolsizlantirib bo'lmaydi** (409). Aks holda
kartalar va bajarilmagan vazifalar ko'rinmas mas'ulga qolib ketardi.
Xatoda aniq son ko'rsatiladi ("3 ta ochiq karta va 2 ta vazifa"), ya'ni
nima qilish kerakligi o'zidan ko'rinadi: ishni boshqa hodimga o'tkazish.

Hodim ham, hisob ham **o'chirilmaydi** — `active=false`. Ism kartalarda,
vazifalarda va tarixda qolgan.

---

## 8. AUTH-2 — tender-ai ham yopildi

Auth-1 ERP ni yopgan edi, tender-ai esa ochiq turardi. Endi u ham yopiq.

### 8.1. Darvoza BITTA joyda, har endpointda emas

```python
app = FastAPI(..., dependencies=[Depends(gate)])
```

Tender-AI da 60 dan ortiq endpoint bor va ularning imzolari xilma-xil
(`Query(...)`, `File(...)`, `Header(...)`). Har biriga qo'lda `Depends()`
qo'shib chiqilsa **bir nechtasi e'tibordan chetda qolishi aniq** — ERP
tomonida aynan shunday bo'lgan edi: bitta endpoint (`/erp/document-types`)
ochiq qolib ketgan va uni faqat keyingi audit topgan.

Global darvozaning asosiy foydasi shunda: u **yopiq holatda boshlanadi**.
Ro'yxatga OCHIQlar yoziladi, yopiqlar emas — ya'ni ertaga qo'shiladigan
endpoint avtomatik himoyalangan bo'ladi.

Ochiq qolganlar (`PUBLIC_PATHS` / `PUBLIC_PREFIXES`) sanoqli:

| Yo'l | Sabab |
|---|---|
| `/health` | interfeys login OLDIDAN holatni ko'rsatadi |
| `/auth/login` | kirishning o'zi |
| `/docs`, `/openapi.json`, `/redoc` | Swagger — sxema, ma'lumot emas |
| `/catalog/import/template`, `/company/documents/template` | BO'SH shablon (faqat ustun sarlavhalari); ularni `<a href>` yuklab oladi va u sarlavha yubora olmaydi |
| `/documents/...` | tender e'lonining ilovasi — davlat portalida ham ochiq; yuklab olish `<a href>` orqali |

### 8.2. ERP qanday kiradi: SERVICE kaliti

ERP tender-ai ga **odam nomidan bormaydi**: cheklist qoidasi, hujjat
shabloni va xabar yuborish — ERP ning o'z ishi va u fonda ham bajariladi
(tungi eslatma skriptida, hech kim kirmagan paytda). Kompaniya sessiyasi
bunga mos emas — u brauzerda tug'iladi va muddati tugaydi.

Shuning uchun ikkinchi yo'l: `X-Service-Key` sarlavhasi
(`.env` -> `ERP_SERVICE_KEY`, ikkala loyihada bir xil).

**Kalit hamma eshikning kaliti EMAS.** U faqat ERP haqiqatan ishlatadigan
oltita endpointni ochadi (`SERVICE_PATHS`); qolganiga **403**:

```
GET  /tenders/{id}              GET  /company/document-types
GET  /tenders/{id}/pricing      POST /company/documents/parse
POST /tenders/{id}/compliance   POST /notify/send
```

Katalog, saqlangan qidiruvlar, profil va sozlamalar ERP ga kerak emas va
ochilmaydi ham. Kalit sozlanmagan bo'lsa tekshiruv **har doim `False`**:
"sozlanmagan" degani "hammaga ochiq" degani emas.

Kalit **serverda qoladi** — brauzerga hech qachon yuborilmaydi, aks holda
uni JS to'plamidan o'qib olish mumkin bo'lardi.

### 8.3. "Mening ishlarim" endi haqiqatan MENING

Hisob hodimga bog'langan bo'lsa `GET /erp/my-tasks` **sukut bo'yicha
o'shaniki**. Ekranning nomi shuni va'da qilgan edi, lekin ilgari har
ochilganda ro'yxatdan o'zini qidirib topish kerak edi.

- `everyone=true` — hammaniki (rahbar ko'rinishi);
- `broker_id=N` — aniq hodimniki.

Ikkalasi ham har kimga ochiq: vazifalar allaqachon hamma ko'radigan
ma'lumot, bu maxfiylik chegarasi emas. Hisob hodimga bog'lanmagan bo'lsa
(masalan administrator) sukut — hammaniki.

### 8.4. AUTH-3: oxirgi istisno yopildi (VIEW-shartnoma)

`GET /erp/tenders/{id}/opportunities` ochiq qolgan edi: uni tender-ai
interfeysidagi `ErpLink` **brauzerdan** chaqirardi, brauzer esa
server-server kalitini ushlab turolmaydi (kalit JS to'plamiga tushib
qolardi).

**Tanlangan yechim (B):** so'rovni endi SERVER qiladi va u ERP ga HTTP
yubormaydi — `erp.v_tender_status` **view** ini o'qiydi.

```
  ErpLink (brauzer)
      │  GET /tenders/{id}/erp-status      (kompaniya sessiyasi bilan)
      ▼
  tender-ai backend  ──SQL(read-only)──>  erp.v_tender_status
```

**Nega jadval emas, VIEW.** Bu ataylab **shartnoma**: tender-ai
`erp.opportunity` ning ustunlariga emas, ERP kafolatlagan view shakliga
bog'lanadi. ERP ichida ustun nomi o'zgarsa yoki jadval bo'linsa — view
moslashtiriladi va tender-ai umuman sezmaydi.

**Chegara qoidasi endi SIMMETRIK** (`erp_arxitektura_2.md` yangilandi):

| Kim | Nima qiladi |
|---|---|
| ERP | `public.*` dan O'QIYDI (tender snapshoti), **YOZMAYDI** |
| Tender-AI | `erp.v_tender_status` dan O'QIYDI, **YOZMAYDI** |

Ikkala loyihaning sinovi ham har yurishda buni tekshiradi; tender-ai
tomonida yana ikki narsa tekshiriladi: view ga yozib bo'lmasligi
(`is_insertable_into = NO`) va `api/erp_status.py` da HTTP kutubxonasi
umuman yo'qligi.

**Maxfiylik.** View faqat `ErpLink` ko'rsatadigan narsani beradi: status,
mas'ul hodim va mijoz nomi. Summa, narx, izoh, tarix va shartnoma
BERILMAYDI — tender-ai ga kerak emas va sinov ularning javobda yo'qligini
tekshiradi.

**Status nomi (label) view ichida.** Aks holda tender-ai ERP ning status
ro'yxatini o'z kodida takrorlashi kerak bo'lardi. Endi ro'yxat uch joyda —
kod (`STATUSES`), bazadagi CHECK va view CASE i — va `erp_test.py`
**uchalasini** solishtiradi.

**Yon natija:** ERP ning CORS ro'yxatidan tender-ai interfeysi (5173)
olib tashlandi va `frontend/.env` dagi `VITE_ERP_API` endi kerak emas.
ERP endpointlarining **hammasi** himoyalangan; ochiq qolganlar faqat
`/health`, `/erp/meta` va `/erp/auth/*`.

### 8.5. ~~Ochiq qolgan bitta nuqta~~ — YOPILDI

Token `localStorage` da edi va XSS da o'g'irlanardi. Auth-4 da cookie +
CSRF ga o'tildi — 9-bo'lim.

### 8.6. Sinov

```
.venv/Scripts/python.exe _tests/auth_test.py       # 80 tekshiruv
```

Darvoza (namuna endpointlar tokensiz 401, ochiqlar 200), ochiq yo'llar
ro'yxatining **soni** (tasodifan kengayib ketmasin), service kaliti
(ruxsat berilgan eshik 200, qolgani 403, noto'g'ri kalit 401, bo'sh kalit
rad etiladi).

---

## 9. AUTH-4 — token `HttpOnly` cookie'da

### 9.1. Nima o'zgardi

| | Auth-3 gacha | Auth-4 dan keyin |
|---|---|---|
| Token qayerda | `localStorage` | **`HttpOnly` cookie** |
| JavaScript ko'radimi | **ha** (XSS o'g'irlaydi) | **yo'q** |
| Login javobida token | bor | **yo'q** (faqat CSRF tokeni) |
| So'rovda | `Authorization: Bearer` | cookie (brauzer o'zi) + `X-CSRF-Token` |

Cookie bayroqlari: `HttpOnly; Secure; SameSite=Lax; Path=/`.

### 9.2. Cookie'ning narxi — CSRF, va u qanday yopiladi

Cookie'ni brauzer **har** so'rovga o'zi qo'shadi. Ya'ni begona sayt
bizning nomimizdan so'rov yuborishi mumkin. Ikki qatlam:

1. **`SameSite=Lax`** — brauzer cookie'ni boshqa saytdan kelgan
   `POST`/`PUT`/`DELETE` ga qo'shmaydi. Bu birinchi va eng arzon to'siq.
2. **`X-CSRF-Token` sarlavhasi** — o'zgartiruvchi so'rovlarda majburiy.
   Sarlavhani begona sayt qo'ya olmaydi (CORS preflight to'sadi).

CSRF tokeni **`HttpOnly BO'LMAGAN`** cookie'da (`erp_csrf` / `tai_csrf`):
sahifa uni o'qib sarlavhaga qo'yadi. U **sir emas** va kirish huquqini
bermaydi — faqat "so'rovni bizning sahifamiz yubordimi" degan savolga
javob beradi. Shu sababli u login va `/auth/me` javoblarida ham qaytadi
(sahifa yangilanganda tiklash uchun).

### 9.3. Nega SESSIYAGA bog'langan (oddiy "double-submit" dan farqi)

Klassik double-submit da server faqat "cookie va sarlavha bir xilmi" deb
qaraydi. Agar hujumchi biror yo'l bilan cookie qo'ya olsa (subdomen,
MITM), ikkalasini ham o'zi to'ldirib qo'yardi.

Bizda token **sessiya qatorida** saqlanadi (`app_session.csrf_token`) va
sarlavhadagi qiymat **o'sha qator** bilan solishtiriladi
(`secrets.compare_digest`). Boshqa sessiyaning tokeni ham ishlamaydi —
sinov buni alohida tekshiradi.

Sessiya tokeni va CSRF tokeni **ikki xil qiymat**: bittasi bo'lsa,
ochiq nusxasi o'g'irlanganda kirish huquqi ham o'g'irlanardi.

### 9.4. Uch istisno va sabablari

| Istisno | Sabab |
|---|---|
| `GET`/`HEAD` da CSRF tekshirilmaydi | ular ma'lumotni o'zgartirmaydi va javobini begona sayt baribir o'qiy olmaydi (CORS) |
| **Chiqish** (`/auth/logout`) da CSRF tekshirilmaydi | begona sayt bizni "chiqarib yuborishi" zarar keltirmaydi; ammo tokeni eskirgan foydalanuvchining CHIQA OLMAY qolishi — keltiradi |
| **`Authorization: Bearer`** da CSRF tekshirilmaydi | u ATAYLAB qo'yiladi, cookie esa avtomatik qo'shiladi — "begona sayt bizning nomimizdan" holati yuzaga kelmaydi |

Bearer yo'li API mijozlari uchun **qoladi** (skript, sinov, kelajakdagi
integratsiya) va **oshkora sarlavha cookie'dan USTUN**: ikkalasi
uchrashganda oshkora qo'yilgani yutadi.

### 9.5. SERVICE kaliti bunga aralashmaydi

ERP ↔ tender-ai orasidagi `X-Service-Key` — cookie EMAS, alohida
sarlavha. Brauzer uni avtomatik qo'shmaydi, ya'ni CSRF xavfi yo'q va
unga CSRF sarlavhasi TALAB QILINMAYDI. Sinov buni ham tekshiradi.

### 9.6. Ikki amaliy shart

**1. So'rov SAME-ORIGIN bo'lishi kerak.** Ikkala interfeys ham o'z
backendiga Vite proksisi orqali boradi (`VITE_API_BASE=/api`). To'liq
manzil (`http://localhost:8000`) yozilsa cookie cross-site bo'lib qoladi
va kirish ishlamaydi. `frontend/.env.example` da bu yozib qo'yilgan.

**2. `Secure` va HTTP.** Brauzerlar `localhost` ni ishonchli deb
hisoblaydi, shuning uchun ishlab chiqishda ham `Secure` yoqiq qoladi.
HTTP orqali BOSHQA manzilda (masalan `192.168.x.x`) ochilsa cookie
saqlanmaydi — shuning uchun `.env` da `AUTH_COOKIE_SECURE=0` kaliti bor.
Uni **faqat** ichki tarmoqdagi ishlab chiqish uchun o'chiring.

### 9.7. Sxema

```
tender erp/schema_patch_erp_9.sql     erp.app_session.csrf_token
tender-ai/schema_patch_auth_3.sql     company_session.csrf_token
```

Ikkalasi CSRF ustuni bo'lmagan eski sessiyalarni **o'chiradi**: ular
"kirgan, lekin hech narsa yozolmaydigan" holatda osilib qolardi. Ya'ni
patchdan keyin hamma qaytadan kiradi — tokenlar qisqa umrli, zarari yo'q.

### 9.8. Sinov

```
tender erp:  _tests/erp6_test.py      # 121 tekshiruv
tender-ai:   _tests/auth_test.py      # 102 tekshiruv
```

Cookie bo'limi ikkalasida ham: `HttpOnly` va `SameSite=Lax` bayroqlari;
CSRF cookie'sining `HttpOnly` EMASligi; login javobida token yo'qligi;
`GET` CSRF siz ishlashi; `POST`/`PUT` CSRF siz va noto'g'ri CSRF bilan
**403**; to'g'ri CSRF bilan o'tishi; **boshqa sessiyaning** CSRF tokeni
ishlamasligi; chiqishda cookie tozalanishi.

Sinovlar `base_url="https://testserver"` bilan ishlaydi — `Secure`
cookie faqat shunda saqlanadi.

---

## 10. AUTH-5 — PAROL TANLASHDAN HIMOYA

### 10.1. Nima ochiq edi

Parol xeshi kuchli (PBKDF2, 240 000 iteratsiya) va u **bitta**
urinishni sekinlashtiradi. Lekin urinishlar **soni** hech qayerda
cheklanmagan edi va ular hech qanday iz qoldirmasdi.

Ya'ni tarmoqqa ulangan har kim `admin` login bilan lug'at bo'yicha
tinimsiz urinaverishi mumkin edi, kompaniya esa buni bilmasdi. Bu
kimlik qatlamidagi eng katta ochiq joy edi: qolgan hamma narsa
(cookie, CSRF, rollar) parol topilgach ma'nosiz bo'lib qoladi.

### 10.2. JURNAL, hisoblagich ustuni emas

`schema_patch_erp_15.sql` — `erp.login_attempt`: login, manzil,
natija, vaqt.

Sabab ombor qoldig'i bilan bir xil (`erp_ombor.md` 3). "Xato urinishlar
soni" degan ustun `5` deydi va shu bilan tamom: qachon, qayerdan va
qaysi login bilan ekanini ayta olmaydi, tozalash paytini ham kimdir
qo'lda hal qilishi kerak bo'ladi. Jurnal ikkala savolga javob beradi —
bloklash undan **hisoblanadi**, admin esa "kim kirishga urindi" degan
ro'yxatni ko'radi.

**Parol jurnalga yozilmaydi** — na ochiq, na xesh ko'rinishida.

### 10.3. HISOB BLOKLANMAYDI — eng muhim qaror

Odatiy yechim: 5 xatodan keyin hisobni yopish. Bu yerda u **ataylab
qilinmagan**.

Direktorning loginini bilgan har kim (u esa sir emas) uni bir necha
xato urinish bilan ishdan chiqarib qo'ya olardi. Ya'ni himoya vositasi
hujum vositasiga aylanadi va zarari brute-force dan katta bo'ladi.

Shuning uchun to'siq:

- **vaqtincha** (oyna 15 daqiqa);
- **(login + IP) juftligiga** tegadi, hisobga emas;
- hisobning `active` bayrog'i **umuman tegilmaydi**.

Boshqa manzildan o'sha login bilan kirish oddiy 401 bo'lib qolaveradi —
sinov aynan shuni tekshiradi.

### 10.4. Ikki kesim

| Kesim | Chegara | Nima uchun |
|---|---|---|
| login + IP | 5 / 15 daqiqa | odatiy holat |
| IP (hamma loginlar) | 25 / 15 daqiqa | login nomlarini aylantirib chiqib cheklovni chetlab o'tishga qarshi |

Raqamlar `.env` dan o'zgartiriladi (`AUTH_MAX_ATTEMPTS`,
`AUTH_MAX_ATTEMPTS_IP`, `AUTH_ATTEMPT_WINDOW_MIN`).

Ular **odam** uchun tanlangan: ishga kelib parolini ikki-uch marta
noto'g'ri yozgan hodim to'silib qolmasligi kerak, lug'at bo'yicha
urinayotgan dastur esa deyarli darhol to'xtashi kerak.

### 10.5. To'g'ri parol zanjirni UZADI

Xatolar **oxirgi muvaffaqiyatli kirishdan keyin** sanaladi. Kecha uch
marta adashgan hodim bugun toza varaqdan boshlaydi — hisob "eski
gunohlarni" eslab yurmaydi.

### 10.6. Tekshirish PAROLDAN OLDIN

`guard_attempts()` `login()` ning **birinchi** qadami. To'silgan
urinish qimmat xeshlashni ishga tushirmaydi — aks holda cheklovning
o'zi serverga yuk keltirish vositasiga aylanardi.

Shu sababdan bloklangan urinish jurnalga ham **yozilmaydi**: u umuman
tekshirilmadi.

### 10.7. `X-Forwarded-For` — faqat `TRUST_PROXY=1` bo'lganda

Odatda manzil `request.client` dan olinadi. Sarlavhani mijozning o'zi
yozib yuborishi mumkin — unga so'zsiz ishonish cheklovni bir qator matn
bilan chetlab o'tishga yo'l ochardi.

Lekin ERP nginx/IIS orqasiga qo'yilsa, `request.client` HAR DOIM
proksining o'zini ko'rsatadi: hamma so'rov bitta manzildan kelayotgandek
bo'ladi va IP kesimi ishlamay qoladi.

Yechim **sozlama, kod emas**: `TRUST_PROXY=1`. **Default o'chiq** —
to'g'ridan-to'g'ri ishlayotgan o'rnatma xavfsiz holatda qoladi va uni
yoqish ongli qaror bo'ladi.

**Nega OXIRGI manzil.** Sarlavha `mijoz, proksi1, proksi2`
ko'rinishida bo'ladi va **boshidagi** qiymatlarni mijoz o'zi yozib
yuborishi mumkin. Oxirgisini esa bizga eng yaqin (ishonchli) proksi
qo'yadi — u haqiqatan ko'rgan manzil.

```
X-Forwarded-For: 10.0.0.9, 203.0.113.55
                 ^^^^^^^^  ^^^^^^^^^^^^^
                 mijoz     proksi ko'rgan
                 yozgani   HAQIQIY manzil  <- shu olinadi
                 (e'tiborsiz)
```

**Diqqat:** ikki yoki undan ko'p proksi bo'lsa bu joy qayta ko'rib
chiqilishi kerak — o'shanda oxirgi qiymat ichki proksining manzili
bo'ladi. Kodda ham shu izoh turibdi.

Kod: `client_ip()` (`api/main.py`), ikkala loyihada bir xil.
Sinov: `erp6_test.py` — o'chiq holatda soxta sarlavha **yozilmaydi**,
yoqilganda **oxirgi** manzil olinadi va boshidagisi olinmaydi.

### 10.8. Javob nima deydi

`429` va `Retry-After` sarlavhasi; matnda esa necha daqiqa kutish
kerakligi.

Qolgan vaqt **aytiladi**: odam "tizim buzildimi?" deb o'ylab
qolmasligi kerak. Hujumchiga bu foyda bermaydi — u baribir kutishi
kerak.

### 10.9. Admin ko'rinishi

`GET /erp/auth/attempts` (faqat admin) — "kim, qayerdan, qachon".
Interfeys: **Hodimlar** ekranining pastida.

Har qatorda `known_user` bor: bunday login **bor** yoki **yo'q**.
Yo'q loginlar bilan urinish — hujumning eng ko'p uchraydigan izi
(hodim o'z loginini adashtirmaydi).

Ro'yxat faqat adminga: unda mavjud loginlar ko'rinadi.

### 10.10. Sxema qo'llanmagan bo'lsa

Himoya **jim o'chadi** va tizim ishlashdan to'xtamaydi (eski baza bilan
ham ko'tarilishi kerak). Lekin bu holat `check_setup.py` da patch
ro'yxatida **xato** sifatida ko'rinadi.

### 10.11. Sinov

`_tests/erp6_test.py` 8b-bo'lim: cheklovgacha 401 / keyin 429;
bloklangandan keyin jurnal o'smasligi; **boshqa IP dan 401** (hisob
bloklanmagan); `Retry-After` va matndagi vaqt; jurnalda parol ustuni
yo'qligi; **muvaffaqiyatdan keyin hisob noldan boshlanishi**; HTTP
qatlamida 429; admin ro'yxati va uning brokerga **403** bo'lishi.

### 10.12. Tender-AI tomoni ham yopildi

Xuddi shu qatlam tender-ai da ham qurildi: `schema_patch_auth_4.sql`
(`public.login_attempt`), `guard_attempts` / `record_attempt` /
`attempts`, `429` + `Retry-After`, `GET /auth/attempts`.

**Jadval ATAYLAB alohida.** `erp.login_attempt` ni ishlatish chegara
qoidasini buzardi — tender-ai `erp.*` ga yozmaydi. Har tizim o'z
eshigini o'zi qo'riqlaydi. Sinov buni tasdiqlaydi: tender-ai dagi
urinishdan keyin `erp.login_attempt` soni **o'zgarmaydi**.

Ikki tomondagi farqlar faqat ikkitasi va ikkalasi ham domendan
kelib chiqadi:

| | ERP | Tender-AI |
|---|---|---|
| Ro'yxatni kim ko'radi | **admin** (to'rt rol bor) | kirgan hisob (**rol yo'q**, hisob bitta) |
| Hisobni bloklamaslik sababi | loginni bilgan har kim hodimni to'sib qo'yardi | hisob BITTA — uni yopish butun kompaniyani uzib qo'yardi |

Cheklov raqamlari **bir xil** (`.env` dagi bir xil nomlar):
"qaysi eshik qancha ruxsat beradi" degan javobsiz savol bo'lmasin.

Interfeys tomoni ham farq qiladi: ERP interfeysi o'zbekcha, shuning
uchun serverning matni to'g'ridan-to'g'ri ko'rsatiladi. Tender-AI uch
tilli — u serverdan faqat `Retry-After` **sonini** oladi va xabarni
o'z tilida yig'adi (`auth.tooManyAttempts`).

Sinov: `tender-ai/_tests/auth_test.py` 8-bo'lim.

---

## 11. AUTH-6 — PAROLNI XAVFSIZ ALMASHTIRISH

### 11.1. Uchta ochiq joy

Parol almashtirish allaqachon bor edi (`PUT /erp/users/{id}/password`),
lekin uchta narsa yetishmasdi va uchalasi ham jiddiy:

1. **Eski parol so'ralmasdi.** Ochiq qolgan kompyuter yoki o'g'irlangan
   sessiya bilan begona odam parolni o'zgartirib, hisobni butunlay
   egallab olardi — egasi esa endi kira olmasdi.
2. **Parolga hech qanday talab yo'q edi.** `1` ham qabul qilinardi.
3. **Almashtirish boshqa sessiyalarni yopmasdi.** Ya'ni "parolimni
   o'zgartirdim" degan harakat o'g'irlangan tokenni bekor qilmasdi va
   butun amal ma'nosiz bo'lardi.

### 11.2. Talab: UZUNLIK, murakkablik EMAS

Minimal uzunlik — **10 belgi** (`AUTH_PASSWORD_MIN`). "Katta harf +
raqam + belgi" qoidasi ATAYLAB yo'q.

Murakkablik qoidalari amalda teskari natija beradi: odam `Parol123!`
yozadi va uni monitorga yopishtiradi. Uzun, lekin sodda ibora
(`qishloqdagi katta olma`) buni ancha ortda qoldiradi va yodda qoladi.
Bu — NIST 800-63B tavsiyasi.

Yana ikkita shart, ikkalasi ham amaliy:

- parol **login nomini** o'z ichiga olmasin;
- eng ko'p uchraydigan parollar ro'yxatida bo'lmasin. Ro'yxat qisqa
  ataylab: uzunlik talabi (10) ko'pchiligini allaqachon chetlab
  o'tadi, bu yerda faqat o'sha talabdan o'tib ketadiganlari qoldi.

Talab **yaratishda ham** amal qiladi (`create_user`), aks holda zaif
parol tizimga birinchi kundanoq kirib qolardi.

Xato matni NIMA QILISH kerakligini aytadi ("Parol kamida 10 belgi
bo'lsin"), aks holda odam taxmin qilib urinaverardi.

### 11.3. Ikki holat ATAYLAB har xil

| | O'ZINIKI | BOSHQANIKI (admin tiklaydi) |
|---|---|---|
| Joriy parol | **majburiy** | so'ralmaydi |
| Nima uchun | o'g'irlangan sessiya hisobni egallab olmasin | bu odatda "parolni unutdim" holati |
| Sessiyalar | boshqalari o'chadi, **o'ziniki qoladi** | **hammasi** o'chadi |

Oxirgi qator muhim: admin parolni tiklayotgan bo'lsa, demak hisobga
ishonch yo'q — hamma sessiya yopiladi. O'zi almashtirayotgan odam esa
tizimdan chiqib ketmasligi kerak, shuning uchun uning hozirgi
sessiyasi qoladi.

Qaysi sessiya "hozirgi" ekani `keep_token` orqali beriladi va u
DARVOZA bilan bir xil tartibda aniqlanadi (oshkora `Authorization`
sarlavhasi ustun, cookie — zaxira). Ikki joyda ikki xil tartib bo'lsa,
parolni almashtirgan odam o'zi tizimdan chiqib qolardi.

### 11.4. "Yangi parol eskisidan farq qilsin" — faqat O'ZI almashtirganda

Qoidaning maqsadi — "parolni yangiladim" deb o'sha parolni qayta yozib
qo'ymaslik. Admin (yoki CLI) ma'lum parolni QAYTA TIKLAYOTGAN bo'lsa,
bu boshqa amal: uni taqiqlash o'rnatish va sinov skriptlarini buzardi.

Shuning uchun tekshiruv `current` berilgandagina ishlaydi.

### 11.5. Javob nima qaytaradi

```json
{"ok": true, "closed_sessions": 2}
```

`closed_sessions` — yopilgan boshqa sessiyalar soni. U ekranda
ko'rsatiladi: odam "boshqa qurilmalarimdan chiqarildimi?" degan
savolga javob olishi kerak.

### 11.6. Tender-AI da ham shu qoida

`PUT /auth/password` — joriy parol majburiy, talab bir xil, boshqa
sessiyalar o'chadi. Farqi bittagina: u yerda hisob **bitta** va rol
yo'q, ya'ni "admin boshqaning parolini tiklaydi" holati umuman yo'q —
tiklash faqat serverdagi CLI (`create_company.py`) orqali bo'ladi.

### 11.7. Interfeys

**ERP.** Yon paneldagi "Parolni o'zgartirish" — **har kim** uchun.
Ilgari parolni almashtirishning yagona yo'li Hodimlar ekrani edi va u
faqat adminga ochiq, ya'ni broker o'z parolini umuman o'zgartira
olmasdi.

Hodimlar ekranidagi blok esa endi "almashtirish" emas, **"tiklash"**
deb ataladi va ostida yozib qo'yilgan: joriy parol so'ralmaydi, lekin
hisobning hamma sessiyasi yopiladi.

**Tender-AI.** Akkaunt sozlamalarida yangi **"Xavfsizlik"** bo'limi.
Unda Go/No-Go rozetkasi yo'q: bu profil to'liqligi emas, xavfsizlik
sozlamasi.

**PAROL QOIDASI INTERFEYSDA TAKRORLANMAYDI.** Uzunlik talabi faqat
serverda yashaydi va uning xato matni nima qilish kerakligini
aytadi ("Parol kamida 10 belgi bo'lsin"). Mijozda faqat formaning o'z
sharti tekshiriladi: maydonlar to'la va ikki nusxa mos. Sabab amaliy —
ikki joyda ikki xil raqam qolib ketishi vaqt masalasi, bu loyihada
bunday xato bir necha marta uchragan (`erp_ombor.md` dagi yorliqlar
hikoyasi).

`closed_sessions` ekranda AYTILADI: "Boshqa 2 ta sessiya yopildi —
ular qaytadan kirishi kerak". Odam "boshqa qurilmalarimdan
chiqarildimi?" degan savolga javob olishi kerak.

Tender-AI interfeysi uch tilli, server matni esa bitta tilda. Shuning
uchun bilingan holatlar (429) mijoz tilida yig'iladi, qolganlari
serverdan qanday kelsa shunday ko'rsatiladi: noma'lum xatoni
"tarjima qilib" yashirgandan ko'ra aslini ko'rsatgan afzal.

### 11.8. Sinov

`_tests/erp6_test.py` 6d-bo'lim va
`tender-ai/_tests/auth_test.py` 5g-bo'lim: zaif parol (qisqa / ko'p
uchraydigan / login nomi ichida) → 400; joriy parolsiz → 400;
noto'g'ri joriy parol → 400; yangi = eski → 400; to'g'ri almashtirish →
200 va `closed_sessions`; **o'z sessiyasi ishlaydi**; **boshqa sessiya
endi ishlamaydi**; yangi parol bilan kirish; admin tiklagach HAMMA
sessiya yopilishi; adminning ham zaif parol qo'yolmasligi.
