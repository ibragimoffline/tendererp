-- =============================================================================
-- Sxema patch — TENDER-AI YO'NALTIRISHI (topshiriq -> ish kartasi)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_21.sql
-- Talab: schema_patch_erp_1 (kartalar), _5 (own_company), _19/_20 (view'lar).
-- Juftlik: Tender-AI repozitoriysidagi `schema_patch_topshiriq.sql`.
--
-- MUAMMO: broker Tender-AI navbatida "Olindi" deydi va zanjir shu
-- yerda UZILADI. ERP kartani QO'LDA ochadi: tenderni qidiradi,
-- mijozni tanlaydi, muddatni ko'chiradi. Ya'ni qaror u yerda, ish esa
-- bu yerda va o'rtada odam turadi. Qaror bilan karta orasidagi
-- bog'lanish esa umuman yozilmaydi — "bu karta qaysi qarordan
-- kelgan?" degan savolga javob yo'q.
--
-- YECHIM: Tender-AI `public.tender_topshiriq` ga yozadi va
-- `pg_notify` yuboradi; ERP `public.v_erp_topshiriq` dan O'QIYDI va
-- karta ochadi. HTTP yo'q, service kaliti yo'q. Chegara qoidasi
-- buzilmaydi: ERP `public.*` ga YOZMAYDI.
--
-- BU PATCH UCH NARSA QO'SHADI:
--   1. `erp.own_company.tai_company_id` — XARITA: bizning kompaniya
--      qaysi Tender-AI ijarachisi. Bu OPERATOR qarori.
--   2. `erp.opportunity` ga uchta ustun + UNIQUE indeks — karta
--      qaysi qarordan kelgani va u qanchalik ishonchli ekani.
--   3. `erp.opportunity_analysis` — TAHLIL SNAPSHOTI.
--
-- NEGA XARITA `own_company` DA, SOZLAMADA EMAS:
-- Bu kompaniya PASSPORTINING bir qismi ("biz Tender-AI da falon
-- ijarachimiz"), ha/yo'q sozlamasi emas. Va u YO'Q bo'lsa tinglovchi
-- hech narsa qilmaydi — bu ATAYLAB xavfsiz standart: xarita
-- qo'yilmagan o'rnatma boshqa ijarachining topshirig'ini o'ziniki
-- deb qabul qilmaydi (sinov ijarachilari ham shunga kiradi).
--
-- NEGA `routing_id` GA FK YO'Q: u `public.tender_routing.id` —
-- BOSHQA loyihaning jadvali. FK qo'yish ikki sxemani qattiq bog'lardi
-- va chegara qoidasini buzardi (`erp.opportunity.tender_id` bilan bir
-- xil sabab, `schema_patch_erp_1.sql`).
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. XARITA — biz qaysi ijarachimiz
-- --------------------------------------------------------------------------
ALTER TABLE erp.own_company
    ADD COLUMN IF NOT EXISTS tai_company_id INT;

COMMENT ON COLUMN erp.own_company.tai_company_id IS
    'Tender-AI dagi ijarachi (company_account.id). OPERATOR qo''yadi. '
    'NULL bo''lsa yo''naltirish tinglovchisi ishlamaydi - begona '
    'ijarachining topshirig''i o''ziniki deb qabul qilinmasin.';

-- --------------------------------------------------------------------------
-- 2. KARTA — qaysi qarordan kelgan
-- --------------------------------------------------------------------------
ALTER TABLE erp.opportunity
    ADD COLUMN IF NOT EXISTS routing_id INT,
    ADD COLUMN IF NOT EXISTS tai_company_id INT,
    --: Tender-AI `audit_jurnal.ishonch` lug'ati: erp_sessiya /
    --: aktor_elon / kompaniya_sessiyasi / servis. ERP yorliqni
    --: DALILDAN OSHIRMAYDI: `aktor_elon` "e'lon qilingan" deb
    --: ko'rsatiladi, "tasdiqlangan" deb emas.
    ADD COLUMN IF NOT EXISTS assigned_ishonch TEXT,
    --: `public.tender_topshiriq.id` — tahlil qaysi topshiriqdan
    --: kelgani (FK YO'Q, yuqoridagi sabab).
    ADD COLUMN IF NOT EXISTS topshiriq_id INT;

COMMENT ON COLUMN erp.opportunity.routing_id IS
    'public.tender_routing.id - karta qaysi QARORDAN tug''ilgan. '
    'FK ataylab yo''q (boshqa loyihaning jadvali).';

-- Bitta qarordan bitta karta. Tender-AI qayta yuborsa ham (tahlil
-- yangilanishi) ikkinchi karta ochilmaydi.
--
-- QISMIY indeks: qo'lda ochilgan kartalarda `routing_id` NULL va
-- ular bir-biriga xalaqit qilmasligi kerak.
CREATE UNIQUE INDEX IF NOT EXISTS opportunity_routing_uq
    ON erp.opportunity (routing_id) WHERE routing_id IS NOT NULL;

-- --------------------------------------------------------------------------
-- 3. TAHLIL SNAPSHOTI
-- --------------------------------------------------------------------------
-- NEGA ALOHIDA JADVAL, KARTADA JSONB USTUN EMAS:
--   1. Tahlil YANGILANISHI mumkin ("Tahlilni yangilash" tugmasi) va
--      eskisi TARIXDA qolishi kerak: broker qaysi ma'lumotga qarab
--      ish qilganini keyin tekshirish mumkin bo'lsin.
--   2. Karta har ro'yxatda o'qiladi; tahlil esa faqat ochilganda.
--      Uni kartaga qo'shish har so'rovga ortiqcha kilobaytlar
--      qo'shardi.
--
-- ERP TAHLILNI QAYTA HISOBLAMAYDI: qoidalar (moslik, malaka,
-- cheklist, ombor mosligi) Tender-AI da va ularning IKKINCHI NUSXASI
-- bo'lmasligi kerak. Bu yerda faqat NUSXA saqlanadi.
CREATE TABLE IF NOT EXISTS erp.opportunity_analysis (
    id             SERIAL PRIMARY KEY,
    opportunity_id INT NOT NULL
                   REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    --: public.tender_topshiriq.id (FK yo'q — boshqa loyiha).
    topshiriq_id   INT,
    --: Tender-AI yig'gan tahlil (api/topshiriq.py -> tahlil_yig).
    payload        JSONB NOT NULL,
    --: O'sha paytdagi ishonch darajasi.
    ishonch        TEXT,
    captured_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE erp.opportunity_analysis IS
    'Tender-AI tahlilining SNAPSHOTI (erp_rollar.md §6). ERP uni '
    'qayta hisoblamaydi. Yangi tahlil - YANGI qator, eskisi tarixda '
    'qoladi.';

CREATE INDEX IF NOT EXISTS opportunity_analysis_opp_idx
    ON erp.opportunity_analysis (opportunity_id, captured_at DESC);
