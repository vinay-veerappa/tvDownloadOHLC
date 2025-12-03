import pandas as pd
import glob
import os
import numpy as np

def process_market_data():
    # Configuration
    downloads_dir = os.path.join(os.getcwd(), "downloads_es_futures")
    output_file = "ES_1m_continuous.csv"
    
    print(f"Processing data from: {downloads_dir}")
    
    # 1. Load all CSV files
    # Only pick up ES1 files (renamed or original)
    files = glob.glob(os.path.join(downloads_dir, "*ES1*.csv"))
    if not files:
        print("No ES1 CSV files found.")
        return

    print(f"Found {len(files)} files.")
    
    dfs = []
    for f in files:
        try:
            # Read CSV
            df = pd.read_csv(f)
            
            # Normalize columns
            df.columns = [c.lower().strip() for c in df.columns]
            
            # Identify time column
            time_col = df.columns[0] # Assumption: first column is time
            
            # Parse datetime
            if pd.api.types.is_numeric_dtype(df[time_col]):
                df['datetime'] = pd.to_datetime(df[time_col], unit='s')
            else:
                df['datetime'] = pd.to_datetime(df[time_col])
                
            # Set index
            df.set_index('datetime', inplace=True)
            
            # Keep only OHLCV columns (optional, but good for cleaning)
            # For now, keep all
            
            dfs.append(df)
            # print(f"Loaded {os.path.basename(f)}: {len(df)} rows, {df.index.min()} to {df.index.max()}")
            
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not dfs:
        print("No valid data loaded.")
        return

    # 2. Stitch and Sort
    full_df = pd.concat(dfs)
    full_df.sort_index(inplace=True)
    
    total_raw_rows = len(full_df)
    print(f"\nTotal raw rows: {total_raw_rows}")

    # 3. Deduplicate
    # Remove rows with exact same index (keep first or last? usually they are identical)
    full_df = full_df[~full_df.index.duplicated(keep='first')]
    
    unique_rows = len(full_df)
    duplicates_removed = total_raw_rows - unique_rows
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Final unique rows: {unique_rows}")
    
    if unique_rows == 0:
        return

    # 4. Gap Analysis
    print("\n--- Gap Analysis ---")
    start_date = full_df.index.min()
    end_date = full_df.index.max()
    print(f"Range: {start_date} to {end_date}")
    
    # Calculate time differences between consecutive rows
    full_df['time_diff'] = full_df.index.to_series().diff()
    
    # Define a "gap" as missing more than 1 minute (e.g., > 2 minutes diff)
    # Note: This will flag weekends and market closes.
    gaps = full_df[full_df['time_diff'] > pd.Timedelta(minutes=1)]
    
    # Filter for "significant" gaps (e.g., > 1 hour) to avoid noise
    significant_gaps = full_df[full_df['time_diff'] > pd.Timedelta(minutes=60)]
    
    print(f"Found {len(gaps)} discontinuities (> 1 min).")
    print(f"Found {len(significant_gaps)} significant gaps (> 60 min).")
    
    if len(significant_gaps) > 0:
        print("\nTop 5 Largest Gaps:")
        print(significant_gaps['time_diff'].sort_values(ascending=False).head(5))
        
    # 5. Save
    # Remove the helper column
    full_df.drop(columns=['time_diff'], inplace=True)
    
    full_df.to_csv(output_file)
    print(f"\nSaved clean data to: {output_file}")
    
    # 6. Basic Stats
    print("\n--- Data Preview ---")
    print(full_df.head(3))
    print("...")
    print(full_df.tail(3))

if __name__ == "__main__":
    process_market_data()
