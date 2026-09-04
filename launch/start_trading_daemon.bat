@echo off
:: trading_daemon - Rust replacement for pnl_widget_server.js (Track 1 cutover)
::
:: Serves port 8635: /health, /api/data (200ms NT8 poller), /api/order/atm,
:: /api/position/close, /api/flatten, /api/lockouts, /api/guard/config, widget HTML,
:: and pushes the account_pnl HUD into TradingView Desktop via CDP (9222).
::
:: THE FLEET P&L HUD IS INERT UNLESS THIS IS RUNNING. That is the point of the restart
:: loop: a dead daemon is a dead HUD, and silence is undetectable by definition.
::
:: EXIT CODE 2 MEANS STOP, NOT RESTART. It is the "binary missing / port taken /
:: configuration" signal - restarting cannot fix it.
title TRADING DAEMON - Fleet P^&L Engine (Rust)

cd /d %~dp0..

set DAEMON=%CD%\crates\target\release\trading_daemon.exe
set PORT=8635

set LOGDIR=%CD%\logs
set LOGFILE=%LOGDIR%\trading_daemon.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:: Roll at ~8MB so an unattended crash-loop cannot fill the disk.
for %%A in ("%LOGFILE%") do if %%~zA GTR 8388608 move /y "%LOGFILE%" "%LOGFILE%.1" >nul

if not exist "%DAEMON%" (
    echo [ERROR] trading_daemon.exe not found at %DAEMON%
    echo         Build it:  cd crates ^&^& cargo build --release -p trading_daemon
    echo [%DATE% %TIME%] FATAL: trading_daemon.exe not found >> "%LOGFILE%"
    exit /b 2
)

:: Someone already serving this port? Then there is nothing to supervise. This is the
:: guard that makes the 15-minute scheduler retrigger harmless: MultipleInstances logic
:: lives HERE, not in Task Scheduler. Without it a second launcher would bind-fail,
:: exit, and loop every 10s forever - the crash-loop that stressed NT8 on 2026-09-03.
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:%PORT%/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo [OK] daemon already serving on port %PORT% - nothing to do.
    echo [%DATE% %TIME%] already running on %PORT%, exiting quietly >> "%LOGFILE%"
    exit /b 0
)

echo ===================================================
echo   trading_daemon (Rust) - Fleet P^&L Engine
echo   port:   %PORT%
echo   binary: %DAEMON%
echo   log:    %LOGFILE%
echo   stop:   close this window, or Ctrl+C
echo ===================================================
echo.

echo [%DATE% %TIME%] daemon launcher starting, port=%PORT% >> "%LOGFILE%"

:daemon_loop
"%DAEMON%" --port %PORT% >> "%LOGFILE%" 2>&1
set DAEMON_RC=%ERRORLEVEL%

echo [%DATE% %TIME%] daemon exited with code %DAEMON_RC% >> "%LOGFILE%"

:: If the port came up under someone else while we were dead, do not fight for it.
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:%PORT%/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo [STOPPED] port %PORT% now served by another instance - exiting quietly.
    echo [%DATE% %TIME%] STOPPING: port %PORT% served by another instance >> "%LOGFILE%"
    exit /b 2
)

echo.
echo [RESTARTING] the daemon exited; restarting in 10s. A dead daemon is a dead HUD.
echo [%DATE% %TIME%] restarting in 10s >> "%LOGFILE%"
ping 127.0.0.1 -n 11 >nul
goto daemon_loop