
import pandas as pd
import json
import numpy as np
from datetime import datetime

# Config
PROFILER_JSON = "data/NQ1_profiler.json"
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"

# The Target Distribution (From Reference App)
TARGET_HIGH = {
    '0.4': 3, '0.5': 1, '0.6': 1, '0.7': 2, '0.8': 2, '0.9': 2, 
    '1.0': 1, '1.1': 2, '1.2': 3, '1.3': 2, '1.4': 2, '1.6': 4, 
    '1.8': 5, '2.3': 1, '2.4': 2, '2.6': 1, '3.8': 1, '4.1': 1, '4.2': 1
}

TARGET_LOW = {
    '0.0': 4, '0.1': 9, '0.2': 7, '0.3': 4, '0.4': 3, '0.5': 1, 
    '0.6': 1, '0.7': 4, '0.8': 1, '1.1': 1, '1.2': 1, '2.4': 1
}

def get_bucket(val):
    import math
    if pd.isna(val): return 0.0
    val_clamped = max(-5.0, min(5.0, val))
    mag = abs(val_clamped)
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def find_match():
    print("Loading Data...")
    
    # 1. Identify Filtered Dates
    with open(PROFILER_JSON, 'r') as f:
        sess_data = json.load(f)
        
    sessions_by_date = {}
    for s in sess_data:
        d = s['date']
        if d not in sessions_by_date: sessions_by_date[d] = {}
        sessions_by_date[d][s['session']] = s
        
    filtered_matches = []
    
    for d, s_map in sessions_by_date.items():
        if 'Asia' not in s_map or 'London' not in s_map or 'NY1' not in s_map:
            continue
            
        asia = s_map['Asia']
        london = s_map['London']
        ny1 = s_map['NY1']
        
        # Filter: Asia LF+Broken, London LT, NY1 LT
        if (asia['status'] == "Long False" and asia['broken'] is True and
            london['status'] == "Long True" and
            ny1['status'] == "Long True"):
            filtered_matches.append(d)
            
    filtered_matches.sort()
    print(f"Total Matches in Full History: {len(filtered_matches)} days")
    
    # 2. Load Prices
    with open(UNADJUSTED_JSON, 'r') as f:
        price_data = json.load(f)
        
    # Build Dataset list
    rows = []
    for d in filtered_matches:
        if d in price_data:
            entry = price_data[d]
            op = entry['daily_open']
            hi = entry['daily_high']
            lo = entry['daily_low']
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            
            rows.append({
                'date': d, 
                'high_b': get_bucket(h_pct), 
                'low_b': get_bucket(l_pct),
                'high_val': h_pct,
                'low_val': l_pct
            })
            
    print("Date | High Bucket | Low Bucket")
    print("-----------------------------")
    for r in rows:
        print(f"{r['date']} | {r['high_b']} | {r['low_b']}")
        
    # 3. Search for Subset of Length 37
    # We have 42 rows. We need 37.
    # We must remove 5 rows.
    # Try removing from Head or Tail first (most likely date range mismatch)
    
    match_found = False
    
    # Try all contiguous windows of length 37
    target_high_sum = sum(TARGET_HIGH.values()) # 37
    
    print("\nScanning contiguous subsets...")
    
    for i in range(len(rows) - 37 + 1):
        subset = rows[i : i+37]
        start_date = subset[0]['date']
        end_date = subset[-1]['date']
        
        # Check Distribution
        s_high_counts = {}
        s_low_counts = {}
        
        for r in subset:
            hk = f"{r['high_b']:.1f}"
            lk = f"{r['low_b']:.1f}"
            s_high_counts[hk] = s_high_counts.get(hk, 0) + 1
            s_low_counts[lk] = s_low_counts.get(lk, 0) + 1
            
        # Compare
        miss = 0
        for k, v in TARGET_HIGH.items():
            if s_high_counts.get(k, 0) != v:
                miss += abs(s_high_counts.get(k, 0) - v)
                
        # Also check keys in ours not in target
        for k in s_high_counts:
            if k not in TARGET_HIGH:
                miss += s_high_counts[k]
                
        if miss == 0:
            print(f"✅ PERFECT MATCH FOUND!")
            print(f"Range: {start_date} to {end_date}")
            match_found = True
            break
            
    if not match_found:
        print("No contiguous date match found. The 5 extra days might be scattered (holidays/missing data).")
        
        # Analyze the dates we have vs target
        # Our Total Buckets vs Target Buckets
        full_high = {}
        for r in rows:
            k = f"{r['high_b']:.1f}"
            full_high[k] = full_high.get(k, 0) + 1
            
        print("\nBuckets with Excess Counts (Candidates to Remove):")
        for k in full_high:
            tgt = TARGET_HIGH.get(k, 0)
            excess = full_high[k] - tgt
            if excess > 0:
                print(f"Bucket {k}: +{excess} (Dates: {[r['date'] for r in rows if f'{r['high_b']:.1f}' == k]})")

if __name__ == "__main__":
    find_match()
