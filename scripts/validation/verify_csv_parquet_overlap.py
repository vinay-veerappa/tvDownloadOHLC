
import pandas as pd
from pathlib import Path
import pytz
from datetime import timedelta

def verify_overlap(csv_path, ticker, timezone="America/Los_Angeles"):
    print(f"Verifying overlap for {ticker} using source TZ: {timezone}")
    
    # 1. Read CSV Sample (first 100 rows)
    # Assuming NinjaTrader format based on previous checks
    try:
        df_csv = pd.read_csv(csv_path)
        # Normalize columns
        df_csv.columns = [c.strip().lower() for c in df_csv.columns]
        
        # Parse datetime
        # NinjaTrader Example: 1/2/2008, 03:00:00
        # If date/time separate
        if 'date' in df_csv.columns and 'time' in df_csv.columns:
            df_csv['datetime'] = pd.to_datetime(df_csv['date'].astype(str) + ' ' + df_csv['time'].astype(str))
        else:
            # Maybe joined?
            print("Could not auto-detect Date/Time columns.")
            print(df_csv.columns)
            return

        df_csv.set_index('datetime', inplace=True)
        # Localize
        df_csv.index = df_csv.index.tz_localize(timezone) # Source TZ
        
        # Convert to Eastern for comparison
        df_csv.index = df_csv.index.tz_convert('US/Eastern')
        
        # NinjaTrader is Close Time. Parquet is Open Time.
        # Shift CSV BACK by 1 minute to match Parquet
        df_csv.index = df_csv.index - timedelta(minutes=1)
        
        csv_start = df_csv.index.min()
        csv_end = df_csv.index.max()
        print(f"CSV Range (Shifted & Eastern): {csv_start} to {csv_end}")
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 2. Read Parquet Sample (around CSV start)
    parquet_path = Path(f"data/{ticker}_1m.parquet")
    if not parquet_path.exists():
        print("Parquet file not found.")
        return
        
    df_pq = pd.read_parquet(parquet_path)
    if df_pq.index.tz is None:
        df_pq.index = df_pq.index.tz_localize('UTC').tz_convert('US/Eastern')
    else:
        df_pq.index = df_pq.index.tz_convert('US/Eastern')

    # Find overlap
    overlap_start = max(csv_start, df_pq.index.min())
    overlap_end = min(csv_end, df_pq.index.max())
    
    if overlap_start > overlap_end:
        print("❌ No overlap found between CSV and Parquet.")
        print(f"Parquet Range: {df_pq.index.min()} to {df_pq.index.max()}")
        return

    print(f"Found Overlap: {overlap_start} to {overlap_end}")
    
    # Compare first 5 overlapping points
    csv_slice = df_csv[(df_csv.index >= overlap_start) & (df_csv.index <= overlap_end)].head(5)
    pq_slice = df_pq[(df_pq.index >= overlap_start) & (df_pq.index <= overlap_end)].head(5)
    
    print("\n--- Comparison (Top 5 Overlap) ---")
    print("CSV (Shifted -1m, Converted to Eastern):")
    print(csv_slice[['open', 'high', 'low', 'close', 'volume']])
    print("\nParquet (Existing Reference):")
    print(pq_slice[['open', 'high', 'low', 'close', 'volume']])
    
    # Check Price Match
    matches = 0
    common_indices = csv_slice.index.intersection(pq_slice.index)
    for idx in common_indices:
        c_close = csv_slice.loc[idx, 'close']
        p_close = pq_slice.loc[idx, 'close']
        if abs(c_close - p_close) < 0.1:
            matches += 1
            
    print(f"\nMatched {matches}/{len(common_indices)} overlapping rows exactly.")
    if matches == len(common_indices) and len(common_indices) > 0:
        print("✅ VERIFIED: Timezone and Shift seem correct!")
    else:
        print("❌ MISMATCH: Data does not align. Check Timezone or Shift.")

if __name__ == "__main__":
    verify_overlap("data/Ninjatrader/NQ Monday 1755.csv", "NQ1")
