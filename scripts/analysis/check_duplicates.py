import pandas as pd
from pathlib import Path

data_dir = Path("data")
tickers = ["ES1", "NQ1"]
timeframes = ["1m", "5m", "15m", "1h", "4h", "1D"]

start_date = "2024-12-02"
end_date = "2025-06-06"

print(f"Checking for duplicates between {start_date} and {end_date}...\n")

for ticker in tickers:
    for tf in timeframes:
        file_path = data_dir / f"{ticker}_{tf}.parquet"
        if not file_path.exists():
            continue
            
        try:
            df = pd.read_parquet(file_path)
            
            # Check for duplicate indices
            duplicates = df.index.duplicated()
            num_duplicates = duplicates.sum()
            
            if num_duplicates > 0:
                print(f"FAIL: {file_path} has {num_duplicates} duplicate timestamps!")
                # Show some examples
                dup_indices = df.index[duplicates]
                print(f"  Examples: {dup_indices[:5]}")
                
                # Check if they are in the specified range
                mask_range = (dup_indices >= pd.to_datetime(start_date)) & (dup_indices <= pd.to_datetime(end_date))
                dups_in_range = mask_range.sum()
                print(f"  Duplicates in target range ({start_date} to {end_date}): {dups_in_range}")
                
            else:
                print(f"OK: {file_path} has no duplicate timestamps.")
                
            # Also check if there are just weirdly close timestamps or data density issues?
            # For now, strict duplicates are the main suspect for "double rendering" (if the chart lib gets two points for same time).
            
        except Exception as e:
            print(f"ERROR reading {file_path}: {e}")
