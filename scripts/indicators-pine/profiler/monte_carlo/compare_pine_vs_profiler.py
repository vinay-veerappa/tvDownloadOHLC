
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from pathlib import Path
from datetime import datetime, timedelta

# --- 1. Load Precomputed Profiler JSON (Truth) ---
def load_json_sessions():
    path = Path("data/NQ1_profiler.json")
    if not path.exists():
        print("Error: NQ1_profiler.json not found.")
        return []
    with open(path, 'r') as f:
        return json.load(f)

# --- 2. Filter Logic (Simulating 'Long True') ---
def filter_long_true(sessions):
    # Depending on how the Pine Generator filtered, we replicate it.
    # The Pine Model LT usually corresponds to NY2 Session Context with Outcome = 1 (Long True) ??
    # OR is it just ANY session that was Long True?
    # Inspecting generate_profiler_pine.py (lines 92-96) suggests:
    # "session": "NY2", "outcome": 1 (Long True)
    # But wait, does it mean we only look at NY2 sessions?
    # Or does it mean we use NY2 *context* to filter for days where NY2 was Long True?
    
    # Let's assume the Pine Model is based on:
    # Target Session: NY2 (as per generator comment)
    # Outcome: Long True
    
    candidates = []
    for s in sessions:
        if s.get('session') == 'NY2' and s.get('status') == 'Long True':
            candidates.append(s)
    return candidates

# --- 3. Composite Path Calculation (Simplified V24 Logic) ---
# We need to calculate the median High/Low path for these sessions.
# Since we don't have the full dataframe in this script easily (parquet loading is heavy),
# We will use a simplified approach IF the JSON has enough info. 
# JSON has `high_time`, `low_time`, `high_pct`, `low_pct`.
# It DOES NOT have minute-by-minute paths.
# Therefore, we MUST load the Parquet data to generate the true path.

def load_parquet_data():
    path = Path("data/NQ1_1m.parquet")
    if not path.exists():
        return None
    return pd.read_parquet(path)

def generate_median_path(sessions, df):
    # Simplified version of ProfilerService.generate_composite_path
    # We will just plot the 5-minute bucketed median path relative to Session Open
    
    all_rel_highs = {} # key: minute_offset, val: list of %
    all_rel_lows = {}
    
    # Pre-process DF for speed
    df = df.sort_index()
    
    count = 0
    for s in sessions:
        start_ts = pd.Timestamp(s['start_time']).tz_convert(df.index.tz)
        # We want to track for say 7 hours (420 mins) or full day?
        # Pine generator usually grabs ~15 hours for "Daily" context or session duration.
        # Let's target 7 hours (07:30 to 14:30) for now if it's NY1/NY2?
        # Wait, if we are filtering NY2 (11:30), the path starts at 11:30.
        # BUT the Pine script drawing shows the FULL DAY (Asia -> NY2).
        # So likely the filter finds the DATES where NY2 was Long True,
        # then generates the path for the WHOLE DAY (starting 18:00 prev day).
        
        # KEY INSIGHT: The Pine Script draws starting from 0 (18:00).
        # So we must identify the TRADING DATES where NY2 = Long True.
        # Then fetch data starting from 18:00 (Asia Open) of that trading day.
        
        trading_date = s['date']
        
        # Find Asia Start for this trading date
        # Asia starts 18:00 on (Date - 1)
        asia_start_str = (pd.Timestamp(trading_date) - timedelta(days=1)).strftime('%Y-%m-%d') + " 18:00"
        asia_start_ts = pd.Timestamp(asia_start_str).tz_localize(df.index.tz)
        
        end_ts = asia_start_ts + timedelta(hours=23) # Full day
        
        try:
            subset = df.loc[asia_start_ts:end_ts]
            if subset.empty: continue
            
            # Anchor: Open of Asia (which is subset.iloc[0]['open'])
            anchor_price = subset.iloc[0]['open']
            
            for ts, row in subset.iterrows():
                delta_m = int((ts - asia_start_ts).total_seconds() / 60)
                if delta_m < 0: continue # specific tz inconsistency protection
                
                pct_h = (row['high'] - anchor_price) / anchor_price * 100
                pct_l = (row['low'] - anchor_price) / anchor_price * 100
                
                if delta_m not in all_rel_highs: all_rel_highs[delta_m] = []
                if delta_m not in all_rel_lows: all_rel_lows[delta_m] = []
                
                all_rel_highs[delta_m].append(pct_h)
                all_rel_lows[delta_m].append(pct_l)
                
            count += 1
        except Exception as e:
            continue
            
    print(f"Processed {count} sessions for median path.")
    
    # Calculate Medians
    minutes = sorted(all_rel_highs.keys())
    med_highs = [np.median(all_rel_highs[m]) for m in minutes]
    med_lows = [np.median(all_rel_lows[m]) for m in minutes]
    
    return minutes, med_highs, med_lows

# --- 4. Load Pine Script Data (Simulating Extraction) ---
def load_pine_data():
    pine_path = Path(r"c:\Users\vinay\tvDownloadOHLC\scripts\profiler\ProfilerData_Model_LT.pine")
    
    with open(pine_path, 'r') as f:
        content = f.read()

    def extract_array(name):
        # matches array.from(1, 2, 3...)
        pat = re.compile(rf"{name}\(\) =>\s+array\.from\(([\d\.,\s-]+)\)")
        m = pat.search(content)
        if m:
            return [float(x) for x in m.group(1).split(',')]
        return []

    times = extract_array("_get_times_0")
    highs = extract_array("_get_high_0")
    lows = extract_array("_get_low_0")
    
    # Pine data is scaled by some factor during generation?
    # In verify_pine_model.py, we saw values like 0.02.
    # If this is 2%, then it is ALREADY percentage * 0.01 (decimal representation of percent).
    # So we should multiply by 100 to compare with our calculated percentages.
    
    highs = [h * 100 for h in highs]
    lows = [l * 100 for l in lows]
    
    return times, highs, lows

# --- 5. Main Execution ---
def main():
    print("Loading JSON Sessions...")
    sessions = load_json_sessions()
    
    print("Filtering for NY2 Long True...")
    lt_sessions = filter_long_true(sessions)
    print(f"Found {len(lt_sessions)} matching sessions.")
    
    print("Loading Parquet Data (Truth Source)...")
    df = load_parquet_data()
    if df is None:
        print("Parquet missing, cannot compute truth.")
        return

    print("Computing Median Path (Truth)...")
    truth_t, truth_h, truth_l = generate_median_path(lt_sessions, df)
    
    print("Loading Pine Script Data (Library)...")
    pine_t, pine_h, pine_l = load_pine_data()
    
    print(f"\n--- DATA SAMPLE (Minute 600) ---")
    if 600 in truth_t and 600 in pine_t:
        t_idx = truth_t.index(600)
        p_idx = pine_t.index(600)
        print(f"Truth High @ 600m: {truth_h[t_idx]:.4f}")
        print(f"Pine High @ 600m: {pine_h[p_idx]:.4f}")
    else:
        print("Minute 600 not found in both datasets.")
    
    print(f"\n--- RAW PINE SAMPLE (First 5) ---")
    print(f"Pine Highs (scaled x100): {pine_h[:5]}")
    
    # --- Plot Comparison ---
    plt.figure(figsize=(12, 6))
    
    # Plot Truth (Raw 1-min)
    plt.plot(truth_t, truth_h, label='Profiler (Calc Truth) - High', color='blue', alpha=0.3)
    plt.plot(truth_t, truth_l, label='Profiler (Calc Truth) - Low', color='brown', alpha=0.3)
    
    # Plot Pine (interpolated/overlay)
    # Pine times are likely every 5 or 15 mins
    plt.plot(pine_t, pine_h, label='Pine Library - High', color='cyan', linestyle='--')
    plt.plot(pine_t, pine_l, label='Pine Library - Low', color='orange', linestyle='--')
    
    plt.title("Verification: Pine Library vs Profiler Calculated Truth (NY2 Long True Days)")
    plt.xlabel("Minutes from 18:00 prev day")
    plt.ylabel("Change %")
    plt.legend()
    plt.grid(True)
    
    out_path = Path("scripts/profiler/monte_carlo/output/compare_pine_profiler.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    print(f"Comparison saved to {out_path}")

if __name__ == "__main__":
    main()
