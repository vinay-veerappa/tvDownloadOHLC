@echo off
echo ===================================================
echo     STARTING UNIFIED DASHBOARD SYSTEM
echo ===================================================
echo.
echo Launching Python Live Data Engine (2-Tier Priority Loop)...
start cmd /k "title Live Options Data Engine && cd /d %~dp0 && python -m scripts.streaming.options.run_options_levels --loop"

echo Starting Next.js Frontend...
cd web
npm run dev
pause
