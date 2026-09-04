@echo off
title FinancialJuice Widget - Stop
echo Stopping FinancialJuice Native Rust Widget...

cd /d %~dp0..\..

taskkill /F /IM fj_widget.exe >nul 2>&1
taskkill /F /IM fj_daemon.exe >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_fj_widget.ps1" -Stop >nul 2>&1

echo.
echo [OK] FinancialJuice Widget stopped.
ping 127.0.0.1 -n 2 >nul
exit /b 0