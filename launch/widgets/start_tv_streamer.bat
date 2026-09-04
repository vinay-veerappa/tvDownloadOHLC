@echo off
title TradingView HUD Streamer - Launcher
echo Starting TradingView HUD streamer (P^&L + copier pump into TV Desktop)...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\start_pnl_streamer.ps1" -Background

echo.
echo The unified native Rust daemon (trading_daemon.exe) serves BOTH:
echo   - the floating widget backend at http://127.0.0.1:8635/pnl-widget
echo   - the in-chart TradingView HUD (CDP pump, 200ms)
echo.
echo Requires: NinjaTrader 8 bridge (port 7890) + TradingView Desktop with CDP (port 9222).
echo This window can be closed; the daemon keeps running in the background.
timeout /t 5 >nul