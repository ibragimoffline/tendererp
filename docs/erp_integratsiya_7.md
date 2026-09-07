# INTEGRATSIYA 7 — YO'NALTIRISH OQIMI (Tender-AI → ERP, HTTP'siz)

**Patchlar:** ERP `schema_patch_erp_21.sql` · Tender-AI
`schema_patch_topshiriq.sql` · **Kod:** ERP `api/erp/topshiriq.py`,
Tender-AI `api/topshiriq.py` · **Sinov:** ERP `_tests/erp16_test.py`,
Tender-AI `_tests/topshiriq_test.py` · **Asos:** `erp_rollar.md` §5

---

## 1. Nima o'zgardi

Ilgari broker Tender-AI navbatida "Olindi" derdi va zanjir **shu
yerda uzilardi**: ERP kartani qo'lda ochardi — tenderni qidiradi,
mijozni tanlaydi, muddatni ko'chiradi. Qaror bir tomonda, ish
ikkinchisida, o'rtada esa odam.

Endi:

```
Tender-AI  BrokerQueue: "Olindi" + kimga + ustuvorlik + muddat
   │
   ├─► tender_topshiriq   (tahlil SNAPSHOTI bilan)
   │        │ trigger
   │        └─► pg_notify('erp_topshiriq', id)
   │
   └─► v_erp_topshiriq  ──o'qiydi──►  ERP: LISTEN + zaxira so'rov
                                        └─► erp.opportunity (karta)
                                            erp.opportunity_analysis
                                            erp.notification (hodimga)
```

**HTTP yo'q, service kaliti yo'q, CORS yo'q.** Baza bitta: har tomon
o'z jadvaliga yozadi, qarshi tomon view dan o'qiydi. Chegara qoidasi
buzilmaydi va ikkala loyihaning sinovi buni tekshiradi.

---

## 2. Xabar — tezlik uchun, ishonchlilik uchun emas

`LISTEN` uzilishi mumkin (ulanish uzildi, ERP o'chirilgan edi,
migratsiya yurdi). Shuning uchun `sync()` xabardan **mustaqil**:
u view ni o'qiydi va "kartasi yo'q" topshiriqlarni topadi.
Tinglovchi har 60 soniyada (`ERP_TOPSHIRIQ_ORALIQ`) shu tekshiruvni
baribir yuritadi.

Ya'ni xabar yo'qolsa topshiriq **yo'qolmaydi** — kechikadi, xolos.
Qo'lda tortish ham bor: `POST /erp/topshiriq/sync`.

---

## 3. Operator qadamlari (ochiq qarz №2 — XARITALASH)

Oqim **xarita qo'yilmaguncha ishlamaydi**. Bu ataylab: xaritasiz
o'rnatma begona (yoki sinov) ijarachisining topshirig'ini o'ziniki
deb qabul qilmasligi kerak.

1. **Tender-AI da aktor yaratish** — har ERP hodimi uchun:
   `POST /aktor` → `{manba: "erp", erp_user_id: <ERP hisob id>, login,
   ism, rol}`. ERP hodimlari ro'yxatini Tender-AI `erp.v_tai_actor`
   view idan o'qiydi. Bu **operator qarori**, taxmin emas.
2. **ERP da ijarachini ko'rsatish** — ERP interfeysida:
   **Hodimlar → "Tender-AI ulanishi"** paneli: ijarachi id sini
   kiritib "Saqlash". Panel o'sha yerda holatni ham ko'rsatadi
   (tinglovchi ishlayaptimi, nechta topshiriq kutmoqda) va
   "Hozir sinxronlash" tugmasi bor.
   API bilan: `PUT /erp/topshiriq/xarita`
   → `{"tai_company_id": <company_account.id>}` (faqat administrator).
3. **Tekshirish**: o'sha panel, `GET /erp/topshiriq/holat` yoki
   `check_setup.py` — uchalasi ham "sozlanmagan" holatini ochiq
   aytadi.
4. Xarita to'liq bo'lgach Tender-AI da `aktor_majburiy` yoqiladi
   (ochiq qarz №3).

**Xaritalanmagan hodimga yo'naltirilgan karta yo'qolmaydi:** u
"Taqsimlanmagan" bo'lib ochiladi, menejerga xabar ketadi va
kartalar ekranidagi **"taqsimlanmagan"** filtri bilan topiladi.

---

## 4. Qoidalar (nega shunday)

| Holat | Nima bo'ladi | Nega |
|---|---|---|
| Hodim xaritalanmagan | Karta baribir ochiladi, `broker_id = NULL`, **menejerga xabar** | Topshiriqni tashlab yuborish eng yomoni: Tender-AI da "berildi", ERP da hech narsa |
| Karta allaqachon bor (qo'lda ochilgan) | Ikkinchisi ochilmaydi — mavjudi qarorga **bog'lanadi** | "Bir tender + bir mijoz = bir karta" qoidasi |
| Takror topshiriq | O'tkaziladi (`routing_id` UNIQUE ikkala tomonda) | Ikki karta = ikki ish |
| Tahlil yangilandi | Yangi snapshot qo'shiladi, **karta maydonlari tegilmaydi** | Hodim ularni o'zgartirgan bo'lishi mumkin — uning ishini bekor qilmaymiz |
| Qaror bekor qilindi (`olindi` → `rad`) | Karta **o'chmaydi**, `rejected` ga o'tadi + xabar | Kartada izoh, vazifa va tarix bo'lishi mumkin |
| Boshqa ijarachining topshirig'i | Jimgina o'tkaziladi | Bitta bazada bir necha ijarachi bo'lishi mumkin |

---

## 5. Tahlil — snapshot

`tahlil` JSONB qaror **paytida** hisoblanadi (Tender-AI
`api/topshiriq.py` → `tahlil_yig`) va keyin o'zgarmaydi. Bo'limlar:
moslik, AI qarori, malaka, talablar, cheklist, ombor, narx, havolalar.

- Har bo'lim alohida `try` ichida: biri yiqilsa qolganlari yoziladi va
  **sabab ko'rinadi** (`{"ok": false, "xato": "..."}`).
- Hajm chegarasi 60 KB; oshsa og'ir bo'limlar tashlanadi va buning
  sababi ham yoziladi.
- `localhost` havolasi **yozilmaydi** (`ommaviy_url` qoidasi).

ERP uni **qayta hisoblamaydi**: qoidalar Tender-AI da va ikkinchi
nusxasi bo'lmasligi kerak. ERP da faqat nusxa saqlanadi
(`erp.opportunity_analysis`) va `GET /erp/opportunities/{id}/tahlil`
orqali o'qiladi.

---

## 6. Tahlil ekranda

`TahlilPanel.tsx` kartada ko'rsatadi: sarlavhada sana va **ishonch
yorlig'i** (`aktor_elon` → "e'lon qilingan", "tasdiqlangan" DEB
KO'RSATILMAYDI), keyin sakkiz bo'lim. Ikki qoida ekranda ham amal
qiladi va ikkalasi ham ekran sinovida qulflangan:

1. **Yiqilgan bo'lim yashirilmaydi** — "ombor: olinmadi — <sabab>".
2. **Tasdiqlanmagan talab "ko'rilmagan" yorlig'i bilan** chiqadi
   (`UPDATED.md` §18: inson tasdig'i 0 marta ishlatilgan — yorliqsiz
   broker uni "tekshirilgan" deb o'qirdi).

Eski snapshotlar yo'qolmaydi: sarlavhadagi tugmalar bilan
ko'riladi ("broker qaysi ma'lumotga qarab ish boshlagan edi?").

---

## 7. Hali qilinmagani

- **Tashqi kanal** (email/Telegram) — bildirishnoma hozir faqat ERP
  ichida (`docs/erp_xabar.md` §5).
- **`aktor_majburiy`** — xaritalashdan keyin, operator qadami (№3).
- **30 ta eski qaror** (№7) — ularga aktor tayinlanmaydi, ERP'da
  qo'lda ochiladi.

`SOURCE_URL` lug'ati **o'chirildi**: manba havolasi endi
`v_tender_manba` dan olinadi (ikkinchi nusxa yo'q). ERP rolining
huquqlari **toraytirildi** (`schema_patch_erp_23.sql`, ochiq qarz
№6) — himoyani yoqish operator qadami.
