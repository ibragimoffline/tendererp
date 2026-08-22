# ERP — ARXITEKTURA QARORI 2: AJRATISH

Bu hujjat `erp_arxitektura.md` dagi birinchi qarorni **almashtiradi**.
Birinchi qaror: "ERP tender-ai ichida, qat'iy chegaralangan modul
(modulli monolit). Alohida servis emas." Yangi qaror: **ERP alohida loyiha**.

---

## 1. Nima o'zgardi va nega

Qarorni loyiha egasi o'zgartirdi: maqsad boshidanoq **ikki mahsulotni
integratsiya qilish** edi, bitta ilova ichida ikkinchi bo'lim yasash emas.
Belgi ham ko'rinib qoldi — ERP sahifalari tender-ai interfeysining ichida
turgani uchun ikkalasi bitta loyihadek ko'rinardi.

Texnik sabab yo'q edi: 1- va 2-bosqich hujjatdagi qarorga to'liq mos
qurilgan. O'zgargani — **maqsad**, va u texnik qarordan ustun.

Ajratish arzon bo'ldi, chunki `erp_arxitektura.md` 2-bo'limidagi chegaralar
buzilmagan edi: alohida sxema, alohida paket, `/erp/*` prefiksi, alohida
komponent papkasi, bir tomonlama bog'liqlik va `public.*` ga tegadigan
**yagona** funksiya. O'sha hujjatning 6-bo'limi ("keyin ajratish yo'li")
aynan shu ish ro'yxatini bergan edi va u ro'yxat qisqa chiqdi.

---

## 2. Yangi qaror

| Qatlam | Qaror | Sabab |
|---|---|---|
| Backend | **Alohida FastAPI ilovasi** (`api/main.py`, port 8100) | O'z hayotiy sikli, o'z bog'liqliklari (4 ta paket, tender-ai da 10 ta) |
| Frontend | **Alohida Vite ilovasi** (port 5174) | Foydalanuvchi uchun ham alohida mahsulot; tender-ai interfeysida ERP bo'limlari YO'Q |
| Baza | **Bitta PostgreSQL, `erp` sxemasi** | Ma'lumot migratsiyasi kerak emas; snapshot uchun tenderni to'g'ridan-to'g'ri o'qish arzon va ishonchli |
| Repo | `D:\MVP projects\tender erp` — o'z `.venv`, `.env`, `package.json` | Alohida loyihaning oddiy belgisi |

### Nega baza baham ko'riladi

Alohida baza (`pg_dump -n erp`) ham ko'rib chiqildi. Uning narxi: snapshot
uchun har safar tender-ai API'siga borish kerak, ya'ni tender-ai yiqilsa
**yangi karta umuman ochilmaydi**; ustiga migratsiya va ikkinchi DSN.
Foydasi hozircha nazariy. Shuning uchun baza bitta qoldi, lekin chegara
saqlanadi: ERP `public.*` ga **yozmaydi** (har sinovda tekshiriladi) va
undan faqat 9 maydonli snapshot o'qiydi.

**YANGILANDI (auth-3).** Chegara endi SIMMETRIK:

| Kim | Nima qiladi |
|---|---|
| ERP | `public.tender` dan O'QIYDI (snapshot), **YOZMAYDI** |
| Tender-AI | `erp.v_tender_status` VIEW idan O'QIYDI, **YOZMAYDI** |

Ikkinchi qator yangi: ilgari tender-ai `erp` sxemasiga umuman tegmasdi va
`ErpLink` ma'lumotni brauzerdan HTTP bilan olardi. Buning narxi ERP
tomonidagi OCHIQ endpoint edi (brauzer server-server kalitini ushlab
turolmaydi). Sabab va tanlov: `erp_auth.md` 8.4.

Muhimi: tender-ai jadvalga emas, **view ga** bog'lanadi — u ataylab
shartnoma. ERP ichida ustunlar o'zgarsa view moslashtiriladi va tender-ai
o'zgarmaydi.

Bu qaror qayta ko'riladi, agar: ERP boshqa mijozga/serverga ko'chsa, yoki
tender-ai bazasi bilan versiyalanish jadvali ajralsa.

---

## 3. Integratsiya — aynan uch nuqta

Boshqa hech qanday bog'lanish YO'Q. Uchtasi ham bir tomonlama.

### 3.1. ERP → tender-ai: snapshot (SQL)

`api/erp/opportunity.py` dagi `TENDER_SNAPSHOT_SQL` — `public.tender` dan
9 maydon. Baza baham ko'rilgani uchun to'g'ridan-to'g'ri o'qiladi. Alohida
bazaga o'tilsa **shu bitta so'rov** HTTP chaqiruviga almashadi.

### 3.2. ERP → tender-ai: cheklist qoidalari (HTTP)

Qoidalar (`compliance.DOC_TYPES`, tender matnidan talab aniqlash) tender-ai
da, 1400 qator. **Ikkinchi nusxasi bo'lmasligi kerak.** Shuning uchun
tender-ai ularni xizmat sifatida beradi:

```
POST /tenders/{id}/compliance   {"documents": [...]}   -> tayyor cheklist
GET  /company/document-types                           -> kanonik ro'yxat
```

ERP mijozning hujjatlarini yuboradi, natijani ko'rsatadi. Tender-ai kirishda
oddiy ro'yxat ko'radi va `erp` sxemasi haqida hech narsa bilmaydi.
Hammasi `api/tenderai.py` da — ERP'ning tashqi dunyoga yagona ko'prigi.

### 3.3. tender-ai → ERP: bitta savol va ikki havola

`frontend/src/components/ErpLink.tsx`:

```
GET  /tenders/{id}/erp-status        -> "ishga olinganmi?" (O'Z backendi)
     {VITE_ERP_WEB}/?take=<tender_id>   -> "ERP da ishga olish"
     {VITE_ERP_WEB}/?opp=<opp_id>       -> "ERP kartasi"
```

Birinchi qatorni **server** bajaradi: `api/erp_status.py`
`erp.v_tender_status` view ini o'qiydi (auth-3 gacha buni brauzer ERP
backendiga to'g'ridan-to'g'ri so'rardi va shuning uchun ERP da ochiq
endpoint qolgan edi).

Interfeys manzili `.env` da berilmasa yoki view topilmasa — blok **umuman
ko'rinmaydi** va tender paneli avvalgidek ishlaydi. Tender-AI ERP haqida
status ro'yxatini ham, jadvalni ham, formani ham bilmaydi: hatto
statusning o'qiladigan nomi ham view dan keladi.

---

## 4. Nima yo'qotildi

Opportunity kartasida narx hisobi, ombor qoldig'i va tender hujjatlari
**endi ko'rsatilmaydi** — ular tender-ai komponentlari va ikki ilovada
saqlanishi ikki marta qarishga olib borardi. Karta o'rniga havola beradi:
"Tender-AI panelida ochish" (yangi oyna).

Cheklist esa ERP'da **qoldi**, chunki u 2-bosqichning asosiy va'dasi
(mijoz hujjatlari bo'yicha) va u komponent emas — ma'lumot. ERP uni o'zi
chizadi, qoidalar tender-ai'da qoladi.

Narxi: broker ba'zan ikki oyna orasida yuradi. Foydasi: bitta qoida manbasi
va ikki mustaqil mahsulot.

---

## 5. Keyin nima o'zgaradi

- **Auth kelganda:** ikkala ilova ham bir xil provayderga ulanadi;
  `created_by`/`changed_by` matn ustunlari `user_id` ga o'tadi.
- **ERP boshqa serverga ko'chsa:** 3.1 dagi SQL 3.2 kabi HTTP chaqiruviga
  aylanadi — o'zgarish bitta faylda (`api/erp/opportunity.py`).
- **Tender-AI o'zgarsa:** ERP faqat ikki endpointga bog'liq
  (`POST /tenders/{id}/compliance`, `GET /company/document-types`). Ular
  o'zgarsa `api/tenderai.py` o'zgaradi, boshqa hech qayer.
