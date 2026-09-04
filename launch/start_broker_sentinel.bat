@echo off
:: broker_sentinel - Track 3 watchdog (OBSERVE-ONLY until broker credentials exist).
::
:: Polls NT8 port 7890 /api/positions every 500ms. If positions are open and the port
:: stops answering for >3000ms, it trips the killswitch path.
::
:: READ THIS BEFORE ASSUMING YOU ARE PROTECTED.
:: With arm_live_flatten=false (the default) and no Tradovate/Rithmic credentials, the
:: killswitch LOGS the broker call it would have made and places no order. This process
:: is CONFIGURED and EVALUATING; it is not ENFORCING. It buys you a timestamped record
:: and an alert, not a flatten. Do not size positions as though a killswitch exists.
::
:: Config: %USERPROFILE%\Documents\NinjaTrader 8\RiskGuard\sentinel.json
:: EXIT CODE 2 MEANS STOP, NOT RESTART (binary missing / already running).
title BROKER SENTINEL - NT8 Watchdog (observe-only)

cd /d %~dp0..

set SENTINEL=%CD%\crates\target\release\broker_sentinel.exe

set LOGDIR=%CD%\logs
set LOGFILE=%LOGDIR%\broker_sentinel.log
:: The CHILD owns %LOGFILE% for as long as it runs, and Windows refuses a second
:: append handle to it. So the supervisor lines written precisely WHEN a child is
:: alive go to a separate file. Without this the "already running" and "another
:: instance" branches print a sharing violation and record nothing - which is exactly
:: the audit trail you want when diagnosing a duplicate launch.
set LAUNCHLOG=%LOGDIR%\broker_sentinel.launcher.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:: Roll at ~8MB so an unattended crash-loop cannot fill the disk.
for %%A in ("%LOGFILE%") do if %%~zA GTR 8388608 move /y "%LOGFILE%" "%LOGFILE%.1" >nul

if not exist "%SENTINEL%" (
    echo [ERROR] broker_sentinel.exe not found at %SENTINEL%
    echo         Build it:  cd crates ^&^& cargo build --release -p broker_sentinel
    echo [%DATE% %TIME%] FATAL: broker_sentinel.exe not found >> "%LOGFILE%"
    exit /b 2
)

:: The sentinel binds no port, so the daemon's health-probe guard does not apply here.
:: Guard on the process instead. Two sentinels would double the 500ms poll against NT8
:: and race each other to trip - and the scheduler retriggers this every 15 minutes.
powershell -NoProfile -Command "if (Get-Process -Name broker_sentinel -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo [OK] broker_sentinel already running - nothing to do.
    echo [%DATE% %TIME%] already running, exiting quietly >> "%LAUNCHLOG%"
    exit /b 0
)

echo ===================================================
echo   broker_sentinel (Rust) - NT8 deadlock watchdog
echo   mode:   OBSERVE-ONLY (no broker credentials)
echo   binary: %SENTINEL%
echo   log:    %LOGFILE%
echo   stop:   launch\stop_broker_sentinel.bat, or Ctrl+C
echo ===================================================
echo.
echo   THIS IS NOT AN ACTIVE KILLSWITCH. It records what it would have done.
echo.

echo [%DATE% %TIME%] sentinel launcher starting >> "%LOGFILE%"

:sentinel_loop
"%SENTINEL%" >> "%LOGFILE%" 2>&1
set SENTINEL_RC=%ERRORLEVEL%

echo [%DATE% %TIME%] sentinel exited with code %SENTINEL_RC% >> "%LOGFILE%"

:: If another instance came up while we were dead, do not fight it.
powershell -NoProfile -Command "if (Get-Process -Name broker_sentinel -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo [STOPPED] another broker_sentinel is running - exiting quietly.
    echo [%DATE% %TIME%] STOPPING: another instance is running >> "%LAUNCHLOG%"
    exit /b 2
)

echo.
echo [RESTARTING] sentinel exited; restarting in 10s.
echo [%DATE% %TIME%] restarting in 10s >> "%LOGFILE%"
ping 127.0.0.1 -n 11 >nul
goto sentinel_loop
