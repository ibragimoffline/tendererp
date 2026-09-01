-- =============================================================================
-- Sxema patch — SHARTNOMA-VIEW'LAR (ERP -> Tender-AI)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_19.sql
-- Talab: schema_patch_erp_1..8, 10, 17 (rollar).
--
-- `erp_rollar.md` §7 va §9 (ochiq qarzlar №1, №5, №6).
--
-- QOIDA (o'zgarmaydi): Tender-AI `erp.*` ga YOZMAYDI va jadvallarni
-- KO'RMAYDI — u faqat shu yerdagi VIEW larni o'qiydi. View — ATAYLAB
-- SHARTNOMA: ERP ichida ustun nomi o'zgarsa yoki jadval bo'linsa,
-- view moslashtiriladi va Tender-AI umuman sezmaydi.
--
-- BU PATCH TO'RT VIEW BERADI:
--
--   erp.v_tai_actor        YANGI — hodimlar (ochiq qarz №1). Usiz
--                          Tender-AI aktori ERP hodimiga bog'lanmaydi
--                          va yo'naltirish "Taqsimlanmagan" ga tushadi.
--   erp.v_tender_status    MAVJUD — `assignee_full_name` QO'SHILADI
--                          (drawer'da "kim ishlayapti" ko'rinsin).
--   erp.v_stock            YANGI NOM — hujjatda Tender-AI `erp.v_stock`
--                          ni o'qiydi deyilgan, bazada esa
--                          `v_stock_balance` bor (pastga qarang).
--   erp.v_client_document  YANGI — MIJOZ hujjatlari (ochiq qarz №5).
--                          Cheklist hozir faqat broker kompaniyasining
--                          o'z hujjatlarini ko'radi.
--
-- MAXFIYLIK CHEGARASI: view lar faqat KERAKLI ustunni beradi. Parol
-- xeshi, email, sessiya, mijoz rekvizitlari, summa va izoh
-- BERILMAYDI — Tender-AI ga kerak emas.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. HODIMLAR — erp.v_tai_actor (ochiq qarz №1)
-- --------------------------------------------------------------------------
-- Tender-AI da ODAM yo'q: u yerga KOMPANIYA kiradi va aktor faqat
-- "e'lon qilinadi" (`aktor_elon`). Shu view chop etilgach, Tender-AI
-- o'z `actor` xaritasini ERP hodimlaridan to'ldiradi va yo'naltirish
-- qarori haqiqiy hodimga bog'lanadi.
--
-- USTUN NOMLARI o'zbekcha (`rol`, `faol`) — `erp_rollar.md` §7 dagi
-- shartnoma shunday e'lon qilingan. ERP ichida ular `role` va `active`;
-- moslashtirish AYNAN shu view ning vazifasi.
--
-- NEGA FAOLSIZ HODIM HAM CHIQADI: xaritada eski bog'lanish qolgan
-- bo'lishi mumkin. Uni JIMGINA yo'qotsak, Tender-AI "aktor topilmadi"
-- deb tarixni uzib qo'yardi. `faol` ustuni "endi ishlamaydi" deyish
-- uchun yetarli.
--
-- PAROL, EMAIL, SESSIYA YO'Q — ataylab.
CREATE OR REPLACE VIEW erp.v_tai_actor AS
SELECT u.id        AS erp_user_id,
       u.full_name,
       u.role      AS rol,
       u.active    AS faol,
       -- Hodim yozuvi (`erp.broker`) — kartaning MAS'ULI shu.
       -- Hisob hodimga bog'lanmagan bo'lsa NULL: Tender-AI bunday
       -- aktorga karta biriktira olmasligini bilishi kerak.
       u.broker_id AS erp_broker_id
FROM erp.app_user u;

COMMENT ON VIEW erp.v_tai_actor IS
    'SHARTNOMA: tender-ai aktor xaritasini shu view dan to''ldiradi '
    '(faqat o''qish). Parol, email va sessiya ATAYLAB yo''q. Ustun '
    'nomlari erp_rollar.md §7 bilan bir xil: rol, faol.';

-- --------------------------------------------------------------------------
-- 2. KARTA HOLATI — erp.v_tender_status (mavjud view kengaytiriladi)
-- --------------------------------------------------------------------------
-- `assignee_full_name` QO'SHILADI. Mavjud ustunlar O'ZGARMAYDI va
-- tartibi ham saqlanadi: tender-ai ularni o'qiyapti (`ErpLink`), yangi
-- ustun esa OXIRIGA qo'shiladi — eski kod buzilmaydi.
--
-- NEGA `broker_name` QOLADI: u allaqachon o'qilyapti. Ikkalasi hozir
-- BIR XIL qiymat beradi (kartaning mas'uli), lekin nomlari boshqa
-- savolga javob beradi: `broker_name` — "kim bu hodim", `assignee_
-- full_name` — "kimga biriktirilgan". Tender-AI yo'naltirishi
-- (`tender_topshiriq`) kiritilganda ikkinchisi `assignee_id` dan
-- olinadi va o'shanda farq paydo bo'ladi.
CREATE OR REPLACE VIEW erp.v_tender_status AS
SELECT o.id                AS opportunity_id,
       o.tender_id,
       o.status,
       CASE o.status
           WHEN 'new'            THEN 'Yangi'
           WHEN 'reviewing'      THEN 'Ko''rib chiqilmoqda'
           WHEN 'sent_to_client' THEN 'Mijozga yuborildi'
           WHEN 'confirmed'      THEN 'Qatnashish tasdiqlandi'
           WHEN 'preparing'      THEN 'Taklif tayyorlanmoqda'
           WHEN 'submitted'      THEN 'Topshirildi'
           WHEN 'won'            THEN 'Yutildi'
           WHEN 'lost'           THEN 'Yutqazildi'
           WHEN 'rejected'       THEN 'Rad etildi'
       END                 AS status_label,
       o.priority,
       b.full_name         AS broker_name,
       c.name              AS client_name,
       o.created_at,
       o.updated_at,
       --: KIMGA BIRIKTIRILGAN — tender-ai drawer'ida ko'rsatiladi.
       b.full_name         AS assignee_full_name
FROM erp.opportunity o
LEFT JOIN erp.broker b        ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id;

COMMENT ON VIEW erp.v_tender_status IS
    'SHARTNOMA: tender-ai shu view ni o''qiydi (faqat o''qish). '
    'Ustunlarni o''zgartirish tender-ai ni buzadi (u yerda '
    'api/erp_status.py). Yangi status qo''shilsa CASE ni ham '
    'yangilang - erp_test.py buni tekshiradi. Yangi ustun faqat '
    'OXIRIGA qo''shiladi.';

-- --------------------------------------------------------------------------
-- 3. OMBOR — erp.v_stock (nom bo'yicha shartnoma)
-- --------------------------------------------------------------------------
-- MUAMMO: hujjatda (`erp_rollar.md` §0, §6) tender-ai `erp.v_stock` ni
-- o'qiydi deyilgan, bazada esa `erp.v_stock_balance` bor. Ikki nom —
-- ikki tomon bir-birini kutib qolishi degani.
--
-- NEGA QAYTA NOMLAMAYMIZ: `v_stock_balance` ERP ning O'Z ekranida
-- ishlatiladi (`api/erp/stock.py`) va tender-ai unga allaqachon
-- SELECT huquqiga ega. Nomni almashtirish ikkala tomonni ham bir
-- vaqtda buzardi.
--
-- YECHIM: `v_stock` — SHARTNOMA yuzasi, ustunlari ATAYLAB SANAB
-- o'tilgan. `v_stock_balance` ga yangi ustun qo'shilsa u bu yerga
-- O'ZIDAN o'tmaydi: shartnoma faqat ataylab kengayadi.
CREATE OR REPLACE VIEW erp.v_stock AS
SELECT s.product_id,
       s.product_name,
       s.unit,
       --: JISMONIY qoldiq (harakatlar yig'indisi).
       s.qty,
       --: Kartalarga ajratilgani — qoldiqni kamaytirmaydi.
       s.reserved,
       --: qty - reserved. "Yetadimi?" savoliga javob beradigan son.
       s.available,
       s.updated_at
FROM erp.v_stock_balance s;

COMMENT ON VIEW erp.v_stock IS
    'SHARTNOMA: tender-ai ombor qoldig''ini shu view dan o''qiydi '
    '(erp_rollar.md §3.3). erp.v_stock_balance - ERP ning ICHKI '
    'ko''rinishi; bu esa tashqi yuza va ustunlari sanab o''tilgan.';

-- --------------------------------------------------------------------------
-- 4. MIJOZ HUJJATLARI — erp.v_client_document (ochiq qarz №5)
-- --------------------------------------------------------------------------
-- MUAMMO: cheklist (tender-ai `compliance`) hozir faqat BROKER
-- KOMPANIYASINING o'z hujjatlarini ko'radi (`company_document`).
-- Mijoz nomidan qatnashilganda esa talab MIJOZNING hujjatlariga
-- qo'yiladi va ular ERP da.
--
-- Hozir ERP ularni HTTP orqali yuboradi (`api/tenderai.py` ->
-- compliance). Bu view o'sha ro'yxatning AYNAN o'zini beradi, ya'ni
-- tender-ai tayyor bo'lganda o'tish — bir tomonlama va sezilmaydigan.
--
-- FAYLNING O'ZI YO'Q: `file_ref` — havola, hujjat MATNI yoki fayli
-- berilmaydi. Cheklistga "bormi va muddati o'tmaganmi" degan javob
-- yetarli.
CREATE OR REPLACE VIEW erp.v_client_document AS
SELECT d.client_id,
       c.name        AS client_name,
       --: Mijozni tender e'lonidagi buyurtmachi bilan solishtirish uchun.
       c.inn         AS client_inn,
       d.id          AS document_id,
       --: Kanonik tur (tender-ai `compliance.DOC_TYPES` lug'ati).
       d.doc_type,
       d.name,
       d.number,
       d.issued_at,
       d.valid_until,
       --: Muddati o'tganmi. HISOB SHU YERDA: aks holda ikki tomon
       --: "bugun" ni har xil hisoblardi (vaqt mintaqasi, sana turi).
       (d.valid_until IS NOT NULL AND d.valid_until < current_date) AS expired
FROM erp.client_document d
JOIN erp.client_company c ON c.id = d.client_id;

COMMENT ON VIEW erp.v_client_document IS
    'SHARTNOMA: mijoz hujjatlari cheklisti uchun (erp_rollar.md §3.2, '
    'ochiq qarz №5). Faylning o''zi va izoh BERILMAYDI - "bormi va '
    'muddati o''tmaganmi" degan javob yetarli.';

-- --------------------------------------------------------------------------
-- 5. HUQUQLAR — tai_app faqat shu view larni ko'radi
-- --------------------------------------------------------------------------
-- Rol bo'lmasa (masalan yangi o'rnatmada, tender-ai hali qo'yilmagan)
-- patch YIQILMASLIGI kerak: `GRANT` mavjud bo'lmagan rolga xato
-- beradi va butun migratsiyani to'xtatardi.
--
-- JADVALGA huquq BERILMAYDI — faqat view larga. Ya'ni tender-ai
-- `erp.opportunity` ni ham, `erp.app_user` ni ham ko'rmaydi.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tai_app') THEN
        GRANT USAGE ON SCHEMA erp TO tai_app;
        GRANT SELECT ON erp.v_tai_actor,
                        erp.v_tender_status,
                        erp.v_stock,
                        erp.v_stock_balance,
                        erp.v_client_document
                     TO tai_app;
    ELSE
        RAISE NOTICE 'tai_app roli yo''q - GRANT o''tkazib yuborildi. '
                     'Tender-AI o''rnatilganda shu patchni qayta yuriting.';
    END IF;
END $$;
