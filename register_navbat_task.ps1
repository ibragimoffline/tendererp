# =============================================================================
# Bildirishnoma NAVBATINI Windows Task Scheduler ga qo'yadi (har N daqiqada).
#
#   .\register_navbat_task.ps1              # har 5 daqiqada
#   .\register_navbat_task.ps1 -Minutes 15
#   .\register_navbat_task.ps1 -Remove
#
# NEGA ESLATMA VAZIFASIDAN ALOHIDA (`register_erp_task.ps1`):
# ikkalasi BOSHQA tezlikda ishlaydi va sababi ham boshqa.
#
#   Eslatma  - kuniga bir marta. "Muddat yaqin" soatlik ma'lumot emas;
#              tez-tez yuborilsa odam uni o'qishni to'xtatadi.
#   Navbat   - har bir necha daqiqada. Bu YUBORISH mexanizmi:
#              kechikish odamning xabarni qachon olishini belgilaydi,
#              va yiqilgan urinish qayta uriniladigan yagona joy shu.
#
# Ikkalasini bitta vazifaga qo'shish navbatni kuniga bir martaga
# tushirardi - ya'ni Telegram bir soatga o'chsa, xabar ERTAGA ketardi.
#
# NAVBAT BO'SH BO'LSA HECH NARSA QILMAYDI: `yur()` vaqti kelgan
# qatorlarni oladi va ular yo'q bo'lsa darhol qaytadi. Ya'ni tez-tez
# yurishning narxi bitta arzon so'rov.
#
# TASHQI KANAL YO'Q BO'LSA HAM ZARAR QILMAYDI: ilova bildirishnomasi
# navbatdan o'tmaydi (u jadvalning O'ZI), shuning uchun bu vazifa
# ro'yxatdan o'tmagan o'rnatmada ham ERP to'liq ishlaydi - faqat
# Telegram/email ketmaydi.
#
# ESLATMA: fayl ATAYIN faqat ASCII belgilardan iborat - PowerShell 5.1 BOM'siz
# .ps1 ni ANSI deb o'qiydi va lotin bo'lmagan belgilar qatorni buzadi.
# =============================================================================
param(
    [int] $Minutes = 5,
    [switch] $Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'TenderERP-Notifications'
$Root = $PSScriptRoot

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] '$TaskName' olib tashlandi."
    return
}

if ($Minutes -lt 1 -or $Minutes -gt 60) {
    throw "Oraliq 1-60 daqiqa bo'lishi kerak (berildi: $Minutes)."
}

$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Virtual muhit yo'q: $py" }

$action = New-ScheduledTaskAction -Execute $py `
    -Argument '-m api.erp.navbat' -WorkingDirectory $Root

# TAKRORLANISH MUDDATSIZ: vazifa kun boshida ishga tushadi va
# to'xtamaydi. `-RepetitionDuration` berilmasa Windows uni "cheksiz"
# deb oladi; berilsa esa muddat tugagach navbat JIMGINA to'xtardi va
# buni hech narsa ko'rsatmasdi.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes)

# QISQA VAQT CHEGARASI: navbat bitta yurishda ko'p ish qilmaydi
# (`--limit 50`). Osilib qolgan jarayon keyingi yurishni to'sib
# qo'yishidan ko'ra to'xtatilgani yaxshi.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings `
    -Description 'Tender ERP: bildirishnoma navbati (Telegram/email)' `
    -Force | Out-Null

Write-Host "[OK] '$TaskName' ro'yxatdan o'tdi - har $Minutes daqiqada"
Write-Host "Sinash:  .\.venv\Scripts\python.exe -m api.erp.navbat --dry-run"
Write-Host "Holat:   ERP -> Sozlash -> bildirishnoma navbati (yoki"
Write-Host "         .\.venv\Scripts\python.exe -m api.erp.navbat)"
