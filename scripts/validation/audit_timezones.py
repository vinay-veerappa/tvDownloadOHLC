
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
BACKUP_DIR = Path("data/backup")
results = []

print(f"{'File':<30} | {'Timezone':<20} | {'Start':<25} | {'End':<25}")
print("-" * 105)

for p_file in sorted(BACKUP_DIR.glob("*.parquet*")): # Scan backups
    if "pre_merge" not in p_file.name and ".bak" not in p_file.name: continue # optimize for relevant backups
    try:
        # Read only index/metadata to be fast if possible, but pandas reads all usually.
        # fastparquet or pyarrow could be faster but let's use pandas for simplicity/consistency
        df = pd.read_parquet(p_file, columns=[]) 
        # Re-read index if reading empty cols doesn't give index. 
        # Actually read_parquet([]) might return empty df with index.
        # Let's just read index.
        # Accessing metadata directly is better but pandas is robust.
        
        # Optimization: try reading just first/last row?
        # df = pd.read_parquet(p_file) # might be slow for big files
        
        # Using pyarrow for speed if available? 
        # Environment is user's. stick to pandas.
        try:
            df = pd.read_parquet(p_file)
            tz = str(df.index.tz) if df.index.tz else "None (Naive)"
            start = str(df.index[0])
            end = str(df.index[-1])
            results.append((p_file.name, tz, start, end))
            print(f"{p_file.name:<30} | {tz:<20} | {start:<25} | {end:<25}")
        except Exception as e:
             print(f"{p_file.name:<30} | Error: {str(e)}")

    except Exception as e:
        print(f"Skipping {p_file.name}: {e}")

print("-" * 105)
