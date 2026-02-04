
import json
import math
import pandas as pd

# Configuration
UNADJUSTED_CSV = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584

def get_bucket_floor(val):
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
    print("Loading Reference Data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    print("Loading CSV Data...")
    df = pd.read_csv(UNADJUSTED_CSV)
    df['date_str'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d')
    
    # Calculate Percentages
    df['h_pct'] = (df['high'] - df['open']) / df['open'] * 100
    df['l_pct'] = (df['low'] - df['open']) / df['open'] * 100
    
    # Array of buckets (using Floor logic as primary candidate)
    h_buckets = [get_bucket_floor(v) for v in df['h_pct']]
    l_buckets = [get_bucket_floor(v) for v in df['l_pct']]
    
    results = []
    
    # Init first window
    curr_h = {}
    curr_l = {}
    for i in range(TARGET_COUNT):
        curr_h[h_buckets[i]] = curr_h.get(h_buckets[i], 0) + 1
        curr_l[l_buckets[i]] = curr_l.get(l_buckets[i], 0) + 1
        
    print(f"Scanning {len(df) - TARGET_COUNT + 1} windows...")
    
    for i in range(len(df) - TARGET_COUNT + 1):
        mh, th = calc_stats(curr_h, ref_h)
        ml, tl = calc_stats(curr_l, ref_l)
        max_d = max(mh, ml)
        tot_e = th + tl
        
        results.append({
            'start': df.iloc[i]['date_str'],
            'end': df.iloc[i+TARGET_COUNT-1]['date_str'],
            'max_diff': max_d,
            'total_err': tot_e
        })
        
        if max_d <= 5:
            print(f"HIT: {df.iloc[i]['date_str']} -> {df.iloc[i+TARGET_COUNT-1]['date_str']} (MaxDiff: {max_d})")
            if max_d <= 2:
                print(">>> REACHED PRECISION GOAL! <<<")

        # Slide
        if i < len(df) - TARGET_COUNT:
            # Out
            curr_h[h_buckets[i]] -= 1
            if curr_h[h_buckets[i]] == 0: del curr_h[h_buckets[i]]
            curr_l[l_buckets[i]] -= 1
            if curr_l[l_buckets[i]] == 0: del curr_l[l_buckets[i]]
            # In
            curr_h[h_buckets[i+TARGET_COUNT]] = curr_h.get(h_buckets[i+TARGET_COUNT], 0) + 1
            curr_l[l_buckets[i+TARGET_COUNT]] = curr_l.get(l_buckets[i+TARGET_COUNT], 0) + 1

    print("\n--- Top 20 Global Best Matches ---")
    top = sorted(results, key=lambda x: (x['max_diff'], x['total_err']))[:20]
    print(f"{'Start':<12} | {'End':<12} | {'MaxDiff':<7} | {'TotalErr':<8}")
    print("-" * 50)
    for r in top:
        print(f"{r['start']:<12} | {r['end']:<12} | {r['max_diff']:<7} | {r['total_err']:<8}")

if __name__ == "__main__":
    solve()
