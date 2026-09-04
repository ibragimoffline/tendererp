# FOYDA — "bu tenderdan qancha ishladik?"

Bu hujjat ERP dagi eng oxirgi savolga javob beradi. Karta olingan,
taklif topshirilgan, shartnoma tuzilgan, tovar chiqarilgan, faktura
yozilgan — **shundan keyin nima qoldi?**

Savol sodda ko'rinadi, lekin javobi uchta alohida raqamni bir joyga
keltirishni talab qiladi va ularning har biri boshqa moduldan keladi.

---

## 1. Uchta raqam va ularning manbai

| Raqam | Qayerdan | Modul |
|---|---|---|
| **Daromad** | Chiqarilgan fakturalarning qatorlaridan, **QQS SIZ** | `invoice.py` |
| **Tannarx** | Kartaga bog'langan chiqimlarning **muzlatilgan** narxidan | `stock.py` |
| **Foyda** | Ayirma. Foiz: `foyda / daromad` | `profit.py` |

Kod: `api/erp/profit.py`, endpointlar `GET /erp/profit` (rahbar) va
`GET /erp/opportunities/{id}/profit` (karta ustida ishlagan odam).

---

## 2. QQS DAROMAD EMAS

Faktura 2 240 000 so'mga chiqarilgan bo'lsa, kompaniya 2 240 000
ishlamadi. Bu summaning 240 000 i — QQS: u davlatniki, biz uni faqat
mijozdan yig'ib, byudjetga o'tkazamiz. Uni daromadga qo'shish — o'zini
o'zi aldash.

Shuning uchun `revenue` da faqat QQS siz summa turadi, QQS esa `vat` da
**alohida** ko'rsatiladi. Kartadagi blokda ham u alohida yozuv sifatida
chiqadi:

```
Daromad (QQS siz): 2 000 000  + QQS 240 000
```

Sabab shunchaki hisobda emas: agar QQS ko'rinmasa, "nega faktura 2.24
mln, foyda esa 2 mln dan hisoblanyapti?" degan savol tug'iladi va unga
javob berish uchun har safar kodga qarash kerak bo'lardi.

---

## 3. TANNARX MUZLATILADI — eng muhim qaror

Katalogdagi `cost_price` vaqt o'tib o'zgaradi: yetkazib beruvchi narxni
ko'taradi, kurs siljiydi, yangi partiya boshqa narxda keladi.

Agar foyda **joriy** katalog narxidan hisoblansa, o'tgan yilgi tender
foydasi bugun katalogni tahrirlaganingizda o'zgarib ketadi. Ya'ni
hisobot barqaror bo'lmaydi: bir xil savolga har hafta boshqa javob.

Shuning uchun `schema_patch_erp_14.sql` `erp.stock_move` ga `unit_cost`
ustunini qo'shdi. Tannarx **harakat yozilgan paytda** o'sha yerga
ko'chiriladi va boshqa hech qachon qayta yozilmaydi.

```
katalog: cost_price = 300 000
   -> chiqim yozildi: stock_move.unit_cost = 300 000   [MUZLADI]
katalog: cost_price = 999 999  (narx ko'tarildi)
   -> o'sha chiqimning tannarxi hamon 300 000
```

Bu snapshot qoidasining o'sha o'zi: tender ma'lumoti, rekvizitlar,
faktura qatorlari — hammasi shu tarzda muzlatiladi
(`erp_arxitektura.md`).

Sinov buni to'g'ridan-to'g'ri tekshiradi: `erp8_test.py` katalog narxini
o'zgartiradi va tannarx **o'zgarmaganini** talab qiladi.

### Teskari harakat ham o'sha narx bilan

Karta `won` dan qaytarilsa, ERP kompensatsiya qiluvchi `in` harakatini
yozadi. U **asl harakatning** `unit_cost` ini oladi, katalogdagi joriy
narxni emas — aks holda bekor qilishning o'zi foydani o'zgartirib
yuborardi.

---

## 4. `NULL` — "bilmaymiz", nol emas

Katalogda narx ko'rsatilmagan bo'lsa, `unit_cost` `NULL` bo'lib qoladi.

Uni nolga aylantirish oson yo'l edi va **eng zararli** yo'l: nol
"tovar tekin keldi" degani, ya'ni butun summa foyda bo'lib ko'rinadi.
Rahbar ekranda 100% foyda ko'radi va uni ishonch bilan hisobotga
qo'yadi.

Shuning uchun:

- `NULL` tannarxli chiqimlar summaga **qo'shilmaydi**;
- ular `unknown_cost_moves` da **sanaladi**;
- `complete: false` bo'ladi va bu javobda ham, ekranda ham ochiq
  yoziladi:

> Hisob to'liq emas: 3 ta chiqimning tannarxi noma'lum (katalogda narx
> ko'rsatilmagan). Ular tannarxga qo'shilmadi — ya'ni haqiqiy foyda
> bundan kam.

Oxirgi jumla ataylab: foydalanuvchi raqam qaysi **tomonga** xato
ekanini bilishi kerak.

---

## 5. Daromadga nima kirmaydi

| Holat | Kiradimi | Nega |
|---|---|---|
| `draft` | **Yo'q** | Qoralama hali hujjat emas |
| `issued`, `partial`, `paid` | Ha | Hujjat chiqarilgan |
| `cancelled` | **Yo'q** | Bekor qilingan hujjat pul keltirmaydi |

Diqqat: `paid` emas, `issued` dan boshlab hisoblanadi. Bu — **hisoblash
usuli** (accrual): daromad hujjat chiqarilganda tan olinadi, pul
kelganda emas. Kim qancha qarzdorligi alohida ko'rsatkich va u
`erp_faktura.md` da (`/erp/invoices/stats`).

Tannarxga esa faqat `kind = 'out'` harakatlar kiradi. Kirim va
inventarizatsiya tuzatishi sotuv emas.

---

## 6. Foiz `NULL` bo'lishi mumkin

Daromad nol bo'lsa foiz hisoblanmaydi va `null` qaytadi.

Nolga bo'lishdan qochish — bu yerda ikkinchi darajali sabab. Asosiysi:
"0% foyda" degan raqam **yolg'on**. Faktura hali chiqarilmagan karta
zarar keltirgani yo'q — u shunchaki hali yakunlanmagan. Ekranda `—`
ko'rinadi.

Xuddi shu sabab bilan, kartada hech qanday pul harakati bo'lmasa
(`revenue = 0` va `cost = 0`), foyda bloki umuman **ko'rsatilmaydi**:
nol-nol-nol qator hech narsa aytmaydi.

---

## 7. Rahbar hisoboti

`GET /erp/profit` kartalar bo'yicha ro'yxat va umumiy yig'indi beradi.
Endpoint `menejer` (va undan yuqori) huquqini talab qiladi: pul haqidagi umumiy
ko'rsatkich har kimga emas. Brokerga panel ko'rinmaydi (403 kelsa UI uni
jim yashiradi), lekin **o'z kartasining** foydasini u ko'radi — bu
`/erp/opportunities/{id}/profit` orqali va u rollar bilan
cheklanmagan.

Ro'yxatdan pul harakati bo'lmagan kartalar tashlab yuboriladi. **Bitta
istisno bor:** tannarxi noma'lum karta summasi nol ko'rinsa ham
ro'yxatda qoladi. Aynan o'sha karta yig'indini shubhali qilyapti — uni
yashirish hisobotni yolg'on qilardi.

---

## 8. Nima qilinmagan (ataylab)

| Nima | Nega yo'q |
|---|---|
| **FIFO / o'rtacha tannarx** | Partiyalar hisobi yo'q. Har chiqim o'sha paytdagi katalog narxini oladi. Bu — sodda va tushunarli model; partiyalar kerak bo'lsa, u alohida bosqich |
| **Bilvosita xarajatlar** (transport, ish haqi, bank) | ERP da xarajat moduli yo'q. "Foyda" bu yerda **yalpi** foyda: daromad − tovar tannarxi. Sof foyda buxgalteriyada hisoblanadi |
| **Valyuta konvertatsiyasi** | Kurs bo'yicha qo'shish yo'q — aralash valyuta ALOHIDA qatorlar bo'lib chiqadi (9-bo'lim) |

Uchalasi ham bilib qoldirilgan cheklov, kamchilik emas — lekin
ularning har biri hisobotni o'qiyotgan odamga aytilishi kerak.

---

## 9. ARALASH VALYUTA QO'SHILMAYDI

### 9.1. Nima noto'g'ri edi

Foyda hisobotining umumiy yig'indisi hamma kartani bir qopga solib
qo'shardi, interfeys esa natijani `UZS` deb yozardi. Bazada bitta USD
karta paydo bo'lishi bilan bu son **yolg'on** bo'lardi — va uni
yolg'on ekanini hech narsa ko'rsatmasdi.

Xuddi shu xato rahbar panelida (`stats.py`), tahlilda
(`analytics.py` — yutqazish sabablari) va mijoz kartasida
(`clients.py` — yutilgan summa) ham bor edi.

### 9.2. Qaror

**Konvertatsiya YO'Q.** Kurs bo'yicha qo'shish uchun "qaysi kungi
kurs?" degan savolga javob kerak: hujjat sanasidagimi, bugungimi,
o'rtachami? Har javob boshqa raqam beradi va hisobot har kuni
o'zgarib turadi.

Buning o'rniga:

| Holat | Nima ko'rsatiladi |
|---|---|
| Hamma karta **bitta** valyutada | Odatdagidek: umumiy yig'indi |
| **Bir nechta** valyuta | Har valyuta uchun ALOHIDA qator; umumiy yig'indi — **yo'q** |

Bu loyihadagi umumiy qoidaning davomi: turli o'lchovlar
aralashtirilmaydi (`erp_arxitektura.md` — Go/No-Go bali va moslik bali
ham qo'shilmaydi).

### 9.3. Javobda nima bor

`GET /erp/profit`:

```json
{
  "by_currency": [
    {"currency": "UZS", "revenue": 10000000, "profit": 8000000, "cards": 3},
    {"currency": "USD", "revenue": 1200,     "profit": 400,     "cards": 1}
  ],
  "totals": null,
  "currencies": ["UZS", "USD"],
  "mixed_currency": true
}
```

`totals` — **faqat** bitta valyuta bo'lganda to'ldiriladi (o'shanda u
`by_currency` ning yagona qatoriga teng). Aralashda `null`: noto'g'ri
yig'indi yo'q yig'indidan yomonroq.

`GET /erp/stats` da esa pul yig'indilari (`open_total`, `won_total`,
bosqichlar bo'yicha summalar, broker va mijoz kesimlari) aralashda
`null` qaytadi. **Sanoq esa qoladi** — nechta karta borligi valyutaga
bog'liq emas.

### 9.4. Ekranda

Foyda panelida har valyuta o'z qatorida (aralash bo'lgandagina valyuta
kodi yoziladi — bitta valyutada ortiqcha ustun ko'rinmasin). Ostida
sabab turadi: *"Valyutalar aralash — umumiy yig'indi berilmaydi."*

Rahbar panelida son o'rniga bo'sh joy qoladi va tepada bir qator
izoh: qaysi valyutalar aralashgani va nega yig'indi yo'qligi. Nol
ko'rsatish yolg'on bo'lardi ("hech narsa yo'q"), qo'shib yuborish esa
undan ham yomon.

### 9.5. "Aralash" ikki joyda BOSHQACHA hisoblanadi

Bu bilib qilingan:

- **foyda** — valyutani KARTADAN oladi, chunki daromad fakturadan
  yig'iladi va faktura kartaga bog'langan;
- **rahbar paneli** — `start_price` bor kartalarni sanaydi, chunki u
  aynan boshlang'ich narxlarni yig'adi.

Ya'ni narxi ko'rsatilmagan karta panelda "valyuta" hisobiga
kirmaydi — u yerda qo'shiladigan narsaning o'zi yo'q. Sinov ikkala
yo'lni ham alohida tekshiradi.

### 9.6. Sinov

`_tests/erp8_test.py` 10-bo'lim: bitta valyutada umumiy yig'indi bor;
ikkinchi valyutali karta qo'shilgach `mixed_currency` yoqiladi,
`totals` **`null`** bo'ladi, `by_currency` ikki qator qaytaradi va
valyutalar bir-biriga qo'shilib ketmagani tekshiriladi. Rahbar
panelida esa summalar `null`, kartalar soni esa joyida.
