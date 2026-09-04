#!/usr/bin/env bash
# =============================================================================
# Tender ERP — serverni BIR MARTA tayyorlash
# =============================================================================
#     sudo bootstrap.sh <staging|production>
#
# Bu skript SIR YARATMAYDI va SIR SO'RAMAYDI. U faqat katalog, rol va
# xizmat fayllarini joyiga qo'yadi. Sirlarni operator o'zi
# `/etc/tendererp/<muhit>.env` ga yozadi (namuna: deploy/env/).
#
# QAYTA YURGIZSA BO'LADI (idempotent).
#
# TENDER-AI NING `deploy/bin/bootstrap.sh` I BILAN BIR XIL SHAKLDA —
# ataylab. Ikkala loyiha bitta serverda turadi va operator ikkalasini
# bir xil biladigan bo'lsin.
#
# BAZA BU YERDA YARATILMAYDI: ERP tender-ai bilan BITTA bazada yashaydi
# (`erp` sxemasi). Bazani va rollarni tender-ai o'rnatmasi tayyorlaydi.
# =============================================================================
set -euo pipefail

MUHIT="${1:?foydalanish: bootstrap.sh <staging|production>}"
case "$MUHIT" in staging|production) ;; *) echo "Noma'lum muhit"; exit 2 ;; esac

[ "$(id -u)" = "0" ] || { echo "root kerak: sudo $0 $MUHIT"; exit 1; }

BU="$(cd "$(dirname "$0")/.." && pwd)"
log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

# --- 1) Xizmat foydalanuvchisi (kirish YO'Q) ---------------------------------
if ! id tendererp >/dev/null 2>&1; then
    useradd --system --home-dir /opt/tendererp --shell /usr/sbin/nologin tendererp
    log "tendererp foydalanuvchisi yaratildi (nologin)"
fi

# --- 2) Kataloglar -----------------------------------------------------------
# `var/logs` — ERP jurnali shu yerga tushadi. Sabab `tendererp-api@.service`
# dagi izohda: jurnal yo'li kodda qotirilgan va reliz katalogi yozishdan
# yopilgan, shuning uchun `<reliz>/logs` shu yerga havola qilinadi.
install -d -o tendererp -g tendererp -m 0755 \
    "/opt/tendererp/${MUHIT}/releases" \
    "/opt/tendererp/${MUHIT}/var/logs" \
    "/opt/tendererp/${MUHIT}/var/cache"
install -d -o root -g tendererp -m 0750 /etc/tendererp
log "kataloglar tayyor"

# --- 3) Muhit fayli NAMUNASI (mavjudini USTIGA YOZMAYDI) --------------------
if [ ! -f "/etc/tendererp/${MUHIT}.env" ]; then
    install -o root -g tendererp -m 0640 \
        "${BU}/env/${MUHIT}.env.example" "/etc/tendererp/${MUHIT}.env"
    log "MUHIM: /etc/tendererp/${MUHIT}.env yaratildi — QIYMATLARNI TO'LDIRING"
else
    log "/etc/tendererp/${MUHIT}.env allaqachon bor — tegilmadi"
fi

# --- 4) systemd birliklari ---------------------------------------------------
install -m 0644 "${BU}"/systemd/*.service "${BU}"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
log "systemd birliklari o'rnatildi"

# --- 5) Sudo: joylashtirish skripti xizmatni qayta yurgiza olsin ------------
# ANIQ ro'yxat — `NOPASSWD: ALL` emas.
#
# YO'L IKKI MARTA: `/bin/systemctl` va `/usr/bin/systemctl`. Ubuntu 24.04+
# birlashtirilgan `/usr` ishlatadi (`/bin` -> `/usr/bin` havolasi), `sudo`
# esa buyruq yo'lini havola bo'yicha OCHMAYDI — u satrni satr bilan
# solishtiradi. Bitta yo'l yozilsa, boshqa distributivda qoida jimgina
# mos kelmay qolardi va joylashtirish "Xizmatlar" bosqichida parol
# so'rab to'xtardi.
{
    for YOL in /bin/systemctl /usr/bin/systemctl; do
        for M in staging production; do
            echo "tendererp ALL=(root) NOPASSWD: ${YOL} restart tendererp-api@${M}"
            echo "tendererp ALL=(root) NOPASSWD: ${YOL} enable --now tendererp-remind@${M}.timer"
        done
    done
} > /etc/sudoers.d/tendererp
chmod 0440 /etc/sudoers.d/tendererp
visudo -c -f /etc/sudoers.d/tendererp >/dev/null
log "sudo qoidalari (aniq ro'yxat)"

# --- 6) Bare repozitoriya ----------------------------------------------------
# `deploy.sh` kodni SHU YERDAN oladi (`git archive`). Manba GitHub bo'lsa,
# uni ko'zgu qilib klon qiling:
#     git clone --mirror https://github.com/<egasi>/tendererp.git \
#         /opt/tendererp/repo.git
if [ ! -d /opt/tendererp/repo.git ]; then
    git init --bare /opt/tendererp/repo.git
    chown -R tendererp:tendererp /opt/tendererp/repo.git
    log "bare repo: /opt/tendererp/repo.git (push shu yerga)"
fi

echo
log "TAYYOR. Keyingi qadamlar:"
echo "  1. /etc/tendererp/${MUHIT}.env ni TO'LDIRING (XT_DB_DSN, ERP_SERVICE_KEY, ...)"
echo "  2. Kodni push qiling va: deploy/bin/deploy.sh ${MUHIT} <ref>"
