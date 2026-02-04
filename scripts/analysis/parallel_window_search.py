"""
Parallel Window Search for Exact 4584-Day Period Match
Tests both Floor and Round methods, constrains windows to end before 2025
"""
import json
import numpy as np
import pandas as pd

# Configuration
UNADJUSTED_CSV = "data/TV_OHLC/Badj/CME_MINI_NQ1!, 1D_94cae.csv"
REF_JSON = "data/analysis/reference_data_full.json"
TARGET_COUNT = 4584
ANCHOR_DATE = "2006-10-01"
SEARCH_OFFSET = 150
MAX_END_DATE = "2024-12-31"  # Windows must end before 2025

def get_bucket_floor(pct_array):
    """Floor to 0.1%"""
    buckets = np.floor(np.round(pct_array, 4) * 10) / 10.0
    return np.clip(buckets, 0.0, 5.0)

def get_bucket_round(pct_array):
    """Round to 0.1%"""
    buckets = np.round(pct_array, 1)
    return np.clip(buckets, 0.0, 5.0)

def count_buckets(bucket_array, bucket_keys):
    counts = {}
    for k in bucket_keys:
        counts[k] = int(np.sum(bucket_array == k))
    return counts

def calc_max_diff(my_counts, ref_counts):
    all_keys = set(my_counts.keys()) | set(ref_counts.keys())
    return max(abs(my_counts.get(k, 0) - ref_counts.get(k, 0)) for k in all_keys)

def calc_total_error(my_counts, ref_counts):
    all_keys = set(my_counts.keys()) | set(ref_counts.keys())
    return sum(abs(my_counts.get(k, 0) - ref_counts.get(k, 0)) for k in all_keys)

def search_with_method(method_name, bucket_func, h_pct, l_pct, dates, ref_h, ref_l_abs, anchor_idx):
    """Run search with a specific bucketing method"""
    
    h_buckets = bucket_func(h_pct)
    l_buckets = bucket_func(l_pct)
    
    h_keys = sorted(ref_h.keys())
    l_keys = sorted(ref_l_abs.keys())
    
    # Find valid search range (windows ending before MAX_END_DATE)
    max_end_idx = np.where(dates <= MAX_END_DATE)[0][-1]
    
    start_idx = max(0, anchor_idx - SEARCH_OFFSET)
    end_idx = min(max_end_idx - TARGET_COUNT + 1, anchor_idx + SEARCH_OFFSET)
    
    results = []
    
    for i in range(start_idx, end_idx + 1):
        h_window = h_buckets[i : i + TARGET_COUNT]
        l_window = l_buckets[i : i + TARGET_COUNT]
        
        h_counts = count_buckets(h_window, h_keys)
        l_counts = count_buckets(l_window, l_keys)
        
        max_h = calc_max_diff(h_counts, ref_h)
        max_l = calc_max_diff(l_counts, ref_l_abs)
        max_diff = max(max_h, max_l)
        
        total_err = calc_total_error(h_counts, ref_h) + calc_total_error(l_counts, ref_l_abs)
        
        results.append({
            'method': method_name,
            'start_date': dates[i],
            'end_date': dates[i + TARGET_COUNT - 1],
            'max_diff': max_diff,
            'total_err': total_err,
            'h0': h_counts.get(0.0, 0),
            'l0': l_counts.get(0.0, 0)
        })
    
    return results

def main():
    print("=" * 70)
    print("PARALLEL WINDOW SEARCH - FLOOR vs ROUND")
    print(f"Anchor: {ANCHOR_DATE} | ±{SEARCH_OFFSET} days | Window ends before {MAX_END_DATE}")
    print("=" * 70)
    
    # Load Reference Data
    with open(REF_JSON, 'r') as f:
        ref_data = json.load(f)
    
    ref_h = {float(k): v for k, v in ref_data['distributions']['daily']['high'].items()}
    ref_l_abs = {abs(float(k)): v for k, v in ref_data['distributions']['daily']['low'].items()}
    
    # Load CSV Data
    df = pd.read_csv(UNADJUSTED_CSV)
    df['date'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d')
    
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    dates = df['date'].values
    
    h_pct = (highs - opens) / opens * 100
    l_pct = np.abs((lows - opens) / opens * 100)
    
    anchor_idx = np.where(dates >= ANCHOR_DATE)[0][0]
    
    print(f"\nData rows: {len(df)} | Anchor index: {anchor_idx}")
    
    # Search with both methods
    all_results = []
    
    for name, func in [("Floor", get_bucket_floor), ("Round", get_bucket_round)]:
        print(f"\nSearching with {name} method...")
        results = search_with_method(name, func, h_pct, l_pct, dates, ref_h, ref_l_abs, anchor_idx)
        all_results.extend(results)
        print(f"  Found {len(results)} windows")
    
    # Convert to DataFrame and sort
    results_df = pd.DataFrame(all_results)
    results_df = results_df.sort_values(['max_diff', 'total_err'])
    
    # Display results
    print("\n" + "=" * 90)
    print("TOP 20 CLOSEST MATCHES (sorted by MaxDiff, then TotalError)")
    print("=" * 90)
    print(f"{'Method':<6} | {'Start':<12} | {'End':<12} | {'MaxDiff':>7} | {'TotalErr':>8} | {'H0':>4} | {'L0':>4}")
    print("-" * 90)
    
    for _, row in results_df.head(20).iterrows():
        print(f"{row['method']:<6} | {row['start_date']:<12} | {row['end_date']:<12} | {row['max_diff']:>7} | {row['total_err']:>8} | {row['h0']:>4} | {row['l0']:>4}")
    
    print("\n" + "=" * 90)
    print("REFERENCE TARGETS: H0=305, L0=473")
    print("=" * 90)
    
    # Summary by method
    print("\nBEST RESULT PER METHOD:")
    for method in ["Floor", "Round"]:
        subset = results_df[results_df['method'] == method].head(1)
        if len(subset) > 0:
            row = subset.iloc[0]
            print(f"  {method}: MaxDiff={row['max_diff']}, Range={row['start_date']} to {row['end_date']}")

if __name__ == "__main__":
    main()
