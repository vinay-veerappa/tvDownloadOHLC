import pandas as pd
from pathlib import Path
import sys

# Add scripts dir to path
sys.path.append(str(Path("scripts").resolve()))
from import_ninjatrader import import_ninjatrader_data
from regenerate_derived import regenerate_all
import data_utils

def purge_and_import():
    ticker = "NQ1"
    parquet_path = Path("data/NQ1_1m.parquet")
    csv_path = Path("data/NinjaTrader/NQ Monday 1755.csv")
    
    print(f"=== PURGING DECEMBER 2025 DATA FOR {ticker} ===")
    
    if not parquet_path.exists():
        print("Parquet file not found!")
        return
        
    # 1. Purge Bad Data
    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    original_len = len(df)
    
    # Define Cutoff: Dec 1, 2025
    cutoff_date = pd.Timestamp("2025-12-01", tz=df.index.tz)
    
    print(f"Purging data >= {cutoff_date}...")
    df_clean = df[df.index < cutoff_date]
    new_len = len(df_clean)
    
    print(f"Dropped {original_len - new_len} rows.")
    
    # Save the cleaned state temporarily
    data_utils.safe_save_parquet(df_clean, str(parquet_path))
    print("✅ Cleaned Parquet saved.")
    
    # 2. Re-Import from NinjaTrader (Clean Fill)
    print("\n=== RE-IMPORTING FROM NINJATRADER ===")
    import_ninjatrader_data(
        csv_path=csv_path,
        ticker=ticker,
        interval="1m",
        align=False,
        shift_to_open=True,
        timezone="America/Los_Angeles"
    )
    
    # 3. Regenerate
    print("\n=== REGENERATING DERIVED DATA ===")
    regenerate_all(ticker)

if __name__ == "__main__":
    purge_and_import()
