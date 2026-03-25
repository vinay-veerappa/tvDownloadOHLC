import pandas as pd
import os

data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
if not os.path.exists(data_path):
    print("Data file not found.")
else:
    df = pd.read_csv(data_path, nrows=0) # Only read header
    cols = sorted(list(df.columns))
    print(f"Total Columns: {len(cols)}")
    
    # Check for profiler-like terms
    profiler_cols = [c for c in cols if 'status' in c.lower() or 'profiler' in c.lower() or 'box' in c.lower()]
    print(f"\nProfiler Columns ({len(profiler_cols)}):")
    for c in profiler_cols:
        print(f"  - {c}")
        
    # Check for session specific outcome columns
    asia_cols = [c for c in cols if 'asia' in c.lower()]
    print(f"\nAsia Columns ({len(asia_cols)}):")
    # print first 10
    for c in asia_cols[:10]:
        print(f"  - {c}")
