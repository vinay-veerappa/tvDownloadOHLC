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

def debug_day(d_str):
    d = pd.to_datetime(d_str).date()
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    m = df_1m[df_1m['date'] == d]
    h = df_1h[df_1h['date'] == d]
    
    or_candle = m[m['time_only'] == time(9, 30)]
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    print(f"DEBUG {d_str}: OR={or_l}-{or_h}")
    
    rth_h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(15, 0))]
    tolerance = 2.0 * 0.25
    
    for i, (t, row) in enumerate(rth_h.iterrows()):
        hh, hl = row['high'], row['low']
        overlap = hh >= (or_l - tolerance) and hl <= (or_h + tolerance)
        broke = hl > (or_h + tolerance) or hh < (or_l - tolerance)
        print(f"Hour {t.time()}: H={hh}, L={hl} | Overlap={overlap}, Broke={broke}")

if __name__ == "__main__":
    debug_day("2026-01-05")
    print("-" * 20)
    debug_day("2025-12-29")
