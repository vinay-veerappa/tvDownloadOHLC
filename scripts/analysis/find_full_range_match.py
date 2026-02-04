
import pandas as pd
import json
import numpy as np
from datetime import datetime

# Config
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"

def get_bucket(val):
    import math
    if pd.isna(val): return 0.0
    val_clamped = max(-5.0, min(5.0, val))
    mag = abs(val_clamped) # Magnitude
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def run_scan():
    print("Loading Data...")
    
    # 1. Load Reference Data
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
        
    target_count = ref_data['meta']['count']
    print(f"Target Count: {target_count}")
    
    # Prase Target Buckets
    target_high = {}
    for k, v in ref_data['distributions']['daily']['high'].items():
        b = float(k)
        target_high[b] = v
        
    target_low = {}
    for k, v in ref_data['distributions']['daily']['low'].items():
        b = abs(float(k)) # Convert '-0.1' to 0.1 for magnitude matching
        target_low[b] = v
        
    # 2. Load Our Data
    with open(UNADJUSTED_JSON, 'r') as f:
        price_data = json.load(f)
        
    # Convert to sorted list
    all_dates = sorted(price_data.keys())
    day_stats = []
    
    print(f"Total Available Days: {len(all_dates)}")
    
    for d in all_dates:
        entry = price_data[d]
        op = entry['daily_open']
        hi = entry['daily_high']
        lo = entry['daily_low']
        
        if op > 0:
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            
            day_stats.append({
                'date': d,
                'high_bucket': get_bucket(h_pct),
                'low_bucket': get_bucket(l_pct)
            })
            
    # 3. Rolling Scan
    # We maintain a running count of buckets in the window
    # Initial Window
    window_stats = day_stats[:target_count]
    current_high_counts = {}
    current_low_counts = {}
    
    for d in window_stats:
        hb = d['high_bucket']
        lb = d['low_bucket']
        current_high_counts[hb] = current_high_counts.get(hb, 0) + 1
        current_low_counts[lb] = current_low_counts.get(lb, 0) + 1
        
    best_error = float('inf')
    best_range = (None, None)
    best_high_match = None
    
    # Helper to calc error
    def calc_error():
        err = 0
        # High Errors
        keys = set(current_high_counts.keys()) | set(target_high.keys())
        for k in keys:
            t = target_high.get(k, 0)
            c = current_high_counts.get(k, 0)
            err += abs(c - t)
            
        # Low Errors
        keys = set(current_low_counts.keys()) | set(target_low.keys())
        for k in keys:
            t = target_low.get(k, 0)
            c = current_low_counts.get(k, 0)
            err += abs(c - t)
        return err

    print(f"Scanning {len(day_stats) - target_count} windows...")
    
    for i in range(len(day_stats) - target_count + 1):
        # Current Window: day_stats[i : i+target_count]
        # Range
        start_date = day_stats[i]['date']
        end_date = day_stats[i + target_count - 1]['date']
        
        if end_date > "2024-12-31":
            continue
            
        # Calc Error
        err = calc_error()
        
        if err < best_error:
            best_error = err
            best_range = (start_date, end_date)
            # print(f"New Best: {err} ({start_date} -> {end_date})")
            
            if err == 0:
                print("PERFECT MATCH FOUND!")
                break
                
        # Slide Window: Remove outgoing (i), Add incoming (i + target_count)
        if i < len(day_stats) - target_count:
            # Remove outgoing
            out_d = day_stats[i]
            current_high_counts[out_d['high_bucket']] -= 1
            current_low_counts[out_d['low_bucket']] -= 1
            
            # Add incoming
            in_d = day_stats[i + target_count]
            current_high_counts[in_d['high_bucket']] = current_high_counts.get(in_d['high_bucket'], 0) + 1
            current_low_counts[in_d['low_bucket']] = current_low_counts.get(in_d['low_bucket'], 0) + 1
            
    print("-" * 50)
    print(f"Best Match Found:")
    print(f"Start Date: {best_range[0]}")
    print(f"End Date:   {best_range[1]}")
    print(f"Total Error Points: {best_error}")
    print(f"Reference Count: {target_count}")
    
    # If error is small, show where the diffs are
    if best_error > 0:
        print("\nTop Mismatches (Bucket: Ref vs Our):")
        # Regenerate best counts (lazy way: finding best index again or just trusting we stopped/tracked)
        # Actually I didn't save the counts for best_range.
        # But for user, the Dates are most important.
        pass

if __name__ == "__main__":
    run_scan()
