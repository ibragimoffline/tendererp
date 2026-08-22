-- =============================================================================
-- Sxema patch — TANNARX ombor harakatida (foyda hisobi uchun)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_14.sql
-- Talab: schema_patch_erp_8.sql (ombor).
--
-- SAVOL: "bu tenderdan qancha ishladik?" Javob uchun ikki son kerak:
--   DAROMAD — fakturadagi QQS SIZ summa (QQS bizniki emas, u davlatniki);
--   TANNARX — chiqib ketgan tovarning tannarxi.
--
-- MUAMMO: tannarx tender-ai katalogida (`catalog_product.cost_price`) va u
-- O'ZGARADI. Bugungi tannarx bilan o'tgan yilgi chiqimni hisoblasak,
-- foyda raqami har oy o'zgarib turardi va hech qachon to'g'ri bo'lmasdi.
--
-- YECHIM: tannarx HARAKAT PAYTIDA muzlatiladi. Loyihadagi boshqa
-- snapshotlar bilan bir xil qoida (tender, rekvizitlar, faktura qatori).
--
-- `NULL` = NOMA'LUM va u NOL EMAS:
--   * eski qatorlar (bu patchdan oldingilar) — tannarxi yozilmagan;
--   * katalogda tannarx ko'rsatilmagan mahsulotlar.
-- Foyda hisobi bunday qatorlarni ALOHIDA sanaydi va "hisob to'liq emas"
-- deb ochiq aytadi. Nolga aylantirish foydani sun'iy oshirib ko'rsatardi.
-- =============================================================================

ALTER TABLE erp.stock_move
    ADD COLUMN IF NOT EXISTS unit_cost NUMERIC(18,2);

COMMENT ON COLUMN erp.stock_move.unit_cost IS
    'Harakat paytidagi BIRLIK TANNARXI (public.catalog_product.cost_price '
    'dan ko''chiriladi). NULL = noma''lum, NOL EMAS: foyda hisobi bunday '
    'qatorlarni alohida sanaydi.';
