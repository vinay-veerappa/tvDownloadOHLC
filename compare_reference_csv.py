
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time, timedelta

DATA_FILE = Path("data/NQ1_level_stats.json")
REF_FILE = Path("docs/ReferenceDailyLevels.json")
OUTPUT_DIR = Path("data/csv_reports")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def my_min_to_ref_min(my_min):
    # My Min: 0 = 18:00
    # Ref Min: 1080 = 18:00 (Minutes from Midnight)
    
    # 0 -> 1080
    # 360 (00:00) -> 1440 -> 0?
    # 600 (04:00) -> 240
    
    # Formula: (my_min + 1080) % 1440
    
    ref = (my_min + 1080) % 1440
    return str(ref)

def min_to_time(minutes_from_1800):
    base = pd.Timestamp("2000-01-01 18:00:00")
    t = base + timedelta(minutes=minutes_from_1800)
    return t.strftime("%H:%M")

def run_comparison():
    print("Loading Data...")
    with open(DATA_FILE) as f:
        my_data = json.load(f)['All']
    
    with open(REF_FILE) as f:
        ref_data = json.load(f)
        
    # Standardize Ref Structure
    # ref_data keys: 'daily', 'ny', 'p12', 'asia'
    # We want to compare against the BEST match.
    # 'daily' likely covers full day? 
    # 'ny' covers 08:00-...?
    
    # Let's try to find keys in 'daily' first, fallback to others?
    # No, let's map My Levels to Ref Sections
    
    # Create Time Index (5 min steps)
    # 0 to 1440-5 = 1435
    bins = list(range(0, 1440, 5)) 
    
    rows = []
    
    # We want columns: Time, My_PDH, Ref_PDH, My_PDL, Ref_PDL...
    
    # Prepare Data Dictionary
    data_dict = {'Time': [min_to_time(b) for b in bins]}
    
    # Which levels to compare? All available in My Data
    levels_to_compare = list(my_data.keys())
    # Sort them?
    # Use 'count' (number of hits) to filter active levels
    levels_to_compare = sorted([k for k in levels_to_compare if my_data[k].get('count', 0) > 0])
    
    for lvl in levels_to_compare:
        print(f"Processing {lvl}...")
        
        # 1. My Hits (5 min bucket)
        times = my_data[lvl]['times']
        hist, _ = np.histogram(times, bins=list(range(0, 1441, 5)))
        
        data_dict[f"My_{lvl}"] = hist
        
        # 2. Ref Hits
        # Find Ref Section
        # Try 'daily', then 'ny', then 'p12', then 'asia'
        ref_src = None
        ref_lvl_key = lvl
        
        # Map nice names to possible ref names
        # My: daily_open -> Ref: open?
        # My: midnight_open -> Ref: midnight?
        
        # Heuristic search
        found = False
        for section in ['daily', 'ny', 'p12', 'asia']:
            if section not in ref_data: continue
            
            # Check for exact match or simple variance
            candidates = [lvl, lvl.replace('_', ''), lvl.upper(), lvl.lower()]
            # Specific mappings
            if lvl == 'daily_open': candidates.append('open')
            if lvl == 'midnight_open': candidates.append('open') # valid in London/Midnight context?
            if lvl == 'open_0730': candidates.append('open') 
            if lvl == 'pdm': candidates.append('mid')
            
            for c in candidates:
                if c in ref_data[section]:
                    ref_src = ref_data[section][c]
                    found = True
                    break
            if found: break
        
        ref_col = []
        if found and ref_src:
            for b in bins:
                r_key = my_min_to_ref_min(b)
                val = ref_src.get(r_key, 0)
                ref_col.append(val)
        else:
            ref_col = [0] * len(bins)
            
        data_dict[f"Ref_{lvl}"] = ref_col
        
        # 3. Diff
        data_dict[f"Diff_{lvl}"] = [m - r for m, r in zip(hist, ref_col)]

    df = pd.DataFrame(data_dict)
    
    # Reorder columns: Time, My_Lvl1, Ref_Lvl1, Diff_Lvl1, ...
    cols = ['Time']
    for lvl in levels_to_compare:
        cols.extend([f"My_{lvl}", f"Ref_{lvl}", f"Diff_{lvl}"])
        
    df = df[cols]
    
    out_path = OUTPUT_DIR / "Comparison_5min_stats.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved Side-by-Side Comparison to {out_path}")

if __name__ == "__main__":
    run_comparison()
