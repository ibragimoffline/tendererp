#!/usr/bin/env bash
# =============================================================================
# Tender ERP — oldingi relizga QAYTISH
# =============================================================================
#     rollback.sh --royxat <muhit>          # relizlar ro'yxati
#     rollback.sh <muhit>                   # bir qadam orqaga
#     rollback.sh <muhit> <reliz-nomi>      # aniq relizga
#
# QAYTISH BITTA AMAL: `ln -sfn`. Kod qayta qurilmaydi, `npm` va `pip`
# chaqirilmaydi — ular allaqachon o'sha relizda turibdi. Shuning uchun
# qaytish soniyalar ichida bo'ladi va TARMOQQA BOG'LIQ EMAS.
#
# MIGRATSIYA QAYTARILMAYDI va bu ATAYLAB. Sxemani orqaga qaytarish
# ma'lumot yo'qotadi; kod esa eski sxemada emas, YANGI sxemada ishlashi
# kerak. Shuning uchun migratsiyalar oldinga mos bo'lishi shart —
# ustunni o'chirish yangi patchda, kod olib tashlangandan KEYIN.
# =============================================================================
set -euo pipefail

if [ "${1:-}" = "--royxat" ]; then
    MUHIT="${2:?foydalanish: rollback.sh --royxat <muhit>}"
    ILDIZ="${TENDERERP_ILDIZ:-/opt/tendererp/${MUHIT}}"
    JORIY="$(readlink -f "${ILDIZ}/current" 2>/dev/null || echo '-')"
    echo "Relizlar (${ILDIZ}/releases), yangisi birinchi:"
    ( cd "${ILDIZ}/releases" && ls -1dt */ 2>/dev/null ) | while read -r R; do
        R="${R%/}"
        if [ "$(readlink -f "${ILDIZ}/releases/${R}")" = "$JORIY" ]; then
            echo "  * ${R}   <- JORIY"
        else
            echo "    ${R}"
        fi
    done
    exit 0
fi

MUHIT="${1:?foydalanish: rollback.sh <staging|production> [reliz]}"
NISHON="${2:-}"
case "$MUHIT" in staging|production) ;; *) echo "Noma'lum muhit"; exit 2 ;; esac

ILDIZ="${TENDERERP_ILDIZ:-/opt/tendererp/${MUHIT}}"
RELIZLAR="${ILDIZ}/releases"
JORIY="${ILDIZ}/current"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
xato() { printf '[%s] XATO: %s\n' "$(date '+%F %T')" "$*" >&2; exit 1; }

HOZIR="$(readlink -f "$JORIY" 2>/dev/null || true)"

if [ -z "$NISHON" ]; then
    # Bir qadam orqaga: vaqt bo'yicha JORIY dan keyingisi.
    NISHON="$(cd "$RELIZLAR" && ls -1dt */ 2>/dev/null | sed 's#/$##' \
              | awk -v joriy="$(basename "${HOZIR:-yoq}")" \
                    'topildi { print; exit } $0 == joriy { topildi = 1 }')"
    [ -n "$NISHON" ] || xato "qaytadigan eski reliz yo'q. Ko'rish: $0 --royxat $MUHIT"
fi

YOL="${RELIZLAR}/${NISHON}"
[ -d "$YOL" ] || xato "bunday reliz yo'q: $YOL"
[ -x "${YOL}/.venv/bin/uvicorn" ] || xato "reliz to'liq emas (.venv yo'q): $YOL"

log "qaytarilmoqda: $(basename "${HOZIR:-yoq}") -> ${NISHON}"
ln -sfn "$YOL" "$JORIY"
sudo systemctl restart "tendererp-api@${MUHIT}"

# TASDIQ BEKOR QILINADI: `.verified` "shu ref staging da tekshirilgan"
# degani. Qaytgandan keyin u endi HAQIQAT EMAS — qoldirilsa, buzuq ref
# ishlab chiqarishga o'tib ketishi mumkin edi.
if [ "$MUHIT" = "staging" ]; then
    rm -f "${ILDIZ}/.verified"
    log "staging tasdig'i bekor qilindi"
fi

if "${YOL}/deploy/bin/health-check.sh" "$MUHIT"; then
    log "TUGADI: ${MUHIT} <- ${NISHON}"
else
    xato "qaytarildi, LEKIN sog'liq tekshiruvi o'tmadi — qo'lda qarang"
fi
