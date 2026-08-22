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
param([switch] $Stop)

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

# --- 1) Backend --------------------------------------------------------------
Write-Host "`n[1/2] ERP backend (:8100)" -ForegroundColor Cyan
Stop-OnPort 8100
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py  (python -m venv .venv)" }
Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'api.main:app', '--port', '8100' `
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
