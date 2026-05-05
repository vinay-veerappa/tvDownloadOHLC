
import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import timedelta

def simulate_daily_path():
    # Load NQ1 Data
    path = Path("data/NQ1_1m.parquet")
    df = pd.read_parquet(path)
    
    # Load Sessions to find "Long True" days (NY2 context)
    with open("data/NQ1_profiler.json", "r") as f:
        sessions = json.load(f)
    
    # Find dates where NY2 was Long True
    lt_dates = [s['date'] for s in sessions if s['session'] == 'NY2' and s['status'] == 'Long True']
    print(f"Found {len(lt_dates)} Long True days.")
    
    # Let's take the first 50 days (for speed)
    lt_dates = lt_dates[:50]
    
    all_paths = []
    
    for d in lt_dates:
        # Start at 18:00 prev day
        start_ts = pd.Timestamp(d) - timedelta(days=1)
        start_ts = start_ts.replace(hour=18, minute=0)
        end_ts = start_ts + timedelta(hours=22)
        
        try:
            subset = df.loc[start_ts:end_ts]
            if subset.empty: continue
            
            # Static Anchor: Asia Open
            anchor = subset.iloc[0]['open']
            
            # Continuous Path
            path = (subset['high'] - anchor) / anchor * 100
            # Normalize index to minutes from start
            path.index = ((path.index - start_ts).total_seconds() / 60).astype(int)
            all_paths.append(path)
        except:
            continue
            
    # Combine and median
    combined = pd.concat(all_paths, axis=1)
    median_path = combined.median(axis=1)
    
    print("\n--- MEDIAN PATH (Static Anchor) ---")
    print(median_path.iloc[::60]) # Every hour
    
    return median_path

if __name__ == "__main__":
    simulate_daily_path()
