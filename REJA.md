# ERP — REJALASHTIRILGAN ISHLAR

Holat: **1-4 bosqich, 5A va AUTH-1 bajarilgan**, **meros xatolari yopilgan**, **ajratish bajarilgan**, **0-ish yopilgan** (ERP endi
alohida loyiha — `docs/erp_arxitektura_2.md`). Sinovlar: `erp_test.py` 83/0,
`erp_test.py` 123/0, `erp2_test.py` 79/0, `erp3_test.py` 58/0,
`erp4_test.py` 45/0, `erp5_test.py` 81/0, `erp6_test.py` 121/0,
`erp7_test.py` 102/0, `erp8_test.py` 113/0, `erp9_test.py` 48/0 —
jami **770 tekshiruv** (baza BO'SH bo'lsa ham shuncha: sinovlar
o'z ma'lumotini o'zi yaratadi)
(tender-ai tomonida yana 102 ta);
ikkala frontend ham toza quriladi.

Quyidagilar — qolgan ishlar, bajarilish tartibida.

Har ish qadamlarga bo'lingan. Qadamlar tartibi har bosqichda bir xil, chunki
loyiha kelishuvi shuni talab qiladi (`erp_bosqichlar.md` "Har bosqich uchun
umumiy qoida"):

```
sxema patchi -> modul kodi -> main.py ulash -> sinov -> frontend
   -> ULASH.md + integratsiya hujjati -> sync.ps1 -> tekshirish
```

Belgilar: `[ ]` bajarilmagan, `[~]` qisman, `[x]` bajarilgan.

---

## 0-ish — Qoldiq ishlar (1-2 bosqichdan)

Kichik, lekin 3-bosqichdan oldin yopilgani ma'qul: ular allaqachon yozilgan
kodga tegishli.

- [x] **0.1. Brauzerda tekshirish (dastur tomonidan).** Ikkala ilova
      ko'tarildi, proksi va barcha ERP oqimlari jonli stekda tekshirildi,
      namuna ma'lumot yaratildi. **Ko'z bilan ko'rish (drag-and-drop, joylashuv)
      sizda qoladi** — hisobotdagi ro'yxat bo'yicha.
- [x] **0.A. AJRATISH** (rejadan tashqari, loyiha egasi talabi bilan):
      ERP alohida backend + alohida frontend; tender-ai da ERP kodi qolmadi;
      integratsiya uch nuqtada (`docs/erp_arxitektura_2.md`, `INTEGRATSIYA.md`).
- [x] **0.2. Mijoz hujjatlari uchun shablon (.xlsx/.csv) va import.**
      Bajarildi: tender-ai'da `compliance.parse_document_file()` yozishdan
      ajratildi va `POST /company/documents/parse` xizmat sifatida ochildi;
      ERP'da `tenderai.template/parse_documents`, `clients.import_documents`,
      ikki endpoint va `ClientCard` dagi shablon/import bloki (dry-run ->
      ko'rish -> tasdiqlash). Sinov: `erp2_test.py` da 20 ta yangi tekshiruv
      (round-trip, takror yuklash yangilaydi, yaroqsiz fayl -> 422).
- [x] **0.3. "Tenderda yangilanish bor" belgisi.** Bajarildi:
      `opportunity.diff_with_tender()` snapshotni jonli tender bilan
      solishtiradi (9 maydon) va HECH NARSA YOZMAYDI; tender manbadan
      o'chirilgan bo'lsa `exists: false` (xato emas). Endpoint
      `GET /erp/opportunities/{id}/tender-diff`; kartada nishon —
      "Tenderda N maydon o'zgargan", ochilsa "eski → yangi" ro'yxati.
      Sinov: `erp_test.py` da 12 ta yangi tekshiruv (snapshot qo'lda
      buzilib, farq topilishi va snapshot o'zgarmagani tasdiqlanadi).
- [x] **0.4. ERP interfeysi tili** — o'zbekcha qoldirildi (ajratishda
      tasdiqlandi: ERP o'z ilovasi, i18n qatlami umuman ko'chirilmadi).
- [x] **0.5. `run_all.ps1` xatosi (M3)** — BAJARILDI (pastdagi M3 ga
      qarang). `run_all.ps1` endi exit kodiga emas, `/health` JAVOBIGA
      qaraydi; `run_api.ps1` esa `exit 0` bilan tugaydi. Bu qator
      ro'yxatda ochiq qolib ketgan edi — tuzatildi.

---

## 1-ish — 3-BOSQICH: vazifalar, eslatmalar va bildirishnoma  ✅ BAJARILDI

- [x] **1.1. `schema_patch_erp_3.sql`** — `opportunity_task`, `lost_reason`,
      `reminded_at` / `deadline_reminded_at`; eski `next_task` bir martalik
      ko'chirildi (5 yozuv), ustunlar joyida qoldi.
- [x] **1.2. `api/erp/tasks.py`** — CRUD, "mening ishlarim", eslatma tanlovi.
- [x] **1.3. Endpointlar** — `/erp/opportunities/{id}/tasks`, `/erp/tasks/{id}`,
      `/erp/my-tasks`, `/erp/reminders`; `lost_reason` status endpointida.
- [x] **1.4. `api/erp/remind.py` + `register_erp_task.ps1`.**
      REJADAN CHETGA CHIQISH: `run_etl.py` post-qadami EMAS (ERP alohida
      loyiha) — o'z jadvali. Transport tender-ai'da qoldi
      (`POST /notify/send`), sirlar ERP'ga ko'chmadi.
- [x] **1.5. Frontend** — kartada vazifalar bloki, "Mening ishlarim"
      bo'limi, `lost` da sabab tanlash.
- [x] **1.6. `_tests/erp3_test.py`** — 58 tekshiruv.
- [x] **1.7. Hujjat** — `docs/erp_integratsiya_3.md`, `INTEGRATSIYA.md` 8-bo'lim.

---

## 2-ish — 4-BOSQICH: taklif va topshirish  ✅ BAJARILDI

- [x] **2.1. `schema_patch_erp_4.sql`** — `erp.submission`, JSONB nusxalar,
      `UNIQUE (opportunity_id, version)`.
- [x] **2.2. `api/erp/submission.py`** — paket (narx + cheklist + hujjatlar +
      manba statusi) va topshirishni qayd etish. Narx va cheklist O'QILADI,
      qayta hisoblanmaydi.
- [x] **2.3. To'siq tekshiruvi** — `blocking > 0` da ogohlantirish; tasdiq
      majburiy va u `blocking_count` + `confirmed_note` + TARIXGA yoziladi.
- [x] **2.4. Frontend** — kartada "Taklif va topshirish" bo'limi:
      yig'ma holat, ogohlantirishlar, narx, tasdiq va versiyalar ro'yxati.
- [x] **2.5. Manbadan natija** — CHEKLOV OCHIQ AYTILDI: manba g'olibni
      bermaydi (bazada bunday ustun yo'q). Shuning uchun faqat "tender
      yopilgan, kartani yakunlash kerakmi?" degan TAKLIF; status avtomatik
      o'zgarmaydi.
- [x] **2.6. Sinov va hujjat** — `_tests/erp4_test.py` (45 tekshiruv),
      `docs/erp_integratsiya_4.md`.

---

## 3-ish — 5-BOSQICH: og'ir modullar

- [x] **3.1. Qaror hujjati** — `docs/erp_arxitektura_3.md`. Xulosa:
      ajratish savoli yopilgan; 5-bosqich **ikkiga bo'linadi** —
      **5A** (auth'siz xavfsiz) va **5B** (pul va ombor, auth TALAB QILADI).
- [x] **3.2. 5A-1: shartnoma** + `erp.own_company` (bizning rekvizitlar).
      `docs/erp_integratsiya_5.md`, `_tests/erp5_test.py` — 47 tekshiruv.
- [x] **3.3. 5A-2: rahbar tahlili** — `api/erp/analytics.py`,
      `GET /erp/analytics`. Bosqich vaqtlari (o'rtacha/mediana/eng uzun +
      hozir turganlar alohida), voronka, broker sikli, qotib qolganlar,
      yutqazish sabablari. YANGI JADVAL YO'Q — `opportunity_history` dan.
- [x] **3.4. 5B-1: ombor** — **A1** yo'li bilan bajarildi.
      `schema_patch_erp_8.sql` — `erp.stock_move` jurnali va
      `erp.v_stock_balance` SHARTNOMA-VIEW i. Qoldiq alohida ustunda
      saqlanmaydi: u `SUM(qty)`. Tender-AI qoldiqni view dan o'qiydi
      (`api/erp_stock.py`) — `public.*` ga yozmaslik qoidasi buzilmadi.
      To'rt tur (`opening`/`in`/`out`/`adjust`), manfiy qoldiq taqiq
      emas — ogohlantiriladi, import qoldig'idan bir tugma bilan
      ko'chirish. Interfeys: **Ombor** bo'limi.
      **REZERV** (`schema_patch_erp_10.sql`): "shu karta uchun ajratildi" —
      qoldiqni kamaytirmaydi, MAVJUD miqdorni kamaytiradi
      (`available = qty - reserved`) va kartaning statusiga bog'langan:
      `confirmed` da qo'yiladi, `won` da chiqimga aylanadi,
      `lost`/`rejected` da bo'shaydi, yakuniydan qaytganda teskari kirim
      bilan tiklanadi. Tender-AI ning "yetadimi?" hisobi endi
      **mavjud** miqdordan yuradi.
      **TAKLIF:** `GET /erp/opportunities/{id}/reserve-suggestions` —
      tender pozitsiyalaridan "nima kerak, omborda bormi" ro'yxati
      (moslashuv tender-ai da, yozish faqat odam tasdig'i bilan:
      `POST .../reserves/bulk`). Sinov: `erp7_test.py` 102 tekshiruv.
      Hujjat: `docs/erp_ombor.md` 9-bo'lim.
- [x] **3.5. 5B-2: hisob-faktura** — ma'lumot modeli qurildi
      (`schema_patch_erp_11.sql`). **QQS mijoz passportida**
      (`vat_payer` / `vat_rate`; NULL = hali so'ralmagan) va faktura
      QATORIGA nusxa ko'chiriladi — passport keyin o'zgarsa chiqarilgan
      hujjat buzilmasin. Summalar SAQLANMAYDI, qatorlardan hisoblanadi;
      rekvizitlar SNAPSHOT; `draft` dan chiqqach hujjat MUZLAYDI.
      To'lovlar alohida jadval ("qisman to'landi" — status emas, hisob
      natijasi). **Eksport qatlami ATAYLAB bo'sh** (`invoice_export.py`,
      501): format mijozdan so'raladi. Interfeys: **Hisob-fakturalar**
      bo'limi.
      **ZANJIR:** `POST /erp/opportunities/{id}/invoice` — kartadan
      faktura chiqaradi va qatorlarni AJRATILGAN TOVARDAN to'ldiradi
      (miqdor haqiqiy, narx katalogdan; topilmasa 0 va bu ochiq
      aytiladi). Taklif -> shartnoma -> faktura -> to'lov zanjiri
      yopildi. Sinov: `erp8_test.py` 90 tekshiruv.
      **BOSMA SHAKL:** `InvoicePrint.tsx` — brauzer chop etadi (PDF
      kutubxonasi yo'q), summa SO'Z bilan (`amount_words`, serverda va
      sinaladi). Shaklning o'zida yozilgan: yuridik kuch yo'q, EHF
      operator orqali yuboriladi.
      Hujjat: `docs/erp_faktura.md`.
- [x] **3.6. AUTH** — TARTIB O'ZGARDI: 5B dan oldin bajarildi.
      **Auth-1 da kimlik teskari tomonda edi va tuzatildi**: hodim
      hisoblari ERP ga ko'chdi (`erp.app_user`, `broker_id` -> `erp.broker`
      FK), tender-ai da esa KOMPANIYA hisobi qoldi (`company_account`).
      Sabab: odam — ERP ning tushunchasi. 50/56 endpoint himoyalangan,
      3 tasi rahbar, 6 tasi admin huquqini talab qiladi,
      **`created_by` sessiyadan**. Administrator uchun **Hodimlar**
      ekrani (`/erp/staff`): hodim va uning hisobi bitta ro'yxatda,
      hisob ochish, rol, parol tiklash; ochiq ishi bor hodimni
      faolsizlantirib bo'lmaydi. Sinov: `erp6_test.py` 94 tekshiruv
      (endi tender-ai'siz) + `tender-ai/_tests/auth_test.py` 43 tekshiruv.
      Hujjat: `docs/erp_auth.md`.
- [x] **3.7. AUTH-2** — tender-ai ham yopildi.
      Kirish ekrani (uz/ru/en), **global darvoza** (`FastAPI(dependencies=
      [Depends(gate)])`) — 63 endpointdan 8 tasi ataylab ochiq, qolgani
      yopiq va yangi endpoint avtomatik himoyalanadi. ERP u yerga
      **service kaliti** bilan boradi (`X-Service-Key`), kalit faqat 6
      endpointni ochadi. "Mening ishlarim" endi sessiyadagi `broker_id`
      bo'yicha sukut filtrlanadi. Sinov: `tender-ai/_tests/auth_test.py`
      64 tekshiruv. Hujjat: `docs/erp_auth.md` 8-bo'lim.
- [x] **3.8. AUTH-3** — `ErpLink` istisnosi YOPILDI ("B" varianti).
      `schema_patch_erp_7.sql` — `erp.v_tender_status` SHARTNOMA-VIEW i;
      tender-ai uni o'z backendida o'qiydi (`api/erp_status.py`,
      `GET /tenders/{id}/erp-status`) va ERP ga HTTP yubormaydi.
      ERP ning 56 endpointidan 51 tasi himoyalangan — ochiq qolgani
      faqat `/health`, `/erp/meta`, `/erp/auth/*`. Chegara endi
      SIMMETRIK va ikkala sinov ham tekshiradi. Yon natija: ERP CORS
      ro'yxatidan 5173 va `VITE_ERP_API` olib tashlandi.
- [x] **3.9. AUTH-4** — token `HttpOnly` cookie'ga ko'chdi.
      `HttpOnly; Secure; SameSite=Lax`; CSRF uchun `X-CSRF-Token`
      sarlavhasi va `HttpOnly` bo'lmagan cookie, qiymati **sessiyaga
      bog'langan** (`app_session.csrf_token`, `schema_patch_erp_9.sql` va
      `tender-ai/schema_patch_auth_3.sql`). `localStorage` da token
      YO'Q. Service kaliti tegilmadi — u alohida sarlavha va CSRF talab
      qilmaydi. Sinov: `erp6_test.py` 121, `auth_test.py` 102.
      Hujjat: `docs/erp_auth.md` 9-bo'lim.

- [x] **4.1. ISHGA TUSHIRISH** — `check_setup.py` (tayyorlik: baza,
      11 patch, kirish, rekvizitlar, tender-ai, cookie, demo) va
      `cleanup_demo.py` (belgi bo'yicha tozalash; sukut bo'yicha HECH
      NARSA o'chirilmaydi). Skriptning xavfsizligi sinovda qayd etilgan
      (`erp_test.py` 9-bo'lim). Yo'riqnoma:
      `docs/erp_ishga_tushirish.md`.

- [x] **4.2. DALOLATNOMA (akt)** — `schema_patch_erp_12.sql`.
      Faktura "qancha to'lash kerak", akt "bajarildi" deydi. Hisob-kitob
      FAKTURANIKI bilan bir xil kod; bank rekvizitlari yo'q; yakuniy
      holat `signed`. Fakturadan chiqariladi va qatorlar KO'CHIRILADI
      (bog'lanmaydi) — faktura bekor bo'lsa ham akt qoladi. Bosma shakli
      ham bor. Sinov: `erp9_test.py` 48 tekshiruv.
      Hujjat: `docs/erp_faktura.md` 7b-bo'lim.

- [x] **4.3. ZAXIRA NUSXASI** — `backup_erp.ps1` (faqat `erp` sxemasi,
      `pg_dump -Fc`, hajm tekshiruvi, eskilarini avtomatik olib tashlash)
      va `register_backup_task.ps1` (kuniga 02:00). Tiklash VAQTINCHALIK
      BAZAGA tiklab tekshirilgan: 21 jadval, 2 view, qator sonlari asl
      bilan bir xil. `backups/` — `.gitignore` da.
      Hujjat: `docs/erp_ishga_tushirish.md` 7b-bo'lim.

- [x] **4.4. SHARTNOMA ILOVASI** — `GET /erp/contracts/{id}/specification`
      va `ContractPrint.tsx`. QAROR (javob olindi): ERP shartnoma
      MATNINI yozmaydi, faqat ILOVANI chiqaradi. Ma'lumot uch manbadan,
      MUZLATILGANI ustun (faktura > rezerv > yo'q); manba shaklda
      yoziladi; shartnoma summasi bilan farq bo'lsa ogohlantiriladi.
      Sinov: `erp5_test.py` 7-bo'lim.
      Hujjat: `docs/erp_faktura.md` 7c-bo'lim.

- [x] **4.5. DEMO TOZALANDI va SINOVLAR MUSTAQILLASHTIRILDI.**
      `cleanup_demo.py --yes` bilan 13 ta belgili yozuv o'chirildi
      (oldin zaxira olindi). Tozalash sinov qamrovini **863 -> 582** ga
      tushirgani ANIQLANDI: sinovlar bazadagi demo ma'lumotga tayanib,
      bo'lmasa jimgina SKIP qilardi. `_tests/fixture.py` qo'shildi —
      kerakli ma'lumotni sinovning o'zi yaratadi va o'chiradi.
      Qamrov tiklandi (**761**), baza esa sinovdan keyin ham TOZA
      qoladi.

- [x] **4.6. BIZNING QQS HOLATIMIZ** — `schema_patch_erp_13.sql`.
      QQS ni SOTUVCHI hisoblaydi: endi stavka ikkala passportga qarab
      hal bo'ladi (`invoice.default_vat_rate`). `NULL` = hali
      so'ralmagan va u ESKI xatti-harakatni saqlaydi — patch o'zi hech
      narsani o'zgartirmaydi. Ikki stavka farq qilsa KICHIGI olinadi.
      Interfeys: **Kompaniya** ekranida. Sinov: `erp8_test.py`
      (113 tekshiruv). Hujjat: `docs/erp_faktura.md` 2-bo'lim.

- [x] **4.7. FOYDA** — `schema_patch_erp_14.sql` +
      `api/erp/profit.py` + `GET /erp/profit` (rahbar) va
      `GET /erp/opportunities/{id}/profit` (har kim o'z kartasi uchun).
      "Bu tenderdan qancha ishladik?" degan savolga javob: daromad
      (**QQS SIZ** — QQS davlatniki), tannarx va foyda.
      ASOSIY QAROR: tannarx `erp.stock_move.unit_cost` da harakat
      paytida **MUZLATILADI**. Katalogdagi narx keyin o'zgarsa, o'tgan
      foyda qayta yozilmaydi — sinov buni to'g'ridan-to'g'ri
      tekshiradi (katalog narxi 300 000 -> 999 999, tannarx
      o'zgarmadi). `NULL` tannarx nolga AYLANTIRILMAYDI: u
      "bilmaymiz" degani, nol esa "tekin keldi" — noma'lum chiqimlar
      sanaladi va hisob "to'liq emas" deb ochiq aytiladi.
      Interfeys: kartada `ProfitLine`, rahbar panelida `ProfitPanel`.
      Sinov: `erp8_test.py` 10-bo'lim (131 tekshiruv).
      Hujjat: `docs/erp_foyda.md`.

- [x] **4.8. PAROL TANLASHDAN HIMOYA (auth-5)** —
      `schema_patch_erp_15.sql` (`erp.login_attempt`),
      `auth.guard_attempts/record_attempt/attempts`,
      `GET /erp/auth/attempts` (admin) va **Hodimlar** ekranidagi
      ro'yxat. Kirish sahifasi shu paytgacha cheksiz urinishga ochiq
      edi: xesh kuchli, lekin urinishlar SONI cheklanmagan va hech
      qanday iz qolmasdi.
      ASOSIY QAROR: **hisob bloklanmaydi.** 5 xatodan keyin hisobni
      yopish direktorning loginini bilgan har kimga uni ishdan
      chiqarish imkonini berardi — himoya vositasi hujum vositasiga
      aylanardi. To'siq VAQTINCHA (15 daqiqa) va (login + IP)
      juftligiga tegadi; IP bo'yicha alohida chegara (25) login
      nomlarini aylantirib chiqishga qarshi. To'g'ri parol zanjirni
      UZADI. Tekshiruv paroldan OLDIN — to'silgan urinish qimmat
      xeshlashni ishga tushirmaydi. `X-Forwarded-For` ga ishonilmaydi.
      Javob: `429` + `Retry-After` + necha daqiqa kutish kerakligi.
      Sinov: `erp6_test.py` 8b-bo'lim (138 tekshiruv).
      Hujjat: `docs/erp_auth.md` 10-bo'lim.

- [x] **4.9. TENDER-AI KIRISHI HAM HIMOYALANDI (auth-5, ikkinchi
      tomon)** — `tender-ai/schema_patch_auth_4.sql`
      (`public.login_attempt`), `api/auth.py` da o'sha qatlam,
      `GET /auth/attempts`, `429` + `Retry-After`.
      Tender-AI — TASHQI eshik va ERP nikidan ochiqroq turardi.
      JADVAL ATAYLAB ALOHIDA: `erp.login_attempt` ni ishlatish chegara
      qoidasini buzardi (tender-ai `erp.*` ga yozmaydi) — sinov
      urinishdan keyin `erp.login_attempt` sonining o'zgarmaganini
      tekshiradi. Hisobni bloklamaslik qarori bu yerda yanada
      muhimroq: kompaniya hisobi BITTA, uni yopish butun kompaniyani
      tizimdan uzib qo'yardi.
      Interfeys uch tilli bo'lgani uchun 429 xabari MATNDAN emas,
      `Retry-After` SONIDAN yig'iladi (`auth.tooManyAttempts`,
      uz/ru/en). Sinov: `tender-ai/_tests/auth_test.py` 8-bo'lim
      (110 tekshiruv). Hujjat: `docs/erp_auth.md` 10.12,
      `INTEGRATSIYA.md` 12-bo'lim.

- [x] **4.10. PAROLNI XAVFSIZ ALMASHTIRISH (auth-6)** — ikkala
      tomonda. Uchta ochiq joy yopildi: (a) eski parol so'ralmasdi —
      ochiq qolgan kompyuter yoki o'g'irlangan sessiya bilan begona
      odam hisobni butunlay egallab olardi; (b) parolga hech qanday
      talab yo'q edi (`1` ham o'tardi); (c) almashtirish boshqa
      sessiyalarni yopmasdi, ya'ni "parolimni o'zgartirdim" degan
      harakat o'g'irlangan tokenni bekor qilmasdi.
      TALAB — UZUNLIK (10 belgi), murakkablik EMAS: "katta harf +
      raqam + belgi" qoidasi `Parol123!` ni keltirib chiqaradi va u
      monitorga yopishtiriladi (NIST 800-63B). Qoida MIJOZDA
      TAKRORLANMAYDI — faqat serverda.
      O'ZINIKI va BOSHQANIKI ataylab har xil: o'zinikida joriy parol
      majburiy va o'z sessiyasi qoladi; admin tiklaganda joriy parol
      so'ralmaydi (bu "unutdim" holati), lekin HAMMA sessiya yopiladi.
      Interfeys: ERP yon panelida "Parolni o'zgartirish" (har kim
      uchun — ilgari broker o'z parolini umuman o'zgartira olmasdi),
      tender-ai da yangi "Xavfsizlik" bo'limi (uz/ru/en).
      Yo'l-yo'lakay tender-ai da haqiqiy xato topildi: `keep_token`
      cookie'ni ustun qo'yardi, darvoza esa sarlavhani — parolni
      almashtirgan odam O'ZI tizimdan chiqib qolardi.
      Sinov: `erp6_test.py` 6d (154), `tender-ai/auth_test.py` 5g (123).
      Hujjat: `docs/erp_auth.md` 11-bo'lim.

- [x] **4.11. ARALASH VALYUTA QO'SHILMAYDI** — foyda hisoboti, rahbar
      paneli, tahlil va mijoz kartasi. Ilgari hamma karta bir qopga
      solib qo'shilardi va natija `UZS` deb yozilardi: bazada bitta
      USD karta paydo bo'lishi bilan bu son YOLG'ON bo'lardi va uni
      yolg'on ekanini hech narsa ko'rsatmasdi.
      QAROR: konvertatsiya YO'Q ("qaysi kungi kurs?" degan savolga
      javob yo'q). Bitta valyutada — odatdagidek umumiy yig'indi;
      aralashda — har valyuta ALOHIDA qator, umumiy yig'indi `null`,
      ekranda sabab yoziladi. Rahbar panelida summalar `null`, SANOQ
      esa qoladi (u valyutaga bog'liq emas).
      Sinov: `erp8_test.py` 10-bo'lim (142 tekshiruv).
      Hujjat: `docs/erp_foyda.md` 9-bo'lim.

- [x] **4.12. PROKSI ORQASIDA MANZIL** — `TRUST_PROXY` bayrog'i,
      ikkala loyihada. Muammo: nginx/IIS ortida `request.client` har
      doim proksining o'zini ko'rsatadi, ya'ni parol himoyasining IP
      kesimi ishlamaydi. `X-Forwarded-For` ga so'zsiz ishonish esa
      cheklovni bir qator matn bilan chetlab o'tishga yo'l ochardi.
      YECHIM — KOD EMAS, SOZLAMA: `TRUST_PROXY=1`, default O'CHIQ.
      Yoqilganda sarlavhaning OXIRGI qiymati olinadi (uni ishonchli
      proksi qo'yadi; boshidagilarni mijoz o'zi yozishi mumkin).
      Sinov: `erp6_test.py` — o'chiqda soxta manzil yozilmaydi,
      yoqilganda oxirgisi olinadi, boshidagisi olinmaydi (158).
      Hujjat: `docs/erp_auth.md` 10.7, `docs/erp_ishga_tushirish.md`.

- [x] **4.13. PUL HUJJATLARI O'ZGARISHLAR JURNALI** —
      `schema_patch_erp_16.sql` (`erp.doc_audit` + triggerlar),
      `api/erp/audit.py` (FAQAT O'QIYDI), `GET /erp/audit` va
      `GET /erp/audit/{doc_type}/{doc_id}` (rahbar), rahbar panelida
      `AuditPanel`.
      SABAB: "faktura `issued` dan keyin o'zgarmaydi" degan qoida kodda
      ham, sinovda ham bor edi — lekin ikkalasi ham FAQAT ilova orqali
      o'tgan o'zgarishlarni ushlardi. Ya'ni tekshiruv bor, DALIL yo'q
      edi.
      QAROR: yozuvchi — TRIGGER, ilova kodi emas. Ilova qatlamidagi
      jurnal "men hech narsa o'zgartirmadim" degan gapning o'zi aytgan
      dalili bo'lardi. Sinov ham ataylab to'g'ridan-to'g'ri SQL yozadi.
      `doc_status` — o'zgarish paytidagi holat; hujjatning o'zi
      o'zgarganda ESKI holat yoziladi, aks holda "chiqarildi"
      o'tishning o'zi shubhali bo'lib ko'rinardi.
      `actor` `SET LOCAL erp.actor` orqali keladi; `NULL` = ERP dan
      TASHQARIDA. Jurnal `UPDATE` qilinmaydi, `DELETE` faqat
      `erp.audit_purge = on` bilan. FK ataylab yo'q — hujjat
      o'chirilsa ham tarix qoladi.
      Sinov: `_tests/erp10_test.py` (35 tekshiruv).
      Hujjat: `docs/erp_audit.md`.

- [x] **4.14. MA'LUMOT KIRITISH TARTIBI** — `check_setup.py` 9-bo'limi
      besh qadamni tekshiradi (kompaniya passporti → hodimlar va
      hisoblar → mijoz passportlari → ombor qoldig'i → tannarx) va
      BIRINCHI to'ldirilmaganini alohida ko'rsatadi: "nimadan
      boshlayman?" degan savolga javob bitta bo'lsin. Hammasi
      to'ldirilgach shunday deb yoziladi — "tekshirdimmi?" degan savol
      ham ochiq qolmaydi.
      Yo'l-yo'lakay: faktura eksporti uchun buxgalterga yuboriladigan
      uchta savol tayyor matn qilib yozildi
      (`docs/eksport_savollari.md`) — 3-savol IKPU/MXIK kodi haqida va
      javobi "ha" bo'lsa ish hajmi kattalashadi (katalogga ustun).
      Hujjat: `docs/erp_ishga_tushirish.md` "Birinchi kun".

- [x] **4.15. ISHLAB CHIQARISHGA TAYYORGARLIK (1-bosqich)** —
      `git init` + GitHub (`ibragimoffline/tendererp`), `.gitattributes`
      (loyihaning qator oxirlari kelishuvi muzlatildi);
      `run_erp.ps1 -Prod` — frontend QURILADI va uni backendning o'zi
      uzatadi (bitta jarayon, bitta port; Vite dev serveri ishlab
      chiqarishda ko'tarilmaydi); `-BindHost` bilan tarmoqqa ochiladi;
      `/api` prefiksini server kesadi — BITTA build ikkala rejimda
      ishlaydi; `logs/erp.log` (aylanma) — ilgari xato yashirin oynada
      yo'qolardi; ikkala jadval vazifasi ro'yxatdan o'tkazildi
      (`TenderERP-Backup`, `TenderERP-Reminders`) — ular
      QO'YILMAGAN edi, ya'ni zaxira va eslatmalar umuman ishlamasdi.
      `check_setup.py` ning KO'R NUQTASI yopildi: u zaxira fayllarini
      sanab "sog'lom" ko'rsatardi, avtomatika yoqilganini esa
      tekshirmasdi. Hujjat: `docs/erp_ishga_tushirish.md`.

**Uch savolga javob olindi** — `erp_arxitektura_3.md` 6-bo'lim.

---

## Meros muammolar (tender-ai tomonida)  ✅ BAJARILDI

- [x] **M1. `_tests/compliance_test.py` — 6 xato.** Ikki sabab edi:
      (a) `_days_left()` berilgan `today` ni e'tiborsiz qoldirib, har doim
      haqiqiy bugundan hisoblardi — natijada bitta javob ichida `status`
      bir sanaga, `days_left` boshqasiga qarardi. Endi `today` uzatiladi
      (`shape_document()` ham). (b) Baza fixture'i qotirilgan `TODAY`
      (2026-07-28) dan siljitilgan sanalar yozardi va o'sha kundan keyin
      o'z-o'zidan yiqila boshlagan; endi HAQIQIY bugundan siljitiladi.
      Natija: **119/0** (avval 113/6).
- [x] **M2. `_tests/pricing_test.py` — 1 xato.** Sabab TypeScript EMAS
      edi (Node 24 tur izohlarini o'zi olib tashlaydi): `calculate(inp, t)`
      i18n migratsiyasida ikkinchi parametr olgan, harness esa bittasini
      uzatardi. Harness endi `locales/uz.ts` lug'atidan `t` yasaydi.
      Shundan keyin sinov O'Z ISHINI qildi va HAQIQIY drift topdi: Python
      matnlarida oddiy `'`, lug'atda tipografik `‘`. Foydalanuvchi
      brauzerdagi (lug'atdagi) matnni ko'rgani uchun `api/pricing.py`
      moslandi — 79 ta apostrof (asosan izohlarda).
      Natija: **26/26** (avval 25/26).
- [x] **M3. `run_all.ps1` — noto'g'ri xato.** `$LASTEXITCODE` skriptning
      emas, uning ichidagi oxirgi TASHQI buyruqning natijasini saqlaydi.
      Endi `run_api.ps1` muvaffaqiyatda aniq `exit 0` qaytaradi, `run_all.ps1`
      esa `/health` ga so'rov yuborib TEKSHIRADI. Yo'l-yo'lakay: `run_api.ps1`
      izohidagi kirill qoldig'i ASCII ga keltirildi (fayl sarlavhasi
      "ATAYIN faqat ASCII" deb yozib qo'yilgan, PowerShell 5.1 shuni talab
      qiladi).

**Tuzatilmagan (bizga bog'liq emas):** `_tests/etl_coverage_test.py` —
manba API'siga (`api.xt-xarid.uz`) real so'rov yuboradi va u 400/timeout
qaytaryapti. Kod muammosi emas.

---

## Ish tartibi (tavsiya)

**Rejalashtirilgan hamma ish bajarildi.** Qolgani — tashqi javob
kutayotgan yoki yangi qaror talab qiladigan ishlar; ular
`docs/README.md` dagi "Nima ataylab yo'q" bilan bir qatorda turadi.

1. ~~0-ish~~, ~~1-ish~~, ~~2-ish~~, ~~M1/M2/M3~~, ~~3.x~~, ~~4.x~~ — bajarildi.
2. **Faktura eksporti** — mijozdan format javobi kelgach
   (`api/erp/invoice_export.py` tayyor turibdi). Bu — tashqi javob
   kutayotgan YAGONA ish. Savol hali YUBORILMAGAN; yuborish uchun
   tayyor matn: `docs/eksport_savollari.md`.
2b. ~~Tender-AI kirishini ham himoyalash~~ — **BAJARILDI** (4.9).
3. **Birinchi real ma'lumot** — tartib bilan: kompaniya passporti
   (QQS) → hodimlar va hisoblar → mijoz passportlari → ombor
   boshlang'ich qoldig'i → katalogda tannarx. Tizim o'zi tekshiradi va
   keyingi qadamni aytadi: `check_setup.py` 9-bo'lim; tavsif
   `docs/erp_ishga_tushirish.md` "Birinchi kun".

**Yetkazib berish jadvali — QAROR qilindi (ataylab yo'q).** MVP uchun
akt (qabul qilindi) va ombor chiqimi (ketdi) yetarli. "Qachon /
qayerga / kim olib boradi" — logistika savoli va u keyingi bosqichga.
Keyin qilinsa: `erp.delivery` **aktga bog'lanadi**, akt esa
yetkazishning tasdig'i bo'lib qoladi (`docs/erp_faktura.md` 7d).

Hujjatlar xaritasi: `docs/README.md` — qaysi qaror qaysi hujjatda
yozilgani shu yerda.

Har ish oxirida: `erp*_test.py` -> `npm run build` -> hujjat yangilanadi.
(`sync.ps1` endi yo'q — ajratishdan keyin kod bitta joyda yashaydi.) Bosqich yakunlanmaguncha keyingisi boshlanmaydi
(`erp_bosqichlar.md` kelishuvi).
