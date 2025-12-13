
import pandas as pd
import json
from pathlib import Path
from datetime import time, timedelta
import numpy as np

# Load Data
def load_data():
    # 1. Load Touch Data (My Data)
    # We need the source dates/times, which are in `_level_touches.json`
    # But `_level_touches` only has "first touch time". 
    # To do a proper "Windowed Comparison", we technically need the RAW touches or recalculate them.
    # The user asks for "Comparison Table".
    
    # Actually, `precompute_level_stats.py` generates the histograms for the "NY1" (08-12) window by default logic (or whatever was set).
    # To get "Full Trading Day" stats AND "8-12" stats, we might need to recalculate hits for those specific windows on the fly.
    
    # Let's use the Raw Prices (Parquet) to check touches in the 2 windows?
    # Or modify `precompute_level_touches.py` to output multiple windows?
    # 
    # Faster approach: "First Touch" in `level_touches.json` tells us WHEN it was touched.
    # If touch_time is e.g. "09:30", it counts for "Full Day" AND "8-12".
    # If touch_time is "18:05", it counts for "Full Day" but NOT "8-12".
    # This assumes the "First Touch" is the one that matters.
    # The Reference "ny" keys probably mean "Hits during NY session".
    # If a level was touched in London (04:00) AND NY (10:00), does Reference count it for NY?
    # Usually "Daily Stats" counts "First touch of the session/day".
    # If Reference 'ny' means "Was this level touched between 08:00 and 12:00?", then we check if ANY touch happened then.
    # The `level_touches.json` only stores the *first* touch of the trading day.
    # This is a limitation. If first touch is 18:05, we stop checking. 
    # So we don't know if it was touched *again* at 09:00.
    
    # CONCLUSION: We must scan the 1m data to properly answer "Was it touched in 8-12?".
    # We cannot rely solely on `level_touches.json` if it only stores the first daily touch.
    pass

DATA_DIR = Path("data")
REF_PATH = Path("docs/ReferenceDailyLevels.json")

def time_to_min(t_str):
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

def run_comparison():
    print("Loading Reference Data...")
    with open(REF_PATH) as f:
        ref = json.load(f)

    # Reference counts are sum of histogram values
    # ref['ny'] -> 08:00 - 12:00 (Presumably)
    # ref['daily'] -> Full Day?
    
    ref_counts = {}
    for scope in ['ny', 'daily', 'p12']:
        if scope not in ref: continue
        ref_counts[scope] = {}
        for lvl, hist in ref[scope].items():
            total_hits = sum(hist.values())
            ref_counts[scope][lvl] = total_hits

    print("Reference Counts Loaded.")
    
    # Load 1m Data
    print("Loading 1m Data for Recalculation...")
    df = pd.read_parquet(DATA_DIR / "NQ1_1m.parquet")
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df = df.tz_convert('US/Eastern')

    # Needed for Mids/Opens
    # Load Profiler/Daily Levels
    # This is expensive validation.
    # Maybe we just use the precomputed `level_touches.json` for "Full Day" (since it scans full day)
    # And we assume 'ny' reference requires a rescan?
    
    # Let's simplify. 
    # 1. Full Day: `level_touches.json` (My Data) vs `ref['daily']` (Reference).
    # 2. 8-12 Time: We need to calc this.
    
    with open(DATA_DIR / "NQ1_level_touches.json") as f:
        my_touches = json.load(f)
        
    with open(DATA_DIR / "NQ1_profiler.json") as f:
        profiler = json.load(f)
    prof_map = {p['date']: p for p in profiler}

    # Recalculate 8-12 Hits
    print("Calculating 8-12 Hits...")
    
    hits_8_12 = {
        'pdh': 0, 'pdl': 0, 'pdm': 0, 
        'daily_open': 0, 'midnight_open': 0, 'open_0730': 0,
        'asia_mid': 0, 'london_mid': 0, 'ny1_mid': 0, 'ny2_mid': 0,
        'p12h': 0, 'p12l': 0, 'p12m': 0
    }
    
    valid_days = 0
    
    # Helper to check touch in window
    # Optimized: We iterate days in my_touches (which has the levels)
    # Then slice DF for 08:00-12:00
    
    # Need to group DF by day first to avoid repeated indexing
    df_shifted = df.copy()
    df_shifted.index = df.index - pd.Timedelta(hours=8) # Shift so 08:00 starts the "day block" for easy grouping? No.
    # Just group by date. 08:00-12:00 is same calendar day.
    
    grouped = df.groupby(df.index.date)
    
    for date_obj, group in grouped:
        d_str = date_obj.strftime('%Y-%m-%d')
        if d_str not in my_touches: continue
        
        day_rec = my_touches[d_str]
        
        # Slice 08:00 - 12:00
        # Check strict window? 
        start_t = time(8, 0)
        end_t = time(12, 0)
        
        window = group.between_time(start_t, end_t)
        if window.empty: continue
        
        valid_days += 1
        
        l_high = window['high'].max()
        l_low = window['low'].min()
        
        # Check levels
        def check(lvl_name, rec_key=None):
            if rec_key is None: rec_key = lvl_name
            
            if rec_key not in day_rec: return False
            lvl_val = day_rec[rec_key]['level']
            if lvl_val is None: return False
            
            # Touch logic
            return (l_low <= lvl_val <= l_high)

        if check('pdh'): hits_8_12['pdh'] += 1
        if check('pdl'): hits_8_12['pdl'] += 1
        if check('pdm'): hits_8_12['pdm'] += 1
        
        if check('p12h'): hits_8_12['p12h'] += 1
        if check('p12l'): hits_8_12['p12l'] += 1
        if check('p12m'): hits_8_12['p12m'] += 1

        if check('daily_open'): hits_8_12['daily_open'] += 1
        if check('midnight_open'): hits_8_12['midnight_open'] += 1
        if check('open_0730'): hits_8_12['open_0730'] += 1

        if check('asia_mid'): hits_8_12['asia_mid'] += 1
        if check('london_mid'): hits_8_12['london_mid'] += 1
        # NY1 Mid established at 12:00? Cannot be hit in 8-12?
        # User says "Asia mid can never be broken *during* Asia".
        # So NY1 mid valid after 12:00. Thus 0 hits in 8-12.
        # We can skip NY1/NY2 for 8-12 window.
        
    # Build Table
    # My Full Day (from touches json)
    my_full = {k: 0 for k in hits_8_12}
    total_days = len(my_touches)
    
    for d, rec in my_touches.items():
        for k in my_full:
            if k in rec and rec[k]['touched']:
                my_full[k] += 1

    # Map keys to Ref keys
    # Ref Keys: ny (08-12?), daily (Full?)
    # PDH -> pdh
    
    row_fmt = "{:<20} | {:<10} | {:<10} | {:<10} | {:<10} | {:<10}"
    print(row_fmt.format("Level", "Ref(Day)", "My(Day)", "Diff(Day)", "Ref6(NY)", "My(8-12)"))
    print("-" * 85)
    
    levels = [
        ('pdh', 'pdh'), ('pdl', 'pdl'), ('pdm', 'pdm'),
        ('daily_open', 'daily_open'), ('midnight_open', 'midnight_open'), ('open_0730', 'open_0730'),
        ('p12h', 'p12h'), ('p12l', 'p12l'), ('p12m', 'p12m'),
        ('asia_mid', 'asia_mid'), ('london_mid', 'london_mid')
    ]
    
    # We assume ref['ny'] is the 08:00-12:00 window? Or 09:30-16:00?
    # User asked for "8-12 time". Let's assume Ref 'ny' matches 8-12 or similar.
    # Ref 'daily' matches Full Day.
    
    for my_k, ref_k in levels:
        ref_d = ref_counts.get('daily', {}).get(ref_k, "-")
        ref_ny = ref_counts.get('ny', {}).get(ref_k, "-")
        
        my_d = my_full.get(my_k, 0)
        my_ny = hits_8_12.get(my_k, 0)
        
        diff_d = my_d - ref_d if isinstance(ref_d, int) else "-"
        
        print(row_fmt.format(my_k, ref_d, my_d, diff_d, ref_ny, my_ny))

if __name__ == "__main__":
    run_comparison()
