"""
Apply +24h timestamp offset to existing futures daily parquet files.
This preserves the full historical data while fixing the timestamp convention.
"""
import pandas as pd
from pathlib import Path

data_dir = Path("data")

# Futures tickers that need timestamp offset (23-hour overnight sessions)
FUTURES_TICKERS = ["ES1", "NQ1", "RTY1", "YM1", "GC1", "CL1"]

for ticker in FUTURES_TICKERS:
    daily_file = data_dir / f"{ticker}_1D.parquet"
    
    if not daily_file.exists():
        print(f"{ticker}_1D.parquet: Not found, skipping")
        continue
    
    # Load existing data
    df = pd.read_parquet(daily_file)
    
    print(f"{ticker}_1D.parquet:")
    print(f"  Before: {df.index.min()} to {df.index.max()} ({len(df):,} bars)")
    
    # Apply +24h offset to index
    df.index = df.index + pd.Timedelta(hours=24)
    
    # Save back
    df.to_parquet(daily_file)
    
    print(f"  After:  {df.index.min()} to {df.index.max()}")
    print(f"  Applied +24h offset")
    print()

print("Done! All futures daily timestamps shifted by +24 hours.")
