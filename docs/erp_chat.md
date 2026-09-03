# ERP — ICHKI CHAT (hodimlar muloqoti)

> Kodlash: UTF-8. Bu hujjatda maxsus belgilar ATAYLAB kam ishlatiladi —
> jadvallarda `+` / `oz` / `-` so'zlari, "tik" belgisi emas. Sabab: hujjat
> ikki marta cp1252 sifatida o'qilib buzilib keldi (`—` -> `â`, `§` -> `Â§`,
> `·` -> `Â·`) va shu sababli birinchi nusxa repoga qo'yilmagan edi.
> Tahrirlashdan keyin `file -i docs/erp_chat.md` -> `charset=utf-8`
> bo'lishi shart. `.gitattributes` da `*.md text eol=lf` turadi.

Talab: (1) rahbar va hodimlar o'rtasida **umumiy** chat; (2) har ish
(opportunity) bo'yicha biriktirilgan hodim bilan **alohida** chat;
(3) chatga hodim **qo'shish/chiqarish**; (4) xabarni **tahrirlash/o'chirish**.

Chat — **ERP tushunchasi**: hodimlar faqat ERP'da (`erp.app_user`).
Tender-AI'dagi `ChatPanel` (RAG, AI bilan suhbat) boshqa narsa — unga
tegilmaydi. ERP'da bo'lim nomi "Muloqot". Chegara o'zgarmaydi: chat
`public.*` ga tegmaydi, `tai_app` roliga chat obyektlari berilmaydi.

**Holat (2026-09-04):** qurilgan va yurgizilgan —
`schema_patch_erp_25.sql`, `api/erp/chat.py`, 11 endpoint, `Muloqot.tsx`,
`_tests/erp_chat_test.py` (88 tekshiruv). Qurilish jurnali va chetlanishlar
sabablari: `docs/erp_chat_qurilish.md`.

---

## 1. Chat turlari

| Turi | Kim uchun | A'zolik |
|---|---|---|
| `umumiy` | butun kompaniya | virtual: barcha faol hodimlar avtomatik. Chiqib bo'lmaydi, qo'shib bo'lmaydi — a'zo yozuvlari yuritilmaydi |
| `opportunity` | bitta ish (karta) atrofida | ro'yxatli: karta ochilganda avtomatik — biriktirilgan hodim + yo'naltirgan menejer/rahbar; keyin qo'shish/chiqarish mumkin |

- `umumiy` bitta dona, patch bilan yaratiladi. Yangi hodim hech narsa
  qilmasdan uni ko'radi; deaktiv hodim ko'rmaydi (tarixi qoladi).
- `opportunity` chati kartaga 1:1 (`opportunity_id UNIQUE`). Karta yakuniy
  statusga o'tganda chat arxiv (faqat o'qish); yakuniydan qaytarilsa ochiladi.
- Shaxsiy (1:1) chat — ataylab yo'q (§7).
- Karta chatiga tizim xabarlari avtomatik tushadi (muallif `NULL` = tizim,
  tahrirlanmaydi/o'chirilmaydi): status o'zgardi, hodim almashdi,
  Tender-AI'dan yo'naltirildi/bekor qilindi.

---

## 2. Huquqlar

Belgilar: `+` mumkin · `oz` faqat o'z xabari/kartasi · `-` mumkin emas.

> **Admin ustuni `admin_faqat_koradi = true` holatini tavsiflaydi.**
> Sozlama o'chiq bo'lganda (hozirgi standart, 17-patchdan beri) `perm.py`
> adminga hamma narsaga to'liq huquq beradi — ya'ni admin chatlarni ko'radi
> va yozadi. Bu ongli, oldinroq qabul qilingan qaror; chat uni o'zgartirmaydi.
> Sinov `can()` ni emas, shu matritsani tekshiradi — u sozlama yoqilganda
> xulq qanday bo'lishini qo'riqlaydi.
>
> **Yoqish tartibi (hal qilindi).** Savol "qachon yoqamiz" emas edi:
> hozir uni yoqib BO'LMAYDI, chunki bazada faol `rahbar` ham,
> `menejer` ham yo'q — yoqilsa kompaniyada biznes ma'lumotni
> o'zgartira oladigan hech kim qolmasdi. Tartib: rahbar hisobini
> oching -> faollashtiring -> shundan keyin yoqing.
>
> Himoya endi KODDA: `sozlama.saqla("admin_faqat_koradi", True)` faol
> rahbar/menejer bo'lmasa **400** qaytaradi va sababini aytadi. Ilgari
> u faqat izohda edi, ya'ni odam o'qishiga tayanardi — bu loyihada
> takrorlangan sinf ("izoh bilan himoyalangan qoida", `UPDATED.md`
> §16). O'chirish har doim mumkin: u huquqni kengaytiradi.

| Amal | admin | rahbar | menejer | broker |
|---|---|---|---|---|
| `umumiy` da o'qish/yozish | - (audit ko'r) | + | + | + |
| Karta chatini ko'rish | - (audit ko'r) | + hammasi | + hammasi | a'zo bo'lsa |
| Karta chatida yozish | - | a'zo bo'lgach | a'zo bo'lgach | a'zo bo'lsa |
| A'zo qo'shish | - | + | + | oz kartasida |
| A'zoni chiqarish | - | + | + | - |
| O'z xabarini tahrirlash | - | + | + | + |
| O'z xabarini o'chirish | - | + | + | + |
| Boshqa xabarini o'chirish (moderatsiya) | - | + | + | - |
| Boshqa xabarini tahrirlash | - | - | - | - |
| Arxiv chatda yozish | - | - | - | - |
| Tahrir tarixini ko'rish | + | + | - | - |

Qoidalar:

- Rahbar/menejer karta chatlarini a'zo bo'lmasa ham **ko'radi** (kartalarni
  ko'rish huquqi bilan izchil), lekin yozish uchun avval o'zini qo'shadi.
  Qo'shilish lentada tizim xabari sifatida ko'rinadi — "jimgina kuzatib
  turib yozish" bo'lmaydi.
- Biriktirilgan hodimni karta chatidan **chiqarib bo'lmaydi** (chat aynan
  u bilan muloqot uchun). Avval hodim almashtiriladi, keyin xohlasa chiqariladi.
- Broker o'z kartasiga hamkasb qo'sha oladi (maslahat so'rash); chiqarish —
  menejer/rahbar (nizoli amal boshliqda qolsin).
- Chiqarilgan a'zo yangi xabarlarni ko'rmaydi, o'zi yozganlari qoladi.
  Qayta qo'shilsa — chiqarilgan davr xabarlari ham ko'rinadi ("davr kesish"
  murakkabligi ataylab yo'q, §7).
- A'zo qo'shishda `app_user_id` **ixtiyoriy**: berilmasa so'rov yuborgan
  hodimning o'zi qo'shiladi. Eng ko'p uchraydigan holat — rahbarning o'zini
  qo'shishi; foydalanuvchi o'z hisob id sini bilishi shart emas.

---

## 3. Tahrirlash va o'chirish

- **Tahrir:** faqat o'z xabari, muddat cheklovisiz. Xabar yonida
  "tahrirlangan" belgisi; eski matn `chat_message_history` ga yoziladi.
  Tarixni rahbar va admin ko'radi. Tamoyil: o'zgartirish mumkin, **izsiz**
  o'zgartirish mumkin emas.
- **O'chirish yumshoq:** qator o'chmaydi, `deleted_at`/`deleted_by` to'ladi,
  lentada "Xabar o'chirildi (kim, qachon)" turadi. Matn oddiy foydalanuvchiga
  ko'rinmaydi, tarixda saqlanadi. Jismoniy o'chirish yo'q — hatto admin ham.
- Moderatsiyada (birovnikini o'chirish) izoh **majburiy** va muallifga
  `erp.notification` orqali bildiriladi.
- Tizim xabarlari tahrirlanmaydi va o'chirilmaydi.
- `reply_to_id` o'chirilgan xabarga ishora qilsa — "o'chirilgan xabarga
  javob" deb ko'rinadi, yo'qolmaydi.

---

## 4. Sxema — `schema_patch_erp_25.sql` (idempotent)

> Nomi `_erp_chat.sql` emas, `_25.sql`: `check_setup.py` patchlarni raqamli
> tartibda ro'yxatlaydi, raqamsiz nom ro'yxatdan tushib qolardi.

```sql
CREATE TABLE IF NOT EXISTS erp.chat (
    id             SERIAL PRIMARY KEY,
    turi           TEXT NOT NULL CHECK (turi IN ('umumiy','opportunity')),
    opportunity_id INT UNIQUE REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    title          TEXT,
    created_by     INT REFERENCES erp.app_user(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at    TIMESTAMPTZ,
    CHECK ( (turi = 'opportunity') = (opportunity_id IS NOT NULL) )
);
CREATE UNIQUE INDEX IF NOT EXISTS chat_umumiy_bitta ON erp.chat (turi) WHERE turi = 'umumiy';

CREATE TABLE IF NOT EXISTS erp.chat_member (
    chat_id     INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    app_user_id INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    added_by    INT REFERENCES erp.app_user(id),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_by  INT REFERENCES erp.app_user(id),
    removed_at  TIMESTAMPTZ,                  -- NULL = faol a'zo
    PRIMARY KEY (chat_id, app_user_id)
);

CREATE TABLE IF NOT EXISTS erp.chat_message (
    id          SERIAL PRIMARY KEY,
    chat_id     INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    author_id   INT REFERENCES erp.app_user(id),   -- NULL = tizim xabari
    text        TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
    reply_to_id INT REFERENCES erp.chat_message(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at   TIMESTAMPTZ,
    deleted_at  TIMESTAMPTZ,
    deleted_by  INT REFERENCES erp.app_user(id),
    delete_note TEXT
);
CREATE INDEX IF NOT EXISTS chat_message_lenta ON erp.chat_message (chat_id, id);

CREATE TABLE IF NOT EXISTS erp.chat_message_history (
    id          SERIAL PRIMARY KEY,
    message_id  INT NOT NULL REFERENCES erp.chat_message(id) ON DELETE CASCADE,
    amal        TEXT NOT NULL CHECK (amal IN ('tahrir','ochirish')),
    old_text    TEXT NOT NULL,
    by_user     INT REFERENCES erp.app_user(id),
    at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- chat_history_guard: UPDATE/DELETE trigger bilan to'siladi
-- (erp.doc_audit_guard naqshi, 16-patch).

CREATE TABLE IF NOT EXISTS erp.chat_read (
    chat_id      INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    app_user_id  INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    last_read_id INT NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, app_user_id)
);
```

**Ko'chirish (patch ichida):** mavjud kartalar uchun chat va a'zolar
yaratiladi; yakuniy statusdagi kartalar darhol arxivlanadi. (Amalda: 21 karta,
shundan 12 tasi arxiv.) Bu talabda yo'q edi — bo'lmasa eski kartalar chatsiz
qolardi va "chat faqat yangi kartalarda bor" degan tushunarsiz holat chiqardi.

Karta chatini yaratish — opportunity yaratilganda (`take()`). Hodim `NULL`
bo'lsa chat kartani ochgan odam bilan ochiladi va hodim tayinlanganda a'zo
qilib qo'shiladi (tizim xabari bilan).

---

## 5. API — `/erp/chats/*`

Hammasi ERP sessiyasi ostida; huquq `perm.can()` orqali (endpoint ichida
`if rol ==` yozilmaydi).

| Metod | Yo'l | Vazifasi |
|---|---|---|
| GET | `/erp/chats` | mening chatlarim + unread soni (umumiy birinchi) |
| GET | `/erp/chats/{id}/messages?after_id=&limit=&q=` | lenta (sahifalash `id` bo'yicha) |
| POST | `/erp/chats/{id}/messages` | yozish (`text`, `reply_to_id?`, `mentions[]?`) |
| PUT | `/erp/chats/{id}/messages/{mid}` | o'z xabarini tahrirlash |
| DELETE | `/erp/chats/{id}/messages/{mid}` | yumshoq o'chirish (`note` — moderatsiyada majburiy) |
| GET | `/erp/chats/{id}/members` | faol a'zolar |
| POST | `/erp/chats/{id}/members` | qo'shish (`app_user_id` ixtiyoriy — o'zini) |
| DELETE | `/erp/chats/{id}/members/{uid}` | chiqarish |
| PUT | `/erp/chats/{id}/read` | `last_read_id` yangilash (faqat oldinga) |
| GET | `/erp/chats/{id}/messages/{mid}/history` | tahrir tarixi (rahbar/admin) |
| GET | `/erp/opportunities/{id}/chat` | karta chatiga o'tish; chat yo'q bo'lsa **ochadi** |

Xato kodlari: a'zo emas -> 403; arxiv chatga yozish -> 400; biriktirilgan
hodimni chiqarish -> 400; o'zganing xabarini tahrirlash -> 403.

**Eslatish (`@ism`) — uch filtr, uchalasi ham ongli qaror:**

1. **Id bilan yuboriladi, matndan qidirilmaydi.** Matndan `@ism`
   qidirilsa bir xil ismli ikki hodimda bildirishnoma noto'g'ri odamga
   ketardi, umuman topilmasa esa jim qolardi.
2. **Faqat SHU CHATNING faol a'zolari.** Ekranda taklif ro'yxati
   `GET /erp/chats/{id}/members` dan quriladi (qo'shimcha endpoint
   yo'q) va faolsiz hodim ko'rsatilmaydi. A'zo bo'lmagan id server
   tomonda **jimgina tashlanadi**, 400 emas: bu foydalanuvchi tuzata
   olmaydigan holat (u ro'yxatdan tanlagan, oradan a'zo chiqarilgan
   bo'lishi mumkin) va xato qaytarsak uning XABARI sababsiz
   yuborilmay qolardi. Chatda yo'q odamni eslatmoqchi bo'lsa — avval
   qo'shadi.
3. **Takror yo'q.** Kimga yuborilgani `chat_message.eslatilgan`
   (26-patch) da qoladi. Bu TAHRIRDA muhim: "eslatishni unutdim,
   tahrirlab qo'shdim" ishlashi kerak, lekin har tahrirda hammaga
   takror ketsa odam bildirishnomalarni o'qimay yopishni odat
   qilardi — shundan keyin haqiqiy eslatish ham ko'rinmay qolardi.

**Matn va id bog'lanishi.** Tanlangach matnga `@Ism Familiya` yoziladi
va id mijozda eslab qolinadi. Yuborishdan oldin ro'yxat MATN bo'yicha
filtrlanadi: foydalanuvchi ismni o'chirgan bo'lsa id ham ketadi —
ko'rinmaydigan eslatish yuborilmasin. Server bunga ISHONMAYDI va
a'zolikni qayta tekshiradi (2-band).

**O'qilgan chegara faqat oldinga siljiydi** — `greatest(eski, yangi)`. Aks
holda eski sahifani ochish unread ni "tiriltirar" edi.

**Yangilanish:** polling 5 soniyada (`after_id` bilan). `pg_notify('erp_chat',
chat_id)` server tomonda **yoziladi** (`chat._signal`): xabar yozilganda,
tahrirlanganda va o'chirilganda. Tinglovchi hozir yo'q — WebSocket/SSE
qo'shilganda faqat u kerak bo'ladi. Signal yozish AYNAN hozir qilindi:
keyin qo'shilsa "qaysi joyda yozishni unutdik" degan savol paydo bo'lardi
va bir-ikkitasi albatta unutilardi — natijada WebSocket "ba'zan ishlaydi"
bo'lib qolardi, bu esa umuman ishlamasligidan yomonroq.

---

## 6. Interfeys va bildirishnoma

- Yon panelda "Muloqot" bo'limi (`Muloqot.tsx`): chapda chatlar ro'yxati
  (umumiy + kartalar, unread belgisi), o'ngda lenta. Karta oynasida
  "Muloqot" tabi — o'sha lentaning o'zi, chat ro'yxatisiz.
- Karta oynasidagi tab ataylab **yopiq** turadi: u polling yuritadi va har
  karta ochilganda avtomatik boshlansa, bir nechta ochiq oyna serverga
  bejiz so'rov yog'dirardi.
- Bildirishnoma (`xabar.py`, 3 tur): chatga qo'shildingiz; sizni eslatishdi;
  xabaringiz moderatsiyada o'chirildi (+izoh). Har xabarga bildirishnoma
  **yo'q** — unread hisoblagichi yetadi.
- Karta chatidagi tizim xabarlari `opportunity_history` bilan takrorlanadi —
  ataylab: tarix rasmiy jurnal, chat esa muloqot oqimi.

---

## 7. Ataylab yo'q

- Shaxsiy 1:1 chat va ixtiyoriy guruh yaratish.
- Fayl biriktirish (hujjatlar o'z joyida — chat matn).
- Reaksiyalar, "yozmoqda...", o'qilganlik belgilari.
- Xabarni jismoniy o'chirish.
- Chiqarilgan a'zodan tarixni yashirish.
- Tender-AI bilan bog'lanish: `tai_app` ga chat obyektlari berilmaydi.

---

## 8. Sinov — `_tests/erp_chat_test.py` (88 tekshiruv)

1. Umumiy chat bitta (baza darajasida ham); har kartada chat bor.
2. Broker begona karta chatini ko'rmaydi (403); a'zo qilingach ko'radi.
3. Rahbar a'zo bo'lmagan chatni o'qiydi, yozolmaydi; o'zini qo'shgach yozadi
   va qo'shilish lentada ko'rinadi.
4. Javob boshqa chatdagi xabarga bog'lanmaydi -> 400.
5. Tahrir: `edited_at` to'ladi, eski matn tarixda; o'zganikini -> 403.
6. O'chirish: matn lentada yo'q, qator bor; moderatsiyada izohsiz -> 400;
   muallifga bildirishnoma yozildi; rahbar matnni ko'radi.
7. Umumiy chatga a'zo qo'shish/chiqarish -> 400; takror qo'shish -> 409;
   faolsiz hisobni qo'shish -> 400.
8. Biriktirilgan hodimni chiqarish -> 400; boshqasi chiqadi, yozganlari
   qoladi; qayta qo'shilsa butun tarix ko'rinadi.
9. `chat_message_history` ga UPDATE -> trigger rad etadi.
10. Unread: `last_read_id` dan keyin sanaladi; o'z xabaring sanalmaydi;
    chegara orqaga ketmaydi.
11. Yakuniy status -> arxiv, yozish -> 400; qaytarilgach yoziladi; status
    o'zgarishi lentada tizim xabari bo'lib ko'rinadi.
12. Huquqlar **matritsasi** (§2) tekshiriladi — `can()` emas, chunki
    `admin_faqat_koradi` hozir o'chiq.
13. `pg_notify` — xabar yozilganda, tahrirlanganda va o'chirilganda
    signal ketadi (haqiqiy `LISTEN` ulanishi bilan tekshiriladi).
14. Eslatish: a'zoga ketadi; ikkinchi marta takror yo'q; a'zo
    bo'lmagan id jimgina tashlanadi; o'zini eslatish sanalmaydi;
    tahrirda YANGI id ga ketadi, eskisiga takror emas; kimga
    yuborilgani xabarda saqlanadi.
15. `ZZTEST` yozuvlari `finally` da tozalanadi; `public.*` qator soni
    o'zgarmagan.

Ekran sinovi (`qoidalar.test.tsx`, 10 qoida): o'chirilgan xabar yo'qolmaydi;
unga javob ko'rinadi; arxivda / a'zo bo'lmaganda / huquqsiz yozish maydoni
yo'q va SABABI yoziladi; tizim xabarida tugmalar yo'q; `@` ro'yxati
faqat faol a'zolardan va harf bo'yicha filtrlanadi; matndan ism
o'chirilsa `mentions` yuborilmaydi.

---

## 9. Ochiq qolgani

| Nima | Server | Ekran | Izoh |
|---|---|---|---|
| `@ism` tanlash ro'yxati | tayyor | **tayyor** | Bajarildi: taklif ro'yxati a'zolardan, matndan o'chirilsa id ham ketadi |
| Chat ichida qidiruv | tayyor (`?q=`) | yo'q | `ILIKE`, chat ichida |
| WebSocket/SSE | `pg_notify` yoziladi | yo'q | Polling 5 s yetarli; deploy talabi (Caddy/systemd) tufayli keyinga |
| `admin_faqat_koradi` yoqish | himoya qo'shildi | — | Yoqish uchun avval FAOL rahbar hisobi kerak (§2). Bu `check_setup.py` 9-bo'limidagi "birinchi real ma'lumot" qadami |
