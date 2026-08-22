# FAKTURA EKSPORTI — buxgalterga yuboriladigan savollar

Bu hujjat — **yuborish uchun tayyor matn**. Javob kelmaguncha
`api/erp/invoice_export.py` bo'sh qatlam bo'lib qoladi (`FORMATS = []`,
har urinish `501` qaytaradi) va kod yozilmaydi.

Sabab: eksport formati mijozning buxgalteriya tizimiga bog'liq. Taxmin
qilib yozilgan format — qayta yozish demakdir, chunki hujjatni qabul
qiladigan tomon boshqa.

---

## Nima uchun so'ralyapti

O'zbekistonda hisob-faktura yuridik kuchga ega bo'lishi uchun
**elektron (EHF)** shaklda, operator orqali yuborilishi kerak. ERP
bosib chiqargan PDF — ichki hujjat, soliq uchun **hujjat emas** (buni
bosma shaklning o'zida ham yozib qo'yganmiz).

Ya'ni ERP ning vazifasi — fakturani **tayyorlash** va uni buxgalter
ishlatadigan tizimga **uzatish**. Qanday uzatish kerakligini faqat
o'sha tizimni biladigan odam ayta oladi.

---

## Yuboriladigan matn

> Assalomu alaykum.
>
> Biz ichki ERP tizimimizda hisob-faktura va dalolatnomalarni
> tayyorlaymiz. Ular sizning tizimingizga tushishi uchun eksport
> qatlamini yozmoqchimiz va uchta aniqlik kerak.
>
> **1. Qaysi tizim va qaysi format?**
> Fakturani qaysi tizimga yuklaysiz — `didox.uz`, `faktura.uz`,
> `soliq.uz` yoki 1C? Import qaysi ko'rinishda qabul qilinadi: XML,
> Excel, CSV, yoki API orqali? Iloji bo'lsa, o'sha tizim qabul
> qiladigan **namuna faylni** yuboring — biz shu namunaga
> moslashtiramiz.
>
> **2. Kim yuboradi?**
> Elektron fakturani operatorga **siz** yuborasizmi (biz sizga fayl
> beramiz), yoki ERP to'g'ridan-to'g'ri yuborishini xohlaysizmi? Agar
> ikkinchisi bo'lsa, operatorda ro'yxatdan o'tish va kalit (EDS/API
> token) kimning nomida bo'ladi?
>
> **3. Qaysi maydonlar majburiy?**
> Bizda hozir bor: faktura raqami va sanasi, ikkala tomonning
> rekvizitlari (nomi, INN, manzil, bank hisobi, MFO, direktor),
> shartnoma raqami, tovar/xizmat qatorlari (nomi, o'lchov birligi,
> miqdor, narx, QQS stavkasi), jami summa va summa so'z bilan.
>
> Sizga bulardan tashqari nima kerak? Xususan:
> - **IKPU/MXIK kodi** (tovar tasnifi) — har pozitsiya uchun kerakmi?
>   Kerak bo'lsa, uni katalogimizga kiritishimiz lozim.
> - **Shtrix-kod yoki tovar belgisi** kerakmi?
> - **QQS ro'yxat raqami** (agar bizniki bo'lsa) qayerda ko'rsatiladi?
>
> Javob kelgach eksportni bir hafta ichida qo'shamiz.
>
> Rahmat.

---

## Javob kelgach nima bo'ladi

`api/erp/invoice_export.py` allaqachon tayyor turibdi:

```python
FORMATS = []          # <- shu yerga format qo'shiladi
def build(...):       # <- va uning yig'uvchisi
    raise ErpError(..., 501)
```

Interfeysda "Eksport" tugmasi shu ro'yxatdan o'qiydi, ya'ni format
qo'shilishi bilan tugma o'zi paydo bo'ladi.

**IKPU/MXIK kodi kerak bo'lsa** — bu katalogga tegadi
(`public.catalog_product`), ya'ni tender-ai tomonida ustun qo'shiladi
va u alohida ish sifatida rejalashtiriladi. Shuning uchun 3-savol
aynan shu maqsadda so'ralmoqda: javob "ha" bo'lsa, ish hajmi
kattalashadi.
