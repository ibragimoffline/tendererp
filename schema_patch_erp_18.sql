-- =============================================================================
-- Sxema patch — TIZIM SOZLAMALARI (`erp_rollar.md` §3.1, §3.5)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_18.sql
-- Talab: schema_patch_erp_6.sql (hodim hisoblari).
--
-- MUAMMO: huquqlar matritsasida (`api/erp/perm.py`) uchta qator
-- "kompaniyaga bog'liq" — bir joyda ha, boshqasida yo'q bo'lishi kerak:
--
--   * broker kartani O'ZI yakunlay oladimi (`broker_can_close`) —
--     hujjatda "default ha", lekin ba'zi kompaniyada yakuniy qarorni
--     faqat rahbar qo'yadi;
--   * menejer kompaniya FOYDASINI ko'radimi — hujjatda "sozlanadi";
--   * admin biznes ma'lumotni faqat KO'RADIMI (tizim sozlovchi va pul
--     hujjati o'zgartiruvchi bitta odam bo'lmasin).
--
-- Ular kodda o'zgarmas bo'lib turgan edi, ya'ni o'zgartirish uchun
-- dasturchi kerak edi. Bu — sozlama, kod emas.
--
-- NEGA KALIT-QIYMAT JADVALI, USTUNLAR EMAS:
-- Sozlamalar SONI o'sadi va har biri uchun `own_company` ga ustun
-- qo'shish migratsiya talab qilardi. Bu yerda esa yangi sozlama —
-- kodda bitta qator (`api/erp/sozlama.py` -> SOZLAMALAR), bazada esa
-- hech narsa: qiymat berilmagan sozlama STANDART qiymatda ishlaydi.
--
-- NEGA QIYMAT `text`, `jsonb` EMAS:
-- Hozir hamma sozlama — ha/yo'q. `jsonb` "har qanday narsa" degani
-- bo'lardi va tekshiruv kodga tushardi. Turi va standarti KODDA
-- e'lon qilinadi, bu yerda faqat SAQLASH.
--
-- KIM O'ZGARTIRDI: `updated_by` — sessiyadagi ism (`auth.actor`).
-- Sozlama huquqni o'zgartiradi, ya'ni "kim yoqdi?" degan savol
-- keyinroq beriladi va javobsiz qolmasligi kerak.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.setting (
    --: Kalit KODDA e'lon qilinadi (api/erp/sozlama.py -> SOZLAMALAR).
    --: Bazada noma'lum kalit qolsa — u JIMGINA e'tiborsiz qoladi
    --: (eskirgan sozlama ilovani yiqitmasin).
    key        text PRIMARY KEY,
    --: Qiymat matn ko'rinishida: 'true' / 'false'. Turini kod biladi.
    value      text        NOT NULL,
    --: Kim o'zgartirgani. NULL = ERP dan tashqarida (to'g'ridan-to'g'ri SQL).
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE erp.setting IS
    'Tizim sozlamalari (kalit-qiymat). Kalitlar, turlari va STANDART '
    'qiymatlari api/erp/sozlama.py da; bazada faqat O''ZGARTIRILGANLARI '
    'yotadi. Sozlama huquqqa ta''sir qiladi (api/erp/perm.py).';
COMMENT ON COLUMN erp.setting.updated_by IS
    'Kim o''zgartirgani (sessiyadagi ism). NULL = ERP dan tashqarida.';
