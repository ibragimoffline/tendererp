-- =============================================================================
-- Sxema patch — HISOB-FAKTURA (5B-2), ma'lumot modeli
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_11.sql
-- Talab: schema_patch_erp_2.sql (mijoz passporti) va _5.sql (shartnoma).
--
-- QAROR: hisob-fakturani ERP O'ZI chiqaradi (javob olingan). Bu patch
-- MA'LUMOT MODELINI quradi; YUBORISH (eksport) qatlami ATAYLAB bo'sh —
-- format mijozning buxgalteri qaysi tizimda ishlashiga bog'liq
-- (`api/erp/invoice_export.py` dagi izohga qarang).
--
-- =============================================================================
-- 1. QQS — MIJOZ PASSPORTIDA
-- =============================================================================
-- Stavka `pricing_settings` da emas, mijoz passportida turadi: O'zbekistonda
-- u asosan TO'LOVCHIGA qarab hal bo'ladi — mijoz QQS to'lovchi bo'lmasa
-- (aylanma solig'i rejimida) faktura QQS'siz chiqadi.
--
-- `vat_payer` NULL = HALI SO'RALMAGAN. `false` bilan aralashtirmaslik
-- muhim: "to'lovchi emas" va "bilmaymiz" — ikki xil holat va interfeys
-- ikkinchisini ochiq so'raydi. Sukut bo'yicha `true` qo'yish esa
-- QQS'siz mijozga jimgina 12% qo'shib qo'yardi.
ALTER TABLE erp.client_company
    ADD COLUMN IF NOT EXISTS vat_payer BOOLEAN,
    ADD COLUMN IF NOT EXISTS vat_rate  NUMERIC(5,2);

COMMENT ON COLUMN erp.client_company.vat_payer IS
    'QQS to''lovchimi. NULL = hali so''ralmagan (false bilan bir xil emas).';
COMMENT ON COLUMN erp.client_company.vat_rate IS
    'Sukut bo''yicha stavka (%). Fakturaning HAR QATORIDA o''z nusxasi '
    'saqlanadi - keyin stavka o''zgarsa eski hujjat buzilmasin.';


-- =============================================================================
-- 2. FAKTURA
-- =============================================================================
-- SNAPSHOT: ikkala tomonning rekvizitlari fakturaga KO'CHIRILADI. Sabab
-- kartadagi tender snapshoti bilan bir xil: hujjat chiqarilgandan keyin
-- passport o'zgarsa (bank almashdi, manzil ko'chdi) ESKI hujjat o'zgarmasligi
-- kerak. Aks holda bir yil oldingi fakturani ochganda bugungi rekvizitlar
-- ko'rinardi va u boshqa hujjatga aylanardi.
CREATE TABLE IF NOT EXISTS erp.invoice (
    id             SERIAL PRIMARY KEY,

    -- Bog'lanishlar. Ikkalasi ham IXTIYORIY: faktura shartnomasiz ham
    -- chiqishi mumkin (oldindan to'lov), kartasiz ham (tenderdan tashqari
    -- savdo). Lekin mijoz MAJBURIY — fakturani kimgadir yozamiz.
    opportunity_id INT REFERENCES erp.opportunity(id) ON DELETE SET NULL,
    contract_id    INT REFERENCES erp.contract(id) ON DELETE SET NULL,
    client_id      INT NOT NULL REFERENCES erp.client_company(id),

    number         TEXT,
    issued_at      DATE,
    due_at         DATE,                     -- to'lov muddati
    currency       CHAR(3) NOT NULL DEFAULT 'UZS',

    -- draft      — qoralama, tahrirlanadi
    -- issued     — chiqarildi (qatorlar MUZLAYDI)
    -- sent       — mijozga yuborildi
    -- paid       — to'liq to'landi
    -- cancelled  — bekor qilindi
    -- Ro'yxat kodda ham bor (api/erp/invoice.py -> STATUSES).
    -- "partly_paid" YO'Q: qisman to'lov — bu HISOB natijasi (to'lovlar
    -- yig'indisi < summa), status emas. Ikki joyda saqlansa ular
    -- ajralib ketardi.
    status         TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'issued', 'sent', 'paid',
                                     'cancelled')),
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- --- MIJOZ rekvizitlari (snapshot) ---
    client_name    TEXT NOT NULL,
    client_inn     TEXT,
    client_address TEXT,
    client_bank    TEXT,
    client_mfo     TEXT,
    client_account TEXT,
    client_director TEXT,
    -- Faktura chiqarilgan paytdagi QQS holati.
    client_vat_payer BOOLEAN,

    -- --- BIZNING rekvizitlar (snapshot) ---
    own_name       TEXT,
    own_inn        TEXT,
    own_address    TEXT,
    own_bank       TEXT,
    own_mfo        TEXT,
    own_account    TEXT,
    own_director   TEXT,

    note           TEXT,
    created_by     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raqam takrorlanmasin, lekin RAQAMSIZ qoralama bo'lishi mumkin.
CREATE UNIQUE INDEX IF NOT EXISTS invoice_number_uq
    ON erp.invoice (number) WHERE number IS NOT NULL;
CREATE INDEX IF NOT EXISTS invoice_client_idx ON erp.invoice (client_id);
CREATE INDEX IF NOT EXISTS invoice_opp_idx    ON erp.invoice (opportunity_id);
CREATE INDEX IF NOT EXISTS invoice_status_idx ON erp.invoice (status);


-- =============================================================================
-- 3. QATORLAR
-- =============================================================================
-- STAVKA HAR QATORDA. Sabab: mijoz passportidagi stavka keyin o'zgarishi
-- mumkin (rejim almashdi, qonun o'zgardi), chiqarilgan hujjat esa
-- o'zgarmasligi kerak. Shuning uchun qator stavkani O'ZIDA saqlaydi.
--
-- SUMMALAR SAQLANMAYDI: net = qty * price, qqs = net * rate/100 — bular
-- HISOB natijasi. Ustunga yozilsa "nega bu son?" degan savolga ikki xil
-- javob paydo bo'lardi (ustun va formula). Ombordagi qoldiq bilan bir xil
-- qoida.
CREATE TABLE IF NOT EXISTS erp.invoice_line (
    id         SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES erp.invoice(id) ON DELETE CASCADE,

    -- Qatorlar tartibi: fakturada 1, 2, 3 deb turadi.
    pos        INT NOT NULL DEFAULT 1,

    -- Katalog bandiga ixtiyoriy bog'lanish. FK ATAYLAB yo'q (ombor
    -- jurnalidagi bilan bir xil sabab: katalog tender-ai da).
    product_id INT,
    name       TEXT NOT NULL,
    unit       TEXT,

    qty        NUMERIC(18,3) NOT NULL CHECK (qty > 0),
    -- QQS SIZ narx (birlik uchun).
    price      NUMERIC(18,2) NOT NULL CHECK (price >= 0),
    -- Stavka foizda: 12.00, 0.00 yoki NULL emas — hisob aniq bo'lsin.
    vat_rate   NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (vat_rate >= 0),

    note       TEXT
);

CREATE INDEX IF NOT EXISTS invoice_line_inv_idx ON erp.invoice_line (invoice_id);


-- =============================================================================
-- 4. TO'LOVLAR
-- =============================================================================
-- NEGA ALOHIDA JADVAL: `paid` statusi to'lovsiz YOLG'ON bo'lardi — "to'landi"
-- deb belgilangan, lekin qachon, qancha va nima bilan degan savolga javob
-- yo'q. Qisman to'lov ham shu yerdan chiqadi (yig'indi < faktura summasi),
-- alohida status sifatida saqlanmaydi.
CREATE TABLE IF NOT EXISTS erp.invoice_payment (
    id         SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES erp.invoice(id) ON DELETE CASCADE,
    paid_at    DATE NOT NULL,
    amount     NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    -- bank | cash | other — ro'yxat kodda (api/erp/invoice.py -> METHODS).
    method     TEXT NOT NULL DEFAULT 'bank'
               CHECK (method IN ('bank', 'cash', 'other')),
    doc_ref    TEXT,                          -- to'lov topshiriqnomasi raqami
    note       TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS invoice_payment_inv_idx
    ON erp.invoice_payment (invoice_id);


COMMENT ON TABLE erp.invoice IS
    'Hisob-faktura. Ikkala tomon rekvizitlari SNAPSHOT. Summalar '
    'saqlanmaydi - qatorlardan hisoblanadi.';
COMMENT ON TABLE erp.invoice_line IS
    'Faktura qatori. QQS stavkasi HAR QATORDA - keyin stavka o''zgarsa '
    'chiqarilgan hujjat buzilmasin.';
COMMENT ON TABLE erp.invoice_payment IS
    'To''lovlar. "Qisman to''landi" - hisob natijasi, status emas.';
