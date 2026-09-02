@echo off
title TradingView HUD Streamer - Stop
echo Stopping TradingView HUD streamer + widget engine...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\start_pnl_streamer.ps1" -Stop

echo.
echo Streamer stopped.
timeout /t 3 >nul