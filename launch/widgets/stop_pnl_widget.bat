@echo off
title Fleet P^&L Widget - Stop
echo Stopping Fleet P^&L ^& Copier Widget server...

cd /d %~dp0..\..
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_pnl_widget.ps1" -Stop

echo.
echo Widget stopped.
timeout /t 3 >nul