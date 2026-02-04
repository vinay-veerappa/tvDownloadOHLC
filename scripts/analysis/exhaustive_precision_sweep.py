
import json
import math
import pandas as pd

# Configuration
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584

# Broad search range around 2006-2007
SEARCH_START_LIMIT = "2005-01-01"
SEARCH_END_LIMIT = "2008-01-01"

def get_bucket_floor(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    b = math.floor(round(mag, 4) * 10) / 10.0
    return b if b < 5.0 else 5.0

def get_bucket_round(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    b = round(mag, 1)
    return b if b < 5.0 else 5.0

def calc_stats(my_counts, target_counts):
    max_diff = 0
    total_err = 0
    all_keys = set(my_counts.keys()) | set(target_counts.keys())
    for k in all_keys:
        m = my_counts.get(k, 0)
        t = target_counts.get(k, 0)
        diff = abs(m - t)
        if diff > max_diff:
            max_diff = diff
        total_err += diff
    return max_diff, total_err

def solve():
    print(f"Loading data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    with open(UNADJUSTED_JSON, 'r') as f:
        local_data = json.load(f)
    
    sorted_dates = sorted(local_data.keys())
    
    # Pre-calculate sequences for both models
    seq_floor = []
    seq_round = []
    for d in sorted_dates:
        e = local_data[d]
        op = e['daily_open']
        hi = e['daily_high']
        lo = e['daily_low']
        if op > 0:
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            seq_floor.append({
                'date': d,
                'h_b': get_bucket_floor(h_pct),
                'l_b': get_bucket_floor(l_pct)
            })
            seq_round.append({
                'date': d,
                'h_b': get_bucket_round(h_pct),
                'l_b': get_bucket_round(l_pct)
            })

    results = []

    for name, seq in [("Floor", seq_floor), ("Round", seq_round)]:
        print(f"Testing Model: {name}")
        
        # Determine search bounds
        start_idx = 0
        end_idx = 0
        for i, d in enumerate(seq):
            if d['date'] >= SEARCH_START_LIMIT and start_idx == 0:
                start_idx = i
            if d['date'] >= SEARCH_END_LIMIT:
                end_idx = i
                break
        
        # Initialize counts
        curr_h = {}
        curr_l = {}
        for i in range(start_idx, start_idx + TARGET_COUNT):
            h = seq[i]['h_b']
            l = seq[i]['l_b']
            curr_h[h] = curr_h.get(h, 0) + 1
            curr_l[l] = curr_l.get(l, 0) + 1
            
        # Sliding window
        # The number of available windows starting from start_idx up to end_idx
        # is end_idx - start_idx + 1.
        # But we must ensure i + TARGET_COUNT < len(seq) for the next iteration.
        
        for i in range(start_idx, end_idx + 1):
            if i + TARGET_COUNT > len(seq):
                break
                
            mh, th = calc_stats(curr_h, ref_h)
            ml, tl = calc_stats(curr_l, ref_l)
            max_d = max(mh, ml)
            tot_e = th + tl
            
            results.append({
                'model': name,
                'start': seq[i]['date'],
                'end': seq[i+TARGET_COUNT-1]['date'],
                'max_diff': max_d,
                'total_err': tot_e
            })
            
            if max_d <= 5: # Relaxed print threshold for progress
                print(f"Candidate [{name}]: {seq[i]['date']} -> {seq[i+TARGET_COUNT-1]['date']} (MaxDiff: {max_d})")
            
            # Slide
            if i < end_idx and (i + TARGET_COUNT) < len(seq):
                # Out
                oh = seq[i]['h_b']
                ol = seq[i]['l_b']
                curr_h[oh] -= 1
                if curr_h[oh] == 0: del curr_h[oh]
                curr_l[ol] -= 1
                if curr_l[ol] == 0: del curr_l[ol]
                
                # In
                ih = seq[i+TARGET_COUNT]['h_b']
                il = seq[i+TARGET_COUNT]['l_b']
                curr_h[ih] = curr_h.get(ih, 0) + 1
                curr_l[il] = curr_l.get(il, 0) + 1

    print("\n--- Final Rankings ---")
    top = sorted(results, key=lambda x: (x['max_diff'], x['total_err']))[:15]
    print(f"{'Model':<6} | {'Start':<12} | {'End':<12} | {'MaxDiff':<7} | {'TotalErr':<8}")
    print("-" * 60)
    for r in top:
        print(f"{r['model']:<6} | {r['start']:<12} | {r['end']:<12} | {r['max_diff']:<7} | {r['total_err']:<8}")

if __name__ == "__main__":
    solve()
