# =============================================================================
# ERP zaxira nusxasini Windows Task Scheduler ga qo'yadi (kuniga bir marta).
#
#   .\register_backup_task.ps1              # har kuni 02:00 da
#   .\register_backup_task.ps1 -At 23:30
#   .\register_backup_task.ps1 -Keep 30
#   .\register_backup_task.ps1 -Remove
#
# NEGA KECHASI: `pg_dump` bazani bloklamaydi, lekin diskni band qiladi.
# Kechqurun ish tugagach olish eng xavfsiz vaqt.
#
# NEGA KUNIGA BIR MARTA: ERP da kuniga o'nlab yozuv paydo bo'ladi,
# minglab emas. Soatlik zaxira disk to'ldiradi va tiklashda "qaysi
# nusxa?" degan savolni qiyinlashtiradi.
#
# ZAXIRA O'ZI YETARLI EMAS: uni BOSHQA diskka yoki bulutga nusxalash
# kerak. Bitta disk ishdan chiqsa, undagi zaxira ham ketadi. Buni
# skript qilmaydi - u sizning saqlash tizimingizga bog'liq.
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1
# BOM'siz .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni
# buzadi.
# =============================================================================
param(
    [string] $At = '02:00',
    [int]    $Keep = 14,
    [string] $Out = '',
    [switch] $Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'TenderERP-Backup'
$Root = $PSScriptRoot

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] '$TaskName' olib tashlandi."
    return
}

$script = Join-Path $Root 'backup_erp.ps1'
if (-not (Test-Path $script)) { throw "backup_erp.ps1 topilmadi: $script" }

$args = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Keep $Keep"
if ($Out) { $args += " -Out `"$Out`"" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument $args -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# `-StartWhenAvailable`: kompyuter o'chiq bo'lsa, yoqilgach bajariladi.
# Zaxira o'tkazib yuborilgandan ko'ra kech olingani yaxshi.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Tender ERP: erp sxemasining zaxira nusxasi' `
    -Force | Out-Null

Write-Host "[OK] '$TaskName' ro'yxatdan o'tdi - har kuni $At"
Write-Host "Sinash:  .\backup_erp.ps1 -DryRun"
Write-Host ""
Write-Host "DIQQAT: zaxira BOSHQA diskka yoki bulutga nusxalanishi kerak." -ForegroundColor Yellow
Write-Host "        Bitta disk ishdan chiqsa, undagi zaxira ham ketadi." -ForegroundColor Yellow
