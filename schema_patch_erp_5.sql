-- =============================================================================
-- Sxema patch — ERP 5A-1: SHARTNOMA va BIZNING REKVIZITLAR
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_5.sql
-- Talab: schema_patch_erp_1..4.sql allaqachon qo'llangan bo'lishi kerak.
--
-- MUAMMO 1: taklif topshirilgach zanjir uziladi. "Yutildi" statusidan keyin
-- shartnoma raqami, summasi va muddati hech qayerda qolmaydi — ular xatda,
-- Excelda yoki odamning yodida.
--
-- MUAMMO 2: shartnoma IKKI tomonning rekvizitlarini talab qiladi. Mijozniki
-- bor (2-bosqich, `erp.client_company`), BIZNIKI esa hech qayerda yo'q:
-- tender-ai dagi `company_profile` — qidiruv va Go/No-Go profili (kalit
-- so'zlar, hududlar, sertifikatlar), unda na INN, na bank rekvizitlari.
--
-- YECHIM: `erp.own_company` (bitta qator) + `erp.contract`.
--
-- MUHIM CHEGARALAR:
--   1. public.* ga TEGILMAYDI. `company_profile` ham o'zgarmaydi — u boshqa
--      modul egasi (erp_arxitektura.md 2.1). Bizning passport ERP'da yashaydi.
--   2. `own_company` ustunlari `client_company` bilan BIR XIL nomlanadi —
--      shartnoma matnida ikkala tomon bir xil shaklda ishlatiladi.
--   3. Shartnoma O'CHIRILMAYDI: noto'g'risi 'terminated' ga o'tkaziladi
--      (karta va taklif bilan bir xil qoida).
-- =============================================================================

-- --- 1. Bizning kompaniya (BITTA qator) --------------------------------------
-- Nega alohida jadval, `client_company` ga bayroq emas: mijoz o'chirilishi
-- yoki faolsizlantirilishi mumkin, biznikisi esa har doim bitta va har doim
-- kerak. Bayroq bilan qilinsa "bizni o'chirib qo'yish" mumkin bo'lardi.
CREATE TABLE IF NOT EXISTS erp.own_company (
    id              INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),   -- bitta qator
    name            TEXT NOT NULL DEFAULT '',
    inn             TEXT,
    oked            TEXT,
    legal_form      TEXT,
    tax_mode        TEXT,
    address_legal   TEXT,
    address_actual  TEXT,
    bank_name       TEXT,
    bank_mfo        TEXT,
    bank_account    TEXT,
    director_name   TEXT,
    phone           TEXT,
    email           TEXT,
    note            TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bo'sh qator darhol yaratiladi: interfeys "yo'q" holatini emas,
-- "to'ldirilmagan" holatini ko'rsatadi (mijoz passportidagi bilan bir xil).
INSERT INTO erp.own_company (id, name)
SELECT 1, '' WHERE NOT EXISTS (SELECT 1 FROM erp.own_company WHERE id = 1);

-- --- 2. Shartnoma ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.contract (
    id              SERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    -- Qaysi taklif asosida imzolangani (bo'lmasa NULL: shartnoma ERP'dan
    -- tashqarida tuzilgan bo'lishi mumkin).
    submission_id   INT REFERENCES erp.submission(id) ON DELETE SET NULL,

    number          TEXT,                  -- shartnoma raqami
    signed_at       DATE,
    -- Ijro muddati: boshlanish va tugash. Yetkazib berish jadvali 5B da.
    starts_at       DATE,
    ends_at         DATE,
    amount          NUMERIC,
    currency        TEXT,

    -- Holat kodlari `api/erp/contracts.py` dagi CONTRACT_STATUSES bilan
    -- BIR XIL ro'yxat; sinov ikkalasini solishtiradi. Kengaytirilganda:
    -- DROP CONSTRAINT IF EXISTS + ADD CONSTRAINT.
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','signed','executing','done','terminated')),
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note            TEXT,
    created_by      TEXT,                  -- auth yo'q: tanlangan broker nomi
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS contract_opp_idx    ON erp.contract (opportunity_id);
CREATE INDEX IF NOT EXISTS contract_status_idx ON erp.contract (status);
-- "Muddati tugayotgan shartnomalar" ro'yxati uchun — ochiqlari bo'yicha.
CREATE INDEX IF NOT EXISTS contract_ends_idx
    ON erp.contract (ends_at) WHERE status IN ('signed','executing');
-- Raqam takrorlanmasin (kiritilgan bo'lsa): bitta raqam ikki shartnomada
-- turса hisobot ham, qidiruv ham chalkashadi.
CREATE UNIQUE INDEX IF NOT EXISTS contract_number_uq
    ON erp.contract (number) WHERE number IS NOT NULL AND number <> '';

COMMENT ON TABLE erp.own_company IS
    'Bizning kompaniya passporti (bitta qator). public.company_profile — qidiruv profili, uning o''rnini bosmaydi.';
COMMENT ON TABLE erp.contract IS
    'Shartnoma. O''chirilmaydi: noto''g''risi ''terminated'' ga o''tkaziladi.';
COMMENT ON COLUMN erp.contract.submission_id IS
    'Qaysi muzlatilgan taklif asosida. NULL — shartnoma ERP''dan tashqarida tuzilgan.';
