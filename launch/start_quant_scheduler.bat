@echo off
set BASE_DIR=%~dp0..
cd /d %BASE_DIR%

:: Force UTF-8 console output for emojis / wide chars
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

title QUANT SCHEDULER - Options + Narratives

echo ===================================================
echo     STARTING QUANT OPTIONS + NARRATIVE SCHEDULER
echo ===================================================
echo.
echo This window runs the unified APScheduler:
echo   - Dealer levels pipeline at config times
echo   - Trader narratives (premarket/open/intraday/close)
echo   - Weekly briefing on Fridays
echo.
echo Press Ctrl-C to stop. Do NOT close during trading hours.
echo.

:: Discord is disabled by default in config.py; keep it explicit here.
.\.venv\Scripts\python.exe -m scripts.streaming.options.run_options_levels --schedule --narratives-only --no-discord

pause
