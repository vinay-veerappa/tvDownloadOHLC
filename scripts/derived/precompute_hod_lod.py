"""
Pre-compute HOD/LOD Time Analysis - Optimized Version

Uses vectorized pandas operations for speed.
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from collections import Counter
import sys
import os

sys.path.append(os.getcwd())

def precompute_hod_lod(ticker="NQ1"):
    from api.services.data_loader import DATA_DIR
    
    from api.services.data_loader import load_parquet
    df = load_parquet(ticker, "1m")
    
    if df is None or df.empty:
        print(f"Error: Data for {ticker} not found or empty")
        return
    
    # Convert Unix 'time' column to US/Eastern index
    # This is the absolute source of truth for alignment.
    df['dt_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.set_index('dt_utc').tz_convert('US/Eastern')
    
    # Force drop the old 'time' column to avoid confusion
    if 'time' in df.columns:
        df = df.drop(columns=['time'])
        
    # Add new EST-based time columns
    df['date'] = df.index.date
    df['time'] = df.index.strftime('%H:%M')
    df['hour'] = df.index.hour
    
    print(f"  [DEBUG] Index TZ: {df.index.tz}, Sample Time: {df['time'].iloc[0]}")
    
    # Session definitions (hour ranges for simplicity)
    session_hours = {
        "Asia": list(range(18, 24)) + list(range(0, 3)),  # 18:00-02:59
        "London": list(range(3, 8)),  # 03:00-07:59
        "NY1": list(range(8, 12)),  # 08:00-11:59
        "NY2": list(range(12, 16)),  # 12:00-15:59
    }
    
    print("Processing daily HOD/LOD...")
    
    # --- Daily HOD/LOD using groupby ---
    # Find the time of max high per day
    idx_hod = df.groupby('date')['high'].idxmax()
    idx_lod = df.groupby('date')['low'].idxmin()
    
    hod_times = df.loc[idx_hod.dropna(), 'time'].tolist()
    lod_times = df.loc[idx_lod.dropna(), 'time'].tolist()
    
    print(f"  [DEBUG] Sample hod_times: {hod_times[:10]}")
    print(f"Daily: {len(hod_times)} HOD samples, {len(lod_times)} LOD samples")
    
    # --- Session High/Low ---
    print("Processing session High/Low...")
    session_results = {}
    
    for sess_name, hours in session_hours.items():
        sess_df = df[df['hour'].isin(hours)]
        
        if sess_df.empty:
            session_results[sess_name] = {
                "high_stats": {"median": None, "mode": None, "count": 0, "distribution": {}},
                "low_stats": {"median": None, "mode": None, "count": 0, "distribution": {}},
            }
            continue
        
        # Find time of high/low within each session per day
        idx_high = sess_df.groupby('date')['high'].idxmax()
        idx_low = sess_df.groupby('date')['low'].idxmin()
        
        high_times = sess_df.loc[idx_high.dropna(), 'time'].tolist()
        low_times = sess_df.loc[idx_low.dropna(), 'time'].tolist()
        
        session_results[sess_name] = {
            "high_times": high_times,
            "low_times": low_times,
        }
        print(f"  {sess_name}: {len(high_times)} high samples, {len(low_times)} low samples")
    
    # --- Calculate stats ---
    def calc_stats(times_list):
        if not times_list:
            return {"median": None, "mode": None, "count": 0, "distribution": {}}
        
        def to_mins(t):
            h, m = map(int, t.split(':'))
            return h * 60 + m
        
        def to_time(mins):
            return f"{mins // 60:02d}:{mins % 60:02d}"
        
        minutes = [to_mins(t) for t in times_list]
        sorted_mins = sorted(minutes)
        mid = len(sorted_mins) // 2
        median_mins = sorted_mins[mid] if len(sorted_mins) % 2 else (sorted_mins[mid-1] + sorted_mins[mid]) // 2
        
        counts = Counter(times_list)
        mode_time = counts.most_common(1)[0][0]
        
        # Hourly distribution
        hourly = {}
        for t in times_list:
            hour = t[:2] + ":00"
            hourly[hour] = hourly.get(hour, 0) + 1
        
        return {
            "median": to_time(median_mins),
            "mode": mode_time,
            "count": len(times_list),
            "distribution": dict(sorted(hourly.items())),
        }
    
    results = {
        "daily": {
            "hod_times": hod_times,  # Raw times for dynamic rebucketing
            "lod_times": lod_times,
            "hod_stats": calc_stats(hod_times),
            "lod_stats": calc_stats(lod_times),
        },
        "sessions": {},
        "metadata": {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
        }
    }
    
    for sess_name, sess_data in session_results.items():
        if "high_times" in sess_data:
            results["sessions"][sess_name] = {
                "high_stats": calc_stats(sess_data["high_times"]),
                "low_stats": calc_stats(sess_data["low_times"]),
            }
        else:
            results["sessions"][sess_name] = sess_data
    
    # Save
    output_path = DATA_DIR / f"{ticker}_hod_lod.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    print(f"Daily HOD: Median={results['daily']['hod_stats']['median']}, Mode={results['daily']['hod_stats']['mode']}")
    print(f"Daily LOD: Median={results['daily']['lod_stats']['median']}, Mode={results['daily']['lod_stats']['mode']}")

if __name__ == "__main__":
    import time
    start = time.time()
    precompute_hod_lod("NQ1")
    print(f"Completed in {time.time() - start:.2f}s")
