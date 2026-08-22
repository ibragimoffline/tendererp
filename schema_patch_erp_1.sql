-- =============================================================================
-- Sxema patch — ERP 1-BOSQICH: "Ishga olish" + Opportunity pipeline
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_1.sql
--
-- MUAMMO: tender ro'yxatda ko'rinadi, lekin "kim ishlayapti, qaysi mijoz
-- uchun, qaysi bosqichda" degan savolga tizim javob bermaydi — bu ma'lumot
-- brokerlarning boshida va Excel'da qoladi. Rahbar umumiy manzarani ko'rmaydi.
--
-- YECHIM: alohida `erp` sxemasi. Tender "ishga olinganda" undan opportunity
-- kartasi tug'iladi; kartaning holati 9 statusli quvur bo'ylab yuradi va har
-- o'tish tarixga yoziladi.
--
-- MUHIM CHEGARALAR (erp_arxitektura.md 2-bo'lim):
--   1. public.* ga TEGILMAYDI — na yozuv, na ustun, na trigger.
--   2. erp.opportunity.tender_id -> public.tender.id ga FOREIGN KEY YO'Q.
--      Sabab: ETL tender qismlarini DELETE+INSERT qiladi va manba tenderni
--      butunlay o'chirishi mumkin. Ishga olingan tender kartasi manbadagi
--      o'zgarishdan YO'QOLMASLIGI kerak (doctext.md 6.1 dagi bilan bir xil
--      sabab). Kartadagi tender ma'lumoti — snapshot, havola emas.
--   3. Karta O'CHIRILMAYDI: noto'g'ri ishga olingan tender 'rejected' ga
--      o'tkaziladi va izoh yoziladi — tarix rahbar uchun ma'lumot.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS erp;

-- Brokerlar (kompaniyaning o'z xodimlari). Auth hali yo'q, shuning uchun
-- "kim qildi" degan savolga javob shu ro'yxatdan tanlangan nom bilan beriladi.
CREATE TABLE IF NOT EXISTS erp.broker (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mijoz korxonalar. 2-bosqichda passport ustunlari (INN, OKED, manzil, bank
-- rekvizitlari) ALTER TABLE ... ADD COLUMN bilan SHU jadvalga qo'shiladi —
-- shuning uchun 1-bosqichdayoq alohida jadval, matn maydoni emas.
CREATE TABLE IF NOT EXISTS erp.client_company (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS erp.opportunity (
    id                SERIAL PRIMARY KEY,
    tender_id         BIGINT NOT NULL,          -- public.tender.id (FK YO'Q, yuqoriga qarang)
    -- --- snapshot: ishga olingan paytdagi holat, keyin tender o'zgarsa ham qoladi ---
    source_platform   TEXT,
    tender_ref        TEXT,                     -- manbadagi ASL raqam (source_id)
    customer_name     TEXT,
    title             TEXT,
    start_price       NUMERIC,
    currency          TEXT,
    deadline_at       TIMESTAMPTZ,
    region_name       TEXT,
    source_url        TEXT,
    -- --- xodim kiritadi ---
    broker_id         INT REFERENCES erp.broker(id),
    client_id         INT REFERENCES erp.client_company(id),
    priority          TEXT NOT NULL DEFAULT 'medium'
                      CHECK (priority IN ('low','medium','high')),
    -- Xodimning SHAXSIY bahosi. Go/No-Go va moslik balli bilan aralashtirilmaydi.
    win_probability   SMALLINT CHECK (win_probability BETWEEN 0 AND 100),
    note              TEXT,
    next_task         TEXT,
    next_task_at      DATE,
    -- --- holat ---
    -- Statuslar ro'yxati api/erp/opportunity.py dagi STATUSES bilan BIR XIL
    -- bo'lishi shart (sinov buni tekshiradi). Ro'yxat kengaysa:
    --   ALTER TABLE erp.opportunity DROP CONSTRAINT IF EXISTS opportunity_status_check;
    --   ALTER TABLE erp.opportunity ADD CONSTRAINT opportunity_status_check CHECK (...);
    status            TEXT NOT NULL DEFAULT 'new'
                      CHECK (status IN ('new','reviewing','sent_to_client','confirmed',
                                        'preparing','submitted','won','lost','rejected')),
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at         TIMESTAMPTZ,
    created_by        TEXT,                     -- auth yo'q: tanlangan broker nomi
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Bir tender -> bir mijoz uchun bitta karta. Ikki MIJOZ nomidan qatnashish
    -- mumkin (ikki karta), bitta mijoz uchun ikki marta — yo'q.
    UNIQUE (tender_id, client_id)
);

-- SQL'da NULL = NULL yolg'on, shuning uchun yuqoridagi UNIQUE mijozsiz
-- kartalarni ushlamaydi: "mijoz hali tanlanmagan" kartani ham takrorlanishdan
-- saqlash uchun qisman indeks kerak.
CREATE UNIQUE INDEX IF NOT EXISTS opportunity_tender_noclient_uq
    ON erp.opportunity (tender_id) WHERE client_id IS NULL;
CREATE INDEX IF NOT EXISTS opportunity_status_idx   ON erp.opportunity (status);
CREATE INDEX IF NOT EXISTS opportunity_broker_idx   ON erp.opportunity (broker_id);
CREATE INDEX IF NOT EXISTS opportunity_client_idx   ON erp.opportunity (client_id);
CREATE INDEX IF NOT EXISTS opportunity_deadline_idx ON erp.opportunity (deadline_at);
CREATE INDEX IF NOT EXISTS opportunity_tender_idx   ON erp.opportunity (tender_id);

-- Har status o'tishi shu yerga yoziladi: "har bosqichda qancha turdi" va
-- "yakuniy statusdan nega qaytarildi" degan savollar shundan javob oladi.
CREATE TABLE IF NOT EXISTS erp.opportunity_history (
    id              SERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    from_status     TEXT,                       -- NULL = karta yangi yaratildi
    to_status       TEXT NOT NULL,
    changed_by      TEXT,
    note            TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS opp_history_opp_idx ON erp.opportunity_history (opportunity_id);

COMMENT ON SCHEMA erp IS
    'ERP moduli. public.* ga yozmaydi, tender_id orqali faqat o''qiydi.';
COMMENT ON COLUMN erp.opportunity.tender_id IS
    'public.tender.id — ATAYLAB FK''siz: ETL manba tenderni o''chirishi mumkin, karta qolishi kerak.';
COMMENT ON COLUMN erp.opportunity.tender_ref IS
    'Manbadagi asl raqam (tender.source_id) — bizning global id emas.';
