@echo off
set BASE_DIR=%~dp0..
cd /d "%BASE_DIR%"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

title CSP CANDIDATE RANKING - BEN METHODOLOGY

echo ==========================================================
echo 🚀 Launching Automated CSP Ranking ^& Scoring Pipeline...
echo ==========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m scripts.csp_ranking.cli --open-browser %*

pause
