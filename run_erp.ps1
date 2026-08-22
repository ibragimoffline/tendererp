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
# DIQQAT: tarmoqqa ochilganda HTTPS bo'lmasa .env dagi
# AUTH_COOKIE_SECURE ni 0 qiling - aks holda brauzer sessiya
# cookie'sini saqlamaydi va kirish JIMGINA ishlamaydi.
param(
    [switch] $Stop,
    [switch] $Prod,
    [string] $BindHost = '127.0.0.1'
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

# --- 0) Ishlab chiqarish: frontendni QURAMIZ ---------------------------------
if ($Prod) {
    Write-Host "`n[0/2] Frontend qurilyapti (ishlab chiqarish)" -ForegroundColor Cyan
    $fe0 = Join-Path $Root 'frontend'
    if (-not (Test-Path (Join-Path $fe0 'node_modules'))) {
        throw "npm install bajarilmagan: $fe0"
    }
    Push-Location $fe0
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build xato bilan tugadi" }
    } finally { Pop-Location }
    Write-Host "[OK] frontend/dist tayyor"
}

# --- 1) Backend --------------------------------------------------------------
Write-Host "`n[1/2] ERP backend (:8100)" -ForegroundColor Cyan
Stop-OnPort 8100
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py  (python -m venv .venv)" }
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
