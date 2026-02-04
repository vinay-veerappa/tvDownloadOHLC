
import pandas as pd
import json
import math

# Files to check
NQ_BADJ = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
NQ_ROOT = "data/TV_OHLC/CME_MINI_NQ1!, 1_23f45.csv"
ES_BADJ = "data/TV_OHLC/Badj/CME_MINI_ES1!, 1D_fdb65.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584

def get_bucket(val):
    if pd.isna(val): return 0.0
    mag = abs(val)
    b = math.floor(round(mag, 4) * 10) / 10.0
    return b if b < 5.0 else 5.0

def score_window(curr_h, ref_high):
    max_d = 0
    err = 0
    all_k = set(curr_h.keys()) | set(ref_high.keys())
    for k in all_k:
        d = abs(curr_h.get(k, 0) - ref_high.get(k, 0))
        err += d
        if d > max_d: max_d = d
    return max_d, err

def test_file(path, ref_high, label):
    print(f"\n--- Testing {label} ({path}) ---")
    try:
        # Detect if it's TV export (has time, open, high, low, close, volume)
        df = pd.read_csv(path)
        # Standardize columns
        df.columns = [c.lower() for c in df.columns]
        
        days = []
        for i, row in df.iterrows():
            op = row['open']
            hi = row['high']
            if op > 0:
                pct = (hi - op) / op * 100
                days.append(get_bucket(pct))
        
        if len(days) < TARGET_COUNT:
            print(f"Skipping: Only {len(days)} samples available.")
            return

        curr_h = {}
        for i in range(TARGET_COUNT):
            b = days[i]
            curr_h[b] = curr_h.get(b, 0) + 1
            
        best_m = 999
        best_e = 999
        best_idx = 0
        
        for i in range(len(days) - TARGET_COUNT + 1):
            m, e = score_window(curr_h, ref_high)
            if m < best_m or (m == best_m and e < best_e):
                best_m = m
                best_e = e
                best_idx = i
            
            if i < len(days) - TARGET_COUNT:
                curr_h[days[i]] -= 1
                if curr_h[days[i]] == 0: del curr_h[days[i]]
                curr_h[days[i+TARGET_COUNT]] = curr_h.get(days[i+TARGET_COUNT], 0) + 1
        
        print(f"Best MaxDiff: {best_m}, TotalErr: {best_e}")
        # Print date if available (assuming index 0 is first column or similar)
        # For simplicity, just reporting the best scores.
    except Exception as e:
        print(f"Error: {e}")

def run():
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    ref_high = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}

    test_file(NQ_BADJ, ref_high, "NQ Badj")
    test_file(NQ_ROOT, ref_high, "NQ Root")
    test_file(ES_BADJ, ref_high, "ES Badj")

if __name__ == "__main__":
    run()
