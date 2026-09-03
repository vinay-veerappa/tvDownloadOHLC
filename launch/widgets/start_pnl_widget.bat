@echo off
:: Floating desktop P&L widget - NATIVE GDI (no browser, no Chromium).
:: Data comes from trading_daemon on 8635; the daemon is started if missing.
title Fleet P^&L Widget - Launcher

cd /d %~dp0..\..

powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8635/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% neq 0 (
    echo [WARN] trading_daemon not running on 8635 - starting it first...
    start "TRADING_DAEMON" /min "%~dp0..\start_trading_daemon.bat"
    timeout /t 4 >nul
)

set WIDGET=%CD%\crates\target\release\pnl_widget_gdi.exe
if not exist "%WIDGET%" (
    echo [ERROR] pnl_widget_gdi.exe not found - build: cd crates ^&^& cargo build --release -p pnl_widget_gdi
    timeout /t 5 >nul
    exit /b 2
)
start "" "%WIDGET%"
echo [OK] Native GDI widget launched.
echo.
echo This window can be closed; the widget keeps running in the background.
timeout /t 3 >nul
