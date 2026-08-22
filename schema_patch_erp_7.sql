-- =============================================================================
-- Sxema patch — TENDER-AI UCHUN SHARTNOMA-VIEW (auth-3, "B" varianti)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_7.sql
-- Talab: schema_patch_erp_1..6.sql qo'llangan bo'lishi kerak.
--
-- MUAMMO: tender-ai interfeysidagi `ErpLink` "shu tender ishga olinganmi?"
-- degan savolni ERP ga BRAUZERDAN yuborardi. Shuning uchun ERP ning
-- `GET /erp/tenders/{id}/opportunities` endpointi ochiq qolishga majbur
-- edi: brauzer server-server kalitini ushlab turolmaydi (kalit JS
-- to'plamiga tushib qolardi).
--
-- YECHIM: tender-ai o'z backendida shu VIEW ni O'QIYDI. HTTP yo'q, sir
-- yo'q, CORS yo'q va ERP endpointi yopiladi.
--
-- NEGA JADVAL EMAS, VIEW: bu ATAYLAB SHARTNOMA. Tender-AI `erp.opportunity`
-- ning ustunlariga emas, shu view ning shakliga bog'lanadi. ERP ichida
-- ustun nomi o'zgarsa yoki jadval bo'linsa — view moslashtiriladi va
-- tender-ai umuman sezmaydi.
--
-- CHEGARA QOIDASI ENDI SIMMETRIK:
--     ERP        `public.*` dan O'QIYDI  (tender snapshoti), YOZMAYDI.
--     Tender-AI  `erp.v_tender_status` dan O'QIYDI, YOZMAYDI.
-- Ikkala sinov ham har yurishda buni tekshiradi.
--
-- MAXFIYLIK: view faqat `ErpLink` ko'rsatadigan narsani beradi — status,
-- mas'ul hodim va mijoz nomi. Summa, narx, izoh, tarix va shartnoma
-- BERILMAYDI: tender-ai ga kerak emas.
-- =============================================================================

CREATE OR REPLACE VIEW erp.v_tender_status AS
SELECT o.id                AS opportunity_id,
       o.tender_id,
       o.status,
       -- O'QILADIGAN nom SHU YERDA hisoblanadi. Aks holda tender-ai ERP
       -- ning status ro'yxatini o'z kodida takrorlashi kerak bo'lardi va
       -- ikki ro'yxat vaqt o'tib ajralib ketardi.
       --
       -- Ro'yxat kodda ham bor (`api/erp/opportunity.py` -> STATUSES) —
       -- loyihada allaqachon shunday: bazadagi CHECK ham, kod ham bitta
       -- ro'yxatni saqlaydi va SINOV ikkalasini solishtiradi. Bu view ham
       -- shu sinovga qo'shildi (`erp_test.py`).
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
       o.updated_at
FROM erp.opportunity o
LEFT JOIN erp.broker b        ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id;

COMMENT ON VIEW erp.v_tender_status IS
    'SHARTNOMA: tender-ai shu view ni o''qiydi (faqat o''qish). Ustunlarini '
    'o''zgartirish tender-ai ni buzadi (u yerda api/erp_status.py). Yangi '
    'status qo''shilsa CASE ni ham yangilang - erp_test.py buni tekshiradi.';
