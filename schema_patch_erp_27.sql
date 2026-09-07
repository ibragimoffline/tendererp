-- =============================================================================
-- ERP 27-patch — BILDIRISHNOMA QUVURI (yetkazish, takrorlanmaslik, kuzatuv)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_27.sql
-- Talab: _22 (erp.notification), _25 (chat), _3 (opportunity_task).
--
-- MUAMMO. 22-patch bildirishnomani SAQLADI, lekin uni YETKAZISHNI
-- hech kim yozmadi. Bugungi holat uchta jim nuqsonga olib keladi:
--
--   1. TASHQI KANAL YO'Q, LEKIN USTUN BOR. `notification.yuborildi_at`
--      22-patchdan beri turibdi va HAR DOIM NULL. Ya'ni jadval
--      "yuborilmagan" deb turadi, hech kim esa yubormaydi.
--   2. TAKROR. Xabar yozish takrorlansa (qayta urinish, ikki marta
--      bosilgan tugma) IKKITA qator paydo bo'lardi — dedup kaliti yo'q.
--   3. NISHON FAQAT KARTA. Chatdagi xabar haqidagi bildirishnoma
--      bosilganda karta ochilardi, CHAT emas; umumiy chatda esa karta
--      umuman yo'q va bildirishnoma HECH QAYERGA olib bormasdi.
--
-- YECHIM: uchta qism — nishon ustunlari, yetkazish navbati (outbox) va
-- sozlama. Bildirishnoma jadvali QAYTA YARATILMAYDI: u ishlayapti va
-- ikkinchi nusxasi "qaysi biri haqiqiy" degan savolni tug'dirardi.
--
-- NEGA OUTBOX ALOHIDA JADVAL, `notification` GA USTUN EMAS:
-- bitta bildirishnoma UCH kanalga ketishi mumkin (ilova, email,
-- Telegram) va ularning holati BOSHQA-BOSHQA: email ketdi, Telegram
-- yiqildi. Bitta `yuborildi_at` ustuni bu farqni ifodalay olmaydi va
-- "yuborildi" degan yolg'on javob berardi.
--
-- `yuborildi_at` QOLDIRILADI (o'chirilmaydi): 22-patch qo'llangan
-- o'rnatmalarda u bor va uni tashlash orqaga qarab buzuvchi o'zgarish
-- bo'lardi. Endi u "kamida bitta TASHQI kanal ketdi" ma'nosini oladi
-- va uni `navbat.py` qo'yadi.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. NISHON — bildirishnoma bosilganda QAYERGA olib boradi
-- --------------------------------------------------------------------------
-- `opportunity_id` yetarli emas edi: umumiy chat kartasiz, vazifa esa
-- kartaning ichida alohida joy. "Umumiy panelga olib borish" eng yomon
-- variant — odam nima haqida ekanini QAYTADAN qidiradi.
ALTER TABLE erp.notification
    ADD COLUMN IF NOT EXISTS chat_id INT
        REFERENCES erp.chat(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS task_id INT
        REFERENCES erp.opportunity_task(id) ON DELETE CASCADE,
    --: TAKRORLANMASLIK kaliti. Hodisa + qabul qiluvchi bo'yicha
    --: hisoblanadi (`api/erp/hodisa.py` -> `dedup()`), ya'ni bir xil
    --: hodisa ikkinchi marta yozilmaydi. NULL — "takror tekshirilmaydi"
    --: (bir martalik xabar), va bu ATAYLAB ruxsat etilgan: har
    --: bildirishnomaga sun'iy kalit o'ylab topish uni ma'nosizlashtirardi.
    ADD COLUMN IF NOT EXISTS dedup_key TEXT,
    --: Oxirgi marta QACHON qayta ko'tarilgan. Yig'ma bildirishnomada
    --: ("chatda 3 ta yangi xabar") yangi qator yozilmaydi — mavjudi
    --: yangilanadi, `read_at` esa tozalanadi. Shusiz o'qilgan
    --: bildirishnoma yangi xabar kelganda ham o'qilgan bo'lib qolardi.
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

COMMENT ON COLUMN erp.notification.dedup_key IS
    'Hodisa + qabul qiluvchi kaliti. Takror yozuvni to''sadi; NULL - '
    'takror tekshirilmaydi (api/erp/hodisa.py).';
COMMENT ON COLUMN erp.notification.chat_id IS
    'Klik nishoni: aynan shu chat. Umumiy chatda karta yo''q.';

-- Dedup FAQAT kalit bor qatorlarda ishlaydi (qisman noyob indeks).
CREATE UNIQUE INDEX IF NOT EXISTS notification_dedup_uk
    ON erp.notification (dedup_key) WHERE dedup_key IS NOT NULL;

-- "Shu chatda menga nima kelgan" — yig'ma xabarni yangilashda ishlatiladi.
CREATE INDEX IF NOT EXISTS notification_chat_idx
    ON erp.notification (chat_id, app_user_id) WHERE chat_id IS NOT NULL;

-- --------------------------------------------------------------------------
-- 2. YETKAZISH NAVBATI (outbox)
-- --------------------------------------------------------------------------
-- HAR KANAL UCHUN BITTA QATOR. Bildirishnoma yozilgan tranzaksiyada
-- shu qatorlar ham yoziladi (`api/erp/hodisa.py`), yetkazish esa
-- KEYIN va ALOHIDA (`api/erp/navbat.py`).
--
-- NEGA SHUNDAY: chat xabari Telegram yiqilgani uchun YO'QOLMASLIGI
-- kerak. Agar yuborish xabar yozish bilan bir tranzaksiyada bo'lsa,
-- tashqi xizmatning sekinligi ERP ni ushlab turardi va xatosi
-- yozuvni orqaga qaytarardi.
CREATE TABLE IF NOT EXISTS erp.notification_delivery (
    id              SERIAL PRIMARY KEY,
    notification_id INT NOT NULL
        REFERENCES erp.notification(id) ON DELETE CASCADE,
    --: 'inapp' | 'email' | 'telegram'. Ro'yxat KODDA
    --: (`api/erp/navbat.py` -> KANALLAR) va u yerda har biri uchun
    --: yuboruvchi bor. Bazada CHECK yo'q: yangi kanal qo'shish patch
    --: talab qilmasin.
    kanal           TEXT NOT NULL,
    --: pending -> sent | failed -> (qayta urinish) -> sent | terminal
    --:
    --: `delivered` YO'Q va bu ONGLI QAROR. Tender-AI orqali yuborilgan
    --: email/Telegram uchun "yetib bordi" degan DALIL yo'q — faqat
    --: "yubordik" bor. Bo'lmagan dalilni holat sifatida yozish
    --: kuzatuvni yolg'on qilardi (§18: UNKNOWN - UNKNOWN bo'lib qolsin).
    --: `read` ham yo'q: u bildirishnomaning O'ZIDA (`read_at`) va
    --: kanalga bog'liq emas.
    holat           TEXT NOT NULL DEFAULT 'pending'
        CHECK (holat IN ('pending', 'sent', 'failed', 'terminal')),
    --: Nechinchi urinish. 0 - hali urinilmagan.
    urinish         INT NOT NULL DEFAULT 0,
    --: Keyingi urinish vaqti (orqaga chekinish bilan o'sadi).
    next_try_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: OXIRGI xato matni. Saqlanadi, chunki "yuborilmadi" degan gap
    --: sababsiz foydasiz: SMTP o'chganmi yoki manzil noto'g'rimi -
    --: birinchisi kutiladi, ikkinchisi tuzatilishi kerak.
    last_error      TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: BITTA bildirishnoma BITTA kanalga bir marta. Qayta urinish
    --: MAVJUD qatorni yangilaydi, yangisini yozmaydi - §17 dagi
    --: "qayta urinish idempotent" aynan shu.
    UNIQUE (notification_id, kanal)
);

COMMENT ON TABLE erp.notification_delivery IS
    'Bildirishnoma yetkazish navbati (outbox). Har kanal uchun bitta '
    'qator: email ketib, Telegram yiqilishi mumkin.';
COMMENT ON COLUMN erp.notification_delivery.holat IS
    'pending/sent/failed/terminal. "delivered" YO''Q: tashqi kanal '
    'yetib borganiga dalil bermaydi (api/erp/navbat.py).';

-- Navbatni olish so'rovi: "vaqti kelgan, tugamagan".
CREATE INDEX IF NOT EXISTS notification_delivery_navbat_idx
    ON erp.notification_delivery (next_try_at)
    WHERE holat IN ('pending', 'failed');

-- --------------------------------------------------------------------------
-- 3. SOZLAMA — kim qaysi kanalni oladi
-- --------------------------------------------------------------------------
-- YO'Q QATOR = STANDART HOLAT (kodda, `api/erp/hodisa.py` -> HODISALAR).
-- Har hodim uchun oldindan qator yozilmaydi: yangi hodisa turi
-- qo'shilganda hammaga qator qo'shish kerak bo'lardi va uni unutish
-- "yangi hodisa hech kimga bormaydi" degan jim nuqsonga aylanardi.
CREATE TABLE IF NOT EXISTS erp.notification_pref (
    app_user_id INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    --: Hodisa turi (`erp.notification.kind`). '*' - hamma tur.
    kind        TEXT NOT NULL,
    kanal       TEXT NOT NULL,
    yoqilgan    BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (app_user_id, kind, kanal)
);

COMMENT ON TABLE erp.notification_pref IS
    'Kanal sozlamasi. Qator YO''Q = standart (kodda). Ilova kanali '
    'o''chirilmaydi - u yagona ishonchli joy.';

-- CHATNI JIMLASH. Alohida jadval EMAS, mavjud a'zolik jadvaliga
-- ustun: "jim" - a'zolikning bir holati, alohida tushuncha emas.
-- Umumiy chatda a'zolik virtual, shuning uchun u yerda jimlash uchun
-- qator PAYDO BO'LADI (`api/erp/chat.py` -> `jimla`) va bu virtual
-- a'zolik qoidasini buzmaydi: qator "a'zo" degani emas, "sozlama"
-- degani. Shuning uchun `azomi()` bu ustunga qaramaydi.
ALTER TABLE erp.chat_member
    ADD COLUMN IF NOT EXISTS muted_at TIMESTAMPTZ;

COMMENT ON COLUMN erp.chat_member.muted_at IS
    'Jimlangan: yangi xabar uchun bildirishnoma kelmaydi. O''qilmagan '
    'hisoblagichi ISHLAYVERADI - jimlash "ko''rmayman" degani emas.';

-- --------------------------------------------------------------------------
-- 4. KUZATUV — "bildirishnoma jim yo'qolmasin"
-- --------------------------------------------------------------------------
-- View, jadval emas: raqamlar HISOBLANADI. Ikkinchi nusxa saqlansa u
-- haqiqatdan ajralib ketardi va aynan shu joyda - nosozlikni
-- ko'rsatishi kerak bo'lgan joyda - yolg'on gapirardi.
CREATE OR REPLACE VIEW erp.v_notification_health AS
SELECT d.kanal,
       count(*)                                          AS jami,
       count(*) FILTER (WHERE d.holat = 'pending')       AS pending,
       count(*) FILTER (WHERE d.holat = 'sent')          AS sent,
       count(*) FILTER (WHERE d.holat = 'failed')        AS failed,
       count(*) FILTER (WHERE d.holat = 'terminal')      AS terminal,
       --: ENG ESKI kutayotgan qator. "Navbat bor" bilan "navbat
       --: to'xtab qolgan" ni faqat shu ajratadi.
       min(d.next_try_at) FILTER (WHERE d.holat IN ('pending', 'failed'))
                                                         AS eng_eski_pending,
       max(d.sent_at)                                    AS oxirgi_yuborilgan,
       --: Nosozlik ULUSHI - butun son foizda. Yakunlangan urinishlar
       --: bo'yicha: hali navbatda turgani nosozlik emas.
       CASE WHEN count(*) FILTER (WHERE d.holat IN ('sent', 'terminal')) > 0
            THEN round(100.0 * count(*) FILTER (WHERE d.holat = 'terminal')
                       / count(*) FILTER (WHERE d.holat IN ('sent', 'terminal')))
            ELSE NULL END                                AS nosozlik_foiz
FROM erp.notification_delivery d
GROUP BY d.kanal;

COMMENT ON VIEW erp.v_notification_health IS
    'Bildirishnoma navbati holati kanal kesimida. `eng_eski_pending` - '
    'navbat to''xtab qolganini ko''rsatadigan yagona raqam.';

-- --------------------------------------------------------------------------
-- 5. MAVJUD QATORLAR
-- --------------------------------------------------------------------------
-- 22-patchdan beri yozilgan bildirishnomalarda navbat qatori YO'Q.
-- Ular uchun ilova kanali ALLAQACHON yetkazilgan (jadvalning o'zi -
-- ilova kanali), shuning uchun `sent` deb yoziladi. Tashqi kanal
-- qatori ORQAGA QARAB yaratilmaydi: bir oy oldingi eslatmani bugun
-- Telegram'ga yuborish - foydali emas, chalg'ituvchi.
INSERT INTO erp.notification_delivery (notification_id, kanal, holat,
                                       urinish, sent_at)
SELECT n.id, 'inapp', 'sent', 1, n.created_at
FROM erp.notification n
WHERE NOT EXISTS (SELECT 1 FROM erp.notification_delivery d
                   WHERE d.notification_id = n.id AND d.kanal = 'inapp');
