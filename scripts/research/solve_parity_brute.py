import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta
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

def get_or(m, start_time_str, duration_mins):
    start = pd.to_datetime(start_time_str).time()
    # Find the candle at exactly start_time
    candle = m[m['time_only'] == start]
    if candle.empty: return None, None
    
    # Simple case: 1m candle
    if duration_mins == 1:
        return candle.iloc[0]['high'], candle.iloc[0]['low']
    
    # Range over X minutes
    end_dt = pd.to_datetime(f"2026-01-01 {start_time_str}") + timedelta(minutes=duration_mins-1)
    end_time = end_dt.time()
    window = m[(m['time_only'] >= start) & (m['time_only'] <= end_time)]
    if window.empty: return None, None
    return window['high'].max(), window['low'].min()

def classify(d, df_1m, df_1h, or_h, or_l, tol=0.5):
    h = df_1h[df_1h['date'] == d]
    # PineScript hourly array starts at 10:00 (ignoring 9:30-10:00)
    # BUT wait! What if it starts at 9:30? The chart shows a 9:30 box!
    # Let's try both.
    
    # Try 10:00 start (per Pine code)
    rth_h = h[(h['time_only'] >= time(10, 0)) & (h['time_only'] <= time(15, 0))]
    highs = rth_h['high'].tolist()
    lows = rth_h['low'].tolist()
    size = len(highs)
    
    def touches(hh, hl): return hh >= (or_l - tol) and hl <= (or_h + tol)
    def broke(hh, hl): return hl > (or_h + tol) or hh < (or_l - tol)

    broke_idx = -1
    ret_idx = -1
    touch_count = 0
    
    for i in range(size):
        hh, hl = highs[i], lows[i]
        if broke(hh, hl):
            if broke_idx == -1: broke_idx = i
        elif touches(hh, hl):
            touch_count += 1
            if broke_idx != -1 and ret_idx == -1: ret_idx = i
            
    is_r2 = broke_idx != -1 and ret_idx != -1 and ret_idx >= 2 and (ret_idx - broke_idx) >= 1
    is_r1 = touch_count >= 4
    
    # Pullbacks
    has_pb = False
    if broke_idx != -1 and not is_r2 and not is_r1:
        # Simplified PB Check
        if lows[broke_idx] > or_h: # Up
            hl = lows[broke_idx]
            for i in range(broke_idx+1, size-1):
                if lows[i] < hl: has_pb = True; break
                hl = max(hl, lows[i])
        else:
            lh = highs[broke_idx]
            for i in range(broke_idx+1, size-1):
                if highs[i] > lh: has_pb = True; break
                lh = min(lh, highs[i])

    if is_r2: return "R2"
    if is_r1: return "R1"
    if broke_idx != -1: return "DWP" if has_pb else "DNP"
    return "R1"

def solve_parity():
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    ref = {
        "2025-10-06": "R2", "2025-12-26": "R2", "2026-01-05": "R2", 
        "2026-01-07": "R2", "2026-01-08": "R2", "2026-01-14": "DWP"
    }

    configs = [
        ("09:30", 1), ("09:30", 5), ("09:30", 30), 
        ("09:29", 1), ("09:31", 1), ("09:35", 1)
    ]
    
    for start, dur in configs:
        print(f"\n--- TRYING OR: {start} ({dur}m) ---")
        correct = 0
        for d_str, r in ref.items():
            d = pd.to_datetime(d_str).date()
            m = df_1m[df_1m['date'] == d]
            oh, ol = get_or(m, start, dur)
            if oh is None: continue
            out = classify(d, df_1m, df_1h, oh, ol)
            print(f"  {d_str}: {out} (Expected {r}) {'OK' if out == r else ''}")
            if out == r: correct += 1
        print(f"  Accuracy: {correct}/{len(ref)}")

if __name__ == "__main__":
    solve_parity()
