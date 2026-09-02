@echo off
title FinancialJuice Widget - Launcher
echo Starting FinancialJuice Squawk ^& News Widget (floating desktop window)...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_fj_widget.ps1"

echo.
echo Widget server: http://127.0.0.1:8636/fj-widget
echo Self-contained - no NT8 bridge required.
echo.
echo This window can be closed; the widget keeps running in the background.
timeout /t 5 >nul