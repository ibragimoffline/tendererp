# =============================================================================
# DEPLOY — muhit NOMI bilan, darvozadan o'tib.
#
#   .\deploy.ps1 -Muhit staging
#   .\deploy.ps1 -Muhit prod
#   .\deploy.ps1 -Muhit staging -Patch schema_patch_erp_28.sql
#   .\deploy.ps1 -Muhit prod -Tekshir        # faqat darvozalar, o'zgarishsiz
#
# NEGA SKRIPT KERAK: darvoza (`check_setup.py --kutilgan`) allaqachon bor,
# lekin uni OPERATOR qo'lda yozardi. Ya'ni staging buyrug'ini ishlab
# chiqarish oynasiga nusxalash yetarli edi - va bu aynan qo'riqlanayotgan
# xato sinfi. Endi muhitni SKRIPT beradi va u BITTA joyda yoziladi.
#
# `-Muhit` MAJBURIY va standart qiymati YO'Q. Standart qiymat - eng
# xavfli narsa: u eslab qolinmaydi va noto'g'ri muhitga jimgina
# tushib qolinadi.
#
# UCH QAVATLI TASDIQ (docs/erp_deploy_28.md):
#     1-qavat   .env nima deydi          (ERP_MUHIT)
#     2-qavat   baza o'zini nima deb belgilagan  (erp.setting.muhit)
#     3-qavat   deploy nimani kutyapti   (shu skript beradi)
# Uchovi ham bir xil bo'lishi shart.
#
# ISHLAB CHIQARISHDA SINOVLAR YURITILMAYDI va bu NUQSON EMAS:
# `api/muhit.py` qulfi ularni baribir to'sadi (haqiqiy yozuv va
# `erp.doc_audit` da qaytarib bo'lmaydigan iz). Skript buni JIM
# o'tkazib yubormaydi - ochiq yozadi va staging'da o'tganini talab
# qiladi.
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1 BOM'siz
# .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni buzadi.
# =============================================================================
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('prod', 'staging', 'dev')]
    [string] $Muhit,

    # Qo'llanadigan sxema patchi (ixtiyoriy). Berilmasa sxema
    # TEGILMAYDI - patchlar bu loyihada ATAYLAB qo'lda qo'llanadi va
    # ularni avtomatik "hammasini qo'lla" qilish orqaga qaytarishni
    # imkonsiz qilardi.
    [string] $Patch,

    # Faqat darvozalarni tekshiradi, hech narsani o'zgartirmaydi.
    [switch] $Tekshir,

    # Zaxira olishni o'tkazib yuborish (faqat staging uchun ma'noli).
    [switch] $ZaxirasiZ
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py" }

$qadam = 0
function Step($nom) {
    $script:qadam++
    Write-Host ''
    Write-Host "=== $script:qadam. $nom ===" -ForegroundColor Cyan
}

function Fail($nom) {
    Write-Host ''
    Write-Host "[TO'XTATILDI] $nom" -ForegroundColor Red
    Write-Host "Deploy bajarilmadi. Yuqoridagi xatoni tuzatib qayta yuriting."
    exit 1
}

Write-Host "TENDER ERP - DEPLOY" -ForegroundColor Cyan
Write-Host "  muhit:  $Muhit"
Write-Host "  patch:  $(if ($Patch) { $Patch } else { '(yo''q)' })"
Write-Host "  rejim:  $(if ($Tekshir) { 'TEKSHIRUV (o''zgarishsiz)' } else { 'to''liq' })"

# --- 1) MUHIT DARVOZASI ------------------------------------------------------
# BIRINCHI va to'xtatuvchi: noto'g'ri bazada qolgan hamma ish ma'nosiz.
Step "Muhit darvozasi (--kutilgan $Muhit)"
& $py (Join-Path $Root 'check_setup.py') --kutilgan $Muhit
if ($LASTEXITCODE -ne 0) { Fail "Muhit darvozasi yopiq (--kutilgan $Muhit)." }

# --- 2) KOD HOLATI -----------------------------------------------------------
# Qaysi SHA joylashtirilayotgani YOZILADI: nosozlikda "nima
# joylashtirilgan edi?" degan savol javobsiz qolmasin.
Step "Kod holati"
Push-Location $Root
try {
    $sha = (& git rev-parse HEAD 2>$null)
    $branch = (& git rev-parse --abbrev-ref HEAD 2>$null)
    $iflos = (& git status --porcelain 2>$null)
    if ($sha) {
        Write-Host "  SHA:    $sha"
        Write-Host "  branch: $branch"
    } else {
        Write-Host "  (git yo'q yoki repo emas)"
    }
    if ($iflos) {
        # ISHLAB CHIQARISHDA to'xtatiladi: commit qilinmagan
        # o'zgarish bilan deploy qilingan narsani keyin qayta
        # tiklab bo'lmaydi.
        Write-Host "  DIQQAT: commit qilinmagan o'zgarishlar bor:"
        $iflos | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" }
        if ($Muhit -eq 'prod') {
            Fail "Ishlab chiqarishga faqat TOZA daraxtdan deploy qilinadi."
        }
    }
} finally { Pop-Location }

# --- 3) ZAXIRA ---------------------------------------------------------------
# SXEMA O'ZGARSA - MAJBURIY. Patch orqaga qaytarilsa ham, ma'lumot
# qaytmaydi.
Step "Zaxira"
if ($Tekshir) {
    Write-Host "  (tekshiruv rejimi - o'tkazib yuborildi)"
} elseif ($ZaxirasiZ -and $Muhit -ne 'prod') {
    Write-Host "  (-ZaxirasiZ berilgan)"
} elseif ($ZaxirasiZ -and $Muhit -eq 'prod') {
    Fail "Ishlab chiqarishda zaxirani o'tkazib yuborib bo'lmaydi."
} else {
    & (Join-Path $Root 'backup_erp.ps1')
    if ($LASTEXITCODE -ne 0) { Fail "Zaxira olinmadi." }
}

# --- 4) SXEMA PATCHI ---------------------------------------------------------
# TARTIB: patch AVVAL, ilova KEYIN. Teskarisi bo'lsa yangi kod hali
# yo'q ustunlarni so'rab 500 beradi (docs/erp_deploy_28.md).
Step "Sxema patchi"
if (-not $Patch) {
    Write-Host "  (patch berilmagan - sxema tegilmaydi)"
} elseif ($Tekshir) {
    Write-Host "  (tekshiruv rejimi) qo'llanardi: $Patch"
} else {
    $patchYol = if (Test-Path $Patch) { $Patch } else { Join-Path $Root $Patch }
    if (-not (Test-Path $patchYol)) { Fail "Patch fayli topilmadi: $Patch" }
    $psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
    if (-not $psql) {
        $c = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' `
            -ErrorAction SilentlyContinue | Sort-Object FullName -Descending
        if ($c) { $psql = $c[0].FullName }
    }
    if (-not $psql) { Fail "psql topilmadi." }
    $dsn = $env:XT_DB_DSN
    if (-not $dsn) {
        foreach ($line in Get-Content (Join-Path $Root '.env')) {
            if ($line -match '^\s*XT_DB_DSN\s*=\s*(.+)$') { $dsn = $Matches[1].Trim() }
        }
    }
    # `ON_ERROR_STOP=1` SHART: usiz psql xatodan keyin ham davom
    # etadi va YARIM qo'llangan patch qoladi.
    & $psql $dsn -v ON_ERROR_STOP=1 -f $patchYol
    if ($LASTEXITCODE -ne 0) { Fail "Patch qo'llanmadi: $Patch" }
    Write-Host "[OK] patch qo'llandi: $Patch"
}

# --- 5) INTERFEYS ------------------------------------------------------------
Step "Interfeys qurilishi"
if ($Tekshir) {
    Write-Host "  (tekshiruv rejimi - o'tkazib yuborildi)"
} else {
    Push-Location (Join-Path $Root 'frontend')
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { Fail "npm ci yiqildi." }
        & npm run build
        if ($LASTEXITCODE -ne 0) { Fail "Interfeys qurilmadi." }
    } finally { Pop-Location }
}

# --- 6) SINOV DARVOZALARI ----------------------------------------------------
# ISHLAB CHIQARISHDA YURITILMAYDI: `api/muhit.py` qulfi ularni
# baribir to'sadi. Bu JIM o'tkazib yuborilmaydi - sabab yoziladi va
# staging'da o'tganini talab qilinadi.
Step "Sinov darvozalari"
if ($Muhit -eq 'prod') {
    Write-Host "  O'TKAZIB YUBORILDI - ishlab chiqarishda sinov YURITILMAYDI."
    Write-Host "  Sabab: sinovlar haqiqiy yozuv yaratadi va erp.doc_audit da"
    Write-Host "         qaytarib bo'lmaydigan iz qoldiradi (api/muhit.py)."
    Write-Host "  TALAB: shu SHA staging'da darvozalardan o'tgan bo'lishi kerak:"
    Write-Host "         .\deploy.ps1 -Muhit staging"
} elseif ($Tekshir) {
    Write-Host "  (tekshiruv rejimi - o'tkazib yuborildi)"
} else {
    $yiqildi = @()
    Get-ChildItem (Join-Path $Root '_tests\*_test.py') | ForEach-Object {
        & $py $_.FullName | Out-Null
        if ($LASTEXITCODE -ne 0) { $yiqildi += $_.Name }
    }
    if ($yiqildi.Count -gt 0) {
        Write-Host "  Yiqilgan sinovlar:" -ForegroundColor Red
        $yiqildi | ForEach-Object { Write-Host "    $_" }
        Fail "Backend darvozasi o'tmadi."
    }
    Write-Host "[OK] backend darvozasi o'tdi"

    Push-Location (Join-Path $Root 'frontend')
    try {
        & npx tsc -b --noEmit
        if ($LASTEXITCODE -ne 0) { Fail "Typecheck o'tmadi." }
        & npx vitest run
        if ($LASTEXITCODE -ne 0) { Fail "Frontend darvozasi o'tmadi." }
    } finally { Pop-Location }
    Write-Host "[OK] frontend darvozasi o'tdi"
}

# --- 7) DEPLOY'DAN KEYINGI TEKSHIRUV -----------------------------------------
# Darvoza QAYTA yuritiladi: patch va qurilish paytida muhit
# o'zgarmaganini tasdiqlaydi (masalan noto'g'ri .env bilan qayta
# ishga tushirilgan bo'lsa).
Step "Deploy'dan keyingi tekshiruv"
& $py (Join-Path $Root 'check_setup.py') --kutilgan $Muhit
if ($LASTEXITCODE -ne 0) { Fail "Deploy'dan keyingi tekshiruv o'tmadi." }

# --- Xulosa ------------------------------------------------------------------
Write-Host ''
if ($Tekshir) {
    Write-Host "[OK] TEKSHIRUV tugadi - darvozalar ochiq ($Muhit)." -ForegroundColor Green
    Write-Host "To'liq deploy: shu buyruqni -Tekshir siz yuriting."
} else {
    Write-Host "[OK] DEPLOY tayyor ($Muhit)." -ForegroundColor Green
    if ($sha) { Write-Host "     SHA: $sha" }
    Write-Host ''
    Write-Host 'ILOVANI ISHGA TUSHIRISH:'
    if ($Muhit -eq 'prod') {
        Write-Host '  .\run_erp.ps1 -Prod'
    } else {
        Write-Host '  .\run_erp.ps1'
    }
}
