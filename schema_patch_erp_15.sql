-- =============================================================================
-- Sxema patch — KIRISH URINISHLARI JURNALI (parol tanlashdan himoya)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_15.sql
-- Talab: schema_patch_erp_6.sql (hodim hisoblari).
--
-- MUAMMO: kirish sahifasi cheksiz urinishga ochiq edi. Parol xeshi kuchli
-- (PBKDF2, 240 000 iteratsiya) va u bitta urinishni sekinlashtiradi, lekin
-- HECH NARSA urinishlar SONINI cheklamaydi. Tarmoqqa ulangan har kim
-- "admin" login bilan lug'at bo'yicha tinimsiz urinaveradi va bu hech
-- qayerda iz qoldirmaydi.
--
-- NEGA JURNAL, "xato urinishlar soni" USTUNI EMAS:
-- Ombor qoldig'i bilan bir xil sabab. Ustun "5 marta xato" deydi, lekin
-- QACHON, QAYERDAN va QAYSI login bilan ekanini ayta olmaydi. Jurnal
-- ikkalasiga ham javob beradi: bloklash undan HISOBLANADI, admin esa
-- "kim kirishga urindi" degan savolga real javob oladi.
--
-- HISOBNI BLOKLAMAYMIZ — bu ataylab:
-- Agar 5 xatodan keyin hisob o'chirilsa, direktorning loginini bilgan har
-- kim uni ishdan chiqarib qo'ya oladi. Ya'ni himoya vositasi hujum
-- vositasiga aylanadi. Shuning uchun VAQTINCHA va (login + IP) juftligi
-- bo'yicha to'xtatiladi; hisobning o'zi tegilmaydi.
--
-- PAROL BU YERGA YOZILMAYDI. Na ochiq, na xesh ko'rinishida — jurnalda
-- faqat login nomi, manzil va natija bor.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.login_attempt (
    id          bigserial PRIMARY KEY,
    -- Login MAVJUD bo'lmasligi ham mumkin: aynan yo'q loginlar bilan
    -- urinish hujumning eng ko'p uchraydigan ko'rinishi, shuning uchun
    -- bu yerda FK yo'q va yozuv baribir saqlanadi.
    username    text        NOT NULL,
    ip          inet,
    ok          boolean     NOT NULL,
    user_agent  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE erp.login_attempt IS
    'Kirish urinishlari jurnali. Bloklash shu jadvaldan HISOBLANADI '
    '(alohida hisoblagich ustuni yo''q). Parol saqlanmaydi.';
COMMENT ON COLUMN erp.login_attempt.username IS
    'Kiritilgan login — mavjud bo''lmasligi ham mumkin (FK ataylab yo''q).';
COMMENT ON COLUMN erp.login_attempt.ok IS
    'Urinish muvaffaqiyatlimi. Muvaffaqiyatli kirish oldingi xatolar '
    'zanjirini UZADI: hisob shu paytdan keyingi xatolardan sanaladi.';

-- Bloklash so'rovi aynan shu ikki kesimda o'qiydi: (login + IP) va (IP).
CREATE INDEX IF NOT EXISTS login_attempt_user_idx
    ON erp.login_attempt (username, created_at DESC);
CREATE INDEX IF NOT EXISTS login_attempt_ip_idx
    ON erp.login_attempt (ip, created_at DESC);
