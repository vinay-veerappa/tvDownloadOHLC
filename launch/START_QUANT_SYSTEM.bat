@echo off
set BASE_DIR=%~dp0..
cd /d %BASE_DIR%

:: Force Python to use UTF-8 for all console output to prevent UnicodeEncodeErrors with Emojis on Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

title QUANT UNIFIED SYSTEM - STARTUP
echo ===================================================
echo     STARTING QUANT UNIFIED HUD SYSTEM
echo ===================================================
echo.

:: 0. Sanity Check: Clean up old instances
echo 🧹 Performing System Sanity Check...
python scripts/utils/cleanup_system.py

:: 1. Start the Producer (Hub)
set HUB_PORT=8080
echo 🚀 Starting Schwab Unified Hub...
start "SCHWAB_HUB" cmd /k "python -m scripts.streaming.schwab_hub --port %HUB_PORT%"
timeout /t 10 /nobreak
echo ✅ Hub should be ready. Checking port %HUB_PORT%...
netstat -ano | findstr :%HUB_PORT%

:: 2. Start API Backend on Port 8000
echo 🚀 Starting API Backend...
start "QUANT_API" cmd /k "python -m api.main"
timeout /t 5 /nobreak

:: 3. Start Spoke: Charting & L1 Data
echo 🚀 Starting Charting Spoke...
start "SPOKE_CHART" cmd /k "python -m scripts.streaming.stream_chart"

:: 4. Start Spoke: L2 Bookmap Engine
::echo 🚀 Starting L2 Engine Spoke...
::start "SPOKE_L2" cmd /k "python -m scripts.streaming.l2_processor_engine"

:: 5. Start Web Dashboard
echo 🚀 Starting Web Dashboard...
start "WEB_DASHBOARD" cmd /k "cd web && npm run dev"

:: 6. [NEW] Start Spoke: Dealer Options Pipeline (GEX) — continuous 2-tier loop
echo 🚀 Starting Dealer Options Pipeline (loop mode)...
start "OPTIONS_GEX" cmd /k "python -m scripts.streaming.options.run_options_levels --loop --discord"

:: 6b. [NEW] Start unified Options + Narrative scheduler
echo 🚀 Starting Options + Narrative Scheduler (time-of-day mode)...
start "QUANT_SCHEDULER" cmd /k "launch\start_quant_scheduler.bat"

:: 7. [NEW] Start Spoke: Weekly Macro HTF Pipeline (Manual/Optional)
:: echo 🚀 Starting Macro HTF Pipeline...
:: start "MACRO_PIPELINE" cmd /k "python -m scripts.streaming.options.run_options_levels --macro"

:: 8. [NEW] Start Options Strategy Engine Runner
echo 🚀 Starting Options Strategy Engine...
start "STRATEGY_ENGINE" cmd /k "python scripts/libs_py/strategy_engine/runner.py"

pause
