# PowerShell Launcher for Master Daily Scanner Suite
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Split-Path -Parent $ScriptDir
Set-Location $BaseDir

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$pythonExe = Join-Path $BaseDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Launching Master Daily Scanner Suite..." -ForegroundColor Green
Write-Host " (Equity Momentum + Cash-Secured Puts + Credit Spreads)" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

& $pythonExe -m scripts.screener.run_all_scans
