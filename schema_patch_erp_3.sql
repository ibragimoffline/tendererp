-- =============================================================================
-- Sxema patch — ERP 3-BOSQICH: vazifalar, eslatmalar va yutqazish sabablari
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_3.sql
-- Talab: schema_patch_erp_1.sql va _2.sql allaqachon qo'llangan bo'lishi kerak.
--
-- MUAMMO: kartada bitta "keyingi vazifa" maydoni bor (`next_task`,
-- `next_task_at`). U bitta ishni eslatadi, lekin ro'yxat bo'lmagani uchun
-- ikkinchi ish yozilsa birinchisi YO'QOLADI — va hech kim eslatmaydi:
-- muddat o'tib ketganini broker faqat o'zi qaraganda biladi.
--
-- YECHIM: vazifalar ALOHIDA jadval (1:N) + eslatma skripti uchun "yuborilgan"
-- belgisi. Eslatma kuniga bir marta yuriladi va TAKROR YUBORMAYDI.
--
-- MUHIM CHEGARALAR:
--   1. public.* ga TEGILMAYDI. Xabar yuborish TRANSPORTI ham tender-ai'da
--      qoladi (bot tokeni va SMTP rekvizitlari o'sha yerda) — ERP unga
--      tayyor matnni beradi, sirlar ERP'ga ko'chmaydi.
--   2. `next_task` / `next_task_at` ustunlari O'CHIRILMAYDI: eski kartalar
--      buzilmasin va ma'lumot yo'qolmasin. Ular bir martalik ko'chiriladi
--      (pastda) va bundan keyin interfeys ro'yxat bilan ishlaydi.
--   3. Vazifa o'chirilishi MUMKIN (kartadan farqli): u ish rejasi, tarix
--      emas. Bajarilgani esa `done` bilan qoladi.
-- =============================================================================

-- --- 1. Vazifalar ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.opportunity_task (
    id                  SERIAL PRIMARY KEY,
    opportunity_id      INT NOT NULL REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    -- Mas'ul: odatda kartaning brokeri, lekin boshqasiga ham berilishi mumkin
    -- (masalan hujjatlarni buxgalter tayyorlaydi).
    assignee_broker_id  INT REFERENCES erp.broker(id),
    due_at              DATE,
    done                BOOLEAN NOT NULL DEFAULT FALSE,
    done_at             TIMESTAMPTZ,
    note                TEXT,
    -- Eslatma YUBORILGAN vaqti. NULL = hali yuborilmagan. Skript shu ustunga
    -- qarab takror yubormaydi — alohida "yuborilganlar" jadvali kerak emas.
    reminded_at         TIMESTAMPTZ,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS opp_task_opp_idx ON erp.opportunity_task (opportunity_id);
-- "Bugungi ishlarim" va eslatma skripti uchun asosiy so'rov: bajarilmagan
-- vazifalar, muddat bo'yicha. Qisman indeks — bajarilganlari ko'p bo'ladi.
CREATE INDEX IF NOT EXISTS opp_task_due_idx
    ON erp.opportunity_task (due_at) WHERE NOT done;
CREATE INDEX IF NOT EXISTS opp_task_assignee_idx
    ON erp.opportunity_task (assignee_broker_id) WHERE NOT done;

-- --- 2. Kartaga ikki ustun ---------------------------------------------------
ALTER TABLE erp.opportunity
    -- Nega yutqazildi: narx, muddat, hujjat, texnik talab... Keyingi tahlil
    -- uchun ERKIN MATN emas, kod (ro'yxat api/erp/tasks.py da).
    ADD COLUMN IF NOT EXISTS lost_reason TEXT,
    -- Deadline eslatmasi yuborilgan vaqti (vazifadagi bilan bir xil mantiq).
    ADD COLUMN IF NOT EXISTS deadline_reminded_at TIMESTAMPTZ;

-- Ro'yxat kodda ham, bazada ham: LOST_REASONS bilan bir xil bo'lishi shart.
-- Kengaytirilganda: DROP CONSTRAINT IF EXISTS + ADD CONSTRAINT.
ALTER TABLE erp.opportunity DROP CONSTRAINT IF EXISTS opportunity_lost_reason_check;
ALTER TABLE erp.opportunity ADD CONSTRAINT opportunity_lost_reason_check
    CHECK (lost_reason IS NULL OR lost_reason IN
           ('price', 'deadline', 'documents', 'requirements', 'capacity',
            'client_declined', 'other'));

-- --- 3. Eski "keyingi vazifa" ni ro'yxatga ko'chirish -------------------------
-- BIR MARTALIK va IDEMPOTENT: faqat mos vazifasi yo'q kartalar uchun.
-- Ustunlarning o'zi joyida qoladi (yuqoridagi 2-chegara).
INSERT INTO erp.opportunity_task (opportunity_id, title, assignee_broker_id,
                                  due_at, created_by, note)
SELECT o.id, o.next_task, o.broker_id, o.next_task_at, o.created_by,
       'schema_patch_erp_3.sql: eski "keyingi vazifa" maydonidan ko''chirildi'
FROM erp.opportunity o
WHERE o.next_task IS NOT NULL AND btrim(o.next_task) <> ''
  AND NOT EXISTS (SELECT 1 FROM erp.opportunity_task t
                  WHERE t.opportunity_id = o.id AND t.title = o.next_task);

COMMENT ON TABLE erp.opportunity_task IS
    'Karta bo''yicha ish rejasi. Kartadan farqli o''laroq O''CHIRILISHI mumkin: bu reja, tarix emas.';
COMMENT ON COLUMN erp.opportunity_task.reminded_at IS
    'Eslatma yuborilgan vaqt. NULL = yuborilmagan; skript shu ustunga qarab takror yubormaydi.';
COMMENT ON COLUMN erp.opportunity.lost_reason IS
    'Yutqazish sababi (kod). Ro''yxat api/erp/tasks.py dagi LOST_REASONS bilan bir xil.';
