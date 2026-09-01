<#
.SYNOPSIS
    Starts the high-frequency real-time P&L & Copier Sync streamer for TradingView Desktop.

.DESCRIPTION
    Runs tv_pnl_streamer.js in background or foreground, pumping live P&L, balance, and copier states
    every 250ms from NinjaTrader 8 into TradingView Desktop.

.PARAMETER Background
    If specified, launches the streamer as a background process.

.PARAMETER Stop
    If specified, stops any running P&L streamer background processes.

.PARAMETER IntervalMs
    Polling interval in milliseconds (default: 250).

.EXAMPLE
    .\start_pnl_streamer.ps1
    # Starts the streamer in console

.EXAMPLE
    .\start_pnl_streamer.ps1 -Background
    # Starts the streamer in background

.EXAMPLE
    .\start_pnl_streamer.ps1 -Stop
    # Stops running background streamer
#>

[CmdletBinding()]
param(
    [switch]$Background,
    [switch]$Stop,
    [int]$IntervalMs = 250
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$StreamerScript = Join-Path $ScriptDir "pnl_widget_server.js"

if ($Stop) {
    Write-Host "[+] Stopping any running P&L streamer processes..." -ForegroundColor Cyan
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*pnl_widget_server.js*" -or $_.CommandLine -like "*tv_pnl_streamer.js*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "  * Stopped process $($_.ProcessId)" -ForegroundColor Green
    }
    exit 0
}

# Ensure HUD is injected into TradingView first
$ManagerPs = Join-Path $ScriptDir "tv_hud_manager.ps1"
if (Test-Path $ManagerPs) {
    Write-Host "[+] Ensuring account_pnl HUD is installed in TradingView Desktop..." -ForegroundColor Cyan
    & $ManagerPs -HUD "account_pnl" -Action inject
}

$env:POLL_INTERVAL_MS = $IntervalMs.ToString()

if ($Background) {
    Write-Host "[+] Launching Unified P&L Engine in background (Poll: ${IntervalMs}ms)..." -ForegroundColor Cyan
    $nodeExe = (Get-Command node).Source
    $wsh = New-Object -ComObject WScript.Shell
    $wsh.Run("`"$nodeExe`" `"$StreamerScript`"", 0, $false)
    Start-Sleep -Milliseconds 600
    Write-Host "[OK] Unified P&L Engine running persistently in background on port 8635." -ForegroundColor Green
} else {
    Write-Host "[+] Starting P&L Streamer in foreground (Press Ctrl+C to stop)..." -ForegroundColor Cyan
    & node $StreamerScript
}
