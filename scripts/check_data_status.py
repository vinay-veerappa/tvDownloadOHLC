import os
import sys
import glob
import json
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def get_file_info(filepath):
    try:
        stats = os.stat(filepath)
        size_mb = stats.st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(stats.st_mtime)
        
        info = {
            "name": os.path.basename(filepath),
            "size": f"{size_mb:.1f} MB",
            "updated": mtime.strftime("%Y-%m-%d %H:%M"),
            "rows": "Unknown",
            "status": "OK" if size_mb > 0 else "Empty"
        }

        # Try to read parquet metadata for row count (fast)
        try:
            if filepath.endswith('.parquet'):
                # PyArrow can read metadata without full file
                import pyarrow.parquet as pq
                meta = pq.read_metadata(filepath)
                info["rows"] = f"{meta.num_rows:,}"
        except Exception as e:
            info["rows"] = "Error reading"

        return info
    except Exception as e:
        return {"name": os.path.basename(filepath), "status": "Error", "error": str(e)}

def main():
    files = []
    # Scan for common parquet files and derived JSONs
    patterns = [
        "*_1m.parquet", "*_5m.parquet", "*_1h.parquet", "*_1D.parquet",
        "*_profiler.json", "*_level_stats.json", "*_hod_lod.json", "*_range_dist.json"
    ]
    
    for pattern in patterns:
        for filepath in glob.glob(os.path.join(DATA_DIR, pattern)):
            files.append(get_file_info(filepath))
            
    # Sort by name
    files.sort(key=lambda x: x["name"])
    
    print(json.dumps(files))

if __name__ == "__main__":
    main()
