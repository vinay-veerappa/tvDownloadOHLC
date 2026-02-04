
import pandas as pd
import json
import numpy as np
from datetime import datetime

# Config
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_END_DATE = "2024-05-07"
REF_DAYS = 4584

# Reference Application Data (Provided by User)
# Only High % was provided
REF_HIGH_BUCKETS = {
    '0.0': 305, '0.1': 346, '0.2': 388, '0.3': 343, '0.4': 349, 
    '0.5': 346, '0.6': 301, '0.7': 244, '0.8': 251, '0.9': 229, 
    '1.0': 177, '1.1': 157, '1.2': 133, '1.3': 110, '1.4': 111
}

def get_bucket(val):
    import math
    if pd.isna(val): return 0.0
    # Round down to nearest 0.1
    b = math.floor(val * 10) / 10.0
    if b < 0: return 0.0 # Clamp negatives for High
    return b if b < 5.0 else 5.0

def get_bucket_low(val):
    import math
    if pd.isna(val): return 0.0
    # For Low, we want magnitude (absolute value) or negative buckets?
    # Reference usually treats Low as "Down form Open", so negative.
    # But distribution charts often show magnitude 0.1% down, 0.2% down.
    # Let's assume Magnitude for easy comparison with High
    val = abs(val)
    b = math.floor(val * 10) / 10.0
    return b if b < 5.0 else 5.0

def run_analysis():
    print(f"Loading {UNADJUSTED_JSON}...")
    
    with open(UNADJUSTED_JSON, 'r') as f:
        data = json.load(f)
        
    # Convert to DataFrame
    df = pd.DataFrame.from_dict(data, orient='index')
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Filter Date Range
    # End Date Inclusive
    mask = df.index <= REF_END_DATE
    if not mask.any():
        print("Error: No data found before end date.")
        return
        
    df_ref = df[mask].iloc[-REF_DAYS:].copy()
    
    start_dt = df_ref.index[0].strftime('%Y-%m-%d')
    end_dt = df_ref.index[-1].strftime('%Y-%m-%d')
    
    print(f"Analysis Period: {start_dt} to {end_dt} ({len(df_ref)} days)")
    
    # Calculate %
    df_ref['high_pct'] = (df_ref['daily_high'] - df_ref['daily_open']) / df_ref['daily_open'] * 100
    df_ref['low_pct'] = (df_ref['daily_low'] - df_ref['daily_open']) / df_ref['daily_open'] * 100
    
    # Bucketing
    high_dist = df_ref['high_pct'].apply(get_bucket).value_counts()
    low_dist = df_ref['low_pct'].apply(get_bucket_low).value_counts()
    
    # Compare High
    print("\n=== HIGH % DISTRIBTION COMPARISON ===")
    print(f"{'Bucket':<6} | {'Ref App':<8} | {'Unadj Data':<10} | {'Diff':<5} | {'Match %':<8}")
    print("-" * 55)
    
    total_ref_provided = sum(REF_HIGH_BUCKETS.values())
    buckets_to_check = sorted([float(k) for k in REF_HIGH_BUCKETS.keys()])
    
    for b in buckets_to_check:
        b_str = str(b)
        if b.is_integer(): b_str = f"{int(b)}.0"
        
        ref_val = REF_HIGH_BUCKETS.get(b_str, 0)
        our_val = high_dist.get(b, 0)
        diff = our_val - ref_val
        match_pct = (1 - abs(diff)/ref_val)*100 if ref_val > 0 else 0
        
        print(f"{b:<6} | {ref_val:<8} | {our_val:<10} | {diff:<5} | {match_pct:5.1f}%")
        
    print("-" * 55)
    
    # Show Low % Distribution (for user verification)
    print("\n=== LOW % DISTRIBUTION (Unadjusted) ===")
    print("Use this table to verify against your Reference App")
    print(f"{'Bucket':<6} | {'Count':<8} | {'% of Total':<10}")
    print("-" * 40)
    
    low_buckets = sorted(low_dist.keys())
    # Limit to reasonable range for print
    low_buckets = [b for b in low_buckets if b <= 2.0] 
    
    for b in low_buckets:
         cnt = low_dist.get(b, 0)
         pct = (cnt / len(df_ref)) * 100
         print(f"{b:<6} | {cnt:<8} | {pct:.1f}%")

if __name__ == "__main__":
    run_analysis()
