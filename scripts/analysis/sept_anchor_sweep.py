
import json
import math
import pandas as pd
from collections import Counter

# Configuration
UNADJUSTED_CSV = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584
# Anchor: Sept 15, 2006
ANCHOR_DATE = "2006-09-15"
OFFSET = 150

def get_bucket_floor(val):
    if pd.isna(val) or val < 0: return 0.0
    return math.floor(round(val, 4) * 10) / 10.0

def get_bucket_eps(val):
    if pd.isna(val) or val < 0: return 0.0
    # Test with a small epsilon that might bridge 'on-the-line' values
    return math.floor(round(val, 4) * 10 + 0.001) / 10.0

def get_bucket_round(val):
    if pd.isna(val) or val < 0: return 0.0
    return round(val, 1)

def calc_max_diff(my, ref):
    max_d = 0
    all_k = set(my.keys()) | set(ref.keys())
    for k in all_k:
        max_d = max(max_d, abs(my.get(k, 0) - ref.get(k, 0)))
    return max_d

def solve():
    print("Loading data...")
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l = {float(abs(float(k))): v for k, v in ref_data['distributions']['daily']['low'].items()}

    df = pd.read_csv(UNADJUSTED_CSV)
    df['h_pct'] = (df['high'] - df['open']) / df['open'] * 100
    df['l_pct'] = abs((df['low'] - df['open']) / df['open'] * 100)
    df['date_str'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d')
    dates = df['date_str'].tolist()

    # Models
    models = {
        "Floor": get_bucket_floor,
        "Eps": get_bucket_eps,
        "Round": get_bucket_round
    }
    
    # Anchor Index
    anchor_idx = df[df['date_str'] >= ANCHOR_DATE].index[0]
    s_idx = max(0, anchor_idx - OFFSET)
    e_idx = min(len(df) - TARGET_COUNT, anchor_idx + OFFSET)
    
    print(f"Scanning indices {s_idx} to {e_idx} (±{OFFSET} days around {ANCHOR_DATE})...")
    
    for name, func in models.items():
        print(f"Testing model: {name}")
        h_buckets = [func(v) for v in df['h_pct']]
        l_buckets = [func(v) for v in df['l_pct']]
        
        curr_h = Counter(h_buckets[s_idx : s_idx + TARGET_COUNT])
        curr_l = Counter(l_buckets[s_idx : s_idx + TARGET_COUNT])
        
        best_in_model = 999
        best_window = None
        
        for i in range(s_idx, e_idx + 1):
            mh = calc_max_diff(curr_h, ref_h)
            ml = calc_max_diff(curr_l, ref_l)
            max_d = max(mh, ml)
            
            if max_d < best_in_model:
                best_in_model = max_d
                best_window = (dates[i], dates[i+TARGET_COUNT-1])
            
            if max_d <= 2:
                print(f"!!! PERFECT MATCH [{name}]: {dates[i]} to {dates[i+TARGET_COUNT-1]} (MaxDiff: {max_d}) !!!")
                
            # Slide
            if i < e_idx:
                curr_h[h_buckets[i]] -= 1
                curr_l[l_buckets[i]] -= 1
                curr_h[h_buckets[i+TARGET_COUNT]] += 1
                curr_l[l_buckets[i+TARGET_COUNT]] += 1
        
        print(f"  Best for {name}: {best_in_model} (Range: {best_window[0]} to {best_window[1]})")

if __name__ == "__main__":
    solve()
