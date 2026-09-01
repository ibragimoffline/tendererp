# BILDIRISHNOMA — hodimga, kompaniyaga emas

**Patch:** `schema_patch_erp_22.sql` · **Kod:** `api/erp/xabar.py` ·
**Ekran:** `frontend/src/components/erp/NotificationBell.tsx` ·
**Sinov:** `_tests/erp17_test.py` · **Asos:** `erp_rollar.md` §8

---

## 1. Nega kerak

ERP da odamga qaratilgan xabar yo'q edi. Bor narsa — Tender-AI orqali
yuboriladigan eslatma (`api/erp/remind.py` → `notify.send`), lekin u
**kompaniya darajasida**: bitta Telegram guruhi, bitta email ro'yxati.
"Sizga karta biriktirildi" degan gap esa **odamga** tegishli.

Yo'naltirish oqimi (`erp_integratsiya_7.md`) kartani o'zi ochadi —
xabarsiz hodim buni faqat ekranni ochib, ro'yxatni ko'zdan
kechirganda bilardi.

---

## 2. Hodisalar

| Tur | Kimga | Qachon |
|---|---|---|
| `topshiriq` | hodimga | Tender-AI'dan karta biriktirildi |
| `taqsimlanmagan` | menejerga (yo'q bo'lsa rahbarga) | hodim xaritalanmagan — karta egasiz |
| `bekor` | hodim + menejer | Tender-AI'da qaror bekor qilindi |
| `otkazildi` | yangi mas'ulga | karta boshqa hodimga o'tkazildi |
| `muddat` | hodimga (egasiz bo'lsa menejerga) | vazifa yoki tender muddati yaqinlashdi |

**Eng muhimi — `taqsimlanmagan`**: aks holda karta "Taqsimlanmagan"
ustunida hech kim ko'rmasdan yotib qolardi, Tender-AI'da esa
"berildi" deb turardi.

`otkazildi` turi ikki holatda ishlatiladi: karta boshqa hodimga
o'tkazilganda (yangi mas'ulga) va **broker qayta taqsimlashni
so'raganda** (menejerga). Broker kartani o'zi o'tkaza olmaydi —
huquqlar matritsasida `karta.biriktirish` unda yo'q — lekin
"menga to'g'ri kelmadi" deyishi kerak. So'rov **tarixga ham**
yoziladi: keyin "aytgan edim" degan bahs bo'lmaydi.

---

## 2b. Muddat eslatmasi — ikki kanal, ikki ishonchlilik

`api/erp/remind.py` (jadval bo'yicha yuriladi) endi **avval ERP
ichida** xabar yozadi, keyin Tender-AI orqali kompaniya kanaliga
(Telegram/email) yuborishga uradi.

Ilgari belgilash (`reminded_at`) TASHQI kanalga bog'liq edi:
Tender-AI o'chgan bo'lsa hech kim hech narsa olmasdi. Endi ERP o'z
ishini o'zi bajaradi va tashqi kanal — qo'shimcha; uning xatosi
javobda ochiq qaytadi, lekin belgilashni to'xtatmaydi (aks holda
ertaga hamma xabar takrorlanardi).

Har kim **faqat o'zinikini** oladi: umumiy ro'yxatda odam o'zinikini
qidirib topishi kerak edi. Mas'uli yo'q muddatlar menejerga
jamlanma bo'lib ketadi.

---

## 3. Uch qoida

**Xabar yozilmasa ish to'xtamaydi.** `yoz()` hech qachon chaqiruvchini
yiqitmaydi: karta ochilishi xabardan muhimroq. Xato jurnalga tushadi —
ya'ni yo'qolgani ham ko'rinadi.

**`localhost` havolasi yozilmaydi.** `ERP_WEB` mahalliy manzil bo'lsa
xabarda havola umuman bo'lmaydi. Boshqa kompyuterda ochilmaydigan
havola — buzuq havola, va "havola bor, lekin ishlamaydi" eng yomon
variant (`ommaviy_url` qoidasi bilan bir xil).

**O'ziniki — faqat o'ziniki.** `app_user_id` **sessiyadan** olinadi,
so'rovdan emas. Begona xabarni o'qish yo'li yo'q, begona id bilan
"o'qildi" deb belgilash esa hech narsani o'zgartirmaydi. Shuning
uchun bu endpointlarda huquq matritsasi ishlatilmaydi (parol
almashtirish bilan bir xil qoida).

---

## 4. Ekran

Yon paneldagi qo'ng'iroq: o'qilmaganlar soni, 60 soniyada bir marta
yangilanadi. Ro'yxat **ochilganda** o'qilgan deb belgilanadi — avtomat
emas, aks holda ko'rilmagan xabar hisoblagichdan tushib ketardi.

Xabarni bosish kartani ochadi.

---

## 5. Hali yo'q — ataylab

**Tashqi kanal (email/Telegram).** ERP ning o'z SMTP/bot rekvizitlari
sozlanmagan; ularni Tender-AI dan "qarzga olish" sirni ikkinchi joyda
saqlash bo'lardi (`erp_rollar.md` §8: obunachi jadvali alohida).
Jadval kanalga tayyor: `yuborildi_at` ustuni shu uchun.

**Obuna sozlamalari** (kim qaysi hodisani oladi) — hozir qoida kodda
va sodda: hodimga o'ziniki, menejerga taqsimlanmaganlar.
