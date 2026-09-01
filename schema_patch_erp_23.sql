-- =============================================================================
-- Sxema patch — ERP ROLINING HUQUQLARINI TORAYTIRISH (ochiq qarz №6)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_23.sql
-- Talab: schema_patch_erp_1..22.
--
-- MUAMMO: chegara qoidasi ("ERP `public.*` dan O'QIYDI, YOZMAYDI")
-- SINOVDA tekshiriladi, lekin BAZADA hech narsa ushlab turmaydi.
-- Ya'ni qoida — kelishuv, himoya emas. Bitta noto'g'ri `UPDATE` va
-- tender-ai ning ma'lumoti o'zgaradi; sinov buni KEYIN aytadi.
--
-- Bundan tashqari ERP butun `public.*` ni o'qiy oladi — unga esa OLTI
-- obyekt yetarli (pastga qarang). "Hammasini o'qish" — kerak
-- bo'lganidan ko'proq huquq.
--
-- YECHIM: `erp` roliga ANIQ huquq beriladi:
--     erp.*      -> to'liq (bu ERP ning O'Z sxemasi);
--     public.*   -> FAQAT SELECT va FAQAT olti obyekt.
--
-- BU PATCH O'ZI HIMOYANI YOQMAYDI. Ilova hozir `postgres` bilan
-- ulanadi (`XT_DB_DSN`), ya'ni cheklovlar unga tegmaydi. Yoqish —
-- OPERATOR qadami va u ATAYLAB shu yerda emas:
--
--     1. ALTER ROLE erp WITH LOGIN PASSWORD '...';   (parol repoda
--        saqlanmaydi)
--     2. .env: XT_DB_DSN=... user=erp password=...
--     3. `python check_setup.py` va sinovlar qayta yuritiladi.
--
-- Shu paytgacha patch NIMA KERAKLIGINI e'lon qiladi va sinov
-- (`_tests/erp18_test.py`) huquqlar ro'yxati kod bilan mos ekanini
-- tekshiradi — ya'ni yangi jadval o'qilsa, ro'yxat ham yangilanadi.
--
-- NEGA OLTI OBYEKT (hujjatda "ikki view" deyilgan edi):
--   tender, dim_status, dim_area   -> karta SNAPSHOTI (9 maydon)
--   v_tender_manba                 -> manbadagi e'lon havolasi
--   catalog_product                -> ombor: mahsulot nomi/tannarxi
--   v_erp_topshiriq                -> Tender-AI yo'naltirishi
-- `erp_rollar.md` §9 (№6) ikki view deb hisoblagan, chunki u ombor
-- va snapshot yo'llarini e'tiborga olmagan. Ro'yxat KODDAN olingan.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp') THEN
        RAISE NOTICE 'erp roli yo''q - patch o''tkazib yuborildi. '
                     'Yaratish: CREATE ROLE erp LOGIN PASSWORD ''...'';';
        RETURN;
    END IF;

    -- 1. ESKI, KENG HUQUQLARNI OLIB TASHLASH.
    --    Toraytirish shundan boshlanadi: avval berilgani qaytariladi,
    --    keyin aniq ro'yxat beriladi. Aks holda "toraytirdik" degan
    --    gap yolg'on bo'lardi.
    REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM erp;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM erp;
    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM erp;

    -- 2. O'Z SXEMASI — to'liq (ERP shu yerda yashaydi).
    GRANT USAGE ON SCHEMA erp TO erp;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA erp TO erp;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA erp TO erp;
    -- Kelajakdagi jadvallar ham: har migratsiyadan keyin qo'lda
    -- GRANT yozish unutiladi va ERP yangi jadvalni ko'rmay qoladi.
    ALTER DEFAULT PRIVILEGES IN SCHEMA erp
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO erp;
    ALTER DEFAULT PRIVILEGES IN SCHEMA erp
        GRANT USAGE, SELECT ON SEQUENCES TO erp;

    -- 3. TENDER-AI TOMONI — FAQAT O'QISH va FAQAT KERAKLISI.
    GRANT USAGE ON SCHEMA public TO erp;
    GRANT SELECT ON public.tender            TO erp;  -- karta snapshoti
    GRANT SELECT ON public.dim_status        TO erp;  -- snapshotdagi status
    GRANT SELECT ON public.dim_area          TO erp;  -- hudud nomi
    GRANT SELECT ON public.v_tender_manba    TO erp;  -- manba havolasi
    GRANT SELECT ON public.catalog_product   TO erp;  -- ombor: mahsulot
    GRANT SELECT ON public.v_erp_topshiriq   TO erp;  -- yo'naltirish
END $$;

COMMENT ON SCHEMA erp IS
    'ERP ning o''z sxemasi. `erp` roli bu yerda to''liq ishlaydi, '
    '`public.*` da esa FAQAT olti obyektni O''QIYDI '
    '(schema_patch_erp_23.sql). Chegara qoidasi endi bazada ham.';
