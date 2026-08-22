-- =============================================================================
-- Sxema patch — OMBOR (5B-1). Qoldiq egasi: ERP.
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_8.sql
-- Talab: schema_patch_erp_1..7.sql qo'llangan bo'lishi kerak.
--
-- QAROR (`erp_arxitektura_3.md` 4.3 va 6.1): qoldiqning EGASI — ERP,
-- "A1" yo'li bilan:
--   * harakat jurnali (`erp.stock_move`) va qoldiq SHU YERDA;
--   * tender-ai qoldiqni `erp.v_stock_balance` VIEW idan O'QIYDI va
--     o'zining `catalog_product.stock_qty` ustuniga TAYANMAYDI;
--   * `public.*` ga yozmaslik qoidasi BUZILMAYDI.
--
-- NEGA JURNAL, "qoldiq" ustuni EMAS: qoldiq — HISOB natijasi, saqlanadigan
-- fakt emas. Ustun bo'lsa "nega 12 dona?" degan savolga javob yo'q. Jurnal
-- bo'lsa har o'zgarish kim, qachon, nima uchun deb yozilgan bo'ladi va
-- qoldiq shundan chiqadi (`SUM`).
--
-- MAHSULOT O'ZI TENDER-AI DA (`catalog_product`): u yerda katalog moslashuvi
-- va bildirishnoma uchun ishlatiladi, ikkinchi nusxasi kerak emas.
-- Shu sababli bu yerda FK YO'Q va NOM SNAPSHOT qilinadi — kartadagi tender
-- snapshoti bilan bir xil sabab:
--   * FK `public.catalog_product` ga bog'lansa, u yerdagi o'chirish ERP
--     jurnalini yiqitardi yoki bloklab qo'yardi;
--   * mahsulot o'chirilsa ham OMBOR TARIXI qolishi kerak — "nima chiqdi"
--     degan savolga javob yo'qolmasin.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.stock_move (
    id            SERIAL PRIMARY KEY,
    -- public.catalog_product.id — FK EMAS (yuqoridagi izoh).
    product_id    INT NOT NULL,
    -- Snapshot: mahsulot o'chirilsa/nomlansa ham jurnal o'qiladi.
    product_name  TEXT NOT NULL,
    unit          TEXT,

    -- Harakat turi. Ro'yxat kodda ham bor (api/erp/stock.py -> KINDS) va
    -- sinov ikkalasini solishtiradi.
    kind          TEXT NOT NULL
                  CHECK (kind IN ('opening', 'in', 'out', 'adjust')),

    -- MIQDOR ISHORALI: kirim +, chiqim -. Qoldiq = SUM(qty), ya'ni view da
    -- CASE kerak emas va "qaysi turni qo'shish, qaysinisini ayirish" degan
    -- qoida bitta joyda — CHECK da — turadi.
    -- API dan MUSBAT son keladi, ishorani `api/erp/stock.py` qo'yadi.
    qty           NUMERIC(18,3) NOT NULL CHECK (qty <> 0),
    CONSTRAINT stock_move_sign_check CHECK (
        (kind IN ('opening', 'in') AND qty > 0)
        OR (kind = 'out' AND qty < 0)
        OR kind = 'adjust'          -- inventarizatsiya: ikki tomonga ham
    ),

    -- Ixtiyoriy bog'lanish: qaysi karta uchun chiqdi. Karta o'chsa
    -- harakat qoladi (ombor haqiqati kartaga bog'liq emas).
    opportunity_id INT REFERENCES erp.opportunity(id) ON DELETE SET NULL,

    -- Hujjat raqami (nakladnoy, akt) — bo'lsa.
    doc_ref       TEXT,
    note          TEXT,

    -- Sessiyadan olinadi (auth-1 dan beri mijozdan qabul qilinmaydi).
    created_by    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS stock_move_product_idx ON erp.stock_move (product_id);
CREATE INDEX IF NOT EXISTS stock_move_created_idx ON erp.stock_move (created_at DESC);
CREATE INDEX IF NOT EXISTS stock_move_opp_idx     ON erp.stock_move (opportunity_id)
    WHERE opportunity_id IS NOT NULL;

-- Bitta mahsulotga BITTA boshlang'ich qoldiq: aks holda import ikki marta
-- yurganda qoldiq ikkilanardi.
CREATE UNIQUE INDEX IF NOT EXISTS stock_move_opening_uq
    ON erp.stock_move (product_id) WHERE kind = 'opening';


-- =============================================================================
-- SHARTNOMA-VIEW — tender-ai shuni o'qiydi (schema_patch_erp_7.sql dagi
-- `v_tender_status` bilan bir xil naqsh).
--
-- Faqat mahsulot va son: tannarx, hujjat raqami va izoh BERILMAYDI —
-- tender-ai ga "yetadimi?" degan savol uchun ular kerak emas.
-- =============================================================================
CREATE OR REPLACE VIEW erp.v_stock_balance AS
SELECT m.product_id,
       -- Eng oxirgi harakatdagi nom va o'lchov birligi: mahsulot
       -- qayta nomlansa jurnalda eski nomlar ham qoladi.
       (array_agg(m.product_name ORDER BY m.created_at DESC, m.id DESC))[1]
                            AS product_name,
       (array_agg(m.unit ORDER BY m.created_at DESC, m.id DESC))[1]
                            AS unit,
       SUM(m.qty)           AS qty,
       max(m.created_at)    AS updated_at,
       count(*)             AS move_count
FROM erp.stock_move m
GROUP BY m.product_id;

COMMENT ON VIEW erp.v_stock_balance IS
    'SHARTNOMA: tender-ai shu view ni o''qiydi (faqat o''qish) - api/erp_stock.py. '
    'Ustunlarini o''zgartirish tender-ai ni buzadi; erp7_test.py tekshiradi.';

COMMENT ON TABLE erp.stock_move IS
    'Ombor harakatlari jurnali. Qoldiq - SUM(qty), alohida ustun yo''q. '
    'product_id -> public.catalog_product.id (FK ATAYLAB yo''q, nom snapshot).';
