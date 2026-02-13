@echo off
echo Starting Streaming...
python scripts\streaming\news_calendar_fetcher.py
python scripts\streaming\stream_chart.py
pause
