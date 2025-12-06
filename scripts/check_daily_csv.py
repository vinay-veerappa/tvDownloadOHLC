"""Check latest dates in daily CSV files"""
import pandas as pd
from pathlib import Path

tv_dir = Path("data/TV_OHLC")

# Find all daily CSV files
daily_files = list(tv_dir.glob("*1D*.csv"))

print("Daily CSV files - Latest dates:")
print()

for f in sorted(daily_files):
    try:
        df = pd.read_csv(f)
        latest_time = df["time"].max()
        latest_date = pd.to_datetime(latest_time, unit="s")
        print(f"  {f.name}: {latest_date}")
    except Exception as e:
        print(f"  {f.name}: ERROR - {e}")
