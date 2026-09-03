@echo off
:: Stop the trading_daemon (Rust) and any legacy Node pnl_widget_server it replaced.
title TRADING DAEMON - Stop

cd /d %~dp0..

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'trading_daemon.exe' -or $_.CommandLine -like '*pnl_widget_server.js*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('  * Stopped ' + $_.Name + ' pid ' + $_.ProcessId) }"

echo.
echo Trading daemon stopped.
timeout /t 3 >nul