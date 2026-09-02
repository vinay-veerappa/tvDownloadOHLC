@echo off
title TRADING STACK - Status
cd /d %~dp0..\..

echo ============================================================
echo     TRADING STACK - LIVE STATUS
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stack_status.ps1"
echo.
echo Individual restarts:
echo   launch\widgets\start_pnl_widget.bat    - Fleet P^&L widget only
echo   launch\widgets\start_fj_widget.bat    - FinancialJuice widget only
echo   launch\widgets\start_tv_streamer.bat  - TV HUD streamer only
echo   launch\start_api.bat                 - API backend
echo   launch\start_web.bat                 - Web dashboard
echo.
timeout /t 15 >nul