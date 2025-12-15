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
        
        # Helper to convert to EST string
        def to_est(dt):
            # Assume naive dt is local (which on this machine might be PST based on user metadata, but let's be safe)
            # Actually, fromtimestamp returns local time. 
            # Let's simple format: if user wants EST, we can just assume the machine might be in different zone, but usually
            # for "Last Updated" file time, local machine time is best. 
            # BUT user specifically asked for "dates look all wrong" for the DATA RANGE.
            # So let's focus on the Parquet Data Range conversion.
            return dt.strftime("%Y-%m-%d %H:%M")

        # Categorize
        if filepath.endswith('.parquet'):
            category = "Market Data"
        elif "profiler" in filepath or "stats" in filepath or "dist" in filepath or "hod_lod" in filepath:
            category = "Derived Assets"
        else:
            category = "Other"

        info = {
            "name": os.path.basename(filepath),
            "size": f"{size_mb:.1f} MB",
            "updated": to_est(mtime),
            "rows": "Unknown",
            "status": "OK" if size_mb > 0 else "Empty",
            "category": category
        }

        # Try to read parquet metadata for row count and range
        try:
            if filepath.endswith('.parquet'):
                import pyarrow.parquet as pq
                meta = pq.read_metadata(filepath)
                info["rows"] = f"{meta.num_rows:,}"
                
                # Try to get range from statistics
                try:
                    pf = pq.ParquetFile(filepath)
                    col_idx = -1
                    
                    # Find the datetime column
                    # It's often named 'datetime', 'time', 'Date', 'Time' or '__index_level_0__'
                    names = pf.schema.names
                    for i, name in enumerate(names):
                        if name.lower() in ['datetime', 'time', 'date', '__index_level_0__']:
                            col_idx = i
                            break
                    
                    if col_idx == -1:
                        # Fallback: Check last column (often index) or first column
                        # If 0 is float (price), likely not it.
                        # Let's try last column if named like a time
                        col_idx = len(names) - 1

                    # Get Min/Max Statistics
                    min_stats = pf.metadata.row_group(0).column(col_idx).statistics
                    max_stats = pf.metadata.row_group(pf.metadata.num_row_groups - 1).column(col_idx).statistics
                    
                    start_val = min_stats.min
                    end_val = max_stats.max

                    def parse_and_format(val):
                        # Handle Integers (Nanoseconds/Microseconds from Epoch)
                        ts = None
                        if isinstance(val, (int, float)):
                            # Guess based on size (ns vs ms vs s)
                            # 10 digits = seconds (1e9)
                            # 13 digits = millis (1e12)
                            # 16 digits = micros (1e15)
                            # 19 digits = nanos (1e18)
                            if val > 1e16: # Nanos
                                ts = pd.to_datetime(val, unit='ns')
                            elif val > 1e13: # Micros
                                ts = pd.to_datetime(val, unit='us')
                            elif val > 1e10: # Millis
                                ts = pd.to_datetime(val, unit='ms')
                            else: # Seconds
                                ts = pd.to_datetime(val, unit='s')
                        else:
                            # String or other
                            ts = pd.to_datetime(val)
                        
                        # Convert to EST (America/New_York)
                        # Assume data is UTC if naive
                        if ts.tz is None:
                            ts = ts.tz_localize('UTC')
                        
                        ts_est = ts.tz_convert('America/New_York')
                        return ts_est.strftime("%Y-%m-%d %H:%M")

                    info["startDate"] = parse_and_format(start_val)
                    info["endDate"] = parse_and_format(end_val)
                    
                except Exception as range_err:
                    # info["startDate"] = f"Err: {str(range_err)}" # Debug
                    info["startDate"] = "-"
                    info["endDate"] = "-"
                    
        except Exception as e:
            info["rows"] = "Error reading"

        return info
    except Exception as e:
        return {"name": os.path.basename(filepath), "status": "Error", "error": str(e)}

def main():
    files = []
    # Scan for common parquet files and derived JSONs
    patterns = [
        "*.parquet", 
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
