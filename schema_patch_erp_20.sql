-- =============================================================================
-- Sxema patch — erp.v_tai_actor SHAKLINI TO'G'RILASH (kimlik shartnomasi)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_20.sql
-- Talab: schema_patch_erp_19.sql (view birinchi marta shu yerda chiqqan).
--
-- MUAMMO: 19-patchda view `erp_user_id, full_name, rol, faol,
-- erp_broker_id` bilan chop etildi. Tender-AI tomonida esa BOSHQA
-- shakl KUTILAYOTGAN ekan va u KODDA yozilgan:
--
--     api/aktor.py -> _erp_sessiyadan():
--       SELECT erp_user_id, login, ism, rol FROM erp.v_tai_actor
--        WHERE token_hash = %(h)s AND expires_at > now()
--
-- Ya'ni shartnoma `docs/erp_kimlik.md` §4 da e'lon qilingan (o'sha
-- repozitoriyda) va men uni o'qimasdan o'z nomlarimni chop etdim.
-- Natija: view "bor" bo'lib turadi, lekin Tender-AI undan HECH NARSA
-- topolmaydi — `token_hash` ustuni yo'q, `ism` esa `full_name` deb
-- ataladi. Bu eng yomon holat: ikkala tomon ham "ulandik" deb o'ylaydi.
--
-- YECHIM: view kutilgan shaklga keltiriladi. Ustun nomi o'zgargani
-- uchun `CREATE OR REPLACE` YETMAYDI — view TASHLANADI va qayta
-- yaratiladi (`GRANT` lar ham qayta beriladi: ular view bilan birga
-- o'chadi).
--
-- BU NIMA BERADI: `erp_sessiya` — eng yuqori ishonch darajasi.
-- Tender-AI xom tokenni KO'RMAYDI: u `X-ERP-Session` sarlavhasidagi
-- tokenning `sha256` ini hisoblab, shu view dagi xesh bilan
-- taqqoslaydi. Ya'ni "bu qarorni ERP ga kirgan falonchi qo'ydi"
-- degan gap DALILGA ega bo'ladi (`aktor_elon` faqat "aytilgan" edi).
--
-- IKKI JOYDA HUJJATDAN CHETLASHDIM — ataylab va sababi bilan:
--
--  1. `JOIN` EMAS, `LEFT JOIN`. Hujjatdagi variantda faqat SESSIYASI
--     BOR hodim ko'rinadi. Lekin Tender-AI shu view dan xaritani ham
--     tekshiradi (`erp_moslikni_tekshir`): "xaritadagi erp_user_id
--     ERP da hali ham bormi". `JOIN` bilan bugun tizimga kirmagan
--     hodim "YETIM" bo'lib chiqardi — ya'ni o'lchov yolg'on
--     ogohlantirish berardi.
--
--  2. `WHERE u.active` EMAS, `faol` USTUNI. Faolsizlantirilgan hodim
--     ko'rinib turadi, lekin `faol = false` bilan. Sababi o'sha:
--     "o'chirilgan" bilan "yo'q" ni ajratib bo'lsin. Sessiya esa
--     faqat FAOL hodimga bog'lanadi (`AND u.active` shartda), ya'ni
--     faolsiz hodim orqali KIRIB bo'lmaydi.
--
-- RO'YXAT UCHUN `DISTINCT` KERAK: bir hodimning bir nechta ochiq
-- sessiyasi bo'lsa, u shuncha qatorda ko'rinadi (xesh har birida
-- boshqa). Kimlik izlashda bu muhim emas (xesh yagona), ro'yxat
-- olayotgan tomon esa `DISTINCT erp_user_id` ishlatadi.
-- =============================================================================

DROP VIEW IF EXISTS erp.v_tai_actor;

CREATE VIEW erp.v_tai_actor AS
SELECT u.id          AS erp_user_id,
       u.username    AS login,
       u.full_name   AS ism,
       u.role        AS rol,
       --: Hodim yozuvi (`erp.broker`) — kartaning mas'uli shu.
       --: NULL bo'lsa bu hisobga karta biriktirib bo'lmaydi.
       u.broker_id   AS erp_broker_id,
       --: Hisob yopilganmi. Yozuv YO'QOLMAYDI — xaritadagi eski
       --: bog'lanish "yetim" deb ko'rinmasin.
       u.active      AS faol,
       --: SESSIYA ISBOTI. Xom token ERP da ham saqlanmaydi — faqat
       --: sha256 xeshi. Tender-AI xeshni o'zi hisoblab solishtiradi.
       s.token_hash,
       s.expires_at
FROM erp.app_user u
LEFT JOIN erp.app_session s
       ON s.user_id = u.id
      AND u.active                 -- faolsiz hisob orqali kirib bo'lmaydi
      AND s.expires_at > now();    -- muddati o'tgan sessiya isbot emas

COMMENT ON VIEW erp.v_tai_actor IS
    'SHARTNOMA (tender-ai docs/erp_kimlik.md §4): aktor kimligi va '
    'ERP sessiyasi isboti. Xom token EMAS, sha256 xeshi. Parol, email '
    'va CSRF ATAYLAB yo''q. Ro''yxat olayotgan tomon DISTINCT '
    'erp_user_id ishlatsin: ochiq sessiya soniga qarab qator ko''payadi.';

-- View qayta yaratilgani uchun huquqlar ham qayta beriladi.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tai_app') THEN
        GRANT SELECT ON erp.v_tai_actor TO tai_app;
    END IF;
END $$;
