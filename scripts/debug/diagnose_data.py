import pandas as pd
import os
from datetime import datetime

file_path = "data/RTY1_1m.parquet"
if os.path.exists(file_path):
    print(f"Reading {file_path}...")
    df = pd.read_parquet(file_path)
    print(f"Total Rows: {len(df)}")
    print(f"Start Date: {df.index.min()}")
    print(f"End Date: {df.index.max()}")
    
    unique_dates = df.index.date
    n_unique = len(set(unique_dates))
    print(f"Unique Dates: {n_unique}")
    
    # Check first 5 and last 5 dates
    print("First 5 dates:", sorted(list(set(unique_dates)))[:5])
    print("Last 5 dates:", sorted(list(set(unique_dates)))[-5:])
    
else:
    print("File not found.")
