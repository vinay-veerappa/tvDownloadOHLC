@echo off
setlocal enabledelayedexpansion
title TRADING STACK - Unified Launcher
cd /d %~dp0..\..

echo ============================================================
echo     TRADING STACK - HEALTH-CHECKED STARTUP
echo     (skips anything already running - idempotent)
echo ============================================================
echo.

set POWERSHELL=powershell -NoProfile -ExecutionPolicy Bypass

:: -----------------------------------------------------------
:: 0. Prerequisites check (things that must be started manually)
:: -----------------------------------------------------------
echo [CHECK] NinjaTrader bridge (port 7890)...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://localhost:7890/api/health' -Headers @{Authorization='Bearer d0b837223cab4653'} -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo         OK - RiskGuard / copier / bridge live inside NT8.
) else (
    echo         WARN - NT8 not reachable. Start NinjaTrader first.
    echo                ^(RiskGuard+copier+bridge are addons inside NT8 - no separate start needed^)
)
echo.

echo [CHECK] TradingView Desktop CDP (port 9222)...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo         OK - TV Desktop running with debug port. HUD injection available.
) else (
    echo         WARN - TradingView not running with CDP. In-chart HUD will be skipped.
)
echo.

:: -----------------------------------------------------------
:: 1. Fleet P&L widget + TV streamer (ONE unified Rust daemon, port 8635)
:: -----------------------------------------------------------
echo [START] Fleet P^&L daemon (Rust trading_daemon)...
powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8635/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo         ALREADY RUNNING - skipping.
) else (
    start "TRADING_DAEMON" /min "%~dp0..\start_trading_daemon.bat"
    timeout /t 4 >nul
    powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8635/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
    if !errorlevel! equ 0 (
        echo         Started on port 8635 ^(Rust daemon: widget + TV CDP pump^).
    ) else (
        echo         FAILED to start on 8635 - check logs\trading_daemon.log
    )
)
echo.

:: -----------------------------------------------------------
:: 1b. Native GDI widget window (fed by the daemon on 8635)
:: -----------------------------------------------------------
echo [START] Native GDI widget...
powershell -NoProfile -Command "if (Get-Process pnl_widget_gdi -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if !errorlevel! equ 0 (
    echo         ALREADY RUNNING - skipping.
) else (
    if exist "%CD%\crates\target\release\pnl_widget_gdi.exe" (
        start "" "%CD%\crates\target\release\pnl_widget_gdi.exe"
        echo         Started ^(native, 15MB^).
    ) else (
        echo         SKIPPED - pnl_widget_gdi.exe not built ^(cd crates ^&^& cargo build --release -p pnl_widget_gdi^)
    )
)
echo.

:: -----------------------------------------------------------
:: 2. FinancialJuice widget (port 8636)
:: -----------------------------------------------------------
echo [START] FinancialJuice widget...
powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8636/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo         ALREADY RUNNING - skipping.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\tradingview\launch_fj_widget.ps1"
    echo         Started on port 8636.
)
echo.

:: -----------------------------------------------------------
:: 3. Inject TV HUD (only if CDP is up) — hard 30s timeout so a
::    wedged CDP can NEVER hang the stack launcher (measured hang
::    2026-09-03: injector blocked on a dead 9222).
:: -----------------------------------------------------------
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if !errorlevel! equ 0 (
    echo [START] Injecting account_pnl HUD into TradingView ^(30s timeout^)...
    powershell -NoProfile -Command "& { $p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\tradingview\tv_hud_manager.ps1','-HUD','account_pnl','-Action','inject' -PassThru -WindowStyle Hidden; if (-not $p.WaitForExit(30000)) { $p.Kill(); Write-Host '        TIMEOUT - HUD injection killed after 30s (TV CDP wedged). The daemon pusher still feeds the HUD; re-run inject later.' } else { Write-Host '        injected.' } }"
) else (
    echo [SKIP]  TV HUD injection - TradingView not running.
)
echo.

:: -----------------------------------------------------------
:: Summary
:: -----------------------------------------------------------
echo ============================================================
echo     STACK STATUS
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stack_status.ps1"
echo.
echo Done. Close this window whenever.
timeout /t 10 >nul