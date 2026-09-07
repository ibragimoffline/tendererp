-- =============================================================================
-- ERP 26-patch — CHATDA ESLATISH: kimga bildirishnoma YUBORILGAN
-- =============================================================================
--
-- MUAMMO: `@ism` eslatish 25-patchda qurilgan, lekin faqat XABAR
-- YOZILGANDA ishlardi. Xabar tahrirlanib unga yangi eslatish qo'shilsa
-- ("eslatishni unutdim, tahrirlab qo'shdim") bildirishnoma KETMASDI.
--
-- Uni ishlatish uchun "kimga allaqachon yuborilgan" ni bilish kerak:
-- aks holda har tahrirda BARCHA eslatilganlarga takror bildirishnoma
-- ketardi va bir necha tahrirdan keyin odam ularni o'qimay yopishni
-- odat qilardi — shundan keyin HAQIQIY eslatish ham ko'rinmay qolardi.
--
-- NEGA XABARDA, ALOHIDA JADVALDA EMAS: bu bittalik ro'yxat, xabarga
-- 1:1 tegishli va u bilan birga o'chadi. Alohida jadval `JOIN` va
-- tozalash qoidasini talab qilardi, hech qanday yangi savolga javob
-- bermasdan.
--
-- NEGA "eslatilgan", "mentions" emas: ustun HOZIR KIM ESLATILGANINI
-- emas, KIMGA BILDIRISHNOMA YUBORILGANINI saqlaydi. Foydalanuvchi
-- matndan ismni o'chirsa ham u yerda qoladi — chunki bildirishnoma
-- allaqachon ketgan va uni "qaytarib olib" bo'lmaydi. Nom noto'g'ri
-- bo'lsa, kod "eslatishni bekor qilish" degan mavjud bo'lmagan
-- xatti-harakatni kutgan bo'lardi.
--
-- Idempotent: qayta yurgizish xavfsiz.
-- =============================================================================

ALTER TABLE erp.chat_message
    ADD COLUMN IF NOT EXISTS eslatilgan INT[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN erp.chat_message.eslatilgan IS
    'Kimga `chat_mention` bildirishnomasi YUBORILGAN (erp.app_user.id). '
    'Tahrirda faqat shu ro''yxatda YO''Q id larga yuboriladi — takror '
    'bildirishnoma bo''lmasin. Matndan ism o''chirilsa ham id bu yerda '
    'qoladi: yuborilgan xabarni qaytarib olib bo''lmaydi.';

-- FK ATAYLAB yo'q: massivga FK qo'yib bo'lmaydi va kerak ham emas —
-- hisob o'chirilsa (amalda `active = false`, o'chirish yo'q) bu yerda
-- qolgan id shunchaki hech kimga mos kelmaydi va zarari yo'q.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON erp.chat_message TO erp;
    END IF;
END $$;
