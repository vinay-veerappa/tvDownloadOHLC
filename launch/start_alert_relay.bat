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

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] venv not found at %CD%\.venv
    exit /b 2
)

echo ===================================================
echo   RiskGuard alert relay
echo   channel:  %CHANNEL%
echo   outbox:   %USERPROFILE%\Documents\NinjaTrader 8\RiskGuard\alerts_outbox.jsonl
echo   stop:     close this window, or Ctrl+C
echo ===================================================
echo.

:relay_loop
.venv\Scripts\python.exe -m scripts.riskguard.alert_relay --channel %CHANNEL%

:: A clean Ctrl+C also lands here. Restarting is still correct: the operator closing the
:: window is what stops it, and an unattended exit is exactly the case this loop exists for.
if errorlevel 2 (
    echo.
    echo [STOPPED] the relay refused to start -- this is a configuration problem and
    echo           restarting cannot fix it. Read the error above.
    pause
    exit /b 2
)

echo.
echo [RESTARTING] the relay exited; restarting in 10s. A dead relay is a dead alert channel.
timeout /t 10 /nobreak >nul
goto relay_loop
