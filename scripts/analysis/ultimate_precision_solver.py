
import json
import math
import pandas as pd

# Configuration
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584

def get_bucket(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    # Truncate to 0.1
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

def solve():
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_high = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_low = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

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

    results = []
    
    # Initialize counts for first window
    curr_h = {}
    curr_l = {}
    for i in range(TARGET_COUNT):
        h = days[i]['h_b']
        l = days[i]['l_b']
        curr_h[h] = curr_h.get(h, 0) + 1
        curr_l[l] = curr_l.get(l, 0) + 1
        
    for i in range(len(days) - TARGET_COUNT + 1):
        mh, th = calc_stats(curr_h, ref_high)
        ml, tl = calc_stats(curr_l, ref_low)
        
        max_d = max(mh, ml)
        tot_e = th + tl
        
        results.append({
            'start': days[i]['date'],
            'end': days[i+TARGET_COUNT-1]['date'],
            'max_diff': max_d,
            'total_err': tot_e
        })
        
        # Slide
        if i < len(days) - TARGET_COUNT:
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

    # Sort by Max Diff, then Total Err
    top_n = sorted(results, key=lambda x: (x['max_diff'], x['total_err']))[:10]
    
    print(f"{'Start':<12} | {'End':<12} | {'MaxDiff':<7} | {'TotalErr':<8}")
    print("-" * 50)
    for r in top_n:
        print(f"{r['start']:<12} | {r['end']:<12} | {r['max_diff']:<7} | {r['total_err']:<8}")

if __name__ == "__main__":
    solve()
