# HUJJATLAR XARITASI

Bu papkada 18 ta hujjat bosqichma-bosqich yozilgan: har biri o'z paytida qabul
qilingan qarorni va **nega shunday qilingani** saqlaydi. Bu fayl — ularga
kirish: nima qayerda va qaysi savolga javob qayerdan topiladi.

---

## Qayerdan boshlash

| Siz kim | Tartib |
|---|---|
| **Tizimni ishga tushirmoqchisiz** | `erp_ishga_tushirish.md` → `../README.md` |
| **Ma'lumot kiritmoqchisiz (egasi)** | `erp_ishga_tushirish.md` "Birinchi kun" → `check_setup.py` 9-bo'lim |
| **Kodga yangi kelgan dasturchi** | `erp_arxitektura_2.md` (ajratish va chegara) → `erp_texnik.md` → o'zingizga kerakli modul hujjati |
| **"Nega shunday qilingan?" degan savol bilan** | quyidagi **Qarorlar indeksi** |
| **Loyihaning holatini bilmoqchisiz** | `../REJA.md` (bajarilgan/qolgan ishlar) |

---

## Hujjatlar

### Poydevor

| Fayl | Nima haqida |
|---|---|
| `erp_texnik.md` | Boshlang'ich texnik topshiriq: ERP nima uchun kerak |
| `erp_bosqichlar.md` | Ishning bosqichlarga bo'linishi va kelishuv: bosqich yakunlanmaguncha keyingisi boshlanmaydi |
| `erp_arxitektura.md` | Birinchi arxitektura: `erp` sxemasi, snapshot, `public.*` ga yozmaslik qoidasi |
| `erp_arxitektura_2.md` | **AJRATISH**: ERP alohida loyihaga chiqarildi. Chegara qoidasi va uch integratsiya nuqtasi |
| `erp_arxitektura_3.md` | 5-bosqich qarori: 5A/5B ga bo'lish, uch savol va ularga olingan javoblar |

### Integratsiya

| Fayl | Nima haqida |
|---|---|
| `erp_integratsiya.md` … `_5.md` | Tender-AI bilan bog'lanishning bosqichma-bosqich tarixi: cheklist, hujjat shabloni, vazifalar, xabar yuborish, kompaniya profili |
| `../INTEGRATSIYA.md` | Tender-AI tomonida **nima o'zgargani** — o'sha loyihaga o'tkaziladigan ro'yxat |

### Modullar

| Fayl | Nima haqida |
|---|---|
| `erp_auth.md` | Kimlik: kim qayerda (hodim ERP da, kompaniya tender-ai da), rollar, cookie/CSRF, service kaliti, **parol tanlashdan himoya** |
| `erp_ombor.md` | Ombor: harakatlar jurnali, qoldiq, **rezerv**, tender pozitsiyalaridan taklif |
| `erp_faktura.md` | Hisob-faktura, to'lovlar, **dalolatnoma (akt)**, shartnoma ilovasi, bosma shakl |
| `erp_foyda.md` | Foyda: daromad (QQS siz), **muzlatilgan tannarx**, to'liq bo'lmagan hisob |
| `erp_audit.md` | O'zgarishlar jurnali: **trigger** yozadi, "chiqarilgandan keyin tegilganmi" |
| `eksport_savollari.md` | Faktura eksporti uchun buxgalterga **yuboriladigan savollar** (tayyor matn) |
| `erp_ishga_tushirish.md` | Bo'sh bazadan real ishgacha: patchlar, hisoblar, tayyorlik tekshiruvi, demo tozalash, **zaxira** |

---

## QARORLAR INDEKSI

Eng ko'p beriladigan savollar va javob qayerda yozilgani.

### Arxitektura

| Savol | Javob | Qayerda |
|---|---|---|
| Nega ERP alohida loyiha? | Ikki mahsulot, ikki auditoriya, ikki tezlik | `erp_arxitektura_2.md` 1 |
| Nega baza bitta? | Snapshot uchun HTTP kerak bo'lmasin; chegara esa saqlanadi | `erp_arxitektura_2.md` 2 |
| ERP `public.*` ga yozadimi? | **Yo'q.** Har sinovda tekshiriladi | `erp_arxitektura_2.md` 2 |
| Tender-AI `erp.*` ga yozadimi? | **Yo'q** — faqat ikki VIEW ni o'qiydi | `erp_arxitektura_2.md` 2, `erp_auth.md` 8.4 |
| Nega snapshot (tender, rekvizitlar, taklif)? | Hujjat chiqarilgandan keyin manba o'zgarsa, hujjat o'zgarmasligi kerak | `erp_arxitektura.md`, `erp_faktura.md` 3.3 |

### Kimlik

| Savol | Javob | Qayerda |
|---|---|---|
| Hodim qayerda, kompaniya qayerda? | Hodim — ERP da (`erp.app_user`), kompaniya — tender-ai da | `erp_auth.md` 1 |
| Nega auth-1 qayta qilindi? | Kimlik teskari tomonda edi: odam ERP ning tushunchasi | `erp_auth.md` 1 |
| Token qayerda saqlanadi? | `HttpOnly` cookie'da; `localStorage` da EMAS | `erp_auth.md` 9 |
| CSRF qanday yopilgan? | `SameSite=Lax` + `X-CSRF-Token`, qiymati **sessiyaga bog'langan** | `erp_auth.md` 9.2–9.3 |
| ERP tender-ai ga qanday kiradi? | `X-Service-Key` — faqat 7 endpointni ochadi | `erp_auth.md` 8.2 |
| Parolni tanlashga urinish cheklanganmi? | Ha: 5 xato / 15 daqiqa, (login + IP) bo'yicha | `erp_auth.md` 10.4 |
| Nega HISOB bloklanmaydi? | Loginni bilgan har kim hodimni ishdan chiqarib qo'ya olardi | `erp_auth.md` 10.3 |
| Xato urinishlar qayerda ko'rinadi? | **Hodimlar** ekranida; `GET /erp/auth/attempts` (admin) | `erp_auth.md` 10.9 |
| `X-Forwarded-For` ishlatiladimi? | Faqat `TRUST_PROXY=1` bo'lganda, **oxirgi** qiymati | `erp_auth.md` 10.7 |
| Parolga qanday talab bor? | **Uzunlik** (10), murakkablik EMAS | `erp_auth.md` 11.2 |
| Parol almashtirishda eski parol kerakmi? | O'ZINIKIDA **ha**; admin tiklashida yo'q | `erp_auth.md` 11.3 |
| Parol almashsa sessiyalar nima bo'ladi? | Boshqalari o'chadi; admin tiklasa — hammasi | `erp_auth.md` 11.3 |

### Pul va hujjatlar

| Savol | Javob | Qayerda |
|---|---|---|
| QQS stavkasi qayerdan? | Mijoz passportidan; qatorga **nusxa** ko'chiriladi | `erp_faktura.md` 2, 3.1 |
| `vat_payer = NULL` nima degani? | "Hali so'ralmagan" — `false` bilan bir xil EMAS | `erp_faktura.md` 2 |
| Summalar qayerda saqlanadi? | **Hech qayerda** — qatorlardan hisoblanadi | `erp_faktura.md` 3.2 |
| Faktura eksporti qani? | ATAYLAB bo'sh: format mijozdan so'raladi | `erp_faktura.md` 1, 8 |
| Buxgalterdan nima so'raladi? | Uchta savol, tayyor matn bilan | `eksport_savollari.md` |
| Ma'lumotni qaysi tartibda kiritaman? | Passport → hodimlar → mijozlar → ombor → tannarx | `erp_ishga_tushirish.md` "Birinchi kun" |
| Ishlab chiqarishda qanday ko'tariladi? | `run_erp.ps1 -Prod` — interfeysni BACKEND uzatadi | `erp_ishga_tushirish.md` "Ishlab chiqarishga qo'yish" |
| Nega nginx yo'q? | Ichki ERP uchun yana bitta xizmat foydasidan ko'p ish | o'sha yerda |
| Interfeys to'g'ri qurilganini kim tekshiradi? | `check_build.py` — `-Prod` uni o'zi yurgizadi | `erp_ishga_tushirish.md` "Build o'tdi" |
| Nega ESLint yo'q? | `typescript-eslint` TS 7 ni rad etadi — vaqtincha holat | o'sha yerda |
| Interfeys qoidalarini kim tekshiradi? | `npm test` — 12 sinov, QARORLAR bo'yicha | `erp_ishga_tushirish.md` "Interfeys sinovi" |
| Nega ranglar sinovda yo'q? | Har dizayn tuzatishida yiqilib, to'sqinlik qilardi | o'sha yerda |
| Tarmoqqa ochsam nega kirish ishlamaydi? | `AUTH_COOKIE_SECURE=1` + HTTPS yo'q | o'sha yerda |
| Bosma shakl yuridik hujjatmi? | **Yo'q** va bu shaklning o'zida yozilgan | `erp_faktura.md` 6c |
| Shartnoma matni ERP da bormi? | **Yo'q** — ERP faqat ILOVANI (spetsifikatsiya) chiqaradi | `erp_faktura.md` 7c |
| Akt nimasi bilan fakturadan farq qiladi? | "Bajarildi" deydi; bank rekvizitlari yo'q; yakuniy holat `signed` | `erp_faktura.md` 7b |
| Faktura o'zgarmagani qayerdan ma'lum? | `erp.doc_audit` — **trigger** yozadi, ilova emas | `erp_audit.md` 2 |
| Qo'lda yozilgan SQL ham ushlanadimi? | **Ha** — audit qatlamining butun sababi shu | `erp_audit.md` 2 |
| Jurnalni o'chirib bo'ladimi? | `UPDATE` — yo'q; `DELETE` — faqat `erp.audit_purge = on` | `erp_audit.md` 6 |
| `actor` bo'sh bo'lsa nima degani? | "ERP dan **tashqarida** o'zgartirilgan" | `erp_audit.md` 3 |
| "Qachon / qayerga / kim olib boradi" qayerda? | **Hech qayerda** — bu QAROR, keyingi bosqichga | `erp_faktura.md` 7d |

### Ombor

| Savol | Javob | Qayerda |
|---|---|---|
| Qoldiqning egasi kim? | **ERP** ("A1" yo'li) | `erp_ombor.md` 2 |
| Nega jurnal, "qoldiq" ustuni emas? | Qoldiq — hisob natijasi; ustun bo'lsa "nega shuncha?" degan savolga javob yo'q | `erp_ombor.md` 3 |
| Manfiy qoldiq taqiqlanadimi? | **Yo'q**, ogohlantiriladi — hujjat kechikishi normal hol | `erp_ombor.md` 5 |
| Rezerv qoldiqni kamaytiradimi? | Yo'q — **mavjud** miqdorni kamaytiradi | `erp_ombor.md` 9.1 |
| Rezerv qachon yopiladi? | Kartaning statusiga qarab, avtomatik | `erp_ombor.md` 9.2 |
| Taklif avtomatik yoziladimi? | **Yo'q** — moslashuv nom bo'yicha, tasdiqni odam beradi | `erp_ombor.md` 9.5 |

### Foyda

| Savol | Javob | Qayerda |
|---|---|---|
| QQS daromadmi? | **Yo'q** — u davlatniki, alohida ko'rsatiladi | `erp_foyda.md` 2 |
| Tannarx qaysi narxdan? | Harakat paytida **muzlatilgan** narxdan, joriy katalogdan emas | `erp_foyda.md` 3 |
| Katalog narxi o'zgarsa o'tgan foyda o'zgaradimi? | **Yo'q**, va buni sinov tekshiradi | `erp_foyda.md` 3 |
| Tannarx noma'lum bo'lsa? | Nolga aylantirilmaydi — sanaladi va "to'liq emas" deb aytiladi | `erp_foyda.md` 4 |
| Daromad qachon tan olinadi? | Faktura **chiqarilganda**, pul kelganda emas | `erp_foyda.md` 5 |
| Nega foiz `—` ko'rinadi? | Daromad nol — "0% foyda" degan yolg'on bo'lmasin | `erp_foyda.md` 6 |
| Foydani kim ko'radi? | Umumiy hisobotni rahbar; o'z kartasinikini har kim | `erp_foyda.md` 7 |
| Turli valyutadagi summalar qo'shiladimi? | **Yo'q** — har valyuta alohida qator, umumiy yig'indi yo'q | `erp_foyda.md` 9 |
| Nega kurs bo'yicha konvertatsiya yo'q? | "Qaysi kungi kurs?" degan savolga javob yo'q — hisobot har kuni o'zgarardi | `erp_foyda.md` 9.2 |

---

## KOD XARITASI

```
api/
  main.py            barcha endpointlar (95 marshrut), kimlik darvozasi
  auth.py            HODIM kimligi: parol, sessiya, rollar, cookie/CSRF,
                     kirish urinishlari jurnali va cheklovi
  db.py              pool va query yordamchilari
  tenderai.py        TENDER-AI GA YAGONA KO'PRIK (service kaliti shu yerda)
  erp/
    opportunity.py   ish kartalari, statuslar, snapshot, tarix
    clients.py       mijoz passporti, aloqalar, hujjatlar, QQS
    tasks.py         vazifalar, "mening ishlarim"
    remind.py        eslatma skripti (jadval bo'yicha)
    submission.py    taklif paketi (muzlatilgan versiyalar)
    contracts.py     shartnoma + bizning rekvizitlar + ILOVA
    stock.py         ombor: jurnal, qoldiq, rezerv, taklif
    invoice.py       hisob-faktura, to'lovlar, summa so'z bilan
    invoice_export.py  eksport — ATAYLAB BO'SH QATLAM
    act.py           dalolatnoma (hisob fakturanikidan)
    staff.py         hodimlar + ularning hisoblari (admin)
    profit.py        FOYDA: daromad - muzlatilgan tannarx
    audit.py         o'zgarishlar jurnali (FAQAT O'QIYDI — trigger yozadi)
    stats.py         rahbar hisoboti
    analytics.py     bosqich vaqtlari, voronka, qotib qolganlar
```

**Bir qoida butun kod bo'ylab:** hisob natijasi saqlanmaydi. Ombor
qoldig'i ham, faktura summasi ham har safar qayta hisoblanadi. Sabab
bitta: ikki manba vaqt o'tib ajralib ketadi.

---

## SINOVLAR

```
_tests/
  fixture.py     sinov O'Z ma'lumotini yaratadi (bazaga tayanmaydi)
  erp_test.py    1-bosqich, diff, tozalash skriptining xavfsizligi — 123
  erp2_test.py   mijoz passporti va import — 79
  erp3_test.py   vazifalar — 58
  erp4_test.py   takliflar — 45
  erp5_test.py   shartnoma, rekvizitlar, ILOVA — 80
  erp6_test.py   AUTH, hodimlar, cookie/CSRF, PAROL HIMOYASI — 158
  erp7_test.py   ombor, rezerv, taklif — 102
  erp8_test.py   faktura, to'lov, zanjir, FOYDA, VALYUTA — 142
  erp9_test.py   dalolatnoma — 48
  erp10_test.py  O'ZGARISHLAR JURNALI (audit) — 35
```

Jami **871 tekshiruv**. Har suite oxirida ikki narsa tekshiriladi:
**chegara** (`public.*` tegilmadimi) va **tozalik** (sinov o'z
yozuvlarini o'chirdimi).

Sinovlar bo'sh bazada ham to'liq yuradi.

---

## NIMA ATAYLAB YO'Q

| Nima | Nega |
|---|---|
| **Yetkazib berish jadvali** | MVP uchun akt + ombor chiqimi yetadi — `erp_faktura.md` 7d |
| Faktura/akt **eksporti** | format mijozning buxgalteri tizimiga bog'liq |
| Shartnoma **matni** | huquqiy matn — yurist ishi |
| **Ko'p kompaniya** (multi-tenant) | bitta kompaniya rejimi |
| **Ombor bo'limlari, partiyalar** | bitta ombor taxmin qilingan |
| **FIFO / partiyalar bo'yicha tannarx** | tannarx harakat paytida muzlatiladi — sodda model, `erp_foyda.md` 8 |
| **Bilvosita xarajatlar** (transport, ish haqi) | foyda YALPI: daromad − tovar tannarxi. Sof foyda buxgalteriyada |
| Zaxirani **bulutga yuborish** | saqlash tizimingizga bog'liq |
| ERP interfeysida **ko'p til** | ichki vosita, bitta til yetarli |

Bu ro'yxat qisqarishi mumkin — lekin har biri **qaror**, unutilgan ish
emas.
