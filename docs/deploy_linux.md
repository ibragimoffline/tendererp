# Joylashtirish (Linux) — staging birinchi

**Maqsad:** ishlab chiqarishga **faqat staging'dan o'tgan** kod tushsin.

Windows dagi `run_erp.ps1` / `register_erp_task.ps1` **o'z joyida qoladi** —
u ishlab chiqish uchun. Bu hujjat SERVER haqida.

---

## 1. Arxitektura — eng kichik saqlab turiladigan shakl

```
            ┌──────────────────────────────────────────┐
            │  uvicorn 127.0.0.1:8100                  │
            │  tendererp-api@production                │
            │  ├─ /api/*      -> ERP backendi          │
            │  └─ /           -> frontend/dist          │
            │  Restart=always                          │
            └───────────────┬──────────────────────────┘
                            │
      ┌─────────────────────┴───────────┐   ┌────────────────────────┐
      │ PostgreSQL — TENDER-AI BILAN    │   │ systemd timer          │
      │ BITTA baza, `erp` sxemasi       │   │  remind@  kuniga 08:30 │
      │ rol: erp_service (DDL yo'q)     │   └────────────────────────┘
      └─────────────────────────────────┘
```

### Nega shunday

| Qaror | Sabab |
|---|---|
| **systemd**, Docker emas | Tender-AI da ham shunday. Bitta serverda ikki xil ish uslubi bo'lsa, operator ikkalasini ham yarim biladi. |
| **Bitta port**, teskari proksisiz | `api/main.py` `frontend/dist` ni o'zi uzatadi va `/api` prefiksini o'zi kesadi. Bu loyihaning ongli qarori — bitta build ikkala rejimda ham ishlaydi. |
| **Shablon birlik** (`@`) | Staging va production uchun ikkita deyarli bir xil fayl — ular ajralib ketishining eng qisqa yo'li. |
| **`current` simvolik havolasi** | Orqaga qaytarish bitta atomar amal — "yarmi eski, yarmi yangi" holati yuzaga kelmaydi. |
| **Zaxira nusxa BU YERDA YO'Q** | Baza tender-ai bilan bitta. Uni `tenderai-backup@` timeri oladi va `erp.*` ham o'sha dump ichida. Ikkinchi zaxira bir xil ma'lumotni ikki marta olardi. |

---

## 2. Bir marta: serverni tayyorlash

**Talab:** baza va rollar allaqachon bor (tender-ai o'rnatmasi tayyorlaydi).

```bash
sudo deploy/bin/bootstrap.sh staging
sudo deploy/bin/bootstrap.sh production
```

`bootstrap.sh` **sir yaratmaydi va so'ramaydi**. U kataloglarni, `tendererp`
xizmat foydalanuvchisini, systemd birliklarini va aniq sudo qoidalarini
qo'yadi, muhit faylini esa namunadan nusxalaydi (`0640`, `root:tendererp`).

Kod manbasi — bare repozitoriya. GitHub dan olinadigan bo'lsa, ko'zgu qiling:

```bash
sudo -u tendererp git clone --mirror \
    https://github.com/<egasi>/tendererp.git /opt/tendererp/repo.git
```

---

## 3. Sirlar

**Repozitoriyaga hech qachon tushmaydi.** `.gitignore` da `deploy/env/*.env`
chetlatilgan, faqat `*.env.example` kuzatiladi.

```bash
sudo -e /etc/tendererp/staging.env
```

**Majburiy:** `XT_DB_DSN`, `XT_DB_DSN_OWNER`, `ERP_SERVICE_KEY`.

`ERP_SERVICE_KEY` **ikkala loyihada bir xil** bo'lishi shart — aks holda ERP
tender-ai ga kira olmaydi (403). Yaratish:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 4. Baza

ERP **o'z bazasini yaratmaydi**. U tender-ai bilan bitta bazada, `erp`
sxemasida yashaydi va `public.*` ga faqat o'qish uchun tegadi.

Sxema patchlari `deploy/bin/migratsiya.sh` bilan qo'llanadi — `deploy.sh`
uni o'zi chaqiradi, lekin qo'lda ham ishlatiladi:

```bash
deploy/bin/migratsiya.sh --holat    # nima qo'llangan, nima yo'q
deploy/bin/migratsiya.sh --qolla
```

U ikki narsani ta'minlaydi:

- **tartib RAQAM bo'yicha** — alifboda `_10` `_2` dan oldin keladi va
  patch 10 patch 8 ga tayanadi;
- **cheksum** — qo'llangan fayl keyin tahrirlansa, skript to'xtaydi.
  O'zgarish yangi patch fayli bo'lib qo'shiladi.

---

## 5. Joylashtirish

```bash
# 1) STAGING — har doim birinchi
deploy/bin/deploy.sh staging main

# 2) Tekshiring
journalctl -u tendererp-api@staging -f
systemctl list-timers 'tendererp-*'

# 3) PRODUCTION — faqat AYNAN SHU ref staging'da o'tgan bo'lsa
deploy/bin/deploy.sh production main
```

Production darvozasi `deploy.sh` ning o'zida: `/opt/tendererp/staging/.verified`
faylidagi ref bilan solishtiriladi va u faylni staging joylashtiruvi
**sog'liq tekshiruvidan o'tgach** yozadi.

Har joylashtiruv oxirida `health-check.sh` yuriladi. O'tmasa — **avtomatik
orqaga qaytariladi**.

---

## 6. Orqaga qaytarish

```bash
deploy/bin/rollback.sh --royxat production
deploy/bin/rollback.sh production                    # bir qadam orqaga
deploy/bin/rollback.sh production 20260904-201500-main
```

**Migratsiya qaytarilmaydi** va bu ataylab: sxemani orqaga qaytarish
ma'lumot yo'qotadi. Shuning uchun migratsiyalar oldinga mos bo'lishi shart —
ustunni o'chirish yangi patchda, kod olib tashlangandan **keyin**.

---

## 7. Birinchi hodim hisobi

Hodimlar ERP niki (`erp.app_user`) va birinchi hisob **shu yerda**
yaratiladi:

```bash
cd /opt/tendererp/production/current
sudo -u tendererp .venv/bin/python create_user.py admin "Bosh administrator" --role admin
```

---

## 8. Kundalik buyruqlar

```bash
systemctl status tendererp-api@production
journalctl -u tendererp-api@production -n 100 --no-pager
systemctl list-timers 'tendererp-*'

# Eslatmani sinash (yubormaydi)
cd /opt/tendererp/production/current
sudo -u tendererp .venv/bin/python -m api.erp.remind --dry-run
```

Ilova jurnali `journalctl` dan tashqari faylda ham:
`/opt/tendererp/<muhit>/var/logs/erp.log` (aylanuvchi, 7 ta fayl).
