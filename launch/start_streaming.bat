@echo off
echo Starting Streaming...
cd /d %~dp0..

start cmd /k "title DB Calendar Sync && python scripts\market_data\fetch_economic_calendar.py"
start cmd /k "title Chart Streamer && python -u scripts\streaming\stream_chart.py"
start cmd /k "title L2 Bookmap Engine && python -m scripts.streaming.l2_processor_engine SPY,QQQ,/ES"
echo Services launched.
pause
