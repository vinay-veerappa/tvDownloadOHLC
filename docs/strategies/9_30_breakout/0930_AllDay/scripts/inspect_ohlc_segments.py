
"""
OHLC Data Inspector
===================
Fetches 1-minute OHLC data for the specific Case Study windows.
Goal: Visualize the "Wick" and Volatility.
"""

import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())
from api.services.data_loader import load_parquet

# Targets: Date + Minute
TARGETS = [
    ("2025-05-28", ["09:40", "09:45", "09:50"]),
    ("2025-06-25", ["09:40", "10:15", "10:55"]),
    ("2025-09-12", ["09:40", "09:50", "10:25"])
]

def inspect():
    print("Loading NQ1 1m Data...")
    df = load_parquet("NQ1", "1m")
    
    if df is None:
        print("Could not load data.")
        return
        
    # TZ Conversion
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
    df['date_str'] = df['dt'].dt.date.astype(str)
    df['time_str'] = df['dt'].dt.strftime('%H:%M')
    
    for t_date, t_times in TARGETS:
        print(f"\n=== {t_date} OHLC ===")
        print(f"{'Time':<8} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10} | {'Range':<8} | {'Body':<8}")
        print("-" * 80)
        
        # Get Data for Date
        day_df = df[df['date_str'] == t_date]
        
        # Filter for Times
        # We want the exact minutes requested + maybe 1 before/after for context?
        # Let's just show the requested ones first.
        
        rows = day_df[day_df['time_str'].isin(t_times)]
        
        for idx, row in rows.iterrows():
            o = row['open']
            h = row['high']
            l = row['low']
            c = row['close']
            r = h - l
            b = abs(c - o)
            
            print(f"{row['time_str']:<8} | {o:<10.2f} | {h:<10.2f} | {l:<10.2f} | {c:<10.2f} | {r:<8.2f} | {b:<8.2f}")

if __name__ == "__main__":
    inspect()
