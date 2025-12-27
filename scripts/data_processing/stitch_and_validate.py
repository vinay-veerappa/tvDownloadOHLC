import pandas as pd
import glob
import os
import time
import argparse

def normalize_timeframe(tf):
    """Normalize timeframe string to standard format (e.g., '5' -> '5m')."""
    if tf.isdigit():
        return f"{tf}m"
    return tf

def stitch_and_validate(ticker, timeframe="1m"):
    # Clean ticker name to match downloader convention
    ticker_clean = ticker.upper().replace("!", "").replace(" ", "_")
    
    # Normalize timeframe
    tf_clean = normalize_timeframe(timeframe)
    
    # Path to downloads
    downloads_path = os.path.join(os.getcwd(), "data", f"downloads_{ticker_clean}")
    
    # Pattern now includes timeframe to avoid mixing 1m and 5m files
    # Downloader format: {ticker_clean}_{tf}_{timestamp}_{task}_{iteration}.csv
    # But old files might just be {ticker_clean}_1m_... or even without timeframe if very old.
    # We'll assume new format or fallback to *1m* if timeframe is 1m.
    
    pattern = os.path.join(downloads_path, f"*{tf_clean}*.csv")
    
    print(f"Looking for files in: {downloads_path} with pattern *{tf_clean}*")
    files = glob.glob(pattern)
    
    # Filter out "continuous" files if they accidentally got in there (though they shouldn't be in downloads dir)
    files = [f for f in files if "continuous" not in f]
    
    print(f"Found {len(files)} total files matching pattern.")
    
    if not files:
        print("No files found.")
        return

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            # Normalize column names
            df.columns = [c.lower() for c in df.columns]
            
            # Parse time
            time_col = df.columns[0]
            if pd.api.types.is_numeric_dtype(df[time_col]):
                df['datetime'] = pd.to_datetime(df[time_col], unit='s')
            else:
                df['datetime'] = pd.to_datetime(df[time_col])
                
            df.set_index('datetime', inplace=True)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not dfs:
        print("No valid dataframes.")
        return

    # Concatenate
    full_df = pd.concat(dfs)
    
    # Remove duplicates
    full_df = full_df[~full_df.index.duplicated(keep='first')]
    
    # Sort
    full_df.sort_index(inplace=True)
    
    print(f"Total rows: {len(full_df)}")
    if not full_df.empty:
        print(f"Date Range: {full_df.index.min()} to {full_df.index.max()}")
        
        # Check for gaps (approximate based on timeframe)
        # Parse timeframe string to minutes
        tf_minutes = 1
        if tf_clean.endswith('m'):
            tf_minutes = int(tf_clean[:-1])
        elif tf_clean.endswith('h'):
            tf_minutes = int(tf_clean[:-1]) * 60
        elif tf_clean.endswith('D'):
            tf_minutes = int(tf_clean[:-1]) * 1440
            
        expected_rows = (full_df.index.max() - full_df.index.min()).total_seconds() / (60 * tf_minutes)
        print(f"Expected rows (approx): {int(expected_rows)}")
        print(f"Actual rows: {len(full_df)}")
    
    # Save stitched
    output_file = os.path.join("data", f"{ticker_clean}_{tf_clean}_continuous.csv")
    full_df.to_csv(output_file)
    print(f"Saved stitched data to {output_file}")
    if not full_df.empty:
        print(full_df.head())
        print(full_df.tail())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stitch downloaded CSV files for a specific ticker.")
    parser.add_argument("--ticker", type=str, default="ES1!", help="Ticker symbol (e.g., ES1!, NQ1!)")
    parser.add_argument("--timeframe", type=str, default="1m", help="Timeframe to stitch (e.g., 1m, 5m). Default: 1m")
    args = parser.parse_args()
    
    stitch_and_validate(args.ticker, args.timeframe)
