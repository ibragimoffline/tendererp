#!/usr/bin/env bash
# =============================================================================
# Tender ERP — joylashtirishdan keyingi sog'liq tekshiruvi
# =============================================================================
#     health-check.sh <staging|production>
#
# TO'RT TEKSHIRUV va ular BOSHQA-BOSHQA narsani o'lchaydi:
#
#   1. TIRIKLIK   /health javob beryaptimi        — jarayon ko'tarildimi
#   2. BAZA       javobdagi `ok`                  — ulanish bormi
#   3. SXEMA      `schema_ready`, `clients_ready` — migratsiya qo'llandimi
#   4. INTERFEYS  `/` 200 va HTML qaytaradimi     — `dist` uzatilyaptimi
#
# Ularni bittaga qo'shish "tirik = ishlayapti" degan yolg'on berardi:
# jarayon ko'tarilgan, lekin migratsiya qo'llanmagan holat HAQIQIY va u
# faqat 3-tekshiruvda ko'rinadi. 4-si esa alohida: `frontend/dist`
# qurilmay qolsa API sog'lom bo'lib turaveradi, foydalanuvchi esa bo'sh
# sahifa ko'radi.
#
# TENDER-AI GA ULANISH TEKSHIRILADI, LEKIN TO'XTATMAYDI. ERP usiz ham
# ishlaydi (README: mavjud kartalar ochiladi, faqat cheklist va yangi
# karta olish ishlamaydi) — bu OGOHLANTIRISH, nosozlik emas.
#
# --- VAQT BYUDJETI -----------------------------------------------------------
# Takror soni EMAS, MUDDAT. "30 marta urinish" `curl` ning o'zi
# bloklanadigan bo'lsa istalgancha cho'zilardi va systemd skriptni
# o'ldirar, xulosa satri esa umuman chiqmasdi — ya'ni nima yiqilgani
# noma'lum qolardi. Byudjet birlikdagi `TimeoutStartSec` dan KICHIK.
# =============================================================================
set -uo pipefail

MUHIT="${1:?foydalanish: health-check.sh <staging|production>}"
ENVFILE="${TENDERERP_ENVFILE:-/etc/tendererp/${MUHIT}.env}"
[ -f "$ENVFILE" ] || { echo "muhit fayli yo'q: $ENVFILE"; exit 2; }

set -a
# shellcheck disable=SC1090
. "$ENVFILE"
set +a

PORT="${API_PORT:-8100}"
BASE="http://127.0.0.1:${PORT}"
KUTISH="${HEALTH_WAIT_SEC:-45}"

BU="$(cd "$(dirname "$0")" && pwd)"
PY="${BU}/../../.venv/bin/python"       # reliz ichidagi muhit

nosoz=0
ayt() { printf '  %-10s %s\n' "$1" "$2"; }

# --- 1) TIRIKLIK — muddat bilan ----------------------------------------------
MUDDAT=$(( $(date +%s) + KUTISH ))
JAVOB=""
while [ "$(date +%s)" -lt "$MUDDAT" ]; do
    JAVOB="$(curl -fsS --max-time 5 "${BASE}/health" 2>/dev/null)" && break
    JAVOB=""
    sleep 2
done

if [ -z "$JAVOB" ]; then
    ayt "TIRIKLIK" "YIQILDI — ${BASE}/health ${KUTISH}s ichida javob bermadi"
    echo
    echo "  Jurnal:  journalctl -u tendererp-api@${MUHIT} -n 50 --no-pager" >&2
    exit 1
fi
ayt "TIRIKLIK" "OK"

# --- 2-3) BAZA va SXEMA -------------------------------------------------------
# JSON `python` bilan o'qiladi, `grep` bilan emas: `"ok":true` ni matn
# sifatida qidirish `"clients_ready":true` bilan ham mos kelib ketardi.
maydon() {
    printf '%s' "$JAVOB" | "$PY" -c \
        "import json,sys; print(json.load(sys.stdin).get('$1'))" 2>/dev/null
}

if [ "$(maydon ok)" = "True" ]; then
    ayt "BAZA" "OK"
else
    ayt "BAZA" "YIQILDI — ilova bazaga ulana olmadi"
    nosoz=1
fi

SXEMA_OK=1
for M in schema_ready clients_ready; do
    [ "$(maydon "$M")" = "True" ] || { SXEMA_OK=0; ayt "SXEMA" "YIQILDI — $M = false"; }
done
if [ "$SXEMA_OK" = 1 ]; then
    ayt "SXEMA" "OK"
else
    echo "            migratsiya qo'llanmagan? deploy/bin/migratsiya.sh --holat" >&2
    nosoz=1
fi

# --- 4) INTERFEYS -------------------------------------------------------------
# `dist` yo'q bo'lsa `api/main.py` interfeysni JIM o'tkazib yuboradi
# (`_mount_ui`) — ya'ni bu holat XATOSIZ ko'rinadi. Shuning uchun
# alohida tekshiriladi.
KOD="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/" 2>/dev/null)"
# Apostrof `${KOD:-...}` ning ICHIDA yozilmaydi: qo'shtirnoq ostidagi
# `:-` qiymatida bash uni QO'SHTIRNOQ deb o'qiydi va fayl oxirigacha
# "yopilmagan qator" bo'lib ketadi (`bash -n` shuni ko'rsatgan edi).
[ -n "$KOD" ] || KOD="javob yo'q"
if [ "$KOD" = "200" ]; then
    ayt "INTERFEYS" "OK"
else
    ayt "INTERFEYS" "YIQILDI — / -> ${KOD} (frontend/dist qurilmadimi?)"
    nosoz=1
fi

# --- 5) TENDER-AI — faqat OGOHLANTIRISH --------------------------------------
TAI="$(maydon tender_ai)"
if [ -n "$TAI" ] && [ "$TAI" != "None" ]; then
    if curl -fsS -o /dev/null --max-time 5 "${TAI}/health" 2>/dev/null; then
        ayt "TENDER-AI" "OK ($TAI)"
    else
        ayt "TENDER-AI" "javob yo'q ($TAI) — cheklist va yangi karta ishlamaydi"
    fi
fi

echo
if [ "$nosoz" -ne 0 ]; then
    echo "  XULOSA: NOSOZ" >&2
    exit 1
fi
echo "  XULOSA: SOG'LOM"
