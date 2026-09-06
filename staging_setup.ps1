# =============================================================================
# STAGING MUHITINI YARATADI: alohida baza + alohida .env
#
#   .\staging_setup.ps1                 # oxirgi zaxiradan
#   .\staging_setup.ps1 -Dump backups\erp_2026-09-06.dump
#   .\staging_setup.ps1 -Yangila        # bazani QAYTA yaratadi
#
# NEGA KERAK: joylashtirish tartibida staging bosqichi bor, lekin
# staging BAZASI yo'q edi - bitta XT_DB_DSN. Ya'ni "staging'da
# sinab ko'rish" amalda ishlab chiqarish bazasida sinash bo'lardi.
#
# ENG MUHIM QOIDA: IKKI FAYL, IKKI BAZA, IKKI NOM
# ================================================
#   .env          -> xtxarid          -> ERP_MUHIT=prod
#   .env.staging  -> xtxarid_staging  -> ERP_MUHIT=staging
#
# `ERP_MUHIT` shunchaki yorliq emas: `api/muhit.py` qulfi shunga
# qaraydi va `prod` bo'lsa SINOVLARNI umuman ishga tushirmaydi.
# Ya'ni fayllar almashib ketsa ham, sinov ishlab chiqarish bazasiga
# YOZA OLMAYDI - u to'xtaydi va sababni aytadi.
#
# ZAXIRADAN NUSXA: staging haqiqiy ma'lumot bilan to'ldiriladi.
# Bo'sh bazada sinash "ishladi" degan yolg'on ishonch beradi -
# ko'chirish (migration) muammolari aynan MAVJUD ma'lumotda
# chiqadi (`schema_patch_erp_28.sql` dagi CHECK'lar shu sababdan
# ma'lumot moslangandan KEYIN qo'yiladi).
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1 BOM'siz
# .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni buzadi.
# =============================================================================
param(
    [string] $Dump,
    [string] $Baza = 'xtxarid_staging',
    [switch] $Yangila
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Find-PgTool($name) {
    $t = (Get-Command $name -ErrorAction SilentlyContinue).Source
    if ($t) { return $t }
    $c = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\$name.exe" `
        -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
    if ($c) { return $c[0].FullName }
    throw "$name topilmadi. PostgreSQL bin papkasini PATH ga qo'shing."
}

$psql = Find-PgTool 'psql'
$createdb = Find-PgTool 'createdb'
$pgRestore = Find-PgTool 'pg_restore'

# --- 1) Ishlab chiqarish DSN sini o'qiymiz -----------------------------------
$envPath = Join-Path $Root '.env'
if (-not (Test-Path $envPath)) { throw ".env topilmadi: $envPath" }
$prodDsn = ''
foreach ($line in Get-Content $envPath) {
    if ($line -match '^\s*XT_DB_DSN\s*=\s*(.+)$') { $prodDsn = $Matches[1].Trim() }
}
if (-not $prodDsn) { throw ".env ichida XT_DB_DSN yo'q." }

$prodBaza = ''
if ($prodDsn -match 'dbname=(\S+)') { $prodBaza = $Matches[1] }
if ($prodBaza -eq $Baza) {
    throw "TO'XTATILDI: staging bazasi ($Baza) ishlab chiqarish bazasi bilan BIR XIL. Boshqa nom bering (-Baza)."
}
Write-Host "[i] ishlab chiqarish bazasi: $prodBaza"
Write-Host "[i] staging bazasi:          $Baza"

# --- 2) Zaxirani topamiz -----------------------------------------------------
# NEGA ZAXIRADAN, `pg_dump | psql` quvuri bilan EMAS: quvur ishlab
# chiqarish bazasiga UZOQ so'rov qo'yadi va ish vaqtida sekinlashtiradi.
# Zaxira esa allaqachon olingan (backup_erp.ps1, kunlik jadval).
if (-not $Dump) {
    $b = Join-Path $Root 'backups'
    if (-not (Test-Path $b)) { throw "backups papkasi yo'q. Avval: .\backup_erp.ps1" }
    $oxirgi = Get-ChildItem (Join-Path $b '*.dump') -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $oxirgi) { throw "Zaxira topilmadi. Avval: .\backup_erp.ps1" }
    $Dump = $oxirgi.FullName
}
if (-not (Test-Path $Dump)) { throw "Zaxira fayli yo'q: $Dump" }
$yosh = [int]((Get-Date) - (Get-Item $Dump).LastWriteTime).TotalDays
Write-Host "[i] zaxira: $Dump ($yosh kun oldin)"
if ($yosh -gt 7) {
    Write-Warning "Zaxira $yosh kunlik. Yangi olish tavsiya etiladi: .\backup_erp.ps1"
}

# --- 3) Bazani yaratamiz -----------------------------------------------------
$bor = & $psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$Baza'" 2>$null
if ($bor -eq '1') {
    if (-not $Yangila) {
        Write-Host "[i] '$Baza' allaqachon bor. Qayta yaratish: -Yangila"
    } else {
        # TASDIQ SO'RALADI: bu bazani BUTUNLAY o'chiradi. Staging
        # bo'lsa ham, unda kimdir sinov ma'lumotini qoldirgan
        # bo'lishi mumkin.
        $j = Read-Host "'$Baza' O'CHIRILADI va qayta yaratiladi. Davom etamizmi? (ha/yo'q)"
        if ($j -ne 'ha') { Write-Host "[i] bekor qilindi."; return }
        & $psql -U postgres -c "DROP DATABASE IF EXISTS $Baza" | Out-Null
        & $createdb -U postgres $Baza
        Write-Host "[OK] '$Baza' qayta yaratildi."
    }
} else {
    & $createdb -U postgres $Baza
    Write-Host "[OK] '$Baza' yaratildi."
}

# --- 4) Zaxirani tiklaymiz ---------------------------------------------------
# `--clean --if-exists`: qayta yurgizishda toza holat.
# Chiqish kodi TEKSHIRILMAYDI: pg_restore mavjud bo'lmagan obyektni
# o'chirmoqchi bo'lganda ogohlantirish beradi va bu NORMAL.
Write-Host "[i] tiklanmoqda... (bir necha daqiqa)"
& $pgRestore -U postgres -d $Baza --clean --if-exists $Dump 2>&1 |
    Select-String -NotMatch 'does not exist|already exists' | Select-Object -First 20
$n = & $psql -U postgres -d $Baza -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='erp'"
Write-Host "[OK] tiklandi: erp sxemasida $n ta jadval"
if ([int]$n -lt 10) { throw "Tiklash to'liq bo'lmadi ($n ta jadval). Zaxirani tekshiring." }

# --- 4b) BAZANI BELGILAYMIZ ------------------------------------------------
# ENG MUHIM QADAM. Zaxira ishlab chiqarish bazasidan olingan, ya'ni
# `erp.setting` dagi `muhit` belgisi ham KO'CHDI: yangi staging bazasi
# hozir o'zini "prod" deb hisoblaydi.
#
# Bu qulfning ikkinchi qavati (`api/muhit.py` -> qulf_tekshir_baza):
# sinovlar bazadan "sen kimsan?" deb so'raydi. Belgi qayta yozilmasa,
# staging'da HECH QAYSI sinov ishlamaydi - va bu XAVFSIZ tomonga
# xato: unutilgan belgi ishni to'xtatadi, ochiq qoldirmaydi.
& $psql -U postgres -d $Baza -v ON_ERROR_STOP=1 -c @"
INSERT INTO erp.setting (key, value, updated_by)
VALUES ('muhit', 'staging', 'staging_setup.ps1')
ON CONFLICT (key) DO UPDATE
    SET value = 'staging', updated_by = 'staging_setup.ps1',
        updated_at = now();
"@ | Out-Null
$belgi = & $psql -U postgres -d $Baza -tAc "SELECT value FROM erp.setting WHERE key='muhit'"
if ($belgi.Trim() -ne 'staging') {
    throw "Baza belgilanmadi (olindi: '$belgi'). erp.setting jadvali bormi? (18-patch)"
}
Write-Host "[OK] baza belgilandi: erp.setting.muhit = staging"

# --- 5) .env.staging -----------------------------------------------------
$stagingEnv = Join-Path $Root '.env.staging'
if ((Test-Path $stagingEnv) -and -not $Yangila) {
    Write-Host "[i] .env.staging allaqachon bor - tegilmadi."
} else {
    $yangiDsn = $prodDsn -replace "dbname=$prodBaza", "dbname=$Baza"
    $satrlar = @()
    $muhitBor = $false
    foreach ($line in Get-Content $envPath) {
        if ($line -match '^\s*XT_DB_DSN\s*=') { $satrlar += "XT_DB_DSN=$yangiDsn"; continue }
        if ($line -match '^\s*ERP_MUHIT\s*=') { $satrlar += 'ERP_MUHIT=staging'; $muhitBor = $true; continue }
        $satrlar += $line
    }
    if (-not $muhitBor) {
        $satrlar += ''
        $satrlar += '# MUHIT NOMI - api/muhit.py qulfi shunga qaraydi.'
        $satrlar += '# `prod` bo''lsa sinovlar UMUMAN ishga tushmaydi.'
        $satrlar += 'ERP_MUHIT=staging'
    }
    $satrlar | Set-Content -Path $stagingEnv -Encoding utf8
    Write-Host "[OK] .env.staging yozildi (dbname=$Baza, ERP_MUHIT=staging)"
}

# --- 6) Ishlab chiqarish .env sida ERP_MUHIT bormi ---------------------------
# QULF FAQAT SHU SATR BO'LGANDA ishlaydi. Usiz staging fayli
# to'g'ri, ishlab chiqarish esa himoyasiz qoladi.
$prodMuhit = $null
foreach ($line in Get-Content $envPath) {
    if ($line -match '^\s*ERP_MUHIT\s*=\s*(.+)$') { $prodMuhit = $Matches[1].Trim() }
}
if (-not $prodMuhit) {
    Write-Warning ".env da ERP_MUHIT YO'Q - ishlab chiqarish qulfi ISHLAMAYDI."
    Write-Host "         Qo'shing:  ERP_MUHIT=prod"
} else {
    Write-Host "[i] .env -> ERP_MUHIT=$prodMuhit"
}

Write-Host ''
Write-Host 'TEKSHIRISH:'
Write-Host '  .\.venv\Scripts\python.exe -m api.muhit'
Write-Host '  (`.env` va baza BIR XIL narsani aytishi kerak)'
Write-Host ''
Write-Host 'KEYINGI QADAM (staging oynasida):'
Write-Host '  $env:XT_DB_DSN = "<.env.staging dagi DSN>"'
Write-Host '  $env:ERP_MUHIT = "staging"'
Write-Host "  psql `"`$env:XT_DB_DSN`" -v ON_ERROR_STOP=1 -f schema_patch_erp_28.sql"
Write-Host '  .\.venv\Scripts\python.exe check_setup.py'
Write-Host '  .\.venv\Scripts\python.exe _tests\erp28_http_test.py --base <staging-url> --tasdiq'
