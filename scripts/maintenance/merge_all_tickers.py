"""
Merge all NinjaTrader ticker data - checks for deltas and merges new data
Handles: ES, NQ, CL, GC, RTY, YM
"""

import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime

# Configuration
NEW_DATA_DIR = Path("data/NinjaTrader/24Dec2025")
DATA_DIR = Path("data")
BACKUP_DIR = Path("data/backup")

# Ticker mapping: NinjaTrader filename prefix -> parquet filename
TICKER_MAP = {
    "ES": "ES1",
    "NQ": "NQ1", 
    "CL": "CL1",
    "GC": "GC1",
    "RTY": "RTY1",
    "YM": "YM1"
}

def find_ninja_csv(ticker_prefix):
    """Find the NinjaTrader CSV file for a given ticker prefix"""
    for f in NEW_DATA_DIR.glob(f"{ticker_prefix}*.csv"):
        if "TICK" not in f.name:  # Skip tick data
            return f
    return None

def load_ninja_csv(csv_path):
    """Load and parse NinjaTrader CSV to match parquet format"""
    df = pd.read_csv(csv_path, usecols=['Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%m/%d/%Y %H:%M:%S')
    df['Datetime'] = df['Datetime'].dt.tz_localize('America/New_York')
    df = df.set_index('Datetime')
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    df['time'] = df.index.astype('int64') // 10**9
    return df

def merge_ticker(ninja_prefix, parquet_prefix):
    """Merge new data for a single ticker"""
    print(f"\n{'='*60}")
    print(f"Processing: {ninja_prefix} -> {parquet_prefix}")
    print("=" * 60)
    
    # Find files
    csv_path = find_ninja_csv(ninja_prefix)
    parquet_path = DATA_DIR / f"{parquet_prefix}_1m.parquet"
    
    if not csv_path:
        print(f"  ⚠️  No CSV found for {ninja_prefix}")
        return 0
    
    if not parquet_path.exists():
        print(f"  ⚠️  No parquet found: {parquet_path}")
        return 0
    
    print(f"  CSV: {csv_path.name}")
    print(f"  Parquet: {parquet_path.name}")
    
    # Load existing parquet
    print("\n  Loading existing parquet...")
    existing_df = pd.read_parquet(parquet_path)
    print(f"  Existing rows: {len(existing_df):,}")
    print(f"  Date range: {existing_df.index.min()} to {existing_df.index.max()}")
    
    # Load new CSV
    print("\n  Loading new NinjaTrader CSV...")
    new_df = load_ninja_csv(csv_path)
    print(f"  New CSV rows: {len(new_df):,}")
    print(f"  Date range: {new_df.index.min()} to {new_df.index.max()}")
    
    # Find new rows
    print("\n  Finding new rows...")
    new_indices = new_df.index.difference(existing_df.index)
    new_rows = new_df.loc[new_indices]
    print(f"  New rows to add: {len(new_rows):,}")
    
    if len(new_rows) == 0:
        print("  ✅ No new data to merge")
        return 0
    
    print(f"  New data range: {new_rows.index.min()} to {new_rows.index.max()}")
    
    # Summary by month
    monthly = new_rows.groupby(new_rows.index.to_period('M')).size()
    print("\n  New rows by month:")
    for period, count in monthly.items():
        print(f"    {period}: {count:,}")
    
    # Backup
    backup_path = BACKUP_DIR / f"{parquet_prefix}_1m_pre_merge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(parquet_path, backup_path)
    print(f"\n  Backed up to: {backup_path}")
    
    # Merge
    merged_df = pd.concat([existing_df, new_rows])
    merged_df = merged_df.sort_index()
    merged_df = merged_df[~merged_df.index.duplicated(keep='last')]
    print(f"  Merged rows: {len(merged_df):,}")
    
    # Save
    merged_df.to_parquet(parquet_path)
    print(f"  ✅ Saved to: {parquet_path}")
    
    return len(new_rows)

def main():
    print("\n" + "=" * 60)
    print("NinjaTrader Data Merge - All Tickers")
    print("=" * 60)
    print(f"Source: {NEW_DATA_DIR}")
    print(f"Target: {DATA_DIR}")
    
    total_new = 0
    results = []
    
    for ninja_prefix, parquet_prefix in TICKER_MAP.items():
        new_rows = merge_ticker(ninja_prefix, parquet_prefix)
        total_new += new_rows
        results.append((parquet_prefix, new_rows))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for ticker, count in results:
        status = "✅" if count > 0 else "—"
        print(f"  {status} {ticker}: {count:,} new rows")
    print(f"\n  Total new rows: {total_new:,}")
    print("\nRun chunk regeneration for tickers with new data!")

if __name__ == "__main__":
    main()
