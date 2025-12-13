
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time, timedelta

DATA_FILE = Path("data/NQ1_level_stats.json")
OUTPUT_DIR = Path("data/csv_reports")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def min_to_time(minutes):
    # Anchor is 18:00 D-1
    # 0 -> 18:00
    # 60 -> 19:00
    # ...
    # 360 (6hr) -> 00:00
    base = pd.Timestamp("2000-01-01 18:00:00")
    t = base + timedelta(minutes=minutes)
    return t.strftime("%H:%M")

def run_export():
    print(f"Loading {DATA_FILE}...")
    with open(DATA_FILE) as f:
        data = json.load(f)

    # Structure: data['All'][LevelName] = { 'hits': ..., 'times': [min, min, ...], 'total': ... }
    
    if 'All' not in data:
        print("Error: 'All' key not found in stats.")
        return

    all_stats = data['All'] # Use 'All' context for total hits
    
    # Levels to process
    # Groups
    groups = {
        'PriorDay': ['pdh', 'pdl', 'pdm'], # 'PDH' etc might be keys
        'TimeOpens': ['daily_open', 'midnight_open', 'open_0730'],
        'P12': ['p12h', 'p12l', 'p12m'],
        'Mids': ['asia_mid', 'london_mid', 'ny1_mid', 'ny2_mid']
    }

    # Identify actual keys in JSON (might be PascalCase vs snake_case)
    # The script output 'pdh', 'pdl' etc (lowercase) in previous steps. 
    # Let's dynamically find them.
    
    available_keys = list(all_stats.keys())
    print(f"Available Levels: {available_keys}")
    
    # Create normalized mapping
    # e.g. 'PDH' -> matches 'pdh' group
    key_map = {}
    for k in available_keys:
        k_lower = k.lower()
        key_map[k] = k # Default
        # Find group
        for g_name, members in groups.items():
            if k_lower in members:
                # Assign to group? No, just map members to real key
                pass

    # Reverse Map: Group Member -> Real Key
    member_to_real = {}
    for k in available_keys:
        member_to_real[k.lower()] = k
        
    # Define Intervals (15 min)
    # Day is 18:00 to 17:00 = 23 hours = 1380 minutes.
    # 0 to 1380, step 15.
    bins = list(range(0, 1381, 15))
    bin_labels = [min_to_time(b) for b in bins[:-1]]
    
    # Process each group
    for g_name, members in groups.items():
        print(f"Processing Group: {g_name}")
        
        # DF for this group
        # Columns: Time, Level1_Hits, Level1_Rate, Level2_Hits...
        
        group_data = {'Time': bin_labels}
        
        found_any = False
        
        for m in members:
            real_k = member_to_real.get(m)
            if not real_k: continue
            if real_k not in all_stats: continue
            
            found_any = True
            
            stats = all_stats[real_k]
            total_sessions = stats.get('total', 0)
            times = stats.get('times', [])
            
            # Histogram
            hist, _ = np.histogram(times, bins=bins)
            
            # Add to data
            group_data[f"{m}_hits"] = hist
            
            # Rate calculation (Hits / Total Sessions * 100)
            # This is "Hit Probability per 15m candle"
            # i.e. "In 100 days, how many times was it hit in this 15m window?"
            if total_sessions > 0:
                rates = [(h / total_sessions) * 100 for h in hist]
            else:
                rates = [0] * len(hist)
                
            group_data[f"{m}_rate"] = [f"{r:.1f}%" for r in rates]
            
        if found_any:
            df = pd.DataFrame(group_data)
            # Add Total Sum row? No, time buckets.
            
            csv_path = OUTPUT_DIR / f"{g_name}_15min_stats.csv"
            df.to_csv(csv_path, index=False)
            print(f"Saved {csv_path}")

    # Generate Individual Level CSVs (or one big joined one?)
    # "put the comparison ... into a csv with multuple csv"
    # User might want raw numbers.
    
    # Let's also do a Master CSV with JUST Hit Counts for ALL levels
    master_data = {'Time': bin_labels}
    for k in available_keys:
        stats = all_stats[k]
        times = stats.get('times', [])
        hist, _ = np.histogram(times, bins=bins)
        master_data[k] = hist

    master_df = pd.DataFrame(master_data)
    master_path = OUTPUT_DIR / "All_Levels_Hits_15min.csv"
    master_df.to_csv(master_path, index=False)
    print(f"Saved Combined Hits to {master_path}")

if __name__ == "__main__":
    run_export()
