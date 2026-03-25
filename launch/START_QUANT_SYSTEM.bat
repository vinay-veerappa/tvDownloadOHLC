@echo off
set BASE_DIR=%~dp0..
cd /d %BASE_DIR%

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
echo 🚀 Starting L2 Engine Spoke...
start "SPOKE_L2" cmd /k "python -m scripts.streaming.l2_processor_engine"

:: 5. Start Web Dashboard
echo 🚀 Starting Web Dashboard...
start "WEB_DASHBOARD" cmd /k "cd web && npm run dev"

:: 6. [NEW] Start Spoke: Dealer Options Pipeline (GEX)
echo 🚀 Starting Dealer Options Pipeline...
start "OPTIONS_GEX" cmd /k "python -m scripts.streaming.options.run_options_levels --loop"

:: 7. [NEW] Start Spoke: Weekly Macro HTF Pipeline (Manual/Optional)
:: echo 🚀 Starting Macro HTF Pipeline...
:: start "MACRO_PIPELINE" cmd /k "python -m scripts.streaming.options.run_options_levels --macro"

pause
