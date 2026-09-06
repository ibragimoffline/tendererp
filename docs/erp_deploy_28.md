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

Eng arzon staging: **o'sha serverning o'zida ikkinchi baza** —
`staging_setup.ps1` shuni qiladi:

```powershell
.\backup_erp.ps1              # yangi zaxira
.\staging_setup.ps1           # xtxarid_staging + .env.staging
```

Skript zaxiradan tiklaydi (**bo'sh bazada emas** — ko'chirish
muammolari aynan mavjud ma'lumotda chiqadi), `.env.staging` ni
yozadi va ishlab chiqarish `.env` sida `ERP_MUHIT` borligini
tekshiradi.

---

## 0b. Muhit ajratish — bu YORLIQ EMAS, QULF

Ikki fayl, ikki baza, ikki nom:

```text
.env          ->  dbname=xtxarid           ->  ERP_MUHIT=prod
.env.staging  ->  dbname=xtxarid_staging   ->  ERP_MUHIT=staging
```

`ERP_MUHIT` ni `api/muhit.py` o'qiydi va u **qulf**: muhit `prod`
bo'lsa, `_tests/` dagi **hech qaysi** skript bazaga ulana olmaydi.

Nega bu kerak: sinovlar haqiqiy yozuv yaratadi va tozalaydi, lekin
`erp.doc_audit` — **faqat qo'shiladigan** jurnal (`doc_audit_guard`
`DELETE` ni to'sadi). Ya'ni "tozaladim" degani "izsiz" degani emas.

Qulf uch xususiyatga ega va uchalasi ham ataylab:

1. **`db.init_pool()` da**, har sinov faylida emas. Qo'lda
   chaqiriladigan qulf ertami-kechmi unutiladi — va aynan
   unutilgan faylda ishlab chiqarishga yoziladi. Hozirgi 26 ta
   sinov ham, hali yozilmagani ham qulfni **avtomatik** oladi.
2. **`SystemExit` dan meros.** Sinov fayllari `init_pool()` ni
   `except Exception` bilan o'raydi ("bazasiz sinov" holati
   uchun). Oddiy xato bo'lsa, qulf ishga tushardi-yu, sinov uni
   **yutib yuborardi** va "0 ta xato" deb chiqardi — darvoza
   muvaffaqiyat deb hisoblanardi. (Bu ishlab chiqish paytida
   haqiqatan yuz berdi va shundan keyin tuzatildi.)
3. **Bayroq bilan chetlab o'tib bo'lmaydi.** `--tasdiq` kabi
   bayroq bir marta yozilgach odat bo'ladi. Haqiqatan kerak
   bo'lsa `ERP_MUHIT` o'zgartiriladi — ancha ongli amal.

`ERP_MUHIT` qo'yilmagan bo'lsa qulf **ishlamaydi** (bugungi
o'rnatmalarni bir zarbada to'xtatmaslik uchun), lekin
ogohlantirish chiqadi va `check_setup.py` buni kamchilik deb
ko'rsatadi. **Ishlab chiqarishni sozlashning birinchi qadami —
`.env` ga `ERP_MUHIT=prod` yozish.**

Tekshirish:

```powershell
.\.venv\Scripts\python.exe _tests\muhit_test.py    # 38 tekshiruv
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

**Ikki qavatli himoya:**

* `--tasdiq` — mahalliy bo'lmagan manzil uchun (tasodifiy
  chaqiruvga qarshi);
* `ERP_MUHIT` qulfi — `prod` bo'lsa sinov **umuman** ulanmaydi va
  nolinchi bo'lmagan kod bilan chiqadi.

Ikkinchisi kuchliroq: `--tasdiq` faqat URL ni tekshiradi, ishlab
chiqarish esa xuddi shu `localhost` da turishi mumkin.

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

## Nosozlikda — TARTIB MUHIM

Odatda yangi sxema eski kodga mos bo'lsa, tartib erkin:

```text
1. eski kodni joylashtirish
2. sxemani qaytarish
```

**Bu holda EMAS.** 28-patchdagi ko'zgu trigger eski kodni
buzayotgani isbotlangan: eski kod `done = TRUE` yozadi, trigger uni
`status` dan qayta hisoblab darhol `FALSE` qiladi. "Bajarildi"
tugmasi bosiladi, vazifa ochiq qolaveradi, **xato yo'q**.

Shuning uchun tartib:

```text
1. traffic to'xtatish (run_erp.ps1 -Stop) yoki maintenance
2. SXEMA rollback   <- OLDIN
3. eski kod deploy
4. moslik tekshiruvi (check_setup.py)
5. smoke (brauzerdan: vazifa yaratish, bajarildi, karta ochish)
6. traffic ochish
```

Amalda:

```powershell
.\run_erp.ps1 -Stop
psql "$env:XT_DB_DSN" -v ON_ERROR_STOP=1 -f schema_patch_erp_28_rollback.sql
git checkout <oldingi SHA>
cd frontend; npm ci; npm run build; cd ..
.\.venv\Scripts\python.exe check_setup.py
.\run_erp.ps1 -Prod
```

Agar 2 va 3 orasida traffic to'xtatilmasa: shu oraliqda YANGI kod
eski sxema bilan ishlaydi va `status` ustunini so'rab 500 beradi.
Oraliq qisqa, lekin nolga teng emas — shuning uchun 1-qadam.

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

## Keyingi qadam: `due_at` → `TIMESTAMPTZ` (alohida patch)

Hozir `due_at` — `DATE`. Bu **blocker emas**, lekin soat
aniqligidagi eslatma uchun **beshta narsa birga** o'zgarishi
kerak. Faqat birinchisini qilish — ishlamaydigan va'da: ekran
"2 soat qoldi" deydi, jadval esa kuniga bir marta yurib uni
o'tkazib yuboradi.

| # | Nima | Nega |
|---|---|---|
| 1 | `ALTER ... TYPE timestamptz USING due_at::timestamptz` | kengaytirish — ma'lumot yo'qolmaydi (`DATE` → 00:00) |
| 2 | Jadval chastotasi | `register_erp_task.ps1` kuniga bir marta; 2 soatlik eslatma uchun kamida soatlik yurish kerak |
| 3 | Dedup kalitlari | hozir kalit **kun** bo'yicha (`muddat:{sana}:{opp}`); soatlik yurishda bir kunda 24 marta takrorlanardi. Kalitga "qaysi bosqich" qo'shiladi: `24h` / `2h` / `kechikdi` |
| 4 | Vaqt mintaqasi | `due_at` `timestamptz` bo'lgach "ertaga soat 14:00" kimning soati ekani muhim bo'ladi. Hozir ERP bitta mintaqada (+05) va u hech qayerda yozilmagan — yozilishi kerak |
| 5 | Bosqich qoidalari | 24 soat / 2 soat / kechikdi — qaysi biri kimga va qaysi kanalga. Tashqi kanal kompaniya darajasida (`docs/erp_xabar.md` §2f), ya'ni "2 soat qoldi" ni Telegram guruhiga yuborish shovqin bo'lardi |

3-qator eng oson unutiladigani: ustun turi va jadval to'g'rilanib,
dedup eski holda qolsa — hodim bir kunda o'nlab bir xil
bildirishnoma oladi va bir haftadan keyin ularni umuman o'qimay
qo'yadi. Shundan keyin **haqiqiy** xabar ham ko'rinmaydi.

Vazifa izohlari uchun ham shu qoida: yangi messaging subsystem
emas, mavjud chatni task konteksti bilan kengaytirish
(`erp.chat.turi` ga uchinchi qiymat).
