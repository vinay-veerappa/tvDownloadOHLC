"""Convert all TV_OHLC CSV files to parquet with proper handling"""
import pandas as pd
from pathlib import Path
import re

source_dir = Path("data/TV_OHLC")
output_dir = Path("data")

ticker_map = {
    "CME_MINI_ES1!": "ES1",
    "CME_MINI_NQ1!": "NQ1",
    "CME_MINI_RTY1!": "RTY1",
    "CBOT_MINI_YM1!": "YM1",
    "COMEX_GC1!": "GC1",
    "NYMEX_CL1!": "CL1",
    "BATS_QQQ": "QQQ",
    "BATS_SPY": "SPY",
    "SP_SPX": "SPX",
    "CBOE_DLY_SPX": "SPX",
    "TVC_VIX": "VIX",
    "CBOE_DLY_VVIX": "VVIX",
}

interval_map = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "60": "1h",
    "240": "4h",
    "1D": "1D",
    "1W": "1W",
}

def process_csv(csv_file: Path) -> tuple:
    """Process a single CSV file and return (ticker, timeframe, df) or None"""
    filename = csv_file.stem
    
    # Handle selenium download format: TICKER_tf_date_type.csv
    selenium_match = re.match(r"(\w+)_(\d+m?)_\d+_", filename)
    if selenium_match:
        ticker = selenium_match.group(1)
        tf_raw = selenium_match.group(2)
        if tf_raw.endswith("m"):
            timeframe = tf_raw
        else:
            timeframe = interval_map.get(tf_raw, tf_raw)
        return ticker, timeframe, csv_file
    
    # Handle TradingView format: EXCHANGE_TICKER!, INTERVAL_HASH.csv
    if ", " in filename:
        parts = filename.split(", ")
        if len(parts) == 2:
            tv_ticker = parts[0]
            interval_part = parts[1].split("_")[0].split(" ")[0]
            
            ticker = ticker_map.get(tv_ticker)
            timeframe = interval_map.get(interval_part)
            
            if ticker and timeframe:
                return ticker, timeframe, csv_file
    
    return None

# Collect all files to process
files_to_process = []
for csv_file in sorted(source_dir.rglob("*.csv")):
    result = process_csv(csv_file)
    if result:
        files_to_process.append(result)

# Group by ticker and timeframe
processed = {}
for ticker, timeframe, csv_file in files_to_process:
    key = f"{ticker}_{timeframe}"
    
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
        else:
            df["volume"] = df["volume"].fillna(0)
        
        df["datetime"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("datetime")
        df = df.drop(columns=["time"])
        
        # Normalize timeframe for the key (1D -> 1d)
        timeframe_norm = timeframe.lower()
        key = f"{ticker}_{timeframe_norm}"

        if key in processed:
            processed[key] = pd.concat([processed[key], df])
        else:
            processed[key] = df
            
    except Exception as e:
        print(f"ERROR reading {csv_file.name}: {e}")

# Merge with existing and save
for key, df in processed.items():
    output_path = output_dir / f"{key}.parquet"
    timeframe = key.split("_")[-1]
    
    # Merge with existing if present
    if output_path.exists():
        if timeframe in ["1d", "1w"]:
            print(f"  Overwriting {output_path} with new Official TV data...")
        else:
            try:
                existing = pd.read_parquet(output_path)
                # Ensure existing has no timezone
                if existing.index.tz is not None:
                    existing.index = existing.index.tz_localize(None)
                
                # Ensure new df has no timezone
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                    
                df = pd.concat([existing, df])
            except Exception as e:
                print(f"Warning: Could not merge with existing {output_path}: {e}")
                pass
    
    # Remove duplicates and sort
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    
    # Save
    df.to_parquet(output_path)
    
    has_vol = (df["volume"] > 0).any()
    vol_str = "VOL" if has_vol else "no vol"
    print(f"{key}: {df.index.min().date()} to {df.index.max().date()} ({len(df):,} bars, {vol_str})")

print()
print("Done!")
