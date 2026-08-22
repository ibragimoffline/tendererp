# OMBOR (5B-1) — qoldiqning egasi ERP

`erp_arxitektura_3.md` 4.3 va 6.1 da qo'yilgan savolga javob olindi:
qoldiqning **egasi — ERP**, "A1" yo'li bilan. Bu hujjat bajarilgan
holatni yozadi.

---

## 1. Muammo nima edi

Tender-AI da `catalog_product` bor va unda `stock_qty`, `stock_unit`,
`stock_updated_at`. Lekin bu **suratga olingan qoldiq**: u faqat Excel
importi orqali to'ladi, harakat jurnali ham, rezervatsiya ham yo'q.

Ombor qo'shilsa savol tug'iladi: raqamning egasi kim? Ikkalasi bir vaqtda
yozsa **ikki haqiqat manbai** paydo bo'ladi va farq muqarrar. Uch yo'ldan
"ikkalasi alohida yashaydi" darhol rad etilgan edi.

---

## 2. Qaror: jurnal ERP da, tender-ai O'QIYDI

```
  ERP                                  Tender-AI
  erp.stock_move  (jurnal)             api/erp_stock.py
      │  SUM(qty)                          │ SQL, faqat o'qish
      ▼                                    ▼
  erp.v_stock_balance  ◄─────────────────  qoldiq
      (SHARTNOMA-VIEW)
```

- harakatlar jurnali va qoldiq — **ERP da**;
- tender-ai qoldiqni `erp.v_stock_balance` view idan **o'qiydi** va o'z
  ustuniga tayanmaydi;
- `public.*` ga yozmaslik qoidasi **buzilmaydi** — bu "A1" ning butun
  ma'nosi ("A2" da ERP `catalog_product.stock_qty` ga yozardi va qoida
  qayta yozilishi kerak bo'lardi).

View — `v_tender_status` (auth-3) bilan bir xil naqsh: tender-ai
jadvalga emas, **shartnomaga** bog'lanadi.

---

## 3. Nega JURNAL, "qoldiq" ustuni emas

Qoldiq — **hisob natijasi**, saqlanadigan fakt emas.

Ustun bo'lsa "nega 12 dona?" degan savolga javob yo'q: kim o'zgartirdi,
qachon, nima uchun — hech biri qolmaydi. Jurnal bo'lsa har o'zgarish
yozilgan va qoldiq shundan chiqadi (`SUM(qty)`).

Shu sababli `erp.stock_move` da `balance` degan ustun **yo'q** va sinov
uning paydo bo'lmaganini ham tekshiradi.

### Ishora qoidasi

`qty` **ishorali** saqlanadi: kirim `+`, chiqim `−`. Shuning uchun
qoldiq — oddiy `SUM`, view da `CASE` kerak emas va "qaysi turni qo'shish,
qaysinisini ayirish" degan qoida **bitta joyda** (bazadagi CHECK da)
turadi.

API dan esa **musbat** son keladi va ishorani server qo'yadi — forma
ishlatuvchi minus belgisini o'ylab o'tirmasin. Istisno: `adjust`
(inventarizatsiya) — u yerda ishora ma'no tashiydi (kam chiqdi / ko'p
chiqdi), shuning uchun u mijozdan keladi.

| Tur | Ma'nosi | Ishora |
|---|---|---|
| `opening` | Boshlang'ich qoldiq | `+` (mahsulotga BIR MARTA) |
| `in` | Kirim | `+` |
| `out` | Chiqim | `−` |
| `adjust` | Tuzatish (inventarizatsiya) | `±`, **izoh majburiy** |

---

## 4. Mahsulot katalogi — tender-ai da qoladi

ERP o'z katalogini yuritmaydi: `catalog_product` tender-ai da tender
moslashuvi va bildirishnoma uchun ishlatiladi, ikkinchi nomenklatura
ikki xil nom degani bo'lardi.

ERP undan **faqat o'qiydi** (nom, o'lchov birligi) va harakat yozilganda
nomni **snapshot** qiladi — kartadagi tender snapshoti bilan bir xil
sabab:

- FK `public.catalog_product` ga bog'lansa, u yerdagi o'chirish ERP
  jurnalini yiqitardi yoki bloklab qo'yardi;
- mahsulot o'chirilsa ham **ombor tarixi qolishi kerak** — "nima chiqdi"
  degan savolga javob yo'qolmasin.

Shuning uchun `product_id` da **FK yo'q**, lekin `product_name` va `unit`
jurnalda muzlatiladi. Interfeys katalogdan o'chirilgan mahsulotni
"(katalogdan o'chirilgan)" deb ko'rsatadi.

---

## 5. Manfiy qoldiq — taqiq emas, ogohlantirish

Haqiqiy omborda hujjat kechikadi: tovar chiqib ketgan, kirim qog'ozi
ertaga keladi. Taqiq qo'yilsa odam raqamni "to'g'rilab" yozardi va
jurnal yolg'onga aylanardi.

Shuning uchun chiqim **o'tadi**, lekin:

- javobda `warning` qaytadi va interfeys uni ko'rsatadi;
- `GET /erp/stock` javobida `negative` ro'yxati bor;
- ekranda manfiy son qizil rangda va pastda umumiy ogohlantirish.

---

## 6. O'tish: import qoldig'idan ko'chirish

Sxema patchi qo'llangani bilan ombor to'ldirilgan bo'lmaydi. Bo'sh
jurnalni "hamma qoldiq nol" deb o'qisak, patch qo'llangan kuniyoq butun
katalogdagi qoldiq **yo'qolib ko'rinardi** va hech kim sababini
tushunmasdi.

Shuning uchun qoida ikki bosqichli:

| Holat | Qoldiq qayerdan |
|---|---|
| Jurnal **bo'sh** | eski surat — Excel importi (`stock_source: "import"`) |
| Jurnalda **harakat bor** | ERP hisobi (`stock_source: "erp"`) |

Ya'ni ikki manba bir vaqtda **yashamaydi**: birinchi harakat kiritilishi
bilan ega butunlay ERP bo'ladi. Buni `tender-ai/api/erp_stock.py`
dagi `in_use()` hal qiladi.

O'tishning o'zi bir tugma: ERP → **Ombor** ekranida "Import
qoldiqlarini ko'chirish" (`POST /erp/stock/seed-opening`, rahbar
huquqi). U `catalog_product.stock_qty` ni `opening` harakatiga
aylantiradi. Idempotent: `stock_move_opening_uq` tufayli ikkinchi marta
yurganda hech narsa qo'shilmaydi.

Import davom etaveradi (u tender-ai ning o'z ustuni), lekin ombor ishga
tushgach import natijasi **ko'rsatilmaydi** — buni jim qoldirmaslik uchun
import javobida `stock_note` qaytadi.

---

## 7. Endpointlar

```
GET  /erp/stock                 qoldiqlar + turlar + manfiylar ro'yxati
GET  /erp/stock/{product_id}    bitta mahsulot: qoldiq + tarix
GET  /erp/stock/moves           harakatlar (product_id / opportunity_id filtri)
POST /erp/stock/moves           yangi harakat (created_by SESSIYADAN)
POST /erp/stock/seed-opening    import qoldig'ini ko'chirish (rahbar)
```

Tender-AI tomonida yangi endpoint **yo'q**: qoldiq mavjud javoblarga
qo'shiladi — `GET /catalog` (har qatorda `stock_source`, `stock_qty` =
**mavjud**, yoniga `stock_physical` va `stock_reserved`) va
`GET /tenders/{id}/stock-check` (`stock.source`).

`stock-check` ning **hisob-kitob qismi o'zgarmadi**: `build_check()`
qoldiq qayerdan kelganini bilmaydi va uning sinovlari ham o'sha-o'sha.

---

## 8. Sinov

```
.venv/Scripts/python.exe _tests/erp7_test.py       # 102 tekshiruv
```

Qamrov: turlar ro'yxati kod va bazadagi CHECK da bir xil; view ustunlari
shartnomaga mos va view'ga yozib bo'lmaydi; kirim/chiqim/tuzatish va
qoldiqning yig'indi ekani; qoidalar (nol miqdor, manfiy kirim, sababsiz
tuzatish, takroriy boshlang'ich → 409, yo'q mahsulot → 404); manfiy
qoldiq o'tadi va ogohlantiradi; nom snapshot qilingani; `seed-opening`
ning idempotentligi; **chegara** — `catalog_product` ga tegilmagani.

Rezerv qamrovi: qo'yish faqat `confirmed` dan boshlab; **qoldiq
o'zgarmasligi va mavjud kamayishi**; topshirilganda ushlab turilishi;
yutilganda chiqimga aylanishi va harakatga bog'lanishi; yakuniydan
qaytganda teskari kirim yozilib rezerv tiklanishi (chiqim o'chirilmasligi);
yutqazilganda bo'shashi; yopilgan rezervni qayta bo'shatib bo'lmasligi
(409); qo'lda bo'shatishda yozuv qolishi; ortiqcha rezervning o'tishi va
ogohlantirishi.

Taklif qamrovi: `required − held = suggest`; **taklif hech narsa
yozmasligi**; tasdiqlangach `bulk` ning bir qismini yozib, xatolarni
ro'yxatda qaytarishi; ikkinchi so'rovda ajratilgani ayirilib taklif
nolga tushishi; moslashmagan pozitsiya va ogohlantirishning uzatilishi.
Moslashtirishning O'ZI tender-ai sinovlarida — bu yerda soxta javob
bilan faqat ERP ning hisobi tekshiriladi.

Tender-AI tomonida `auth_test.py` yana ikki narsani tekshiradi:
`erp_stock` modulida HTTP kutubxonasi yo'qligi va unda `INSERT`/`UPDATE`
umuman yo'qligi (faqat o'qish).

Sinov **o'z mahsulotini yaratmaydi** — katalog tender-ai niki. U mavjud
mahsulot ustida ishlaydi va oxirida faqat o'zi yozgan harakatlarni
o'chiradi.

---

## 9. REZERV — "shu karta uchun ajratildi"

### 9.1. Nega alohida tushuncha

Jurnal ikki savolga javob beradi: nima kirdi, nima chiqdi. Tender ustida
ishlaganda esa **uchinchi holat** bor: tovar hali chiqmagan, ammo boshqa
tenderga va'da qilib bo'lmaydi.

Buni chiqim bilan yozib qo'yish **xato** bo'lardi: omborda tovar turibdi,
jurnalda esa yo'q — inventarizatsiya darhol farq ko'rsatardi. Shuning
uchun rezerv:

- **jismoniy qoldiqni KAMAYTIRMAYDI** (`qty` o'zgarmaydi);
- **mavjud miqdorni kamaytiradi**: `available = qty − reserved`.

Tender-AI ning "yetadimi?" savoliga javob beradigan son endi aynan
`available` — boshqa tenderga ajratilgan tovarni ikkinchi marta hisoblab
bo'lmaydi.

### 9.2. Status qoidasi — rezervni odam yopmaydi

| Karta statusi | Rezervga nima bo'ladi |
|---|---|
| `confirmed` | **qo'yiladi** (qo'lda, karta ichidan) |
| `preparing`, `submitted` | ushlab turiladi |
| `won` | **sarflanadi**: har rezervga chiqim harakati yoziladi |
| `lost`, `rejected` | **bo'shaydi** |
| `won` dan **qaytish** | teskari kirim yoziladi, rezerv **tiklanadi** |

Ilgarigi bosqichlarda (`new` … `sent_to_client`) rezerv qo'yilmaydi:
qatnashish hali tasdiqlanmagan, ya'ni tovarni band qilish erta. Server
buni 400 bilan rad etadi, interfeys esa formani umuman ko'rsatmaydi.

Oxirgi qator muhim: yutilgan karta qaytarilsa **chiqim o'chirilmaydi** —
jurnal sodir bo'lgan narsani yozadi. Uning o'rniga **teskari kirim**
yoziladi va ikkalasi ham tarixda qoladi. Sinov buni alohida tekshiradi
("chiqim O'CHIRILMADI, teskarisi yozildi").

### 9.3. Mavjuddan oshiq rezerv — taqiq emas

Chiqimdagi bilan bir xil sabab: haqiqiy ishda hujjat kechikadi va taqiq
odamni raqamni "to'g'rilab" yozishga majbur qilardi. Rezerv o'tadi,
lekin javobda `warning` qaytadi va ro'yxatda `over_reserved` bo'limiga
tushadi ("jismonan bor, lekin hammasi band").

### 9.4. Nega rezervda kartaga FK bor (jurnalda esa yo'q)

Rezerv kartasiz **ma'nosiz** — u "shu ish uchun ajratildi" degani. Karta
o'chsa rezerv ham o'chadi (`ON DELETE CASCADE`).

Jurnal esa boshqacha: u sodir bo'lgan **harakat**, rezerv — **niyat**.
Harakat kartadan mustaqil yashaydi va `opportunity_id` unda faqat
ixtiyoriy bog'lanish (`ON DELETE SET NULL`).

Qo'lda bo'shatilganda ham yozuv **o'chirilmaydi** — `released` bo'ladi:
"nega band edi va nega bo'shadi" tarixda qolsin.

### 9.5. TAKLIF: tender pozitsiyalaridan

```
GET  /erp/opportunities/{id}/reserve-suggestions
POST /erp/opportunities/{id}/reserves/bulk
```

"Shu tenderga nima kerak va omboringizda bormi" degan savolga javob.

**Moslashtirish TENDER-AI da** bajariladi (`api/stock.py`, ~400 qator
qoida: nom va kalit so'z bo'yicha, alifbodan qat'i nazar). ERP uni
takrorlamaydi — natijasini o'qiydi (`GET /tenders/{id}/stock-check`,
service kaliti bilan). Cheklist va shablon parseri bilan bir xil qoida:
**ikkinchi nusxa bo'lmasin**.

**HECH NARSA AVTOMATIK YOZILMAYDI.** Moslashuv nom bo'yicha ishlaydi va
har doim ham to'g'ri emas — "nasos" har xil nasos bo'lishi mumkin.
Tasdiqsiz rezerv omborni ifloslantirardi va uni keyin qo'lda tozalash
kerak bo'lardi. Shuning uchun `GET` faqat **ro'yxat** qaytaradi; yozishni
odam tasdiqlagach `POST .../bulk` qiladi.

Har taklifda uchta son bor va ular uchta boshqa savolga javob beradi:

| Maydon | Savol |
|---|---|
| `required` | tenderga qancha kerak (tender-ai o'qigan) |
| `held` | shu kartaga ALLAQACHON ajratilgani |
| `suggest` | `required − held` — ikki marta band qilib qo'ymaslik uchun |
| `available` | omborda hozir nechta bo'sh (`qty − rezerv`) |

Miqdor o'qilmagan bo'lsa (`"по требованию"`, `"10-15 dona"`) taklif ham
yo'q: `can_reserve = false`. **Taxmin qilinmaydi.**

Moslashmagan pozitsiyalar ham qaytariladi — "katalogda mos mahsulot
yo'q" degan javob ham ma'lumot va uni yashirish katalogdagi bo'shliqni
ko'rinmas qilardi. Tender-AI ning ogohlantirishi (eskirgan qoldiq)
o'zgarishsiz uzatiladi.

`bulk` da bir qator o'tmasa **qolganlari yoziladi**, xatolar esa
ro'yxatda qaytadi: o'nta qatordan bittasi tufayli hammasini rad etish
odamni boshidan boshlashga majbur qilardi.

### 9.6. Endpointlar

```
GET    /erp/reserves                          (opportunity_id / product_id / only_held)
POST   /erp/opportunities/{id}/reserves       ajratish (qo'lda)
DELETE /erp/reserves/{id}                     qo'lda bo'shatish (released)
```

Status o'zgarishi javobida `stock` bloki qaytadi
(`{consumed, released, restored}`) — interfeys "3 ta rezerv sarflandi"
deb ko'rsatadi, ombor o'zgargani sezilmay qolmasin.

---

## 10. TANNARX jurnalda muzlatiladi

`schema_patch_erp_14.sql` `erp.stock_move` ga `unit_cost` ustunini
qo'shdi: harakat yozilgan paytdagi katalog tannarxi o'sha yerga
KO'CHIRILADI va boshqa qayta yozilmaydi.

Sabab jurnal g'oyasining o'zi bilan bir xil: katalogdagi narx ertaga
o'zgaradi, o'tgan chiqim esa o'sha kungi narxda bo'lib qolishi kerak.
Aks holda o'tgan yilgi tender foydasi bugun katalogni tahrirlaganda
o'zgarib ketardi.

`NULL` = "narx noma'lum", **nol emas**. Nol "tekin keldi" degani
bo'lardi va foydani sun'iy ravishda ko'tarib yuborardi.

To'liq izoh va foyda hisobi: `erp_foyda.md`.

---

## 11. Hali yo'q (ataylab)

- **Ombor bo'limlari / partiyalar** (seriya, muddat). Bitta ombor
  taxmin qilingan.
- **FIFO / o'rtacha tannarx**. Har chiqim o'sha paytdagi katalog
  narxini oladi (10-bo'lim) — partiyalar hisobi yo'q.
- **Taklifni tasdiqsiz yozish** — ataylab yo'q (9.5-bo'lim).
