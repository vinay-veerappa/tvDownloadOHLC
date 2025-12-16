
import pandas as pd
from pathlib import Path
import argparse
from datetime import timedelta

def verify_alignment(csv_path: str, ticker: str, timezone: str = "America/Los_Angeles", shift_minutes: int = 1):
    """
    Verifies alignment between a generic CSV and existing Parquet data.
    Useful for checking Timezone and Time Shift assumptions before importing.
    """
    print(f"=== VERIFY ALIGNMENT: {ticker} ===")
    print(f"Source CSV: {csv_path}")
    print(f"Assumed Source TZ: {timezone}")
    print(f"Assumed Shift: -{shift_minutes} min (Close->Open)")
    
    # 1. Read CSV Sample (first 1000 rows to find range)
    try:
        # Optimistic load
        df_csv = pd.read_csv(csv_path)
        df_csv.columns = [c.strip().lower() for c in df_csv.columns]
        
        # Parse datetime (NinjaTrader generic)
        if 'date' in df_csv.columns and 'time' in df_csv.columns:
            df_csv['datetime'] = pd.to_datetime(df_csv['date'].astype(str) + ' ' + df_csv['time'].astype(str))
        elif 'datetime' in df_csv.columns:
            df_csv['datetime'] = pd.to_datetime(df_csv['datetime'])
        else:
            print("❌ Could not auto-detect Date/Time columns.")
            print(f"Columns: {df_csv.columns}")
            return

        df_csv.set_index('datetime', inplace=True)
        # Localize & Convert
        df_csv.index = df_csv.index.tz_localize(timezone)
        df_csv.index = df_csv.index.tz_convert('US/Eastern')
        
        # Apply Shift
        df_csv.index = df_csv.index - timedelta(minutes=shift_minutes)
        
        csv_start = df_csv.index.min()
        csv_end = df_csv.index.max()
        print(f"CSV Range (Shifted & Eastern): {csv_start} to {csv_end}")
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return

    # 2. Read Parquet
    parquet_path = Path(f"data/{ticker}_1m.parquet")
    if not parquet_path.exists():
        print(f"❌ Parquet file not found: {parquet_path}")
        return
        
    df_pq = pd.read_parquet(parquet_path)
    if df_pq.index.tz is None:
        df_pq.index = df_pq.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df_pq.index = df_pq.index.tz_convert('US/Eastern')

    # 3. Find Overlap
    overlap_start = max(csv_start, df_pq.index.min())
    overlap_end = min(csv_end, df_pq.index.max())
    
    if overlap_start > overlap_end:
        print("❌ No overlapping date range found.")
        print(f"  CSV:     {csv_start} -> {csv_end}")
        print(f"  Parquet: {df_pq.index.min()} -> {df_pq.index.max()}")
        return

    print(f"✅ Found Overlap Window: {overlap_start} to {overlap_end}")
    
    # 4. Compare Samples
    # Compare first 5 overlapping points
    csv_slice = df_csv[(df_csv.index >= overlap_start) & (df_csv.index <= overlap_end)].sort_index().head(5)
    pq_slice = df_pq[(df_pq.index >= overlap_start) & (df_pq.index <= overlap_end)].sort_index().head(5)
    
    print("\n--- Comparison (First 5 Items) ---")
    print("CSV (Processed):")
    print(csv_slice[['open', 'high', 'low', 'close', 'volume']])
    print("\nParquet (Existing):")
    print(pq_slice[['open', 'high', 'low', 'close', 'volume']])
    
    # Check Price Match
    matches = 0
    common_indices = csv_slice.index.intersection(pq_slice.index)
    
    if len(common_indices) == 0:
        print("\n❌ NO TIMESTAMP MATCHES in first 5 sample rows.")
        print("Required Action: Adjust Timezone or Shift.")
        return

    for idx in common_indices:
        c_close = csv_slice.loc[idx, 'close']
        p_close = pq_slice.loc[idx, 'close']
        if abs(c_close - p_close) < 0.1:
            matches += 1
            
    print(f"\nMatched {matches}/{len(common_indices)} overlapping rows exactly.")
    if matches == len(common_indices) and len(common_indices) > 0:
        print("✅ SUCCESS: Data is aligned.")
    else:
        print("❌ MISMATCH: Prices do not match.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to CSV file")
    parser.add_argument("ticker", help="Ticker symbol")
    parser.add_argument("--tz", default="America/Los_Angeles", help="Source Timezone (default: America/Los_Angeles)")
    parser.add_argument("--shift", type=int, default=1, help="Shift minutes (Close->Open) (default: 1)")
    
    args = parser.parse_args()
    
    verify_alignment(args.file, args.ticker, args.tz, args.shift)
