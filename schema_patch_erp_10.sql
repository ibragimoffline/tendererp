-- =============================================================================
-- Sxema patch — REZERVATSIYA (5B-1 davomi)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_10.sql
-- Talab: schema_patch_erp_8.sql qo'llangan bo'lishi kerak.
--
-- MUAMMO: ombor jurnali "nima kirdi, nima chiqdi" degan savolga javob
-- beradi. Lekin tender ustida ishlayotganda uchinchi holat bor: tovar
-- HALI CHIQMAGAN, ammo BOSHQA tenderga va'da qilib bo'lmaydi.
--
-- Buni chiqim bilan yozib qo'yish XATO bo'lardi: omborda tovar turibdi,
-- jurnalda esa yo'q. Shuning uchun REZERV — alohida tushuncha:
--   * qoldiqni KAMAYTIRMAYDI (jismoniy qoldiq o'zgarmaydi);
--   * MAVJUD miqdorni kamaytiradi (mavjud = qoldiq - rezerv).
--
-- STATUS QOIDASI (kartaning statusiga bog'langan):
--   confirmed          -> rezerv qo'yiladi (qo'lda)
--   submitted..        -> ushlab turiladi
--   won                -> SARFLANADI: chiqim harakati yoziladi
--   lost / rejected    -> BO'SHAYDI
--
-- NEGA KARTAGA FK BOR (ombor jurnalidan farqli): rezerv kartasiz ma'nosiz
-- — u "shu ish uchun ajratildi" degani. Karta o'chsa rezerv ham o'chadi.
-- Jurnal esa qoladi: u sodir bo'lgan HARAKAT, rezerv esa NIYAT.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.stock_reserve (
    id             SERIAL PRIMARY KEY,
    opportunity_id INT NOT NULL REFERENCES erp.opportunity(id) ON DELETE CASCADE,

    -- public.catalog_product.id — FK ATAYLAB yo'q (stock_move dagi bilan
    -- bir xil sabab), nom snapshot qilinadi.
    product_id     INT NOT NULL,
    product_name   TEXT NOT NULL,
    unit           TEXT,

    -- Rezerv MUSBAT: u ayirma emas, "ajratilgan miqdor".
    qty            NUMERIC(18,3) NOT NULL CHECK (qty > 0),

    -- held      — ushlab turilibdi (mavjud miqdordan ayiriladi)
    -- consumed  — sarflandi (karta yutildi; chiqim harakati yozildi)
    -- released  — bo'shatildi (yutqazildi/rad etildi yoki qo'lda)
    -- Ro'yxat kodda ham bor (api/erp/stock.py -> RESERVE_STATES).
    status         TEXT NOT NULL DEFAULT 'held'
                   CHECK (status IN ('held', 'consumed', 'released')),

    -- Sarflanganda yozilgan chiqim harakati. Bog'lanish ikki tomonlama
    -- savolga javob beradi: "bu chiqim qaysi rezervdan?" va aksincha.
    move_id        INT REFERENCES erp.stock_move(id) ON DELETE SET NULL,

    note           TEXT,
    created_by     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Qachon yopildi (sarflandi yoki bo'shadi).
    closed_at      TIMESTAMPTZ,
    closed_by      TEXT
);

CREATE INDEX IF NOT EXISTS stock_reserve_opp_idx  ON erp.stock_reserve (opportunity_id);
CREATE INDEX IF NOT EXISTS stock_reserve_prod_idx ON erp.stock_reserve (product_id);
-- Faol rezervlar tez topilsin: qoldiq hisobi HAR so'rovda shularni yig'adi.
CREATE INDEX IF NOT EXISTS stock_reserve_held_idx
    ON erp.stock_reserve (product_id) WHERE status = 'held';


-- =============================================================================
-- SHARTNOMA-VIEW yangilanadi: `reserved` va `available` qo'shiladi.
--
-- `qty` — JISMONIY qoldiq (jurnal yig'indisi), o'zgarmadi.
-- `reserved` — ushlab turilgan miqdor.
-- `available` — tender-ai ning "yetadimi?" savoliga javob beradigan son.
--
-- Mahsulotda harakat yo'q, lekin rezerv bor holati BO'LMAYDI (rezerv
-- qo'yish uchun mahsulot kerak), shuning uchun FULL JOIN shart emas —
-- lekin ehtiyot uchun rezervlar ham jamlanadi.
-- =============================================================================
-- DROP kerak: `CREATE OR REPLACE VIEW` ustunlarni QAYTA TARTIBLAY
-- olmaydi (yangi `reserved` ustuni o'rtaga tushadi). View ga hech
-- narsa bog'lanmagan, shuning uchun tushirib qayta yaratamiz.
DROP VIEW IF EXISTS erp.v_stock_balance;

CREATE VIEW erp.v_stock_balance AS
WITH moves AS (
    SELECT m.product_id,
           (array_agg(m.product_name ORDER BY m.created_at DESC, m.id DESC))[1]
                              AS product_name,
           (array_agg(m.unit ORDER BY m.created_at DESC, m.id DESC))[1] AS unit,
           SUM(m.qty)         AS qty,
           max(m.created_at)  AS updated_at,
           count(*)           AS move_count
    FROM erp.stock_move m
    GROUP BY m.product_id
),
held AS (
    SELECT r.product_id,
           (array_agg(r.product_name ORDER BY r.created_at DESC, r.id DESC))[1]
                              AS product_name,
           (array_agg(r.unit ORDER BY r.created_at DESC, r.id DESC))[1] AS unit,
           SUM(r.qty)         AS reserved,
           count(*)           AS reserve_count
    FROM erp.stock_reserve r
    WHERE r.status = 'held'
    GROUP BY r.product_id
)
SELECT COALESCE(m.product_id, h.product_id)          AS product_id,
       COALESCE(m.product_name, h.product_name)      AS product_name,
       COALESCE(m.unit, h.unit)                      AS unit,
       COALESCE(m.qty, 0)                            AS qty,
       COALESCE(h.reserved, 0)                       AS reserved,
       COALESCE(m.qty, 0) - COALESCE(h.reserved, 0)  AS available,
       m.updated_at,
       COALESCE(m.move_count, 0)                     AS move_count,
       COALESCE(h.reserve_count, 0)                  AS reserve_count
FROM moves m
FULL JOIN held h ON h.product_id = m.product_id;

COMMENT ON VIEW erp.v_stock_balance IS
    'SHARTNOMA: tender-ai shu view ni o''qiydi (faqat o''qish) - api/erp_stock.py. '
    'qty = jismoniy qoldiq, reserved = ushlab turilgani, available = qty - reserved. '
    'Ustunlarini o''zgartirish tender-ai ni buzadi; erp7_test.py tekshiradi.';

COMMENT ON TABLE erp.stock_reserve IS
    'Rezerv: "shu karta uchun ajratildi". Qoldiqni KAMAYTIRMAYDI, MAVJUD '
    'miqdorni kamaytiradi. Karta yutilganda chiqimga aylanadi.';
