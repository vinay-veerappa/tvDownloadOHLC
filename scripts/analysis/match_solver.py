
import pandas as pd
import json
import numpy as np
import math

# Config
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"

def get_ref_data():
    with open(REF_JSON, 'r') as f:
        d = json.load(f)
    
    target_count = d['meta']['count']
    high_dist = {float(k): v for k, v in d['distributions']['daily']['high'].items()}
    # Low dist is less reliable for direction interpretation, focusing on HIGH first
    return target_count, high_dist

def calc_error(my_counts, target_counts):
    err = 0
    all_keys = set(my_counts.keys()) | set(target_counts.keys())
    for k in all_keys:
        m = my_counts.get(k, 0)
        t = target_counts.get(k, 0)
        err += abs(m - t)
    return err

def method_floor(val):
    if pd.isna(val) or val < 0: return 0.0
    b = math.floor(val * 10) / 10.0
    return b if b < 5.0 else 5.0

def method_round(val):
    if pd.isna(val) or val < 0: return 0.0
    b = round(val, 1)
    # round(0.15) -> 0.2? Python 3 rounds to nearest even. 
    # Let's use strict arithmetic rounding 
    b = int(val * 10 + 0.5) / 10.0
    return b if b < 5.0 else 5.0

def method_ceil(val):
    if pd.isna(val) or val < 0: return 0.0
    b = math.ceil(val * 10) / 10.0
    return b if b < 5.0 else 5.0

def solve():
    print("Loading Data...")
    target_count, target_high = get_ref_data()
    print(f"Target High Count Sum: {sum(target_high.values())} (Meta: {target_count})")
    
    with open(UNADJUSTED_JSON, 'r') as f:
        price_data = json.load(f)
    
    dates = sorted(price_data.keys())
    raw_highs = []
    
    # Pre-calc raw percentages
    for d in dates:
        e = price_data[d]
        op = e['daily_open']
        hi = e['daily_high']
        if op > 0:
            pct = (hi - op) / op * 100
            raw_highs.append({'date': d, 'val': pct})
            
    print(f"Total Raw Samples: {len(raw_highs)}")
    
    methods = [
        ("Floor (Standard)", method_floor),
        ("Round (Half Up)", method_round),
        ("Ceil", method_ceil)
    ]
    
    best_global_error = float('inf')
    best_global_method = ""
    best_global_range = ""
    
    for name, func in methods:
        print(f"\nTesting Method: {name}")
        
        # Profile buckets for all days
        bucket_sequence = []
        for item in raw_highs:
            bucket_sequence.append(func(item['val']))
            
        # Sliding Window
        # Initial Window
        current_counts = {}
        for b in bucket_sequence[:target_count]:
            current_counts[b] = current_counts.get(b, 0) + 1
            
        local_best = float('inf')
        
        for i in range(len(bucket_sequence) - target_count + 1):
            # Error check
            err = calc_error(current_counts, target_high)
            
            if err < local_best:
                local_best = err
                if err < best_global_error:
                    best_global_error = err
                    best_global_method = name
                    start_d = raw_highs[i]['date']
                    end_d = raw_highs[i+target_count-1]['date']
                    best_global_range = f"{start_d} to {end_d}"
                    
            if err == 0:
                print("FOUND PERFECT MATCH!")
                print(f"Method: {name}")
                print(f"Range: {raw_highs[i]['date']} -> {raw_highs[i+target_count-1]['date']}")
                return
            
            # Slide
            if i < len(bucket_sequence) - target_count:
                out_b = bucket_sequence[i]
                in_b = bucket_sequence[i+target_count]
                current_counts[out_b] -= 1
                if current_counts[out_b] == 0: del current_counts[out_b]
                current_counts[in_b] = current_counts.get(in_b, 0) + 1
                
        print(f"  Best Error: {local_best}")
        
    print("\n------------------------------")
    print("Optimization Complete.")
    print(f"Best Global Error: {best_global_error}")
    print(f"Method: {best_global_method}")
    print(f"Range: {best_global_range}")

if __name__ == "__main__":
    solve()
