# Tender ERP

Ishga olingan tenderlarning ichki ish kartalari, mijoz korxonalar bazasi va
rahbar hisoboti. **Alohida loyiha** — o'z backendi (:8100), o'z interfeysi
(:5174), o'z bog'liqliklari.

Tender-AI bilan **integratsiya qilingan**, uning ichida emas: bog'lanish uch
nuqtada va hammasi bir tomonlama (`docs/erp_arxitektura_2.md`).

```
  Tender-AI (:5173 / :8000)                 ERP (:5174 / :8100)
  ├─ tender ro'yxati, AI tahlil            ├─ Kanban: ishdagi tenderlar
  ├─ narx hisobi, ombor, Go/No-Go          ├─ mijoz korxonalar passporti
  ├─ hujjat cheklisti QOIDALARI  ←─────────┤  (mijoz hujjatlarini yuboradi)
  └─ "ERP da ishga olish" havolasi ────────→  karta ochiladi
                    └──────── bitta PostgreSQL ────────┘
                       public.*            erp.*
```

---

## Ishga tushirish

**Talab:** PostgreSQL (tender-ai bilan bir xil baza), Python 3.11+, Node 18+.

```powershell
# 1. Baza (bir marta, operator qadami)
psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_1.sql
psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_2.sql
psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_3.sql
psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_4.sql
psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_5.sql

# 2. Backend
copy .env.example .env          # XT_DB_DSN va TENDER_AI_* ni to'ldiring
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Frontend
cd frontend; npm install; cd ..

# 4. Ikkalasini ko'tarish
.\run_erp.ps1                   # :8100 va :5174
.\run_erp.ps1 -Stop

# 5. Eslatmalar (ixtiyoriy) — kuniga bir marta
.\register_erp_task.ps1 -At 08:30
.\.venv\Scripts\python.exe -m api.erp.remind --dry-run   # sinash
```

Birinchi hodim hisobi SHU YERDA yaratiladi (hodimlar ERP niki):

```powershell
.\.venv\Scripts\python.exe create_user.py admin "Bosh administrator" --role admin
.\.venv\Scripts\python.exe create_user.py --brokers    # hodimlar ro'yxati
```

Tender-AI alohida ko'tariladi (`tender-ai\run_all.ps1 -NoTunnel`). ERP
usiz ham ishlaydi — **kirish ham**: kimlik ERP ning o'zida. Faqat
**cheklist** va **yangi karta olish** ishlamaydi, buni interfeys ochiq
aytadi.

Tender-AI tomonida qilinadigan kichik o'zgarishlar — `INTEGRATSIYA.md`.

---

## Tuzilma

```
tender erp/
├── README.md                    # shu fayl
├── INTEGRATSIYA.md              # tender-ai tomonidagi o'zgarishlar
├── REJA.md                      # qolgan ishlar, bosqichlarga bo'lingan
├── run_erp.ps1                  # backend + frontend
├── requirements.txt / .env.example
├── schema_patch_erp_1.sql       # erp sxemasi + 4 jadval
├── schema_patch_erp_2.sql       # passport + kontakt + hujjat
├── schema_patch_erp_3.sql       # vazifalar + sabab + eslatma belgisi
├── schema_patch_erp_4.sql       # muzlatilgan takliflar
├── schema_patch_erp_5.sql       # shartnoma + bizning rekvizitlar
├── schema_patch_erp_6.sql       # HODIM hisoblari va sessiya
├── schema_patch_erp_7.sql       # tender-ai uchun SHARTNOMA-VIEW
├── schema_patch_erp_8.sql       # OMBOR: harakatlar jurnali + qoldiq view
├── schema_patch_erp_9.sql       # AUTH-4: sessiyaga CSRF tokeni
├── schema_patch_erp_10.sql      # REZERV: ajratilgan tovar + mavjud
├── schema_patch_erp_11.sql      # HISOB-FAKTURA: qatorlar, QQS, to'lovlar
├── schema_patch_erp_12.sql      # DALOLATNOMA (akt)
├── create_user.py               # hodim hisobi CLI (birinchi admin)
├── check_setup.py               # TAYYORLIK tekshiruvi (7 bo'lim)
├── cleanup_demo.py              # demo/sinov yozuvlarini tozalash
├── register_erp_task.ps1        # eslatmani jadvalga qo'yadi
├── backup_erp.ps1               # ZAXIRA: faqat erp sxemasi (pg_dump -Fc)
├── register_backup_task.ps1     # zaxirani jadvalga qo'yadi (02:00)
├── deploy/                      # SERVER (Linux) — docs/deploy_linux.md
│   ├── bin/bootstrap.sh         # serverni bir marta tayyorlash
│   ├── bin/deploy.sh            # reliz + atomar almashtirish (staging birinchi)
│   ├── bin/migratsiya.sh        # patchlarni RAQAM tartibida, cheksum bilan
│   ├── bin/health-check.sh      # tiriklik / baza / sxema / interfeys
│   ├── bin/rollback.sh          # bitta `ln -sfn` bilan orqaga
│   ├── systemd/                 # tendererp-api@ , tendererp-remind@
│   └── env/*.env.example        # muhit namunalari (SIR YO'Q)
├── api/
│   ├── main.py                  # FastAPI ilovasi (56 marshrut)
│   ├── db.py                    # pool va query yordamchilari
│   ├── tenderai.py              # TENDER-AI GA YAGONA KO'PRIK
│   ├── auth.py                  # HODIM kimligi: parol, sessiya, rollar
│   └── erp/
│       ├── opportunity.py       # snapshot, CRUD, status o'tish, sabablar
│       ├── stats.py             # rahbar hisoboti (GROUP BY bazada)
│       ├── clients.py           # passport, aloqalar, hujjatlar
│       ├── tasks.py             # vazifalar, "mening ishlarim"
│       ├── submission.py        # taklif paketi, muzlatilgan versiyalar
│       ├── contracts.py         # shartnoma + bizning rekvizitlar
│       ├── analytics.py         # bosqich vaqtlari, voronka, qotib qolganlar
│       ├── staff.py              # hodimlar + ularning hisoblari (admin)
│       ├── stock.py              # ombor: harakatlar jurnali, qoldiq
│       ├── invoice.py            # hisob-faktura: qatorlar, QQS, to'lovlar
│       ├── invoice_export.py     # eksport — ATAYLAB BO'SH QATLAM
│       ├── act.py                # dalolatnoma (hisob fakturanikidan)
│       └── remind.py            # eslatma skripti (jadval bo'yicha)
├── _tests/
│   ├── fixture.py               # sinov ma'lumoti: sinov O'ZI yaratadi
│   ├── erp_test.py              # 1-bosqich + diff + tozalash — 123 tekshiruv
│   ├── erp2_test.py             # 2-bosqich + import — 79 tekshiruv
│   ├── erp3_test.py             # 3-bosqich — 58 tekshiruv
│   ├── erp4_test.py             # 4-bosqich — 45 tekshiruv
│   ├── erp5_test.py             # 5A + ilova — 80 tekshiruv
│   ├── erp6_test.py             # AUTH + hodimlar — 121 tekshiruv
│   ├── erp7_test.py             # OMBOR + rezerv + taklif — 102 tekshiruv
│   ├── erp8_test.py             # HISOB-FAKTURA + zanjir — 105 tekshiruv
│   └── erp9_test.py             # DALOLATNOMA — 48 tekshiruv
├── frontend/                    # alohida Vite ilovasi
│   └── src/
│       ├── App.tsx              # yon panel + chuqur havolalar (?take= / ?opp=)
│       ├── api.ts, types.ts, format.ts
│       └── components/
│           ├── Icon.tsx, ui/    # dizayn tizimi (tender-ai bilan bir xil tokenlar)
│           └── erp/             # 24 ta komponent
├── integratsiya/ErpLink.tsx     # tender-ai ga qo'yiladigan komponent
└── docs/                        # qarorlar va bosqichlar
    └── README.md                # HUJJATLAR XARITASI — qaysi qaror qayerda
```

---

## Bajarilgan ish

### 1-bosqich — "Ishga olish" + Opportunity pipeline
`erp` sxemasi (4 jadval), 9 statusli quvur, Kanban (sudrab ko'chirish),
jadval, karta (snapshot + tahrir + tarix), rahbar hisoboti.
Karta o'chirilmaydi; yakuniy statusdan qaytish faqat izoh bilan.

### 2-bosqich — mijoz korxonalar va passport
INN (takrorlanmaydi), bank rekvizitlari, aloqa shaxslari, mijoz hujjatlari.
**Cheklist mijoz hujjatlariga qarab ishlaydi** — qoidalar tender-ai'da
qoladi, hujjatlar u yerga yuboriladi.

### Hujjatlar shabloni (0.2)
Mijoz hujjatlarini bitta fayl bilan kiritish: shablon (.xlsx/.csv) yuklab
olinadi, to'ldiriladi va qaytarib yuklanadi. Tartib katalog importi bilan
bir xil — **dry-run → ko'rish → tasdiqlash**. Faylni tender-ai o'qiydi
(qoidalar o'sha yerda), yozishni ERP qiladi. Takror yuklashda tur+nom
bo'yicha mavjudi yangilanadi, takror yozuv paydo bo'lmaydi.

### "Tenderda yangilanish bor" belgisi (0.3)
Karta jonli tender bilan solishtiriladi va farq **ko'rsatiladi**: muddat
ko'chgan, narx qayta e'lon qilingan, buyurtmachi nomi o'zgargan. Snapshot
esa **o'zgarmaydi** — qaysi qiymat to'g'ri ekanini odam hal qiladi. Tender
manbadan o'chirilgan bo'lsa karta qoladi va buni ochiq aytadi.

### 3-bosqich — vazifalar, eslatmalar va yutqazish sabablari
Kartada bitta "keyingi vazifa" o'rniga **ro'yxat**: muddat, mas'ul,
bajarildi belgisi. **"Mening ishlarim"** bo'limi kunni boshlash uchun:
kechikkan / bugun / keyingi. **Eslatma** kuniga bir marta yuriladi
(`register_erp_task.ps1`) va takror yubormaydi; transport tender-ai'da
qoladi — sirlar ERP'ga ko'chmaydi. Yutqazishda **sabab** so'raladi (7 kod).

### 4-bosqich — taklif va topshirish
Topshirilgan taklif **muzlatiladi**: narx, o'sha paytdagi cheklist va
hujjatlar nusxasi versiya bo'lib qoladi (o'chirilmaydi, tahrirlanmaydi).
Cheklistdagi to'siq **taqiq emas** — ogohlantirish ko'rsatiladi va tasdiq
tarixga yoziladi. Tender manbada yopilsa karta "yakunlash kerakmi?" deb
**taklif** qiladi: manba g'olibni bermaydi, natijani odam belgilaydi.

### 5A-1 — shartnoma va bizning rekvizitlar
Taklif → shartnoma zanjiri yopildi: raqam, summa, muddat va holat kartada
qoladi. Summa taklifdan/snapshotdan olinadi, raqam takrorlanmaydi,
shartnoma o'chirilmaydi (noto'g'risi "Bekor qilingan" ga o'tadi).
**Bizning yuridik rekvizitlar** ERP'da paydo bo'ldi: tender-ai dagi
kompaniya profilida INN ham, bank rekvizitlari ham yo'q edi.

### 5A-2 — rahbar tahlili (yangi jadvalsiz)
Bosqichda o'tgan vaqt (o'rtacha/mediana/eng uzun), voronka, ishga olishdan
topshirishgacha bo'lgan sikl, **qotib qolgan kartalar** va yutqazish
sabablari — hammasi `opportunity_history` dan hisoblanadi.

### AUTH — kirish, sessiya va rollar
**Hodim hisoblari ERP niki** (`erp.app_user`, `broker_id` -> `erp.broker`
haqiqiy FK bilan): odam — ERP ning tushunchasi. Tender-AI esa KOMPANIYA
hisobi bilan kiriladi (`company_account`) va ikkala tomon o'z kimligini
mustaqil tekshiradi.

56 endpointdan 50 tasi himoyalangan; 3 tasi rahbar, 6 tasi admin
huquqini talab qiladi. Administrator uchun **Hodimlar** ekrani: hodim va
uning hisobi bitta ro'yxatda, hisob ochish va rol berish shu yerdan.

**Auth-2:** tender-ai ham yopildi (kirish ekrani + global darvoza). ERP u
yerga `X-Service-Key` bilan boradi — `.env` dagi `ERP_SERVICE_KEY`
**ikkala loyihada bir xil bo'lishi shart**. "Mening ishlarim" endi
sessiyadagi hodim bo'yicha sukut filtrlanadi.

### 5B-1 — Ombor (qoldiqning egasi ERP)
Qoldiq alohida ustunda saqlanmaydi — u **harakatlar yig'indisi**
(`erp.stock_move`). Har o'zgarish kim, qachon va nima uchun qilgani
bilan yozilgan; "nega 12 dona?" degan savolga javob bor. Tender-AI
qoldiqni `erp.v_stock_balance` **shartnoma-view** idan o'qiydi, ya'ni
`public.*` ga yozmaslik qoidasi buzilmadi. Manfiy qoldiq taqiqlanmaydi —
ogohlantiriladi (hujjat kechikishi normal hol).

**Rezerv:** "shu karta uchun ajratildi" — qoldiqni kamaytirmaydi,
**mavjud** miqdorni kamaytiradi va kartaning statusiga bog'langan
(`confirmed` da qo'yiladi, `won` da chiqimga aylanadi, `lost` da
bo'shaydi). Tender-AI ning "yetadimi?" hisobi mavjud miqdordan yuradi.

**Taklif:** kartada "Tender pozitsiyalaridan taklif" — moslashuv
tender-ai da bajariladi, ERP undan "nima kerak, omborda bormi" ro'yxatini
quradi. **Hech narsa avtomatik yozilmaydi**: moslashuv nom bo'yicha
ishlaydi va tasdiqni odam beradi. Tafsilot: `docs/erp_ombor.md`.

### Sinovlar bazaga tayanmaydi
`_tests/fixture.py` — kerakli minimal ma'lumotni (hodim, mijoz, karta)
**sinovning o'zi** yaratadi va oxirida o'chiradi. Sabab amaliy: demo
ma'lumot tozalanganda qamrov **jimgina** 863 dan 582 ga tushib ketgan
edi va hech bir sinov yiqilmagan — sinov "hammasi joyida" deb turib,
aslida yarmini tekshirmayapti. Katalog mahsuloti bundan mustasno: u
`public.*` da va **sinov ham** u yerga yozmaydi (chegara qoidasi
ilovaga ham, sinovga ham tegishli).

### Zaxira nusxasi
`backup_erp.ps1` — **faqat `erp` sxemasi** (`public.*` tender-ai niki va
uning zaxirasi o'sha loyihaning ishi). ERP mustaqil tiklanadi: karta
tenderga faqat raqam bilan bog'langan. Skript fayl hajmini tekshiradi —
bo'sh fayl "zaxira olindi" deb yozilib qolmasin. Tiklash tekshirilgan:
vaqtinchalik bazaga tiklanib, qator sonlari asl bilan solishtirilgan.
`register_backup_task.ps1` — har kuni 02:00 da.

### Ishga tushirish va tayyorlik
`check_setup.py` — baza, 11 ta patch, kirish, rekvizitlar, tender-ai
bilan bog'lanish, cookie va demo ma'lumotni **bir joyda** tekshiradi
(chiqish kodi: 0/1). `cleanup_demo.py` — demo va sinov yozuvlarini
belgisi bo'yicha tozalaydi; **sukut bo'yicha hech narsa o'chirmaydi**,
faqat ko'rsatadi. Bo'sh bazadan boshlash yo'riqnomasi:
`docs/erp_ishga_tushirish.md`.

### 5B-2 — Hisob-faktura
ERP fakturaning **ma'lumotini** yuritadi; yuborishni operator/1C qiladi
(O'zbekistonda faktura elektron shaklda, operator orqali yuboriladi —
ERP bosgan PDF soliq hujjati emas). Shuning uchun **eksport qatlami
ataylab bo'sh** va format mijozdan so'ralgach to'ldiriladi.

QQS **mijoz passportida** (`vat_payer` / `vat_rate`) va faktura
**qatoriga nusxa** ko'chiriladi — passport keyin o'zgarsa chiqarilgan
hujjat buzilmasin. Summalar saqlanmaydi (qatorlardan hisoblanadi),
rekvizitlar snapshot, `draft` dan chiqqach hujjat muzlaydi.

**Zanjir yopildi:** kartadan "Faktura chiqarish" — qatorlar **ajratilgan
tovardan** to'ldiriladi (miqdor haqiqiy, narx katalogdan; topilmasa 0 va
buni interfeys ochiq aytadi). Taklif → shartnoma → faktura → to'lov.

**Bosma shakl:** brauzer chop etadi (PDF kutubxonasi yo'q), summa so'z
bilan yoziladi. Shaklning o'zida yozilgan: bu yuridik hujjat emas —
elektron faktura operator orqali yuboriladi.

**Shartnoma ilovasi:** ERP shartnoma **matnini yozmaydi** — huquqiy matn
yurist ishi. ERP **ilovani** chiqaradi: pozitsiyalar, miqdor, narx,
jami. Ma'lumot fakturadan (muzlatilgan) yoki rezervdan olinadi va manba
shaklning o'zida yoziladi.

**Dalolatnoma (akt):** faktura "qancha to'lash kerak" deydi, akt
"bajarildi" deydi. Fakturadan chiqariladi, qatorlar **ko'chiriladi** —
faktura keyin bekor qilinsa ham akt o'z holicha qoladi. Hisob-kitob
fakturaning kodi bilan (ikki xil yaxlitlash ikki xil summa degani
bo'lardi). Tafsilot: `docs/erp_faktura.md`.

**Auth-4:** sessiya tokeni endi **`HttpOnly` cookie**'da —
`localStorage` da emas, ya'ni XSS uni o'qiy olmaydi. Cookie'ning narxi
(CSRF) `SameSite=Lax` va `X-CSRF-Token` sarlavhasi bilan yopilgan; token
**sessiyaga bog'langan**, shuning uchun boshqa sessiyaniki ishlamaydi.
Cookie ishlashi uchun so'rov same-origin bo'lishi shart
(`VITE_API_BASE=/api`). Tafsilot: `docs/erp_auth.md` 9-bo'lim.

**Auth-3:** oxirgi ochiq endpoint ham yopildi. Tender-AI endi "bu tender
ishga olinganmi?" degan savolga javobni `erp.v_tender_status`
**shartnoma-view** idan oladi (`schema_patch_erp_7.sql`) — HTTP ham,
sir ham, CORS ham kerak emas. ERP ning 56 endpointidan **51 tasi
himoyalangan**; ochiq qolgani faqat `/health`, `/erp/meta`,
`/erp/auth/*`. Eng muhimi: **`created_by` sessiyadan olinadi** —
brauzer yuborgan ism e'tiborga olinmaydi; hisob hodimga bog'langan bo'lsa
hodim ismi ustun.

Auth-1 da kimlik teskari tomonda edi (hodimlar tender-ai da, ERP HTTP
orqali tekshirardi) — tuzatildi, hisoblar parol xeshi bilan ko'chirildi.
Tafsilot: `docs/erp_auth.md`.

### Ajratish
ERP tender-ai ichidan chiqarildi: o'z ilovasi, o'z interfeysi, o'z venv'i.
Tender-AI tomonida ERP kodi qolmadi — faqat `ErpLink.tsx` va bitta endpoint.

---

## Chegaralar (ongli)

- `public.*` ga **yozilmaydi** — har sinovda tekshiriladi.
- Karta **o'chirilmaydi**: noto'g'ri karta `rejected` + izoh.
- Status ketma-ketligi majburlanmaydi (ochiq → ochiq erkin).
- Auth yo'q: `created_by` — tanlangan brokerning nomi (matn).
- Interfeys **o'zbekcha**: status va ustuvorlik yorliqlari serverdan
  o'zbekcha keladi, ularni tarjima qilish ikkinchi manba yaratardi.
- Narx hisobi, ombor, tender hujjatlari ERP'da ko'rsatilmaydi — tender-ai
  paneliga havola beriladi (bir xil panelni ikki joyda saqlamaslik uchun).

Keyingi ishlar — `REJA.md`.
