# 28-PATCHNI JOYLASHTIRISH — RUNBOOK

**Patch:** `schema_patch_erp_28.sql` ·
**Orqaga qaytarish:** `schema_patch_erp_28_rollback.sql` ·
**Darvoza:** `_tests/erp28_http_test.py`

---

## 0. Muhitning haqiqiy holati

Buni oldindan bilib qo'ying — bu yerda CI/CD, Docker yoki alohida
staging DSN **yo'q**:

| Nima | Holat |
|---|---|
| CI (GitHub Actions va h.k.) | yo'q — darvozalar **qo'lda** yuritiladi |
| Konteyner / IaC | yo'q — `run_erp.ps1 -Prod` bilan ishga tushiriladi |
| Staging bazasi | **alohida sozlanmagan** — bitta `XT_DB_DSN` |
| Zaxira | `backup_erp.ps1` (`pg_dump -Fc`), jadvalda kunlik |

Ya'ni **5-qadam (staging deploy) uchun avval staging muhitini
yaratish kerak**: alohida baza + `.env` nusxasi. Usiz "staging"
degani ishlab chiqarish bazasining o'zi bo'lib qoladi va butun
tartibning ma'nosi yo'qoladi.

Eng arzon staging: **o'sha serverning o'zida ikkinchi baza**.

```powershell
# Zaxiradan nusxa (ishlab chiqarish MA'LUMOTI bilan)
createdb -U postgres xtxarid_staging
pg_restore -U postgres -d xtxarid_staging --clean --if-exists `
    backups\<oxirgi>.dump

# Alohida .env
Copy-Item .env .env.staging
# .env.staging ichida: XT_DB_DSN dbname=xtxarid_staging
```

---

## 1–4. Kod: branch → PR → main → tag

```powershell
git push origin erp-rollar-huquqlar
# PR: https://github.com/ibragimoffline/tendererp/compare/main...erp-rollar-huquqlar
# (gh CLI o'rnatilmagan — PR brauzerdan ochiladi)

# Merge'dan KEYIN aynan o'sha SHA ni oling:
git checkout main; git pull
git rev-parse HEAD          # <- shu SHA joylashtiriladi
git tag -a erp-28 -m "28-patch: jamoa va umumiy vazifalar"
git push origin erp-28
```

**Nega aynan SHA:** `main` keyin ham o'zgaradi. Joylashtirilgan
narsa "main" emas, **o'sha paytdagi main** — va nosozlikda aynan
shu SHA ga qaytiladi.

---

## 5–6. Staging deploy va patch

```powershell
git checkout erp-28
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend; npm ci; npm run build; cd ..

# ZAXIRA — patchdan OLDIN, har doim
.\backup_erp.ps1

$env:XT_DB_DSN = "dbname=xtxarid_staging user=postgres host=localhost"
psql "$env:XT_DB_DSN" -v ON_ERROR_STOP=1 -f schema_patch_erp_28.sql
```

**Patch idempotent va o'zini tuzatadi:** qayta yurgizilsa xato
bermaydi, va ko'zgu trigger tushib qolgan bo'lsa uni tiklab,
`done` ni `status` ga qayta moslaydi. Bu sinab ko'rilgan.

`ON_ERROR_STOP=1` **shart**: usiz psql xatodan keyin ham davom
etadi va yarim qo'llangan patch qoladi.

---

## 7–8. Backend va frontend darvozalari

```powershell
# 7 — backend (24 fayl, ~1640 tekshiruv)
Get-ChildItem _tests\*_test.py | ForEach-Object {
    .\.venv\Scripts\python.exe $_.FullName
}

# 8 — frontend
cd frontend; npx tsc -b --noEmit; npx vitest run; npm run build; cd ..
```

Nolinchi bo'lmagan chiqish kodi — **to'xtash sababi**.

---

## 9. HTTP E2E darvozasi

```powershell
.\run_erp.ps1                       # boshqa oynada
.\.venv\Scripts\python.exe _tests\erp28_http_test.py `
    --base http://127.0.0.1:8100
```

40 ta tekshiruv — bu ro'yxatning aynan o'zi:

| Tekshiriladi | Bo'lim |
|---|---|
| umumiy vazifa yaratish | 2 |
| hodimga vazifa biriktirish va bajarish | 3 |
| tenderga 3 hodim biriktirish | 4 |
| asosiy mas'ul faqat 1 ta | 4 |
| narxchi karta ochishi | 5 |
| begona hodim 403 | 3, 5 |
| chat_member qo'shilishi | 6 |
| hodim chiqarilganda chat yopilishi | 7 |
| notification kelishi | 8 |
| audit yozilishi | 9 |

Qo'shimcha: soxta `created_by` e'tiborga olinmasligi, yuklama
huquqi, yumshoq chiqarish.

**Boshqa mashinadan** yuritilsa `--tasdiq` kerak — sinov haqiqiy
yozuv yaratadi va uni ataylab tasdiqlash shart.

---

## 10. Odam bilan tekshirish (staging)

Darvozalar ushlamaydigan yagona narsa — **ekran**. Uchta hisob
bilan brauzerdan:

1. **Menejer:** karta ochib "Jamoa" → uch hodim qo'shing, rollar
   ko'rinsinmi; kanbanda "Karimov +2" chiqdimi.
2. **Narxchi:** kirib, o'sha karta ro'yxatida ko'rinadimi;
   "Muloqot" ochiladimi; qo'ng'iroqda bildirishnoma bormi va
   bosilganda **aynan o'sha** kartaga olib boradimi.
3. **Begona hodim:** o'sha karta **ko'rinmasligi** kerak.
4. **Mening ishlarim:** "Yangi vazifa" → tendersiz vazifa; ro'yxatda
   `umumiy` belgisi bilan chiqdimi; belgilangach yo'qoldimi.
5. **Telefon ekrani:** ro'yxat va jamoa paneli gorizontal
   surilmasdan o'qiladimi.

---

## 11. Production deploy

```powershell
.\backup_erp.ps1                    # ZAXIRA — majburiy
git checkout erp-28
cd frontend; npm ci; npm run build; cd ..
psql "$env:XT_DB_DSN" -v ON_ERROR_STOP=1 -f schema_patch_erp_28.sql
.\run_erp.ps1 -Prod
```

**Tartib muhim:** patch AVVAL, ilova KEYIN. Teskarisi bo'lsa yangi
kod hali yo'q ustunlarni so'rab 500 beradi.

Patch **eski kodni buzmaydi** (yangi ustunlarda standart qiymat
bor), ya'ni patch va deploy orasidagi bir necha daqiqa xavfsiz.

---

## 12. Deploy'dan keyingi tekshiruv

```powershell
.\.venv\Scripts\python.exe check_setup.py
```

Faqat o'qiydi — ishlab chiqarishda xavfsiz. 28-patch uchun to'rtta
qator:

```text
OK  schema_patch_erp_28.sql — karta jamoasi
OK  vazifa `done` ko'zgu triggeri ulangan
OK  vazifa holati va `done` ustuni mos
OK  asosiy mas'ul jamoa jadvalida takrorlanmagan
```

**Eng muhimi — ikkinchi qator.** Ko'zgu trigger tushib qolsa
`done` va `status` **jimgina** ajralib ketadi: bajarilgan vazifa
ro'yxatda ochiq bo'lib qolaveradi va xato chiqmaydi. Bu holat
ataylab buzib sinab ko'rilgan — tekshiruv uni ushlaydi.

`erp28_http_test.py` ni ishlab chiqarishda yuritmang: u haqiqiy
yozuv yaratadi va tozalasa ham audit jurnalida iz qoladi.

---

## Nosozlikda

**Kod qaytariladi, sxema qoladi** — eng xavfli variant:

```powershell
psql "$env:XT_DB_DSN" -f schema_patch_erp_28_rollback.sql
git checkout <oldingi SHA>
```

Rollback skripti **ma'lumotni o'chirmaydi**: jamoa a'zoliklari va
umumiy vazifalar joyida qoladi (eski kodda ko'rinmaydi, lekin
yo'qolmaydi). U bitta narsani majburan tuzatadi — **ko'zgu
triggerni olib tashlaydi**, chunki eski kod `done` ni
to'g'ridan-to'g'ri yozadi va trigger uni darhol bekor qilardi:
"Bajarildi" tugmasi ishlamayotgandek ko'rinardi.

Rollback → eski xulq → patchni qayta qo'llash tsikli sinab
ko'rilgan.

**Baza buzilsa:**

```powershell
pg_restore -U postgres -d xtxarid --clean --if-exists -n erp `
    backups\<patchdan oldingi>.dump
```

---

## Keyingi qadam: `due_at` → `TIMESTAMPTZ`

Hozir `due_at` — `DATE`. Bu **blocker emas**, lekin soat
aniqligidagi eslatma (24 soat / 2 soat / 30 daqiqa) uchun ikkita
narsa birga o'zgarishi kerak:

1. ustun turi (`ALTER ... TYPE timestamptz USING due_at::timestamptz`
   — kengaytirish, ma'lumot yo'qolmaydi);
2. **eslatma jadvali**: hozir `register_erp_task.ps1` kuniga bir
   marta yuriydi. Soatlik eslatma uchun u ham tez-tez yurishi
   kerak — aks holda ustun turi o'zgaradi-yu, "2 soat qoldi"
   xabari baribir yetib bormaydi.

Faqat birinchisini qilish — ishlamaydigan va'da. Ikkalasi alohida
patch sifatida rejalashtirilsin.
