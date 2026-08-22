-- =============================================================================
-- Sxema patch — PUL HUJJATLARI UCHUN O'ZGARISHLAR JURNALI
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_16.sql
-- Talab: schema_patch_erp_11.sql (faktura), schema_patch_erp_12.sql (akt).
--
-- SAVOL: "kim, qachon va nimani o'zgartirdi?"
--
-- Faktura `issued` bo'lgandan keyin O'ZGARMAYDI degan qoida kodda bor
-- (`invoice.py` muzlatish tekshiruvi) va sinovda ham bor. Lekin ikkalasi
-- ham FAQAT ILOVA orqali o'tgan o'zgarishlarni ushlaydi. Bazaga to'g'ridan
-- to'g'ri `UPDATE` yozilsa, hech qanday iz qolmasdi va "hujjat
-- o'zgarmagan" degan gapni tasdiqlaydigan hech narsa yo'q edi.
--
-- NEGA TRIGGER, ILOVA KODI EMAS:
-- Ilova qatlamidagi jurnal o'zi yozgan o'zgarishlarni yozadi — ya'ni u
-- "men hech narsa o'zgartirmadim" degan gapning O'ZI aytgan dalili.
-- Trigger esa `psql` dan kelgan qo'l bilan yozilgan `UPDATE` ni ham
-- ushlaydi. Audit ma'nosi shunda: uni chetlab o'tib bo'lmasin.
--
-- KIM O'ZGARTIRDI (`actor`):
-- Bazada sessiya foydalanuvchisi yo'q (hammasi bitta `postgres` ulanishi),
-- shuning uchun ism ilovadan `SET LOCAL erp.actor` orqali beriladi.
-- Berilmagan bo'lsa `NULL` qoladi va bu YASHIRILMAYDI: `NULL` = "ERP
-- dan tashqarida o'zgartirilgan". Aynan shunday qatorlar eng qiziq.
--
-- FK YO'Q — ATAYLAB:
-- Jurnal hujjat o'chirilgandan KEYIN ham qolishi kerak. `ON DELETE CASCADE`
-- bo'lsa, hujjatni o'chirish uning tarixini ham o'chirardi — ya'ni izni
-- yo'qotishning eng oson yo'li ochiq qolardi.
--
-- JURNALNI O'ZGARTIRIB BO'LMAYDI:
-- `UPDATE` butunlay taqiqlangan (o'zgartirilgan yozuv — soxta yozuv).
-- `DELETE` esa faqat `erp.audit_purge` bayrog'i ATAYLAB yoqilganda
-- ishlaydi (saqlash muddati tugagan yozuvlarni tozalash va sinovlar
-- uchun). Ya'ni tasodifan o'chirib bo'lmaydi.
-- =============================================================================

CREATE TABLE IF NOT EXISTS erp.doc_audit (
    id          bigserial PRIMARY KEY,
    --: 'invoice' | 'act'
    doc_type    text        NOT NULL,
    --: Hujjatning o'zi (faktura yoki akt) id si. FK ATAYLAB yo'q.
    doc_id      bigint      NOT NULL,
    --: O'zgargan yozuv turi: 'invoice' | 'act' | 'line' | 'payment'
    entity      text        NOT NULL,
    entity_id   bigint,
    --: 'create' | 'update' | 'delete'
    action      text        NOT NULL,
    --: `update` da — ustun nomi. `create`/`delete` da NULL.
    field       text,
    old_value   text,
    new_value   text,
    --: O'ZGARISH PAYTIDAGI hujjat holati. Eng muhim ustun: "chiqarilgan
    --: fakturaga tegilganmi?" degan savolga to'g'ridan-to'g'ri javob.
    doc_status  text,
    --: NULL = ERP dan tashqarida (to'g'ridan-to'g'ri SQL).
    actor       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE erp.doc_audit IS
    'Pul hujjatlari (faktura, akt) o''zgarishlari jurnali. Triggerlar '
    'yozadi, ilova kodi emas — qo''lda yozilgan SQL ham ushlanadi. '
    'UPDATE taqiqlangan, DELETE faqat erp.audit_purge yoqilganda.';
COMMENT ON COLUMN erp.doc_audit.actor IS
    'Kim o''zgartirgani (SET LOCAL erp.actor). NULL = ERP dan tashqarida.';
COMMENT ON COLUMN erp.doc_audit.doc_status IS
    'O''zgarish paytidagi hujjat holati: "issued dan keyin tegilganmi?" '
    'degan savolga javob shu ustundan chiqadi.';

CREATE INDEX IF NOT EXISTS doc_audit_doc_idx
    ON erp.doc_audit (doc_type, doc_id, created_at DESC);
CREATE INDEX IF NOT EXISTS doc_audit_time_idx
    ON erp.doc_audit (created_at DESC);
-- "ERP dan tashqarida o'zgartirilganlar" — eng ko'p so'raladigan kesim.
CREATE INDEX IF NOT EXISTS doc_audit_outside_idx
    ON erp.doc_audit (created_at DESC) WHERE actor IS NULL;

-- --------------------------------------------------------------------------
-- Jurnal O'ZGARMAYDI
-- --------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION erp.doc_audit_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'erp.doc_audit yozuvini o''zgartirib bo''lmaydi (audit jurnali)';
    END IF;
    -- DELETE: faqat ataylab yoqilgan bayroq bilan.
    IF coalesce(current_setting('erp.audit_purge', true), 'off') <> 'on' THEN
        RAISE EXCEPTION
            'erp.doc_audit yozuvini o''chirish uchun erp.audit_purge = on '
            'bo''lishi kerak (saqlash muddati tozalash uchun)';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS doc_audit_guard_trg ON erp.doc_audit;
CREATE TRIGGER doc_audit_guard_trg
    BEFORE UPDATE OR DELETE ON erp.doc_audit
    FOR EACH ROW EXECUTE FUNCTION erp.doc_audit_guard();

-- --------------------------------------------------------------------------
-- Yozuvchi trigger
-- --------------------------------------------------------------------------
-- E'TIBORSIZ ustunlar: ular ma'lumot emas, shovqin.
--   `updated_at` — har o'zgarishda o'zi yangilanadi;
--   `id`         — o'zgarmaydi.
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
    -- Qaysi hujjatga tegishli ekanini jadval nomidan aniqlaymiz.
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
    ELSE
        RETURN coalesce(NEW, OLD);
    END IF;

    -- Hujjatning O'ZGARISHDAN OLDINGI holati.
    --
    -- HUJJATNING O'ZI o'zgarganda ESKI holat olinadi. Aks holda
    -- "qoralamadan chiqarildi" degan o'tishning O'ZI "chiqarilgandan
    -- keyin o'zgardi" bo'lib ko'rinardi — ya'ni har faktura shubhali
    -- deb belgilanardi va ro'yxat ma'nosini yo'qotardi.
    --
    -- Qator va to'lov uchun esa hujjatning JORIY holati olinadi: ular
    -- hujjat holatini o'zgartirmaydi, ya'ni joriysi = o'shandagisi.
    IF v_entity IN ('invoice', 'act') THEN
        IF TG_OP = 'INSERT' THEN
            v_status := to_jsonb(NEW) ->> 'status';
        ELSE
            v_status := to_jsonb(OLD) ->> 'status';
        END IF;
    ELSIF v_doc_type = 'invoice' THEN
        SELECT status INTO v_status FROM erp.invoice WHERE id = v_doc_id;
    ELSE
        SELECT status INTO v_status FROM erp.act WHERE id = v_doc_id;
    END IF;

    IF TG_OP = 'INSERT' THEN
        INSERT INTO erp.doc_audit (doc_type, doc_id, entity, entity_id,
                                   action, new_value, doc_status, actor)
        VALUES (v_doc_type, v_doc_id, v_entity, NEW.id, 'create',
                (to_jsonb(NEW) - 'id')::text, v_status, v_actor);
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        INSERT INTO erp.doc_audit (doc_type, doc_id, entity, entity_id,
                                   action, old_value, doc_status, actor)
        VALUES (v_doc_type, v_doc_id, v_entity, OLD.id, 'delete',
                (to_jsonb(OLD) - 'id')::text, v_status, v_actor);
        RETURN OLD;
    END IF;

    -- UPDATE: HAR O'ZGARGAN USTUN uchun alohida qator.
    -- Sabab — "kim narxni o'zgartirdi?" degan savolga javob bitta
    -- SELECT bo'lishi kerak, JSON ichini titkilash emas.
    v_old := to_jsonb(OLD) - 'updated_at';
    v_new := to_jsonb(NEW) - 'updated_at';
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

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['invoice', 'invoice_line', 'invoice_payment',
                             'act', 'act_line'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS doc_audit_trg ON erp.%I', t);
        EXECUTE format(
            'CREATE TRIGGER doc_audit_trg AFTER INSERT OR UPDATE OR DELETE '
            'ON erp.%I FOR EACH ROW EXECUTE FUNCTION erp.doc_audit_write()', t);
    END LOOP;
END $$;
