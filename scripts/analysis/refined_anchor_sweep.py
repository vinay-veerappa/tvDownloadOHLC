
import json
import math
import pandas as pd
from collections import Counter

# Configuration
UNADJUSTED_CSV = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584
# Anchor: Oct 30, 2006 (Index where it ends Dec 30, 2024)
ANCHOR_DATE = "2006-10-30"
OFFSET = 150

def get_bucket(val):
    if pd.isna(val) or val < 0: return 0.0
    b = math.floor(round(val, 4) * 10) / 10.0
    return b if b < 5.0 else 5.0

def calc_max_diff(my, ref):
    max_d = 0
    all_k = set(my.keys()) | set(ref.keys())
    for k in all_k:
        max_d = max(max_d, abs(my.get(k, 0) - ref.get(k, 0)))
    return max_d

def solve():
    print("Loading Reference Data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    print("Loading CSV Data...")
    df = pd.read_csv(UNADJUSTED_CSV)
    df['h_pct'] = (df['high'] - df['open']) / df['open'] * 100
    df['l_pct'] = abs((df['low'] - df['open']) / df['open'] * 100)
    df['date_str'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d')
    
    h_buckets = [get_bucket(v) for v in df['h_pct']]
    l_buckets = [get_bucket(v) for v in df['l_pct']]
    dates = df['date_str'].tolist()

    # Find Anchor Index
    anchor_idx = df[df['date_str'] >= ANCHOR_DATE].index[0]
    s_idx = max(0, anchor_idx - OFFSET)
    e_idx = min(len(df) - TARGET_COUNT, anchor_idx + OFFSET)
    
    print(f"Scanning indices {s_idx} to {e_idx}...")
    
    curr_h = Counter(h_buckets[s_idx : s_idx + TARGET_COUNT])
    curr_l = Counter(l_buckets[s_idx : s_idx + TARGET_COUNT])
    
    results = []
    
    for i in range(s_idx, e_idx + 1):
        mdh = calc_max_diff(curr_h, ref_h)
        mdl = calc_max_diff(curr_l, ref_l)
        max_d = max(mdh, mdl)
        
        results.append({
            'start': dates[i],
            'end': dates[i+TARGET_COUNT-1],
            'max_diff': max_d
        })
        
        if max_d <= 10:
            print(f"STRONG MATCH: {dates[i]} to {dates[i+TARGET_COUNT-1]} | MaxDiff: {max_d}")
            
        # Slide
        if i < e_idx:
            curr_h[h_buckets[i]] -= 1
            if curr_h[h_buckets[i]] == 0: del curr_h[h_buckets[i]]
            curr_l[l_buckets[i]] -= 1
            if curr_l[l_buckets[i]] == 0: del curr_l[l_buckets[i]]
            
            curr_h[h_buckets[i+TARGET_COUNT]] += 1
            curr_l[l_buckets[i+TARGET_COUNT]] += 1

    print("\n--- Top Results (±150 days around anchor) ---")
    top = sorted(results, key=lambda x: x['max_diff'])[:15]
    for r in top:
        print(f"{r['start']} to {r['end']} | MaxDiff: {r['max_diff']}")

if __name__ == "__main__":
    solve()
