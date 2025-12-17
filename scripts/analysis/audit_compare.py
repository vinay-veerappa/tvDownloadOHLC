import pandas as pd
import sys
from pathlib import Path
import data_utils
from datetime import timedelta

def audit_compare(csv_path, parquet_path):
    print(f"Auditing Structure:\n  CSV: {csv_path}\n  PQ:  {parquet_path}\n")
    
    # 1. READ CSV (Simulate Import Logic for 1m ES1)
    df_csv = pd.read_csv(csv_path, sep=',', header=0) 
    df_csv.columns = [c.strip().lower() for c in df_csv.columns]
    
    # Rename basic
    rename_map = {
        'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume',
        'vol': 'volume', 'date': 'date_str', 'time': 'time_str'
    }
    df_csv.rename(columns=rename_map, inplace=True)
    
    # Parse Dates Quick (Assuming established format for speed)
    # The error was here: using 'date' instead of 'date_str'
    df_csv['datetime'] = pd.to_datetime(df_csv['date_str'] + ' ' + df_csv['time_str'])
    df_csv.set_index('datetime', inplace=True)
    df_csv.sort_index(inplace=True)
    
    # TRANSFORMATION 1: Timezone (Exchange -> NY)
    if df_csv.index.tz is None:
        df_csv.index = df_csv.index.tz_localize('US/Central', ambiguous='infer')
        df_csv.index = df_csv.index.tz_convert('America/New_York')
        
    # TRANSFORMATION 2: Shift (Close -> Open) - 1 Minute
    df_csv.index = df_csv.index - timedelta(minutes=1)

    # 2. READ PARQUET
    df_pq = pd.read_parquet(parquet_path)
    
    # 3. INTERSECT
    common_idx = df_csv.index.intersection(df_pq.index)
    print(f"Overlap: {len(common_idx)} bars")
    
    if len(common_idx) == 0:
        print("No overlap.")
        return

    csv_overlap = df_csv.loc[common_idx]
    pq_overlap = df_pq.loc[common_idx]
    
    # 4. SHAPE ANALYSIS
    # Calculate Range (H-L) and Body (C-O)
    range_csv = csv_overlap['high'] - csv_overlap['low']
    range_pq  = pq_overlap['high'] - pq_overlap['low']
    
    body_csv  = csv_overlap['close'] - csv_overlap['open']
    body_pq   = pq_overlap['close'] - pq_overlap['open']
    
    # Compare Shapes (Should be identical even if price level is shifted)
    range_diff = range_pq - range_csv
    body_diff  = body_pq - body_csv
    
    print("\n--- Shape Consistency (Range: High-Low) ---")
    print(range_diff.describe())
    
    print("\n--- Shape Consistency (Body: Close-Open) ---")
    print(body_diff.describe())
    
    # Check strict equality (allow float error)
    perfect_ranges = (range_diff.abs() < 0.01).sum()
    perfect_bodies = (body_diff.abs() < 0.01).sum()
    
    print(f"\nPerfect Range Match: {perfect_ranges} / {len(common_idx)} ({perfect_ranges/len(common_idx):.1%})")
    print(f"Perfect Body Match:  {perfect_bodies} / {len(common_idx)} ({perfect_bodies/len(common_idx):.1%})")
    
    # Volume Check
    vol_diff = pq_overlap['volume'] - csv_overlap['volume']
    print(f"\nMean Volume Diff: {vol_diff.mean():.2f}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        audit_compare(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python scripts/audit_compare.py <csv_path> <parquet_path>")
