# O'ZGARISHLAR JURNALI — "kim, qachon va nimani o'zgartirdi?"

Pul hujjatlari (hisob-faktura, dalolatnoma) uchun. Kod:
`api/erp/audit.py` (faqat **o'qish**), yozuvchi —
`schema_patch_erp_16.sql` dagi **trigger**.

---

## 1. Muammo: qoida bor edi, dalil yo'q edi

"Faktura `issued` bo'lgandan keyin o'zgarmaydi" — bu qoida kodda ham
(`invoice.py` dagi `_editable`), sinovda ham bor edi.

Lekin ikkalasi ham **faqat ilova orqali o'tgan** o'zgarishlarni
ushlaydi. Bazaga `psql` dan bitta `UPDATE` yozilsa:

* ilova qoidasi ishlamaydi — u umuman chaqirilmagan;
* hech qanday iz qolmaydi;
* "hujjat o'zgarmagan" degan gapni tasdiqlaydigan hech narsa yo'q.

Ya'ni tekshiruv bor edi, **dalil** yo'q edi.

---

## 2. NEGA TRIGGER, ILOVA KODI EMAS

Ilova qatlamidagi jurnal o'zi yozgan o'zgarishlarni yozadi. Bu — "men
hech narsa o'zgartirmadim" degan gapning **o'zi aytgan dalili**, ya'ni
dalil emas.

Trigger esa ma'lumot qayerdan kelishidan qat'i nazar ishlaydi: ilova,
`psql`, migratsiya skripti, boshqa dastur — hammasi bir xil.

Buning narxi ham bor va u ochiq: trigger har `INSERT/UPDATE/DELETE` da
qo'shimcha yozuv qiladi. Pul hujjatlari kamdan-kam o'zgaradi, shuning
uchun bu narx sezilarli emas.

Sinov ham shu mantiq bilan yozilgan: `erp10_test.py` **ataylab**
to'g'ridan-to'g'ri SQL yozadi. Agar u faqat ilova orqali yozsa, aslida
hech narsani tekshirmagan bo'lardi.

---

## 3. Kim o'zgartirdi (`actor`)

Bazada sessiya foydalanuvchisi yo'q — hamma ulanish bitta `postgres`
nomidan boradi. Shuning uchun ism ilovadan beriladi:

```python
db.execute_returning(SQL, actor="karimov", params={...})
#   -> SET LOCAL erp.actor = 'karimov'
#   -> trigger uni current_setting('erp.actor') dan o'qiydi
```

`SET LOCAL` — faqat o'sha tranzaksiya uchun: ulanish puldan qaytganda
qiymat qolib ketmaydi.

**`actor IS NULL` = "ERP dan tashqarida o'zgartirilgan".** Bu holat
yashirilmaydi va alohida sanaladi. Shuning uchun `db.py` da taxminiy
qiymat (`"system"`, `"erp"`) **ataylab qo'yilmaydi** — u haqiqiy ismni
ham, uning yo'qligini ham yashirardi.

---

## 4. `doc_status` — eng muhim ustun

Har yozuvda o'zgarish paytidagi hujjat holati saqlanadi. Aynan shu
ustun "chiqarilgan fakturaga tegilganmi?" degan savolga javob beradi.

**Hujjatning o'zi o'zgarganda ESKI holat yoziladi.** Aks holda
"qoralamadan chiqarildi" degan o'tishning **o'zi** "chiqarilgandan
keyin o'zgardi" bo'lib ko'rinardi va har faktura shubhali deb
belgilanardi — ro'yxat ma'nosini yo'qotardi.

Qator va to'lov uchun esa hujjatning joriy holati olinadi: ular hujjat
holatini o'zgartirmaydi, ya'ni joriysi = o'shandagisi.

---

## 5. Har o'zgargan ustun — ALOHIDA qator

`UPDATE` da JSON emas, har ustun uchun bitta yozuv:

| field | old_value | new_value |
|---|---|---|
| `number` | `F-2026-1` | `F-2026-SOXTA` |

Sabab amaliy: "kim narxni o'zgartirdi?" degan savolga javob bitta
`SELECT` bo'lishi kerak, JSON ichini titkilash emas.

`create` va `delete` da esa bitta yozuv va butun qator JSON ko'rinishida
saqlanadi — u yerda "qaysi ustun" degan savol yo'q.

---

## 6. Jurnalni o'zgartirib bo'lmaydi

O'zgartirilishi mumkin bo'lgan audit — audit emas.

* **`UPDATE` — butunlay taqiqlangan.** O'zgartirilgan yozuv soxta yozuv.
* **`DELETE` — faqat `erp.audit_purge = on`** bo'lganda. Bayroqni
  ataylab yoqish kerak, ya'ni tasodifan o'chib ketmaydi. U saqlash
  muddati tugagan yozuvlarni tozalash va sinovlar uchun.

Ikkalasini ham `erp.doc_audit` dagi `BEFORE UPDATE OR DELETE` trigger
majburlaydi.

---

## 7. FK ATAYLAB yo'q

`doc_id` hujjatga **bog'lanmagan**. `ON DELETE CASCADE` bo'lsa,
hujjatni o'chirish uning tarixini ham o'chirardi — ya'ni izni
yo'qotishning eng oson yo'li ochiq qolardi.

Shuning uchun faktura o'chirilgandan keyin ham uning butun tarixi
jurnalda qoladi (o'chirish faktining o'zi ham yoziladi).

---

## 8. Nima kuzatiladi

`erp.invoice`, `erp.invoice_line`, `erp.invoice_payment`, `erp.act`,
`erp.act_line` — beshta jadval. Sinov beshalasida ham trigger
turganini tekshiradi: bittasi tushib qolsa, o'sha yo'l **jimgina** iz
qoldirmay qolardi.

Shartnoma va ombor bu yerga kirmaydi: birinchisi pul hujjati emas
(summasi bor, lekin u kelishuv), ikkinchisining o'zi allaqachon jurnal
(`erp.stock_move` — harakatlar o'chirilmaydi).

---

## 9. Endpointlar

| Endpoint | Nima beradi |
|---|---|
| `GET /erp/audit` | Oxirgi o'zgarishlar + yig'ma javob. Filtrlar: `days`, `doc_type`, `only_frozen`, `only_outside` |
| `GET /erp/audit/{doc_type}/{doc_id}` | Bitta hujjatning butun tarixi |

Ikkalasi ham **`menejer`** (va undan yuqori) huquqini talab qiladi: jurnalda pul
hujjatlarining ichki tarixi bor.

Javobdagi `clean` — "shubhali o'zgarish yo'q". U ataylab bor: bo'sh
ro'yxat "tekshirilmadi" degani emas va ekranda ham shunday yoziladi.

---

## 10. Sinov

`_tests/erp10_test.py` — 35 tekshiruv:

* beshta jadvalda trigger borligi;
* ilova orqali qilingan o'zgarishda ism jurnalga tushishi;
* **chiqarish amalining o'zi** shubhali deb belgilanmasligi;
* **qo'lda yozilgan `UPDATE`** ham yozilishi, `after_issue` va
  `outside_erp` belgilanishi, eski/yangi qiymat saqlanishi;
* jurnal yozuvini o'zgartirib va bayroqsiz o'chirib bo'lmasligi;
* hujjat o'chirilgach ham tarix qolishi;
* to'lovning ham kuzatilishi;
* `public.*` da ERP triggeri yo'qligi (chegara qoidasi).
