-- =============================================================================
-- Sxema patch — HODIMGA BILDIRISHNOMA
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_22.sql
-- Talab: schema_patch_erp_6.sql (hodim hisoblari), _1 (kartalar).
--
-- MUAMMO: ERP da xabar YO'Q edi. Bor narsa — Tender-AI orqali
-- yuboriladigan ESLATMA (`api/erp/remind.py` -> `notify.send`), lekin u
-- KOMPANIYA darajasida: bitta Telegram guruhi va bitta email ro'yxati.
-- "Sizga karta biriktirildi" degan xabar esa ODAMGA tegishli.
--
-- Natijada yo'naltirish oqimi (`schema_patch_erp_21.sql`) jim ishlardi:
-- karta ochiladi, lekin hodim buni FAQAT ekranni ochganda ko'radi.
--
-- YECHIM: ERP ning O'Z bildirishnomasi — hodim hisobiga bog'langan.
--
-- NEGA TENDER-AI ORQALI EMAS:
-- U yerdagi `notify.py` kompaniya sozlamalari bilan ishlaydi va
-- ijarachi darajasida. Hodim tushunchasi umuman u yerda yo'q (aktor —
-- xarita, kimlik ombori emas). Xabarni o'sha quvurga tiqish "kimga"
-- degan savolni yo'qotardi.
--
-- NEGA JADVAL, FAQAT EMAIL/TELEGRAM EMAS:
--   1. Tashqi kanal YIQILADI (SMTP o'chgan, bot bloklangan) — xabar
--      esa yo'qolmasligi kerak;
--   2. "O'qilganmi" degan holat kerak: ekrandagi hisoblagich shundan;
--   3. Tarix: "menga qachon berilgan edi?" degan savolga javob.
--
-- TASHQI KANAL (email/Telegram) BU PATCHDA YO'Q — ataylab. ERP ning
-- o'z SMTP/bot rekvizitlari hali sozlanmagan va ularni Tender-AI dan
-- "qarzga olish" sirni ikkinchi joyda saqlash bo'lardi. Jadval esa
-- kanal qo'shilganda tayyor turadi: `yuborildi_at` ustuni shu uchun.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.notification (
    id             SERIAL PRIMARY KEY,
    --: KIMGA. Hodim emas, HISOB: xabar ekranda ko'rsatiladi va
    --: ekranga hisob bilan kiriladi.
    app_user_id    INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    --: Hodisa turi (api/erp/xabar.py -> TURLAR). Interfeys shunga
    --: qarab nishon va rang tanlaydi.
    kind           TEXT NOT NULL,
    matn           TEXT NOT NULL,
    --: Qaysi karta haqida. O'chirilsa xabar ham ketadi: kartasiz
    --: "karta biriktirildi" xabari ma'nosiz.
    opportunity_id INT REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    --: Havola. `localhost` bo'lsa YOZILMAYDI (api/erp/xabar.py):
    --: boshqa kompyuterda ochilmaydigan havola - buzuq havola.
    havola         TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: Odam ko'rgan payt. NULL - o'qilmagan (hisoblagich shundan).
    read_at        TIMESTAMPTZ,
    --: Tashqi kanalga (email/Telegram) uzatilgan payt. Kanal hali
    --: yo'q; ustun kelajak uchun va "yuborilmagan" ni ko'rsatadi.
    yuborildi_at   TIMESTAMPTZ
);

COMMENT ON TABLE erp.notification IS
    'Hodimga bildirishnoma (ERP niki). Tender-AI dagi notify.py '
    'KOMPANIYA darajasida ishlaydi va hodim tushunchasini bilmaydi.';
COMMENT ON COLUMN erp.notification.havola IS
    'Karta havolasi. localhost manzili YOZILMAYDI - u boshqa '
    'kompyuterda ochilmaydi (api/erp/xabar.py: havola()).';

-- "Menga nima keldi" — eng ko'p so'raladigan kesim.
CREATE INDEX IF NOT EXISTS notification_user_idx
    ON erp.notification (app_user_id, created_at DESC);
-- O'qilmaganlar hisoblagichi har sahifa yuklanganda so'raladi.
CREATE INDEX IF NOT EXISTS notification_unread_idx
    ON erp.notification (app_user_id) WHERE read_at IS NULL;
