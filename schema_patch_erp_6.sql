-- =============================================================================
-- Sxema patch — AUTH TUZATISHI: hodimlar ERP niki
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_6.sql
-- Talab: schema_patch_erp_1..5.sql qo'llangan bo'lishi kerak.
--
-- NIMA XATO EDI: auth-1 da foydalanuvchilar TENDER-AI ga qo'yilgan edi
-- (`public.app_user`) va ERP tokenni HTTP orqali tekshirardi. Bu domen
-- modeliga zid:
--
--   Tender-AI  — KOMPANIYA hisobi bilan kiriladi (tender agregatori).
--   Tender ERP — kompaniyaning O'Z ERP tizimi; HODIMLAR shu yerda ishlaydi.
--   Tender-AI da tender olish ERP dan kelayotgan hodimga biriktiriladi.
--
-- Ya'ni ODAM (hodim) — ERP ning tushunchasi, kompaniya esa tender-ai niki.
-- Kimlik teskari tomonda turgan edi.
--
-- YECHIM: hodim hisoblari ERP ga ko'chadi (`erp.app_user`), sessiya ham.
-- ERP endi o'z kimlik manbai — tekshirish uchun tarmoqqa chiqmaydi.
--
-- YUTUQ: `broker_id` endi HAQIQIY FK bo'ladi — hodim (`erp.broker`) va uning
-- hisobi bitta sxemada. Auth-1 da bu mumkin emas edi (boshqa sxema, FK yo'q).
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.app_user (
    id            SERIAL PRIMARY KEY,
    -- Kirish nomi kichik harflarda (kodda normallashtiriladi).
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    -- pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    password_hash TEXT NOT NULL,
    -- Rollar kodda ham (api/auth.py ROLES), bazada ham; sinov solishtiradi.
    role          TEXT NOT NULL DEFAULT 'broker'
                  CHECK (role IN ('admin', 'manager', 'broker')),
    -- HODIM bilan bog'lanish. Endi HAQIQIY FK: hisob ham, hodim ham `erp` da.
    -- ON DELETE SET NULL: hodim yozuvi o'chsa hisob qolaveradi (lekin
    -- `erp.broker` ham amalda o'chirilmaydi — `active=false`).
    broker_id     INT REFERENCES erp.broker(id) ON DELETE SET NULL,
    email         TEXT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS app_user_active_idx  ON erp.app_user (active);
-- Bitta hodimga bitta hisob (bog'langan bo'lsa) — "mening ishlarim" filtri
-- ikki xil javob bermasin.
CREATE UNIQUE INDEX IF NOT EXISTS app_user_broker_uq
    ON erp.app_user (broker_id) WHERE broker_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS erp.app_session (
    id            SERIAL PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    -- Tokenning O'ZI emas, sha256 xeshi. Xom token faqat brauzerda.
    token_hash    TEXT NOT NULL UNIQUE,
    expires_at    TIMESTAMPTZ NOT NULL,
    user_agent    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS app_session_user_idx ON erp.app_session (user_id);
CREATE INDEX IF NOT EXISTS app_session_exp_idx  ON erp.app_session (expires_at);

-- --- Auth-1 da yaratilgan hisoblarni KO'CHIRISH ------------------------------
-- Bir martalik va idempotent. Parol xeshlari o'zgarishsiz ko'chadi, ya'ni
-- foydalanuvchilar o'sha parol bilan kiraveradi.
-- `broker_id` KO'CHIRILMAYDI: u yerda FK yo'q edi va qiymatlar bo'sh.
INSERT INTO erp.app_user (username, full_name, password_hash, role, email,
                          active, last_login_at, created_at)
SELECT u.username, u.full_name, u.password_hash, u.role, u.email,
       u.active, u.last_login_at, u.created_at
FROM public.app_user u
WHERE EXISTS (SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public' AND table_name = 'app_user')
  AND NOT EXISTS (SELECT 1 FROM erp.app_user e WHERE e.username = u.username);

-- Sessiyalar KO'CHIRILMAYDI: hamma qaytadan kiradi. Tokenlar qisqa umrli
-- va ularni ko'chirish qiymat bermaydi.

COMMENT ON TABLE erp.app_user IS
    'HODIM hisoblari. Odam — ERP ning tushunchasi; tender-ai esa KOMPANIYA hisobi bilan kiriladi.';
COMMENT ON COLUMN erp.app_user.broker_id IS
    'erp.broker.id — hodimning kartalari va vazifalari shu bog''lanish orqali topiladi.';
COMMENT ON TABLE erp.app_session IS
    'Faol sessiyalar. Token BAZADA XESH ko''rinishida.';
