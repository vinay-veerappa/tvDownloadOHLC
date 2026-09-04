@echo off
:: Stop the broker_sentinel watchdog - supervisor FIRST, then the child.
::
:: KILLING THE CHILD ALONE DOES NOT STOP IT. start_broker_sentinel.bat is a restart
:: loop: kill broker_sentinel.exe and the supervising cmd.exe brings it back 10 seconds
:: later under a NEW pid. Measured 2026-09-03 - "stopped" reported success while the
:: watchdog was already running again. Order matters: supervisor, then child.
title BROKER SENTINEL - Stop

cd /d %~dp0..

echo Stopping supervisor loop(s)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_broker_sentinel.bat*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('  * Stopped supervisor pid ' + $_.ProcessId) }"

echo Stopping sentinel process(es)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'broker_sentinel.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('  * Stopped broker_sentinel pid ' + $_.ProcessId) }"

:: Report the OUTCOME, not the fact that the kill was issued. Re-read after the restart
:: window has had time to fire, otherwise "stopped" only means "the line was reached".
powershell -NoProfile -Command "Start-Sleep -Seconds 12; $p = @(Get-Process -Name broker_sentinel -ErrorAction SilentlyContinue); if ($p.Count -gt 0) { Write-Host ''; Write-Host ('[FAILED] broker_sentinel is STILL running (pid ' + ($p.Id -join ',') + ') - something re-launched it.') -ForegroundColor Red; exit 1 } else { Write-Host ''; Write-Host '[OK] broker_sentinel stopped and stayed stopped.' -ForegroundColor Green; exit 0 }"
set STOP_RC=%ERRORLEVEL%

echo.
echo Nothing is watching NT8 for deadlock now.
echo.
echo NOTE: the BrokerSentinel scheduled task re-fires every 15 minutes and will start it
echo       again. To keep it down:  Disable-ScheduledTask -TaskName 'BrokerSentinel'
echo       To re-enable:            Enable-ScheduledTask  -TaskName 'BrokerSentinel'
exit /b %STOP_RC%
