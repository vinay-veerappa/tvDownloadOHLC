"""Check latest dates in ALL CSV files in TV_OHLC folder"""
import pandas as pd
from pathlib import Path

tv_dir = Path("data/TV_OHLC")

# Find all CSV files
csv_files = list(tv_dir.glob("*.csv"))

results = []
for f in sorted(csv_files):
    try:
        df = pd.read_csv(f)
        latest_time = df["time"].max()
        latest_date = pd.to_datetime(latest_time, unit="s")
        results.append((f.name, str(latest_date)))
    except Exception as e:
        results.append((f.name, f"ERROR: {e}"))

# Write to file
with open("csv_dates.txt", "w") as out:
    out.write("All CSV files - Latest dates:\n")
    out.write("=" * 70 + "\n")
    for name, date in results:
        out.write(f"{name:50s} -> {date}\n")

print(f"Results written to csv_dates.txt ({len(results)} files)")
