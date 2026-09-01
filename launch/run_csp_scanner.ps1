# PowerShell Launcher for Cash-Secured Put (CSP) Ranking Pipeline
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 Launching Automated CSP Ranking & Scoring Pipeline..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

& $pythonExe -m scripts.csp_ranking.cli --open-browser @args
