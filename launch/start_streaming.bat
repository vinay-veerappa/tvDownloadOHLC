@echo off
echo Starting Streaming...
cd /d %~dp0..

start cmd /k "title News Fetcher && python scripts\streaming\news_calendar_fetcher.py"
start cmd /k "title Chart Streamer && python scripts\streaming\stream_chart.py"
start cmd /k "title L2 Bookmap Engine && python -m scripts.streaming.l2_processor_engine SPY,QQQ,/ES"
echo Services launched.
pause
