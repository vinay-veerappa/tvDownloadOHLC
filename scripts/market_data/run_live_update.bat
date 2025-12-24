@echo off
cd /d "C:\Users\vinay\tvDownloadOHLC"
echo ==========================================
echo Starting Unified Data Synchronization
echo Date: %date% %time%
echo ==========================================

echo.
echo [1/2] Syncing from Dolt Database (History)...
echo ------------------------------------------
call python scripts/market_data/dolt_em_sync.py

echo.
echo [2/2] Updating Live Data from Schwab (Today)...
echo ------------------------------------------
call python scripts/market_data/update_em_history_live.py

echo.
echo ==========================================
echo Synchronization Complete.
echo ==========================================
timeout /t 10
