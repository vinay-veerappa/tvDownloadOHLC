import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]
timeframes = ["5m", "15m", "1h", "4h", "1D"]

def resample_ohlc(df, rule):
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
        
    resampled = df.resample(rule, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    # Drop rows with NaNs (gaps)
    resampled = resampled.dropna()
    return resampled

for ticker in tickers:
    print(f"Processing {ticker}...")
    
    # Load 1m data (Source of Truth)
    p1m_path = data_dir / f"{ticker}_1m.parquet"
    if not p1m_path.exists():
        print(f"  Skipping {ticker}, 1m file not found.")
        continue
        
    df_1m = pd.read_parquet(p1m_path)
    start_1m = df_1m.index.min()
    print(f"  1m data starts at {start_1m}")
    
    for tf in timeframes:
        tf_path = data_dir / f"{ticker}_{tf}.parquet"
        if not tf_path.exists():
            print(f"  Creating new {tf} file from 1m data...")
            # If file doesn't exist, just create it from 1m
            rule = tf.replace('m', 'T').replace('d', 'D') # pandas offset aliases
            if tf == '1h': rule = '1H'
            if tf == '4h': rule = '4H'
            if tf == '1D': rule = '1D'
            
            df_new = resample_ohlc(df_1m, rule)
            df_new.to_parquet(tf_path)
            continue
            
        # Load existing TF data
        df_old = pd.read_parquet(tf_path)
        
        # Split old data: keep only what is BEFORE the 1m data starts
        # We want to replace everything from start_1m onwards with the new 1m aggregation
        df_history = df_old[df_old.index < start_1m]
        
        print(f"  {tf}: Keeping {len(df_history)} rows of history (before {start_1m})")
        
        # Resample 1m to this TF
        rule = tf.replace('m', 'T')
        if tf == '1h': rule = '1H'
        if tf == '4h': rule = '4H'
        if tf == '1D': rule = '1D'
        
        df_recent = resample_ohlc(df_1m, rule)
        
        # Concatenate
        df_final = pd.concat([df_history, df_recent])
        
        # Sort just in case
        df_final = df_final.sort_index()
        
        # Deduplicate indices (keep last, which is the new one if overlap occurred exactly at boundary)
        df_final = df_final[~df_final.index.duplicated(keep='last')]
        
        # Save
        df_final.to_parquet(tf_path)
        print(f"  {tf}: Saved merged file with {len(df_final)} rows.")

print("Done.")
