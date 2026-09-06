# JAMOA va UMUMIY VAZIFALAR

**Patch:** `schema_patch_erp_28.sql` ·
**Kod:** `api/erp/jamoa.py`, `api/erp/tasks.py` ·
**Ekran:** `JamoaPanel.tsx`, `MyTasksPage.tsx`, `TaskList.tsx` ·
**Sinov:** `_tests/erp_jamoa_test.py` (137 tekshiruv),
`frontend/src/__tests__/jamoa.test.tsx` (19 tekshiruv) ·
**Asos:** `erp_rollar.md` §3.1, §3.6

---

## 1. Ikki muammo

**Vazifa faqat kartaga bog'lanardi.** `opportunity_id NOT NULL` edi,
ya'ni "sertifikatni yangilash" yoki "hisobot tayyorlash" degan oddiy
ish ERP da umuman yozilmasdi. Hodimning ishi ikki joyda yashardi:
tenderga tegishlisi ERP da, qolgani daftarda — va menejer "bu odam
nima bilan band?" degan savolga javob ololmasdi.

**Kartada yakka mas'ul.** Amalda bitta tenderda uch odam ishlaydi:
narxni biri hisoblaydi, hujjatni ikkinchisi yig'adi, texnik qismni
uchinchisi yozadi. Ular kartani **ko'ra olmasdi** ham — egalik
zanjiri `broker_id` ga tayanadi. Ya'ni ishlash uchun mas'ulning
hisobidan kirish kerak bo'lardi va bu auditning oxiri: har o'zgarish
bitta odam nomidan yozilardi.

---

## 2. Asosiy mas'ul qayerda qoladi

`erp.opportunity.broker_id` da, **o'zgarishsiz**. Yangi jadvalga
ko'chirilmadi:

* **bitta ustun = "ko'pi bilan bitta asosiy" invarianti** tuzilma
  darajasida. Jadvalga `asosiy BOOLEAN` qo'yilsa, uni qisman noyob
  indeks bilan qo'riqlash kerak bo'lardi va ikkita haqiqat manbai
  paydo bo'lardi;
* yigirmaga yaqin joy shu ustunga tayanadi (egalik zanjiri, ro'yxat
  filtri, analitika, eslatma, faktura egaligi) — ularni ko'chirish
  katta va foydasiz xavf edi.

`erp.opportunity_assignee` **qolgan** a'zolarni saqlaydi. Ikkalasi
boshqa-boshqa faktni saqlaydi, takrorlanmaydi; `jamoa.royxat()`
ularni birlashtiradi va asosiyni `asosiy: true` bilan belgilaydi.

---

## 3. Jamoa — huquq ham

A'zolik **uchta** narsani ochadi va ular bir joydan kelib chiqadi:

1. kartani ko'rish/tahrirlash (`egalik.py` zanjiri);
2. karta chatiga kirish (`chat_member` ga qo'shiladi);
3. karta vazifalarini olish (`tasks.royxat` egalik filtri).

Ya'ni "jamoaga qo'shish" — **yagona amal**, uchta joyda alohida
sozlash emas. Aks holda biri unutilardi va odam kartani ko'rib,
chatini ko'rmasdi.

**Chiqarish teskarisini qiladi:** huquq darhol yopiladi va odam
chatdan ham chiqariladi. **Yozganlari lentada qoladi** (chat moduli
qoidasi), a'zolik qatori esa `removed_at` bilan **saqlanadi** — "kim
qachon jamoada edi" degan savol javobsiz qolmasin.

**Asosiy mas'ul almashganda eskisi jamoada qoladi** (`kuzatuvchi`
bo'lib): u karta ustida ishlagan va konteksti kerak bo'lishi mumkin.
Uni butunlay chiqarish — alohida, ongli amal.

### Rollar

`masul` (hosil qilinadi) · `narx` · `hujjat` · `texnik` · `yuridik` ·
`kuzatuvchi`. Ro'yxat **qisqa va kodda**: o'ntadan ortiq rol
tanlanmay qolardi va hamma "kuzatuvchi" ni bosardi.

---

## 4. Vazifa: bitta model, ikki kontekst

`erp.opportunity_task` **kengaytirildi** (ikkinchi jadval emas):
`opportunity_id` endi `NULL` bo'lishi mumkin. Jadval nomi tarixiy —
3-patchda u faqat karta vazifasi edi.

    opportunity_id IS NULL  ->  UMUMIY vazifa
    opportunity_id bor      ->  TENDER vazifasi

Ekran ikkalasini **ajratib** ko'rsatadi (`kontekst` maydoni), lekin
komponent bitta: `GeneralTask.tsx` va `TenderTask.tsx` yaratilmadi.

### Holat

    yangi -> bajarilmoqda -> bajarildi
                          -> bekor
    (bajarildi/bekor -> yangi: qayta ochish)

**KECHIKKAN holat sifatida saqlanmaydi** — u `due_at` va statusdan
hisoblanadi. Saqlansa, uni har kecha yangilab turadigan skript kerak
bo'lardi va u bir kun yurmasa ekran yolg'on gapirardi.

**`done` ustuni qoldi**, lekin endi u `status` ning **ko'zgusi**:
trigger (`erp.task_done_mirror`) uni yuritadi. O'nga yaqin so'rov va
indeks unga tayanadi; ikki qiymat hech qachon ajralib ketmaydi —
hatto `psql` dan qo'lda yozilgan `UPDATE` da ham.

**Bekor qilish "bajarildi" dan ajraladi:** ilgari ikkalasi ham
`done = TRUE` edi va bajarilmagan ish bajarilgan bo'lib hisobotga
tushardi.

### Ustuvorlik

`low` / `medium` / `high` — **kartadagi bilan bir xil** shkala
(`opportunity.PRIORITIES`). Ikkinchi shkala kiritilsa ekranda
"O'rta" va "Normal" yonma-yon turardi.

---

## 5. Kim nima qila oladi

| Amal | Broker | Menejer/Rahbar | Admin |
|---|---|---|---|
| Jamoani ko'rish | o'z kartasi | ha | faqat o'qish |
| Jamoaga qo'shish | o'z kartasiga | ha | **yo'q** |
| Chiqarish / rol | **yo'q** | ha | **yo'q** |
| Asosiy mas'ul | **yo'q** (`karta.biriktirish`) | ha | **yo'q** |
| Umumiy vazifa yaratish | **o'ziga** | ha | **yo'q** |
| Boshqaga biriktirish | **yo'q** | ha | **yo'q** |
| Yuklama | **yo'q** | ha | faqat o'qish |

Broker o'z kartasiga hamkasb **qo'sha oladi** (maslahat so'rash uning
kundalik ishi), lekin **chiqarish** va **asosiy mas'ulni
almashtirish** nizoli amallar va ular boshliqda qoladi.

"O'ziga vazifa qo'yish mumkin, boshqaga yo'q" farqi matritsada emas,
**endpointda** (`_vazifa_biriktirish_huquqi`): matritsa amalni
biladi, obyektni bilmaydi.

Admin ish taqsimlamaydi (`erp_rollar.md` §3.6).

---

## 6. Bildirishnoma va tarix

Bildirishnoma **mavjud quvur** orqali (`api/erp/hodisa.py`,
`docs/erp_xabar.md`): `vazifa`, `jamoa_qoshildi`,
`jamoa_chiqarildi`, `jamoa_rol`, `otkazildi`. To'g'ridan-to'g'ri
`xabar.yoz()` chaqirilmaydi.

Qabul qiluvchi: yangi a'zo, chiqarilgan a'zo, yangi va **eski**
bajaruvchi. Amalni bajargan odam o'ziga xabar olmaydi.

Tarix **mavjud jurnalda**: `erp.doc_audit` (trigger bilan, chetlab
o'tib bo'lmaydi) — vazifa uchun `doc_type='vazifa'`, jamoa uchun
`doc_type='karta', entity='jamoa'`. Jamoa o'zgarishlari
`erp.opportunity_history` ga va chat lentasiga ham yoziladi.
Alohida `task_history` jadvali ochilmadi: ikkita jurnal ikkita
haqiqat manbai bo'lardi.

---

## 7. Yuklama

`erp.v_hodim_yuklama` — ochiq vazifa, kechikkan, bajarilgan, ochiq
karta (asosiy mas'ul **va** jamoa bo'yicha). **View, jadval emas:**
saqlangan ko'rsatkich haqiqatdan ajralib ketardi va aynan qaror
qabul qilinayotgan paytda yolg'on gapirardi.

Bu **baho emas** — reyting, ball yoki "samaradorlik" hisoblanmaydi.
Bunday ko'rsatkich odamni ishni tez yopishga undardi, sifatga emas.
Ekranda ham shu ochiq yozilgan.

---

## 8. API

| Metod | Yo'l | Vazifasi |
|---|---|---|
| GET | `/erp/tasks?kontekst=&status=&priority=&overdue=&q=` | barcha vazifalar, filtrlar bilan |
| POST | `/erp/tasks` | vazifa yaratish (`opportunity_id` ixtiyoriy) |
| GET | `/erp/tasks/{id}` · `/history` | bittasi · tarixi |
| PATCH | `/erp/tasks/{id}/status` | boshlash / bajarish / bekor / qayta ochish |
| PATCH | `/erp/tasks/{id}/assign` | qayta biriktirish |
| GET | `/erp/workload` | hodimlar yuklamasi |
| GET | `/erp/opportunities/{id}/assignees?tarix=` | jamoa |
| POST | `/erp/opportunities/{id}/assignees` | qo'shish |
| PATCH | `/erp/opportunities/{id}/assignees/{broker_id}` | rolni o'zgartirish |
| DELETE | `/erp/opportunities/{id}/assignees/{broker_id}` | chiqarish (yumshoq) |
| PUT | `/erp/opportunities/{id}/primary-assignee` | asosiy mas'ulni almashtirish |

Eski yo'llar saqlandi: `POST /erp/opportunities/{id}/tasks`,
`PATCH /erp/tasks/{id}/done`.

**Muallif so'rovdan olinmaydi.** `created_by` tanada qabul qilinadi
(eski mijozlar uchun), lekin server uni **sessiyadan** yozadi.

---

## 9. Ataylab yo'q

* **Bir vazifa — bir bajaruvchi.** Ko'p bajaruvchili vazifa "kim
  javobgar" degan savolni yo'qotardi; kerak bo'lsa ikkita vazifa
  yoziladi.
* **Soat aniqligidagi muddat.** `due_at` — `DATE`. Eslatma skripti
  kuniga bir marta yuriydi, ya'ni "2 soat qoldi" degan eslatma bu
  arxitekturada baribir yetib bormasdi.
* **Vazifa izohlari (chat).** Karta chati bor; umumiy vazifa uchun
  alohida yozishma tizimi ochilmadi.
* **Reyting va samaradorlik.** Yuqoridagi §7.
