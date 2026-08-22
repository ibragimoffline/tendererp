# Integratsiya — ERP 5A-1: SHARTNOMA va BIZNING REKVIZITLAR

`erp_arxitektura_3.md` da 5-bosqich ikkiga bo'lingan edi: **5A** — auth'siz
ham xavfsiz qism, **5B** — pul va ombor (auth talab qiladi). Bu hujjat
5A-1 ning bajarilgan holati.

**Maqsad:** taklif → shartnoma zanjirini yopish. "Yutildi" statusidan keyin
raqam, summa va muddat kartaning o'zida qoladi.

---

## 1. Fayllar

| Fayl | Holat | Vazifasi |
|---|---|---|
| `schema_patch_erp_5.sql` | yangi | `erp.own_company` (bitta qator) + `erp.contract` |
| `api/erp/contracts.py` | yangi | rekvizitlar, shartnoma CRUD, holat, yig'indi |
| `frontend/.../ContractList.tsx` | yangi | kartadagi shartnomalar bloki |
| `frontend/.../OwnCompanyPage.tsx` | yangi | "Kompaniya va shartnomalar" bo'limi |
| `_tests/erp5_test.py` | yangi | 47 tekshiruv |

Tender-AI tomonida **hech narsa o'zgarmadi**.

---

## 2. Nega `erp.own_company` kerak bo'ldi

Shartnoma IKKI tomonning rekvizitlarini talab qiladi. Mijozniki 2-bosqichda
paydo bo'lgan (`erp.client_company`), **biznikisi esa hech qayerda yo'q edi**:
tender-ai dagi `company_profile` — qidiruv va Go/No-Go profili (`keywords`,
`regions`, `certificates`, `employees`, `min_margin_percent`...), unda na
INN, na bank rekvizitlari, na yuridik manzil.

Shuning uchun bizning yuridik passport **ERP'da** yashaydi va
`company_profile` ga TEGILMAYDI (`erp_arxitektura.md` 2.1: u boshqa modul
egasi).

Ustunlar `client_company` bilan **bir xil nomlanadi** — shartnoma matnida
ikkala tomon bir xil shaklda ishlatiladi.

**Bitta qator** (`id = 1 CHECK`): mijoz o'chirilishi yoki faolsizlanishi
mumkin, biznikisi esa har doim bitta va har doim kerak. `client_company` ga
"bu bizmiz" bayrog'i qo'yilsa, "o'zimizni o'chirib qo'yish" mumkin bo'lardi.

---

## 3. Shartnoma

5 holat: `draft` → `signed` → `executing` → `done` / `terminated`.
Ro'yxat kodda ham, bazadagi CHECK da ham; sinov ikkalasini solishtiradi.

Qarorlar:

- **Summa qo'lda yozilmaydi** (kiritilmasa): taklifdan (`submission.price`),
  u ham bo'lmasa kartadagi snapshotdan olinadi. Bir xil raqamni ikkinchi
  marta yozish — xato manbai.
- **Raqam takrorlanmaydi** — qisman UNIQUE indeks (`number IS NOT NULL AND
  number <> ''`). Raqamsiz shartnomalar cheklovga tushmaydi: ular hali
  imzolanmagan bo'lishi mumkin. Takrorda **409** va `detail.contract_id`.
- **O'chirilmaydi** — noto'g'risi `terminated` ga o'tkaziladi (karta va
  taklif bilan bir xil qoida).
- Sanalar tekshiriladi: tugash sanasi boshlanishdan oldin bo'lsa **400**.
- `submission_id` ixtiyoriy: shartnoma ERP'dan tashqarida ham tuzilgan
  bo'lishi mumkin.

Endpointlar: `GET/PUT /erp/own-company`, `GET /erp/contracts`,
`GET /erp/contracts/stats`, `GET/POST /erp/opportunities/{id}/contracts`,
`PUT /erp/contracts/{id}`, `PATCH /erp/contracts/{id}/status`.

---

## 4. Interfeys

- **Kartada** "Shartnomalar" bloki: qo'shish formasi (raqam, summa, sanalar,
  qaysi taklif asosida) va holat tugmalari.
- **"Kompaniya va shartnomalar" bo'limi**: bizning rekvizitlar (yetishmagan
  maydonlar ochiq ko'rsatiladi) va barcha shartnomalar ro'yxati — qatordan
  kartaga o'tiladi.

---

## 5. Sinov

```
.venv/Scripts/python.exe _tests/erp5_test.py     # 47 tekshiruv
```

Qamrov: holatlar va CHECK mosligi, passport to'liqligi va INN formati,
summaning snapshotdan olinishi, takror raqam (409 + id), teskari sanalar
(400), manfiy summa (400), holat o'tishi va **yozuvning joyida qolishi**,
ro'yxat filtrlari, yig'indi, chegara sinovi.

Sinov bizning passportni o'zgartiradi (u bitta qator) va oxirida **asl
holiga qaytaradi** — buni ham tekshiradi.

---

## 5b. 5A-2: RAHBAR TAHLILI — yangi jadvalsiz

`api/erp/analytics.py` + `GET /erp/analytics?stuck_days=14`.

**Yangi jadval yo'q.** `erp.opportunity_history` 1-bosqichdan beri har
status o'tishini vaqti bilan yozib boradi — javoblar o'sha yerda edi,
faqat so'ralmagan edi.

Beshta savol:

1. **Bosqichda qancha turadi** — `LEAD()` bilan ketma-ket o'tishlar farqi.
   O'rtacha faqat **tugagan** turishlardan; hozir shu bosqichda turganlar
   alohida sanaladi (ularning vaqti hali tugamagan, o'rtachaga qo'shilsa
   ko'rsatkich pasayib ketardi). Mediana ham bor: bitta uzoq karta
   o'rtachani buzadi.
2. **Voronka** — "necha karta shu bosqichga YETIB BORGAN" (hozirgi holati
   emas, tarixi). Foiz ishga olinganlardan, bosqichdan bosqichga emas:
   ish jarayoni erkin va karta bosqichni o'tkazib yuborishi mumkin.
3. **Ishga olishdan topshirishgacha** — broker kesimida. Bu brokerni emas,
   JARAYONni o'lchaydi.
4. **Qotib qolganlar** — ochiq, lekin N kundan beri qimirlamagan kartalar;
   ochiq vazifalari soni bilan.
5. **Yutqazish sabablari** — 3-bosqichdagi kodlar bo'yicha.

Interfeys: "Hisobot" ko'rinishiga beshta bo'lim qo'shildi; qotib qolgan
karta ustiga bosilsa o'sha karta ochiladi.

Sinov (`erp5_test.py` 5b-bo'limi): status o'zgartiriladi va **tugagan
turish paydo bo'lgani** tekshiriladi; voronka sanog'i, chegara
(`stuck_days`) ishlashi va **tahlil hech narsa yozmasligi**.

---

## 6. Nima QILINMADI

To'lov, hisob-faktura, akt, yetkazib berish jadvali, shartnoma faylini
(.docx) yaratish — hammasi **5B** da va `erp_arxitektura_3.md` 6-bo'limdagi
uch savolga javob kelgach. Auth ham o'sha yerda: pul harakati "kim qildi?"
degan savolga ishonchli javobsiz yozilmaydi.
