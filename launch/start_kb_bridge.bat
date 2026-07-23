@echo off
:: ICT Knowledge Base Bridge (LanceDB RAG API) — port 8900
:: Producer repo: C:\Users\vinay\video2pdf\knowledge_ingest (the ingest tool)
:: LanceDB:      C:\Users\vinay\tvDownloadOHLC\data\knowledge\unified_knowledge.lancedb
::                (consumer repo OWNS produced data; override via KB_DATA_DIR)
:: Endpoints:     /health, /stats, /search (raw), /ask (RAG)
title KB BRIDGE - LanceDB RAG API (port 8900)

set PRODUCER_DIR=C:\Users\vinay\video2pdf
set PORT=8900
:: KB data lives in the CONSUMER repo (tvDownloadOHLC/data/knowledge).
:: Set KB_DATA_DIR so the producer's serve.py defaults resolve there.
set KB_DATA_DIR=C:\Users\vinay\tvDownloadOHLC\data\knowledge

cd /d %PRODUCER_DIR%
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Producer venv not found at %PRODUCER_DIR%\.venv
    echo         Create it in the video2pdf repo first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
set PYTHONPATH=.

echo ===================================================
echo   ICT Knowledge Base API Server (KB Bridge)
echo ===================================================
echo   Producer: %PRODUCER_DIR%
echo   DB:       %KB_DATA_DIR%\unified_knowledge.lancedb
echo   URL:      http://127.0.0.1:%PORT%
echo ===================================================
echo.

python -m knowledge_ingest.serve --port %PORT%

pause