@echo off
echo Starting FastAPI Backend...
call .venv\Scripts\activate
python -m uvicorn api.main:app --workers 4 --port 8000
pause
