# =============================================================================
# ERP eslatmalarini Windows Task Scheduler ga qo'yadi (kuniga bir marta).
#
#   .\register_erp_task.ps1              # har kuni 08:30 da
#   .\register_erp_task.ps1 -At 09:00
#   .\register_erp_task.ps1 -Remove
#
# NEGA KUNIGA BIR MARTA: eslatma "muddat yaqin" degan xabar, u soatlik
# ma'lumot emas. Tez-tez yuborilsa odam uni o'qishni to'xtatadi.
#
# NEGA ETL GA QO'SHILMAYDI: ERP alohida loyiha - tender-ai ning ETL jadvaliga
# bog'lanish ikki loyihani qayta bir-biriga ulab qo'yardi.
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1 BOM'siz
# .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni buzadi.
# =============================================================================
param(
    [string] $At = '08:30',
    [switch] $Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'TenderERP-Reminders'
$Root = $PSScriptRoot

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] '$TaskName' olib tashlandi."
    return
}

$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py" }

# UTF-8: xabar matnida o'zbek harflari bor, konsol cp866 da ochiladi.
$action = New-ScheduledTaskAction -Execute $py `
    -Argument '-m api.erp.remind' -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Tender ERP: deadline va vazifa eslatmalari' `
    -Force | Out-Null

Write-Host "[OK] '$TaskName' ro'yxatdan o'tdi - har kuni $At"
Write-Host "Sinash:  .\.venv\Scripts\python.exe -m api.erp.remind --dry-run"
