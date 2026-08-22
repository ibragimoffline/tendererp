# ERP — ARXITEKTURA QARORI 3: 5-BOSQICH OLDIDAN

`erp_bosqichlar.md` 5-bosqich shunday boshlanadi:

> **Shu bosqichga kelganda `erp_arxitektura.md` 1-bo'limdagi "qayta ko'rish"
> shartlari tekshiriladi.**

Bu hujjat — o'sha tekshiruv. Xulosa oxirida, lekin bir jumla bilan:
**og'ir modullarga kirishdan oldin bitta poydevor yetishmayapti — kim nima
qilgani.** Quyida nega shundayligi va nima qilish kerakligi.

---

## 1. Hozirgi holat — raqamlar bilan

`erp` sxemasi: **8 jadval**, `opportunity` da 26 ustun.

| Jadval | Qator | Nima |
|---|---|---|
| `opportunity` | 6 | ish kartalari (hozir — namuna) |
| `opportunity_history` | 11 | har status o'tishi |
| `opportunity_task` | 5 | vazifalar |
| `submission` | 0 | muzlatilgan takliflar |
| `client_company` | 2 | mijoz passporti |
| `client_document` | 5 | mijoz hujjatlari |
| `client_contact` | — | aloqa shaxslari |
| `broker` | 2 | xodimlar (matn ro'yxati) |

Bajarilgani: 1-4 bosqich + ajratish. Sinovlar: **277 tekshiruv**, 0 xato.

---

## 2. "Qayta ko'rish" shartlari — tekshiruv

`erp_arxitektura.md` 1-bo'limi to'rtta shartni sanagan; ikkitasi paydo
bo'lsa qaror qayta ko'riladi.

| # | Shart | Holat |
|---|---|---|
| 1 | Foydalanuvchi login va rollar | **YO'Q** — bazada birorta ham `user`/`auth`/`role` jadvali topilmadi |
| 2 | Mijozlar tizimga o'zlari kiradi | yo'q — 2-bosqich buni ataylab qilmadi |
| 3 | Buxgalteriya/ombor tenderdan mustaqil operatsiyalar bilan yashaydi | **HALI YO'Q, lekin 5-bosqich aynan shuni keltiradi** |
| 4 | ERP alohida mahsulot | **BO'LDI** — ajratish bajarilgan (`erp_arxitektura_2.md`) |

Ya'ni ajratish savoli **yopilgan**. Ochiq qolgani — 1-shart, va u endi
shartdan **to'siqqa** aylanadi.

---

## 3. Asosiy xulosa: auth 5-bosqichning SHARTI

1-4 bosqichda auth yo'qligi zarar keltirmagan: `created_by` — dropdown'dan
tanlangan broker nomi, xato bo'lsa narxi arzon (karta tarixida noto'g'ri
ism).

5-bosqichda narx boshqacha:

- **To'lov va hisob-faktura** — pul harakati. "Kim to'lov qo'shdi?" degan
  savolga "tanlangan ism" javob emas: uni istalgan odam istalgan ism bilan
  yozishi mumkin.
- **Ombor harakati** — qoldiq kamayishi. Kim yozganini bilmasdan
  inventarizatsiya farqini tekshirib bo'lmaydi.
- **HR / KPI** — odamlar haqidagi baho. Uni o'zgartira oladigan odam
  o'zining ko'rsatkichini ham o'zgartira oladi.

Uchalasida ham **auditni saqlaydigan yozuv** kerak, u esa auth'siz bo'lmaydi.

Shu sababli tavsiya: **5-bosqich ikkiga bo'linadi.**

```
5A — auth'siz ham xavfsiz:   shartnoma qaydi, HR HISOBOTI (mavjud tarixdan)
5B — auth TALAB QILADI:      to'lov, hisob-faktura, ombor harakati
```

Auth o'zi alohida ish (taxminan bir bosqich hajmida) va u **ikkala
loyihaga** tegadi: tender-ai ham, ERP ham bir xil provayderga ulanishi
kerak, aks holda ikkita login paydo bo'ladi.

---

## 4. Har modul uchun aniq to'siqlar

### 4.1. Shartnoma — eng arzon, eng foydali

Bor: `submission` (muzlatilgan taklif), `client_company` (mijoz passporti),
manbadagi `tender.contract_num` / `contract_id`.

**Yetishmaydi: BIZNING kompaniyaning rekvizitlari.** `company_profile` da
INN ham, bank rekvizitlari ham, yuridik manzil ham **yo'q** — u qidiruv va
Go/No-Go uchun profil (`name`, `keywords`, `regions`, `certificates`,
`employees`, `min_margin_percent`...). Shartnoma va hisob-faktura esa ikki
tomonning rekvizitlarini talab qiladi.

Yechim: `erp.own_company` — bizning passportimiz, `client_company` bilan
**bir xil ustunlar**. Tender-AI dagi `company_profile` ga tegilmaydi (u
boshqa modul egasi, `erp_arxitektura.md` 2.1).

### 4.2. To'lov va hisob-faktura — auth'dan keyin

Auth'dan tashqari ikki narsa aniqlanishi kerak:
- **QQS va aktlar qoidasi** — bu mahalliy buxgalteriya qoidasi, uni
  taxmin qilib yozish mumkin emas;
- **1C / buxgalteriya dasturi bilan aloqa** bo'ladimi. Bo'lsa — ERP
  hisob-fakturani O'ZI yaratmaydi, faqat qayd etadi va eksport beradi.
  Bu ikki butunlay boshqa hajmdagi ish.

### 4.3. Ombor harakati — mavjud qoldiq bilan to'qnashadi

Tender-AI da `catalog_product` bor va unda `stock_qty`, `stock_unit`,
`stock_updated_at`. Lekin bu **suratga olingan qoldiq**: u faqat Excel
importi orqali to'ladi (`api/importer.py`), harakat jurnali ham,
rezervatsiya ham yo'q.

Ombor harakati qo'shilsa savol tug'iladi: qoldiqning **egasi kim** —
tender-ai (import) yoki ERP (harakatlar yig'indisi)? Ikkalasi bir vaqtda
yozsa raqam ikki manbadan kelib, farq muqarrar.

Uch yo'l bor va ular teng emas:

| Yo'l | Ma'nosi | Narxi |
|---|---|---|
| **A** | Qoldiq egasi ERP: harakat jurnali ERP'da, tender-ai `stock_qty` ni ERP'dan o'qiydi | tender-ai ga o'zgarish, migratsiya |
| **B** | Qoldiq egasi tender-ai: ERP faqat rezerv qiladi ("shu tender uchun ajratildi") | kam ish, lekin haqiqiy ombor emas |
| **C** | Ikkalasi alohida yashaydi | **RAD ETILADI** — ikki haqiqat manbai |

### 4.4. HR / KPI — hozirdan mumkin

`opportunity_history` da har status o'tishi bor: kim, qachon, qaysi
bosqichdan qaysisiga. Ya'ni "broker o'rtacha necha kunda topshiradi",
"qaysi bosqichda ish qotib qoladi" degan savollarga **hozir ham** javob
bor — yangi jadval kerak emas, faqat hisobot.

Faqat bir shart: KPI **odamlar haqida**, shuning uchun uni ko'rish rahbar
huquqiga bog'lanadi — ya'ni yana auth. Auth'gacha: hisobot bor, lekin
"kim ko'ra oladi" cheklovi yo'q.

---

## 5. Qaror

1. **ERP alohida loyiha bo'lib qoladi.** Ajratish savoli yopilgan; qayta
   birlashtirish uchun sabab yo'q.
2. **5-bosqich ikkiga bo'linadi** (3-bo'lim): 5A auth'siz, 5B auth bilan.
3. **Tavsiya etilgan tartib:**
   - **5A-1. Shartnoma qaydi** + `erp.own_company` (bizning rekvizitlar).
     Eng arzon, taklif → shartnoma zanjirini yopadi.
   - **5A-2. Rahbar hisoboti kengaytmasi** — mavjud `opportunity_history`
     dan: bosqichlarda o'tgan vaqt, broker bo'yicha o'rtacha, "qotib
     qolgan" kartalar.
   - **AUTH** — alohida ish, ikkala loyihaga.
   - **5B-1. Ombor** — avval A/B yo'lini tanlash (4.3).
   - **5B-2. To'lov va hisob-faktura** — avval QQS qoidasi va 1C savoliga
     javob (4.2).
4. **Ombor uchun C yo'li rad etiladi** — ikki haqiqat manbai.
5. `public.*` ga yozmaslik qoidasi **5-bosqichda ham saqlanadi**. Ombor A
   yo'li tanlansa — bu qoida qayta ko'riladi va **shu hujjat yangilanadi**,
   jimgina buzilmaydi.

---

## 6. Uch savol — JAVOB OLINDI

| # | Savol | Javob |
|---|---|---|
| 1 | Auth qachon? | ~~5B kerak bo'lgunicha~~ → **DARHOL bajarildi** (`docs/erp_auth.md`) |
| 2 | Ombor qoldig'ining egasi? | **ERP** (A yo'li) → **A1 bilan BAJARILDI** (`docs/erp_ombor.md`) |
| 3 | Hisob-faktura? | **ERP o'zi chiqaradi** → **model BAJARILDI** (`docs/erp_faktura.md`); eksport qatlami ochiq |

### 6.1. Javoblardan kelib chiqadigan ish

**A yo'li (ombor egasi ERP)** tanlangani `erp_arxitektura.md` 2.1 dagi
"`public.*` ga hech qachon yozilmaydi" qoidasiga tegadi: tender-ai dagi
`catalog_product.stock_qty` endi ERP hisobidan kelishi kerak. Ikki yo'l
bor va ular teng emas:

- **A1** — tender-ai `stock_qty` ni ERP dan **o'qiydi** (masalan
  `GET /erp/stock`), o'z ustunini yangilamaydi. Qoida buzilmaydi.
- **A2** — ERP `catalog_product.stock_qty` ni **yozadi**. Qoida buziladi
  va buning uchun shu hujjat qayta yozilishi kerak.

Tavsiya — **A1**: chegara saqlanadi, tender-ai tomonida esa bitta
o'qish nuqtasi qo'shiladi (bu allaqachon tanish naqsh — cheklist va
shablon parseri shunday ishlaydi, faqat teskari yo'nalishda).

**BAJARILDI (A1).** `erp.stock_move` jurnali va `erp.v_stock_balance`
shartnoma-view i (`schema_patch_erp_8.sql`); tender-ai
`api/erp_stock.py` orqali o'qiydi. `public.*` ga yozilmadi.
Tafsilot va o'tish qoidasi: `docs/erp_ombor.md`.

### 6.2. ~~Ochiq qolgan xavf~~ — YOPILDI

**Yangilanish:** auth 5B dan OLDIN bajarildi (auth-1). Quyidagi xavf
tavsifi tarix uchun qoldirildi; u endi ERP tomonida yo'q, chunki
`created_by` sessiyadan olinadi va endpointlar himoyalangan. Tender-AI
ning o'z interfeysi esa hamon ochiq — auth-2.

#### Eski tavsif

1-javob 2 va 3-javob bilan qarama-qarshi turadi: 5B pul (hisob-faktura)
va moddiy qiymat (ombor) bilan ishlaydi, auth esa keyinga qoldirildi.
Ya'ni "kim yozdi?" degan savolga javob hamon `created_by` — dropdown'dan
tanlangan ism.

Bu **ongli qaror** sifatida qabul qilinadi, lekin narxi yozib qo'yiladi:
- to'lov/hisob-faktura yozuvlarini istalgan odam istalgan ism bilan
  kirita oladi;
- inventarizatsiya farqini kimga bog'lash mumkin emas.

Yumshatish: 5B jadvallarida `created_by` **matn** ustuni bo'ladi va auth
kelganda yoniga `user_id` qo'shiladi (matn ustuni saqlanadi) — bu
`erp_arxitektura.md` 5.1 da 1-bosqich uchun tanlangan naqshning o'zi va
u ishlaydi.
