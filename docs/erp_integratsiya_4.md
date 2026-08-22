# Integratsiya — ERP 4-BOSQICH: TAKLIF va TOPSHIRISH

`erp_bosqichlar.md` 4-bosqichining bajarilgan holati.

**Maqsad:** "Topshirildi" statusi belgidan HUJJATGA aylanadi — qaysi narx
bilan, qanday cheklist holatida va qaysi hujjatlar bilan topshirilgani
o'zgarmas ko'rinishda qoladi.

---

## 1. Fayllar

| Fayl | Holat | Vazifasi |
|---|---|---|
| `schema_patch_erp_4.sql` | yangi | `erp.submission` (muzlatilgan versiyalar) |
| `api/erp/submission.py` | yangi | taklif paketi, topshirishni qayd etish |
| `api/tenderai.py` | o'zgardi | `pricing()`, `tender()` — o'qish uchun |
| `api/erp/opportunity.py` | o'zgardi | tender-diff'ga manbadagi status |
| `frontend/.../SubmissionPanel.tsx` | yangi | kartadagi "Taklif" bo'limi |
| `_tests/erp4_test.py` | yangi | 45 tekshiruv |

Tender-AI tomonida **hech narsa qo'shilmadi**: mavjud
`GET /tenders/{id}/pricing` va `GET /tenders/{id}` yetdi.

---

## 2. Muzlatish — nega JSONB

`erp.submission` da narx hisobi, cheklist va hujjatlar nusxasi **JSONB**
ustunlarda. Sabab: narx hisobining tarkibi (`pricing.py` natijasi) vaqt
o'tib o'zgarishi mumkin, muzlatilgan nusxa esa O'SHA PAYTDAGI shaklda
qolishi kerak. Ustunlarga yoyilsa har o'zgarishda migratsiya kerak bo'lardi
va eski yozuvlar buzilardi.

Cheklistdan **kerakli qismi** olinadi (`_compliance_snapshot`): xulosa va
bandlar holati. To'liq javobdagi `evidence` (tender matnidan olingan uzun
dalil) taklif tarixida kerak emas.

Taklif **o'chirilmaydi va tahrirlanmaydi**. Xato bo'lsa yangi versiya:
`UNIQUE (opportunity_id, version)`.

---

## 3. Paket — "hozir topshirsam bo'ladimi?"

`GET /erp/opportunities/{id}/submission` bitta javobda beradi: narx hisobi
(tender-ai), cheklist (mijoz hujjatlariga qarab), mijoz hujjatlari,
manbadagi status va `warnings`.

**Tender-AI yiqilsa ham paket qaytadi**: yiqilgan qismlar `null`, sababi
`warnings` da. Broker savolga baribir javob olishi kerak.

Taklif narxi: qo'lda kiritilgani (`manual_price`) **ustun turadi** — u
xodimning yakuniy qarori, hisob esa tavsiya.

---

## 4. To'siq — OGOHLANTIRISH, taqiq emas

Cheklistda `blocking > 0` bo'lsa topshirish **taqiqlanmaydi**: hujjat
topshirish paytida tayyor bo'lishi mumkin va qaror odamniki
(`erp_bosqichlar.md` 4-bosqich shuni talab qiladi).

Lekin tasdiq **majburiy** va u yozib qo'yiladi:
- `submission.blocking_count` — o'sha paytda nechta to'siq bor edi;
- `submission.confirmed_note` — sabab (ixtiyoriy);
- kartaning **tarixida**: "Taklif topshirildi (v1); cheklistda 4 ta to'siq
  tasdiqlangan".

Tasdiqsiz urinish — **400** va `detail.blocking` bilan.

---

## 5. Manbadagi natija — TAKLIF, buyruq emas

`erp_bosqichlar.md` da "manbadan natija kuzatish — `won/lost` ni taklif
qilish, avtomatik o'zgartirmaslik" deyilgan.

**Manba g'olibni bermaydi.** `public.tender` da `winner` yoki natija ustuni
YO'Q; bor narsa — protsedura statusi (`open`, `close`, `cancel`, `expired`,
`not_realized`) va `contract_num`. Shuning uchun tizim "yutdik" yoki
"yutqazdik" ni **bila olmaydi** va taklif ham shunga mos:

> Tender manbada yopilgan (Отменён) — kartani yakunlash kerakmi?
> Natijani o'zingiz belgilaysiz.

`GET /erp/opportunities/{id}/tender-diff` javobiga `source` va
`suggest_close` qo'shildi (tender yakuniy, karta esa ochiq). Status
**avtomatik o'zgarmaydi** — sinov buni tekshiradi.

---

## 6. Sinov

```
.venv/Scripts/python.exe _tests/erp4_test.py     # 45 tekshiruv
```

Eng muhimi — **muzlatish sinovi**: taklif topshirilgach mijozga hujjat
qo'shiladi, jonli cheklist yaxshilanadi, muzlatilgan nusxa esa
O'ZGARMAYDI. Shuningdek: tasdiqsiz topshirish 400, tasdiq tarixga tushishi,
v1/v2 versiyalar, narxsiz va smetasiz topshirish 400, status avtomatik
o'zgarmasligi, chegara sinovi (`tender_pricing` ham tegilmagan).

---

## 7. Nima QILINMADI (4-bosqich chegarasi)

Taklif hujjatini (.pdf/.docx) yaratish, elektron imzo, manbaga topshirish
(platformaga ariza yuborish), narx hisobini ERP ichida tahrirlash (u
tender-ai da qoladi), g'olib ma'lumotini manbadan o'qish (manba bermaydi).
