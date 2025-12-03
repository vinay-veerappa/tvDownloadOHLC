import pandas as pd
import os
import argparse
from pathlib import Path

def convert_csv_to_parquet(ticker):
    """Convert {ticker}_1m_continuous.csv to Parquet format with timeframe aggregations"""
    
    # Clean ticker name
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    
    # Read the CSV
    csv_path = os.path.join("data", f"{ticker_clean}_1m_continuous.csv")
    print(f"Loading CSV data from: {csv_path}")
    
    if not os.path.exists(csv_path):
        print(f"Error: Input file {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Parse datetime
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
        if 'volume' not in ohlc_columns: ohlc_columns.append('volume')
        
    df = df[ohlc_columns]
    
    print(f"Total bars: {len(df):,}")
    if not df.empty:
        print(f"Date range: {df.index.min()} to {df.index.max()}")
    
    # Save 1-minute data
    parquet_file = data_dir / f"{ticker_clean}_1m.parquet"
    df.to_parquet(parquet_file, compression='snappy')
    print(f"\n✓ Saved 1m data: {parquet_file}")
    print(f"  Size: {os.path.getsize(parquet_file) / 1024 / 1024:.2f} MB")
    
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
        
        print(f"✓ Saved {name} data: {output_file}")
        print(f"  Bars: {len(agg_df):,}, Size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    
    print("\n✅ Conversion complete!")
    print(f"\nAll data stored in: {data_dir.absolute()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert stitched CSV to Parquet for a specific ticker.")
    parser.add_argument("--ticker", type=str, default="ES1!", help="Ticker symbol (e.g., ES1!, NQ1!)")
    args = parser.parse_args()
    
    convert_csv_to_parquet(args.ticker)
