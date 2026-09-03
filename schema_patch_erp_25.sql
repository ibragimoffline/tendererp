-- =============================================================================
-- ERP 25-patch — ICHKI CHAT (hodimlar muloqoti)
-- =============================================================================
--
-- Manba: `docs/erp_chat.md`. Fayl nomi u yerda `schema_patch_erp_chat.sql`
-- deb yozilgan; bu yerda RAQAMLI tartib saqlandi, chunki `check_setup.py`
-- patchlarni ketma-ket ro'yxatlaydi va nomsiz patch o'sha ro'yxatdan
-- tushib qolardi.
--
-- MUAMMO: ERP da hodimlar bir-biriga yozadigan joy yo'q edi. Karta
-- bo'yicha savol og'zaki yoki Telegram'da so'ralardi va javob KARTADA
-- qolmasdi — ya'ni "nega bunday qaror qilindi" degan savolga bir yildan
-- keyin javob topib bo'lmasdi.
--
-- BU TENDER-AI DAGI `ChatPanel` EMAS. U yerdagi chat — AI bilan suhbat
-- (RAG). Bu — odam bilan odam. Nomlash ham farqlanadi: ERP da "Muloqot",
-- Tender-AI da "AI chat". Chegara o'zgarmaydi: chat `public.*` ga
-- tegmaydi va `tai_app` ga BERILMAYDI.
--
-- IKKI TUR, IKKI XIL A'ZOLIK:
--   `umumiy`      — butun kompaniya. A'zolik VIRTUAL: barcha faol
--                   hodimlar ko'radi, a'zo yozuvlari yuritilmaydi.
--                   Chiqib ham, qo'shib ham bo'lmaydi.
--   `opportunity` — bitta karta atrofida. Ro'yxatli a'zolik.
--
-- Idempotent: qayta yurgizish xavfsiz.
-- =============================================================================

-- --------------------------------------------------------------------------
-- 1. Chat
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.chat (
    id             SERIAL PRIMARY KEY,
    turi           TEXT NOT NULL CHECK (turi IN ('umumiy', 'opportunity')),
    --: Kartaga 1:1. `ON DELETE CASCADE` — kartasiz karta chati ma'nosiz.
    opportunity_id INT UNIQUE REFERENCES erp.opportunity(id) ON DELETE CASCADE,
    --: `umumiy`: "Umumiy". `opportunity`: karta nomi SNAPSHOT sifatida —
    --: karta nomi keyin o'zgarsa ham chat ro'yxatida bir xil qoladi.
    title          TEXT,
    created_by     INT REFERENCES erp.app_user(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    --: Karta yakuniy statusga o'tganda to'ladi -> chat FAQAT O'QISH.
    --: Yakuniydan qaytarilsa yana NULL bo'ladi.
    archived_at    TIMESTAMPTZ,
    --: Tur va bog'lanish MOS bo'lsin: `umumiy` da karta yo'q,
    --: `opportunity` da bor. Ikkalasi ham noto'g'ri bo'lsa jimgina
    --: "hech kimga tegishli bo'lmagan chat" paydo bo'lardi.
    CHECK ((turi = 'opportunity') = (opportunity_id IS NOT NULL))
);

-- Umumiy chat BITTA. Qisman indeks: `opportunity` chatlari cheklanmaydi.
CREATE UNIQUE INDEX IF NOT EXISTS chat_umumiy_bitta
    ON erp.chat (turi) WHERE turi = 'umumiy';

INSERT INTO erp.chat (turi, title)
SELECT 'umumiy', 'Umumiy'
WHERE NOT EXISTS (SELECT 1 FROM erp.chat WHERE turi = 'umumiy');

COMMENT ON TABLE erp.chat IS
    'ERP ichki muloqoti (hodim <-> hodim). Tender-AI dagi AI chat BILAN '
    'ALOQASI YO''Q. `public.*` ga tegmaydi, `tai_app` ko''rmaydi.';

-- --------------------------------------------------------------------------
-- 2. A'zolik — faqat `opportunity` chatlari uchun
-- --------------------------------------------------------------------------
-- `umumiy` chatga a'zo YOZILMAYDI. Sabab: yozilsa har yangi hodim uchun
-- qator qo'shish kerak bo'lardi va uni unutish "yangi hodim umumiy
-- chatni ko'rmaydi" degan jim nuqsonga aylanardi.
--
-- Chiqarish YUMSHOQ: qator o'chmaydi, `removed_at` to'ladi. Qayta
-- qo'shilsa o'sha qator tiklanadi (`PRIMARY KEY` shuni majburlaydi) va
-- "qachon qo'shilgan / qachon chiqarilgan" tarixi yo'qolmaydi.
CREATE TABLE IF NOT EXISTS erp.chat_member (
    chat_id     INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    app_user_id INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    added_by    INT REFERENCES erp.app_user(id),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_by  INT REFERENCES erp.app_user(id),
    --: NULL = FAOL a'zo.
    removed_at  TIMESTAMPTZ,
    PRIMARY KEY (chat_id, app_user_id)
);

CREATE INDEX IF NOT EXISTS chat_member_user_idx
    ON erp.chat_member (app_user_id) WHERE removed_at IS NULL;

-- --------------------------------------------------------------------------
-- 3. Xabarlar
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.chat_message (
    id          SERIAL PRIMARY KEY,
    chat_id     INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    --: NULL = TIZIM xabari (status o'zgardi, hodim almashdi...).
    --: Tizim xabari tahrirlanmaydi va o'chirilmaydi.
    author_id   INT REFERENCES erp.app_user(id) ON DELETE SET NULL,
    --: 4000 belgi — Telegram bilan bir xil tartib. Chegarasiz matn
    --: lentani ham, jurnalni ham cho'ktirardi.
    text        TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
    --: Javob. O'chirilgan xabarga ishora qilsa ham YO'QOLMAYDI —
    --: lentada "o'chirilgan xabarga javob" bo'lib turadi.
    reply_to_id INT REFERENCES erp.chat_message(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at   TIMESTAMPTZ,
    --: YUMSHOQ o'chirish: qator qoladi, matn oddiy foydalanuvchiga
    --: ko'rinmaydi. Jismoniy o'chirish YO'Q — hatto admin uchun ham.
    deleted_at  TIMESTAMPTZ,
    deleted_by  INT REFERENCES erp.app_user(id),
    --: Moderatsiyada (birovnikini o'chirishda) MAJBURIY — muallifga
    --: bildirishnoma shu izoh bilan ketadi.
    delete_note TEXT
);

-- Lenta har doim `chat_id` bo'yicha va `id` tartibida o'qiladi
-- (sahifalash ham `after_id` bilan) — indeks aynan shu shaklda.
CREATE INDEX IF NOT EXISTS chat_message_lenta
    ON erp.chat_message (chat_id, id);

-- --------------------------------------------------------------------------
-- 4. Tahrir/o'chirish tarixi — FAQAT QO'SHILADI
-- --------------------------------------------------------------------------
-- Tamoyil `erp.doc_audit` bilan bir xil: o'zgartirish MUMKIN, IZSIZ
-- o'zgartirish mumkin emas.
CREATE TABLE IF NOT EXISTS erp.chat_message_history (
    id         SERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES erp.chat_message(id) ON DELETE CASCADE,
    amal       TEXT NOT NULL CHECK (amal IN ('tahrir', 'ochirish')),
    old_text   TEXT NOT NULL,
    by_user    INT REFERENCES erp.app_user(id),
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_message_history_msg_idx
    ON erp.chat_message_history (message_id, at);

-- Jurnal O'ZGARMAYDI. `doc_audit_guard` bilan bir xil naqsh: DELETE
-- faqat ataylab yoqilgan bayroq bilan (saqlash muddati tozalash uchun).
CREATE OR REPLACE FUNCTION erp.chat_history_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'erp.chat_message_history yozuvini o''zgartirib bo''lmaydi '
            '(tahrir jurnali)';
    END IF;
    IF coalesce(current_setting('erp.audit_purge', true), 'off') <> 'on' THEN
        RAISE EXCEPTION
            'erp.chat_message_history yozuvini o''chirish uchun '
            'erp.audit_purge = on bo''lishi kerak';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chat_history_guard_trg ON erp.chat_message_history;
CREATE TRIGGER chat_history_guard_trg
    BEFORE UPDATE OR DELETE ON erp.chat_message_history
    FOR EACH ROW EXECUTE FUNCTION erp.chat_history_guard();

-- --------------------------------------------------------------------------
-- 5. O'qilganlik — o'qilmagan xabarlar hisoblagichi
-- --------------------------------------------------------------------------
-- Har xabar uchun "kim o'qidi" YOZILMAYDI (§7: "ko'k belgilar" yo'q).
-- Bitta `last_read_id` yetarli va u O(1): lenta `id` bo'yicha o'sadi.
CREATE TABLE IF NOT EXISTS erp.chat_read (
    chat_id      INT NOT NULL REFERENCES erp.chat(id) ON DELETE CASCADE,
    app_user_id  INT NOT NULL REFERENCES erp.app_user(id) ON DELETE CASCADE,
    last_read_id INT NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, app_user_id)
);

-- --------------------------------------------------------------------------
-- 6. MAVJUD kartalar uchun chat — bir martalik va IDEMPOTENT
-- --------------------------------------------------------------------------
-- Patch qo'llangunga qadar ochilgan kartalarda chat bo'lmasdi va ular
-- interfeysda "chatsiz karta" bo'lib qolardi. Yaratamiz; a'zo sifatida
-- kartaning MAS'ULI qo'shiladi (hisobi bo'lsa).
INSERT INTO erp.chat (turi, opportunity_id, title, created_at)
SELECT 'opportunity', o.id, left(coalesce(o.title, '#' || o.id), 200),
       o.created_at
FROM erp.opportunity o
WHERE NOT EXISTS (SELECT 1 FROM erp.chat c WHERE c.opportunity_id = o.id);

INSERT INTO erp.chat_member (chat_id, app_user_id, added_at)
SELECT c.id, u.id, c.created_at
FROM erp.chat c
JOIN erp.opportunity o ON o.id = c.opportunity_id
JOIN erp.app_user u    ON u.broker_id = o.broker_id AND u.active
WHERE c.turi = 'opportunity'
ON CONFLICT (chat_id, app_user_id) DO NOTHING;

-- Yopilgan kartalarning chati darhol ARXIV: ko'chirishdan keyin
-- yakunlangan kartada yozish ochiq qolib ketmasin.
UPDATE erp.chat c SET archived_at = now()
FROM erp.opportunity o
WHERE o.id = c.opportunity_id
  AND c.archived_at IS NULL
  AND o.status IN ('won', 'lost', 'rejected', 'ulgurmadik');

-- --------------------------------------------------------------------------
-- 7. Huquq (18-patchdagi `erp` roli uchun)
-- --------------------------------------------------------------------------
-- Rol bo'lmasa jim o'tamiz: huquq chegarasi hali yoqilmagan o'rnatmada
-- patch YIQILMASLIGI kerak.
--
-- `chat_message_history` ga faqat `INSERT` va `SELECT`: `UPDATE`/`DELETE`
-- ni yuqoridagi trigger ham to'sadi, lekin grant bermaslik — birinchi
-- to'siq va u xato xabarigacha yetmaydi.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON erp.chat, erp.chat_member,
              erp.chat_message, erp.chat_read TO erp;
        GRANT SELECT, INSERT ON erp.chat_message_history TO erp;
        GRANT USAGE, SELECT ON SEQUENCE
              erp.chat_id_seq, erp.chat_message_id_seq,
              erp.chat_message_history_id_seq TO erp;
    END IF;
END $$;
