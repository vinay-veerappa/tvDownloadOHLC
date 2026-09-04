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
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$DaemonBat = Join-Path $RootDir "launch\start_trading_daemon.bat"
$StopBat   = Join-Path $RootDir "launch\stop_trading_daemon.bat"
$DaemonExe = Join-Path $RootDir "crates\target\release\trading_daemon.exe"

if ($Stop) {
    Write-Host "[+] Stopping Trading Daemon and P&L streamer processes..." -ForegroundColor Cyan
    if (Test-Path $StopBat) {
        & cmd.exe /c "`"$StopBat`""
    } else {
        Get-Process trading_daemon -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*pnl_widget_server.js*" -or $_.CommandLine -like "*tv_pnl_streamer.js*" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "  * Stopped legacy process $($_.ProcessId)" -ForegroundColor Green
    }
    Write-Host "[OK] Stopped Trading Daemon." -ForegroundColor Green
    exit 0
}

# Ensure HUD is injected into TradingView first
$ManagerPs = Join-Path $ScriptDir "tv_hud_manager.ps1"
if (Test-Path $ManagerPs) {
    Write-Host "[+] Ensuring account_pnl HUD is installed in TradingView Desktop..." -ForegroundColor Cyan
    & $ManagerPs -HUD "account_pnl" -Action inject
}

# Check if trading_daemon is already healthy
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8635/health" -TimeoutSec 2 -ErrorAction Stop
    if ($health.status -eq "ok") {
        Write-Host "[OK] Trading Daemon is already running on port 8635 (NT8 connected: $($health.nt8Connected))." -ForegroundColor Green
        exit 0
    }
} catch {}

if ($Background) {
    Write-Host "[+] Launching Trading Daemon in background (Port 8635, 200ms tick cadence)..." -ForegroundColor Cyan
    if (Test-Path $DaemonBat) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$DaemonBat`"" -WindowStyle Minimized
    } elseif (Test-Path $DaemonExe) {
        Start-Process -FilePath $DaemonExe -WindowStyle Hidden
    } else {
        throw "Neither start_trading_daemon.bat nor trading_daemon.exe was found."
    }
    Start-Sleep -Milliseconds 800
    Write-Host "[OK] Trading Daemon running persistently on port 8635." -ForegroundColor Green
} else {
    Write-Host "[+] Starting Trading Daemon in foreground (Press Ctrl+C to stop)..." -ForegroundColor Cyan
    if (Test-Path $DaemonExe) {
        & $DaemonExe
    } else {
        & cmd.exe /c "`"$DaemonBat`""
    }
}
