import pandas as pd
import glob
import os
import time

def stitch_and_validate():
    # Path to downloads
    downloads_path = os.path.join(os.getcwd(), "data", "downloads_es_futures")
    pattern = os.path.join(downloads_path, "*.csv")
    
    files = glob.glob(pattern)
    
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
    print(f"Date Range: {full_df.index.min()} to {full_df.index.max()}")
    
    # Check for gaps (assuming 1 min data)
    # This is rough because of weekends/holidays
    expected_rows = (full_df.index.max() - full_df.index.min()).total_seconds() / 60
    print(f"Expected rows (approx): {int(expected_rows)}")
    print(f"Actual rows: {len(full_df)}")
    
    # Save stitched
    # Save stitched
    output_file = os.path.join("data", "ES_1m_continuous.csv")
    full_df.to_csv(output_file)
    print(f"Saved stitched data to {output_file}")
    print(full_df.head())
    print(full_df.tail())

if __name__ == "__main__":
    stitch_and_validate()
