import pandas as pd
from pathlib import Path
import os

DATA_DIR = Path("data")
TIMEFRAMES = ["5m", "15m", "1h", "4h"] # Target timeframes (excl 1d/1w as they need settlement)

def resample_and_save(source_path, source_tf, ticker):
    try:
        df = pd.read_parquet(source_path)
        
        # Ensure DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
             # Try column
             if 'datetime' in df.columns:
                 df = df.set_index('datetime')
             elif 'time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['time'], unit='s') if pd.api.types.is_numeric_dtype(df['time']) else pd.to_datetime(df['time'])
                 df = df.set_index('datetime')
             else:
                 print(f"Skipping {source_path}: No datetime index or column.")
                 return

        # Helper to convert TF string to minutes
        def tf_to_min(tf_str):
            if tf_str == '1m': return 1
            if tf_str == '5m': return 5
            if tf_str == '15m': return 15
            if tf_str == '1h': return 60
            if tf_str == '1d': return 1440
            return 9999

        source_min = tf_to_min(source_tf)

        for tf in TIMEFRAMES:
            target_min = tf_to_min(tf)
            if target_min <= source_min:
                continue # Don't downsample or equal sample
            
            rule = tf.upper().replace('M', 'T') # 1h -> 1H, 1d -> 1D
            
            print(f"  Resampling {ticker} ({source_tf} -> {tf})...")
            
            resampled = df.resample(rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            if resampled.empty:
                print(f"  Warning: Resampled {tf} is empty.")
                continue

            output_path = DATA_DIR / f"{ticker}_{tf}.parquet"
            # Overwrite since source (usually 1m or 5m) is authoritative
            resampled.to_parquet(output_path)
            print(f"    Saved {output_path} ({len(resampled)} bars)")

    except Exception as e:
        print(f"Error resampling {source_path}: {e}")

def main():
    print(f"Scanning {DATA_DIR} for high-res parquet...")
    
    files = list(DATA_DIR.glob("*.parquet"))
    ticker_sources = {}
    
    for f in files:
        parts = f.stem.split('_')
        if len(parts) < 2: continue
        tf = parts[-1]
        ticker = "_".join(parts[:-1])
        
        # Support 1m, 5m, 15m as sources
        if tf in ['1m', '5m', '15m']:
            if ticker not in ticker_sources:
                ticker_sources[ticker] = []
            ticker_sources[ticker].append((tf, f))
            
    for ticker, sources in ticker_sources.items():
        # Pick best source: 1m > 5m > 15m
        def tf_weight(t):
            if t[0] == '1m': return 1
            if t[0] == '5m': return 5
            if t[0] == '15m': return 15
            return 999
            
        sources.sort(key=tf_weight)
        best_source_tf, best_source_path = sources[0]
        
        print(f"Processing {ticker} using source: {best_source_tf}")
        resample_and_save(best_source_path, best_source_tf, ticker)

if __name__ == "__main__":
    main()
