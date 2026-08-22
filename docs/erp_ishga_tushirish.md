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
.egister_backup_task.ps1       # har kuni 02:00 da avtomatik
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
| 2 | **Hodimlar va ularning hisoblari** | Hodimlar | Hisob HODIMGA bog'lansin, aks holda "mening ishlarim" bo'sh qoladi va `created_by` da ism chiqmaydi |
| 3 | **Mijoz passportlari** | Mijozlar | Faktura mijoz rekvizitlarisiz chiqmaydi; QQS stavkasi ham shu yerdan olinadi |
| 4 | **Ombor boshlang'ich qoldig'i** | Ombor | Rezerv va chiqim shundan hisoblanadi |
| 5 | **Katalogda tannarx** | Tender-AI katalogi | Tannarxsiz foyda hisoboti "to'liq emas" bo'lib turaveradi |

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
