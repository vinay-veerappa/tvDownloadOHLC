
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
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def solve():
    print("Loading Reference Data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    target_high = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    
    print("Loading Local Data...")
    with open(UNADJUSTED_JSON, 'r') as f:
        local_data = json.load(f)
    
    sorted_dates = sorted(local_data.keys())
    
    # We will test two methods:
    # 1. High from Open (pct_o)
    # 2. High from Prior Close (pct_c)
    
    seq_open = []
    seq_close = []
    
    for i, d in enumerate(sorted_dates):
        entry = local_data[d]
        op = entry['daily_open']
        hi = entry['daily_high']
        pc = entry.get('prior_close', 0) # Assuming this exists or using previous day close
        
        if pc == 0 and i > 0:
            pc = local_data[sorted_dates[i-1]]['daily_close']

        if op > 0 and pc > 0:
            pct_o = (hi - op) / op * 100
            pct_c = (hi - pc) / pc * 100
            seq_open.append({'d': d, 'b': get_bucket(pct_o)})
            seq_close.append({'d': d, 'b': get_bucket(pct_c)})

    for name, seq in [("High from Open", seq_open), ("High from Prior Close", seq_close)]:
        print(f"\nTesting: {name} (Samples: {len(seq)})")
        
        buckets = [x['b'] for x in seq]
        curr_counts = {}
        for i in range(TARGET_COUNT):
            b = buckets[i]
            curr_counts[b] = curr_counts.get(b, 0) + 1
            
        best_err = float('inf')
        best_range = None
        
        for i in range(len(buckets) - TARGET_COUNT + 1):
            # Error
            err = 0
            all_keys = set(curr_counts.keys()) | set(target_high.keys())
            for k in all_keys:
                err += abs(curr_counts.get(k, 0) - target_high.get(k, 0))
            
            if err < best_err:
                best_err = err
                start_d = seq[i]['d']
                end_d = seq[i+TARGET_COUNT-1]['d']
                best_range = (start_d, end_d)
                
            # Slide
            if i < len(buckets) - TARGET_COUNT:
                curr_counts[buckets[i]] -= 1
                if curr_counts[buckets[i]] == 0: del curr_counts[buckets[i]]
                curr_counts[buckets[i+TARGET_COUNT]] = curr_counts.get(buckets[i+TARGET_COUNT], 0) + 1
        
        print(f"Best Match {name}: {best_range[0]} to {best_range[1]}")
        print(f"  Total Abs Error: {best_err}")

if __name__ == "__main__":
    solve()
