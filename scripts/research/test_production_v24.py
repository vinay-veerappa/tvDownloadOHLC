
import os
import sys
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime

# Add project root to python path
sys.path.append(os.getcwd())

from api.services.profiler_service import ProfilerService

async def test_v24():
    ticker = "NQ1"
    # Get some sessions to test with
    print(f"Loading sessions for {ticker}...")
    stats = ProfilerService.analyze_profiler_stats(ticker, days=15)
    sessions = stats.get('sessions', [])
    
    if len(sessions) < 10:
        print(f"Only found {len(sessions)} sessions. Data might be sparse.")
        return

    # Filter for Asia sessions on a reliable date (e.g., 3 days ago)
    available_dates = sorted(list(set(s['date'] for s in sessions)))
    print(f"Available dates: {available_dates}")
    
    if len(available_dates) < 3:
        print("Not enough dates found.")
        return
        
    test_date = available_dates[-3] # Use 3rd to last date to ensure 22h span
    asia_sess_list = [s for s in sessions if s['date'] == test_date and s['session'] == 'Asia']
    
    if not asia_sess_list:
        print(f"No Asia session found for {test_date}")
        return
    
    asia_sess = asia_sess_list[0]
    
    # Synthetic Daily session
    daily_sess = [{
        'start_time': asia_sess['start_time'],
        'open': asia_sess['open'],
        'date': test_date,
        'session': 'Daily'
    }]
    
    print(f"Using test date: {test_date}, Start Time: {asia_sess['start_time']}")
    
    # Check data bounds
    df = ProfilerService._cache.get(ticker)
    if df is not None:
        print(f"Data Bounds: {df.index[0]} to {df.index[-1]}")
    
    print(f"Generating V24 composite path for {test_date}...")
    # Daily duration is 22 hours
    result = ProfilerService.generate_composite_path(ticker, daily_sess, duration_hours=22.0, bucket_minutes=5)
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    median_path = result.get('median', [])
    print(f"Path generated with {len(median_path)} points.")
    
    # Check for the squeeze at 07:30 (Minute 810)
    # Minute 810 / 5 = 162 index approx
    p1 = [p for p in median_path if p['time'] in ["07:25", "07:30", "07:35"]]
    print("\nPoints around 07:30 (Switch to London Mid):")
    for p in p1:
        print(f"Time: {p['time']}, High: {p['high']}%")

    # Check for the switch at 12:00 (Minute 1080)
    p2 = [p for p in median_path if p['time'] in ["11:55", "12:00", "12:05"]]
    print("\nPoints around 12:00 (Switch to NY AM Mid):")
    for p in p2:
        print(f"Time: {p['time']}, High: {p['high']}%")

    # Last points
    last_points = median_path[-3:]
    print("\nEnd of Day Points:")
    for p in last_points:
        print(f"Time: {p['time']}, High: {p['high']}%")

if __name__ == "__main__":
    asyncio.run(test_v24())
