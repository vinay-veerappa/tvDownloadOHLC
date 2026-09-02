@echo off
title FinancialJuice Widget - Stop
echo Stopping FinancialJuice Widget server...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_fj_widget.ps1" -Stop

echo.
echo Widget stopped.
timeout /t 3 >nul