@echo off
:: Floating desktop P&L widget window (App Mode) bound to the Rust daemon on 8635.
:: The daemon itself is started by start_trading_daemon.bat - this only opens the window.
title Fleet P^&L Widget - Launcher

cd /d %~dp0..\..

powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8635/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% neq 0 (
    echo [WARN] trading_daemon not running on 8635 - starting it first...
    start "TRADING_DAEMON" /min "%~dp0..\start_trading_daemon.bat"
    timeout /t 4 >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_pnl_widget.ps1" -Port 8635

echo.
echo Widget server: http://127.0.0.1:8635/pnl-widget
echo Requires NinjaTrader 8 bridge (port 7890) for live data.
echo.
echo This window can be closed; the widget keeps running in the background.
timeout /t 5 >nul