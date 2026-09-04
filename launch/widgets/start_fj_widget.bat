@echo off
:: Floating desktop FinancialJuice Squawk & News widget - Pure Native Rust (WebView2).
:: Self-contained binary with in-process HTTP reverse proxy on 8636.
title FinancialJuice Widget - Launcher

cd /d %~dp0..\..

set WIDGET=%CD%\crates\target\release\fj_widget.exe
if not exist "%WIDGET%" (
    echo [ERROR] fj_widget.exe not found - build: cd crates ^&^& cargo build --release -p fj_widget
    ping 127.0.0.1 -n 4 >nul
    exit /b 2
)

powershell -NoProfile -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = '%WIDGET%'} | Out-Null"
echo [OK] FinancialJuice Native Rust Widget launched.
echo.
echo Widget server: http://127.0.0.1:8636/fj-widget
echo Self-contained - live audio squawk, SignalR news, and econ calendar.
echo.
echo This window can be closed; the widget keeps running in the background.
ping 127.0.0.1 -n 3 >nul
exit /b 0