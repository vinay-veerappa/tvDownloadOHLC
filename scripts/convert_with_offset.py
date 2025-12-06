"""
Convert TV_OHLC CSV files to parquet with timestamp adjustments.
- Daily: Add 24 hours (timestamps use session start, not close)
- Weekly: Keep as-is (Sunday start is already correct)
"""
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
    "SP_SPX": "SPX",
}

# Futures tickers that need timestamp offset (23-hour overnight sessions)
FUTURES_TICKERS = {"ES1", "NQ1", "RTY1", "YM1", "GC1", "CL1"}

interval_map = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "60": "1h",
    "240": "4h",
    "1D": "1D",
    "1W": "1W",
}


def process_csv(csv_file: Path):
    """Process a single CSV file and return (ticker, timeframe) or None"""
    filename = csv_file.stem
    
    # Handle TradingView format: EXCHANGE_TICKER!, INTERVAL_HASH.csv
    if ", " in filename:
        parts = filename.split(", ")
        if len(parts) == 2:
            tv_ticker = parts[0]
            interval_part = parts[1].split("_")[0].split(" ")[0]
            
            ticker = ticker_map.get(tv_ticker)
            timeframe = interval_map.get(interval_part)
            
            if ticker and timeframe:
                return ticker, timeframe
    
    return None, None


def convert_file(csv_file: Path, ticker: str, timeframe: str) -> pd.DataFrame:
    """Convert a CSV file to DataFrame with proper timestamp handling"""
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
    
    # Apply 24-hour offset for daily FUTURES data (session start -> session date)
    # Stocks/ETFs (QQQ, SPX) don't need this adjustment
    if timeframe == "1D" and ticker in FUTURES_TICKERS:
        df["datetime"] = df["datetime"] + pd.Timedelta(hours=24)
        print(f"  Applied +24h offset for futures daily data")
    
    # Weekly data uses Sunday start timestamp - no adjustment needed
    # The week "Nov 30" represents the trading week Sun Nov 30 - Fri Dec 5
    
    df = df.set_index("datetime")
    df = df.drop(columns=["time"])
    df = df.sort_index()
    
    return df


# Process all CSV files
for csv_file in sorted(source_dir.glob("*.csv")):
    ticker, timeframe = process_csv(csv_file)
    
    if not ticker or not timeframe:
        continue
    
    output_path = output_dir / f"{ticker}_{timeframe}.parquet"
    
    try:
        df = convert_file(csv_file, ticker, timeframe)
        
        # Save (overwrite)
        df.to_parquet(output_path)
        
        has_vol = (df["volume"] > 0).any()
        vol_str = "VOL" if has_vol else "no vol"
        print(f"{ticker}_{timeframe}: {df.index.min().date()} to {df.index.max().date()} ({len(df):,} bars, {vol_str})")
        
    except Exception as e:
        print(f"ERROR {ticker}_{timeframe}: {e}")

print()
print("Done! Daily timestamps adjusted by +24 hours.")
