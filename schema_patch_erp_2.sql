-- =============================================================================
-- Sxema patch — ERP 2-BOSQICH: mijoz korxonalar bazasi va KORXONA PASSPORTI
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_2.sql
-- Talab: schema_patch_erp_1.sql allaqachon qo'llangan bo'lishi kerak.
--
-- MUAMMO: 1-bosqichda mijoz — bitta `name` maydoni. Broker qaysi korxona
-- nomidan qatnashayotganini biladi, lekin arizani to'ldirish uchun kerak
-- bo'lgan hech narsa (INN, bank rekvizitlari, direktor, manzil) tizimda yo'q.
-- Undan ham muhimi: hujjatlar cheklisti (P0-8) BROKER kompaniyasining
-- hujjatlarini tekshiradi — mijoz nomidan qatnashilganda esa MIJOZNING
-- hujjatlari kerak, ular butunlay boshqa to'plam.
--
-- YECHIM: `erp.client_company` passport ustunlari bilan kengayadi, aloqa
-- shaxslari va mijoz hujjatlari alohida jadvallarda (1:N).
--
-- MUHIM CHEGARALAR:
--   1. public.* ga TEGILMAYDI. `company_profile` va `company_document`
--      (broker kompaniyasining O'ZI) avvalgidek ishlaydi — mijoz bazasi
--      ularning o'rnini BOSMAYDI.
--   2. `erp.client_document` ustunlari `public.company_document` bilan AYNAN
--      bir xil nomlanadi — cheklist mantig'i (`build_checklist`) ikkala
--      manbadan ham o'zgarishsiz o'qiy olishi uchun.
--   3. `doc_type` uchun FK/ENUM YO'Q: kanonik ro'yxat kod bilan birga
--      versiyalanadi (`compliance.DOC_TYPES`), yangi tur qo'shilganda
--      migratsiya kerak emas — `company_document` dagi bilan bir xil qaror.
-- =============================================================================

-- --- 1. Korxona passporti ----------------------------------------------------
-- Hammasi IXTIYORIY (NULL): karta INN'siz ham yaratiladi, passport keyin
-- to'ldiriladi. Majburiy qilinsa 1-bosqichdagi mavjud mijozlar buzilardi.
ALTER TABLE erp.client_company
    ADD COLUMN IF NOT EXISTS inn            TEXT,
    ADD COLUMN IF NOT EXISTS oked           TEXT,
    ADD COLUMN IF NOT EXISTS legal_form     TEXT,   -- MCHJ / AJ / YaTT ...
    ADD COLUMN IF NOT EXISTS tax_mode       TEXT,   -- QQS to'lovchi / soddalashtirilgan
    ADD COLUMN IF NOT EXISTS address_legal  TEXT,
    ADD COLUMN IF NOT EXISTS address_actual TEXT,
    ADD COLUMN IF NOT EXISTS bank_name      TEXT,
    ADD COLUMN IF NOT EXISTS bank_mfo       TEXT,
    ADD COLUMN IF NOT EXISTS bank_account   TEXT,
    ADD COLUMN IF NOT EXISTS director_name  TEXT,
    ADD COLUMN IF NOT EXISTS phone          TEXT,
    ADD COLUMN IF NOT EXISTS email          TEXT,
    ADD COLUMN IF NOT EXISTS note           TEXT,
    ADD COLUMN IF NOT EXISTS updated_at     TIMESTAMPTZ NOT NULL DEFAULT now();

-- INN — korxonaning yagona ishonchli identifikatori: takror kiritilsa ikki
-- karta bir korxonaga tegishli bo'lib qoladi va hisobot buziladi.
-- QISMAN indeks: INN hali kiritilmagan (NULL) qatorlar cheklovga tushmaydi,
-- chunki SQL'da NULL = NULL yolg'on va oddiy UNIQUE ularni ushlamaydi.
CREATE UNIQUE INDEX IF NOT EXISTS client_company_inn_uq
    ON erp.client_company (inn) WHERE inn IS NOT NULL;

-- --- 2. Aloqa shaxslari ------------------------------------------------------
-- Bitta korxonada bir nechta odam: direktor, buxgalter, tender bo'yicha
-- mas'ul. `client_company.director_name` passportdagi RASMIY rahbar, bu
-- jadval esa KIM BILAN GAPLASHILADI degan savolga javob — ular bir xil emas.
CREATE TABLE IF NOT EXISTS erp.client_contact (
    id          SERIAL PRIMARY KEY,
    client_id   INT NOT NULL REFERENCES erp.client_company(id) ON DELETE CASCADE,
    full_name   TEXT NOT NULL,
    position    TEXT,
    phone       TEXT,
    email       TEXT,
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS client_contact_client_idx ON erp.client_contact (client_id);

-- --- 3. Mijoz hujjatlari -----------------------------------------------------
-- Ustunlar `public.company_document` bilan AYNAN bir xil (id, client_id dan
-- tashqari) — cheklist ikkala manbani ham bir xil o'qiydi.
-- MVP: fayl yuklash yo'q, `file_ref` — tashqi havola yoki yo'l.
CREATE TABLE IF NOT EXISTS erp.client_document (
    id           SERIAL PRIMARY KEY,
    client_id    INT NOT NULL REFERENCES erp.client_company(id) ON DELETE CASCADE,
    doc_type     TEXT NOT NULL,   -- compliance.DOC_TYPES kodi (FK emas — yuqoriga qarang)
    name         TEXT NOT NULL,
    number       TEXT,
    issued_at    DATE,
    -- Cheklistning yuragi. NULL = MUDDATSIZ; "muddati tugagan" deb
    -- hisoblash MUMKIN EMAS (company_document dagi bilan bir xil qoida).
    valid_until  DATE,
    file_name    TEXT,
    file_ref     TEXT,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS client_document_client_idx ON erp.client_document (client_id);
CREATE INDEX IF NOT EXISTS client_document_type_idx   ON erp.client_document (client_id, doc_type);
CREATE INDEX IF NOT EXISTS client_document_valid_idx  ON erp.client_document (valid_until);

COMMENT ON TABLE erp.client_document IS
    'Mijoz korxonaning hujjatlari. public.company_document — BROKER kompaniyasiniki; ikkalasi bir-birini almashtirmaydi.';
COMMENT ON COLUMN erp.client_company.inn IS
    'Soliq to''lovchi raqami. Qisman UNIQUE indeks: NULL lar cheklanmaydi.';
