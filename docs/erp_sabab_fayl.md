# Sabab hujjati va "ulgurmadik" holati (24-patch)

> **Manba:** grill sessiyasi, 2026-09-04. Sakkiz savol, sakkiz qaror.
> **Kod:** `schema_patch_erp_24.sql`, `api/erp/fayl.py`,
> `frontend/src/components/erp/SababFayl.tsx`, `_tests/erp19_test.py`

---

## 1. Nima muammo edi

Karta yutqazilganda `lost_reason` yoziladi — ro'yxatdan **bitta kod**:
narx, muddat, hujjat, texnik talab, resurs, mijoz voz kechdi, boshqa.

Kod kerak va u qoladi: uni `GROUP BY` qilib bo'ladi, rahbar paneli
shundan hisoblaydi. Lekin u **"aynan nima bo'ldi"** degan savolga javob
bermaydi. Javob odatda hujjatda bo'ladi — buyurtmachi xati, raqobatchi
narxi, ichki xizmat yozuvi — va u hech qayerda saqlanmasdi. Broker uni
og'zaki aytardi, iz qolmasdi.

Ikkinchi muammo: muddat o'tib ketgan karta `preparing` da **abadiy**
qolardi. `analytics.py` uni "hozir shu bosqichda ishlanmoqda" deb
sanardi — ya'ni voronka va bosqich vaqti yolg'on raqam berardi.

---

## 2. Qarorlar

| # | Savol | Qaror | Nega |
|---|---|---|---|
| 1 | O'tish matritsasi kerakmi | `submitted` va `won` ga kirish oldingi statusni talab qiladi | `won` da `stock` rezervni **sarflaydi**; sakrash rezervsiz sarf berardi |
| 2 | Fayl qayerda | **`bytea`**, bazada | `backup_erp.ps1` faqat `pg_dump` — diskdagi papka zaxiraga tushmaydi |
| 3 | "Yakunlanmagan" | **O'z statusi**: `ulgurmadik` | `rejected` — bizning qaror, ulgurmaslik — natija |
| 4 | Kim qo'yadi | **Faqat odam** | 1-patchdan beri: tizim status qo'ymaydi |
| 5 | Fayl majburiymi | **Ixtiyoriy** | Majburiy bo'lsa bo'sh fayl yuklanadi → yolg'on ko'rsatkich |
| 6 | `lost_reason` qoladimi | **Qoladi** | Faylni `GROUP BY` qilib bo'lmaydi |
| 7 | O'chirish | **Ruxsat, iz bilan** | Xato yuklash tuzatilishi kerak; `doc_audit` yozadi |
| 8 | `ulgurmadik` yakuniymi | **Ha** | `stock.on_status_change` shunga qarab rezervni bo'shatadi |

---

## 3. Nima qurildi

### 3.1 Yangi status

`ulgurmadik` — "Ulgurmadik (muddat o'tdi)". **Yakuniy.** Ro'yxat uch
joyda mos turishi shart va sinov uchalasini solishtiradi:

| Joy | Nima |
|---|---|
| `api/erp/opportunity.py` → `STATUSES` | kod ro'yxati |
| `schema_patch_erp_24.sql` → `opportunity_status_check` | bazadagi CHECK |
| `erp.v_tender_status` → `CASE` | **tender-ai o'qiydigan shartnoma** |

Uchinchisi eng oson unutiladigan joy: u yerda status bo'lmasa
`status_label` NULL bo'lardi va tender-ai dagi `ErpLink` da karta
**nomsiz** ko'rinardi — jimgina, xatosiz. `erp_test.py` buni ushlaydi
(va qurish paytida haqiqatan ushladi ham).

### 3.2 Ro'yxat TAKRORLANMAYDI

Ilgari `closed_at` ni qo'yadigan SQL da `('won','lost','rejected')`
qo'lda yozilgan edi — ya'ni yakuniy statuslar ro'yxatining **uchinchi
nusxasi**. `ulgurmadik` qo'shilganda u jimgina tashqarida qolardi:
karta yakuniy bo'lardi, `closed_at` esa NULL.

Endi ro'yxat parametr sifatida koddan uzatiladi:

```python
FINAL           = {"won", "lost", "rejected", "ulgurmadik"}
SABAB_HOLATLARI = FINAL - {"won"}    # `won` da "nega yutqazdik" yo'q
```

`api/erp/fayl.py` `SABAB_HOLATLARI` ni **import qiladi**, o'zida
takrorlamaydi.

### 3.3 O'tish sharti

```python
KIRISH_SHARTI = {
    "submitted": {"preparing"},
    "won":       {"submitted"},
}
```

To'liq matritsa **ataylab emas**: `sent_to_client` va `confirmed`
mijozli kartalarga tegishli va mijozsiz kartada o'tkazib yuboriladi —
qattiq matritsa ularni majburiy qilib qo'yardi.

Ruxsatsiz o'tish → **409** va sabab bilan: *"'Yutildi' holatiga faqat
'Topshirildi' dan o'tish mumkin (hozir: 'Yangi')"*.

**Yon ta'sir, tuzatildi:** `submission.create()` avval taklifni yozib,
keyin `set_status` chaqirardi. O'tish sharti faqat o'sha yerda
tekshirilsa, 409 taklif yozilgandan **keyin** chiqardi va u yetim
qolardi (taklif muzlatilgan, o'chirilmaydi). Tekshiruv yozishdan
oldinga ko'chirildi. Ikkinchi versiya (`submitted` → `submitted`)
ruxsat etiladi — bu 4-bosqichning "yangi versiya" qoidasi.

### 3.4 Fayl

`erp.opportunity_file` — `bytea`, 10 MB chegara **bazada** (ilova
chetlab o'tilsa ham ishlaydi), turlar oq ro'yxatda (`api/erp/fayl.py`
→ `TURLAR`), `UNIQUE (opportunity_id, sha256)` takror yuklashni to'sadi.

Biriktiriladi: `lost`, `rejected`, `ulgurmadik`. O'chiriladi — **har
qanday holatda**: qayta ochilgan kartada ham xato yuklangan fayl
ushlanib qolmasligi kerak.

### 3.5 Jurnal — yangi kod YOZILMADI

16-patchdagi `erp.doc_audit_write()` triggeriga oltinchi tarmoq
qo'shildi. Yangi jurnal jadvali yaratilmadi: ikkita jurnal ikkita
haqiqat manbai bo'lardi.

Ikki muhim tafsilot:

1. **Baytlar jurnalga tushmaydi.** Trigger `to_jsonb(NEW)` dan
   `- 'baytlar'` qiladi. Usiz 10 MB lik fayl `doc_audit.new_value` ga
   20 MB hex satr bo'lib yozilardi. O'lchandi: 200 KB lik fayl uchun
   jurnal yozuvi **264 belgi**.
2. **`doc_status` = kartaning holati.** "Fayl qaysi holatdagi kartadan
   o'chirildi?" degan savolga to'g'ridan-to'g'ri javob.

`actor` `SET LOCAL erp.actor` orqali uzatiladi. Usiz jurnalda `NULL`
qolardi va u **"ERP dan tashqarida o'zgartirilgan"** degan ma'noni
bildiradi — ya'ni o'z yozuvimizni begona qilib ko'rsatardik.

### 3.6 Ekran

`SababFayl.tsx`. Uchta qoida faqat shu yerda ushlanadi:

- Fayl yo'q bo'lsa **"yo'q — biriktirilmagan"** deb yoziladi. Jimgina
  bo'sh joy "biriktirilmagan" degani ham, "bunday narsa yo'q" degani
  ham bo'lib ko'rinardi.
- Ochiq kartada yuklash maydoni yo'q va **sababi yoziladi**.
- Patch qo'llanmagan bo'lsa blok **umuman ko'rsatilmaydi**.

Turlar, hajm chegarasi va holatlar ro'yxati **serverdan** (`/erp/meta`)
— ekran o'z lug'atini tutmaydi.

---

## 4. O'lchov

`GET /erp/files/qamrov` → *"Yopilgan N kartadan M tasida sabab hujjati
bor"*.

Foiz **10 tadan kam yopiq kartada berilmaydi**: 2 ta kartada "50%"
ma'nosiz raqam. Bu `MOSLIK_MIN` bilan bir qoida.

Funksiya ishlatilyaptimi degan savolga javob shu raqamdan chiqadi. Bir
oy nol tursa — bu funksiya kerak emas ekan, keyingisini qurishdan oldin
shuni ko'rish kerak.

---

## 4b. Ochiq qolganlar YOPILDI

Boshida uchtasi ochiq qoldirilgan edi; keyin uchalasi ham qilindi.

### Eskalatsiya (`remind.py`)

Status faqat odam tomonidan qo'yilgani uchun kartani hech kim
yopmasligi mumkin. Endi kunlik eslatmada alohida bo'lim bor:

```
MUDDATI O'TGAN, YOPILMAGAN (7) — kartani yoping:
  • Дизель-генератор ... — 10 kun oldin tugagan · S. Rahimova
  ...
  Holat: yutqazildi / rad etildi / ulgurmadik.
```

Birinchi yurishda **7 ta karta** topildi — ular voronkani shishirib
turgan ekan.

Ikki qaror bor:

* **Bildirishnoma karta boshiga emas, BITTA yig'ma.** Ro'yxat karta
  yopilmaguncha har kuni qaytadi; har kartaga alohida xabar bir hafta
  ichida qutini to'ldirardi va odam hammasini o'qimay yopishni odat
  qilardi — shundan keyin haqiqiy xabar ham ko'rinmay qolardi.
* **Ro'yxat 10 ta bilan cheklangan** (`MAX_KECHIKKAN`), qolgani "va
  yana N ta". 40 qatorlik xabarni hech kim o'qimaydi.

### Voronka ajratildi (`analytics.py`)

`ongoing_n` endi **`faol_n` + `kechikkan_n`**. Eski nom saqlandi.
Jadvalda ikki ustun: "Faol" va "Muddati o'tgan".

Haqiqiy raqamlar buni oqladi:

| Bosqich | Jami | Faol | Muddati o'tgan |
|---|---|---|---|
| `new` | 3 | 2 | 1 |
| `sent_to_client` | 1 | 0 | 1 |
| `confirmed` | 2 | 0 | 2 |
| `preparing` | 1 | 0 | 1 |
| `submitted` | 2 | 0 | 2 |

Ya'ni "9 ta karta ishlanmoqda" degan raqam aslida **2 ta**.

### Sabab majburiy

`lost`, `rejected`, `ulgurmadik` — uchalasida ham sabab shart. Tekshiruv
**serverda** (`set_status`), ekranda esa tugma oldindan o'chiq turadi.
`won` bundan tashqarida.

`topshiriq.py` da Tender-AI yo'naltirishni bekor qilganda karta
`rejected` bo'ladi — u endi `other` sababi bilan yopiladi. Yangi kod
qo'shilmadi: `lost_reason` — broker tanlaydigan ro'yxat va unga tizim
sababini qo'shish odam ko'radigan tanlovni chalg'itardi.

### Yo'l-yo'lakay: ro'yxatning YETTITA takror nusxasi

`ulgurmadik` qo'shilishi bilan ma'lum bo'ldiki, `('won','lost',
'rejected')` kodda **sakkiz joyda** qo'lda yozilgan ekan:

| Fayl | Nima buzilardi |
|---|---|
| `opportunity.py` — `closed_at` | karta yakuniy, `closed_at` NULL |
| `opportunity.py` — `open_only` | yopilgan karta "ochiq" ro'yxatda |
| `tasks.py` ×3 | yopilgan kartaning vazifasi eslatilardi |
| `analytics.py` ×2 | voronka va "qotib qolganlar" da sanalardi |
| `stats.py` ×3 | "ochiq kartalar" soni va summasi noto'g'ri |
| `clients.py` ×2 | mijoz sahifasida ochiq kartalar noto'g'ri |

Hammasi endi `FINAL` dan parametr sifatida keladi. Hech biri xato
bermasdi — **jimgina noto'g'ri raqam** berardi.

---

## 5. Nima QURILMADI

- **Tizim `ulgurmadik` ni avtomatik qo'yishi.** Qaror: faqat odam.
  Buning o'rniga eslatma eskalatsiyasi (§4b) — tizim so'raydi, odam
  hal qiladi.
- Fayl ko'rish/oldindan ko'rish (preview), versiyalash, papkalar.
- Fayl `won` kartaga ham biriktirilishi — so'ralmadi.
