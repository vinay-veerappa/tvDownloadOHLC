"""
Analyze BacktestMarket NQ data to verify anomalies from NinjaTrader import.
BacktestMarket format: semicolon-delimited, DD/MM/YYYY, America/Chicago timezone.
"""
import pandas as pd
from pathlib import Path

BM_PATH = Path("data/TV_OHLC/NQ Full_backtestmarket/nq-1m_bk.csv")

# Anomaly dates from NinjaTrader import (>200pt moves)
ANOMALY_DATES = [
    "2025-01-26 23:00",
    "2025-02-02 23:00",
    "2025-04-06 22:00",
    "2025-04-07 14:10",
]

print(f"=== Analyzing BacktestMarket NQ Data ===")
print(f"Source: {BM_PATH}")

# Read BacktestMarket format (semicolon, no header, DD/MM/YYYY)
# Columns: Date;Time;Open;High;Low;Close;Volume
df = pd.read_csv(BM_PATH, sep=';', header=None, 
                 names=['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume'],
                 dtype={'date_str': str, 'time_str': str})

print(f"Raw rows: {len(df):,}")

# Parse datetime (DD/MM/YYYY format)
df['datetime'] = pd.to_datetime(df['date_str'] + ' ' + df['time_str'], dayfirst=True)

# Convert Chicago -> UTC -> strip TZ
df['datetime'] = df['datetime'].dt.tz_localize('America/Chicago').dt.tz_convert('UTC').dt.tz_localize(None)

df.set_index('datetime', inplace=True)
df.sort_index(inplace=True)

print(f"Date range: {df.index.min()} to {df.index.max()}")

# Check each anomaly date
print(f"\n=== Checking Anomaly Dates ===")
for date_str in ANOMALY_DATES:
    try:
        ts = pd.Timestamp(date_str)
        # Get 5 minutes around the timestamp
        start = ts - pd.Timedelta(minutes=2)
        end = ts + pd.Timedelta(minutes=2)
        subset = df.loc[start:end]
        
        if subset.empty:
            print(f"\n{date_str}: NO DATA in BacktestMarket")
        else:
            print(f"\n{date_str}:")
            print(subset[['open', 'high', 'low', 'close']].to_string())
    except Exception as e:
        print(f"\n{date_str}: Error - {e}")
