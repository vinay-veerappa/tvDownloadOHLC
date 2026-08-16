@echo off
:: NT8 RiskGuard -> Discord alert relay (F-6)
::
:: The guard DECIDES which events a human should be told about and appends them to
::   %USERPROFILE%\Documents\NinjaTrader 8\RiskGuard\alerts_outbox.jsonl
:: This process delivers them. The guard performs no network I/O: it shares a process with
:: the platform that manages real positions, and a webhook POST from an NT8 callback thread
:: can block on a wedged remote host.
::
:: THE WHOLE FEATURE IS INERT UNLESS THIS IS RUNNING. That is the point of the restart loop
:: and of the heartbeat: a crashed relay is a silently dead alert channel, and silence is
:: undetectable by definition -- you cannot notice a message you were never going to get.
:: The relay posts a periodic heartbeat so the question becomes checkable in the other
:: direction: if the heartbeat stops arriving, something is wrong.
::
:: EXIT CODE 2 MEANS STOP, NOT RESTART. It is the relay's "this is configuration and
:: restarting cannot fix it" signal (no webhook URL, unknown transport). Restarting on it
:: would spin forever, look busy, and deliver nothing.
title RISKGUARD ALERT RELAY - NT8 -> Discord

cd /d %~dp0..

set CHANNEL=test_channel
if not "%~1"=="" set CHANNEL=%~1

:: WHY THERE IS A LOG FILE (added 2026-08-16). Under Task Scheduler there is no console, so
:: everything this window prints was going NOWHERE. Measured: the task's LastTaskResult read
:: 255 from a run the previous afternoon, the relay was not running, and there was NOT ONE
:: LINE anywhere on the box saying why. The heartbeat tells you the channel died; it cannot
:: tell you what killed it, and by the time you look the console is long gone.
::
:: That is half of "you cannot detect silence" left undone: F-6 made the SILENCE detectable
:: and left the CAUSE unrecorded.
set LOGDIR=%CD%\logs
set LOGFILE=%LOGDIR%\alert_relay.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:: Roll at ~8MB so an unattended crash-loop cannot fill the disk. One generation back is
:: enough: the interesting lines are always the last ones before a death.
for %%A in ("%LOGFILE%") do if %%~zA GTR 8388608 move /y "%LOGFILE%" "%LOGFILE%.1" >nul

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] venv not found at %CD%\.venv
    echo [%DATE% %TIME%] FATAL: venv not found at %CD%\.venv >> "%LOGFILE%"
    exit /b 2
)

echo ===================================================
echo   RiskGuard alert relay
echo   channel:  %CHANNEL%
echo   outbox:   %USERPROFILE%\Documents\NinjaTrader 8\RiskGuard\alerts_outbox.jsonl
echo   log:      %LOGFILE%
echo   stop:     close this window, or Ctrl+C
echo ===================================================
echo.

echo [%DATE% %TIME%] relay launcher starting, channel=%CHANNEL% >> "%LOGFILE%"

:relay_loop
:: stdout AND stderr to the log. The relay logs through `logging`, which writes to stderr --
:: redirecting only stdout would produce an empty file and read as a quiet, healthy relay.
.venv\Scripts\python.exe -m scripts.riskguard.alert_relay --channel %CHANNEL% >> "%LOGFILE%" 2>&1
set RELAY_RC=%ERRORLEVEL%

echo [%DATE% %TIME%] relay exited with code %RELAY_RC% >> "%LOGFILE%"

:: A clean Ctrl+C also lands here. Restarting is still correct: the operator closing the
:: window is what stops it, and an unattended exit is exactly the case this loop exists for.
if %RELAY_RC% GEQ 2 (
    echo.
    echo [STOPPED] the relay refused to start -- this is a configuration problem and
    echo           restarting cannot fix it. See %LOGFILE%
    echo [%DATE% %TIME%] STOPPING: exit %RELAY_RC% is a configuration failure; not restarting. >> "%LOGFILE%"
    :: No `pause` here. Under Task Scheduler there is no console to read it, so it bought
    :: nothing headless -- and the reason it existed (let the operator read the error) is
    :: now served by the log, which outlives the window.
    exit /b 2
)

echo.
echo [RESTARTING] the relay exited; restarting in 10s. A dead relay is a dead alert channel.
echo [%DATE% %TIME%] restarting in 10s >> "%LOGFILE%"
timeout /t 10 /nobreak >nul
goto relay_loop
