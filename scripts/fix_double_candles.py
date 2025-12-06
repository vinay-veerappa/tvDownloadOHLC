"""
Resample ES1 and NQ1 data from 1m to higher timeframes with consistent intervals.
This fixes the "double candle" issue caused by irregular timestamps.
"""

import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]

# Define resampling rules: target_tf -> pandas resample rule
resample_rules = {
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1D": "1D",
    "1W": "1W"
}

def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLC data to a larger timeframe."""
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Resample with proper OHLC aggregation
    resampled = df.resample(rule, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Drop rows with NaNs (no data in that period)
    resampled = resampled.dropna()
    
    return resampled

def process_ticker(ticker: str):
    print(f"\n=== Processing {ticker} ===")
    
    # Load 1m data (source)
    source_file = data_dir / f"{ticker}_1m.parquet"
    if not source_file.exists():
        print(f"  ERROR: {source_file} not found!")
        return
    
    df_1m = pd.read_parquet(source_file)
    print(f"  Loaded 1m data: {len(df_1m)} bars")
    print(f"  Date range: {df_1m.index.min()} to {df_1m.index.max()}")
    
    # Resample to each target timeframe
    for tf, rule in resample_rules.items():
        output_file = data_dir / f"{ticker}_{tf}.parquet"
        
        try:
            resampled = resample_ohlc(df_1m, rule)
            
            # Check time gaps (for validation)
            time_diffs = resampled.index.to_series().diff()
            gap_counts = time_diffs.value_counts().head(3)
            
            print(f"\n  {tf}: {len(resampled)} bars")
            print(f"    Primary gap: {gap_counts.index[0]} ({gap_counts.iloc[0]} bars)")
            
            # Save to parquet
            resampled.to_parquet(output_file)
            print(f"    Saved to {output_file}")
            
        except Exception as e:
            print(f"  ERROR resampling to {tf}: {e}")

if __name__ == "__main__":
    for ticker in tickers:
        process_ticker(ticker)
    
    print("\n=== Done! ===")
    print("Restart the dev server to see the changes.")
