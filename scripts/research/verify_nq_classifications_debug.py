import pandas as pd
import numpy as np
import pytz
import json
from datetime import time, timedelta
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker: str, tf: str):
    path = DATA_DIR / f"{ticker}_{tf}.parquet"
    if not path.exists():
        print(f"Error: {path} not found.")
        return pd.DataFrame()
    
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df.index = pd.to_datetime(df['time'], unit='s', utc=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
    df = df.tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def debug_day(d_str, ticker="NQ1"):
    df_1m = load_data(ticker, "1m")
    df_15m = load_data(ticker, "15m")
    d = pd.to_datetime(d_str).date()
    m = df_1m[df_1m['date'] == d]
    h15 = df_15m[df_15m['date'] == d]
    
    or_bar = m[m['time_only'] == time(9, 30)].iloc[0]
    or_h, or_l = or_bar['high'], or_bar['low']
    print(f"\n--- DEBUG {d_str} ---")
    print(f"09:30 Range: {or_l} - {or_h}")
    
    # Check 15m overlaps
    rth_15m = h15[(h15['time_only'] >= time(9, 30)) & (h15['time_only'] <= time(15, 0))]
    hours_touched = set()
    for t, row in rth_15m.iterrows():
        touched = row['low'] <= or_h and row['high'] >= or_l
        if touched:
            hours_touched.add(t.hour)
    print(f"Hours Touched: {sorted(list(hours_touched))}")
    
    # Check 1m returns after 11:00
    r_late = m[(m['time_only'] >= time(11, 0)) & (m['time_only'] <= time(15, 0))]
    touched_1m = r_late[(r_late['low'] <= or_h) & (r_late['high'] >= or_l)]
    print(f"1m Returns after 11:00: {len(touched_1m)} bars")
    
    # Check if price "moved away" significantly before returning
    early = m[(m['time_only'] > time(9, 31)) & (m['time_only'] < time(11, 0))]
    outside = early[(early['low'] > or_h + 5) | (early['high'] < or_l - 5)]
    print(f"1m bars 'Away' (>5pts) before 11:00: {len(outside)}")

if __name__ == "__main__":
    for d in ["2026-01-05", "2026-01-08", "2026-01-13"]:
        debug_day(d)
