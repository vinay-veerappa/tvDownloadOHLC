"""
Merge historical and recent daily data with +24h offset for futures.
"""
import pandas as pd
from pathlib import Path

output_dir = Path("data")
historical_dir = Path("data/TV_OHLC/New folder")
recent_dir = Path("data/TV_OHLC")

# Files to merge: (historical_file, recent_file, ticker, timeframe)
merge_configs = [
    ("CME_MINI_ES1!, 1D_74842.csv", "CME_MINI_ES1!, 1D_33a40.csv", "ES1", "1D"),
    ("CME_MINI_NQ1!, 1D_b42dd.csv", "CME_MINI_NQ1!, 1D_88908.csv", "NQ1", "1D"),
    ("CBOT_MINI_YM1!, 1D_bfd9c.csv", "CBOT_MINI_YM1!, 1D_ece14.csv", "YM1", "1D"),
    ("CME_MINI_RTY1!, 1D_1fb58.csv", "CME_MINI_RTY1!, 1D_b438e.csv", "RTY1", "1D"),
    ("COMEX_GC1!, 1D_0f855.csv", "COMEX_GC1!, 1D_574da.csv", "GC1", "1D"),
    ("NYMEX_CL1!, 1D_f7492.csv", "NYMEX_CL1!, 1D_d28d9.csv", "CL1", "1D"),
]

def load_and_convert(csv_path: Path, apply_offset: bool = True) -> pd.DataFrame:
    """Load CSV and convert with optional +24h offset"""
    df = pd.read_csv(csv_path)
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
    
    # Apply +24h offset for futures
    if apply_offset:
        df["datetime"] = df["datetime"] + pd.Timedelta(hours=24)
    
    df = df.set_index("datetime")
    df = df.drop(columns=["time"])
    
    return df

for hist_file, recent_file, ticker, timeframe in merge_configs:
    print(f"\n{ticker}_{timeframe}:")
    
    # Load historical
    hist_path = historical_dir / hist_file
    if hist_path.exists():
        df_hist = load_and_convert(hist_path, apply_offset=True)
        print(f"  Historical: {df_hist.index.min().date()} to {df_hist.index.max().date()} ({len(df_hist)} bars)")
    else:
        df_hist = pd.DataFrame()
        print(f"  Historical: NOT FOUND")
    
    # Load recent
    recent_path = recent_dir / recent_file
    if recent_path.exists():
        df_recent = load_and_convert(recent_path, apply_offset=True)
        print(f"  Recent: {df_recent.index.min().date()} to {df_recent.index.max().date()} ({len(df_recent)} bars)")
    else:
        df_recent = pd.DataFrame()
        print(f"  Recent: NOT FOUND")
    
    # Merge
    if len(df_hist) > 0 or len(df_recent) > 0:
        df = pd.concat([df_hist, df_recent])
        df = df[~df.index.duplicated(keep="last")]  # Keep recent data for overlaps
        df = df.sort_index()
        
        # Save
        output_path = output_dir / f"{ticker}_{timeframe}.parquet"
        df.to_parquet(output_path)
        
        has_vol = (df["volume"] > 0).any()
        vol_str = "VOL" if has_vol else "no vol"
        print(f"  Merged: {df.index.min().date()} to {df.index.max().date()} ({len(df):,} bars, {vol_str})")

print("\n\nDone! Historical and recent data merged with +24h offset.")
