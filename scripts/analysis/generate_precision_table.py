
import json
import math
import pandas as pd

# Config
UNADJUSTED_JSON = "data/NQ1_daily_hod_lod_unadjusted.json"
REF_JSON = "data/analysis/reference_data_full.json"
START_DATE = "2006-11-15"
END_DATE = "2025-01-16"

def get_bucket(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    b = math.floor(mag * 10) / 10.0
    return b if b < 5.0 else 5.0

def run_comparison():
    # 1. Load Ref
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_high = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_low = {abs(float(k)): v for k, v in ref_data['distributions']['daily']['low'].items()}
    target_count = ref_data['meta']['count']

    # 2. Load Our Data
    with open(UNADJUSTED_JSON, 'r') as f:
        price_data = json.load(f)
    
    dates = sorted([d for d in price_data.keys() if START_DATE <= d <= END_DATE])
    
    our_high_counts = {}
    our_low_counts = {}
    
    valid_count = 0
    for d in dates:
        e = price_data[d]
        op = e['daily_open']
        hi = e['daily_high']
        lo = e['daily_low']
        
        if op > 0:
            h_pct = (hi - op) / op * 100
            l_pct = (lo - op) / op * 100
            
            bh = get_bucket(h_pct)
            bl = get_bucket(l_pct)
            
            our_high_counts[bh] = our_high_counts.get(bh, 0) + 1
            our_low_counts[bl] = our_low_counts.get(bl, 0) + 1
            valid_count += 1

    # 3. Print Tables
    print(f"# Precision Comparison Report")
    print(f"- Range: {START_DATE} to {END_DATE}")
    print(f"- Samples: Our {valid_count} vs Ref {target_count}")
    print("\n## HIGH % DISTRIBUTION")
    print("| Bucket | Ref | Ours | Diff |")
    print("|:---|:---|:---|:---|")
    
    all_high_keys = sorted(set(ref_high.keys()) | set(our_high_counts.keys()))
    for k in all_high_keys:
        r = ref_high.get(k, 0)
        o = our_high_counts.get(k, 0)
        diff = o - r
        print(f"| {k:0.1f}% | {r} | {o} | {diff:+d} |")

    print("\n## LOW % MAGNITUDE DISTRIBUTION")
    print("| Bucket | Ref | Ours | Diff |")
    print("|:---|:---|:---|:---|")
    
    all_low_keys = sorted(set(ref_low.keys()) | set(our_low_counts.keys()))
    for k in all_low_keys:
        r = ref_low.get(k, 0)
        o = our_low_counts.get(k, 0)
        diff = o - r
        print(f"| {k:0.1f}% | {r} | {o} | {diff:+d} |")

if __name__ == "__main__":
    run_comparison()
