"""
TENDER-AI YO'NALTIRISHI — topshiriq ish kartasiga aylanadigan joy.

    from api.erp import topshiriq
    topshiriq.holat()      # xarita bormi, nechta kutyapti
    topshiriq.sync()       # kutayotganlarini kartaga aylantiradi
    topshiriq.tingla_boshla()   # LISTEN — fonda, ilova bilan birga

MUAMMO: broker Tender-AI navbatida "Olindi" derdi va zanjir shu yerda
UZILARDI. ERP kartani QO'LDA ochardi: tenderni qidiradi, mijozni
tanlaydi, muddatni ko'chiradi. Qaror u yerda, ish esa bu yerda va
o'rtada odam turardi. "Bu karta qaysi qarordan kelgan?" degan savolga
javob umuman yo'q edi.

YECHIM (`erp_rollar.md` §5): Tender-AI `public.tender_topshiriq` ga
yozadi va `pg_notify('erp_topshiriq', id)` yuboradi. ERP shu xabarni
eshitadi va `public.v_erp_topshiriq` VIEW idan o'qib karta ochadi.

    HTTP yo'q. Service kaliti yo'q. CORS yo'q.
    ERP `public.*` ga YOZMAYDI — faqat o'qiydi (chegara qoidasi).

XABAR — TEZLIK UCHUN, ISHONCHLILIK UCHUN EMAS
═════════════════════════════════════════════
`LISTEN` uzilishi mumkin (ulanish uzildi, ERP o'chirilgan edi,
migratsiya yurdi). Shuning uchun `sync()` XABARDAN MUSTAQIL ishlaydi:
u view ni o'qiydi va "kartasi yo'q" topshiriqlarni topadi. Tinglovchi
har `SO'ROV_ORALIG'I` soniyada baribir shu tekshiruvni yuritadi.

Ya'ni xabar YO'QOLSA ham topshiriq yo'qolmaydi — kechikadi, xolos.

XARITA — OPERATOR QARORI
════════════════════════
`erp.own_company.tai_company_id` qo'yilmagan bo'lsa modul HECH NARSA
qilmaydi va buni ochiq aytadi (`holat()`). Bu ATAYLAB xavfsiz
standart: xaritasiz o'rnatma boshqa ijarachining (yoki sinov
ijarachisining) topshirig'ini o'ziniki deb qabul qilmasin.

XAT ETMAGAN HODIM JIMGINA YO'QOLMAYDI
═════════════════════════════════════
Topshiriqdagi aktor ERP hodimiga xaritalanmagan bo'lsa karta baribir
ochiladi — `broker_id = NULL`, ya'ni "Taqsimlanmagan". Muqobili
(topshiriqni tashlab yuborish) eng yomoni bo'lardi: Tender-AI da
"berildi" deb turadi, ERP da esa hech narsa yo'q.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import psycopg2

from api import db
from api.erp import opportunity as erp_opp
from api.erp import xabar
from api.erp.opportunity import ErpError

log = logging.getLogger("erp.topshiriq")

#: Xabar kanali — Tender-AI tomonidagi trigger bilan BIR XIL nom
#: (`schema_patch_topshiriq.sql`).
KANAL = "erp_topshiriq"

#: Zaxira so'rov oralig'i (soniya). Xabar yo'qolsa ham topshiriq shu
#: muddat ichida topiladi.
SOROV_ORALIGI = float(os.environ.get("ERP_TOPSHIRIQ_ORALIQ", "60"))

#: Bir yurishda ko'riladigan eng ko'p topshiriq.
LIMIT = 50

VIEW = "public.v_erp_topshiriq"

_tinglovchi: Optional[threading.Thread] = None
_toxta = threading.Event()
_oxirgi_xato: Optional[str] = None


# ---------------------------------------------------------------------------
# Tayyorlik va xarita
# ---------------------------------------------------------------------------
def ready() -> bool:
    """Ikkala tomon ham migratsiyani qo'llaganmi."""
    return bool(db.scalar(
        "SELECT to_regclass('public.v_erp_topshiriq') IS NOT NULL"
        "   AND to_regclass('erp.opportunity_analysis') IS NOT NULL"))


def xarita() -> Optional[int]:
    """Biz qaysi Tender-AI ijarachisimiz (`own_company.tai_company_id`).

    NULL — modul o'chiq. Bu xato emas, sozlanmagan holat."""
    try:
        return db.scalar("SELECT tai_company_id FROM erp.own_company "
                         "ORDER BY id LIMIT 1")
    except Exception:                           # noqa: BLE001
        return None


def xarita_qoy(company_id: Optional[int]) -> Optional[int]:
    """Xaritani o'rnatadi (operator qarori, admin huquqi)."""
    if not db.query_one("SELECT 1 AS x FROM erp.own_company LIMIT 1"):
        raise ErpError("Avval kompaniya passportini to'ldiring.", 400)
    db.execute_returning(
        "UPDATE erp.own_company SET tai_company_id = %(c)s, updated_at = now() "
        "WHERE id = (SELECT id FROM erp.own_company ORDER BY id LIMIT 1) "
        "RETURNING id", {"c": company_id})
    return xarita()


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------
KUTAYOTGAN_SQL = f"""
SELECT t.*
FROM {VIEW} t
LEFT JOIN erp.opportunity o ON o.routing_id = t.routing_id
WHERE t.company_id = %(c)s
  AND (
       -- 1. Kartasi yo'q va bekor ham qilinmagan -> ochiladi.
       (o.id IS NULL AND t.bekor_at IS NULL)
       -- 2. Bekor qilingan, lekin karta hali yopilmagan -> yopiladi.
    OR (o.id IS NOT NULL AND t.bekor_at IS NOT NULL
        AND o.status <> 'rejected')
       -- 3. Tahlil YANGILANGAN (yangi topshiriq versiyasi).
    OR (o.id IS NOT NULL AND t.bekor_at IS NULL
        AND o.topshiriq_id IS DISTINCT FROM t.id)
  )
ORDER BY t.yaratilgan_at
LIMIT %(l)s
"""

BITTA_SQL = f"SELECT * FROM {VIEW} WHERE id = %(i)s"


def holat() -> Dict[str, Any]:
    """Interfeys va `check_setup.py` uchun: nima sozlangan, nima kutyapti."""
    tayyor = ready()
    cid = xarita()
    out: Dict[str, Any] = {
        "ready": tayyor, "tai_company_id": cid,
        "tinglovchi": bool(_tinglovchi and _tinglovchi.is_alive()),
        "oraliq": SOROV_ORALIGI, "oxirgi_xato": _oxirgi_xato,
    }
    if not tayyor:
        out["sabab"] = ("schema_patch_erp_21.sql yoki Tender-AI tomonidagi "
                        "schema_patch_topshiriq.sql qo'llanmagan")
        return out
    if not cid:
        out["sabab"] = ("erp.own_company.tai_company_id qo'yilmagan — "
                        "qaysi Tender-AI ijarachisi ekanimiz noma'lum")
        return out
    out["kutayotgan"] = len(db.query(KUTAYOTGAN_SQL, {"c": cid, "l": LIMIT}))
    out["kartalar"] = db.scalar(
        "SELECT count(*) FROM erp.opportunity WHERE routing_id IS NOT NULL")
    return out


# ---------------------------------------------------------------------------
# Kartaga aylantirish
# ---------------------------------------------------------------------------
def _hodim(app_user_id: Optional[int]) -> Optional[int]:
    """ERP hisob id si -> HODIM yozuvi (`erp.broker.id`).

    Kartaning mas'uli hodim, hisob emas: hisob yopilishi mumkin,
    hodim esa tarixda qoladi."""
    if not app_user_id:
        return None
    return db.scalar("SELECT broker_id FROM erp.app_user WHERE id = %(i)s",
                     {"i": app_user_id})


def _tarix(opp_id: int, matn: str, kim: Optional[str],
           to_status: str, from_status: Optional[str] = None) -> None:
    """Tarix yozuvi. `to_status` MAJBURIY — jadvalda `NOT NULL`.

    Bosqich o'tishi bo'lmagan yozuvda (masalan "tahlil yangilandi")
    joriy status qo'yiladi: tarix "status o'zgardi" deb ko'rsatmasin,
    lekin yozuv ham yo'qolmasin."""
    db.execute_returning(erp_opp.HISTORY_INSERT_SQL, {
        "opportunity_id": opp_id, "from_status": from_status,
        "to_status": to_status, "changed_by": kim, "note": matn})


def _tahlil_saqla(opp_id: int, t: Dict[str, Any]) -> None:
    """Tahlil SNAPSHOTI — har topshiriq versiyasi uchun yangi qator."""
    payload = t.get("tahlil")
    if payload is None:
        return
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, default=str)
    db.execute_returning(
        "INSERT INTO erp.opportunity_analysis "
        "(opportunity_id, topshiriq_id, payload, ishonch) "
        "VALUES (%(o)s, %(t)s, %(p)s::jsonb, %(i)s) RETURNING id",
        {"o": opp_id, "t": t.get("id"), "p": payload, "i": t.get("ishonch")})


def _kim(t: Dict[str, Any]) -> str:
    """Tarixdagi ism: kim yo'naltirgani + ishonch darajasi.

    Yorliq DALILDAN OSHMAYDI: `aktor_elon` — "e'lon qilingan", ya'ni
    kompaniya sessiyasida aytilgan, isbotlanmagan."""
    ism = t.get("yonaltirgan_ism") or "Tender-AI"
    if t.get("ishonch") == "aktor_elon":
        return f"{ism} (e'lon qilingan)"
    if t.get("ishonch") == "kompaniya_sessiyasi":
        return "Tender-AI (hodim ko'rsatilmagan)"
    if t.get("ishonch") == "servis":
        return "Tender-AI (avtomat)"
    return ism


def _karta_yarat(t: Dict[str, Any]) -> Dict[str, Any]:
    """Topshiriqdan yangi karta. Snapshot `public.tender` dan.

    KARTA ALLAQACHON BOR BO'LSA (hodim uni qo'lda ochib qo'ygan yoki
    eski qaror bo'yicha ochilgan) — YANGISI OCHILMAYDI, mavjudi
    topshiriqqa BOG'LANADI. Sabab: "bir tender + bir mijoz = bir
    karta" qoidasi (`erp.opportunity` UNIQUE) va ikkinchi kartani
    ochish odamning ishini ikkiga bo'lardi."""
    broker_id = _hodim(t.get("hodim_app_user_id"))
    kim = _kim(t)
    try:
        return _yangi_karta(t, broker_id, kim)
    except ErpError as e:
        mavjud = (e.extra or {}).get("opportunity_id")
        if e.code != 409 or not mavjud:
            raise
        return _mavjudga_bogla(t, mavjud, kim)


def _mavjudga_bogla(t: Dict[str, Any], opp_id: int,
                    kim: str) -> Dict[str, Any]:
    """Qo'lda ochilgan kartani qarorga bog'laydi (maydonlarga tegmaydi)."""
    db.execute_returning(
        "UPDATE erp.opportunity SET routing_id = %(r)s, tai_company_id = %(c)s,"
        " assigned_ishonch = %(i)s, topshiriq_id = %(t)s, updated_at = now() "
        "WHERE id = %(id)s AND routing_id IS NULL RETURNING id",
        {"r": t["routing_id"], "c": t["company_id"], "i": t.get("ishonch"),
         "t": t.get("id"), "id": opp_id})
    holat = db.scalar("SELECT status FROM erp.opportunity WHERE id = %(i)s",
                      {"i": opp_id}) or "new"
    _tarix(opp_id, f"Tender-AI qaroriga bog'landi: {kim}", kim,
           to_status=holat, from_status=holat)
    _tahlil_saqla(opp_id, t)
    return {"holat": "mavjudga_boglandi", "opportunity_id": opp_id,
            "routing_id": t["routing_id"], "taqsimlanmagan": False}


def _yangi_karta(t: Dict[str, Any], broker_id: Optional[int],
                 kim: str) -> Dict[str, Any]:
    karta = erp_opp.take(int(t["tender_id"]), {
        "broker_id": broker_id,
        # Mijoz ERP tushunchasi — Tender-AI uni bilmaydi. Hodim
        # kartani ochganda tanlaydi.
        "client_id": None,
        "priority": t.get("ustuvorlik") or "medium",
        "note": t.get("izoh"),
        # Muddat berilgan bo'lsa u HAQIQIY vazifaga aylanadi
        # (`opportunity._birinchi_vazifa`) — ya'ni vazifalar ro'yxatida,
        # "mening ishlarim" da va eslatmada ko'rinadi. Shu sababli
        # sarlavha ham odam o'qiydigan bo'lishi kerak.
        "next_task": ("Tender-AI bergan muddatga tayyorgarlik"
                      if t.get("muddat") else None),
        "next_task_at": t.get("muddat"),
        "created_by": kim,
    })
    db.execute_returning(
        "UPDATE erp.opportunity SET routing_id = %(r)s, tai_company_id = %(c)s,"
        " assigned_ishonch = %(i)s, topshiriq_id = %(t)s, updated_at = now() "
        "WHERE id = %(id)s RETURNING id",
        {"r": t["routing_id"], "c": t["company_id"], "i": t.get("ishonch"),
         "t": t.get("id"), "id": karta["id"]})
    kimga = t.get("hodim_ism") or "Taqsimlanmagan"
    _tarix(karta["id"], f"Tender-AI'dan yo'naltirildi: {kim} → {kimga}", kim,
           to_status="new", from_status="new")
    _tahlil_saqla(karta["id"], t)
    _xabar_bering(karta, t, broker_id, kim)
    return {"holat": "yaratildi", "opportunity_id": karta["id"],
            "routing_id": t["routing_id"],
            "taqsimlanmagan": broker_id is None}


def _xabar_bering(karta: Dict[str, Any], t: Dict[str, Any],
                  broker_id: Optional[int], kim: str) -> None:
    """Karta ochilgani JIM QOLMAYDI.

    Ikki holat, ikki manzil:
      * hodim biriktirilgan -> O'SHA odamga ("sizga karta berildi");
      * xaritalanmagan      -> MENEJERGA ("kimdir taqsimlashi kerak").

    Ikkinchisi eng muhim: aks holda karta "Taqsimlanmagan" ustunida
    hech kim ko'rmasdan yotib qolardi va Tender-AI da "berildi" deb
    turardi."""
    nom = karta.get("title") or f"#{karta['id']}"
    if broker_id:
        xabar.brokerga(broker_id, "topshiriq",
                       f"Tender-AI'dan yangi karta: {nom}. "
                       f"Yo'naltirdi: {kim}.", karta["id"])
    else:
        xabar.menejerlarga(
            "taqsimlanmagan",
            f"Karta TAQSIMLANMAGAN: {nom}. Tender-AI'da hodim "
            f"ko'rsatilmagan yoki u ERP hodimiga xaritalanmagan "
            f"(yo'naltirdi: {kim}).", karta["id"])


def _karta_bekor(t: Dict[str, Any], opp: Dict[str, Any]) -> Dict[str, Any]:
    """Tender-AI da qaror bekor qilindi — karta YOPILADI, o'chmaydi.

    O'chirish ma'lumot yo'qotish bo'lardi: kartada izoh, vazifa va
    tarix bo'lishi mumkin."""
    # SABAB 'other': 24-patchdan boshlab yakunlanmagan holatlar sababsiz
    # yopilmaydi. Ro'yxatdagi yettita koddan hech biri "manba tizimda
    # yo'naltirish bekor qilindi" ni ANIQ ifodalamaydi, shuning uchun
    # 'other' + izoh. Yangi kod QO'SHILMADI: `lost_reason` broker
    # tanlaydigan ro'yxat va unga tizim sababini qo'shish odam ko'radigan
    # tanlovni chalg'itardi. Izoh esa tarixda to'liq qoladi.
    erp_opp.set_status(opp["id"], "rejected", "Tender-AI",
                       "Tender-AI'da qaror bekor qilindi", "other")
    # Karta ustida ishlayotgan odam buni BILISHI kerak: u tayyorgarlik
    # ko'rayotgan bo'lishi mumkin.
    to_liq = db.query_one("SELECT broker_id, title FROM erp.opportunity "
                          "WHERE id = %(i)s", {"i": opp["id"]}) or {}
    nom = to_liq.get("title") or f"#{opp['id']}"
    xabar.brokerga(to_liq.get("broker_id"), "bekor",
                   f"Tender-AI'da qaror bekor qilindi: {nom}. "
                   f"Karta 'Rad etildi' ga o'tkazildi.", opp["id"])
    xabar.menejerlarga("bekor",
                       f"Tender-AI'da qaror bekor qilindi: {nom}.", opp["id"])
    return {"holat": "bekor_qilindi", "opportunity_id": opp["id"],
            "routing_id": t["routing_id"]}


def _tahlil_yangila(t: Dict[str, Any], opp: Dict[str, Any]) -> Dict[str, Any]:
    """Yangi tahlil versiyasi. KARTA MAYDONLARI TEGILMAYDI.

    Hodim kartani allaqachon tahrirlagan bo'lishi mumkin (mijoz,
    ustuvorlik, izoh). Ularni Tender-AI qiymatiga qaytarish odamning
    ishini bekor qilardi — shuning uchun faqat tahlil qo'shiladi."""
    _tahlil_saqla(opp["id"], t)
    db.execute_returning(
        "UPDATE erp.opportunity SET topshiriq_id = %(t)s, "
        "assigned_ishonch = %(i)s, updated_at = now() WHERE id = %(id)s "
        "RETURNING id",
        {"t": t.get("id"), "i": t.get("ishonch"), "id": opp["id"]})
    _tarix(opp["id"], "Tender-AI tahlili yangilandi", _kim(t),
           to_status=opp["status"], from_status=opp["status"])
    return {"holat": "tahlil_yangilandi", "opportunity_id": opp["id"],
            "routing_id": t["routing_id"]}


def _bitta(t: Dict[str, Any]) -> Dict[str, Any]:
    """Bitta topshiriqni ko'rib chiqadi (idempotent)."""
    opp = db.query_one(
        "SELECT id, status, topshiriq_id FROM erp.opportunity "
        "WHERE routing_id = %(r)s", {"r": t["routing_id"]})
    if t.get("bekor_at"):
        if opp and opp["status"] != "rejected":
            return _karta_bekor(t, opp)
        return {"holat": "o'tkazildi", "sabab": "bekor, karta yopiq yoki yo'q",
                "routing_id": t["routing_id"]}
    if not opp:
        return _karta_yarat(t)
    if opp["topshiriq_id"] != t.get("id"):
        return _tahlil_yangila(t, opp)
    return {"holat": "o'tkazildi", "sabab": "allaqachon ko'rilgan",
            "routing_id": t["routing_id"]}


def sync(limit: int = LIMIT) -> Dict[str, Any]:
    """Kutayotgan topshiriqlarni kartaga aylantiradi.

    XABARDAN MUSTAQIL: view ni o'qiydi va farqni topadi. Shuning
    uchun uni qo'lda ham, jadval bo'yicha ham chaqirish mumkin."""
    if not ready():
        return {"holat": "migratsiya_yoq", "natijalar": []}
    cid = xarita()
    if not cid:
        return {"holat": "xarita_yoq", "natijalar": []}
    natijalar: List[Dict[str, Any]] = []
    for t in db.query(KUTAYOTGAN_SQL, {"c": cid, "l": max(1, min(limit, 200))}):
        try:
            natijalar.append(_bitta(dict(t)))
        except Exception as e:                  # noqa: BLE001
            # BITTA topshiriq yiqilsa qolganlari to'xtamaydi va sabab
            # YO'QOLMAYDI: u natijada ham, jurnalda ham qoladi.
            log.exception("topshiriq %s ko'rilmadi", t.get("id"))
            natijalar.append({"holat": "xato", "routing_id": t.get("routing_id"),
                              "xato": f"{type(e).__name__}: {e}"[:300]})
    return {"holat": "ok", "natijalar": natijalar,
            "yaratildi": sum(1 for n in natijalar if n["holat"] == "yaratildi"),
            "bekor": sum(1 for n in natijalar if n["holat"] == "bekor_qilindi"),
            "xato": sum(1 for n in natijalar if n["holat"] == "xato")}


def bitta_id(topshiriq_id: int) -> Dict[str, Any]:
    """Xabarda kelgan aniq topshiriq (kanal `id` yuboradi)."""
    if not ready():
        return {"holat": "migratsiya_yoq"}
    cid = xarita()
    t = db.query_one(BITTA_SQL, {"i": topshiriq_id})
    if not t or not cid or t["company_id"] != cid:
        # BEGONA IJARACHI — jimgina o'tkaziladi. Bu xato emas: bitta
        # bazada bir necha ijarachi bo'lishi mumkin va ular bir-birini
        # ko'rmasligi kerak.
        return {"holat": "o'tkazildi", "sabab": "boshqa ijarachi yoki yo'q"}
    return _bitta(dict(t))


# ---------------------------------------------------------------------------
# Tinglovchi
# ---------------------------------------------------------------------------
def _dsn() -> str:
    return os.environ.get("XT_DB_DSN", "")


def _tingla() -> None:
    """LISTEN halqasi. ALOHIDA ulanish: pul ulanishini band qilib
    bo'lmaydi (u so'rovlarga kerak)."""
    global _oxirgi_xato
    while not _toxta.is_set():
        conn = None
        try:
            conn = psycopg2.connect(dsn=_dsn())
            conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute(f"LISTEN {KANAL}")
            log.info("topshiriq tinglovchisi ishga tushdi (kanal=%s)", KANAL)
            _oxirgi_xato = None
            while not _toxta.is_set():
                # Vaqt tugashi ZAXIRA SO'ROV ham bo'ladi: xabar
                # yo'qolgan bo'lsa ham kutayotganlar topiladi.
                if _toxta.wait(SOROV_ORALIGI):
                    break
                conn.poll()
                xabarlar = [n.payload for n in conn.notifies]
                conn.notifies.clear()
                try:
                    if xabarlar:
                        for p in xabarlar:
                            bitta_id(int(p))
                    else:
                        sync()
                except Exception as e:          # noqa: BLE001
                    _oxirgi_xato = f"{type(e).__name__}: {e}"[:300]
                    log.exception("topshiriqni ko'rishda xato")
        except Exception as e:                  # noqa: BLE001
            _oxirgi_xato = f"{type(e).__name__}: {e}"[:300]
            log.warning("tinglovchi uzildi: %s", e)
            # Qayta ulanishdan oldin kutamiz: baza o'chgan bo'lsa
            # halqa protsessorni yeb qo'ymasin.
            _toxta.wait(min(SOROV_ORALIGI, 30))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:               # noqa: BLE001
                    pass


def tingla_boshla() -> bool:
    """Fon oqimini ishga tushiradi. Xarita yo'q bo'lsa — boshlamaydi.

    `ERP_TOPSHIRIQ_LISTEN=0` bilan butunlay o'chiriladi (sinov va
    ishlab chiqishda foydali)."""
    global _tinglovchi
    if os.environ.get("ERP_TOPSHIRIQ_LISTEN", "1") == "0":
        return False
    if _tinglovchi and _tinglovchi.is_alive():
        return True
    if not ready() or not xarita():
        return False
    _toxta.clear()
    _tinglovchi = threading.Thread(target=_tingla, name="erp-topshiriq",
                                   daemon=True)
    _tinglovchi.start()
    # Birinchi yurishda kutayotganlar darhol ko'riladi: ERP o'chiq
    # turgan paytda kelgan topshiriqlar kutib qolmasin.
    try:
        sync()
    except Exception:                           # noqa: BLE001
        log.exception("boshlang'ich sync yiqildi")
    return True


def tingla_toxta(timeout: float = 3.0) -> None:
    _toxta.set()
    t = _tinglovchi
    if t and t.is_alive():
        t.join(timeout=timeout)


def tahlil(opp_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Kartaning tahlil snapshotlari — eng yangisi birinchi."""
    if not ready():
        return []
    rows = db.query(
        "SELECT id, topshiriq_id, payload, ishonch, captured_at "
        "FROM erp.opportunity_analysis WHERE opportunity_id = %(o)s "
        "ORDER BY captured_at DESC, id DESC LIMIT %(l)s",
        {"o": opp_id, "l": max(1, min(limit, 20))})
    return [{"id": r["id"], "topshiriq_id": r["topshiriq_id"],
             "ishonch": r["ishonch"],
             "captured_at": r["captured_at"].isoformat() if r["captured_at"] else None,
             "payload": r["payload"]} for r in rows]
