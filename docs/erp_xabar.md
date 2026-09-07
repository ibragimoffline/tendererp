# BILDIRISHNOMA — hodimga, kompaniyaga emas

**Patch:** `schema_patch_erp_22.sql`, `schema_patch_erp_27.sql` ·
**Kod:** `api/erp/hodisa.py` (quvur), `api/erp/xabar.py` (saqlash),
`api/erp/navbat.py` (yetkazish) ·
**Ekran:** `frontend/src/components/erp/NotificationBell.tsx` ·
**Sinov:** `_tests/erp_bildirishnoma_test.py`, `_tests/erp17_test.py` ·
**Asos:** `erp_rollar.md` §8

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
| `biriktirish_olib_tashlandi` | **eski** mas'ulga | karta undan boshqasiga o'tkazildi |
| `status` | mas'ul + chat a'zolari | karta holati o'zgardi |
| `vazifa` | vazifa bajaruvchisiga | vazifa unga biriktirildi |
| `hujjat_muddat` | menejerga | mijoz hujjati muddati 30 kundan kam qoldi |
| `qaror` | menejerga (yo'q bo'lsa rahbarga) | odam qaror qabul qilishi kerak |
| `tizim` | menejerga | ish oqimi to'xtadi, aralashuv kerak |
| `chat_yangi` | chat a'zolariga | chatga yangi xabar (**yig'ma**) |
| `chat_mention`, `chat_qoshildi`, `chat_ochirildi` | tegishli odamga | chat hodisalari |

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

## 2c. Uch qatlam (27-patch)

Ilgari bildirishnoma yuborish **to'rt modulga** tarqalgan edi —
`topshiriq.py`, `opportunity.py`, `remind.py`, `chat.py`. Har biri
o'zicha qabul qiluvchi tanlardi va "kim nima oladi?" degan savolga
javob berish uchun to'rttasini birga o'qish kerak edi.

    hodisa.py   NIMA bo'ldi -> KIMGA -> qaysi KANAL
    xabar.py    qanday SAQLANADI va O'QILADI
    navbat.py   tashqi kanalga qanday YETKAZILADI

**Qabul qiluvchi — munosabatdan, ro'yxatdan emas.** Hech qayerda
hisob id si qo'lda yozilmaydi: kartaning mas'uli
(`opportunity.broker_id`), chat a'zolari (`chat_member`), vazifa
bajaruvchisi (`opportunity_task.assignee_broker_id`). Hodim almashsa
bildirishnoma ham o'zi to'g'ri odamga ketadi.

**O'z amali haqida xabar kelmaydi.** Har chaqiruvda `chiqaruvchi`
ro'yxatdan olib tashlanadi. Istisno yo'q: "o'zim yozgan xabarim
haqida bildirishnoma" — bildirishnomalarga bo'lgan ishonchni
yo'qotadigan birinchi narsa.

---

## 2d. Takrorlanmaslik va yig'ish

`erp.notification.dedup_key` — hodisa + qabul qiluvchi kaliti,
qisman **noyob** indeks bilan. Qayta urinish yoki ikki marta bosilgan
tugma ikkinchi qator yozmaydi.

Ikki xil xulq:

* `kotar=False` — takror butunlay e'tiborsiz (vazifa biriktirish,
  bir yo'naltirish bir marta);
* `kotar=True` — mavjud qator **ko'tariladi**: matn yangilanadi,
  o'qilgan belgisi olinadi. Chat uchun shu: 20 ta xabarlik suhbat
  **bitta** bildirishnoma beradi, aks holda odam ertasiga hammasini
  o'qimay yopishni odat qilardi.

Chatdagi aniq son baribir ko'rinadi — chat ro'yxatidagi o'qilmagan
hisoblagichida.

---

## 2e. Yetkazish: navbat, qayta urinish, holat

`erp.notification_delivery` — har kanal uchun bitta qator (email
ketib, Telegram yiqilishi mumkin). Bildirishnoma bilan **bitta
tranzaksiyada** yoziladi (`db.tx()`), yuborish esa keyin va alohida
(`api/erp/navbat.py`, jadval bo'yicha — `register_navbat_task.ps1`).

    pending -> sent | failed -> (qayta urinish) -> sent | terminal

**`delivered` holati yo'q** va bu ongli qaror: Tender-AI `notify`
"yubordim" deydi, "yetib bordi" demaydi. Bo'lmagan dalilni holat
sifatida yozish kuzatuvni yolg'on qilardi.

Qayta urinish 1, 5, 15, 60, 240 daqiqada. **Terminal** — ikki yo'l
bilan: xatoning o'zi tuzalmaydigan bo'lsa (404, "chat not found")
yoki urinishlar tugasa. Tarmoq uzilishi va 503 — vaqtinchalik,
qayta uriniladi.

**Ikki ishonchlilik chegarasi.** Chat xabari Telegram yiqilgani
uchun yo'qolmaydi: yozuv oldin va o'z tranzaksiyasida, yuborish
keyin. Teskarisi — yuborishni yozuv bilan bir tranzaksiyaga qo'yish
— tashqi xizmat o'chganda odamlarning yozishmasini yo'qotardi.

---

## 2f. Kanal kompaniya darajasida — bu cheklov

Telegram bot tokeni va SMTP rekvizitlari Tender-AI o'rnatmasida,
qabul qiluvchilar ham o'sha yerda sozlangan. ERP manzil yubormaydi
va **yubora olmaydi**. Ya'ni "Karimovga email ketdi" degan gap bu
arxitekturada yolg'on bo'lardi.

Shuning uchun tashqi kanal hodisaga **bir marta** qo'yiladi (har
odamga emas) va faqat butun kompaniyaga tegishli hodisalarda:
`taqsimlanmagan`, `muddat`, `hujjat_muddat`, `tizim`. Chat u yerda
yo'q — yozishmani Telegram guruhiga ko'chirish yozishmaning o'zini
ma'nosiz qilardi.

Kanal sozlamasi: `erp.notification_pref` (hodim x hodisa x kanal).
Qator yo'q = standart holat (kodda). **Ilova kanali sozlanmaydi**:
u yagona ishonchli joy va uni o'chirish "yubordik, lekin hech
qayerda yo'q" degan holatni yaratardi.

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
yangilanadi. Hisoblagich **yagona manbadan** keladi
(`GET /erp/unread`) — bildirishnoma ham, chat ham. Ilgari ikki
so'rov ikki xil paytda tugab, ekranda ikki xil son ko'rinardi.

**O'qilgan deb belgilash — qaysi hodisada.** Ro'yxat ochilgani
o'qilgan degani **emas** (ilgari shunday edi: qo'ng'iroqni bexosdan
bosgan odam hisoblagichni nolga tushirardi va o'qilmagan xabar
ro'yxat ichida ko'milib qolardi). Endi ikki aniq hodisa: qatorning
o'zini bosish, yoki "hammasini o'qildi" tugmasi.

**Klik manzilini server aytadi** (`nishon`): chat bildirishnomasi
aynan o'sha **chatni** ochadi, vazifa — vazifani, karta — kartani.
Umumiy panelga hech qachon olib bormaydi. Ekran o'z qoidasini
tutmasligi kerak, aks holda yangi hodisa turi jimgina "hech qayerga
olib bormaydigan" bildirishnoma bo'lib qolardi.

Sahifalash: `before_id` bo'yicha "yana yuklash". Xato **ko'rsatiladi**
va qayta urinish tugmasi bor — jim yutilgan xato "xabar yo'q" bo'lib
ko'rinardi.

---

## 5. Kuzatuv

`erp.v_notification_health` — kanal kesimida: pending, sent, failed,
terminal, **eng eski kutayotgan qator** va oxirgi muvaffaqiyatli
yuborish. Eng muhim raqam — `eng_eski_pending`: "navbat bor" bilan
"navbat to'xtab qolgan" ni faqat u ajratadi.

Ekran: `GET /erp/notifications/health` (administrator). `check_setup.py`
ham qaraydi: bir soatdan ortiq kutayotgan qator bo'lsa ogohlantiradi
va jadval vazifasi qo'yilmaganini aytadi.

---

## 6. Hali yo'q — ataylab

**Odam darajasidagi email/Telegram.** Yuqoridagi 2f: rekvizitlar
Tender-AI da va u kompaniya darajasida ishlaydi. ERP ning o'z
obunachi jadvali (`erp_rollar.md` §8) kiritilganda `navbat.py`
dagi `_yubor()` ni almashtirish yetadi — navbat, qayta urinish va
holat allaqachon joyida.

**Tinch soatlar (quiet hours).** Sozlama infratuzilmasi endi bor
(`erp.notification_pref`), lekin vaqt bo'yicha to'sish qo'shilmadi:
u faqat tashqi kanalga ma'noli, u kanal esa hozir kompaniya
guruhiga ketadi — ya'ni "kimning tuni" degan savolning javobi yo'q.
