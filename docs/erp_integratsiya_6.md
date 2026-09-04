# INTEGRATSIYA 6 — SHARTNOMA-VIEW'LAR (ERP → Tender-AI)

**Patch:** `schema_patch_erp_19.sql` · **Sinov:** `_tests/erp15_test.py` ·
**Asos:** `erp_rollar.md` §7, §9 (ochiq qarzlar №1, №5, №6)

---

## 1. Nima o'zgardi

Auth-3 dan beri Tender-AI ERP dan **bitta** view o'qirdi
(`erp.v_tender_status`, `erp_auth.md` §8.4). Endi ular to'rtta:

| View | Nima uchun | Holati |
|---|---|---|
| `erp.v_tender_status` | "Bu tender ishga olinganmi, kim ishlayapti" | **kengaydi** — `assignee_full_name` |
| `erp.v_tai_actor` | Hodimlar: Tender-AI aktor xaritasini shundan to'ldiradi | **yangi** (qarz №1) |
| `erp.v_stock` | Ombor qoldig'i — tender pozitsiyalari bilan solishtirish | **yangi nom** |
| `erp.v_client_document` | MIJOZ hujjatlari — cheklist ular bo'yicha yuritilsin | **yangi** (qarz №5) |

Yo'nalish o'zgarmadi: **Tender-AI `erp.*` ga yozmaydi**, ERP `public.*`
ga yozmaydi. Ikkalasi ham o'z tomonida yozadi, qarshi tomon view dan
o'qiydi.

---

## 2. Nega aynan view

View — **ataylab shartnoma**. Tender-AI `erp.opportunity` ning
ustunlariga emas, view ning shakliga bog'lanadi: ERP ichida ustun nomi
o'zgarsa yoki jadval bo'linsa, view moslashtiriladi va ikkinchi tomon
umuman sezmaydi.

Shuning uchun ikki qoida:

1. **Ustun faqat OXIRIGA qo'shiladi** — eski o'quvchi buzilmaydi.
2. **Shakl sinovda qulflangan** (`_tests/erp15_test.py` → `SHAKL`).
   Tender-AI sinovlari boshqa repozitoriyda va bu yerda ishlamaydi;
   shartnomani buzganini SHU sinov aytadi.

---

## 3. Maxfiylik chegarasi

View faqat kerakli ustunni beradi. **Berilmaydi:** parol xeshi, email,
sessiya, summa, izoh, `win_probability`, tannarx, hujjat fayli.
Sinov ularning yo'qligini ro'yxat bo'yicha tekshiradi (`TAQIQ`).

`tai_app` roliga faqat shu view larga `SELECT` berilgan; **birorta
jadvalga huquq yo'q** va buni ham sinov tekshiradi.

---

## 4. Nega `v_stock` va `v_stock_balance` — ikkalasi

`v_stock_balance` — ERP ning O'Z ekrani uchun (`api/erp/stock.py`),
`v_stock` — tashqi yuza: ustunlari sanab o'tilgan, ya'ni ichkarida
yangi ustun paydo bo'lsa u shartnomaga O'ZIDAN o'tmaydi. Nomi
hujjatdagi bilan bir xil (`erp_rollar.md` §3.3).

Qayta nomlash mumkin emas edi: `v_stock_balance` ga Tender-AI
allaqachon ulangan va ERP ekrani ham undan o'qiydi.

---

## 5. Tender-AI tomonida nima qilinadi

1. `actor` xaritasini `erp.v_tai_actor` dan to'ldirish (operator
   tasdig'i bilan) — **ochiq qarz №2**, `own_company` ↔
   `company_account` mosligi.
2. `ErpLink` da `assignee_full_name` ni ko'rsatish (ixtiyoriy).
3. Cheklistda `erp.v_client_document` ni ishlatish — hozir ERP
   hujjatlarni HTTP orqali yuboradi (`api/tenderai.py` → `compliance`),
   view esa **aynan o'sha ro'yxatni** beradi, ya'ni o'tish bir
   tomonlama va sezilmaydigan.
4. `aktor_majburiy` ni yoqish — 1 va 2 bajarilgandan **keyin**
   (qarz №3).

---

## 6. Hali qilinmagani

`erp_rollar.md` §5 dagi **yo'naltirish oqimi** (Tender-AI →
`tender_topshiriq` → `v_erp_topshiriq` → `pg_notify` → ERP `LISTEN`)
shu patchga kirmadi: u Tender-AI repozitoriysida jadval va migratsiya
talab qiladi. Shu paytgacha karta ERP da qo'lda ochiladi
(`POST /erp/tenders/{id}/take`, rahbar yoki menejer).

Shuningdek ochiq: ERP rolining `public.*` o'qishini ikki view'ga
toraytirish (qarz №6) — u yo'naltirish oqimi bilan birga bajariladi.
