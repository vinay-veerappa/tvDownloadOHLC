
import json
import math
import pandas as pd
from collections import defaultdict, Counter

# Targets from Ref
NY1_LONG = 2326
ASIA_LONG = 2325
LONDON_LONG = 2299
NY2_NONE = 78
HIGH_ZERO_BUCKET = 305
TARGET_COUNT = 4584

# Config
PROFILER_JSON = "data/NQ1_profiler.json"
UNADJ_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
ANCHOR_START = "2006-10-01"
OFFSET = 150

def get_bucket(val):
    if val is None or val < 0: return 0.0
    # Floor to 0.1
    b = math.floor(round(val, 4) * 10) / 10.0
    return b if b < 5.0 else 5.0

def solve():
    print("Loading data...")
    with open(PROFILER_JSON, 'r') as f:
        p_data = json.load(f)
    with open(UNADJ_JSON, 'r') as f:
        u_data = json.load(f)
        
    daily = defaultdict(lambda: {"h0": 0, "n1l": 0, "al": 0, "ll": 0, "n2n": 0})
    
    # Process Profiler (Sessions)
    for e in p_data:
        d = e['date']
        s = e['session'].lower()
        st = e.get('status', '').lower()
        
        if s == 'ny1' and 'long' in st: daily[d]['n1l'] = 1
        if s == 'asia' and 'long' in st: daily[d]['al'] = 1
        if s == 'london' and 'long' in st: daily[d]['ll'] = 1
        if s == 'ny2' and st == 'none': daily[d]['n2n'] = 1
        
    # Process Unadjusted (Buckets)
    for d, e in u_data.items():
        op = e['daily_open']
        hi = e['daily_high']
        if op > 0:
            b = get_bucket((hi - op) / op * 100)
            if b == 0.0: daily[d]['h0'] = 1
            
    sorted_dates = sorted(daily.keys())
    
    # Find Anchor
    start_point = 0
    for i, d in enumerate(sorted_dates):
        if d >= ANCHOR_START:
            start_point = i
            break
    
    s_idx = max(0, start_point - OFFSET)
    e_idx = min(len(sorted_dates) - TARGET_COUNT, start_point + OFFSET)
    
    # Init first window
    c = {"n1l": 0, "al": 0, "ll": 0, "n2n": 0, "h0": 0}
    for i in range(s_idx, s_idx + TARGET_COUNT):
        d = sorted_dates[i]
        for k in c: c[k] += daily[d][k]
        
    print(f"Scanning starting between {sorted_dates[s_idx]} and {sorted_dates[e_idx]}...")
    
    results = []
    for i in range(s_idx, e_idx + 1):
        err = abs(c['n1l'] - NY1_LONG) + abs(c['al'] - ASIA_LONG) + abs(c['ll'] - LONDON_LONG) + \
              abs(c['n2n'] - NY2_NONE) + abs(c['h0'] - HIGH_ZERO_BUCKET)
              
        results.append({
            'start': sorted_dates[i],
            'end': sorted_dates[i+TARGET_COUNT-1],
            'error': err,
            'stats': c.copy()
        })
        
        if err < 20:
            print(f"CANDIDATE: {sorted_dates[i]} to {sorted_dates[i+TARGET_COUNT-1]} | Total Error: {err}")
            
        # Slide
        if i < e_idx:
            # Out
            d_out = sorted_dates[i]
            for k in c: c[k] -= daily[d_out][k]
            # In
            d_in = sorted_dates[i + TARGET_COUNT]
            for k in c: c[k] += daily[d_in][k]

    print("\n--- Top 10 Best Fingerprints ---")
    top = sorted(results, key=lambda x: x['error'])[:10]
    for r in top:
        print(f"{r['start']} to {r['end']} | Err: {r['error']} | H0: {r['stats']['h0']}")

if __name__ == "__main__":
    solve()
