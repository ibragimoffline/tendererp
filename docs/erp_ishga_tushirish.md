# ISHGA TUSHIRISH — bo'sh bazadan real ishgacha

Bu hujjat bitta savolga javob beradi: **yangi joyda ERP ni qanday
ishga tushirish kerak va real ishga o'tishdan oldin nima tekshiriladi.**

Bosqichlar tartibi muhim: har biri o'zidan oldingisiga tayanadi.

---

## 0. Talablar

- PostgreSQL (tender-ai bilan **bitta baza**, `erp` sxemasi alohida);
- Python 3.11+ va Node 20+ (interfeys uchun);
- ishlab turgan **tender-ai** — majburiy emas, lekin usiz cheklist,
  hujjat shabloni va yangi karta olish ishlamaydi.

---

## 1. Sozlamalar

```powershell
cd 'D:\MVP projects\tender erp'
copy .env.example .env
```

`.env` da to'ldiriladigan uch narsa:

| Kalit | Nima |
|---|---|
| `XT_DB_DSN` | baza manzili (tender-ai bilan bir xil) |
| `ERP_SERVICE_KEY` | ERP ↔ tender-ai kaliti — **ikkala loyihada bir xil** |
| `TENDER_AI_API` / `TENDER_AI_WEB` | tender-ai manzillari |

Kalit yaratish:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Uni **`tender-ai/.env`** ga ham o'sha qiymat bilan yozing — aks holda
ERP tender-ai ga kira olmaydi (403).

---

## 2. Sxema patchlari

Tartib bilan, bittadan:

```powershell
$dsn = "dbname=xtxarid user=postgres host=localhost"
1..13 | ForEach-Object { psql $dsn -f "schema_patch_erp_$_.sql" }
```

| Patch | Nima beradi |
|---|---|
| 1 | ish kartalari, hodimlar, mijoz lug'ati, tarix |
| 2 | mijoz passporti, aloqalar, hujjatlar |
| 3 | vazifalar va eslatmalar |
| 4 | takliflar (muzlatilgan versiyalar) |
| 5 | shartnomalar + bizning rekvizitlar |
| 6 | **hodim hisoblari** (kirish) |
| 7 | tender-ai uchun shartnoma-view |
| 8 | ombor: harakatlar jurnali va qoldiq |
| 9 | cookie/CSRF (auth-4) |
| 10 | rezerv: ajratilgan tovar |
| 11 | hisob-faktura, qatorlar, to'lovlar |
| 12 | dalolatnoma (akt) |
| 13 | bizning QQS holatimiz |

Hammasi **idempotent** — ikki marta ishlatsa ham xavfsiz.

**TENDER-AI tomonida** ham ikki patch bor va ular ERP nikidan **KEYIN**
qo'llanadi:

```powershell
cd 'D:\MVP projects\tender-ai'
psql $dsn -f schema_patch_auth_2.sql    # kompaniya hisobi
psql $dsn -f schema_patch_auth_3.sql    # cookie/CSRF
```

Tartib sababi: `auth_2` eski hodim jadvallarini olib tashlaydi, lekin
**faqat** ular ERP ga ko'chirilgan bo'lsa (`erp_6`). Aks holda
ogohlantirish beradi va hech narsaga tegmaydi.

---

## 3. Birinchi hisoblar

```powershell
# ERP — HODIM (odam)
cd 'D:\MVP projects\tender erp'
.\.venv\Scripts\python.exe create_user.py admin "Bosh administrator" --role admin

# Tender-AI — KOMPANIYA
cd 'D:\MVP projects\tender-ai'
.\.venv\Scripts\python.exe create_company.py alfa "Alfa Savdo MChJ"
```

Ikkalasi ikki xil tushuncha: hodim ERP niki, kompaniya tender-ai niki
(`erp_auth.md` 1-bo'lim).

Interfeysdan yaratib bo'lmaydi va bu ataylab: "birinchi foydalanuvchi"
endpointi — ochiq eshik.

---

## 4. Ishga tushirish

```powershell
cd 'D:\MVP projects\tender erp'
.\run_erp.ps1            # backend :8100 + interfeys :5174
```

Tender-AI alohida: `tender-ai\run_all.ps1 -NoTunnel` (:8000 va :5173).

---

## 5. TAYYORLIK TEKSHIRUVI

```powershell
.\.venv\Scripts\python.exe check_setup.py
```

Sakkiz bo'limni bir joyda ko'rsatadi: baza, patchlar, kirish, bizning
rekvizitlar, tender-ai bilan bog'lanish, cookie sozlamasi, demo
ma'lumot va **zaxira nusxasi** (oxirgisi qachon olingani).

Chiqish kodi: `0` — ishlaydi, `1` — kamida bitta **xato** bor.

Nega kerak: 13 patch, ikki `.env`, ikki backend va umumiy kalit —
birortasi qo'llanmagan bo'lsa xato **keyin** chiqadi va odam interfeysda
"503" ni ko'rib sababini qidiradi.

---

## 6. Demo ma'lumotni tozalash

Ishlab chiqish davomida bazaga demo kartalar va sinov yozuvlari yig'iladi.
Real ishga o'tishdan oldin:

```powershell
.\.venv\Scripts\python.exe cleanup_demo.py          # FAQAT KO'RSATADI
.\.venv\Scripts\python.exe cleanup_demo.py --yes    # o'chiradi
```

**Ikki qoida:**

1. **Sukut bo'yicha hech narsa o'chirilmaydi.** `--yes` berilmasa faqat
   ro'yxat chiqadi. O'chirish qaytarib bo'lmaydigan amal.
2. **Faqat belgili yozuvlar.** `DEMO`, `ZZTEST`, `ZZSMOKE` prefikslari.
   Belgisi yo'q yozuv tegilmaydi — bu "hammasini tozalash" vositasi
   emas.

Skript **faqat `erp` sxemasiga** tegadi. Tender-AI katalogidagi demo
mahsulot bo'lsa, u haqda ogohlantiradi, lekin o'chirmaydi: `public.*` —
tender-ai niki (`erp_arxitektura_2.md` chegara qoidasi).

Skriptning xavfsizligi **sinovda qayd etilgan** (`erp_test.py`
9-bo'lim): sanash so'rovlari haqiqiy SQL ekani, ular hech narsani
o'zgartirmasligi va `public.*` ga tegilmasligi.

**Tozalashdan oldin zaxira oling** (7b-bo'lim). O'chirilgan yozuvni
faqat zaxiradan qaytarish mumkin.

Tozalashdan keyin **sinovlar baribir to'liq yuradi**: ular kerakli
ma'lumotni o'zi yaratadi (`_tests/fixture.py`) va oxirida o'chiradi.
Faqat tender-ai ning `auth_test.py` dagi 7 tekshiruv o'tkazib
yuboriladi — ular ERP da karta bo'lishini talab qiladi, tender-ai esa
`erp.*` ga yozmaydi (chegara qoidasi).

---

## 7. Birinchi ish uchun tartib

Tekshiruv o'tgach, interfeysda quyidagi tartib eng qisqa yo'l:

1. **Kompaniya** → bizning rekvizitlar (shartnoma va faktura shundan
   oladi);
2. **Hodimlar** → hodimlarni kiritish va ularga hisob ochish;
3. **Kompaniya** ekranida "Biz QQS to'lovchimizmi" — faktura stavkasi
   ikkala tomonga qarab hal bo'ladi;
4. **Mijoz korxonalar** → passport, shu jumladan **QQS holati**;
5. **Ombor** → "Import qoldiqlarini ko'chirish" yoki boshlang'ich
   qoldiqni qo'lda kiritish;
6. Tender-AI da tenderni topib **"ERP da ishga olish"**.

---

## 7b. ZAXIRA NUSXASI

```powershell
.ackup_erp.ps1                 # zaxira olish
.ackup_erp.ps1 -DryRun         # nima bo'lishini ko'rsatadi
.
egister_backup_task.ps1       # har kuni 02:00 da avtomatik
```

**Faqat `erp` sxemasi.** `public.*` — tender-ai niki va uning zaxirasi
o'sha loyihaning ishi. Ikkalasini bitta faylga solsak, ERP ni tiklash
uchun tender-ai ni ham tiklashga majbur bo'lardik.

**ERP mustaqil tiklanadi:** `erp.opportunity` tenderga faqat RAQAM bilan
bog'langan (FK yo'q, ma'lumot snapshot ichida) — ya'ni bu nusxa o'zi
yetarli. Tender-AI bo'lmasa cheklist va yangi karta olish ishlamaydi,
xolos.

Format — `pg_dump -Fc` (custom): siqilgan va `pg_restore` bilan **tanlab**
tiklash mumkin (bitta jadval, faqat ma'lumot va h.k.).

### Nima tekshiriladi

Skript zaxira olgach **fayl hajmini tekshiradi**: 1 KB dan kichik bo'lsa
xato deb hisoblanadi va `exit 1` qaytaradi. "Zaxira olindi" deb yozib
qo'yib, aslida bo'sh fayl qoldirish eng yomon holat — nosozlik faqat
tiklash paytida ma'lum bo'lardi.

Eski nusxalar avtomatik olib tashlanadi (`-Keep`, sukut 14 ta).

### Tiklash

```powershell
pg_restore -d xtxarid --clean --if-exists -n erp fayl.dump
```

**DIQQAT:** `--clean` mavjud `erp` sxemasini **o'chirib** tiklaydi. Avval
hozirgi holatning nusxasini oling.

Tiklash **tekshirilgan**: zaxira vaqtinchalik bazaga tiklanib, 21 jadval,
2 view va barcha qator sonlari asl baza bilan solishtirilgan. Tiklab
bo'lmaydigan zaxira — zaxira emas.

### Bitta disk yetarli emas

Zaxira **boshqa diskka yoki bulutga** nusxalanishi kerak. Bitta disk
ishdan chiqsa, undagi zaxira ham ketadi. Buni skript qilmaydi — u
sizning saqlash tizimingizga bog'liq.

`backups/` papkasi `.gitignore` da: zaxira — ma'lumot, kod emas.

---

## 8. Nima YO'Q (ataylab)

- **Faktura eksporti** — format mijozdan so'raladi
  (`erp_faktura.md` 1-bo'lim);
- **Zaxirani bulutga yuborish** — 7b-bo'limga qarang: nusxa olinadi,
  lekin uni ikkinchi joyga ko'chirish saqlash tizimingizga bog'liq;
- **Ko'p kompaniya (multi-tenant)** — bitta kompaniya rejimi.

---

## Proksi ortiga qo'yilsa

Bitta satr: `.env` ga **`TRUST_PROXY=1`**.

Usiz nginx/IIS ortida hamma so'rov bitta manzildan kelayotgandek
ko'rinadi va parol tanlashdan himoyaning IP kesimi ishlamaydi
(`erp_auth.md` 10.7). To'g'ridan-to'g'ri ochiq turgan serverda esa uni
**yoqmang**: o'shanda mijoz `X-Forwarded-For` ni o'zi yozib, cheklovni
chetlab o'tadi.

Ikkala loyihada ham bir xil (`tender erp` va `tender-ai`).

---

## BIRINCHI KUN — ma'lumot kiritish tartibi

Kod tayyor, lekin **ma'lumotsiz sinab bo'lmaydi**: bo'sh bazada
faktura ham, foyda ham, ombor ham ko'rsatadigan narsasi yo'q.

Tartib muhim — har qadam o'zidan oldingisiga tayanadi:

| # | Nima | Qayerda | Nega aynan shu joyda |
|---|---|---|---|
| 1 | **Kompaniya passporti** (QQS holati bilan) | Kompaniya | Shartnoma va fakturaga MUZLATIB ko'chiriladi — keyin to'ldirilsa, oldin chiqarilgan hujjatlar rekvizitsiz qoladi |
| 2 | **Hodimlar, hisoblar va kamida bitta RAHBAR** | Hodimlar | Hisob HODIMGA bog'lansin, aks holda "mening ishlarim" bo'sh qoladi va `created_by` da ism chiqmaydi. **Kamida bittasi `rahbar` yoki `menejer` bo'lsin** — pastga qarang |
| 3 | **Mijoz passportlari** | Mijozlar | Faktura mijoz rekvizitlarisiz chiqmaydi; QQS stavkasi ham shu yerdan olinadi |
| 4 | **Ombor boshlang'ich qoldig'i** | Ombor | Rezerv va chiqim shundan hisoblanadi |
| 5 | **Katalogda tannarx** | Tender-AI katalogi | Tannarxsiz foyda hisoboti "to'liq emas" bo'lib turaveradi |

### Nega RAHBAR hisobi kerak

Tizim rahbarsiz ham ISHLAYDI: `admin_faqat_koradi` sozlamasi o'chiq
turganda admin hamma amalni bajara oladi. Ya'ni bu to'siq emas,
**ajratilmagan javobgarlik**:

- 18 ta amal (karta yaratish, hodimga biriktirish, yakuniydan
  qaytarish, chat moderatsiyasi va h.k.) brokerda yo'q va rahbar/
  menejerga tegishli. Rahbar bo'lmasa ularning hammasini admin
  bajaradi — ya'ni tizim sozlovchi va biznes qaror qabul qiluvchi
  BITTA odam bo'lib qoladi.
- `admin_faqat_koradi` ni yoqib bo'lmaydi: `sozlama.saqla()` faol
  rahbar/menejer bo'lmasa **400** qaytaradi (usiz kompaniya o'z ERP
  siga yozolmay qolardi).

**Oqim uchidan-uchiga tekshirilgan** (2026-09-04) va to'liq ishlaydi:
hodim yaratish -> hisob ochish (rol bilan) -> rolni o'zgartirish ->
faolsizni qayta faollashtirish -> parol o'rnatish -> kirish. Hammasi
`Hodimlar` ekranidan qilinadi, buyruq satri kerak emas.

Tartib:

1. Hodimlar -> **Yangi hodim** (ism, email).
2. O'sha qatorda **Hisob ochish**: login, parol, rol = `rahbar`.
3. `check_setup.py` 3-bo'limi endi "N ta faol rahbar/menejer — rollar
   ajratilgan" deb yozadi. Yozmasa — qadam bajarilmagan.

**`admin_faqat_koradi` ni DARHOL yoqmang.** Rahbar hisobi ochilgani
qulfni ochadi, lekin sozlamani yoqish adminni cheklaydi va hamma ish
yangi hisobga o'tadi. Agar o'sha hisobga kirishda muammo chiqsa
(parol, cookie, ekran) kompaniya to'xtaydi. Avval rahbar hisobi bilan
haqiqiy ish qiling — bir-ikki karta, chat, status o'tishi — keyin
yoqing.

**2-qadam `auth-6` bilan bog'liq:** hodim hisobi ochilgach, unga parolni
o'zi almashtirish kerak bo'ladi — yon paneldagi "Parolni o'zgartirish"
har kim uchun ochiq (`erp_auth.md` 11).

**5-qadam kechikishi mumkin va bu xato emas.** Tannarx yo'q ekan, foyda
hisoboti daromadni ko'rsatadi va "N ta chiqimning tannarxi noma'lum"
deb ochiq yozadi (`erp_foyda.md` 4). Bu — dasturning kamchiligi emas,
ma'lumotning yo'qligi va u shunday deb aytiladi.

### Qayerdan boshlashni tizimning o'zi aytadi

```
.venv\Scripts\python.exe check_setup.py
```

9-bo'lim har qadamni tekshiradi va **birinchi to'ldirilmaganini**
alohida ko'rsatadi:

```
  KEYINGI QADAM: 1. Kompaniya passporti (QQS bilan)
        -> interfeys -> Kompaniya
```

Hammasi to'ldirilgach o'sha joyda "hamma ma'lumot kiritilgan" deb
yoziladi — ya'ni "tekshirdimmi?" degan savol ochiq qolmaydi.

---

## ISHLAB CHIQARISHGA QO'YISH

### Ikki rejim

| Rejim | Buyruq | Kim uzatadi interfeysni |
|---|---|---|
| **Ishlab chiqish** | `.\run_erp.ps1` | Vite dev serveri (`:5174`), qayta yig'ish bilan |
| **Ishlab chiqarish** | `.\run_erp.ps1 -Prod` | **Backendning o'zi** (`:8100`), qurilgan `dist` dan |

`-Prod` da Vite **umuman ko'tarilmaydi**: u qayta yig'ish uchun
mo'ljallangan vosita, ishlatish uchun emas (sekin va himoyalanmagan).

Bitta jarayon, bitta port. `nginx` qo'shilmadi — ichki ERP uchun yana
bitta xizmatni o'rnatish, sozlash va yangilash foydasidan ko'ra ko'proq
ish. Tashqariga chiqarilganda nginx old tomonga qo'yiladi va bu joy
o'zgarishsiz qoladi.

**`/api` prefiksi:** mijoz kodi doim `/api/...` ga murojaat qiladi.
Ishlab chiqishda uni Vite proksisi, ishlab chiqarishda esa serverning
o'zi kesadi. Ya'ni **bitta build ikkala rejimda ham ishlaydi** va "prod
uchun boshqa build" degan xatolik manbai yo'q.

### Tarmoqqa ochish

```powershell
.\run_erp.ps1 -Prod -BindHost 0.0.0.0
```

Default `127.0.0.1` — faqat shu kompyuter. `0.0.0.0` bilan boshqa
hodimlar `http://<IP>:8100` orqali kiradi.

**DIQQAT — bu yerda jimgina buziladigan joy bor.** HTTPS bo'lmasa
`.env` dagi `AUTH_COOKIE_SECURE` ni **0** qiling. Aks holda brauzer
sessiya cookie'sini saqlamaydi va kirish "parol noto'g'ri" demasdan,
shunchaki **ishlamaydi**. `check_setup.py` 11-bo'limi buni eslatib
turadi.

### Jadvalga qo'yiladigan ikki vazifa

```powershell
.\register_backup_task.ps1     # TenderERP-Backup    — har kuni 02:00
.\register_erp_task.ps1        # TenderERP-Reminders — har kuni 08:30
```

Ularsiz zaxira ham, eslatmalar ham **umuman ishlamaydi**. Ilgari
`check_setup.py` zaxira FAYLLARINI sanab "hammasi joyida" deb
ko'rsatardi — hatto jadvalga qo'yilmagan bo'lsa ham. Endi u vazifaning
o'zini tekshiradi.

### Jurnal

`logs/erp.log` — aylanma (10 MB × 7 fayl, `.env` dan sozlanadi).
Ilgari server yashirin oynada ishlardi va xato o'sha yerda yo'qolardi.

Parol, token va CSRF jurnalga **tushmaydi**: ular so'rov tanasida, u
esa yozilmaydi.

### Yangilash tartibi

```powershell
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # kerak bo'lsa
psql ... -f schema_patch_erp_NN.sql                             # yangi patch bo'lsa
.\run_erp.ps1 -Prod                                             # qayta qurib ko'taradi
.\.venv\Scripts\python.exe check_setup.py                      # tekshirish
```

### Hali yo'q (ongli qaror emas, ish)

- **HTTPS** — domen va sertifikat kerak;
- **avtomatik qayta ishga tushish** — hozir kompyuter o'chsa qo'lda
  ko'tariladi (Windows xizmati yoki `nssm` bilan hal bo'ladi);
- **zaxirani boshqa joyga nusxalash** — bitta disk ishdan chiqsa,
  undagi zaxira ham ketadi.

---

## "BUILD O'TDI" DEGANI "ISHLAYDI" DEGANI EMAS

```
.venv/Scripts/python.exe check_build.py
```

`run_erp.ps1 -Prod` buni O'ZI yurgizadi va xato bo'lsa serverni
ko'tarmaydi.

### Nega bu tekshiruv bor

`frontend/vite.config.ts` da `plugins` ro'yxati tushib qolgan edi:
`react` va `tailwindcss` import qilingan, lekin ro'yxatga
qo'shilmagan. Tailwind umuman ishga tushmagan — birorta utilita sinfi
(`.flex`, `.rounded-lg`) yaratilmagan va interfeys **butunlay
bezaksiz** chiqqan.

Eng yomoni: `tsc` ham, `npm run build` ham **muvaffaqiyatli** tugagan.
Utilitasiz CSS ham to'g'ri CSS. Ya'ni hech qanday vosita xato
ko'rsatmagan va buzuqlik haftalab sezilmagan — u faqat EKRANDA
ko'rinardi.

### Nima tekshiriladi

| Nima | Nega |
|---|---|
| `plugins` ro'yxatida `react()` va `tailwindcss()` | aynan o'sha xato |
| Import qilingan plagin **ishlatilganmi** | uning izi |
| CSS da `.flex`, `.grid`, `.rounded-lg`, `.bg-card` | Tailwind haqiqatan yurganmi |
| CSS da `@custom-variant` **qolmaganmi** | xom fayl uzatilyaptimi |
| `.dark` qoidalari | qorong'i mavzu qurilganmi |
| JS hajmi > 100 KB | qurilish yarim qolmaganmi |
| `<head>` da mavzu skripti | chaqnash bo'lmasin |

Qo'riqchining o'zi ham tekshirilgan: `plugins` qatori vaqtincha olib
tashlanganda **5 ta xato** bilan yiqiladi va "ishlab chiqarishga
qo'ymang" deb aytadi.

### ESLint nega yo'q

Qo'shishga urinildi. `typescript-eslint` **TypeScript 7 ni butunlay
rad etadi** — ishga tushishdan bosh tortadi (peer talab: `<6.1`).
Uni majburlab o'rnatish ham yordam bermadi.

U qo'llab-quvvatlaganda `no-unused-vars` shu xatoni ham ushlagan
bo'lardi (import bor, ishlatilishi yo'q). Shuning uchun bu — vaqtincha
holat, qaror emas: `typescript-eslint` TS 7 ni qo'llaganda qaytib
ko'riladi.

---

## INTERFEYS SINOVI

```
cd frontend
npm test          # bir marta
npm run test:watch
```

`run_erp.ps1 -Prod` uni **qurishdan oldin** yurgizadi: buzuq kodni
qurib, keyin tekshirishning ma'nosi yo'q.

### Nima tekshiriladi — va nima YO'Q

Backendda 875 tekshiruv bor edi, frontendda **bittasi ham yo'q**. Ya'ni
"aralash valyutada summa ko'rsatilmaydi", "hisob to'liq emas deb
aytiladi", "brokerga pul bloklari ko'rinmaydi" degan qoidalar serverda
tekshirilardi, **ekranda esa hech kim tekshirmasdi**. Bitta noto'g'ri
`&&` va qoida jimgina yo'qoladi.

Shuning uchun sinov komponentlarni emas, **qarorlarni** tekshiradi:

| Qoida | Qayerda |
|---|---|
| Hisob to'liq bo'lmasa OCHIQ aytiladi + "haqiqiy foyda bundan kam" | `ProfitLine` |
| QQS daromaddan ALOHIDA | `ProfitLine` |
| Pul harakati yo'q -> blok UMUMAN chiqmaydi | `ProfitLine` |
| Aralash valyutada umumiy yig'indi YO'Q + sababi | `ProfitPanel` |
| Aralashda panel pul yig'indilarini yashiradi, SANOQ qoladi | `Dashboard` |
| Brokerga pul/audit so'rovlari UMUMAN yuborilmaydi | `Dashboard` |
| Audit toza bo'lsa ham buni AYTADI | `AuditPanel` |
| "ERP dan tashqarida" va "chiqarilgandan keyin" belgilari | `AuditPanel` |
| Parol: nusxalar mos kelmasa tugma o'chiq | `MyPasswordPanel` |
| Yopilgan sessiyalar soni aytiladi | `MyPasswordPanel` |
| Parol uzunligi sharti MIJOZDA takrorlanmaydi | `MyPasswordPanel` |

**Ranglar, oraliqlar va joylashuv tekshirilmaydi.** Ular ko'z bilan
ko'riladi; sinov ularni ushlashga urinsa, har dizayn tuzatishida
yiqilib, foydadan ko'ra ko'proq to'sqinlik qilardi.

`api` moduli almashtiriladi — sinov na tarmoqqa, na bazaga chiqadi.

### Birinchi yurishda topilgani

`MyPasswordPanel` da maydonlar yorliq bilan **bog'lanmagan** edi:
yorliq oddiy `<div>` bo'lgani uchun ekran o'quvchisi uchun maydon
nomsiz qolardi va yorliqni bosish ham ishlamasdi. Ko'zga esa hammasi
joyida ko'rinardi. Tuzatildi (`htmlFor` + `id`).
