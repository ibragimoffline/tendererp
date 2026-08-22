-- =============================================================================
-- Sxema patch — ERP 4-BOSQICH: TAKLIF va TOPSHIRISH
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_4.sql
-- Talab: schema_patch_erp_1..3.sql allaqachon qo'llangan bo'lishi kerak.
--
-- MUAMMO: "Topshirildi" statusi faqat BELGI. Qaysi narx bilan topshirildi,
-- o'sha paytda cheklist qanday edi, qaysi hujjatlar bilan ketdi — hech
-- qayerda qolmaydi. Bir oydan keyin "nega bu narxni qo'ygan ekanmiz?"
-- degan savolga javob yo'q, chunki smeta o'shandan beri qayta hisoblangan.
--
-- YECHIM: topshirilgan taklif MUZLATILADI. `erp.submission` — o'sha
-- paytdagi holatning nusxasi, xuddi opportunity snapshot'i kabi.
--
-- MUHIM CHEGARALAR:
--   1. public.* ga TEGILMAYDI. Narx hisobi (`tender_pricing`) va cheklist
--      qoidalari tender-ai'da qoladi; ERP ularni O'QIYDI va nusxasini
--      saqlaydi.
--   2. Taklif O'CHIRILMAYDI va TAHRIRLANMAYDI. Xato bo'lsa yangi versiya
--      qo'shiladi — tarix rahbar uchun ma'lumot (kartadagi bilan bir xil
--      qoida).
--   3. JSONB ATAYLAB: narx hisobining tarkibi (`pricing.py` natijasi)
--      vaqt o'tib o'zgarishi mumkin, muzlatilgan nusxa esa O'SHA PAYTDAGI
--      shaklda qolishi kerak. Ustunlarga yoyilsa har o'zgarishda migratsiya
--      kerak bo'lardi va eski yozuvlar buzilardi.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.submission (
    id              SERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    -- Versiya: bitta karta bo'yicha bir necha marta topshirilishi mumkin
    -- (qayta e'lon, tuzatilgan taklif). 1 dan boshlab o'sadi.
    version         INT NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_by    TEXT,                  -- auth yo'q: tanlangan broker nomi

    -- --- taklifning O'ZI ---
    price           NUMERIC,               -- taklif qilingan narx
    currency        TEXT,
    -- Narx hisobining to'liq nusxasi (tender-ai `tender_pricing` dan).
    -- NULL = smeta hisoblanmagan holda topshirilgan (bu ham ma'lumot).
    pricing         JSONB,
    -- Cheklist holati: nechta tayyor / yetishmaydi / muddati o'tgan + bandlar.
    compliance      JSONB,
    -- Mijoz hujjatlari ro'yxati (o'sha paytdagi nomlar va muddatlar).
    documents       JSONB,

    -- Cheklistda to'siq bo'lsa ham topshirilganmi. Taqiq YO'Q — ogohlantirish
    -- bor, lekin qaror odamniki; shu ustun "ogohlantirish ko'rsatilgan va
    -- tasdiqlangan" degan yozuv.
    blocking_count  INT NOT NULL DEFAULT 0,
    confirmed_note  TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Bir karta bo'yicha bir versiya raqami bir marta
    UNIQUE (opportunity_id, version)
);

CREATE INDEX IF NOT EXISTS submission_opp_idx ON erp.submission (opportunity_id);
CREATE INDEX IF NOT EXISTS submission_at_idx  ON erp.submission (submitted_at DESC);

COMMENT ON TABLE erp.submission IS
    'Topshirilgan taklifning MUZLATILGAN nusxasi. O''chirilmaydi va tahrirlanmaydi: xato bo''lsa yangi versiya.';
COMMENT ON COLUMN erp.submission.pricing IS
    'tender-ai dagi tender_pricing nusxasi. JSONB: hisob tarkibi o''zgarsa ham eski yozuv o''sha shaklda qoladi.';
COMMENT ON COLUMN erp.submission.blocking_count IS
    'Topshirish paytida cheklistda nechta to''siq bor edi. Taqiq emas — ogohlantirish tasdiqlangani.';
