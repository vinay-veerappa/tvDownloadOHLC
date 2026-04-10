$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$syncScript = Join-Path $repoRoot 'scripts\maintenance\sync-economic-events-daily.ps1'
$taskName = 'tvDownloadOHLC-EconomicEvents-DailySync'

if (!(Test-Path $syncScript)) {
    throw "Sync script not found: $syncScript"
}

$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$syncScript`""

schtasks /Create /TN $taskName /TR $action /SC DAILY /ST 06:05 /F | Out-Host
Write-Host "Registered task: $taskName" -ForegroundColor Green
Write-Host "Run once now with: schtasks /Run /TN $taskName"
