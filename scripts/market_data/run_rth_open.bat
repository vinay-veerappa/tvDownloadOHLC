@echo off
cd /d "C:\Users\vinay\tvDownloadOHLC"
echo ==========================================
echo Capturing RTH Open Metrics (Straddle, IV, VIX)
echo Date: %date% %time%
echo ==========================================

python scripts/market_data/capture_rth_open.py

echo.
echo ==========================================
echo Capture Complete.
echo ==========================================
timeout /t 5
