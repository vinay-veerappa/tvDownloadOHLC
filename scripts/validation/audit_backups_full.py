
import pandas as pd
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path("data/backup")
results = []

print(f"{'File':<55} | {'ModTime':<20} | {'Timezone':<20}")
print("-" * 100)

# Get all parquet/bak files
files = sorted(BACKUP_DIR.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True)

for p_file in files:
    if "parquet" not in p_file.name: continue
    
    try:
        # Optimization: Read only metadata/index
        try:
             # Fast read if possible
             # df = pd.read_parquet(p_file, columns=[]) 
             # actually full read is safer for tz info if index isn't loaded by checks
             df = pd.read_parquet(p_file)
             tz = str(df.index.tz) if getattr(df.index, 'tz', None) else "None (Naive)"
        except:
             tz = "Error"

        mtime = datetime.fromtimestamp(p_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f"{p_file.name:<55} | {mtime:<20} | {tz:<20}")
        
    except Exception as e:
        pass
        # print(f"{p_file.name}: {e}")

print("-" * 100)
