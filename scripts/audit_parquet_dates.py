import os
import glob
import pandas as pd
import json

def get_parquet_date_range(file_path):
    try:
        df = pd.read_parquet(file_path)
        
        dates = None
        # Check standard columns
        if 'time' in df.columns:
            dates = pd.to_datetime(df['time'], unit='s')
        elif 'date' in df.columns:
             dates = pd.to_datetime(df['date'])
        
        # Check if index is datetime
        if dates is None:
            if isinstance(df.index, pd.DatetimeIndex):
                dates = df.index
            # Check if index name implies time but wasn't detected as index type
            elif df.index.name in ['time', 'date', 'datetime']:
                dates = pd.to_datetime(df.index)
        
        if dates is None:
             # Last resort: check if any column looks like a date
             for col in df.columns:
                 if 'date' in col.lower() or 'time' in col.lower():
                     try:
                         dates = pd.to_datetime(df[col])
                         break
                     except:
                         pass

        if dates is None:
            return f"No time col/index. Cols: {list(df.columns)}"

        return {
            "min": dates.min().isoformat(),
            "max": dates.max().isoformat(),
            "count": len(df)
        }
    except Exception as e:
        return f"Error: {str(e)}"

def audit_data_dir(data_dir):
    files = glob.glob(os.path.join(data_dir, "*.parquet"))
    results = {}
    
    print(f"{'File':<25} | {'Max Date':<25} | {'Count':<10}")
    print("-" * 65)
    
    for f in sorted(files):
        basename = os.path.basename(f)
        # Skip hidden files or temp files if any
        if basename.startswith("."): continue
        
        info = get_parquet_date_range(f)
        if isinstance(info, dict):
            print(f"{basename:<25} | {info['max']:<25} | {info['count']:<10}")
            results[basename] = info
        else:
            print(f"{basename:<25} | {str(info):<25} | -")

if __name__ == "__main__":
    audit_data_dir("data")
