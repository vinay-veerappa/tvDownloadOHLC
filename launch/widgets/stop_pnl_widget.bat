@echo off
:: Stop the Fleet P&L widget server (Rust trading_daemon) - mirrors old stop behavior.
title Fleet P^&L Widget - Stop
echo Stopping Fleet P^&L ^& Copier daemon...

cd /d %~dp0..\..
call "%~dp0..\stop_trading_daemon.bat"

echo.
echo Widget stopped.
timeout /t 3 >nul