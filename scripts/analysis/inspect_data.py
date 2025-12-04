import pandas as pd
from pathlib import Path

data_dir = Path("data")
ticker = "ES1"
tf = "1h" # Check 1h as it's a common viewing timeframe

file_path = data_dir / f"{ticker}_{tf}.parquet"
df = pd.read_parquet(file_path)

start_date = "2024-12-01"
end_date = "2024-12-05" # Look at the start of the problem

mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
subset = df[mask]

print(f"Data for {ticker} {tf} from {start_date} to {end_date}:")
print(subset.head(20))

print("\nChecking time differences:")
subset['diff'] = subset.index.to_series().diff()
print(subset['diff'].value_counts().head())

print("\nChecking for very small diffs:")
small_diffs = subset[subset['diff'] < pd.Timedelta(minutes=59)] # For 1h, diff should be >= 1h usually
if not small_diffs.empty:
    print(small_diffs.head())
else:
    print("No small time gaps found.")
