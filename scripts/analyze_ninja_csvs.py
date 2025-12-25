"""
Analyze the date ranges of the two NinjaTrader ES CSVs and check for overlaps/gaps.
"""
import pandas as pd
from pathlib import Path

CSV_15 = Path("data/NinjaTrader/15Dec2025/ES Monday 1719.csv")
CSV_24 = Path("data/NinjaTrader/24Dec2025/ES Thursday 857.csv")

def analyze_csv(path):
    print(f"\n=== {path.name} ===")
    
    # Read with our robust settings
    col_names = ['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume', 'aux1', 'aux2', 'aux3']
    df = pd.read_csv(path, sep=',', on_bad_lines='skip', names=col_names, skiprows=1, engine='python', index_col=False)
    
    # Parse datetime
    df['datetime'] = pd.to_datetime(df['date_str'].astype(str) + ' ' + df['time_str'].astype(str), format='%m/%d/%Y %H:%M:%S')
    df.sort_values('datetime', inplace=True)
    
    print(f"Rows: {len(df):,}")
    print(f"Start: {df['datetime'].min()}")
    print(f"End:   {df['datetime'].max()}")
    
    # Check for price anomalies
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    diffs = df['close'].diff().abs()
    anomalies = diffs[diffs > 80]
    print(f"Price anomalies (>80pt): {len(anomalies)}")
    
    return df

df1 = analyze_csv(CSV_15)
df2 = analyze_csv(CSV_24)

print("\n=== Date Range Summary ===")
print(f"CSV 15Dec: {df1['datetime'].min()} to {df1['datetime'].max()}")
print(f"CSV 24Dec: {df2['datetime'].min()} to {df2['datetime'].max()}")
