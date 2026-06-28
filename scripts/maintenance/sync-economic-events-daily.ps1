$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$webRoot = Join-Path $repoRoot 'web'
$logDir = Join-Path $repoRoot 'logs'

if (!(Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory | Out-Null
}

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$logFile = Join-Path $logDir 'economic-events-sync.log'

function Invoke-LoggedCmd {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$StepName
    )

    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $StepName" | Tee-Object -FilePath $logFile -Append
    $output = cmd /c "$Command 2>&1"
    $exitCode = $LASTEXITCODE
    $output | Tee-Object -FilePath $logFile -Append
    if ($exitCode -ne 0) {
        throw "$StepName failed with exit code $exitCode"
    }
}

Push-Location $repoRoot
try {
    $env:DATABASE_URL = 'file:./web/prisma/dev.db'
    Invoke-LoggedCmd -Command "python scripts/market_data/fetch_economic_calendar.py" -StepName "Starting economic-event sync (Python)"
    "[$timestamp] Economic-event sync completed" | Tee-Object -FilePath $logFile -Append
}
finally {
    Pop-Location
}
