"""
Fresh import of ES data from the Dec 24 NinjaTrader CSV.
This completely replaces the existing ES1_1m.parquet with clean data.
"""
import pandas as pd
from pathlib import Path
import shutil

CSV_PATH = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")
OUTPUT_PATH = Path("data/ES1_1m.parquet")
BACKUP_PATH = Path("data/backup/ES1_1m_pre_clean_import.parquet")

def main():
    print("=== Fresh ES1 Import from NinjaTrader CSV ===")
    print(f"Source: {CSV_PATH}")
    
    # 1. Backup current file
    if OUTPUT_PATH.exists():
        print(f"Backing up current file to {BACKUP_PATH}...")
        shutil.copy(OUTPUT_PATH, BACKUP_PATH)
    
    # 2. Read CSV with robust settings
    print("Reading CSV (this takes a few minutes)...")
    col_names = ['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume', 'aux1', 'aux2', 'aux3']
    df = pd.read_csv(CSV_PATH, sep=',', on_bad_lines='skip', names=col_names, skiprows=1, engine='python', index_col=False)
    
    print(f"Raw rows: {len(df):,}")
    
    # 3. Parse datetime (PST source -> UTC)
    print("Parsing timestamps (PST -> UTC)...")
    df['datetime'] = pd.to_datetime(df['date_str'].astype(str) + ' ' + df['time_str'].astype(str), format='%m/%d/%Y %H:%M:%S')
    
    # Localize to PST, convert to UTC, strip timezone
    df['datetime'] = df['datetime'].dt.tz_localize('America/Los_Angeles').dt.tz_convert('UTC').dt.tz_localize(None)
    
    # 4. Shift timestamps (NinjaTrader uses bar close time, we want bar open time)
    print("Shifting timestamps (Close -> Open)...")
    df['datetime'] = df['datetime'] - pd.Timedelta(minutes=1)
    
    # 5. Clean up columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']].copy()
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 6. Set index, sort, deduplicate
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    before_dedup = len(df)
    df = df[~df.index.duplicated(keep='last')]
    print(f"Deduplicated: {before_dedup - len(df):,} duplicates removed")
    
    # 7. Drop NaN rows
    df.dropna(subset=['close'], inplace=True)
    
    print(f"Final rows: {len(df):,}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    # 8. Check anomalies
    diffs = df['close'].diff().abs()
    anomalies = diffs[diffs > 80]
    print(f"Price anomalies (>80pt): {len(anomalies)}")
    
    # 9. Save
    print(f"Saving to {OUTPUT_PATH}...")
    df.to_parquet(OUTPUT_PATH)
    
    print("✅ Fresh import complete!")

if __name__ == "__main__":
    main()
