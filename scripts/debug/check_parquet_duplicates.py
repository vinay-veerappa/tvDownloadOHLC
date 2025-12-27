
import pandas as pd
import sys

def check_parquet(file_path, target_ts=None):
    print(f"Loading {file_path}...")
    try:
        df = pd.read_parquet(file_path)
        print(f"Loaded {len(df)} rows.")
        
        # Check for duplicates in time column
        if 'time' in df.columns:
            dupes = df[df.duplicated(subset=['time'], keep=False)]
            if len(dupes) > 0:
                print(f"FOUND {len(dupes)} duplicate rows based on 'time'!")
                print(dupes.head(10))
                
                if target_ts:
                    target_dupes = dupes[dupes['time'] == target_ts]
                    if len(target_dupes) > 0:
                        print(f"confirmed specific duplicates for {target_ts}:")
                        print(target_dupes)
                    else:
                        print(f"Target {target_ts} not among duplicates.")
            else:
                print("No duplicates found in 'time' column.")
        else:
            print("Column 'time' not found.")
            print(df.columns)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Check ES1_1m.parquet
    check_parquet("data/ES1_1m.parquet", 1764126000)
