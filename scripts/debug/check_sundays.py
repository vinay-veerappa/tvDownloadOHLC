
import pandas as pd
from pathlib import Path

path = Path("data/NQ1_1m.parquet")
if path.exists():
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('America/New_York')
    
    df['dow'] = df.index.day_name()
    counts = df['dow'].value_counts()
    print("Day counts in America/New_York:")
    print(counts)
    
    # Check 18:00-23:59 on Sundays
    sun_night = df[(df.index.dayofweek == 6) & (df.index.hour >= 18)]
    print(f"Sunday Night Rows (18:00+): {len(sun_night)}")
else:
    print("File not found")
