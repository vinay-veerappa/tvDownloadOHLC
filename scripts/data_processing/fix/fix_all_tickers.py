import pandas as pd
import data_utils
from pathlib import Path

tickers = ["CL1", "RTY1", "YM1"]  # GC1 is already fixed

for t in tickers:
    path = Path(f"data/{t}_1m.parquet")
    if not path.exists():
        print(f"Skipping {t}: Not found")
        continue

    print(f"\n--- Fixing {t} ---")
    print(f"Reading {path}...")
    try:
        df = pd.read_parquet(path)
        print(f"Loaded {len(df):,} rows.")
        
        if not isinstance(df.index, pd.DatetimeIndex):
             # Try to recover index from column if needed, or assume it's just wrong type
             # But usually it's correct index, just missing time column
             print("Warning: Index is not DatetimeIndex. Attempting conversion...")
             df.index = pd.to_datetime(df.index)

        # Force recalculate 'time' column to remove NaNs
        df['time'] = df.index.astype(int) // 10**9

        # Fill any remaining NaNs (though there shouldn't be any if index is valid)
        if df['time'].isna().any():
             print("Found NaNs in time, filling...")
             df['time'] = df['time'].fillna(0).astype(int)
        
        print("Saving...")
        data_utils.safe_save_parquet(df, str(path))
        print(f"✅ Fixed {t}")

    except Exception as e:
        print(f"❌ Failed to fix {t}: {e}")
