# HUQUQLAR — kim nima qila oladi

**Manba:** `erp_rollar.md` (v2) §3 · **Kod:** `api/erp/perm.py`
(matritsa), `api/erp/egalik.py` (egalik), `api/erp/sozlama.py`
(kompaniya sozlamalari) · **Sinov:** `_tests/erp12_test.py`,
`_tests/erp13_test.py`, `_tests/erp14_test.py` · **Rollar:**
`erp_auth.md` §5

---

## 1. Muammo va yechim

Huquq tekshiruvi endpointlar bo'ylab tarqalgan edi: bir joyda
`require_role(user, "menejer")`, boshqasida `Depends(menejer)`, qolgan
yuzlab endpointda esa umuman yo'q. "Broker fakturani chiqara oladimi?"
degan savolga javob berish uchun `api/main.py` ni boshdan-oxir o'qish
kerak edi — va javob har safar boshqacha chiqardi.

Endi qoida bitta:

```python
_can(user, "hujjat.chiqarish")     # ruxsat bo'lmasa 403
```

Endpoint **qaysi amal** bajarilayotganini aytadi. **Kim** uni qila
olishi — faqat `api/erp/perm.py` dagi jadvalda. Endpoint ichida
`if rol == ...` yozilmaydi va buni sinov tekshiradi (3-bo'lim).

---

## 2. Darajalar

| Daraja | Ma'nosi |
|---|---|
| `full` | to'liq |
| `own` | faqat o'ziga biriktirilgani |
| `read` | faqat o'qish |
| `None` | yo'q (403) |

`can()` **darajani** qaytaradi, `require()` esa faqat "yo'q"ni to'sadi.
`require_write()` — `read` ni ham rad etadi.

### `own` nima degani — egalik zanjiri

Matritsa AMALNI biladi, obyektni bilmaydi. "Shu kartani" degan qism
`api/erp/egalik.py` da:

```
erp.app_user.broker_id  ->  erp.broker.id  ->  erp.opportunity.broker_id
```

Vazifa, shartnoma, rezerv, faktura va akt — hammasi kartaga borib
taqaladi. Kartasiz faktura/akt esa MIJOZ orqali ("shu mijoz bilan
mening kartam bormi") — aks holda broker o'zi chiqargan hujjatni
ko'ra olmasdi.

Endpointda ikki shakl:

```python
_can_obj(user, "karta.tahrirlash", "opportunity", opp_id)  # bitta obyekt
_oz_filtr(user, "karta.korish")                            # ro'yxat filtri
```

Begona obyekt — **403**, 404 emas: "yo'q" bilan "meniki emas"ni
ajratib ko'rsatish begona kartaning mavjudligini aytib qo'yardi.

**Hisob hodimga bog'lanmagan bo'lsa** (`app_user.broker_id IS NULL`)
"o'ziniki" — bo'sh to'plam: ro'yxatlar bo'sh, obyektlar 403. Bu
ataylab; muqobili sozlamadagi kamchilikni maxfiylik teshigiga
aylantirardi. Interfeys sababini ochiq yozadi.

---

## 3. Matritsa (qisqacha)

To'liq va aniq ro'yxat — `api/erp/perm.py`. Bu yerda mazmuni:

| Soha | admin | rahbar | menejer | broker |
|---|---|---|---|---|
| Kartalar: ko'rish | ko'r | ✓ | ✓ | o'z |
| Kartalar: yaratish, biriktirish, qaytarish | — | ✓ | ✓ | — |
| Kartalar: tahrirlash, status, yakunlash | — | ✓ | ✓ | o'z |
| Kartalar: qayta taqsimlashni **so'rash** | — | ✓ | ✓ | o'z |
| Mijoz: ko'rish | ko'r | ✓ | ✓ | o'z |
| Mijoz: passport, hujjatlar | — | ✓ | ✓ | — |
| Ombor: qoldiq | ko'r | ✓ | ✓ | ko'r |
| Ombor: kirim/chiqim | — | ✓ | ✓ | — |
| Ombor: rezerv | — | ✓ | ✓ | o'z |
| Pul hujjati: ko'rish, qoralama | ko'r / — | ✓ | ✓ | o'z |
| Pul hujjati: chiqarish, bekor, to'lov, eksport | — | ✓ | ✓ | — |
| O'zgarishlar jurnali | — | ✓ | ko'r | — |
| Kompaniya ko'rsatkichlari, foyda | ✓ / — | ✓ | ✓ | — |
| Hodim va hisoblar | ✓ | — | — | — |
| Kompaniya passporti | ✓ | ✓ | — | — |

**Nega broker karta yaratmaydi:** yo'naltirish qarori Tender-AI da
(`BrokerQueue`) va uni menejer yoki rahbar qabul qiladi
(`erp_rollar.md` §5). Broker — ijrochi.

---

## 4. Kompaniya sozlamalari

Matritsaning uch qatori har kompaniyada bir xil emas. Ular **kod
emas, sozlama**: qiymat `erp.setting` da, ta'rifi va standart qiymati
`api/erp/sozlama.py` da, huquqqa ulanishi esa `perm.SOZLAMAGA_BOGLIQ`
da. Administrator ularni "Hodimlar" ekranidan o'zgartiradi
(`GET/PUT /erp/settings`, amal — `tizim.sozlama`).

| Sozlama | Standart | Yoqilganda |
|---|---|---|
| `broker_can_close` | ha | Broker o'z kartasini yakunlaydi (yutildi / yutqazildi / rad). O'chirilsa — yakuniy qarorni faqat rahbar-menejer qo'yadi, broker kartani "topshirildi" gacha olib boradi |
| `menejer_foyda` | ha | Menejer kompaniya foydasini ko'radi (narx va marja bo'yicha qaror uchun). O'chirilsa — faqat rahbar va admin |
| `admin_faqat_koradi` | **yo'q** | Administrator biznes ma'lumotni o'zgartira olmaydi (ko'radi). **Yoqishdan oldin `rahbar` hisobi ochilsin**, aks holda kompaniya o'z ERP siga yozolmay qoladi |

Sozlama darhol kuchga kiradi (kesh 15 soniya) va kim o'zgartirgani
yoziladi: sozlama huquqni o'zgartiradi, ya'ni "kim yoqdi?" degan savol
keyinroq beriladi.

Interfeys ham bo'ysunadi: `broker_can_close` o'chiq bo'lsa yakuniy
statuslar ro'yxatdan chiqariladi va Kanban'da yakuniy ustunga sudrab
tashlab bo'lmaydi — bosilganda 403 beradigan variant yolg'on va'da
bo'lardi.

**`perm.OZ_FILTRI_TAYYOR`** — `own` obyekt darajasida filtrlanadimi
(kod bayrog'i, **yoqilgan**). Saqlangan sabab: egalik zanjiri
`erp.opportunity.broker_id` ga tayanadi va ma'lumot ko'chirishda
zanjir vaqtincha uzilsa, filtrni bir joydan o'chirib turish mumkin
bo'lsin.

---

## 5. Interfeys

Server matritsani `GET /erp/auth/me` javobida `perms` maydonida
beradi (`perm.for_user`). Ekran undan foydalanadi:

```tsx
import { can } from './erpShared'
{can('ombor.harakat') && <Button …/>}
```

**Bu himoya emas** — himoya serverda, har so'rovda. Bu ko'rinish
qoidasi: bosilganda 403 beradigan tugma — yolg'on va'da. Ro'yxat
ekranda takrorlanmaydi: u serverdan keladi.

---

## 5b. BAZADAGI huquq — `erp` roli

Matritsa ILOVA ichidagi huquq. Undan pastda yana bir qatlam bor:
`erp` DB roli `public.*` dan **faqat olti obyektni o'qiydi** va
hech qayerga yozmaydi (`schema_patch_erp_23.sql`, ochiq qarz №6):

```
tender, dim_status, dim_area      — karta snapshoti
v_tender_manba                    — manbadagi e'lon havolasi
catalog_product                   — ombor: mahsulot nomi va tannarxi
v_erp_topshiriq                   — Tender-AI yo'naltirishi
```

Ro'yxat **koddan olingan** va `_tests/erp18_test.py` uni kod bilan
solishtiradi: yangi jadval o'qilsa, grant ham yangilanishi kerak.

**Himoya hali yoqilmagan:** ilova `postgres` bilan ulanadi, ya'ni
cheklovlar unga tegmaydi. Yoqish — operator qadami (`ALTER ROLE erp
LOGIN PASSWORD ...` + `.env` dagi `XT_DB_DSN`), va `check_setup.py`
buni ogohlantirish sifatida ko'rsatib turadi.

---

## 6. Ataylab tekshirilmaydigan endpointlar

`/health`, `/erp/meta` (lug'atlar), `/erp/auth/*`,
`GET /erp/own-company` (rekvizitlar hujjat chop etishda kerak),
`GET`/`POST /erp/brokers` (hodim lug'ati va formadagi tez qo'shish),
`GET /erp/document-types` (tender-ai lug'ati). Ro'yxat `api/main.py`
dagi `_can()` izohida ham bor — "unutilganmi yoki shundaymi?" degan
savol qolmasin.

---

## 7. Aniqlashtirilishi kerak

Manba hujjatdagi (`erp_rollar.md` §3) jadvalda ✓ va — belgilari
kodlash buzilgani uchun ajratib bo'lmadi. Uch katak **ehtiyotkorlik
tomoniga** o'girilgan edi va **2026-09-02 da egasi tomonidan
tasdiqlandi** — ya'ni quyidagilar endi qaror, taxmin emas:

| Amal | Qaror |
|---|---|
| `tizim.hodim` | faqat admin. Rahbarga berish OBYEKT darajasidagi shartni talab qiladi ("admin hisobidan tashqari") — kerak bo'lsa alohida ish sifatida qo'shiladi |
| `tizim.kompaniya` | admin va rahbar |
| `hisobot.foyda` menejer uchun | ochiq, lekin endi SOZLAMA (`menejer_foyda`) — kompaniya o'chirib qo'ya oladi |

---

## 8. Yangi amal qo'shish

1. `api/erp/perm.py` — `AMALLAR` ga qator (nom + har rol uchun daraja);
2. endpointda `_can(user, "yangi.amal")`;
3. kerak bo'lsa ekranda `can('yangi.amal')`;
4. `_tests/erp12_test.py` — `HOLATLAR` ga kamida ikki qator (ruxsat va
   rad).

Sinov jadvalning to'liqligini o'zi tekshiradi: rol tushib qolsa yiqiladi.
