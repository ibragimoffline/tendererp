-- =============================================================================
-- Sxema patch — AUTH-4: sessiyaga CSRF tokeni
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_9.sql
-- Talab: schema_patch_erp_6.sql qo'llangan bo'lishi kerak.
--
-- NIMA O'ZGARADI: sessiya tokeni endi `HttpOnly` cookie'da yuriladi
-- (`localStorage` da EMAS). Bu XSS da tokenni o'g'irlashning oldini
-- oladi, lekin YANGI xavf ochadi: cookie brauzer tomonidan HAR
-- so'rovga avtomatik qo'shiladi, ya'ni boshqa sayt bizning nomimizdan
-- so'rov yubora oladi (CSRF).
--
-- YECHIM: har sessiyaga tasodifiy CSRF tokeni. U IKKI joyda yuradi:
--   1. `HttpOnly BO'LMAGAN` cookie'da — sahifa uni o'qiy oladi;
--   2. `X-CSRF-Token` sarlavhasida — sahifa uni O'ZI qo'yadi.
-- Server sarlavhadagi qiymatni SESSIYADAGI qiymat bilan solishtiradi.
--
-- NEGA SESSIYADA SAQLANADI (oddiy "double-submit" dan farqi): klassik
-- usulda server faqat "cookie va sarlavha bir xilmi" deb qaraydi. Agar
-- hujumchi biror yo'l bilan cookie qo'ya olsa (subdomen, MITM),
-- ikkalasini ham o'zi to'ldirib qo'yardi. Bazadagi qiymat bilan
-- solishtirish bu yo'lni yopadi: token SESSIYA bilan bog'langan.
-- =============================================================================

ALTER TABLE erp.app_session
    ADD COLUMN IF NOT EXISTS csrf_token TEXT;

COMMENT ON COLUMN erp.app_session.csrf_token IS
    'CSRF tokeni. Sessiya tokenidan FARQLI: bu qiymat sahifaga ochiq '
    '(HttpOnly bo''lmagan cookie) va u faqat "so''rovni bizning sahifamiz '
    'yubordimi" degan savolga javob beradi. Kirish huquqini bermaydi.';

-- Eski sessiyalarda CSRF yo'q — ular ishlamaydi va bu TO'G'RI: patch
-- qo'llangandan keyin hamma qaytadan kiradi (tokenlar qisqa umrli).
-- Tozalaymiz, aks holda ular muddati tugagunicha "kirgan, lekin hech
-- narsa yozolmaydigan" holatda osilib turardi.
DELETE FROM erp.app_session WHERE csrf_token IS NULL;
