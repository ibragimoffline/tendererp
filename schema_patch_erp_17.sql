-- =============================================================================
-- Sxema patch — ROLLAR: 3 ta emas, 4 ta (`erp_rollar.md` v2, §2)
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_17.sql
-- Talab: schema_patch_erp_6.sql (hodim hisoblari) qo'llangan bo'lishi kerak.
--
-- MUAMMO: `manager` roli IKKI XIL ODAMNI bitta nom ostiga qo'yardi.
--
--   - DIREKTOR — hammasini ko'radi, pul hujjatini tasdiqlaydi, hisobot
--     o'qiydi. Tizimga har kuni kirmaydi.
--   - TENDER BO'LIMI BOSHLIG'I — kartalarni taqsimlaydi, yo'naltirish
--     qarorini qabul qiladi, muddatlarni kuzatadi. Kun bo'yi shu yerda.
--
-- Ikkalasi bitta rol bo'lgani uchun KUNDALIK ishning EGASI yo'q edi:
-- yo direktorga "har kuni kir" deb aytiladi (aytilmaydi), yo brokerga
-- "o'zing taqsimla" deb beriladi (u boshqalarning kartasini ko'rmasligi
-- kerak). Tender-AI tomonidagi o'lchov ham shuni ko'rsatdi: inson halqasi
-- FAQAT yo'naltirishda ishlagan (30 qaror), talab ko'rish 0, kodlash
-- qarori 0 — ya'ni bu ishlarning mas'uli tayinlanmagan edi.
--
-- YECHIM: `manager` ikkiga bo'linadi — `rahbar` va `menejer`.
--
-- NEGA MAVJUD `manager` HISOBLARI `rahbar` BO'LADI:
-- Ularning interfeysdagi yorlig'i shu paytgacha "Rahbar" edi va aynan
-- shu ma'noda berilgan. `menejer` esa YANGI ish o'rni — uni hech kim
-- egallamagan, demak avtomat tayinlash noto'g'ri bo'lardi. Kim menejer
-- bo'lishini administrator "Hodimlar" ekranida o'zi belgilaydi.
--
-- NEGA USTUN NOMI `role` QOLADI (hujjatda `rol` deyilgan):
-- Nom kod, sxema, sinov va TypeScript turlarida — to'rt joyda. Uni
-- almashtirish HECH QANDAY xatti-harakatni o'zgartirmaydi, lekin to'rt
-- joyni bir vaqtda tegishga majbur qiladi. Ro'yxatning O'ZI (qiymatlar)
-- muhim, ustun nomi emas.
--
-- NEGA QIYMATLAR O'ZBEKCHA (`rahbar`, `menejer`), `admin`/`broker` esa
-- INGLIZCHA QOLDI: mavjud ikki qiymatni almashtirish 19 ta karta, sessiya
-- va sinovlarni qayta yozishni talab qilardi — foydasi yo'q. Yangi
-- qiymatlar hujjatdagi nomlar bilan bir xil bo'lishi esa muhim: kelajakda
-- Tender-AI `erp.v_tai_actor` orqali AYNAN shu qatorlarni o'qiydi.
--
-- ERP ICHIDAGI HUQUQ o'zgarishi kodda (`api/auth.py` ROLE_RANK) va
-- keyingi bosqichda `api/erp/perm.py` da. Bu yerda faqat LUG'AT.
-- =============================================================================

-- Tartib MUHIM: eski CHECK yangi qiymatlarni o'tkazmaydi, shuning uchun
-- avval u olib tashlanadi, keyin ko'chirish, keyin yangi CHECK.
ALTER TABLE erp.app_user DROP CONSTRAINT IF EXISTS app_user_role_check;

-- Ko'chirish. Ikkinchi marta ishlatilganda `manager` qolmaydi va
-- `UPDATE` 0 qator tegadi — takrorlash xavfsiz.
UPDATE erp.app_user SET role = 'rahbar', updated_at = now()
 WHERE role = 'manager';

ALTER TABLE erp.app_user ADD CONSTRAINT app_user_role_check
    CHECK (role IN ('admin', 'rahbar', 'menejer', 'broker'));

COMMENT ON COLUMN erp.app_user.role IS
    'Rol: admin (tizim sozlovchi), rahbar (direktor), menejer (tender '
    'bo''limi boshlig''i), broker (ijrochi). Ro''yxat KODDA ham bor '
    '(api/auth.py ROLES) va _tests/erp11_test.py ikkalasini solishtiradi. '
    'Yangi rol qo''shilsa uchala joy birga o''zgaradi.';
