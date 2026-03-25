import pandas as pd
import os

data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
if not os.path.exists(data_path):
    print("Data file not found.")
else:
    df = pd.read_csv(data_path, nrows=0) 
    cols = sorted(list(df.columns))
    
    break_cols = [c for c in cols if 'break' in c.lower()]
    print(f"\n'Break' Columns ({len(break_cols)}):")
    for c in break_cols:
        print(f"  - {c}")

    time_cols = [c for c in cols if 'time' in c.lower() and 'asia' in c.lower()]
    print(f"\nAsia Time Columns ({len(time_cols)}):")
    for c in time_cols:
        print(f"  - {c}")
