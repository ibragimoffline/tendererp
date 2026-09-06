-- =============================================================================
-- ERP 28-patch — UMUMIY VAZIFALAR va KARTA JAMOASI
-- Ishga tushirish (idempotent, bir necha marta ishlatsa ham xavfsiz):
--   psql "dbname=xtxarid user=postgres host=localhost" -f schema_patch_erp_28.sql
-- Talab: _1 (kartalar), _3 (vazifalar), _6 (hisoblar), _16 (jurnal), _25 (chat).
--
-- IKKI MUAMMO, IKKI QISM.
--
-- 1. VAZIFA FAQAT KARTAGA BOG'LANARDI. `opportunity_id NOT NULL` edi,
--    ya'ni "sertifikatni yangilash" yoki "hisobot tayyorlash" degan
--    oddiy ish ERP da UMUMAN yozilmasdi. Natijada hodimning ishi ikki
--    joyda yashardi: tenderga tegishlisi ERP da, qolgani daftarda yoki
--    Telegram'da — va menejer "bu odam nima bilan band?" degan savolga
--    javob ololmasdi.
--
-- 2. KARTADA BITTA MAS'UL. `opportunity.broker_id` yakka ustun.
--    Amalda esa bitta tenderda uch odam ishlaydi: narxni biri
--    hisoblaydi, hujjatni ikkinchisi yig'adi, texnik qismni uchinchisi
--    yozadi. Ular kartani KO'RA OLMASDI ham (egalik zanjiri
--    `broker_id` ga tayanadi), ya'ni ish qilish uchun mas'ulning
--    hisobidan kirish kerak bo'lardi — bu esa auditning oxiri.
--
-- ASOSIY MAS'UL QAYERDA QOLADI
-- ════════════════════════════
-- `erp.opportunity.broker_id` da, O'ZGARISHSIZ. Yangi jadvalga
-- ko'chirilmadi va bu ONGLI qaror:
--
--   * BITTA USTUN = "ko'pi bilan bitta asosiy mas'ul" invarianti
--     tuzilma darajasida ta'minlanadi. Jadvalga `asosiy BOOLEAN`
--     qo'yilsa, uni qisman noyob indeks bilan qo'riqlash kerak
--     bo'lardi va ikkita haqiqat manbai paydo bo'lardi.
--   * Yigirmaga yaqin joy shu ustunga tayanadi (`egalik.py` zanjiri,
--     ro'yxat filtri, analitika, eslatma, faktura egaligi). Ularni
--     ko'chirish katta va foydasiz xavf edi.
--
-- Ya'ni: `broker_id` — ASOSIY, `opportunity_assignee` — QOLGAN jamoa.
-- Ikkalasi BOSHQA-BOSHQA faktni saqlaydi, takrorlanmaydi.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. VAZIFA: kartasiz ham bo'ladi
-- --------------------------------------------------------------------------
-- Jadval nomi `opportunity_task` bo'lib QOLADI. Uni qayta nomlash
-- (yoki `erp.task` degan ikkinchi jadval ochish) — kod bo'ylab yuzta
-- joyni tegish yoki ikkita vazifa tizimini yonma-yon saqlash demakdir.
-- Nom endi tarixiy: izoh shuni ochiq aytadi.
COMMENT ON TABLE erp.opportunity_task IS
    'Hodim vazifasi. `opportunity_id` NULL bo''lsa - UMUMIY vazifa '
    '(tenderga bog''liq emas). Jadval nomi TARIXIY: 3-patchda u faqat '
    'karta vazifasi edi (schema_patch_erp_28.sql).';

ALTER TABLE erp.opportunity_task ALTER COLUMN opportunity_id DROP NOT NULL;

ALTER TABLE erp.opportunity_task
    --: HOLAT. `done` ni almashtiradi (pastga qarang): "bekor qilindi"
    --: bilan "bajarildi" ni ajratib bo'lmasdi va ikkalasi ham
    --: `done = TRUE` edi — ya'ni bajarilmagan ish bajarilgan bo'lib
    --: hisobotga tushardi.
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'yangi',
    --: USTUVORLIK — kartadagi bilan BIR XIL ro'yxat
    --: (`opportunity.priority`: low/medium/high). Ikkinchi shkala
    --: kiritilsa, ekranda "O'rta" va "Normal" yonma-yon turardi.
    ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium',
    --: Tavsif. `note` allaqachon bor va AYNAN shu ma'noda ishlatiladi
    --: (`TaskList.tsx` uni "izoh" deb ko'rsatadi) - ikkinchi matn
    --: maydoni qo'shilmadi.
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
    --: Bekor qilingan payt. `done_at` "bajarildi" uchun va u
    --: bekor qilishda TO'LDIRILMAYDI: aks holda "qachon bajarildi"
    --: degan savol yolg'on javob olardi.
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
    --: KIM biriktirdi (hisob). `created_by` ISM va u tarixga yoziladi;
    --: hisob id si esa bildirishnomada "o'z amali" ni ajratish uchun
    --: kerak (`api/erp/hodisa.py`).
    ADD COLUMN IF NOT EXISTS created_by_user_id INT
        REFERENCES erp.app_user(id);

-- Mavjud qatorlarni MOSLASH — cheklovdan OLDIN (§34: avval ma'lumot,
-- keyin cheklov).
UPDATE erp.opportunity_task
   SET status = CASE WHEN done THEN 'bajarildi' ELSE 'yangi' END
 WHERE status IS NULL OR status NOT IN ('yangi', 'bajarilmoqda',
                                        'bajarildi', 'bekor');
UPDATE erp.opportunity_task SET priority = 'medium'
 WHERE priority NOT IN ('low', 'medium', 'high');

DO $$
BEGIN
    ALTER TABLE erp.opportunity_task
        ADD CONSTRAINT opp_task_status_chk
        CHECK (status IN ('yangi', 'bajarilmoqda', 'bajarildi', 'bekor'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE erp.opportunity_task
        ADD CONSTRAINT opp_task_priority_chk
        CHECK (priority IN ('low', 'medium', 'high'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON COLUMN erp.opportunity_task.status IS
    'yangi | bajarilmoqda | bajarildi | bekor. KECHIKKAN holat YO''Q - '
    'u `due_at` va statusdan HISOBLANADI (ikkinchi haqiqat manbai '
    'bo''lmasin).';

-- `done` — ENDI KO'ZGU, haqiqat manbai emas.
--
-- O'CHIRILMAYDI: unga o'nga yaqin so'rov va indeks tayanadi
-- (`my_tasks`, eslatma tanlovi, qisman indekslar), va uni bir zarbada
-- ko'chirish katta xavf edi. Trigger uni `status` dan yuritadi, ya'ni
-- ikkita qiymat HECH QACHON ajralib ketmaydi - hatto `psql` dan
-- qo'lda yozilgan `UPDATE` da ham.
--
-- "Bekor" ham `done = TRUE` beradi: eski so'rovlar uchun u "ochiq
-- emas" degani va aynan shu to'g'ri. "Bajarildi" degan MA'NO endi
-- `status` da.
CREATE OR REPLACE FUNCTION erp.task_done_mirror() RETURNS trigger AS $$
BEGIN
    NEW.done := NEW.status IN ('bajarildi', 'bekor');
    IF NEW.status = 'bajarildi' THEN
        NEW.done_at := coalesce(NEW.done_at, now());
        NEW.cancelled_at := NULL;
    ELSIF NEW.status = 'bekor' THEN
        NEW.cancelled_at := coalesce(NEW.cancelled_at, now());
        NEW.done_at := NULL;
    ELSE
        NEW.done_at := NULL;
        NEW.cancelled_at := NULL;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        NEW.updated_at := now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS task_done_mirror_trg ON erp.opportunity_task;
CREATE TRIGGER task_done_mirror_trg
    BEFORE INSERT OR UPDATE ON erp.opportunity_task
    FOR EACH ROW EXECUTE FUNCTION erp.task_done_mirror();

-- Ko'zgu mavjud qatorlarda ham to'g'ri bo'lsin.
UPDATE erp.opportunity_task SET status = status;

-- UMUMIY vazifalar ro'yxati ("mening ishlarim" da kartasizlar).
CREATE INDEX IF NOT EXISTS opp_task_umumiy_idx
    ON erp.opportunity_task (assignee_broker_id, due_at)
    WHERE opportunity_id IS NULL AND status IN ('yangi', 'bajarilmoqda');

-- "Kimda nechta ochiq ish" — yuklama ko'rinishi.
CREATE INDEX IF NOT EXISTS opp_task_yuklama_idx
    ON erp.opportunity_task (assignee_broker_id, status);

-- --------------------------------------------------------------------------
-- 2. KARTA JAMOASI
-- --------------------------------------------------------------------------
-- QOLGAN a'zolar (asosiy mas'ul `opportunity.broker_id` da - yuqoridagi
-- izohga qarang).
CREATE TABLE IF NOT EXISTS erp.opportunity_assignee (
    id             SERIAL PRIMARY KEY,
    opportunity_id INT NOT NULL
        REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    --: HODIM, hisob emas: kartada ishlaydigan odam hisobsiz bo'lishi
    --: mumkin (omborchi, hujjatchi) va u baribir jamoada turadi.
    --: Bildirishnoma esa hisob topilganda ketadi (`hodisa.py`).
    broker_id      INT NOT NULL REFERENCES erp.broker(id),
    --: Mas'uliyat: narx, hujjat, texnik, yuridik, kuzatuvchi.
    --: Ro'yxat KODDA (`api/erp/jamoa.py` -> ROLLAR): u ekranda
    --: yorliq bilan ko'rsatiladi va bazadagi CHECK bilan ikkinchi
    --: nusxaga aylanmasligi kerak. Noto'g'ri qiymat modulda rad
    --: etiladi.
    rol            TEXT NOT NULL DEFAULT 'kuzatuvchi',
    izoh           TEXT,
    added_by       INT REFERENCES erp.app_user(id),
    added_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: YUMSHOQ chiqarish (§26): qator qoladi, tarix yo'qolmaydi.
    removed_at     TIMESTAMPTZ,
    removed_by     INT REFERENCES erp.app_user(id)
);

-- BIR KARTADA BIR ODAM BIR MARTA (faol a'zolik bo'yicha). Qisman
-- indeks: chiqarilgan a'zoni QAYTA qo'shish mumkin bo'lishi kerak va
-- eski qator tarix sifatida qoladi.
CREATE UNIQUE INDEX IF NOT EXISTS opp_assignee_faol_uk
    ON erp.opportunity_assignee (opportunity_id, broker_id)
    WHERE removed_at IS NULL;

CREATE INDEX IF NOT EXISTS opp_assignee_broker_idx
    ON erp.opportunity_assignee (broker_id) WHERE removed_at IS NULL;

COMMENT ON TABLE erp.opportunity_assignee IS
    'Karta JAMOASI. Asosiy mas''ul bu yerda EMAS - u '
    'erp.opportunity.broker_id da (schema_patch_erp_28.sql sarlavhasi).';
COMMENT ON COLUMN erp.opportunity_assignee.removed_at IS
    'Yumshoq chiqarish. Qator o''chirilmaydi: "kim qachon jamoada '
    'edi" degan savol javobsiz qolmasin.';

-- --------------------------------------------------------------------------
-- 3. TARIX — MAVJUD JURNALGA ulanadi
-- --------------------------------------------------------------------------
-- Yangi "task_history" jadvali OCHILMADI: `erp.doc_audit` (16-patch)
-- aynan shu savolga javob beradi va u TRIGGER bilan yoziladi, ya'ni
-- uni chetlab o'tib bo'lmaydi. Ikkinchi jurnal ikkita haqiqat manbai
-- bo'lardi va "kim o'zgartirdi" ikki joydan qidirilardi
-- (`api/erp/audit.py` sarlavhasidagi qoida).
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
    -- 28-patch: VAZIFA. `doc_id` - vazifaning O'ZI, kartasi emas:
    -- umumiy vazifada karta YO'Q va `doc_id NOT NULL`. Shu bilan
    -- "shu vazifa tarixi" bitta so'rovga aylanadi.
    ELSIF TG_TABLE_NAME = 'opportunity_task' THEN
        v_doc_type := 'vazifa'; v_entity := 'vazifa';
        v_doc_id := coalesce(NEW.id, OLD.id);
    -- 28-patch: JAMOA. Bu KARTAGA tegishli o'zgarish, shuning uchun
    -- `doc_id` - karta: "shu kartada kim qachon jamoada edi" degan
    -- savol karta jurnalidan chiqadi.
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
        -- Vazifaning O'ZGARISHDAN OLDINGI holati: "bajarilgan
        -- vazifaga tegilganmi?" degan savolga javob beradi.
        IF TG_OP = 'INSERT' THEN
            v_status := NEW.status;
        ELSE
            v_status := OLD.status;
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

    -- UPDATE: HAR O'ZGARGAN USTUN uchun alohida qator.
    --
    -- `done` CHIQARIB TASHLANADI: u `status` ning ko'zgusi (yuqoridagi
    -- trigger) va jurnalda har status o'zgarishida IKKI qator
    -- ko'rinardi - bir xil faktni ikki marta.
    v_old := to_jsonb(OLD) - 'updated_at' - 'baytlar' - 'done';
    v_new := to_jsonb(NEW) - 'updated_at' - 'baytlar' - 'done';
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

DROP TRIGGER IF EXISTS doc_audit_trg ON erp.opportunity_task;
CREATE TRIGGER doc_audit_trg
    AFTER INSERT OR UPDATE OR DELETE ON erp.opportunity_task
    FOR EACH ROW EXECUTE FUNCTION erp.doc_audit_write();

DROP TRIGGER IF EXISTS doc_audit_trg ON erp.opportunity_assignee;
CREATE TRIGGER doc_audit_trg
    AFTER INSERT OR UPDATE OR DELETE ON erp.opportunity_assignee
    FOR EACH ROW EXECUTE FUNCTION erp.doc_audit_write();

-- --------------------------------------------------------------------------
-- 4. YUKLAMA — view, jadval emas
-- --------------------------------------------------------------------------
-- "Kimga ish berish mumkin" degan savolga javob. HISOBLANADI: saqlangan
-- ko'rsatkich haqiqatdan ajralib ketardi va aynan qaror qabul
-- qilinayotgan paytda yolg'on gapirardi.
--
-- KECHIKKAN SHU YERDA ham hisoblanadi (saqlanmaydi): `due_at` o'tgan
-- va status hali ochiq.
CREATE OR REPLACE VIEW erp.v_hodim_yuklama AS
SELECT b.id AS broker_id, b.full_name, b.active,
       (SELECT count(*) FROM erp.opportunity_task t
         WHERE t.assignee_broker_id = b.id
           AND t.status IN ('yangi', 'bajarilmoqda'))          AS ochiq_vazifa,
       (SELECT count(*) FROM erp.opportunity_task t
         WHERE t.assignee_broker_id = b.id
           AND t.status IN ('yangi', 'bajarilmoqda')
           AND t.due_at IS NOT NULL AND t.due_at < current_date) AS kechikkan,
       (SELECT count(*) FROM erp.opportunity_task t
         WHERE t.assignee_broker_id = b.id
           AND t.status = 'bajarildi')                         AS bajarilgan,
       --: OCHIQ kartalar: asosiy mas'ul BO'LGANLARI + jamoada
       --: turganlari. Ikkalasi ham "shu odam bu tenderda ishlayapti"
       --: degani.
       (SELECT count(*) FROM erp.opportunity o
         WHERE o.status NOT IN ('won', 'lost', 'rejected', 'ulgurmadik')
           AND (o.broker_id = b.id
                OR EXISTS (SELECT 1 FROM erp.opportunity_assignee a
                            WHERE a.opportunity_id = o.id
                              AND a.broker_id = b.id
                              AND a.removed_at IS NULL)))      AS ochiq_karta
FROM erp.broker b;

COMMENT ON VIEW erp.v_hodim_yuklama IS
    'Hodim yuklamasi: ochiq vazifa, kechikkan, ochiq karta. '
    'HISOBLANADI - saqlangan ko''rsatkich haqiqatdan ajralib ketardi.';
