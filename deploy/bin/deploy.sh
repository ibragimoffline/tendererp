#!/usr/bin/env bash
# =============================================================================
# Tender ERP — joylashtirish (STAGING BIRINCHI)
# =============================================================================
#     deploy.sh staging    <git-ref>
#     deploy.sh production <git-ref>
#
# ISHLAB CHIQARISHGA TO'G'RIDAN-TO'G'RI JOYLASHTIRIB BO'LMAYDI: shu ref
# STAGING da tekshirilgan bo'lishi SHART. Tasdiq `.verified` faylida va
# uni shu skriptning O'ZI yozadi — staging joylashtiruvi sog'liq
# tekshiruvidan o'tgach.
#
# NEGA SIMVOLIK HAVOLA (`current`): orqaga qaytarish BITTA atomar amal
# (`ln -sfn`), ya'ni "qaytardim, lekin yarmi eski yarmi yangi" holati
# yuzaga kelmaydi.
#
# BU SKRIPTDA SIR YO'Q. Sirlar `/etc/tendererp/<muhit>.env` da va u
# repozitoriyaga tushmaydi.
#
# TENDER-AI DAGI `deploy/bin/deploy.sh` NING TUZILISHI. Farqlari uchtta
# va har biri o'z joyida izohlangan: (a) frontend backend ichidan
# uzatiladi, (b) migratsiya `migratsiya.sh` bilan, (c) jurnal havolasi.
# =============================================================================
set -euo pipefail

MUHIT="${1:?foydalanish: deploy.sh <staging|production> <git-ref>}"
REF="${2:?git ref (tag yoki commit) kerak}"

case "$MUHIT" in
    staging|production) ;;
    *) echo "Noma'lum muhit: $MUHIT"; exit 2 ;;
esac

# Yo'llar almashtirilishi mumkin — skriptni serverdan tashqarida
# (mashq yoki sinovda) yurgiza olish uchun. Standart qiymat o'zgarmaydi.
ILDIZ="${TENDERERP_ILDIZ:-/opt/tendererp/${MUHIT}}"
RELIZLAR="${ILDIZ}/releases"
JORIY="${ILDIZ}/current"
ENVFILE="${TENDERERP_ENVFILE:-/etc/tendererp/${MUHIT}.env}"
REPO="${TENDERERP_REPO:-/opt/tendererp/repo.git}"

log()  { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
xato_izoh() { printf '[%s] %s' "$(date '+%F %T')" "$*" >&2; echo >&2; }
xato() { printf '[%s] XATO: %s\n' "$(date '+%F %T')" "$*" >&2; exit 1; }

[ -f "$ENVFILE" ] || xato "muhit fayli yo'q: $ENVFILE"

# --- 1) ISHLAB CHIQARISH UCHUN STAGING TASDIQI SHART -------------------------
if [ "$MUHIT" = "production" ]; then
    TASDIQ="${TENDERERP_STAGING_ILDIZ:-/opt/tendererp/staging}/.verified"
    [ -f "$TASDIQ" ] || xato "staging tasdig'i yo'q ($TASDIQ). Avval: deploy.sh staging $REF"
    TASDIQLANGAN="$(cat "$TASDIQ")"
    if [ "$TASDIQLANGAN" != "$REF" ]; then
        xato "staging da BOSHQA ref tekshirilgan: '$TASDIQLANGAN' != '$REF'"
    fi
    log "staging tasdig'i topildi: $REF"
fi

# --- 2) Yangi reliz katalogi -------------------------------------------------
STAMP="$(date +%Y%m%d-%H%M%S)"
TOZA_REF="$(printf '%s' "$REF" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-24)"
YANGI="${RELIZLAR}/${STAMP}-${TOZA_REF}"
mkdir -p "$YANGI" "${ILDIZ}/var/logs" "${ILDIZ}/var/cache"
log "reliz: $YANGI"

# YIQILSA YARIM RELIZ QOLMASIN. Aks holda `rollback.sh` ro'yxatida eng
# yangi reliz bo'lib turardi va tiklanayotgan operatorga aynan eng
# yaroqsiz nishon ko'rsatilardi.
#
# `trap` faqat ALMASHTIRISHGACHA amal qiladi: `current` yangi relizga
# o'tgach uni o'chirish tirik xizmatni o'ldirardi.
TOZALA="$YANGI"
tozalash() {
    kod=$?
    if [ "$kod" -ne 0 ] && [ -n "$TOZALA" ] && [ -d "$TOZALA" ]; then
        xato_izoh "yiqildi -> yarim reliz olib tashlanmoqda: $TOZALA"
        rm -rf "$TOZALA"
    fi
    exit "$kod"
}
trap tozalash EXIT

git --git-dir="$REPO" archive "$REF" | tar -x -C "$YANGI"

# --- 3) Python muhiti --------------------------------------------------------
log "python muhiti quriladi"
python3 -m venv "${YANGI}/.venv"
"${YANGI}/.venv/bin/pip" install --quiet --upgrade pip
"${YANGI}/.venv/bin/pip" install --quiet -r "${YANGI}/requirements.txt"

# --- 4) MUHIT FAYLI O'QILADI -------------------------------------------------
# QURILMADAN OLDIN: frontend qurilmasi ham muhit qiymatlariga muhtoj.
set -a
# shellcheck disable=SC1090
. "$ENVFILE"
set +a

# --- 5) Jurnal katalogi — HAVOLA ---------------------------------------------
# `api/main.py` jurnalni `<loyiha>/logs/erp.log` ga yozadi va bu yo'l
# KODDA QOTIRILGAN (sozlanmaydi). Reliz katalogi esa systemd birligida
# yozishdan yopilgan (`ProtectSystem=strict`, `ReadWritePaths=.../var`).
#
# Havola ikkalasini yarashtiradi: ilova o'zi kutgan joyga yozadi, yozuv
# esa aslida `var/logs` ga tushadi. Yon foyda: jurnal RELIZDAN TASHQARIDA
# qoladi, ya'ni yangi joylashtiruv eski jurnalni yo'qotmaydi.
ln -sfn "${ILDIZ}/var/logs" "${YANGI}/logs"
log "logs -> ${ILDIZ}/var/logs"

# --- 6) Frontend QURILADI (dev-server ISHLATILMAYDI) -------------------------
# Vite dev-serveri qayta yig'ish uchun, ishlatish uchun emas — u
# 0.0.0.0 ga bog'lanadi. Joylashtirishda faqat statik qurilma.
#
# `.env.production` SHU YERDA YOZILADI: reliz `git archive` bilan
# yasaladi va `frontend/.env` kuzatilmagan fayl — u relizga TUSHMAYDI.
#
# BU FAYLDA SIR YO'Q: `VITE_*` qiymatlari ta'rifi bo'yicha qurilmaga
# tushadi, ya'ni ular OMMAVIY.
log "frontend sozlamasi yoziladi"
cat > "${YANGI}/frontend/.env.production" <<EOF
VITE_API_BASE=${VITE_API_BASE:-/api}
EOF

log "frontend quriladi"
( cd "${YANGI}/frontend" && npm ci --silent && npm run build )
[ -d "${YANGI}/frontend/dist" ] || xato "frontend/dist yaratilmadi"

# QURILMA TEKSHIRUVI — mahalliy manzil singib qolmaganiga ISHONMAYMIZ,
# QARAYMIZ. `VITE_API_BASE` nisbiy (`/api`) bo'lishi kerak; qotirilgan
# `localhost` ommaviy sahifada ishlamaydi.
if grep -rqE 'localhost|127\.0\.0\.1|0\.0\.0\.0' "${YANGI}/frontend/dist/assets"; then
    grep -roE 'localhost:[0-9]*|127\.0\.0\.1:[0-9]*' "${YANGI}/frontend/dist/assets" \
        | sort -u | head -20 >&2
    xato "qurilmada MAHALLIY manzil bor (yuqorida) — ommaviy sahifada ishlamaydi"
fi
log "qurilma toza: mahalliy manzil yo'q"

# --- 7) MIGRATSIYA — EGASI roli bilan ---------------------------------------
# Ilova roli (erp_service) da DDL huquqi ataylab yo'q.
: "${XT_DB_DSN_OWNER:?migratsiya uchun XT_DB_DSN_OWNER kerak (muhit faylida)}"
log "migratsiya holati"
"${YANGI}/deploy/bin/migratsiya.sh" --holat --dsn "$XT_DB_DSN_OWNER" || true
log "migratsiya qo'llanadi"
"${YANGI}/deploy/bin/migratsiya.sh" --qolla --dsn "$XT_DB_DSN_OWNER"

# --- 8) ALMASHTIRISH (atomar) ------------------------------------------------
ESKI="$(readlink -f "$JORIY" 2>/dev/null || true)"
ln -sfn "$YANGI" "$JORIY"
# ALMASHTIRILDI: bundan keyin reliz TIRIK, o'chirib bo'lmaydi. Keyingi
# qadamlar yiqilsa 10-bo'lim ORQAGA QAYTARADI — bu boshqa va TO'G'RI
# mexanizm.
TOZALA=""
log "current -> $YANGI"

# --- 9) Xizmatlar ------------------------------------------------------------
sudo systemctl restart "tendererp-api@${MUHIT}"
sudo systemctl enable --now "tendererp-remind@${MUHIT}.timer" >/dev/null

# --- 10) SOG'LIQ TEKSHIRUVI — o'tmasa AVTOMATIK QAYTARILADI ------------------
if ! "${YANGI}/deploy/bin/health-check.sh" "$MUHIT"; then
    log "sog'liq tekshiruvi O'TMADI — orqaga qaytarilmoqda"
    if [ -n "$ESKI" ] && [ -d "$ESKI" ]; then
        ln -sfn "$ESKI" "$JORIY"
        sudo systemctl restart "tendererp-api@${MUHIT}"
        xato "qaytarildi -> $ESKI"
    fi
    xato "qaytariladigan eski reliz yo'q"
fi

# --- 11) STAGING muvaffaqiyatli -> TASDIQ yoziladi ---------------------------
if [ "$MUHIT" = "staging" ]; then
    printf '%s' "$REF" > "${ILDIZ}/.verified"
    log "staging tasdig'i yozildi: $REF"
fi

# --- 12) Eski relizlar (oxirgi 5 tasi qoladi) -------------------------------
( cd "$RELIZLAR" && ls -1dt */ 2>/dev/null | tail -n +6 | xargs -r rm -rf )

log "TUGADI: ${MUHIT} <- ${REF}"
