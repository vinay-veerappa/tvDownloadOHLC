@echo off
set BASE_DIR=%~dp0..
cd /d %BASE_DIR%

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

title MASTER DAILY SCANNER SUITE (Qullamaggie, Minervini, Stockbee, Ben CSP)

echo ==========================================================
echo  Launching Master Daily Scanner Suite...
echo  (Equity Momentum + Cash-Secured Puts + Credit Spreads)
echo ==========================================================
echo.

.\.venv\Scripts\python.exe -m scripts.screener.run_all_scans

pause
