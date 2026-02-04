
import json
import math
import pandas as pd
from datetime import datetime, timedelta

# Configuration
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584
# Anchor: Nov 26, 2007
ANCHOR_START_DATE = "2007-11-26"
WINDOW_DAYS = 150 

def get_bucket(val):
    if pd.isna(val): return 0.0
    # Truncate to 0.1
    mag = abs(val)
    # Using floor for binning
    b = math.floor(round(mag, 4) * 10) / 10.0
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

def run_search():
    print(f"Loading data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    with open(UNADJUSTED_JSON, 'r') as f:
        local_data = json.load(f)
    
    sorted_dates = sorted(local_data.keys())
    days = []
    for d in sorted_dates:
        e = local_data[d]
        op = e['daily_open']
        hi = e['daily_high']
        lo = e['daily_low']
        if op > 0:
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            days.append({
                'date': d,
                'h_b': get_bucket(h_pct),
                'l_b': get_bucket(l_pct)
            })

    # Find anchor index
    anchor_idx = 0
    for i, d in enumerate(days):
        if d['date'] >= ANCHOR_START_DATE:
            anchor_idx = i
            break
            
    start_search = max(0, anchor_idx - WINDOW_DAYS)
    end_search = min(len(days) - TARGET_COUNT, anchor_idx + WINDOW_DAYS)
    
    print(f"Scanning windows starting between {days[start_search]['date']} and {days[end_search]['date']}...")
    
    # Initialize counts for the first window in the search range
    curr_h = {}
    curr_l = {}
    for i in range(start_search, start_search + TARGET_COUNT):
        h = days[i]['h_b']
        l = days[i]['l_b']
        curr_h[h] = curr_h.get(h, 0) + 1
        curr_l[l] = curr_l.get(l, 0) + 1

    best_match = None
    results = []

    for i in range(start_search, end_search + 1):
        mh, th = calc_stats(curr_h, ref_h)
        ml, tl = calc_stats(curr_l, ref_l)
        
        max_d = max(mh, ml)
        tot_e = th + tl
        
        entry = {
            'start': days[i]['date'],
            'end': days[i+TARGET_COUNT-1]['date'],
            'max_diff': max_d,
            'total_err': tot_e
        }
        results.append(entry)
        
        if max_d <= 2:
            print(f"FOUND MATCH WITHIN TOLERANCE: {entry['start']} to {entry['end']} (MaxDiff: {max_d})")
            # We keep searching for better total error
            
        # Slide
        if i < end_search:
            # Out
            oh = days[i]['h_b']
            ol = days[i]['l_b']
            curr_h[oh] -= 1
            if curr_h[oh] == 0: del curr_h[oh]
            curr_l[ol] -= 1
            if curr_l[ol] == 0: del curr_l[ol]
            # In
            ih = days[i+TARGET_COUNT]['h_b']
            il = days[i+TARGET_COUNT]['l_b']
            curr_h[ih] = curr_h.get(ih, 0) + 1
            curr_l[il] = curr_l.get(il, 0) + 1

    # Output Top Bests
    print("\n--- Top 10 Best Matches (Sorted by MaxDiff) ---")
    top = sorted(results, key=lambda x: (x['max_diff'], x['total_err']))[:10]
    for r in top:
        star = "***" if r['max_diff'] <= 2 else ""
        print(f"{r['start']} to {r['end']} | MaxDiff: {r['max_diff']:<2} | TotalErr: {r['total_err']:<4} {star}")

if __name__ == "__main__":
    run_search()
