-- =============================================================================
-- ERP 24-patch — "ULGURMADIK" holati va KARTAGA FAYL BIRIKTIRISH
-- =============================================================================
--
-- MUAMMO 1 — yakunlanmagan kartaning holati yo'q.
--   Muddat o'tib ketsa karta `preparing` da ABADIY qolardi. `analytics.py`
--   uni "hozir shu bosqichda ishlanmoqda" deb sanardi, ya'ni voronka va
--   bosqich vaqti YOLG'ON raqam berardi. `rejected` ("rad etildi") esa
--   boshqa ma'no: u "biz voz kechdik", "ulgurmadik" emas.
--
-- MUAMMO 2 — nega yutqazdik degan savolga TAFSILOT yozib bo'lmasdi.
--   `lost_reason` — ro'yxatdan bitta kod (narx, muddat, hujjat...).
--   Bu tasniflash uchun yetarli, lekin "aynan nima bo'ldi" degan
--   savolga javob bermaydi. Broker uni og'zaki aytadi va iz qolmaydi.
--
-- QAROR (grill sessiyasi, 2026-09-04):
--   1. Yangi status `ulgurmadik` — YAKUNIY va uni FAQAT ODAM qo'yadi.
--      Tizim hech qanday status qo'ymaydi (1-patchdan beri amal qilgan
--      tamoyil buzilmaydi). Muddati o'tgan ochiq kartani `remind.py`
--      eslatadi, yopishni odam hal qiladi.
--   2. Fayl BAZADA (`bytea`), diskda emas. Sabab: `backup_erp.ps1`
--      faqat `pg_dump` qiladi va diskdagi papkani ZAXIRALAMAYDI —
--      "nega yutqazdik" hujjati zaxirada jimgina yo'q bo'lardi.
--   3. Fayl IXTIYORIY. Majburiy qilinsa broker bo'sh fayl yuklab
--      o'tib ketadi va bizda "hujjat bor" degan YOLG'ON ko'rsatkich
--      paydo bo'ladi — bu hujjat umuman bo'lmaganidan yomonroq.
--      Yo'qligi ekranda ochiq yoziladi, qamrovi esa sanaladi.
--   4. Fayl O'CHIRILISHI mumkin (xato yuklash tuzatilishi kerak),
--      lekin IZ o'chmaydi: mavjud `doc_audit` triggeri ulanadi.
--
-- Idempotent: qayta yurgizish xavfsiz.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. Yangi status
-- --------------------------------------------------------------------------
-- Ro'yxat IKKI joyda: shu CHECK va `api/erp/opportunity.py` dagi STATUSES.
-- Sinov ikkalasini solishtiradi (`erp_test.py`), shuning uchun bittasini
-- o'zgartirib ikkinchisini unutish JIMGINA o'tmaydi.
ALTER TABLE erp.opportunity DROP CONSTRAINT IF EXISTS opportunity_status_check;
ALTER TABLE erp.opportunity ADD CONSTRAINT opportunity_status_check
    CHECK (status IN ('new', 'reviewing', 'sent_to_client', 'confirmed',
                      'preparing', 'submitted', 'won', 'lost', 'rejected',
                      'ulgurmadik'));

COMMENT ON COLUMN erp.opportunity.status IS
    'Karta holati. `ulgurmadik` = muddat o''tdi, topshirmadik. `rejected` '
    'dan farqi: rad etish — BIZNING qaror, ulgurmaslik — natija. Ikkalasini '
    'ham FAQAT ODAM qo''yadi: tizim status o''zgartirmaydi.';

-- `lost_reason` ro'yxatiga tegilmaydi: undagi `deadline` ("Muddatga
-- ulgurmadik") aynan shu holat uchun mos va yangi kod kerak emas.
-- Sabab endi `ulgurmadik` va `rejected` da HAM so'raladi (ilova kodida) —
-- ilgari faqat `lost` da so'ralardi va "to'xtatildi, nega — noma'lum"
-- degan ko'r nuqta qolardi.

-- --------------------------------------------------------------------------
-- 2. Kartaga biriktirilgan fayl
-- --------------------------------------------------------------------------
-- NEGA `bytea`, diskda papka emas — yuqoridagi 2-qarorga qarang.
--
-- HAJM CHEGARASI bazada, ilovada emas: ilova chetlab o'tilsa (qo'lda SQL,
-- kelajakdagi ikkinchi mijoz) chegara baribir ishlaydi. 10 MB — sabab
-- hujjati uchun ortig'i bilan yetadi va `pg_dump` ni ham o'ldirmaydi.
CREATE TABLE IF NOT EXISTS erp.opportunity_file (
    id              BIGSERIAL PRIMARY KEY,
    opportunity_id  INT NOT NULL
                    REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    --: Foydalanuvchi ko'radigan nom (yuklangandagi asl nomi).
    fayl_nom        TEXT NOT NULL CHECK (length(btrim(fayl_nom)) > 0),
    --: Oq ro'yxat ILOVADA (`api/erp/fayl.py` -> TURLAR): u yerda kengaytma
    --: va mime birga tekshiriladi. Bazada faqat bo'sh emasligi.
    mime            TEXT NOT NULL,
    hajm            INT  NOT NULL CHECK (hajm > 0 AND hajm <= 10485760),
    --: Takror yuklashni to'sadi (pastdagi UNIQUE) va o'chirilgan faylni
    --: jurnalda TANIB olish imkonini beradi — baytlar yo'q, hash bor.
    sha256          TEXT NOT NULL CHECK (length(sha256) = 64),
    --: Ixtiyoriy: "bu qaysi fayl" degan bir qatorlik izoh.
    izoh            TEXT,
    --: FAYLNING O'ZI. TOAST uni avtomatik siqadi va tashqariga chiqaradi.
    baytlar         BYTEA NOT NULL,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: Bir xil faylni ikki marta biriktirish — har doim xato (ikki marta
    --: bosilgan tugma). Turli fayl, hatto bir xil nomli — mumkin.
    UNIQUE (opportunity_id, sha256)
);

CREATE INDEX IF NOT EXISTS opportunity_file_opp_idx
    ON erp.opportunity_file (opportunity_id, created_at DESC);

COMMENT ON TABLE erp.opportunity_file IS
    'Kartaga biriktirilgan fayl — asosan "nega yutqazdik/to''xtatdik" '
    'tafsiloti. IXTIYORIY: yo''qligi ekranda ochiq yoziladi. `lost_reason` '
    'ning O''RNINI BOSMAYDI — kod tasniflash uchun, fayl tafsilot uchun '
    '(faylni GROUP BY qilib bo''lmaydi).';
COMMENT ON COLUMN erp.opportunity_file.baytlar IS
    'Faylning o''zi. `doc_audit` ga HECH QACHON tushmaydi (pastdagi '
    'trigger uni jsonb dan chiqarib tashlaydi) — 10 MB lik hex satr '
    'jurnalni o''ldirardi.';

-- --------------------------------------------------------------------------
-- 3. Jurnal — mavjud trigger ULANADI, yangi kod yozilmaydi
-- --------------------------------------------------------------------------
-- `erp.doc_audit_write()` (16-patch) beshta pul jadvalida ishlaydi. Unga
-- oltinchi tarmoq qo'shiladi. Yangi jurnal jadvali YARATILMAYDI: ikkita
-- jurnal ikkita haqiqat manbai bo'lardi va "kim o'chirdi" degan savol
-- ikki joydan qidirilardi.
--
-- IKKI O'ZGARISH, ikkalasi ham eski tarmoqlarga TEGMAYDI:
--   a) `opportunity_file` tarmog'i — hujjat = KARTA, yozuv turi = fayl;
--   b) `- 'baytlar'` — jsonb dan fayl baytlari chiqarib tashlanadi.
--      Boshqa jadvallarda bunday kalit yo'q, `-` operatori esa yo'q
--      kalitda hech narsa qilmaydi, ya'ni ular uchun o'zgarish yo'q.
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
    ELSIF TG_TABLE_NAME = 'opportunity_file' THEN
        v_doc_type := 'karta'; v_entity := 'fayl';
        v_doc_id := coalesce(NEW.opportunity_id, OLD.opportunity_id);
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
    --
    -- Fayl uchun — KARTANING joriy statusi. Aynan shu savolga javob
    -- beradi: "fayl qaysi holatdagi kartadan o'chirildi?"
    IF v_entity IN ('invoice', 'act') THEN
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

    -- UPDATE: HAR O'ZGARGAN USTUN uchun alohida qator.
    -- Sabab — "kim narxni o'zgartirdi?" degan savolga javob bitta
    -- SELECT bo'lishi kerak, JSON ichini titkilash emas.
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

DROP TRIGGER IF EXISTS doc_audit_trg ON erp.opportunity_file;
CREATE TRIGGER doc_audit_trg
    AFTER INSERT OR UPDATE OR DELETE ON erp.opportunity_file
    FOR EACH ROW EXECUTE FUNCTION erp.doc_audit_write();

-- Jadval izohi endi to'g'ri emas edi: jurnalda pul hujjatlaridan tashqari
-- karta fayllari ham bor. Izoh KODNING O'ZI kabi eskiradi — yangilanadi.
COMMENT ON TABLE erp.doc_audit IS
    'Hujjat o''zgarishlari jurnali: pul hujjatlari (faktura, akt) va '
    'kartaga biriktirilgan fayllar. Triggerlar yozadi, ilova kodi emas — '
    'qo''lda yozilgan SQL ham ushlanadi. UPDATE taqiqlangan, DELETE faqat '
    'erp.audit_purge yoqilganda.';

-- --------------------------------------------------------------------------
-- 4. Huquq (patch 18 dagi `erp` roli uchun)
-- --------------------------------------------------------------------------
-- Rol mavjud bo'lmasa jim o'tamiz: huquq chegarasi hali yoqilmagan
-- o'rnatmada patch YIQILMASLIGI kerak (check_setup.py buni alohida
-- ogohlantirish sifatida ko'rsatadi).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp') THEN
        GRANT SELECT, INSERT, DELETE ON erp.opportunity_file TO erp;
        GRANT USAGE, SELECT ON SEQUENCE erp.opportunity_file_id_seq TO erp;
    END IF;
END $$;

-- --------------------------------------------------------------------------
-- 5. `v_tender_status` — YANGI STATUS SHU YERGA HAM
-- --------------------------------------------------------------------------
-- Bu view TENDER-AI o'qiydigan shartnoma (7-patch, 19-patchda
-- `assignee_full_name` bilan kengaytirilgan). Uning `CASE` i yangi
-- statusni qamramasa `status_label` NULL bo'lardi va tender-ai dagi
-- `ErpLink` da karta NOMSIZ ko'rinardi — jimgina, xatosiz.
--
-- Yorliq SHU YERDA hisoblangani uchun tender-ai tomonida KOD O'ZGARMAYDI:
-- u nomni tayyor holda oladi. `erp_test.py` CASE ni `STATUSES` bilan
-- solishtiradi va aynan shu unutishni ushlaydi (ushladi ham).
--
-- USTUNLAR VA TARTIB 19-patchdagidek QOLADI. `CREATE OR REPLACE VIEW`
-- ustun nomini ham, tartibini ham o'zgartirishga RUXSAT BERMAYDI —
-- `assignee_full_name` ni tushirib qoldirish patchni yiqitadi (birinchi
-- urinishda aynan shunday bo'ldi). Bu yaxshi: shartnoma tasodifan
-- buzilmaydi.
CREATE OR REPLACE VIEW erp.v_tender_status AS
SELECT o.id                AS opportunity_id,
       o.tender_id,
       o.status,
       CASE o.status
           WHEN 'new'            THEN 'Yangi'
           WHEN 'reviewing'      THEN 'Ko''rib chiqilmoqda'
           WHEN 'sent_to_client' THEN 'Mijozga yuborildi'
           WHEN 'confirmed'      THEN 'Qatnashish tasdiqlandi'
           WHEN 'preparing'      THEN 'Taklif tayyorlanmoqda'
           WHEN 'submitted'      THEN 'Topshirildi'
           WHEN 'won'            THEN 'Yutildi'
           WHEN 'lost'           THEN 'Yutqazildi'
           WHEN 'rejected'       THEN 'Rad etildi'
           WHEN 'ulgurmadik'     THEN 'Ulgurmadik (muddat o''tdi)'
       END                 AS status_label,
       o.priority,
       b.full_name         AS broker_name,
       c.name              AS client_name,
       o.created_at,
       o.updated_at,
       b.full_name         AS assignee_full_name
FROM erp.opportunity o
LEFT JOIN erp.broker b        ON b.id = o.broker_id
LEFT JOIN erp.client_company c ON c.id = o.client_id;
