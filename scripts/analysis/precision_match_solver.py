
import json
import math
import pandas as pd
import numpy as np

# Configuration
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584

def get_bucket(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    # Floor to nearest 0.1
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def calc_error_summary(my_counts, target_counts):
    total_err = 0
    max_diff = 0
    all_keys = set(my_counts.keys()) | set(target_counts.keys())
    for k in all_keys:
        m = my_counts.get(k, 0)
        t = target_counts.get(k, 0)
        diff = abs(m - t)
        total_err += diff
        if diff > max_diff:
            max_diff = diff
    return total_err, max_diff

def solve():
    print("Loading Reference Data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    
    target_high = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    target_low = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}
    
    print("Loading Local Unadjusted Data...")
    with open(UNADJUSTED_JSON, 'r') as f:
        local_data = json.load(f)
    
    sorted_dates = sorted(local_data.keys())
    processed_days = []
    
    for d in sorted_dates:
        entry = local_data[d]
        op = entry['daily_open']
        hi = entry['daily_high']
        lo = entry['daily_low']
        
        if op > 0:
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            processed_days.append({
                'date': d,
                'high_b': get_bucket(h_pct),
                'low_b': get_bucket(l_pct)
            })
            
    print(f"Searching {len(processed_days) - TARGET_COUNT} windows...")
    
    best_total_err = float('inf')
    best_max_bucket_diff = float('inf')
    best_window = None
    
    # Pre-calculate bucket sequence for speed
    high_seq = [d['high_b'] for d in processed_days]
    low_seq = [d['low_b'] for d in processed_days]
    
    # Initialize first window
    curr_high_counts = {}
    curr_low_counts = {}
    for i in range(TARGET_COUNT):
        h = high_seq[i]
        l = low_seq[i]
        curr_high_counts[h] = curr_high_counts.get(h, 0) + 1
        curr_low_counts[l] = curr_low_counts.get(l, 0) + 1
        
    for i in range(len(processed_days) - TARGET_COUNT + 1):
        # Calc High Error
        h_err, h_max = calc_error_summary(curr_high_counts, target_high)
        # Calc Low Error
        l_err, l_max = calc_error_summary(curr_low_counts, target_low)
        
        total_err = h_err + l_err
        max_diff = max(h_max, l_max)
        
        # Primary sort: Minimizing Max Bucket Diff (requested precision)
        # Secondary sort: Total Absolute Error
        if max_diff < best_max_bucket_diff or (max_diff == best_max_bucket_diff and total_err < best_total_err):
            best_max_bucket_diff = max_diff
            best_total_err = total_err
            best_window = (processed_days[i]['date'], processed_days[i+TARGET_COUNT-1]['date'])
            print(f"New Best Window Match: {processed_days[i]['date']} to {processed_days[i+TARGET_COUNT-1]['date']}")
            print(f"  Max Bucket Diff: {max_diff}, Total Abs Error: {total_err}")
            
            if max_diff <= 2:
                print(">>> REACHED USER PRECISION GOAL! <<<")
        
        # Slide Window
        if i < len(processed_days) - TARGET_COUNT:
            # Remove i
            out_h = high_seq[i]
            out_l = low_seq[i]
            curr_high_counts[out_h] -= 1
            if curr_high_counts[out_h] == 0: del curr_high_counts[out_h]
            curr_low_counts[out_l] -= 1
            if curr_low_counts[out_l] == 0: del curr_low_counts[out_l]
            
            # Add i + TARGET_COUNT
            in_h = high_seq[i + TARGET_COUNT]
            in_l = low_seq[i + TARGET_COUNT]
            curr_high_counts[in_h] = curr_high_counts.get(in_h, 0) + 1
            curr_low_counts[in_l] = curr_low_counts.get(in_l, 0) + 1
            
    print("\n--------------------------------")
    print("Search Completed.")
    print(f"Final Best Match Window: {best_window[0]} to {best_window[1]}")
    print(f"Minimum Max Bucket Discrepancy: {best_max_bucket_diff}")
    print(f"Total Absolute Error Points: {best_total_err}")

if __name__ == "__main__":
    solve()
