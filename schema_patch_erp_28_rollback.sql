-- =============================================================================
-- 28-PATCHNI ORQAGA QAYTARISH
-- Ishga tushirish:
--   psql "dbname=xtxarid user=postgres host=localhost" \
--        -f schema_patch_erp_28_rollback.sql
--
-- QACHON KERAK: joylashtirishdan keyin KOD orqaga qaytarilsa
-- (28-patchdan oldingi versiyaga). Sxema o'sha holda qolsa, eski kod
-- JIMGINA buziladi — pastdagi 1-bo'limga qarang.
--
-- BU SKRIPT MA'LUMOTNI O'CHIRMAYDI
-- ════════════════════════════════
-- Jamoa a'zoliklari, umumiy vazifalar va jurnal JOYIDA QOLADI.
-- Ularni o'chirish 3-bo'limda va u ATAYLAB izohga olingan: bir marta
-- yaratilgan ish ma'lumotini orqaga qaytarish paytida yo'qotish —
-- tuzatib bo'lmaydigan xato. Kod qaytarilganda ular shunchaki
-- KO'RINMAY qoladi, yo'qolmaydi.
--
-- Idempotent: qayta yurgizish xavfsiz.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. ENG MUHIM QADAM: `done` KO'ZGU TRIGGERINI OLIB TASHLASH
-- --------------------------------------------------------------------------
-- 28-patchda `done` — `status` ning ko'zgusi va uni trigger yuritadi.
-- ESKI KOD esa `done` ni TO'G'RIDAN-TO'G'RI yozadi (`TASK_DONE_SQL`).
--
-- Trigger qolsa nima bo'ladi: eski kod `done = TRUE` deb yozadi,
-- trigger esa uni `status` dan qayta hisoblaydi va `status` hamon
-- 'yangi' bo'lgani uchun `done` DARHOL `FALSE` ga qaytadi.
--
-- Natija: "Bajarildi" tugmasi bosiladi, ekran yangilanadi va vazifa
-- yana ochiq turadi. Xato YO'Q, jurnalda hech narsa yo'q — foydalanuvchi
-- tugma "ishlamayapti" deb o'ylaydi. Bu 28-patchni orqaga qaytarishdagi
-- ENG QIMMAT nuqson, shuning uchun u birinchi bo'lib olib tashlanadi.
DROP TRIGGER IF EXISTS task_done_mirror_trg ON erp.opportunity_task;
DROP FUNCTION IF EXISTS erp.task_done_mirror();

-- Ko'zgu endi yo'q — `done` ni oxirgi marta `status` ga moslaymiz,
-- ya'ni eski kod TO'G'RI holatdan boshlaydi.
UPDATE erp.opportunity_task
   SET done = (status IN ('bajarildi', 'bekor'))
 WHERE done IS DISTINCT FROM (status IN ('bajarildi', 'bekor'));

-- --------------------------------------------------------------------------
-- 2. JURNAL TRIGGERLARI
-- --------------------------------------------------------------------------
-- Eski kod bu jadvallarni bilmaydi, lekin trigger ishlayveradi va
-- jurnalga yozaveradi. Bu ZARARSIZ (jurnal — faqat qo'shiladigan
-- jadval), shuning uchun ULAR QOLDIRILADI: o'chirish "kim
-- o'zgartirdi" degan izni yo'qotardi, foyda esa yo'q.
--
-- `erp.doc_audit_write()` funksiyasi ham QAYTARILMAYDI: uning
-- 28-patchdagi shakli eski jadvallar uchun AYNAN bir xil ishlaydi
-- (yangi tarmoqlar faqat yangi jadval nomlariga tegishli).
--
-- Yagona farq: `UPDATE` da `done` ustuni jurnaldan chiqarilgan.
-- Eski kodda `done` haqiqat manbai, ya'ni uning o'zgarishi jurnalda
-- ko'rinishi kerak. Shuni qaytaramiz.
CREATE OR REPLACE FUNCTION erp.doc_audit_write() RETURNS trigger AS $$
DECLARE
    v_doc_type text;
    v_doc_id   bigint;
    v_entity   text;
    v_status   text;
    v_actor    text := nullif(current_setting('erp.actor', true), '');
    v_old      jsonb;
    v_new      jsonb;
    k          text;
    ov         text;
    nv         text;
BEGIN
    IF TG_TABLE_NAME = 'invoice' THEN
        v_doc_type := 'invoice'; v_entity := 'invoice';
        v_doc_id := coalesce(NEW.id, OLD.id);
    ELSIF TG_TABLE_NAME = 'invoice_line' THEN
        v_doc_type := 'invoice'; v_entity := 'line';
        v_doc_id := coalesce(NEW.invoice_id, OLD.invoice_id);
    ELSIF TG_TABLE_NAME = 'invoice_payment' THEN
        v_doc_type := 'invoice'; v_entity := 'payment';
        v_doc_id := coalesce(NEW.invoice_id, OLD.invoice_id);
    ELSIF TG_TABLE_NAME = 'act' THEN
        v_doc_type := 'act'; v_entity := 'act';
        v_doc_id := coalesce(NEW.id, OLD.id);
    ELSIF TG_TABLE_NAME = 'act_line' THEN
        v_doc_type := 'act'; v_entity := 'line';
        v_doc_id := coalesce(NEW.act_id, OLD.act_id);
    ELSIF TG_TABLE_NAME = 'opportunity_file' THEN
        v_doc_type := 'karta'; v_entity := 'fayl';
        v_doc_id := coalesce(NEW.opportunity_id, OLD.opportunity_id);
    ELSIF TG_TABLE_NAME = 'opportunity_task' THEN
        v_doc_type := 'vazifa'; v_entity := 'vazifa';
        v_doc_id := coalesce(NEW.id, OLD.id);
    ELSIF TG_TABLE_NAME = 'opportunity_assignee' THEN
        v_doc_type := 'karta'; v_entity := 'jamoa';
        v_doc_id := coalesce(NEW.opportunity_id, OLD.opportunity_id);
    ELSE
        RETURN coalesce(NEW, OLD);
    END IF;

    IF v_entity IN ('invoice', 'act') THEN
        IF TG_OP = 'INSERT' THEN
            v_status := to_jsonb(NEW) ->> 'status';
        ELSE
            v_status := to_jsonb(OLD) ->> 'status';
        END IF;
    ELSIF v_entity = 'vazifa' THEN
        IF TG_OP = 'INSERT' THEN
            v_status := to_jsonb(NEW) ->> 'status';
        ELSE
            v_status := to_jsonb(OLD) ->> 'status';
        END IF;
    ELSIF v_doc_type = 'karta' THEN
        SELECT status INTO v_status FROM erp.opportunity WHERE id = v_doc_id;
    ELSIF v_doc_type = 'invoice' THEN
        SELECT status INTO v_status FROM erp.invoice WHERE id = v_doc_id;
    ELSE
        SELECT status INTO v_status FROM erp.act WHERE id = v_doc_id;
    END IF;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO erp.doc_audit (doc_type, doc_id, entity, entity_id,
                                   action, new_value, doc_status, actor)
        VALUES (v_doc_type, v_doc_id, v_entity, NEW.id, 'create',
                (to_jsonb(NEW) - 'id' - 'baytlar')::text, v_status, v_actor);
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        INSERT INTO erp.doc_audit (doc_type, doc_id, entity, entity_id,
                                   action, old_value, doc_status, actor)
        VALUES (v_doc_type, v_doc_id, v_entity, OLD.id, 'delete',
                (to_jsonb(OLD) - 'id' - 'baytlar')::text, v_status, v_actor);
        RETURN OLD;
    END IF;

    -- `done` ENDI JURNALDA: ko'zgu yo'q, ya'ni u haqiqat manbai.
    v_old := to_jsonb(OLD) - 'updated_at' - 'baytlar';
    v_new := to_jsonb(NEW) - 'updated_at' - 'baytlar';
    FOR k IN SELECT jsonb_object_keys(v_new) LOOP
        ov := v_old ->> k;
        nv := v_new ->> k;
        IF ov IS DISTINCT FROM nv THEN
            INSERT INTO erp.doc_audit (doc_type, doc_id, entity, entity_id,
                                       action, field, old_value, new_value,
                                       doc_status, actor)
            VALUES (v_doc_type, v_doc_id, v_entity, NEW.id, 'update',
                    k, ov, nv, v_status, v_actor);
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- --------------------------------------------------------------------------
-- 3. NIMA QOLDIRILADI VA NEGA
-- --------------------------------------------------------------------------
-- Quyidagilar TEGILMAYDI. Ular eski kodga xalaqit bermaydi:
--
--   `erp.opportunity_assignee`   — eski kod bu jadvalni bilmaydi.
--   `status`, `priority`, ...    — standart qiymatlari bor, ya'ni
--                                  eski `INSERT` ishlayveradi.
--   `erp.v_hodim_yuklama`        — hech kim so'ramaydi.
--   `opportunity_id` NULL ruxsati — eski kod NULL yozmaydi.
--
-- MAVJUD UMUMIY VAZIFALAR: eski kod ularni ko'rmaydi (`JOIN
-- erp.opportunity` ularni tashlab yuboradi). Ular YO'QOLMAYDI va
-- patch qayta qo'llanganda qaytadi. Nechtasi borligini bilish uchun:
--
--   SELECT count(*) FROM erp.opportunity_task WHERE opportunity_id IS NULL;
--
-- `NOT NULL` ni QAYTARISH SHART EMAS va u umumiy vazifalar mavjud
-- bo'lsa YIQILADI. Ataylab qaytarish kerak bo'lsa — avval o'sha
-- qatorlarni kartaga bog'lang yoki o'chiring, keyin:
--
--   ALTER TABLE erp.opportunity_task
--       ALTER COLUMN opportunity_id SET NOT NULL;
--
-- JADVALNI BUTUNLAY O'CHIRISH (jamoa ma'lumoti YO'QOLADI —
-- faqat ataylab, zaxira olingandan keyin):
--
--   DROP TRIGGER IF EXISTS doc_audit_trg ON erp.opportunity_assignee;
--   DROP TABLE IF EXISTS erp.opportunity_assignee;
--   DROP VIEW IF EXISTS erp.v_hodim_yuklama;

-- --------------------------------------------------------------------------
-- 4. HOLAT
-- --------------------------------------------------------------------------
DO $$
DECLARE
    n_umumiy int;
    n_jamoa  int;
BEGIN
    SELECT count(*) INTO n_umumiy FROM erp.opportunity_task
     WHERE opportunity_id IS NULL;
    SELECT count(*) INTO n_jamoa FROM erp.opportunity_assignee
     WHERE removed_at IS NULL;
    RAISE NOTICE 'Ko''zgu trigger olib tashlandi, `done` moslandi.';
    RAISE NOTICE 'Saqlanib qolgan: % ta umumiy vazifa, % ta faol jamoa a''zoligi.',
                 n_umumiy, n_jamoa;
    RAISE NOTICE 'Ular ESKI kodda KO''RINMAYDI, lekin yo''qolmadi.';
END $$;
