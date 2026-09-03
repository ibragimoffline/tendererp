"""ERP ichki chati — hodim bilan hodim muloqoti (`docs/erp_chat.md`).

BU TENDER-AI DAGI CHAT EMAS. U yerdagi `ChatPanel` — AI bilan suhbat
(RAG). Bu — odamlar o'rtasidagi yozishma. Ekranda ham farqlanadi: ERP
da "Muloqot", Tender-AI da "AI chat".

IKKI TUR, IKKI XIL A'ZOLIK:

  `umumiy`      butun kompaniya. A'zolik VIRTUAL — barcha faol
                hodimlar ko'radi va a'zo qatorlari YURITILMAYDI.
                Yozilsa, har yangi hodim uchun qator qo'shish kerak
                bo'lardi va uni unutish "yangi hodim umumiy chatni
                ko'rmaydi" degan jim nuqsonga aylanardi.

  `opportunity` bitta karta atrofida, ro'yxatli a'zolik.

UCH QOIDA BUTUN MODUL BO'YLAB:

  1. YOZISH UCHUN A'ZOLIK SHART — rahbar uchun ham. U chatni a'zosiz
     KO'RADI, lekin yozish uchun avval o'zini qo'shadi va bu qo'shilish
     tizim xabari bo'lib lentada ko'rinadi. "Jimgina kuzatib turib
     yozish" bo'lmaydi.
  2. HECH NARSA JISMONAN O'CHMAYDI — xabar ham, a'zolik ham. O'chirish
     yumshoq, tahrir esa `chat_message_history` ga yoziladi. Tamoyil
     `erp.doc_audit` bilan bir xil: o'zgartirish mumkin, IZSIZ
     o'zgartirish mumkin emas.
  3. ADMIN YOZISHMADA QATNASHMAYDI — "biznes ma'lumotga ko'r" qoidasi
     (`erp_rollar.md`). Lekin tahrir/o'chirish jurnalini KO'RADI.

Chegara: `public.*` ga na yozadi, na o'qiydi. `tai_app` ga chat
obyektlari berilmaydi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api import db
from api.erp.opportunity import FINAL, ErpError, _iso, _need_schema

#: Bir xabarning eng katta uzunligi. Bazada ham CHECK bor.
MAX_MATN = 4000

#: Lentaning bir sahifasi.
LIMIT_DEFAULT = 50
LIMIT_MAX = 200

#: Karta chati ARXIV bo'ladigan statuslar — `FINAL` ning o'zi.
#: Alohida ro'yxat yozilmaydi: 24-patchda `ulgurmadik` qo'shilganda
#: qo'lda yozilgan har bir nusxa uni jimgina tashqarida qoldirgan edi.
ARXIV_HOLATLAR = FINAL


# ---------------------------------------------------------------------------
# Sxema tayyorligi (25-patch alohida qo'llanadi)
# ---------------------------------------------------------------------------
_SCHEMA25_READY = False

SCHEMA25_CHECK_SQL = """
SELECT 1 AS x FROM information_schema.tables
WHERE table_schema = 'erp' AND table_name = 'chat_message'
"""


def schema_ready() -> bool:
    global _SCHEMA25_READY
    if _SCHEMA25_READY:
        return True
    _SCHEMA25_READY = bool(db.query_one(SCHEMA25_CHECK_SQL))
    return _SCHEMA25_READY


def _need_schema25() -> None:
    _need_schema()
    if not schema_ready():
        raise ErpError("Chat jadvallari yo'q: schema_patch_erp_25.sql "
                       "bazaga qo'llanmagan.", 503)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
CHAT_GET_SQL = """
SELECT c.id, c.turi, c.opportunity_id, c.title, c.archived_at,
       o.status AS opp_status, o.broker_id AS opp_broker_id
FROM erp.chat c
LEFT JOIN erp.opportunity o ON o.id = c.opportunity_id
WHERE c.id = %(id)s
"""

CHAT_BY_OPP_SQL = ("SELECT id FROM erp.chat WHERE opportunity_id = %(opp)s")

# Mening chatlarim.
#
# `umumiy` SHARTSIZ chiqadi (a'zolik virtual). Karta chatlari esa
# a'zolik bo'yicha; rahbar/menejer uchun chaqiruvchi `hammasi=True`
# beradi va shart olib tashlanadi.
CHATLARIM_SQL = """
SELECT c.id, c.turi, c.opportunity_id, c.title, c.archived_at,
       o.status AS opp_status,
       (SELECT count(*) FROM erp.chat_message m
         WHERE m.chat_id = c.id
           AND m.id > coalesce(r.last_read_id, 0)
           AND m.deleted_at IS NULL
           AND (m.author_id IS NULL OR m.author_id <> %(uid)s)) AS oqilmagan,
       (SELECT max(m2.created_at) FROM erp.chat_message m2
         WHERE m2.chat_id = c.id)                               AS oxirgi_at,
       (a.app_user_id IS NOT NULL)                              AS azoman
FROM erp.chat c
LEFT JOIN erp.opportunity o ON o.id = c.opportunity_id
LEFT JOIN erp.chat_read r
       ON r.chat_id = c.id AND r.app_user_id = %(uid)s
LEFT JOIN erp.chat_member a
       ON a.chat_id = c.id AND a.app_user_id = %(uid)s AND a.removed_at IS NULL
WHERE c.turi = 'umumiy'
   OR %(hammasi)s::bool IS TRUE
   OR a.app_user_id IS NOT NULL
-- `umumiy` HAR DOIM birinchi, qolgani oxirgi xabar bo'yicha.
ORDER BY (c.turi = 'umumiy') DESC, oxirgi_at DESC NULLS LAST, c.id DESC
"""

AZO_SQL = """
SELECT m.app_user_id, u.full_name, u.username, u.role, u.active,
       m.added_at, m.added_by, ab.full_name AS added_by_name
FROM erp.chat_member m
JOIN erp.app_user u ON u.id = m.app_user_id
LEFT JOIN erp.app_user ab ON ab.id = m.added_by
WHERE m.chat_id = %(chat)s AND m.removed_at IS NULL
ORDER BY m.added_at, m.app_user_id
"""

# `umumiy` chatning a'zolari — BARCHA FAOL hisoblar. Jadval o'qilmaydi.
UMUMIY_AZO_SQL = """
SELECT u.id AS app_user_id, u.full_name, u.username, u.role, u.active,
       NULL::timestamptz AS added_at, NULL::int AS added_by,
       NULL::text AS added_by_name
FROM erp.app_user u WHERE u.active ORDER BY u.full_name, u.id
"""

AZOMI_SQL = """
SELECT 1 AS x FROM erp.chat_member
WHERE chat_id = %(chat)s AND app_user_id = %(uid)s AND removed_at IS NULL
"""

LENTA_SQL = """
SELECT m.id, m.chat_id, m.author_id, u.full_name AS author_name,
       u.role AS author_role,
       m.text, m.reply_to_id, m.created_at, m.edited_at,
       m.deleted_at, m.deleted_by, d.full_name AS deleted_by_name,
       m.delete_note,
       rm.author_id  AS reply_author_id,
       ru.full_name  AS reply_author_name,
       rm.text       AS reply_text,
       (rm.deleted_at IS NOT NULL) AS reply_deleted
FROM erp.chat_message m
LEFT JOIN erp.app_user u  ON u.id = m.author_id
LEFT JOIN erp.app_user d  ON d.id = m.deleted_by
LEFT JOIN erp.chat_message rm ON rm.id = m.reply_to_id
LEFT JOIN erp.app_user ru ON ru.id = rm.author_id
WHERE m.chat_id = %(chat)s
  AND (%(after_id)s::int IS NULL OR m.id > %(after_id)s)
  AND (%(q)s::text IS NULL OR (m.deleted_at IS NULL
                               AND m.text ILIKE '%%' || %(q)s || '%%'))
ORDER BY m.id
LIMIT %(limit)s
"""

# Bitta xabar — lenta bilan BIR XIL shaklda. Ilgari bu yerda `LENTA_SQL`
# ni satr almashtirish bilan qayta yasash bor edi: so'rov matni ozgina
# o'zgarsa u JIMGINA buzilardi va buni hech qanday sinov ushlamasdi.
BITTA_SQL = """
SELECT m.id, m.chat_id, m.author_id, u.full_name AS author_name,
       u.role AS author_role,
       m.text, m.reply_to_id, m.created_at, m.edited_at,
       m.deleted_at, m.deleted_by, d.full_name AS deleted_by_name,
       m.delete_note,
       rm.author_id  AS reply_author_id,
       ru.full_name  AS reply_author_name,
       rm.text       AS reply_text,
       (rm.deleted_at IS NOT NULL) AS reply_deleted
FROM erp.chat_message m
LEFT JOIN erp.app_user u  ON u.id = m.author_id
LEFT JOIN erp.app_user d  ON d.id = m.deleted_by
LEFT JOIN erp.chat_message rm ON rm.id = m.reply_to_id
LEFT JOIN erp.app_user ru ON ru.id = rm.author_id
WHERE m.id = %(id)s
"""

MSG_GET_SQL = """
SELECT m.id, m.chat_id, m.author_id, m.text, m.deleted_at, c.archived_at,
       c.turi, c.opportunity_id
FROM erp.chat_message m
JOIN erp.chat c ON c.id = m.chat_id
WHERE m.id = %(id)s
"""

MSG_INSERT_SQL = """
INSERT INTO erp.chat_message (chat_id, author_id, text, reply_to_id)
VALUES (%(chat)s, %(author)s, %(text)s, %(reply)s)
RETURNING id
"""

MSG_EDIT_SQL = """
UPDATE erp.chat_message SET text = %(text)s, edited_at = now()
WHERE id = %(id)s RETURNING id
"""

MSG_DELETE_SQL = """
UPDATE erp.chat_message
SET deleted_at = now(), deleted_by = %(by)s, delete_note = %(note)s
WHERE id = %(id)s RETURNING id
"""

HISTORY_INSERT_SQL = """
INSERT INTO erp.chat_message_history (message_id, amal, old_text, by_user)
VALUES (%(msg)s, %(amal)s, %(old)s, %(by)s) RETURNING id
"""

HISTORY_SQL = """
SELECT h.id, h.amal, h.old_text, h.by_user, u.full_name AS by_name, h.at
FROM erp.chat_message_history h
LEFT JOIN erp.app_user u ON u.id = h.by_user
WHERE h.message_id = %(msg)s ORDER BY h.at, h.id
"""

MEMBER_ADD_SQL = """
INSERT INTO erp.chat_member (chat_id, app_user_id, added_by)
VALUES (%(chat)s, %(uid)s, %(by)s)
ON CONFLICT (chat_id, app_user_id) DO UPDATE
    SET removed_at = NULL, removed_by = NULL,
        added_by = EXCLUDED.added_by, added_at = now()
RETURNING chat_id
"""

MEMBER_REMOVE_SQL = """
UPDATE erp.chat_member SET removed_at = now(), removed_by = %(by)s
WHERE chat_id = %(chat)s AND app_user_id = %(uid)s AND removed_at IS NULL
RETURNING chat_id
"""

READ_SQL = """
INSERT INTO erp.chat_read (chat_id, app_user_id, last_read_id)
VALUES (%(chat)s, %(uid)s, %(last)s)
ON CONFLICT (chat_id, app_user_id) DO UPDATE
    -- ORQAGA KETMAYDI: ikkita oyna ochiq bo'lsa, eskisi yangisining
    -- o'qilganini bekor qilib, hisoblagichni "tirilitib" yuborardi.
    SET last_read_id = greatest(erp.chat_read.last_read_id, EXCLUDED.last_read_id)
RETURNING last_read_id
"""

CHAT_CREATE_SQL = """
INSERT INTO erp.chat (turi, opportunity_id, title, created_by)
VALUES ('opportunity', %(opp)s, %(title)s, %(by)s)
ON CONFLICT (opportunity_id) DO NOTHING
RETURNING id
"""

# Arxivlash/ochish. Shart `<>` bilan: allaqachon kerakli holatda bo'lsa
# yozuv TEGILMAYDI va `archived_at` bejiz yangilanmaydi ("qachon
# arxivlandi" savoli javobsiz qolmasin).
ARXIV_SQL = """
UPDATE erp.chat
SET archived_at = CASE WHEN %(yopiq)s THEN now() ELSE NULL END
WHERE opportunity_id = %(opp)s
  AND (archived_at IS NOT NULL) <> %(yopiq)s
RETURNING id, archived_at
"""

USER_BY_BROKER_SQL = ("SELECT id FROM erp.app_user "
                      "WHERE broker_id = %(b)s AND active ORDER BY id LIMIT 1")


# ---------------------------------------------------------------------------
# Ko'rish va yozish huquqi
# ---------------------------------------------------------------------------
# Huquq matritsasi `api/erp/perm.py` da; bu yerda faqat OBYEKT qismi —
# "shu chatga bu odamning aloqasi bormi". Ikkalasi birga ishlatiladi
# (`api/main.py`), xuddi `karta.korish` + `egalik.talab` kabi.
def azomi(chat_id: int, user_id: int) -> bool:
    """Faol a'zomi. `umumiy` chatda hamma a'zo (a'zolik virtual)."""
    ch = db.query_one(CHAT_GET_SQL, {"id": chat_id})
    if not ch:
        return False
    if ch["turi"] == "umumiy":
        return True
    return bool(db.query_one(AZOMI_SQL, {"chat": chat_id, "uid": user_id}))


def _chat_yoki_404(chat_id: int) -> Dict[str, Any]:
    ch = db.query_one(CHAT_GET_SQL, {"id": chat_id})
    if not ch:
        raise ErpError("Chat topilmadi.", 404)
    return ch


def korish_talab(chat_id: int, user_id: int, hammasi: bool) -> Dict[str, Any]:
    """Ko'rish huquqi. `hammasi` — rahbar/menejer (barcha karta chatlari).

    403 QAYTADI, 404 EMAS: karta chatining MAVJUDLIGI sir emas (karta
    ro'yxati baribir ko'rinadi), sir — ichidagi yozishma."""
    ch = _chat_yoki_404(chat_id)
    if ch["turi"] == "umumiy" or hammasi:
        return ch
    if not db.query_one(AZOMI_SQL, {"chat": chat_id, "uid": user_id}):
        raise ErpError("Bu chatning a'zosi emassiz.", 403)
    return ch


def yozish_talab(chat_id: int, user_id: int) -> Dict[str, Any]:
    """Yozish huquqi — KO'RISHDAN QAT'IY NAZAR a'zolik talab qiladi.

    Rahbar chatni a'zosiz o'qiydi, lekin yozish uchun o'zini qo'shadi
    va bu qo'shilish lentada tizim xabari bo'lib ko'rinadi."""
    ch = _chat_yoki_404(chat_id)
    if ch["archived_at"]:
        raise ErpError(
            "Chat arxivlangan (karta yakunlangan) — yozib bo'lmaydi. "
            "Kartani qayta ochsangiz chat ham ochiladi.")
    if ch["turi"] != "umumiy" and not db.query_one(
            AZOMI_SQL, {"chat": chat_id, "uid": user_id}):
        raise ErpError(
            "Yozish uchun avval chatga qo'shiling — qo'shilganingiz "
            "lentada ko'rinadi.", 403)
    return ch


# ---------------------------------------------------------------------------
# Shakllantirish
# ---------------------------------------------------------------------------
def _shape_msg(r: Dict[str, Any], matn_korinadi: bool) -> Dict[str, Any]:
    """`matn_korinadi` — o'chirilgan xabarning MATNI berilsinmi.

    Oddiy foydalanuvchiga berilmaydi: lentada "Xabar o'chirildi (kim)"
    turadi. Rahbar/admin tahrir tarixi orqali ko'radi."""
    ochirilgan = r["deleted_at"] is not None
    out = {
        "id": r["id"], "chat_id": r["chat_id"],
        "author_id": r["author_id"],
        # `author_id IS NULL` = TIZIM xabari. Ism o'rniga aniq belgi:
        # "—" bo'sh maydonga o'xshab ketardi.
        "author_name": r["author_name"] or ("Tizim" if r["author_id"] is None
                                            else "(o'chirilgan hisob)"),
        "tizim": r["author_id"] is None,
        "text": (r["text"] if (not ochirilgan or matn_korinadi) else None),
        "ochirilgan": ochirilgan,
        "ochirdi": r["deleted_by_name"],
        "ochirish_izohi": r["delete_note"] if ochirilgan else None,
        "reply_to_id": r["reply_to_id"],
        "created_at": _iso(r["created_at"]),
        "edited_at": _iso(r["edited_at"]),
        "tahrirlangan": r["edited_at"] is not None,
    }
    if r["reply_to_id"]:
        # Javob qilingan xabar O'CHIRILGAN bo'lsa ham ko'rsatiladi —
        # "o'chirilgan xabarga javob" deb. Yo'qolsa suhbat uziladi.
        out["reply"] = {
            "id": r["reply_to_id"],
            "author_name": r["reply_author_name"] or "Tizim",
            "text": None if r["reply_deleted"] else (r["reply_text"] or "")[:120],
            "ochirilgan": bool(r["reply_deleted"]),
        }
    return out


def _shape_chat(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"], "turi": r["turi"],
        "opportunity_id": r["opportunity_id"],
        "title": r["title"] or ("Umumiy" if r["turi"] == "umumiy" else None),
        "arxiv": r["archived_at"] is not None,
        "oqilmagan": int(r["oqilmagan"] or 0),
        "oxirgi_at": _iso(r["oxirgi_at"]),
        "azoman": bool(r["azoman"]) or r["turi"] == "umumiy",
    }


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------
def chatlarim(user_id: int, hammasi: bool = False) -> List[Dict[str, Any]]:
    """Mening chatlarim + o'qilmagan soni. `umumiy` har doim birinchi."""
    _need_schema25()
    return [_shape_chat(r) for r in db.query(
        CHATLARIM_SQL, {"uid": user_id, "hammasi": bool(hammasi)})]


def lenta(chat_id: int, user_id: int, hammasi: bool = False,
          after_id: Optional[int] = None, limit: int = LIMIT_DEFAULT,
          q: Optional[str] = None,
          tarix_korish: bool = False) -> Dict[str, Any]:
    """Xabarlar lentasi. Sahifalash `after_id` bo'yicha (`id` o'sib boradi)."""
    _need_schema25()
    ch = korish_talab(chat_id, user_id, hammasi)
    lim = max(1, min(int(limit or LIMIT_DEFAULT), LIMIT_MAX))
    rows = db.query(LENTA_SQL, {"chat": chat_id, "after_id": after_id,
                                "limit": lim, "q": (q or "").strip() or None})
    return {
        "chat": {"id": ch["id"], "turi": ch["turi"],
                 "opportunity_id": ch["opportunity_id"],
                 "title": ch["title"], "arxiv": ch["archived_at"] is not None,
                 "azoman": azomi(chat_id, user_id)},
        "messages": [_shape_msg(r, tarix_korish) for r in rows],
        # "Yana bormi" — mijoz shunga qarab keyingi sahifani so'raydi.
        "yana": len(rows) == lim,
    }


def azolar(chat_id: int, user_id: int, hammasi: bool = False) -> Dict[str, Any]:
    _need_schema25()
    ch = korish_talab(chat_id, user_id, hammasi)
    sql = UMUMIY_AZO_SQL if ch["turi"] == "umumiy" else AZO_SQL
    rows = db.query(sql, {"chat": chat_id})
    return {
        "chat_id": chat_id, "turi": ch["turi"],
        # `umumiy` da a'zolik VIRTUAL: interfeys "qo'shish" tugmasini
        # ko'rsatmasligi uchun buni OCHIQ aytadi.
        "virtual": ch["turi"] == "umumiy",
        "members": [{"app_user_id": r["app_user_id"],
                     "full_name": r["full_name"], "username": r["username"],
                     "role": r["role"], "active": r["active"],
                     "added_at": _iso(r["added_at"]),
                     "added_by_name": r["added_by_name"]} for r in rows],
    }


def tarix(msg_id: int) -> List[Dict[str, Any]]:
    """Tahrir va o'chirish tarixi. Huquq (`chat.tarix`) main.py da."""
    _need_schema25()
    if not db.query_one(MSG_GET_SQL, {"id": msg_id}):
        raise ErpError("Xabar topilmadi.", 404)
    return [{"id": r["id"], "amal": r["amal"], "old_text": r["old_text"],
             "by_name": r["by_name"], "at": _iso(r["at"])}
            for r in db.query(HISTORY_SQL, {"msg": msg_id})]


# ---------------------------------------------------------------------------
# Yozish
# ---------------------------------------------------------------------------
def yoz(chat_id: int, user_id: int, text: str,
        reply_to_id: Optional[int] = None) -> Dict[str, Any]:
    _need_schema25()
    yozish_talab(chat_id, user_id)
    matn = (text or "").strip()
    if not matn:
        raise ErpError("Xabar bo'sh.")
    if len(matn) > MAX_MATN:
        raise ErpError(f"Xabar {len(matn)} belgi — chegara {MAX_MATN}.")
    if reply_to_id is not None:
        r = db.query_one(MSG_GET_SQL, {"id": reply_to_id})
        # Javob BOSHQA chatdagi xabarga bog'lanmasin: lentada
        # kontekstsiz "javob" bo'lib chiqardi.
        if not r or r["chat_id"] != chat_id:
            raise ErpError("Javob qilinayotgan xabar bu chatda yo'q.")
    row = db.execute_returning(MSG_INSERT_SQL, {
        "chat": chat_id, "author": user_id, "text": matn,
        "reply": reply_to_id})
    return _bitta(row["id"])


def tizim_xabari(chat_id: Optional[int], text: str) -> Optional[int]:
    """TIZIM xabari (`author_id IS NULL`) — status o'zgardi, hodim
    almashdi va h.k.

    HECH QACHON CHAQIRUVCHINI YIQITMAYDI (`xabar.yoz()` bilan bir xil
    qoida): karta statusini o'zgartirish chat yozuvidan muhimroq.
    Arxiv chatga ham yoziladi — tizim xabari muloqot emas, jurnal."""
    if not chat_id:
        return None
    try:
        if not schema_ready():
            return None
        row = db.execute_returning(MSG_INSERT_SQL, {
            "chat": chat_id, "author": None,
            "text": (text or "").strip()[:MAX_MATN], "reply": None})
        return row["id"] if row else None
    except Exception:                               # noqa: BLE001
        import logging
        logging.getLogger("erp.chat").exception("tizim xabari yozilmadi")
        return None


def tahrir(msg_id: int, user_id: int, text: str) -> Dict[str, Any]:
    """FAQAT O'Z xabari. Eski matn tarixga yoziladi."""
    _need_schema25()
    m = db.query_one(MSG_GET_SQL, {"id": msg_id})
    if not m:
        raise ErpError("Xabar topilmadi.", 404)
    if m["author_id"] is None:
        raise ErpError("Tizim xabari tahrirlanmaydi.")
    if m["author_id"] != user_id:
        raise ErpError("Faqat o'z xabaringizni tahrirlaysiz.", 403)
    if m["deleted_at"]:
        raise ErpError("O'chirilgan xabar tahrirlanmaydi.")
    if m["archived_at"]:
        raise ErpError("Chat arxivlangan — tahrirlab bo'lmaydi.")
    matn = (text or "").strip()
    if not matn:
        raise ErpError("Xabar bo'sh.")
    if len(matn) > MAX_MATN:
        raise ErpError(f"Xabar {len(matn)} belgi — chegara {MAX_MATN}.")
    if matn == m["text"]:
        return _bitta(msg_id)
    # TARIX AVVAL: yozuv o'zgargandan keyin eski matnni olib bo'lmaydi.
    db.execute_returning(HISTORY_INSERT_SQL, {
        "msg": msg_id, "amal": "tahrir", "old": m["text"], "by": user_id})
    db.execute_returning(MSG_EDIT_SQL, {"id": msg_id, "text": matn})
    return _bitta(msg_id)


def ochir(msg_id: int, user_id: int, moderator: bool = False,
          note: Optional[str] = None) -> Dict[str, Any]:
    """YUMSHOQ o'chirish. Qator qoladi, matn tarixda saqlanadi.

    Moderatsiyada (birovnikini o'chirishda) izoh MAJBURIY va muallifga
    bildirishnoma ketadi — "xabarim qayoqqa ketdi" degan savol
    qolmasin."""
    _need_schema25()
    m = db.query_one(MSG_GET_SQL, {"id": msg_id})
    if not m:
        raise ErpError("Xabar topilmadi.", 404)
    if m["author_id"] is None:
        raise ErpError("Tizim xabari o'chirilmaydi.")
    if m["deleted_at"]:
        raise ErpError("Xabar allaqachon o'chirilgan.")

    oziniki = m["author_id"] == user_id
    if not oziniki and not moderator:
        raise ErpError("Boshqaning xabarini o'chirish huquqi yo'q.", 403)
    izoh = (note or "").strip() or None
    if not oziniki and not izoh:
        raise ErpError("Boshqaning xabarini o'chirishda SABAB majburiy — "
                       "u muallifga yuboriladi.")

    db.execute_returning(HISTORY_INSERT_SQL, {
        "msg": msg_id, "amal": "ochirish", "old": m["text"], "by": user_id})
    db.execute_returning(MSG_DELETE_SQL, {
        "id": msg_id, "by": user_id, "note": izoh})

    if not oziniki:
        # Import shu yerda: `xabar` moduli `chat` ni bilmaydi va aylanma
        # bog'lanish paydo bo'lmasin.
        from api.erp import xabar
        xabar.yoz(m["author_id"], "chat_ochirildi",
                  f"Xabaringiz o'chirildi. Sabab: {izoh}",
                  m["opportunity_id"])
    return _bitta(msg_id)


def _bitta(msg_id: int) -> Dict[str, Any]:
    # ALOHIDA so'rov (`BITTA_SQL`), `LENTA_SQL` ni satr almashtirish
    # bilan qayta yasash EMAS: bir vaqtlar shunday edi va so'rov matni
    # ozgina o'zgarganda u JIMGINA bo'sh natija qaytardi — xato ham
    # bermasdi, shunchaki "xabar yozildi, lekin javob bo'sh" bo'lardi.
    r = db.query_one(BITTA_SQL, {"id": msg_id})
    return _shape_msg(r, False) if r else {}


# ---------------------------------------------------------------------------
# A'zolar
# ---------------------------------------------------------------------------
def azo_qosh(chat_id: int, kim_id: int, yangi_user_id: int) -> Dict[str, Any]:
    _need_schema25()
    ch = _chat_yoki_404(chat_id)
    if ch["turi"] == "umumiy":
        raise ErpError("Umumiy chatga a'zo qo'shilmaydi — barcha faol "
                       "hodimlar uni allaqachon ko'radi.")
    u = db.query_one("SELECT id, full_name, active FROM erp.app_user "
                     "WHERE id = %(id)s", {"id": yangi_user_id})
    if not u:
        raise ErpError("Hisob topilmadi.", 404)
    if not u["active"]:
        raise ErpError("Faolsizlantirilgan hisob chatga qo'shilmaydi.")
    if db.query_one(AZOMI_SQL, {"chat": chat_id, "uid": yangi_user_id}):
        raise ErpError("Bu hodim allaqachon a'zo.", 409)

    db.execute_returning(MEMBER_ADD_SQL, {
        "chat": chat_id, "uid": yangi_user_id, "by": kim_id})
    kim = db.query_one("SELECT full_name FROM erp.app_user WHERE id = %(id)s",
                       {"id": kim_id}) or {}
    ozini = kim_id == yangi_user_id
    tizim_xabari(chat_id, f"{u['full_name']} chatga qo'shildi."
                 if not ozini else f"{u['full_name']} chatga o'zi qo'shildi.")
    if not ozini:
        from api.erp import xabar
        xabar.yoz(yangi_user_id, "chat_qoshildi",
                  f"Sizni chatga qo'shdi: {kim.get('full_name') or 'hodim'}"
                  + (f" — {ch['title']}" if ch["title"] else ""),
                  ch["opportunity_id"])
    return azolar(chat_id, kim_id, hammasi=True)


def azo_chiqar(chat_id: int, kim_id: int, user_id: int) -> Dict[str, Any]:
    """Chiqarish YUMSHOQ: yozganlari lentada QOLADI.

    Kartaning MAS'ULINI chiqarib bo'lmaydi — chat aynan u bilan muloqot
    uchun. Avval hodim almashtiriladi, keyin xohlasa chiqariladi."""
    _need_schema25()
    ch = _chat_yoki_404(chat_id)
    if ch["turi"] == "umumiy":
        raise ErpError("Umumiy chatdan chiqib bo'lmaydi.")
    if ch["opp_broker_id"]:
        mas_ul = db.query_one(USER_BY_BROKER_SQL, {"b": ch["opp_broker_id"]})
        if mas_ul and mas_ul["id"] == user_id:
            raise ErpError(
                "Kartaning mas'ulini chatdan chiqarib bo'lmaydi — chat "
                "aynan u bilan muloqot uchun. Avval hodimni almashtiring.")
    if not db.execute_returning(MEMBER_REMOVE_SQL, {
            "chat": chat_id, "uid": user_id, "by": kim_id}):
        raise ErpError("Bu hodim chatda faol a'zo emas.", 404)
    u = db.query_one("SELECT full_name FROM erp.app_user WHERE id = %(id)s",
                     {"id": user_id}) or {}
    tizim_xabari(chat_id, f"{u.get('full_name') or 'Hodim'} chatdan chiqarildi.")
    return azolar(chat_id, kim_id, hammasi=True)


def oqildi(chat_id: int, user_id: int,
           last_read_id: Optional[int] = None) -> Dict[str, Any]:
    """O'qilgan chegarani surish. Berilmasa — chatning oxirgi xabari."""
    _need_schema25()
    _chat_yoki_404(chat_id)
    if last_read_id is None:
        r = db.query_one("SELECT coalesce(max(id), 0) AS m "
                         "FROM erp.chat_message WHERE chat_id = %(c)s",
                         {"c": chat_id})
        last_read_id = int(r["m"] if r else 0)
    row = db.execute_returning(READ_SQL, {
        "chat": chat_id, "uid": user_id, "last": int(last_read_id)})
    return {"chat_id": chat_id, "last_read_id": row["last_read_id"]}


# ---------------------------------------------------------------------------
# Karta bilan bog'lanish — boshqa modullar shu funksiyalarni chaqiradi
# ---------------------------------------------------------------------------
def karta_chati(opp_id: int) -> Optional[int]:
    """Kartaning chat id si. Sxema yo'q bo'lsa `None` (xato emas)."""
    if not schema_ready():
        return None
    r = db.query_one(CHAT_BY_OPP_SQL, {"opp": opp_id})
    return r["id"] if r else None


def karta_chati_yarat(opp_id: int, title: Optional[str],
                      broker_id: Optional[int] = None,
                      created_by_user_id: Optional[int] = None,
                      birinchi_xabar: Optional[str] = None) -> Optional[int]:
    """Karta ochilganda chat ham ochiladi.

    HECH QACHON CHAQIRUVCHINI YIQITMAYDI: karta ochilishi chatdan
    muhimroq (`xabar.yoz()` va `_birinchi_vazifa()` bilan bir xil
    qoida). Sxema qo'llanmagan bo'lsa jim o'tadi.

    A'zolar: kartaning mas'uli (hisobi bo'lsa) va kartani ochgan odam.
    Mas'ul yo'q bo'lsa ("Taqsimlanmagan") — faqat ochgan odam; hodim
    tayinlanganda `azo_qosh` bilan qo'shiladi."""
    try:
        if not schema_ready():
            return None
        row = db.execute_returning(CHAT_CREATE_SQL, {
            "opp": opp_id, "title": (title or f"#{opp_id}")[:200],
            "by": created_by_user_id})
        if not row:                                  # allaqachon bor
            return karta_chati(opp_id)
        chat_id = row["id"]
        azo_ids = set()
        if broker_id:
            u = db.query_one(USER_BY_BROKER_SQL, {"b": broker_id})
            if u:
                azo_ids.add(u["id"])
        if created_by_user_id:
            azo_ids.add(created_by_user_id)
        for uid in sorted(azo_ids):
            db.execute_returning(MEMBER_ADD_SQL, {
                "chat": chat_id, "uid": uid, "by": created_by_user_id})
        if birinchi_xabar:
            tizim_xabari(chat_id, birinchi_xabar)
        return chat_id
    except Exception:                               # noqa: BLE001
        import logging
        logging.getLogger("erp.chat").exception("karta chati ochilmadi")
        return None


def karta_arxiv(opp_id: int, yopiq: bool) -> None:
    """Karta yakuniy statusga o'tdi/qaytdi — chat arxivlanadi/ochiladi."""
    try:
        if not schema_ready():
            return
        db.execute_returning(ARXIV_SQL, {"opp": opp_id, "yopiq": bool(yopiq)})
    except Exception:                               # noqa: BLE001
        import logging
        logging.getLogger("erp.chat").exception("chat arxivi o'zgarmadi")


def karta_chati_id(opp_id: int, user_id: int) -> Dict[str, Any]:
    """Kartadan chatga o'tish. Chat yo'q bo'lsa SHU YERDA ochiladi.

    NEGA SHU YERDA: 25-patchdan OLDIN ochilgan kartalarni patch
    ko'chirgan, lekin patch qo'llangandan keyin, ilova yangilanmasidan
    oldin ochilgan karta chatsiz qolishi mumkin. Interfeys "chat yo'q"
    degan tushunarsiz holat ko'rsatgandan ko'ra, uni ochib beradi."""
    _need_schema25()
    o = db.query_one("SELECT id, title, broker_id, status FROM erp.opportunity "
                     "WHERE id = %(id)s", {"id": opp_id})
    if not o:
        raise ErpError("Karta topilmadi.", 404)
    chat_id = karta_chati(opp_id)
    if not chat_id:
        chat_id = karta_chati_yarat(opp_id, o["title"], o["broker_id"], user_id)
        if not chat_id:
            raise ErpError("Chat ochilmadi.", 503)
        # Karta allaqachon yakuniy bo'lsa chat darhol arxiv bo'lsin —
        # yopilgan kartada yozish ochiq qolib ketmasin.
        if o["status"] in ARXIV_HOLATLAR:
            karta_arxiv(opp_id, True)
    return {"chat_id": chat_id, "opportunity_id": opp_id}


def egalik_talab(chat_id: int, user: Dict[str, Any], amal: str) -> None:
    """`OZ` darajali amal uchun: chat MENING kartamnikimi.

    Huquq matritsasi amalni biladi, obyektni bilmaydi (`api/erp/perm.py`)
    — `karta.korish` + `egalik.talab` juftligi bilan bir xil naqsh.
    Bu yerda zanjir: chat -> karta -> kartaning brokeri -> mening
    hisobim. `umumiy` chatda egalik tushunchasi yo'q."""
    from api.erp import perm
    if perm.can(user, amal) != perm.OZ or not perm.OZ_FILTRI_TAYYOR:
        return
    ch = _chat_yoki_404(chat_id)
    if ch["turi"] == "umumiy":
        return
    from api.erp import egalik
    egalik.talab(user, "opportunity", ch["opportunity_id"])


def eslat(chat_id: int, kim_id: int, msg_id: int,
          user_ids: List[int]) -> Dict[str, Any]:
    """`@ism` eslatish -> bildirishnoma.

    MATNDAN QIDIRILMAYDI: bir xil ismli ikki hodim bo'lsa xabar
    noto'g'ri odamga ketardi, umuman topilmasa esa JIM qolardi.
    Interfeys kimni eslatganini aniq yuboradi.

    Faqat CHATNING FAOL A'ZOLARI eslatiladi: a'zo bo'lmagan odamga
    "sizni eslatishdi" deb yuborish, u ochganda 403 bilan tugardi."""
    _need_schema25()
    ch = _chat_yoki_404(chat_id)
    kimlar = {int(u) for u in (user_ids or []) if int(u) != kim_id}
    if not kimlar:
        return {"eslatildi": 0}
    if ch["turi"] == "umumiy":
        mumkin = {r["app_user_id"] for r in db.query(UMUMIY_AZO_SQL, {})}
    else:
        mumkin = {r["app_user_id"] for r in db.query(AZO_SQL, {"chat": chat_id})}
    kim = db.query_one("SELECT full_name FROM erp.app_user WHERE id = %(id)s",
                       {"id": kim_id}) or {}
    nom = ch["title"] or "Umumiy"
    from api.erp import xabar
    n = 0
    for uid in sorted(kimlar & mumkin):
        if xabar.yoz(uid, "chat_mention",
                     f"{kim.get('full_name') or 'Hodim'} sizni eslatdi "
                     f"({nom}).", ch["opportunity_id"]):
            n += 1
    return {"eslatildi": n, "message_id": msg_id}
