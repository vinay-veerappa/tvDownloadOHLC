import pandas as pd
import os
import argparse
from pathlib import Path

import merge_tv_ohlc

def normalize_timeframe(tf):
    """Normalize timeframe string to standard format (e.g., '5' -> '5m')."""
    if tf.isdigit():
        return f"{tf}m"
    return tf

def convert_csv_to_parquet(ticker, timeframe="1m"):
    """Convert {ticker}_{timeframe}_continuous.csv to Parquet format with timeframe aggregations"""
    
    # Clean ticker name
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    
    # Normalize timeframe
    tf_clean = normalize_timeframe(timeframe)
    
    # Read the CSV
    csv_path = os.path.join("data", f"{ticker_clean}_{tf_clean}_continuous.csv")
    print(f"Loading CSV data from: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"Error: Input file {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Parse datetime
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['datetime'] = df['datetime'].dt.tz_convert('US/Eastern')
    else:
        df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Keep only OHLCV columns (and Volume if present)
    ohlc_columns = ['open', 'high', 'low', 'close']
    if 'volume' in df.columns:
        ohlc_columns.append('volume')
    if 'vol' in df.columns: # Sometimes named 'vol'
        df.rename(columns={'vol': 'volume'}, inplace=True)
    if 'Volume' in df.columns: # Sometimes named 'Volume'
        df.rename(columns={'Volume': 'volume'}, inplace=True)
        
    # Volume added above if present
        
    df = df[ohlc_columns]
    
    print(f"Total bars: {len(df):,}")
    if not df.empty:
        print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    # Save base data
    parquet_file = data_dir / f"{ticker_clean}_{tf_clean}.parquet"
    df.to_parquet(parquet_file, compression='snappy')
    
    # Merge history for base timeframe
    merge_tv_ohlc.merge_history(ticker_clean, tf_clean, str(parquet_file))
    
    print(f"\n✓ Saved {tf_clean} data: {parquet_file}")
    print(f"  Size: {os.path.getsize(parquet_file) / 1024 / 1024:.2f} MB")
    
    # Only create aggregated timeframes if base is 1m
    if tf_clean == "1m":
        # Create aggregated timeframes
        timeframes = {
            '5m': '5T',
            '15m': '15T',
            '1h': '1H',
            '4h': '4H',
            '1D': '1D'
        }
        
        print("\nCreating aggregated timeframes...")
        for name, freq in timeframes.items():
            agg_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }
            if 'volume' in df.columns:
                agg_dict['volume'] = 'sum'
                
            agg_df = df.resample(freq).agg(agg_dict).dropna()
            
            output_file = data_dir / f"{ticker_clean}_{name}.parquet"
            agg_df.to_parquet(output_file, compression='snappy')
            
            # Merge history for aggregated timeframe
            merge_tv_ohlc.merge_history(ticker_clean, name, str(output_file))
            
            print(f"✓ Saved {name} data: {output_file}")
            print(f"  Bars: {len(agg_df):,}, Size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    else:
        print(f"\nSkipping aggregation for base timeframe {tf_clean}. Only base parquet created.")
    
    print("\n✅ Conversion complete!")
    print(f"\nAll data stored in: {data_dir.absolute()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert stitched CSV to Parquet for a specific ticker.")
    parser.add_argument("--ticker", type=str, default="ES1!", help="Ticker symbol (e.g., ES1!, NQ1!)")
    parser.add_argument("--timeframe", type=str, default="1m", help="Timeframe to convert (e.g., 1m, 5m). Default: 1m")
    args = parser.parse_args()
    
    convert_csv_to_parquet(args.ticker, args.timeframe)
