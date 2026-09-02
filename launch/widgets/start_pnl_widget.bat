@echo off
title Fleet P^&L Widget - Launcher
echo Starting Fleet P^&L ^& Copier Widget (floating desktop window)...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_pnl_widget.ps1"

echo.
echo Widget server: http://127.0.0.1:8635/pnl-widget
echo Requires NinjaTrader 8 bridge (port 7890) for live data.
echo.
echo This window can be closed; the widget keeps running in the background.
timeout /t 5 >nul