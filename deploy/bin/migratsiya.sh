#!/usr/bin/env bash
# =============================================================================
# Tender ERP — sxema patchlarini QO'LLASH
# =============================================================================
#     migratsiya.sh --holat            # nima qo'llangan, nima yo'q
#     migratsiya.sh --qolla            # qo'llash
#     migratsiya.sh --qolla --dsn "dbname=... user=... "
#
# DSN: argumentdan, bo'lmasa `XT_DB_DSN_OWNER`, bo'lmasa `XT_DB_DSN`.
#
# --- NEGA BU FAYL BOR --------------------------------------------------------
# README shu buyruqni beradi:
#
#     1..13 | ForEach-Object { psql $dsn -f "schema_patch_erp_$_.sql" }
#
# U ikki narsani jimgina buzadi:
#
#   1. TARTIB. `schema_patch_erp_*.sql` ni alifbo bo'yicha olsak,
#      `_10` `_2` dan OLDIN keladi. Patch 10 esa 8 ga tayanadi
#      ("rezerv: ajratilgan tovar" ombor jadvallarini talab qiladi).
#      Shuning uchun tartib RAQAM bo'yicha, matn bo'yicha emas.
#
#   2. QAYTA QO'LLASH KO'RINMAYDI. Patchlar idempotent, lekin
#      "qo'llandimi yoki yo'qmi" degan savolga javob beradigan hech
#      narsa yo'q edi. Reliz oldidan operator buni BILISHI kerak.
#
# Tender-AI da xuddi shu vazifani `migratsiya.py` bajaradi va u ancha
# boy (manifest, `--reja`, `--bootstrap`). Bu yerda 16 ta fayl bor va
# ular RAQAM bilan tartiblangan — manifest saqlashga arzimaydi. Fayl
# soni o'sib, bog'liqlik chalkashsa — o'sha yondashuvga o'tiladi.
#
# --- CHEKSUM -----------------------------------------------------------------
# Qo'llangan faylning SHA-256 i yoziladi. Fayl KEYIN tahrirlansa,
# skript TO'XTAYDI: bazadagi holat repozitoriydagi matnga mos emas va
# buni jimgina o'tkazib yuborish — eng qimmat xatolik turi.
# Yangi o'zgarish YANGI patch fayli bo'lib qo'shiladi.
#
# --- IDEMPOTENTLIK -----------------------------------------------------------
# Patchlar o'zi ham idempotent (har birining sarlavhasida yozilgan), ya'ni
# jurnal yo'qolsa ham qayta qo'llash xavfsiz. Jurnal TEZLIK uchun emas,
# KO'RINISH uchun.
# =============================================================================
set -euo pipefail

BU="$(cd "$(dirname "$0")/../.." && pwd)"       # loyiha ildizi
AMAL="--holat"
DSN=""

while [ $# -gt 0 ]; do
    case "$1" in
        --holat|--qolla) AMAL="$1"; shift ;;
        --dsn)           DSN="${2:?--dsn qiymatsiz}"; shift 2 ;;
        *) echo "Noma'lum argument: $1" >&2; exit 2 ;;
    esac
done

DSN="${DSN:-${XT_DB_DSN_OWNER:-${XT_DB_DSN:-}}}"
[ -n "$DSN" ] || { echo "XATO: DSN yo'q (--dsn yoki XT_DB_DSN_OWNER)" >&2; exit 2; }

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
psql_() { psql "$DSN" -v ON_ERROR_STOP=1 -qtA "$@"; }

# --- Jurnal jadvali ----------------------------------------------------------
# `erp` sxemasi 1-patchda tug'iladi, jurnal esa undan OLDIN kerak —
# shuning uchun sxemani shu yerda ham ta'minlaymiz. `IF NOT EXISTS`
# tufayli 1-patch bilan to'qnashmaydi.
psql_ <<'SQL' >/dev/null
CREATE SCHEMA IF NOT EXISTS erp;
CREATE TABLE IF NOT EXISTS erp.schema_migration (
    fayl        TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    qollandi_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE erp.schema_migration IS
    'Qaysi schema_patch_erp_*.sql qo''llangani. deploy/bin/migratsiya.sh yuritadi.';
SQL

# --- Fayllar RAQAM bo'yicha (yuqoridagi 1-sabab) -----------------------------
mapfile -t FAYLLAR < <(
    find "$BU" -maxdepth 1 -name 'schema_patch_erp_*.sql' -printf '%f\n' \
    | sed -E 's/^schema_patch_erp_([0-9]+)\.sql$/\1 &/' \
    | sort -n -k1,1 \
    | cut -d' ' -f2
)
[ "${#FAYLLAR[@]}" -gt 0 ] || { echo "XATO: patch fayli topilmadi: $BU" >&2; exit 1; }

KUTILMOQDA=()
for F in "${FAYLLAR[@]}"; do
    YANGI_SHA="$(sha256sum "${BU}/${F}" | cut -d' ' -f1)"
    ESKI_SHA="$(psql_ -c "SELECT sha256 FROM erp.schema_migration WHERE fayl = '${F}'")"

    if [ -z "$ESKI_SHA" ]; then
        printf '  %-28s KUTILMOQDA\n' "$F"
        KUTILMOQDA+=("$F")
    elif [ "$ESKI_SHA" = "$YANGI_SHA" ]; then
        printf '  %-28s qo`llangan\n' "$F"
    else
        printf '  %-28s CHEKSUM MOS EMAS\n' "$F"
        echo >&2
        echo "XATO: '$F' qo'llangandan KEYIN tahrirlangan." >&2
        echo "      bazada: $ESKI_SHA" >&2
        echo "      faylda: $YANGI_SHA" >&2
        echo "      O'zgarishni YANGI patch fayli qilib qo'shing." >&2
        exit 2
    fi
done

if [ "$AMAL" = "--holat" ]; then
    echo
    log "kutilmoqda: ${#KUTILMOQDA[@]} ta"
    exit 0
fi

# --- Qo'llash ----------------------------------------------------------------
if [ "${#KUTILMOQDA[@]}" -eq 0 ]; then
    echo
    log "hammasi qo'llangan — qiladigan ish yo'q"
    exit 0
fi

echo
for F in "${KUTILMOQDA[@]}"; do
    log "qo'llanmoqda: $F"
    # `ON_ERROR_STOP=1` va BITTA tranzaksiya (`--single-transaction`):
    # patch yarmida yiqilsa yarim sxema QOLMASIN.
    psql "$DSN" -v ON_ERROR_STOP=1 --single-transaction -q -f "${BU}/${F}"
    SHA="$(sha256sum "${BU}/${F}" | cut -d' ' -f1)"
    psql_ -c "INSERT INTO erp.schema_migration (fayl, sha256)
              VALUES ('${F}', '${SHA}')
              ON CONFLICT (fayl) DO UPDATE SET sha256 = EXCLUDED.sha256" >/dev/null
    log "  OK"
done

echo
log "TUGADI: ${#KUTILMOQDA[@]} ta patch qo'llandi"
