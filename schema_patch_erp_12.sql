-- =============================================================================
-- Sxema patch — DALOLATNOMA (akt)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_12.sql
-- Talab: schema_patch_erp_11.sql (faktura) qo'llangan bo'lishi kerak.
--
-- NIMA UCHUN: faktura "qancha to'lash kerak" deydi, dalolatnoma esa
-- "ish BAJARILDI / tovar TOPSHIRILDI" deydi. Bular ikki xil fakt va
-- ikkalasi ham kerak: to'lov nizosida "pulni to'ladim" bilan "ishni
-- oldim" boshqa-boshqa dalil.
--
-- FAKTURA BILAN BIR XIL UCH QOIDA (`erp_faktura.md` 3-bo'lim):
--   1. rekvizitlar SNAPSHOT — hujjat chiqarilgan paytdagi holat;
--   2. summalar SAQLANMAYDI — qatorlardan hisoblanadi;
--   3. `draft` dan chiqqach MUZLAYDI.
-- Hisob-kitob ham AYNAN o'sha kod bilan bajariladi (`invoice.line_totals`)
-- — ikki xil yaxlitlash ikki xil summa degani bo'lardi.
--
-- FAKTURAGA BOG'LANISH IXTIYORIY: dalolatnoma fakturasiz ham bo'ladi
-- (masalan bosqichma-bosqich topshirish), faktura ham dalolatnomasiz
-- (oldindan to'lov). Lekin odatda ikkalasi juftlik bo'lib yuradi va
-- shuning uchun aktni fakturadan YARATISH mumkin.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.act (
    id             SERIAL PRIMARY KEY,

    -- Bog'lanishlar. Hammasi IXTIYORIY, mijozdan tashqari.
    invoice_id     INT REFERENCES erp.invoice(id) ON DELETE SET NULL,
    contract_id    INT REFERENCES erp.contract(id) ON DELETE SET NULL,
    opportunity_id INT REFERENCES erp.opportunity(id) ON DELETE SET NULL,
    client_id      INT NOT NULL REFERENCES erp.client_company(id),

    number         TEXT,
    act_date       DATE,
    -- Ish qaysi davr uchun bajarilgani (bo'lsa). Oylik xizmatlarda
    -- dalolatnoma "1-31 avgust uchun" deb yoziladi.
    period_from    DATE,
    period_to      DATE,
    currency       CHAR(3) NOT NULL DEFAULT 'UZS',

    -- draft      — qoralama, tahrirlanadi
    -- issued     — chiqarildi (qatorlar MUZLAYDI)
    -- signed     — IKKALA TOMON imzoladi (aktning maqsadi shu)
    -- cancelled  — bekor qilindi
    -- Ro'yxat kodda ham bor (api/erp/act.py -> STATUSES).
    status         TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'issued', 'signed', 'cancelled')),
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Qachon imzolangani: `status_changed_at` dan farqli, bu HUJJATDAGI
    -- sana (keyin kiritilishi mumkin).
    signed_at      DATE,

    -- --- MIJOZ rekvizitlari (snapshot) ---
    client_name    TEXT NOT NULL,
    client_inn     TEXT,
    client_address TEXT,
    client_director TEXT,

    -- --- BIZNING rekvizitlar (snapshot) ---
    own_name       TEXT,
    own_inn        TEXT,
    own_address    TEXT,
    own_director   TEXT,

    note           TEXT,
    created_by     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raqam takrorlanmasin, lekin RAQAMSIZ qoralama bo'lishi mumkin.
CREATE UNIQUE INDEX IF NOT EXISTS act_number_uq
    ON erp.act (number) WHERE number IS NOT NULL;
CREATE INDEX IF NOT EXISTS act_client_idx  ON erp.act (client_id);
CREATE INDEX IF NOT EXISTS act_invoice_idx ON erp.act (invoice_id);
CREATE INDEX IF NOT EXISTS act_status_idx  ON erp.act (status);


-- Qatorlar — faktura qatorlari bilan bir xil shakl. Bank rekvizitlari
-- bu yerda YO'Q: dalolatnoma to'lov hujjati emas, shuning uchun unda
-- hisob raqam kerak emas.
CREATE TABLE IF NOT EXISTS erp.act_line (
    id       SERIAL PRIMARY KEY,
    act_id   INT NOT NULL REFERENCES erp.act(id) ON DELETE CASCADE,
    pos      INT NOT NULL DEFAULT 1,

    -- Katalog bandiga ixtiyoriy bog'lanish, FK ataylab yo'q.
    product_id INT,
    name     TEXT NOT NULL,
    unit     TEXT,

    qty      NUMERIC(18,3) NOT NULL CHECK (qty > 0),
    price    NUMERIC(18,2) NOT NULL CHECK (price >= 0),
    vat_rate NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (vat_rate >= 0),

    note     TEXT
);

CREATE INDEX IF NOT EXISTS act_line_act_idx ON erp.act_line (act_id);

COMMENT ON TABLE erp.act IS
    'Bajarilgan ish / topshirilgan tovar dalolatnomasi. Faktura "qancha '
    'to''lash kerak" deydi, akt "bajarildi" deydi. Rekvizitlar SNAPSHOT, '
    'summalar saqlanmaydi.';
COMMENT ON COLUMN erp.act.signed_at IS
    'HUJJATDAGI imzo sanasi. `status_changed_at` esa tizimda qachon '
    'belgilangani - ikkalasi bir xil bo''lishi shart emas.';
