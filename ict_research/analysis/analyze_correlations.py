import pandas as pd
import numpy as np
import os
import sys

# Add parent dir to path to import local modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_deep_correlations():
    data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}")
        return

    print(f"Loading data from {data_path}...")
    # Low memory=False to avoid DtypeWarning, or specify dtypes
    df = pd.read_csv(data_path, low_memory=False)
    # Clean col names
    df.columns = df.columns.str.strip()
    
    # ----------------------------------------------------
    # 1. Define Engine Logic (States)
    # ----------------------------------------------------
    def get_sweep_state(row):
        try:
            h = float(row['london_high']) > float(row['asia_high'])
            l = float(row['london_low']) < float(row['asia_low'])
            if h and not l: return "PARTIAL_UP"
            if not h and l: return "PARTIAL_DOWN"
            if h and l: return "ENGULFS"
            return "INSIDE"
        except:
            return "UNKNOWN"
        
    def get_alignment(row):
        try:
            mid = (float(row['london_high']) + float(row['london_low'])) / 2
            op = float(row.get('ny_open', np.nan))
            if pd.isna(op) or pd.isna(mid): return "UNKNOWN"
            return "ABOVE_MID" if op > mid else "BELOW_MID"
        except:
            return "UNKNOWN"

    df['state'] = df.apply(get_sweep_state, axis=1)
    df['alignment'] = df.apply(get_alignment, axis=1)
    df['engine_combo'] = df['state'] + " + " + df['alignment']
    
    # ----------------------------------------------------
    # 2. Add Profiler Data (BEFORE Subsetting)
    # ----------------------------------------------------
    # Asia Range Quartiles
    df['asia_range'] = pd.to_numeric(df['asia_range'], errors='coerce')
    # Remove outliers for clean quartiles? Or just qcut
    df = df.dropna(subset=['asia_range'])
    df['asia_quartile'] = pd.qcut(df['asia_range'], 4, labels=["Small", "Med", "Large", "XL"])
    
    # Day of Week
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['dow'] = df['date'].dt.day_name()
    
    # ----------------------------------------------------
    # 3. Define Outcome (Hit Targets)
    # ----------------------------------------------------
    def get_outcome(row):
        try:
            # Initial targets
            lh = float(row['london_high'])
            ll = float(row['london_low'])
            
            # Check AM session first
            am_h = float(row.get('ny_am_high', -1))
            am_l = float(row.get('ny_am_low', 999999))
            
            hit_lh = am_h > lh
            hit_ll = am_l < ll
            
            # Simple case: Only one hit
            if hit_lh and not hit_ll: return "HIT_HIGH"
            if not hit_lh and hit_ll: return "HIT_LOW"
            
            # Both hit: Check times
            if hit_lh and hit_ll:
                t_h = pd.to_datetime(row.get('ny_am_high_time'), errors='coerce')
                t_l = pd.to_datetime(row.get('ny_am_low_time'), errors='coerce')
                
                if pd.isna(t_h) or pd.isna(t_l): return "BOTH_UNKNOWN"
                return "HIT_HIGH" if t_h < t_l else "HIT_LOW"
                
            return "NO_HIT"
        except:
            return "ERROR"

    df['outcome'] = df.apply(get_outcome, axis=1)
    
    # Subset for valid outcomes
    valid_out = df[df['outcome'].isin(["HIT_HIGH", "HIT_LOW"])].copy()
    
    print(f"\nTotal Rows: {len(df)}")
    print(f"Valid Outcomes (Hit High or Low): {len(valid_out)}")

    # ----------------------------------------------------
    # 4. Correlation Analysis
    # ----------------------------------------------------
    print("\n--- 1. Baseline: Probability Engine Performance ---")
    baseline = valid_out.groupby('engine_combo')['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
    # Sort by index for readability
    print(baseline.sort_index().round(1))
    
    print("\n--- 2. Complementing: Asia Range Impact ---")
    # For a Bullish Case: PARTIAL_UP + ABOVE_MID -> Expect HIT_HIGH
    target_case = "PARTIAL_UP + ABOVE_MID"
    subset = valid_out[valid_out['engine_combo'] == target_case]
    
    if not subset.empty:
        print(f"\nAnalysis for {target_case} (Expect HIGH):")
        stats = subset.groupby('asia_quartile', observed=False)['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
        print(stats.round(1))
        
    # For a Bearish Case: PARTIAL_DOWN + BELOW_MID -> Expect HIT_LOW
    target_case_bear = "PARTIAL_DOWN + BELOW_MID"
    subset_bear = valid_out[valid_out['engine_combo'] == target_case_bear]
    
    if not subset_bear.empty:
        print(f"\nAnalysis for {target_case_bear} (Expect LOW):")
        stats = subset_bear.groupby('asia_quartile', observed=False)['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
        print(stats.round(1))
        
    print("\n--- 3. Complementing: Day of Week Impact ---")
    if not subset.empty:
        print(f"\nAnalysis for {target_case} (Expect HIGH) by Day of Week:")
        stats = subset.groupby('dow', observed=False)['outcome'].value_counts(normalize=True).unstack().fillna(0) * 100
        # Sort days
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        stats = stats.reindex(days)
        print(stats.round(1))

if __name__ == "__main__":
    analyze_deep_correlations()
