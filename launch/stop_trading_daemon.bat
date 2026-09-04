@echo off
:: Stop the trading_daemon, the native GDI widget, and any legacy Node pnl_widget_server.
::
:: SUPERVISOR FIRST, THEN CHILD. start_trading_daemon.bat is a restart loop: killing
:: trading_daemon.exe alone lets the supervising cmd.exe bring it back 10 seconds later
:: under a NEW pid, while this script reports success. Measured on the sibling
:: broker_sentinel launcher 2026-09-03, same shape here.
title TRADING DAEMON - Stop

cd /d %~dp0..

echo Stopping supervisor loop(s)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_trading_daemon.bat*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('  * Stopped supervisor pid ' + $_.ProcessId) }"

:: The legacy-Node clause is scoped to node.exe on purpose: an unqualified CommandLine
:: wildcard matched this script's own powershell child during testing, i.e. the stop
:: path would have killed an unrelated process that merely named the file.
echo Stopping daemon, widget, and legacy Node server...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'trading_daemon.exe' -or $_.Name -eq 'pnl_widget_gdi.exe' -or ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*pnl_widget_server.js*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('  * Stopped ' + $_.Name + ' pid ' + $_.ProcessId) }"

:: Report the OUTCOME. Re-read after the restart window could have fired - otherwise
:: "stopped" only records that the kill line was reached.
powershell -NoProfile -Command "Start-Sleep -Seconds 12; $p = @(Get-Process -Name trading_daemon -ErrorAction SilentlyContinue); if ($p.Count -gt 0) { Write-Host ''; Write-Host ('[FAILED] trading_daemon is STILL running (pid ' + ($p.Id -join ',') + ') - something re-launched it.') -ForegroundColor Red; exit 1 } else { Write-Host ''; Write-Host '[OK] trading_daemon stopped and stayed stopped.' -ForegroundColor Green; exit 0 }"
set STOP_RC=%ERRORLEVEL%

echo.
echo The Fleet P^&L HUD is inert until the daemon is started again.
echo.
echo NOTE: the TradingDaemon scheduled task re-fires every 15 minutes and will start it
echo       again. To keep it down:  Disable-ScheduledTask -TaskName 'TradingDaemon'
echo       To re-enable:            Enable-ScheduledTask  -TaskName 'TradingDaemon'
exit /b %STOP_RC%
