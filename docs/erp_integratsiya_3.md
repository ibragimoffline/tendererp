# Integratsiya — ERP 3-BOSQICH: vazifalar, eslatmalar, yutqazish sabablari

`erp_bosqichlar.md` 3-bosqichining bajarilgan holati. ERP endi alohida
loyiha (`erp_arxitektura_2.md`), shuning uchun rejadagi bir qaror o'zgardi —
pastda 4-bo'limda.

**Maqsad:** karta "esdan chiqadigan" narsadan "eslatib turadigan" narsaga
aylanadi. Rahbar esa "nega yutqazdik?" degan savolga raqam bilan javob oladi.

---

## 1. Fayllar

| Fayl | Holat | Vazifasi |
|---|---|---|
| `schema_patch_erp_3.sql` | yangi | `opportunity_task`, `lost_reason`, `reminded_at` |
| `api/erp/tasks.py` | yangi | vazifa CRUD, "mening ishlarim", eslatma tanlovi |
| `api/erp/remind.py` | yangi | eslatma skripti (jadval bo'yicha yuriladi) |
| `api/erp/opportunity.py` | o'zgardi | `LOST_REASONS`, `set_status(..., lost_reason)` |
| `register_erp_task.ps1` | yangi | Windows Task Scheduler ga qo'yish |
| `_tests/erp3_test.py` | yangi | 58 tekshiruv |
| `frontend/.../TaskList.tsx` | yangi | kartadagi vazifalar bloki |
| `frontend/.../MyTasksPage.tsx` | yangi | "Mening ishlarim" bo'limi |
| `frontend/.../StatusChangeDialog.tsx` | o'zgardi | `lost` da sabab tanlash |

Tender-AI tomonida: **bitta yangi endpoint** — `POST /notify/send`
(`INTEGRATSIYA.md` 8-bo'lim).

---

## 2. Baza

`erp.opportunity_task` — id, opportunity_id (CASCADE), title,
assignee_broker_id, due_at, done, done_at, note, **reminded_at**, created_by.

`erp.opportunity` ga ikki ustun: `lost_reason` (CHECK bilan, 7 kod) va
`deadline_reminded_at`.

**Eski `next_task` yo'qolmadi.** Patch ichida bir martalik va idempotent
ko'chirish bor (`INSERT ... SELECT ... WHERE NOT EXISTS`), ustunlarning
o'zi esa joyida qoladi — eski kartalar buzilmasin. Bizning bazada 5 ta
yozuv ko'chdi.

**`reminded_at` nega jadvalda, alohida "yuborilganlar" ro'yxatida emas:**
eslatma bitta yozuvga tegishli va uning hayoti shu yozuv bilan tugaydi.
Alohida jadval faqat qo'shimcha JOIN va tozalash ishi bo'lardi.

---

## 3. Vazifalar

- Javob har doim kartaning **butun ro'yxati** — interfeys qayta so'ramaydi.
- **Kechikkanini SERVER belgilaydi** (`overdue`): brauzer soati noto'g'ri
  bo'lishi mumkin, "kechikdi" degan xabar esa qarorga ta'sir qiladi.
- Mas'ul ko'rsatilmasa — vazifa **kartaning brokeriniki**. Aks holda eski
  `next_task` dan ko'chirilgan yozuvlar hech kimda ko'rinmasdi.
- **Muddat o'zgarsa `reminded_at` tozalanadi** (SQL'da, `IS DISTINCT FROM`):
  ko'chirilgan muddat jimgina o'tib ketmasin.
- Vazifa **o'chirilishi mumkin** — kartadan farqli o'laroq: bu ish rejasi,
  tarix emas.

Endpointlar: `GET/POST /erp/opportunities/{id}/tasks`,
`PUT/DELETE /erp/tasks/{id}`, `PATCH /erp/tasks/{id}/done`,
`GET /erp/my-tasks?broker_id=&days=`, `GET /erp/reminders?days=&deadline_days=`.

---

## 4. Eslatmalar — REJADAN CHETGA CHIQISH

`erp_bosqichlar.md` da eslatma `run_etl.py` ga **post-qadam** sifatida
rejalashtirilgan edi. ERP alohida loyiha bo'lgach bu mumkin emas:
tender-ai ning ETL jadvaliga ulanish ikki loyihani qayta bir-biriga
bog'lab qo'yardi.

**Amalda:** ERP o'z jadvali bilan yuradi — `register_erp_task.ps1`
(Windows Task Scheduler, kuniga bir marta). Soatlik emas: "muddat yaqin"
xabari soatlik ma'lumot emas, tez-tez kelsa o'qilmay qoladi.

**Transport esa tender-ai'da qoldi.** SMTP rekvizitlari va Telegram bot
tokeni o'sha o'rnatmada; ularni ERP'ga nusxalash — sirni ikkinchi joyda
saqlash demakdir. Shuning uchun tender-ai `POST /notify/send` beradi va ERP
unga TAYYOR MATN yuboradi. Manzil yuborilmaydi va yuborib bo'lmaydi:
xabar faqat o'sha o'rnatmada sozlangan qabul qiluvchilarga ketadi
(endpoint ochiq relay bo'la olmaydi).

Skript qoidalari:
- **Bitta xabar** — hamma eslatma bir matnga yig'iladi (15 ta alohida
  bildirishnoma o'qilmaydi).
- **Yuborilmasa belgilanmaydi** — tender-ai javob bermasa keyingi yurishda
  qayta uriniladi.
- `--dry-run` — topilganini ko'rsatadi, yubormaydi va belgilamaydi.

```
.venv/Scripts/python.exe -m api.erp.remind --dry-run
.venv/Scripts/python.exe -m api.erp.remind --days 2 --deadline-days 5
powershell -ExecutionPolicy Bypass -File register_erp_task.ps1 -At 08:30
```

---

## 5. Yutqazish sabablari

7 ta kod (`price`, `deadline`, `documents`, `requirements`, `capacity`,
`client_declined`, `other`) — bazada CHECK, kodda `LOST_REASONS`, sinov
ikkalasini solishtiradi. `/erp/meta` ularni frontendga beradi.

- `lost` ga o'tishda sabab **majburiy** (interfeysda tugma bloklanadi).
- Boshqa statusga o'tilganda sabab **tozalanadi** — qayta ochilgan kartada
  eski sabab qolib ketmasin.
- Status o'zgarmasa-yu sabab o'zgarsa — sabab yoziladi, tarixga esa
  yozilmaydi (bosqich o'tishi bo'lmadi).
- Noto'g'ri kod **kodda** ushlanadi (400), bazadagi CHECK ga yetib bormaydi:
  u yerga tushsa 500 chiqardi.

---

## 6. Sinov

```
.venv/Scripts/python.exe _tests/erp3_test.py     # 58 tekshiruv
```

Qamrov: sabablar ro'yxati va CHECK mosligi, eslatma matnini yig'ish
(sanalar odam o'qiydigan ko'rinishda, HTML tegsiz), vazifa CRUD, kechikkan
belgisi, "mening ishlarim" guruhlari va broker filtri, eslatma tanlovi
(**belgilangach takror chiqmaydi**, muddat o'zgarsa qaytadan chiqadi),
dry-run hech narsa yozmasligi, yopilgan kartaning vazifasi eslatilmasligi,
sabab saqlanishi/tozalanishi, chegara sinovi.

**Xabar YUBORILMAYDI** — sinov faqat "kimga nima ketardi" ro'yxatini
tekshiradi, shuning uchun uni istalgan vaqtda yurgizish xavfsiz.

---

## 7. Nima QILINMADI (3-bosqich chegarasi)

Takrorlanuvchi vazifalar, vazifa bo'yicha izohlar tarixi, brokerga alohida
xabar (hozir hamma eslatma bitta manzilga ketadi — obunachilar tender-ai da
sozlangan), eslatma vaqtini foydalanuvchi sozlashi (hozir `.ps1` da),
KPI hisoboti (`opportunity_history` da ma'lumot bor, ko'rinish 5-bosqichda).
