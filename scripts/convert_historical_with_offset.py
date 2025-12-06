"""
Convert historical CSV files from 'New folder' with +24h offset for futures daily.
This restores full historical data with correct timestamps.
"""
import pandas as pd
from pathlib import Path

source_dir = Path("data/TV_OHLC/New folder")
output_dir = Path("data")

# Map TradingView files to our tickers
files_to_convert = {
    # format: (csv_glob_pattern, ticker, timeframe, apply_offset)
    ("CME_MINI_ES1!, 1D_74842.csv", "ES1", "1D", True),
    ("CME_MINI_NQ1!, 1D_b42dd.csv", "NQ1", "1D", True),  
    ("CBOT_MINI_YM1!, 1D_bfd9c.csv", "YM1", "1D", True),
    ("CME_MINI_RTY1!, 1D_1fb58.csv", "RTY1", "1D", True),
    ("COMEX_GC1!, 1D_0f855.csv", "GC1", "1D", True),
    ("NYMEX_CL1!, 1D_f7492.csv", "CL1", "1D", True),
}

for filename, ticker, timeframe, apply_offset in files_to_convert:
    csv_file = source_dir / filename
    output_path = output_dir / f"{ticker}_{timeframe}.parquet"
    
    if not csv_file.exists():
        print(f"{filename}: NOT FOUND")
        continue
    
    try:
        df = pd.read_csv(csv_file)
        cols = [c.lower() for c in df.columns]
        df.columns = cols
        
        keep_cols = ["time", "open", "high", "low", "close"]
        if "volume" in cols:
            keep_cols.append("volume")
        df = df[keep_cols].copy()
        
        if "volume" not in df.columns:
            df["volume"] = 0
        
        # Convert Unix timestamp to datetime
        df["datetime"] = pd.to_datetime(df["time"], unit="s")
        
        # Apply +24h offset for daily futures
        if apply_offset:
            df["datetime"] = df["datetime"] + pd.Timedelta(hours=24)
        
        df = df.set_index("datetime")
        df = df.drop(columns=["time"])
        df = df.sort_index()
        
        # Save
        df.to_parquet(output_path)
        
        has_vol = (df["volume"] > 0).any()
        vol_str = "VOL" if has_vol else "no vol"
        offset_str = "(+24h offset)" if apply_offset else ""
        print(f"{ticker}_{timeframe}: {df.index.min().date()} to {df.index.max().date()} ({len(df):,} bars, {vol_str}) {offset_str}")
        
    except Exception as e:
        print(f"ERROR {ticker}_{timeframe}: {e}")
        import traceback
        traceback.print_exc()

print()
print("Done! Full historical data restored with +24h offset.")
