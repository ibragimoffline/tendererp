# =============================================================================
# ERP zaxira nusxasi - FAQAT `erp` sxemasi.
#
#   .\backup_erp.ps1                 # zaxira olish
#   .\backup_erp.ps1 -DryRun         # nima bo'lishini ko'rsatadi, olmaydi
#   .\backup_erp.ps1 -Keep 30        # oxirgi 30 tasini saqlab qoladi
#   .\backup_erp.ps1 -Out D:\backup  # boshqa papkaga
#
# NEGA FAQAT `erp`: `public.*` - tender-ai niki va uning zaxirasi o'sha
# loyihaning ishi. Ikkalasini bitta faylga solsak, ERP ni tiklash uchun
# tender-ai ni ham tiklashga majbur bo'lardik.
#
# ERP MUSTAQIL TIKLANADI: `erp.opportunity` tenderga faqat RAQAM bilan
# bog'langan (FK yo'q, snapshot ichida) - ya'ni bu nusxa o'zi yetarli.
# Tender-AI bo'lmasa cheklist va yangi karta olish ishlamaydi, xolos.
#
# FORMAT: `-Fc` (custom). `.sql` matnidan farqi - `pg_restore` bilan
# tanlab tiklash mumkin (bitta jadval, faqat ma'lumot va h.k.) va u
# siqilgan bo'ladi.
#
# TIKLASH:
#   pg_restore -d xtxarid --clean --if-exists -n erp fayl.dump
# DIQQAT: `--clean` mavjud `erp` sxemasini O'CHIRIB tiklaydi. Avval
# hozirgi holatning nusxasini oling.
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1
# BOM'siz .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni
# buzadi.
# =============================================================================
param(
    [string] $Out = '',
    [int]    $Keep = 14,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
if (-not $Out) { $Out = Join-Path $Root 'backups' }

# --- 1. DSN ni .env dan olamiz -----------------------------------------------
# Bitta manba: ilova ham shu qiymatdan foydalanadi. Skriptga qo'lda
# yozib qo'yilsa, ular vaqt o'tib ajralib ketardi.
$EnvFile = Join-Path $Root '.env'
if (-not (Test-Path $EnvFile)) {
    Write-Host "XATO: .env topilmadi: $EnvFile" -ForegroundColor Red
    exit 1
}
$dsn = ''
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*XT_DB_DSN\s*=\s*(.+?)\s*$') { $dsn = $Matches[1] }
}
if (-not $dsn) {
    Write-Host "XATO: .env da XT_DB_DSN yo'q" -ForegroundColor Red
    exit 1
}

# --- 2. pg_dump ni topamiz ---------------------------------------------------
# PATH da bo'lmasligi mumkin (Windows'da odatiy hol), shuning uchun
# standart o'rnatish papkasiga ham qaraymiz.
$pgDump = (Get-Command pg_dump -ErrorAction SilentlyContinue).Source
if (-not $pgDump) {
    $cand = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_dump.exe' `
        -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    if ($cand) { $pgDump = $cand[0].FullName }
}
if (-not $pgDump) {
    Write-Host "XATO: pg_dump topilmadi. PostgreSQL o'rnatilganmi?" -ForegroundColor Red
    Write-Host "      PATH ga qo'shing yoki C:\Program Files\PostgreSQL\<versiya>\bin" -ForegroundColor Yellow
    exit 1
}

# --- 3. Fayl nomi ------------------------------------------------------------
# Nomda SANA va VAQT: bir kunda bir necha marta olish mumkin va ular
# bir-birini bosib ketmasligi kerak.
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'
$file = Join-Path $Out "erp_$stamp.dump"

Write-Host "Zaxira: erp sxemasi" -ForegroundColor Cyan
Write-Host "  pg_dump : $pgDump"
Write-Host "  fayl    : $file"
Write-Host "  saqlash : oxirgi $Keep ta"

if ($DryRun) {
    Write-Host ""
    Write-Host "DryRun - hech narsa bajarilmadi." -ForegroundColor Yellow
    $old = @(Get-ChildItem (Join-Path $Out 'erp_*.dump') -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep)
    if ($old.Count) {
        Write-Host "O'chiriladigan eski nusxalar: $($old.Count) ta"
        $old | ForEach-Object { Write-Host "  $($_.Name)" }
    }
    exit 0
}

if (-not (Test-Path $Out)) { New-Item -ItemType Directory -Path $Out | Out-Null }

# --- 4. Zaxira ---------------------------------------------------------------
# `-n erp` - faqat bizning sxema. `--no-owner` - boshqa serverga
# tiklaganda egasi mos kelmasligi muammo qilmasin.
& $pgDump --dbname=$dsn -n erp -Fc --no-owner --file=$file
if ($LASTEXITCODE -ne 0) {
    Write-Host "XATO: pg_dump $LASTEXITCODE kodi bilan tugadi" -ForegroundColor Red
    if (Test-Path $file) { Remove-Item $file }   # yarim fayl qolmasin
    exit 1
}

# --- 5. Natijani TEKSHIRAMIZ -------------------------------------------------
# Bo'sh yoki juda kichik fayl - bu ham nosozlik. "Zaxira olindi" deb
# yozib qo'yib, aslida bo'sh fayl qoldirish eng yomon holat: nosozlik
# faqat tiklash paytida ma'lum bo'lardi.
$size = (Get-Item $file).Length
if ($size -lt 1024) {
    Write-Host "XATO: fayl juda kichik ($size bayt) - zaxira olinmadi" -ForegroundColor Red
    exit 1
}
Write-Host ("  hajmi   : {0:N0} KB" -f ($size / 1KB)) -ForegroundColor Green

# --- 6. Eskilarini olib tashlaymiz -------------------------------------------
$old = @(Get-ChildItem (Join-Path $Out 'erp_*.dump') |
         Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep)
if ($old.Count) {
    $old | Remove-Item -Force
    Write-Host "  eski nusxalar o'chirildi: $($old.Count) ta"
}

Write-Host "Tayyor." -ForegroundColor Green
