import pandas as pd
import numpy as np
import os
import sys

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_profiler_correlations():
    data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, low_memory=False)
    df.columns = df.columns.str.strip()
    
    # ----------------------------------------------------
    # 1. Derive Profiler States (Asia)
    # ----------------------------------------------------
    # Logic:
    # LT: Hit High, Not Low
    # ST: Hit Low, Not High
    # LF: Hit High First, then Low
    # SF: Hit Low First, then High
    # Inside: Neither
    
    def get_profiler_state(row):
        h_time = pd.to_datetime(row.get('hit_asia_high_time', 'NaT'), errors='coerce')
        l_time = pd.to_datetime(row.get('hit_asia_low_time', 'NaT'), errors='coerce')
        
        hit_h = pd.notna(h_time)
        hit_l = pd.notna(l_time)
        
        if not hit_h and not hit_l: return "INSIDE"
        
        if hit_h and not hit_l: return "LONG_TRUE"
        if not hit_h and hit_l: return "SHORT_TRUE"
        
        # Both hit
        if h_time < l_time:
            return "LONG_FALSE" # Broke High First -> Reversed
        else:
            return "SHORT_FALSE" # Broke Low First -> Reversed
            
    df['asia_profiler'] = df.apply(get_profiler_state, axis=1)
    
    # ----------------------------------------------------
    # 2. Derive Engine States (Probability Engine)
    # ----------------------------------------------------
    def get_sweep_state(row):
        try:
            h = float(row['london_high']) > float(row['asia_high'])
            l = float(row['london_low']) < float(row['asia_low'])
            if h and not l: return "PARTIAL_UP"
            if not h and l: return "PARTIAL_DOWN"
            if h and l: return "ENGULFS"
            return "INSIDE"
        except: return "UNKNOWN"
        
    def get_alignment(row):
        try:
            mid = (float(row['london_high']) + float(row['london_low'])) / 2
            op = float(row.get('ny_open', np.nan))
            if pd.isna(op) or pd.isna(mid): return "UNKNOWN"
            return "ABOVE_MID" if op > mid else "BELOW_MID"
        except: return "UNKNOWN"

    df['engine_state'] = df.apply(get_sweep_state, axis=1)
    df['engine_alignment'] = df.apply(get_alignment, axis=1)
    df['engine_combo'] = df['engine_state'] + " + " + df['engine_alignment']

    # ----------------------------------------------------
    # 3. Derive Outcome (Did NY hit London High/Low?)
    # ----------------------------------------------------
    def get_outcome(row):
        try:
            lh = float(row['london_high'])
            ll = float(row['london_low'])
            
            # Did NY AM or PM hit these levels?
            # We can use hit_london_high_time if available, or infer from ny_am/pm highs
            # Let's use ny_am/pm highs as proxies for NY Session Action
            
            am_h = float(row.get('ny_am_high', -1))
            am_l = float(row.get('ny_am_low', 999999))
            pm_h = float(row.get('ny_pm_high', -1))
            pm_l = float(row.get('ny_pm_low', 999999))
            
            # Max High / Min Low during entire NY Session
            ny_h = max(am_h, pm_h) if am_h != -1 or pm_h != -1 else -1
            ny_l = min(am_l, pm_l) if am_l != 999999 or pm_l != 999999 else 999999
            
            hit_lh = ny_h > lh
            hit_ll = ny_l < ll
            
            if hit_lh and not hit_ll: return "HIT_HIGH"
            if not hit_lh and hit_ll: return "HIT_LOW"
            if hit_lh and hit_ll: return "HIT_BOTH" # Expansion/Volatile
            return "NO_HIT" # Inside day
        except: return "ERROR"

    df['outcome'] = df.apply(get_outcome, axis=1)
    
    # Filter for trend days (HIT_HIGH or HIT_LOW)
    valid = df[df['outcome'].isin(["HIT_HIGH", "HIT_LOW"])].copy()

    # ----------------------------------------------------
    # 4. Correlation Analysis
    # ----------------------------------------------------
    print("\n--- 1. Baseline Engine Performance (Trend Days) ---")
    print(valid.groupby('engine_combo')['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100)

    print("\n--- 2. PROFILER Correlation: Asia State vs Outcome ---")
    # Does Asia LONG_TRUE predict HIT_HIGH better?
    # Segment by Asia Profiler State
    
    print("\n[All Engine States Combined]")
    print(valid.groupby('asia_profiler')['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100)
    
    print("\n--- 3. deep Dive: Engine + Profiler ---")
    # Specific Case: PARTIAL_UP + ABOVE_MID (Bullish Continuation)
    # How does Asia Profiler State affect this?
    
    target = "PARTIAL_UP + ABOVE_MID"
    subset = valid[valid['engine_combo'] == target]
    if not subset.empty:
        print(f"\nAnalysis for {target} (Expect HIT_HIGH):")
        stats = subset.groupby('asia_profiler', observed=False)['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
        print(stats.round(1))
        
    # Specific Case: PARTIAL_DOWN + BELOW_MID (Bearish Continuation)
    target_bear = "PARTIAL_DOWN + BELOW_MID"
    subset_bear = valid[valid['engine_combo'] == target_bear]
    if not subset_bear.empty:
        print(f"\nAnalysis for {target_bear} (Expect HIT_LOW):")
        stats = subset_bear.groupby('asia_profiler', observed=False)['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
        print(stats.round(1))

if __name__ == "__main__":
    analyze_profiler_correlations()
