import pandas as pd
from pathlib import Path
import os

DATA_DIR = Path("data")
TIMEFRAMES = ["1h", "4h"] # Target timeframes

def resample_and_save(source_path, ticker):
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

        for tf in TIMEFRAMES:
            # Pandas rule: '1h', '4h'. 
            # Note 'h' is deprecated in strict pandas, 'h' -> 'H'? No, 'h' is usually fine or 'H'.
            # 'h' is lower case alias. 'H' is standard.
            rule = tf.upper().replace('M', 'T') # 1h -> 1H, 4h -> 4H. 
            
            print(f"  Resampling {ticker} to {tf}...")
            
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
            # Overwrite or Merge?
            # Ideally overwrite if source is authoritative. 
            # User said "upsample it".
            resampled.to_parquet(output_path)
            print(f"    Saved {output_path} ({len(resampled)} bars)")

    except Exception as e:
        print(f"Error resampling {source_path}: {e}")

def main():
    print(f"Scanning {DATA_DIR} for high-res parquet...")
    
    # gather files
    files = list(DATA_DIR.glob("*.parquet"))
    
    # Group by Ticker
    # Files: TICKER_TF.parquet
    ticker_sources = {}
    
    for f in files:
        parts = f.stem.split('_')
        if len(parts) < 2: continue
        tf = parts[-1]
        ticker = "_".join(parts[:-1])
        
        if tf in ['5m', '15m']:
            if ticker not in ticker_sources:
                ticker_sources[ticker] = []
            ticker_sources[ticker].append((tf, f))
            
    for ticker, sources in ticker_sources.items():
        # Pick best source: 5m > 15m
        # Sort by resolution (low numeric value of minutes is better)
        # 5m = 5, 15m = 15.
        
        def tf_weight(t):
            if t[0] == '5m': return 5
            if t[0] == '15m': return 15
            return 999
            
        sources.sort(key=tf_weight)
        best_source_tf, best_source_path = sources[0]
        
        print(f"Processing {ticker} using source: {best_source_tf}")
        resample_and_save(best_source_path, ticker)

if __name__ == "__main__":
    main()
