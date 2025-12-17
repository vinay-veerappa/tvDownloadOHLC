"""Verify OHLC matching across 10 contiguous rows"""
import pandas as pd
from pathlib import Path

# Load both files
csv_chicago = Path("data/TV_OHLC/nq-1m_bk.csv")
df_chicago = pd.read_csv(csv_chicago, sep=";", header=None,
                         names=["date", "time", "open", "high", "low", "close", "volume"])

csv_unix = Path("data/TV_OHLC/CME_MINI_NQ1!, 1_e0c08.csv")
df_unix = pd.read_csv(csv_unix)
df_unix.columns = [c.lower() for c in df_unix.columns]
df_unix["datetime"] = pd.to_datetime(df_unix["time"], unit="s")

# Take 10 contiguous rows from Unix file
sample_start = 100
sample_end = 110
sample = df_unix.iloc[sample_start:sample_end]

print("=== Matching 10 contiguous rows ===")
print()

for i, (idx, row) in enumerate(sample.iterrows()):
    utc_dt = row["datetime"]
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    
    # Find match in Chicago file
    matches = df_chicago[
        (abs(df_chicago["open"] - o) < 0.01) &
        (abs(df_chicago["high"] - h) < 0.01) &
        (abs(df_chicago["low"] - l) < 0.01) &
        (abs(df_chicago["close"] - c) < 0.01)
    ]
    
    if len(matches) == 1:
        m = matches.iloc[0]
        chi_dt = f"{m['date']} {m['time']}"
        status = "MATCH"
    elif len(matches) == 0:
        chi_dt = "NOT FOUND"
        status = "MISS"
    else:
        chi_dt = f"{len(matches)} matches"
        status = "MULTI"
    
    print(f"{i+1:2d}. UTC: {utc_dt} | Chicago: {chi_dt} | O={o:.2f} | {status}")
