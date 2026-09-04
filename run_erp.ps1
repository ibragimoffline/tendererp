# =============================================================================
# ERP ni ko'tarish (backend :8100 + frontend :5174)
#
#   .\run_erp.ps1            # ikkalasini yurgizadi va tekshiradi
#   .\run_erp.ps1 -Stop      # to'xtatadi
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1 BOM'siz
# .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni buzadi.
#
# Tender-AI ALOHIDA loyiha va alohida ko'tariladi (:8000 / :5173). ERP usiz
# ham ishlaydi: mavjud kartalar ochiladi, faqat cheklist va yangi karta
# olish ishlamaydi.
# =============================================================================
# ISHLAB CHIQARISH REJIMI (-Prod):
#   * frontend QURILADI va uni backendning o'zi uzatadi (bitta port);
#   * Vite dev serveri UMUMAN ko'tarilmaydi - u qayta yig'ish uchun,
#     ishlatish uchun emas;
#   * -Host bilan tarmoqqa ochiladi (default 127.0.0.1 - faqat shu
#     kompyuter).
#
# COOKIE VA HTTPS. `AUTH_COOKIE_SECURE=1` (default) da brauzer
# sessiya cookie'sini faqat HTTPS orqali yuboradi. `localhost` ni
# u ishonchli deb hisoblaydi, shuning uchun mahalliy ishda
# hech narsa qilish kerak emas.
#
# TARMOQQA HTTPS'siz chiqilganda kirish ishlamaydi. Ilgari bu
# izoh 'AUTH_COOKIE_SECURE ni 0 qiling' derdi - va aynan shu yo'l
# bilan ishlab chiqish qulayligi ishlab chiqarishga sizib o'tardi:
# `Secure` siz sessiya cookie'si OCHIQ ketadi va bir tarmoqdagi
# istalgan odam uni ushlab boshqa hisobga kira oladi.
#
# Shuning uchun -Prod rejimida bunday ishga tushirish TO'XTATILADI
# (pastdagi 0a-bo'lim). Ikkita haqiqiy yechim: HTTPS qo'yish yoki
# tarmoqqa chiqmaslik. Ishonchli ichki tarmoq uchun ongli chetlab
# o'tish: -InsecureCookies.
param(
    [switch] $Stop,
    [switch] $Prod,
    [string] $BindHost = '127.0.0.1',
    # ONGLI QAROR: HTTPS'siz tarmoqqa chiqishga ruxsat. Usiz -Prod
    # rejimida bunday ishga tushirish TO'XTATILADI (pastga qarang).
    [switch] $InsecureCookies
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

function Stop-OnPort($port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "[i] :$port (PID $($_.OwningProcess)) to'xtatildi"
        }
}

if ($Stop) {
    Stop-OnPort 8100
    Stop-OnPort 5174
    Write-Host "[OK] ERP to'xtatildi."
    return
}

# --- 0a) XAVFSIZLIK QULFI ----------------------------------------------------
# `AUTH_COOKIE_SECURE=0` - IShLAB CHIQISH uchun qulaylik. Yuqoridagi izoh
# uni tarmoqqa chiqishda 0 qilishni TAVSIYA qiladi, va aynan shu yo'l
# bilan u ishlab chiqarishga sizib o'tadi.
#
# NIMA YO'QOTILADI: `Secure` bayrog'isiz sessiya cookie'si HTTP orqali
# OCHIQ ketadi. Bir tarmoqdagi istalgan odam uni ushlab, boshqa
# hisobga kira oladi - parol ham, tasdiq ham talab qilinmaydi.
#
# LOCALHOST ISTISNO: brauzerlar `127.0.0.1` ni ishonchli deb hisoblaydi
# va u tarmoqqa umuman chiqmaydi.
#
# Bu `localhost` havolasi qoidasi bilan bir sinf: ishlab chiqishdagi
# qulaylik ishlab chiqarishda teshik bo'lib qoladi.
if ($Prod) {
    $envPath = Join-Path $Root '.env'
    $secure = '1'
    if (Test-Path $envPath) {
        $hit = Select-String -Path $envPath -Pattern '^\s*AUTH_COOKIE_SECURE\s*=\s*(.+)$' |
               Select-Object -Last 1
        if ($hit) { $secure = $hit.Matches[0].Groups[1].Value.Trim() }
    }
    $secureOff = $secure -in @('0', 'false', 'no', 'off', '')
    $loopback  = $BindHost -in @('127.0.0.1', 'localhost', '::1')

    if ($secureOff -and -not $loopback -and -not $InsecureCookies) {
        Write-Host ""
        Write-Host "TO'XTATILDI: AUTH_COOKIE_SECURE=0 va tarmoqqa chiqilyapti ($BindHost)." -ForegroundColor Red
        Write-Host "Sessiya cookie'si HTTP orqali OCHIQ ketadi - bir tarmoqdagi" -ForegroundColor Red
        Write-Host "istalgan odam uni ushlab, boshqa hisobga kira oladi." -ForegroundColor Red
        Write-Host ""
        Write-Host "Ikkita HAQIQIY yechim:" -ForegroundColor Yellow
        Write-Host "  1. HTTPS qo'ying (teskari proksi) va .env da AUTH_COOKIE_SECURE=1;"
        Write-Host "  2. yoki tarmoqqa chiqmang: -BindHost 127.0.0.1 (default)."
        Write-Host ""
        Write-Host "Ishonchli ichki tarmoqda ONGLI ravishda davom etmoqchi bo'lsangiz:"
        # `./` ATAYLAB, `.\` emas: teskari chiziq matn ichida oson
        # yo'qoladi (birinchi yozuvda aynan shunday bo'ldi -
        # qaytarish belgisiga aylanib, qator "un_erp.ps1" bo'lib
        # chiqdi). PowerShell ikkala shaklni ham qabul qiladi.
        Write-Host "  ./run_erp.ps1 -Prod -BindHost $BindHost -InsecureCookies"
        exit 1
    }
    if ($secureOff -and -not $loopback) {
        Write-Host ""
        Write-Host "OGOHLANTIRISH: -InsecureCookies bilan ishga tushirildi." -ForegroundColor Yellow
        Write-Host "Sessiya cookie'si HTTP orqali ochiq ketadi ($BindHost)." -ForegroundColor Yellow
        Write-Host "Bu FAQAT ishonchli ichki tarmoq uchun." -ForegroundColor Yellow
        Write-Host ""
    }
}

# --- 0) Ishlab chiqarish: frontendni QURAMIZ ---------------------------------
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py  (python -m venv .venv)" }

if ($Prod) {
    Write-Host "`n[0/2] Frontend qurilyapti (ishlab chiqarish)" -ForegroundColor Cyan
    $fe0 = Join-Path $Root 'frontend'
    if (-not (Test-Path (Join-Path $fe0 'node_modules'))) {
        throw "npm install bajarilmagan: $fe0"
    }
    Push-Location $fe0
    # DIQQAT: PowerShell 5.1 tashqi dasturning stderr qatorini XATO deb
    # hisoblaydi ($ErrorActionPreference = 'Stop' bilan skript o'sha
    # yerda uziladi). Vite esa ogohlantirishlarni stderr ga yozadi va
    # ular xato EMAS. Haqiqat - CHIQISH KODIDA, matnda emas.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Interfeys sinovi QURISHDAN OLDIN: buzuq kodni qurib, keyin
        # tekshirishning ma'nosi yo'q.
        & npm.cmd run test
        if ($LASTEXITCODE -ne 0) { throw "interfeys sinovi yiqildi" }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build xato bilan tugadi" }
    } finally {
        $ErrorActionPreference = $prev
        Pop-Location
    }
    # "Build o'tdi" degani "ishlaydi" degani EMAS: bir marta Tailwind
    # umuman ishga tushmagan va build baribir muvaffaqiyatli tugagan.
    & $py (Join-Path $Root 'check_build.py')
    if ($LASTEXITCODE -ne 0) {
        throw "Qurilgan interfeys buzuq - yuqoridagi ro'yxatga qarang"
    }
    Write-Host "[OK] frontend/dist tayyor va tekshirildi"
}

# --- 1) Backend --------------------------------------------------------------
Write-Host "`n[1/2] ERP backend (:8100)" -ForegroundColor Cyan
Stop-OnPort 8100
Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'api.main:app', '--port', '8100', '--host', $BindHost `
    -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Root 'api.stdout.log') `
    -RedirectStandardError  (Join-Path $Root 'api.stderr.log')

$ok = $false
foreach ($i in 1..20) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8100/health' -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { throw "Backend javob bermadi - api.stderr.log ga qarang." }
Write-Host "[OK] http://127.0.0.1:8100/docs"

# --- 2) Frontend -------------------------------------------------------------
if ($Prod) {
    Write-Host "`n[2/2] Frontend - BACKEND UZATADI (Vite ko'tarilmaydi)" -ForegroundColor Cyan
    Stop-OnPort 5174
    $addr = if ($BindHost -eq '0.0.0.0') { 'http://<shu-kompyuter-IP>:8100' }
            else { 'http://127.0.0.1:8100' }
    Write-Host "[OK] $addr"
    Write-Host "`nTender-AI alohida ko'tariladi: D:\MVP projects\tender-ai\run_all.ps1 -NoTunnel"
    return
}

Write-Host "`n[2/2] ERP frontend (:5174)" -ForegroundColor Cyan
$fe = Join-Path $Root 'frontend'
if (-not (Test-Path (Join-Path $fe 'node_modules'))) { throw "npm install bajarilmagan: $fe" }
Stop-OnPort 5174
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
    -WorkingDirectory $fe -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $fe 'vite.stdout.log') `
    -RedirectStandardError  (Join-Path $fe 'vite.stderr.log')

$ok = $false
foreach ($i in 1..20) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:5174/' -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { throw "Vite javob bermadi - frontend\vite.stderr.log ga qarang." }
Write-Host "[OK] http://localhost:5174"
Write-Host ""
Write-Host "Tender-AI alohida ko'tariladi: D:\MVP projects\tender-ai\run_all.ps1 -NoTunnel"
