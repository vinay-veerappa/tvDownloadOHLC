import pandas as pd
import glob
import os
from datetime import datetime

def generate_inventory():
    data_dir = "data"
    output_file = "DATA_INVENTORY.md"
    
    files = glob.glob(f"{data_dir}/*.parquet")
    inventory = []
    
    print(f"Scanning {len(files)} parquet files...")
    
    for f in files:
        try:
            # Optimize: Try reading only metadata if possible, but reading whole file is safer for dates
            # For 1m data this might be slow, let's try reading head/tail if index is sorted
            # But parquet doesn't guarantee sorted order unless written that way.
            # We'll read the whole file for now but keep it simple.
            # To speed up, we can read just 'date' or index columns.
            
            df = pd.read_parquet(f, columns=[]) # Just read metadata/index first?
            # Actually read_parquet with specific columns is faster.
            # We need index (if datetime) or 'date'/'time' columns.
            
            # Let's inspect columns first
            df_cols = pd.read_parquet(f).columns
            cols_to_read = []
            if 'date' in df_cols: cols_to_read.append('date')
            if 'time' in df_cols: cols_to_read.append('time')
            
            df = pd.read_parquet(f, columns=cols_to_read)
            
            # Count
            count = len(df)
            
            # Dates
            start_date = "N/A"
            end_date = "N/A"
            
            if isinstance(df.index, pd.DatetimeIndex):
                start_date = df.index.min().strftime('%Y-%m-%d')
                end_date = df.index.max().strftime('%Y-%m-%d')
            elif 'date' in df.columns:
                # Convert to datetime if string
                dates = pd.to_datetime(df['date'])
                start_date = dates.min().strftime('%Y-%m-%d')
                end_date = dates.max().strftime('%Y-%m-%d')
            
            # Parse filename for Ticker/Timeframe
            # Format: Ticker_Timeframe.parquet (e.g. NQ1_1m.parquet)
            basename = os.path.basename(f).replace('.parquet', '')
            parts = basename.split('_')
            ticker = parts[0]
            tf = parts[1] if len(parts) > 1 else "Unknown"
            
            inventory.append({
                'Ticker': ticker,
                'Timeframe': tf,
                'Start Date': start_date,
                'End Date': end_date,
                'Bars': count,
                'Filename': os.path.basename(f)
            })
            print(f"Processed {os.path.basename(f)}")
            
        except Exception as e:
            print(f"Error processing {f}: {e}")

    # Sort
    df_inv = pd.DataFrame(inventory)
    if not df_inv.empty:
        df_inv = df_inv.sort_values(['Ticker', 'Timeframe'])
    
    # Generate Markdown
    with open(output_file, 'w') as f:
        f.write("# Data Inventory\n")
        f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Ticker | Timeframe | Start Date | End Date | Bars | Parquet File |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        for _, row in df_inv.iterrows():
            f.write(f"| {row['Ticker']} | {row['Timeframe']} | {row['Start Date']} | {row['End Date']} | {row['Bars']} | `{row['Filename']}` |\n")
            
    print(f"Inventory saved to {output_file}")

if __name__ == "__main__":
    generate_inventory()
