@echo off
echo ===================================================
echo     STARTING UNIFIED DASHBOARD SYSTEM
echo ===================================================
echo.
cd /d %~dp0..

REM echo Launching Python Live Data Engine (2-Tier Priority Loop)...
REM start cmd /k "title Live Options Data Engine && python -m scripts.streaming.options.run_options_levels --loop --discord"

echo Starting Next.js Frontend...
cd web
npm run dev
pause
