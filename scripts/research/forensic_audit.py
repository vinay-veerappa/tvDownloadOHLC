import pandas as pd
import numpy as np
import pytz
from datetime import time
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data_1m(ticker: str):
    path = DATA_DIR / f"{ticker}_1m.parquet"
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def dump_minutes(d_str, start_time, end_time):
    d = pd.to_datetime(d_str).date()
    df_1m = load_data_1m("NQ1")
    m = df_1m[df_1m['date'] == d]
    
    window = m.between_time(start_time, end_time)
    print(f"\n--- DUMP {d_str} {start_time} to {end_time} ---")
    print(window[['high', 'low', 'volume']])
    print(f"Max High: {window['high'].max()}, Min Low: {window['low'].min()}")

if __name__ == "__main__":
    # Audit Jan 05 10:00 hour
    dump_minutes("2026-01-05", "10:00", "10:05")
    dump_minutes("2026-01-05", "10:55", "11:00")
    
    # Audit Jan 14 (Short day)
    dump_minutes("2026-01-14", "09:30", "09:35")
