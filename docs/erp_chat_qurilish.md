# Ichki chat — qurilish hisoboti (25-patch)

> **Manba:** `erp_chat.md` — talab hujjati, loyiha egasi bergan.
> U REPODA YO'Q (kelgan nusxada belgilar kodlashi buzilgan edi va
> buzilgan matnni repoga qo'yish uni "rasmiy" qilib ko'rsatardi).
> Talabning qaror qismi quyida to'liq keltirilgan.
> **Kod:** `schema_patch_erp_25.sql`, `api/erp/chat.py`,
> `frontend/src/components/erp/Muloqot.tsx`, `_tests/erp_chat_test.py`

Bu fayl talabdan **chetga chiqilgan** joylarni va nima uchunligini
yozadi. Qolgan hamma narsa `erp_chat.md` dagidek.

---

## 1. Chetga chiqishlar

| Talabda | Qurilganda | Nega |
|---|---|---|
| `schema_patch_erp_chat.sql` | `schema_patch_erp_25.sql` | `check_setup.py` patchlarni **raqamli tartibda** ro'yxatlaydi; nomsiz patch o'sha ro'yxatdan tushib qolardi |
| "`audit_jurnal` dagi naqsh" | `erp.doc_audit_guard` naqshi | Loyihada jurnal qo'riqchisi shu nomda (16-patch); yangi funksiya `erp.chat_history_guard` o'shanga aynan taqlid qiladi |
| `POST /erp/chats/{id}/members` — `app_user_id` majburiy | **ixtiyoriy** | Eng ko'p uchraydigan holat — rahbar **o'zini** qo'shadi. Mijoz o'z hisob id sini bilishi shart emas: u sessiyada bor |
| `@ism` matndan aniqlanadi | `mentions` — id lar ro'yxati | Matndan qidirilsa bir xil ismli ikki hodimda xabar **noto'g'ri odamga** ketardi, topilmasa esa jim qolardi |

---

## 2. Talabda yo'q, lekin qo'shildi

**Mavjud kartalar uchun chat.** Patch qo'llangunga qadar ochilgan 21 ta
karta chatsiz qolardi. Patch ularni ko'chiradi, a'zo sifatida mas'ulni
qo'shadi va **yopilgan 12 tasini darhol arxiv** qiladi. Idempotent.

**`GET /erp/opportunities/{id}/chat` chat yo'q bo'lsa OCHADI.** Patch
qo'llangandan keyin, lekin ilova yangilanmasidan oldin ochilgan karta
chatsiz qolishi mumkin. Interfeys "chat yo'q" degan tushunarsiz holat
ko'rsatgandan ko'ra ochib beradi.

**O'qilgan chegara ORQAGA ketmaydi** (`greatest(...)`). Ikki oyna ochiq
bo'lsa, eskisi yangisining o'qilganini bekor qilib hisoblagichni
"tiriltirib" yuborardi.

**Mas'ul almashganda yangisi chatga qo'shiladi.** Aks holda unga karta
berilardi-yu, u haqidagi butun yozishma ko'rinmasdi — aynan ishni qabul
qilib olayotgan paytda. **Eskisi chiqarilmaydi**: chiqarish alohida,
ongli amal.

---

## 3. Muhim tafsilotlar

### Yozish uchun a'zolik SHART — rahbar uchun ham

Rahbar chatni a'zosiz **o'qiydi** (`chat.hammasi`), lekin yozish uchun
o'zini qo'shadi va bu qo'shilish lentada tizim xabari bo'lib ko'rinadi.
"Jimgina kuzatib turib yozish" bo'lmaydi.

### Admin va matritsa

Matritsada admin uchun barcha chat amallari `None` (yagona istisno —
`chat.tarix`, nazorat jurnali). **Lekin** loyihada `admin_faqat_koradi`
sozlamasi o'chiq turganda `perm.can()` adminga hamma narsaga `full`
beradi — bu 17-patchdan beri amal qilgan, ongli qaror (bitta o'rnatmada
admin aynan ishni yuritayotgan odam). Chat matritsasi o'sha sozlama
**yoqilganda** kuchga kiradi. Sinov shuning uchun `can()` ni emas,
**matritsani** tekshiradi.

### Arxiv ro'yxati takrorlanmaydi

`ARXIV_HOLATLAR = FINAL` — alohida ro'yxat yozilmadi. 24-patchda
`ulgurmadik` qo'shilganda qo'lda yozilgan har bir nusxa uni jimgina
tashqarida qoldirgan edi (11 ta nusxa topilgan edi).

### Tizim xabari chaqiruvchini yiqitmaydi

`tizim_xabari()` va `karta_chati_yarat()` hech qachon `raise`
qilmaydi — karta statusini o'zgartirish chat yozuvidan muhimroq
(`xabar.yoz()` bilan bir xil qoida). Xato jurnalga tushadi.

### `_bitta()` — alohida so'rov

Bir vaqtlar bu yerda `LENTA_SQL` ni satr almashtirish bilan qayta
yasash bor edi. So'rov matni ozgina o'zgarganda u **jimgina bo'sh
natija** qaytardi: xato ham bermasdi, shunchaki "xabar yozildi, lekin
javob bo'sh" bo'lardi. Endi `BITTA_SQL` alohida turadi.

---

## 4. Tekshiruv

| | |
|---|---|
| `_tests/erp_chat_test.py` | **73** tekshiruv |
| Ekran sinovi | **5** yangi qoida (jami 47) |
| Backend jami | **1 287 / 1 287**, 0 xato |

Sinov to'rtta buzilish sinfini qo'riqlaydi: jim sizib chiqish (begona
broker), izsiz o'zgartirish (tahrir jurnali), yozilgan narsaning
yo'qolishi (o'chirilgan xabar, unga javob, chiqarilgan a'zoning
xabarlari), "jimgina kuzatib yozish".

---

## 5. Hali qilinmadi

- `pg_notify('erp_chat', chat_id)` — talabda "allaqachon yozilsin"
  deyilgan, hozir **yo'q**. So'rov (polling) ishlaydi; WebSocket
  qo'shilganda shu qator kerak bo'ladi.
- `@ism` tanlash interfeysi — server tomoni (`mentions`) tayyor,
  ekranda tanlash ro'yxati hali yo'q.
- Chat ichida qidiruv — server tomoni (`?q=`) tayyor, ekranda maydon yo'q.
