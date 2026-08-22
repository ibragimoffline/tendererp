# HISOB-FAKTURA (5B-2) — ma'lumot modeli

`erp_arxitektura_3.md` 4.2 da ikki savol ochiq qolgan edi: QQS qoidasi va
1C/operator bilan aloqa. Birinchisiga javob olindi va u modelga kirdi;
ikkinchisi hali ochiq, shuning uchun **eksport qatlami ataylab bo'sh**.

---

## 1. Qaror: ERP fakturani o'zi chiqaradi, lekin YUBORMAYDI

O'zbekistonda hisob-faktura yuridik kuchga ega bo'lishi uchun **elektron**
shaklda (EHF), operator orqali yuboriladi — `didox`, `faktura.uz`, soliq
portali. **ERP bosib chiqargan PDF soliq uchun hujjat emas.**

Shuning uchun mehnat taqsimoti quyidagicha:

| Kim | Nima qiladi |
|---|---|
| ERP | fakturaning **ma'lumotini** saqlaydi, hisoblaydi, ko'rsatadi |
| Operator / 1C | uni **yuboradi** (yuridik kuch shu yerdan) |

Eksport formati texnik tanlov emas: u mijozning buxgalteri qaysi tizimda
ishlashiga bog'liq. Javob olinmaguncha kod yozish — taxminga qurish va
keyin uni tashlab yuborish degani. `api/erp/invoice_export.py` shuning
uchun **bo'sh qatlam** bo'lib turibdi va 501 qaytaradi.

---

## 2. QQS — IKKALA passportda

QQS ni **sotuvchi** hisoblaydi. Shuning uchun ikki savol bor va
ikkalasiga ham javob kerak:

| Savol | Qayerda |
|---|---|
| **BIZ** to'lovchimizmi? | `erp.own_company.vat_payer` / `vat_rate` |
| **MIJOZ** to'lovchimi? | `erp.client_company.vat_payer` / `vat_rate` |

Qoida (`invoice.default_vat_rate`):

1. bizniki `false` → **0**. Savol tugadi: biz QQS hisoblamaymiz, mijoz
   to'lovchi bo'lsa ham;
2. bizniki `NULL` ("hali so'ralmagan") → **eski xatti-harakat**: stavka
   mijozdan. Bu ataylab: patch qo'llangan kuniyoq fakturalar QQS'siz
   chiqib ketmasligi kerak;
3. mijozniki `false` yoki `NULL` → **0**;
4. ikkala stavka berilgan va farq qilsa → **kichigi**. Ortiqcha soliq
   qo'shib qo'yish kam qo'shishdan xavfliroq: mijoz to'lamagan pulni
   keyin undirib bo'lmaydi.

### 2b. Mijoz passportida

Stavka `pricing_settings` da emas, **`erp.client_company`** da:

```sql
vat_payer BOOLEAN   -- NULL = HALI SO'RALMAGAN
vat_rate  NUMERIC(5,2)
```

Sabab: O'zbekistonda QQS asosan **to'lovchiga qarab** hal bo'ladi. Mijoz
QQS to'lovchi bo'lmasa (aylanma solig'i rejimida) faktura QQS'siz
chiqadi. 2-bosqichdagi mijoz passporti aynan shunday savollar uchun
qilingan.

### `NULL` va `false` — ikki xil holat

`vat_payer = NULL` "hali so'ralmagan", `false` esa "to'lovchi emas".
Ularni aralashtirib bo'lmaydi:

- sukut bo'yicha `true` qo'yilsa — QQS'siz mijozga **jimgina 12% qo'shib
  qo'yardik**;
- `NULL` ni `false` deb o'qisak — savol berilmaganini hech kim
  sezmasdi.

Shuning uchun `NULL` da stavka 0 bo'ladi, lekin interfeys buni **ochiq
aytadi**: "Bu mijozning QQS holati so'ralmagan — passportda to'ldiring".

---

## 3. Uchta qoida — hammasi "bir haqiqat" tamoyilidan

### 3.1. Stavka HAR QATORDA

`erp.invoice_line.vat_rate` — qatorning **o'z** nusxasi. Sukut mijoz
passportidan olinadi, lekin keyin passport o'zgarsa (rejim almashdi,
qonun o'zgardi) **chiqarilgan hujjat o'zgarmaydi**.

Bitta fakturada turli stavkalar bo'lishi ham normal: tovarga 12%,
yetkazib berishga 0%.

### 3.2. Summalar SAQLANMAYDI

`net = qty × price`, `vat = net × rate/100` — bular hisob natijasi.
Ustunga yozilsa "nega bu son?" degan savolga **ikki xil javob** paydo
bo'lardi (ustun va formula), ular esa vaqt o'tib ajralib ketardi.
Ombordagi qoldiq bilan bir xil qoida.

Sinov jadvalda `total` / `amount` ustuni **yo'qligini** ham tekshiradi.

**Yaxlitlash QATOR darajasida** (tiyingacha). Aks holda yig'indi bilan
qatorlar summasi bir tiyinga farq qilardi va buxgalter buni xato deb
hisoblardi.

Pul `NUMERIC`/`Decimal` bilan hisoblanadi, `float` bilan emas: `0.1+0.2`
muammosi hisob-kitobda ko'rinadigan xatoga aylanadi.

### 3.3. Rekvizitlar SNAPSHOT

Ikkala tomonning rekvizitlari fakturaga **ko'chiriladi** (mijozniki
passportdan, biznikisi `erp.own_company` dan). Hujjat chiqarilgandan
keyin passport o'zgarsa — bank almashdi, manzil ko'chdi — eski faktura
o'zgarmasligi kerak. Aks holda bir yil oldingi fakturani ochganda
bugungi rekvizitlar ko'rinardi va u **boshqa hujjatga** aylanardi.

Kartadagi tender snapshoti va taklifning muzlatilgan versiyasi bilan bir
xil naqsh.

---

## 4. Muzlatish: `draft` dan chiqqach tahrirlanmaydi

| Holat | Ma'nosi |
|---|---|
| `draft` | qoralama — qatorlar va rekvizitlar tahrirlanadi |
| `issued` | chiqarildi — **muzlatildi** |
| `sent` | mijozga yuborildi |
| `paid` | to'liq to'landi |
| `cancelled` | bekor qilindi |

Xato bo'lsa faktura **bekor qilinadi va yangisi chiqariladi** —
chiqarilgan hujjatni jimgina o'zgartirish buxgalteriyada yo'q qoida.
Bekor qilingandan qaytish ham yo'q.

`issued` ga o'tish uchun faktura **to'liq** bo'lishi kerak: raqam, sana
va kamida bitta qator. Bo'sh hujjatni "chiqarildi" deb belgilash uni
yolg'onga aylantiradi; server nima yetishmayotganini aniq aytadi.

---

## 5. To'lovlar: "qisman to'landi" — STATUS EMAS

`erp.invoice_payment` — alohida jadval. Statuslar ro'yxatida
`partly_paid` **ataylab yo'q**: qisman to'lov — bu hisob natijasi
(to'lovlar yig'indisi < faktura summasi), holat emas. Ikki joyda
saqlansa ular ajralib ketardi.

Javobda uchta son bor: `paid` (yig'indi), `balance` (qarz),
`fully_paid`.

Ikkita avtomatik harakat:

- **to'liq to'langanda** status o'zi `paid` bo'ladi — odam ikkinchi
  marta bosib o'tirmasin;
- **to'lov o'chirilganda** (xato kiritilgan bo'lsa) va summa yetmay
  qolsa, status `issued` ga **qaytariladi** — aks holda "to'landi" deb
  turgan, lekin qarzi bor faktura qolardi.

Ortiqcha to'lov taqiqlanmaydi (ombordagi manfiy qoldiq bilan bir xil
sabab: hayotda shunday bo'ladi), lekin `balance` manfiy bo'ladi va
interfeys ko'rsatadi.

Qoralamaga va bekor qilinganga to'lov yozilmaydi.

---

## 6. Endpointlar

```
GET    /erp/invoices                        (status / client_id / opportunity_id)
GET    /erp/invoices/stats                  holatlar + QARZ (rahbar)
GET    /erp/invoices/export-formats         sozlangan formatlar (hozir BO'SH)
POST   /erp/invoices                        yangi qoralama
GET    /erp/invoices/{id}
PUT    /erp/invoices/{id}                   faqat qoralama
PUT    /erp/invoices/{id}/status
POST   /erp/invoices/{id}/lines
DELETE /erp/invoices/{id}/lines/{line_id}
POST   /erp/invoices/{id}/payments
DELETE /erp/payments/{payment_id}
GET    /erp/invoices/{id}/export?fmt=...    -> 501 (hali sozlanmagan)
```

`/erp/invoices/stats` **rahbar** huquqini talab qiladi: pul haqidagi
umumiy ko'rsatkich (qarz) har kimga emas.

Interfeysda **eksport tugmasi yo'q** — formatlar ro'yxati bo'sh ekan,
ishlamaydigan tugma yolg'on va'da bo'lardi (`ErpLink` bilan bir xil
qoida).

---

## 6b. Zanjir: karta -> shartnoma -> FAKTURA -> to'lov

```
POST /erp/opportunities/{id}/invoice
```

Kartadan qoralama chiqaradi va **qatorlarni o'zi to'ldiradi**.

**Qayerdan:**

| Maydon | Manba |
|---|---|
| mijoz, valyuta | kartadan (shartnoma bo'lsa undan) |
| shartnoma | kartaning eng so'nggisi |
| qator nomi, o'lchov birligi, **miqdor** | kartaga AJRATILGAN tovar (`erp.stock_reserve`) |
| birlik narxi | tender-ai katalogidagi SOTUV narxi (faqat o'qish) |
| QQS stavkasi | mijoz passportidan (odatdagidek, qatorga nusxa) |

Rezervlardan `held` va `consumed` olinadi — birinchisi hali chiqmagan,
ikkinchisi yutilgach chiqib bo'lgan; ikkalasi ham **sotilgan** tovar.
`released` (bekor qilingani) tushmaydi.

**Nima TAXMIN QILINMAYDI:**

- **narx topilmasa 0 qoladi** — tannarxni yozib qo'yish fakturani
  jimgina noto'g'ri qilardi. Javobdagi `filled.no_price` nechta qator
  narxsiz ekanini aytadi va interfeys buni ochiq ko'rsatadi;
- **shartnoma summasi qatorga aylantirilmaydi**: u QQS bilanmi yoki
  QQS sizmi noma'lum, bu farq esa butun hisobni o'zgartiradi. Rezerv
  bo'lmasa faktura QATORSIZ chiqadi va odam to'ldiradi.

Javobdagi `filled` bloki nima qayerdan kelganini aytadi:
`{lines, no_price, from_contract, contract_number}`.

Kartada faqat **ro'yxat va chiqarish** bor; tahrirlash, to'lov va holat —
"Hisob-fakturalar" bo'limida. Bitta hujjatni ikki joyda tahrirlash
chalkashlik keltirardi.

---

## 6c. Bosma shakl — brauzer chop etadi

`InvoicePrint.tsx` — fakturaning qog'ozga tushadigan ko'rinishi:
ikkala tomonning rekvizitlari, qatorlar jadvali, QQS ajratilgan jami va
imzo joylari.

**PDF kutubxonasi YO'Q.** `reportlab` / `weasyprint` shrift, sahifa
o'lchami va Windows'da o'rnatish muammolarini olib kelardi. Brauzer esa
buni allaqachon biladi va uning chop etish oynasida "PDF ga saqlash" ham
bor. Sahifa sozlamalari (`@page A4`, chekkalar, qator bo'linmasligi,
uzun jadval sarlavhasining har varaqda takrorlanishi) `index.css` dagi
`@media print` blokida.

**YURIDIK KUCH YO'Q va bu shaklning O'ZIDA yozilgan:** "Ushbu shakl
ichki foydalanish va imzolatish uchun. Soliq hisoboti uchun elektron
hisob-faktura (EHF) operator orqali yuboriladi." Aks holda uni haqiqiy
hujjat deb o'ylash mumkin edi.

Ma'lumot **snapshotdan** olinadi — shakl passportga qaramaydi, ya'ni bir
yil oldingi fakturani bosganda o'sha paytdagi rekvizitlar chiqadi.

### Summa so'z bilan

Hujjatda summa raqam bilan ham, **so'z bilan ham** yoziladi: raqamdagi
bitta nolni qo'shib qo'yish oson, so'zdagisini esa emas. Bu
buxgalteriyaning eski va foydali odati.

Matn **serverda** yasaladi (`invoice.py` -> `amount_words`) va javobda
`totals.words` bo'lib keladi. Nega brauzerda emas: bu sof mantiq va u
**sinaladi** — ERP sinovlari Pythonda, brauzerda yozilsa sinovsiz
qolardi.

O'zbekcha sonlarning ikki nozikligi qoidaga aylantirilgan va sinovda
qayd etilgan:

- `100` -> "yuz", `1000` -> "ming" (**"bir" tushib qoladi**);
- `1 000 000` -> "bir million" (**"bir" qoladi**).

Noma'lum valyuta uchun nom **o'ylab topilmaydi** — kodning o'zi
yoziladi ("yuz ellik XYZ").

---

## 7. Sinov

```
.venv/Scripts/python.exe _tests/erp8_test.py       # 105 tekshiruv
```

Qamrov: hisob (net/QQS/jami, nol stavka, qator darajasidagi
yaxlitlash); statuslar va to'lov usullari kod va bazadagi CHECK da bir
xil; **jadvalda summa ustuni yo'qligi**; QQS ning uch holati
(so'ralmagan / to'lovchi emas / to'lovchi); **passport o'zgarganda qator
stavkasi o'zgarmasligi**; snapshot; muzlatish (qator qo'shib bo'lmaydi,
tahrirlanmaydi); to'liqmas fakturani chiqarib bo'lmasligi; to'lovlar
(qisman → status o'zgarmaydi, to'liq → avtomatik `paid`, o'chirilganda
qaytish); bekor qilish; eksportning 501 qaytarishi; CASCADE; **chegara**
(`public.*` ga yozilmaydi).

Summa so'z bilan: nol, bir/ikki xonali, "yuz"/"ming" da `bir` ning
tushib qolishi, "bir million" da qolishi, o'rtadagi nollar, tiyin,
boshqa valyuta va noma'lum valyuta.

Zanjir qamrovi: kartadan chiqarilgan faktura kartaga va mijozga
bog'lanishi; qator miqdorining **rezervdan** olinishi; narx yo'qligining
sanalishi; **bo'shatilgan rezervning tushmasligi**; mijozsiz kartadan
faktura chiqmasligi (400) va yo'q kartadan 404.

Sinov o'z mijozini yaratmaydi — mavjud mijoz passportini vaqtincha
o'zgartiradi va **oxirida tiklaydi**. Karta statusi va ombor ham
tiklanadi.

---

## 7b. DALOLATNOMA (akt)

Faktura "qancha to'lash kerak" deydi, dalolatnoma esa **"ish
BAJARILDI"**. Bular ikki xil fakt va ikkalasi ham kerak: to'lov
nizosida "pulni to'ladim" bilan "ishni oldim" boshqa-boshqa dalil.

`schema_patch_erp_12.sql` — `erp.act` va `erp.act_line`.

### Fakturadagi qoidalar bu yerda ham

Rekvizitlar **snapshot**, summalar **saqlanmaydi**, `draft` dan chiqqach
hujjat **muzlaydi**. Hisob-kitob esa **aynan fakturaning kodi** bilan
bajariladi (`invoice.line_totals` / `totals`) — ikki xil yaxlitlash ikki
xil summa degani bo'lardi va aktdagi son fakturadagidan bir tiyinga
farq qilib turardi. Sinov `act.py` da o'z yaxlitlashi yo'qligini
tekshiradi.

### Uch farq

| | Faktura | Dalolatnoma |
|---|---|---|
| Nima deydi | "qancha to'lash kerak" | "bajarildi" |
| Bank rekvizitlari | bor | **yo'q** (to'lov hujjati emas) |
| Yakuniy holat | `paid` | **`signed`** — ikkala tomon imzoladi |

`signed_at` — **hujjatdagi** imzo sanasi, `status_changed_at` esa
tizimda qachon belgilangani. Ikkalasi bir xil bo'lishi shart emas.

### Fakturadan chiqarish

```
POST /erp/invoices/{id}/act
```

Qatorlar **ko'chiriladi**, bog'lanmaydi. Sabab: faktura keyin bekor
qilinishi mumkin (yangisi chiqariladi), dalolatnoma esa bajarilgan
ishning dalili va **o'z holicha turishi kerak**. Sinov buni tekshiradi:
faktura bekor qilinganidan keyin ham akt qatorlari va summasi
o'zgarmaydi.

**Qoralama fakturadan akt chiqarilmaydi** (409): hali chiqarilmagan
hujjat bo'yicha "ish bajarildi" deb yozish mantiqsiz. Bekor qilingan
fakturadan ham chiqarilmaydi.

### Bosma shakl

`ActPrint.tsx` — fakturanikidek: brauzer chop etadi, ma'lumot
snapshotdan, yuridik kuchi yo'qligi shaklning o'zida yozilgan.
Farqi mazmunida: bank rekvizitlari yo'q va matnda aktning butun
ma'nosi turadi — *"Yuqorida ko'rsatilgan ishlar to'liq va sifatli
bajarildi. Tomonlarning bir-biriga da'vosi yo'q."*

### Sinov

```
.venv/Scripts/python.exe _tests/erp9_test.py       # 48 tekshiruv
```

Qamrov: statuslar kod va bazada bir xil; **jadvalda summa ustuni ham,
bank rekvizitlari ham yo'qligi**; snapshot; fakturadan ko'chirish va
faktura bekor bo'lganda aktning saqlanishi; qoralama/bekor qilingan
fakturadan chiqarib bo'lmasligi; muzlatish; imzo sanasi (berilmasa akt
sanasi olinadi); ro'yxat filtrlari; chegara.

---

## 7c. SHARTNOMA ILOVASI (spetsifikatsiya)

```
GET /erp/contracts/{id}/specification
```

### Qaror: ERP shartnoma MATNINI yozmaydi

Huquqiy matn — yurist ishi. Uni shablondan o'ylab topish noto'g'ri
hujjat chiqarish demak. ERP shartnomani **qayd qiladi** (raqam, sana,
summa, holat).

ERP chiqaradigan qism — **ilova**: tovar/xizmat ro'yxati, miqdor, narx,
jami. Bu aynan ERP da bor va har bitimda o'zgaradigan qism.

### Ma'lumot uch manbadan, MUZLATILGANI ustun

| `source` | Qayerdan | Muzlatilganmi |
|---|---|---|
| `invoice` | shu shartnoma bo'yicha chiqarilgan faktura | **ha** — qatorlar ham, rekvizitlar ham snapshot |
| `reserves` | kartaga ajratilgan tovar | yo'q — passport hozirgi holatda |
| `none` | hech biri yo'q | — ro'yxat **bo'sh** va shakl buni aytadi |

**Bekor qilingan faktura hisobga olinmaydi**: u endi hujjat emas, ya'ni
manba rezervga tushadi. Sinov buni tekshiradi.

Manba **shaklning o'zida** yoziladi — o'quvchi raqamlar qayerdan
kelganini bilishi kerak: *"Ma'lumot … fakturadan olindi (hujjat
chiqarilgan paytdagi holat)"* yoki *"… ombordan ajratilgan tovarlardan
olindi (hozirgi holat). Narxlarni tekshiring."*

### Farq jim qoldirilmaydi

Shartnomada ko'rsatilgan summa ilova summasidan farq qilsa, shaklda
**ogohlantirish** chiqadi. Jim qoldirsak, ikki raqam ikki hujjatda
turib qolardi va farqni hech kim sezmasdi.

### Sinov

`erp5_test.py` 7-bo'limi: uch manba, muzlatilganlik belgisi, bekor
qilingan fakturaning hisobga olinmasligi, bo'sh ro'yxat va 404.

---

## 8. Ochiq qolgan uch savol

1. **Eksport formati** — mijozdan so'raladi (1-bo'lim). Javob olingach
   `invoice_export.py` ga qo'shiladi; `invoice.py` ga tegilmaydi, chunki
   model formatdan mustaqil qurilgan.
2. ~~Bizning QQS holatimiz~~ — **BAJARILDI** (2-bo'lim,
   `schema_patch_erp_13.sql`). Mexanizm qurildi va stavka endi ikkala
   tomonga qarab hal bo'ladi. QIYMATNI egasi kiritadi: **Kompaniya**
   ekranida "Biz QQS to'lovchimizmi". So'ralmaguncha (`NULL`) hech
   narsa o'zgarmaydi.
3. ~~Aktlar~~ — **BAJARILDI** (7b-bo'lim). Ularning eksporti ham
   fakturaniki bilan bir xil savolga tayanadi: operator formati.

---

## 7d. YETKAZIB BERISH JADVALI — ataylab yo'q (qaror)

`erp_integratsiya_5.md` 6-bo'limida "5B da qilinadi" deb sanalgan
beshta narsadan to'rttasi bajarildi (to'lov, faktura, akt, shartnoma
ilovasi). Beshinchisi — **yetkazib berish jadvali** — bajarilmadi va
uzoq vaqt na ro'yxatda, na qarorlar orasida turdi. Endi u qaror:

**MVP uchun akt va ombor chiqimi yetarli.**

- Ombor chiqimi (`stock_move`, `kind='out'`) — tovar **ketdi**;
- akt — mijoz **qabul qildi**.

Ikkalasi birgalikda "yetkazildimi?" degan savolga javob beradi.
Javobsiz qoladigani — **"qachon, qayerga, kim olib boradi"**, ya'ni
rejalashtirish. Bu boshqa savol va u bitta tenderning hujjat
zanjiriga emas, logistikaga tegishli.

### Keyin qilinsa qanday bo'ladi

Yangi jadval `erp.delivery` **aktga bog'lanadi**, aksincha emas:

```
erp.delivery   (reja: sana, manzil, mas'ul, holat)
      |
      v
erp.act        (tasdiq: qabul qilindi)
```

Ya'ni akt — yetkazishning **tasdig'i**. Bu tartib muhim: reja
o'zgaradi (sana suriladi, mas'ul almashadi), tasdiq esa
muzlatilgan hujjat. Tasdiqni rejaga bog'lash hujjatni
o'zgaruvchan qilardi.

Shu sababdan hozir `erp.act` da yetkazish maydonlari YO'Q va
qo'shilmaydi ham: ular kelganda `erp.delivery` da tug'iladi.
