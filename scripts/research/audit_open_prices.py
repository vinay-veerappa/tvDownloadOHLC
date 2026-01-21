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

def audit_or_prices():
    df_1m = load_data("NQ1", "1m")
    dates = ["2025-10-06", "2025-11-17", "2025-12-22", "2025-12-26", "2026-01-05"]
    
    for d_str in dates:
        d = pd.to_datetime(d_str).date()
        m = df_1m[df_1m['date'] == d]
        
        # Check first few minutes of RTH
        rth_open = m.between_time('09:30', '09:35')
        print(f"\nAUDIT {d_str} Open:")
        print(rth_open[['high', 'low', 'volume']])

if __name__ == "__main__":
    audit_or_prices()
