
import json
import math
import pandas as pd
from collections import Counter

# Configuration
UNADJUSTED_CSV = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584
TARGET_H0 = 305 # The specific 0.0% bucket target
TARGET_L0 = 473 # The specific 0.0% low bucket target

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
    
    h_buckets = [get_bucket(v) for v in df['h_pct']]
    l_buckets = [get_bucket(v) for v in df['l_pct']]
    dates = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d').tolist()

    curr_h = Counter(h_buckets[:TARGET_COUNT])
    curr_l = Counter(l_buckets[:TARGET_COUNT])
    
    print(f"Scanning all {len(df) - TARGET_COUNT + 1} windows...")
    
    candidates = []
    
    for i in range(len(df) - TARGET_COUNT + 1):
        # We look for windows where H0 or L0 is very close
        h0 = curr_h.get(0.0, 0)
        l0 = curr_l.get(0.0, 0)
        
        if abs(h0 - TARGET_H0) <= 5 and abs(l0 - TARGET_L0) <= 5:
            max_dh = calc_max_diff(curr_h, ref_h)
            max_dl = calc_max_diff(curr_l, ref_l)
            max_d = max(max_dh, max_dl)
            
            candidates.append({
                'start': dates[i],
                'end': dates[i+TARGET_COUNT-1],
                'max_diff': max_d,
                'h0': h0,
                'l0': l0
            })
            
            if max_d < 30:
                print(f"LOW DIFF: {dates[i]} to {dates[i+TARGET_COUNT-1]} | MaxDiff: {max_d} | H0: {h0}, L0: {l0}")
            
        # Slide
        if i < len(df) - TARGET_COUNT:
            # Out
            curr_h[h_buckets[i]] -= 1
            if curr_h[h_buckets[i]] == 0: del curr_h[h_buckets[i]]
            curr_l[l_buckets[i]] -= 1
            if curr_l[l_buckets[i]] == 0: del curr_l[l_buckets[i]]
            # In
            curr_h[h_buckets[i+TARGET_COUNT]] += 1
            curr_l[l_buckets[i+TARGET_COUNT]] += 1

    print("\n--- Top Targets ---")
    top = sorted(candidates, key=lambda x: x['max_diff'])[:15]
    for r in top:
        print(f"{r['start']} to {r['end']} | MaxDiff: {r['max_diff']} | H0: {r['h0']}, L0: {r['l0']}")

if __name__ == "__main__":
    solve()
