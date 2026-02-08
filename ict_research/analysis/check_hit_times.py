import pandas as pd
import os

data_path = "c:\\Users\\vinay\\tvDownloadOHLC\\ict_research\\data\\trading_days_enhanced_NQ.csv"
if not os.path.exists(data_path):
    print("Data file not found.")
else:
    df = pd.read_csv(data_path, nrows=0) 
    cols = sorted(list(df.columns))
    
    london_time_cols = [c for c in cols if 'london' in c.lower() and 'time' in c.lower()]
    print(f"\nLondon Time Columns ({len(london_time_cols)}):")
    for c in london_time_cols:
        print(f"  - {c}")
        
    hit_cols = [c for c in cols if 'hit' in c.lower() and 'time' in c.lower()]
    print(f"\nHit Time Columns ({len(hit_cols)}):")
    for c in hit_cols:
        print(f"  - {c}")
