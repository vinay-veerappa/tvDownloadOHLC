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

def debug_day_full(d_str):
    d = pd.to_datetime(d_str).date()
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    m = df_1m[df_1m['date'] == d]
    h = df_1h[df_1h['date'] == d]
    
    or_candle = m[m['time_only'] == time(9, 30)]
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    print(f"\n--- DEBUG {d_str} ---")
    print(f"OR: {or_l} - {or_h}")
    
    # Hourly boxes starting 09:00 (covers 09:30-10:00)
    rth_h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(15, 0))]
    tolerance = 2.0 * 0.25 # 0.5
    
    hourly_highs = rth_h['high'].tolist()
    hourly_lows = rth_h['low'].tolist()
    
    broke_idx = -1
    touches = 0
    cont = 0
    max_cont = 0
    ret_idx = -1
    
    print("Hourly Bars:")
    for i, (t, row) in enumerate(rth_h.iterrows()):
        hh, hl = row['high'], row['low']
        overlap = hh >= (or_l - tolerance) and hl <= (or_h + tolerance)
        broke = hl > (or_h + tolerance) or hh < (or_l - tolerance)
        
        status = "OVERLAP" if overlap else "BROKE"
        print(f"[{i}] {t.time()}: H={hh}, L={hl} | {status}")
        
        if overlap:
            touches += 1
            cont += 1
            max_cont = max(max_cont, cont)
            if broke_idx != -1 and ret_idx == -1:
                ret_idx = i
        else:
            cont = 0
            if broke_idx == -1:
                broke_idx = i
                
    print(f"Total Touches: {touches}, Max Cont: {max_cont}")
    print(f"Broke Idx: {broke_idx}, Ret Idx: {ret_idx}")
    
    # Check for Pullbacks
    if broke_idx != -1:
        dir_up = hourly_lows[broke_idx] > or_h
        print(f"Direction: {'UP' if dir_up else 'DOWN'}")
        has_pb = False
        if dir_up:
            highest_low = hourly_lows[broke_idx]
            for i in range(broke_idx + 1, len(hourly_lows) - 1): # Exclude final hourly bar per pine rule
                if hourly_lows[i] < highest_low:
                    print(f"PULLBACK at Idx {i}: Low {hourly_lows[i]} < Highest Low {highest_low}")
                    has_pb = True
                    break
                highest_low = max(highest_low, hourly_lows[i])
        else:
            lowest_high = hourly_highs[broke_idx]
            for i in range(broke_idx + 1, len(hourly_highs) - 1):
                if hourly_highs[i] > lowest_high:
                    print(f"PULLBACK at Idx {i}: High {hourly_highs[i]} > Lowest High {lowest_high}")
                    has_pb = True
                    break
                lowest_high = min(lowest_high, hourly_highs[i])
        if not has_pb: print("No Hourly Pullbacks found")

if __name__ == "__main__":
    for d in ["2025-12-26", "2026-01-07", "2026-01-08", "2026-01-14", "2026-01-05"]:
        debug_day_full(d)
