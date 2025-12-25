"""
Generic fresh import script for any ticker from NinjaTrader CSV.
Usage: python scripts/fresh_ticker_import.py <ticker> <csv_path>
"""
import pandas as pd
from pathlib import Path
import shutil
import sys

def fresh_import(ticker: str, csv_path: str):
    csv_path = Path(csv_path)
    output_path = Path(f"data/{ticker}_1m.parquet")
    backup_path = Path(f"data/backup/{ticker}_1m_pre_clean_import.parquet")
    
    print(f"=== Fresh {ticker} Import from NinjaTrader CSV ===")
    print(f"Source: {csv_path}")
    
    # 1. Backup current file
    if output_path.exists():
        print(f"Backing up to {backup_path}...")
        shutil.copy(output_path, backup_path)
    
    # 2. Read CSV
    print("Reading CSV...")
    col_names = ['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume', 'aux1', 'aux2', 'aux3']
    df = pd.read_csv(csv_path, sep=',', on_bad_lines='skip', names=col_names, skiprows=1, engine='python', index_col=False)
    
    print(f"Raw rows: {len(df):,}")
    
    # 3. Parse datetime (PST -> UTC)
    print("Parsing timestamps (PST -> UTC)...")
    df['datetime'] = pd.to_datetime(df['date_str'].astype(str) + ' ' + df['time_str'].astype(str), format='%m/%d/%Y %H:%M:%S')
    df['datetime'] = df['datetime'].dt.tz_localize('America/Los_Angeles').dt.tz_convert('UTC').dt.tz_localize(None)
    
    # 4. Shift timestamps (Close -> Open)
    print("Shifting timestamps (Close -> Open)...")
    df['datetime'] = df['datetime'] - pd.Timedelta(minutes=1)
    
    # 5. Clean columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']].copy()
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 6. Set index, sort, deduplicate
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    before_dedup = len(df)
    df = df[~df.index.duplicated(keep='last')]
    print(f"Deduplicated: {before_dedup - len(df):,} duplicates removed")
    
    # 7. Drop NaN
    df.dropna(subset=['close'], inplace=True)
    
    print(f"Final rows: {len(df):,}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    # 8. Check anomalies
    diffs = df['close'].diff().abs()
    anomalies = diffs[diffs > 80]
    print(f"Price anomalies (>80pt): {len(anomalies)}")
    
    # 9. Save
    print(f"Saving to {output_path}...")
    df.to_parquet(output_path)
    
    print(f"✅ Fresh {ticker} import complete!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fresh_ticker_import.py <ticker> <csv_path>")
        sys.exit(1)
    
    ticker = sys.argv[1]
    csv_path = sys.argv[2]
    fresh_import(ticker, csv_path)
