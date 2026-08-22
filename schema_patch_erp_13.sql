-- =============================================================================
-- Sxema patch — BIZNING QQS holatimiz
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_13.sql
-- Talab: schema_patch_erp_5.sql (own_company) va _11.sql (faktura).
--
-- MUAMMO: 5B-2 da QQS stavkasi FAQAT mijoz passportidan olinardi
-- (`erp_faktura.md` 8-bo'lim, 2-savol). Amalda esa QQS ni SOTUVCHI
-- hisoblaydi: biz QQS to'lovchi bo'lmasak, mijoz to'lovchi bo'lsa ham
-- faktura QQS'siz chiqishi kerak.
--
-- YECHIM: bizning holatimiz ham passportda saqlanadi va stavka IKKALA
-- TOMONGA qarab hal bo'ladi (`api/erp/invoice.py` -> `default_vat_rate`).
--
-- `NULL` = HALI SO'RALMAGAN va bu MUHIM: patch qo'llangan kuniyoq
-- fakturalar QQS'siz chiqib ketmasligi kerak. NULL bo'lganda eski
-- xatti-harakat saqlanadi (stavka mijozdan). Faqat ochiq `false`
-- qo'yilganda QQS umuman qo'shilmaydi.
--
-- Ya'ni bu patch O'ZI hech narsani o'zgartirmaydi — u imkoniyat qo'shadi.
-- =============================================================================

ALTER TABLE erp.own_company
    ADD COLUMN IF NOT EXISTS vat_payer BOOLEAN,
    ADD COLUMN IF NOT EXISTS vat_rate  NUMERIC(5,2);

COMMENT ON COLUMN erp.own_company.vat_payer IS
    'BIZ QQS to''lovchimizmi. NULL = hali so''ralmagan (eski xatti-harakat: '
    'stavka mijoz passportidan). false = faktura QQS''siz chiqadi.';
COMMENT ON COLUMN erp.own_company.vat_rate IS
    'Bizning stavkamiz (%). Mijozning stavkasidan farq qilsa, KICHIGI '
    'olinadi - ortiqcha soliq qo''shib qo''ymaslik uchun.';
