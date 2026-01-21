import pandas as pd
import numpy as np
import pytz
from datetime import time
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker: str, tf: str):
    path = DATA_DIR / f"{ticker}_{tf}.parquet"
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def debug_late_price(d_str):
    d = pd.to_datetime(d_str).date()
    df_1m = load_data("NQ1", "1m")
    m = df_1m[df_1m['date'] == d]
    
    or_candle = m[m['time_only'] == time(9, 30)]
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    print(f"DEBUG {d_str}: OR={or_l}-{or_h}")
    
    late = m.between_time('15:00', '16:15')
    print(f"Late Price (15:00-16:15):")
    touched = False
    for t, row in late.iterrows():
        if row['high'] >= or_l and row['low'] <= or_h:
            print(f"TOUCH at {t.time()} | H={row['high']}, L={row['low']}")
            touched = True
            break
    if not touched:
        print("No touch 15:00-16:15")

if __name__ == "__main__":
    debug_late_price("2026-01-05")
    debug_late_price("2025-12-26")
    debug_late_price("2025-10-06")
