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

def analyze_parity_fixed(d, df_1m, tol_ticks=2.0, min_touches_r1=4, min_sep_r2=1, r2_win_start_idx=2):
    m = df_1m[df_1m['date'] == d]
    if m.empty: return None
    
    # OR: 9:30 1m candle
    or_candle = m[m['time_only'] == time(9, 30)]
    if or_candle.empty: return None
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    
    # Parity Boxes: 10:00, 11:00, 12:00, 13:00, 14:00, 15:00
    # PineScript array starts at 10:00 because ta.change(hour) happens then.
    boxes = []
    for h in range(10, 16):
        bh = m.between_time(f"{h:02d}:00", f"{h:02d}:59")
        if not bh.empty:
            boxes.append({'h': bh['high'].max(), 'l': bh['low'].min()})
    
    if not boxes: return None
    
    tol = tol_ticks * 0.25
    def touches(bh, bl): return bh >= (or_l - tol) and bl <= (or_h + tol)
    def broke(bh, bl): return bl > (or_h + tol) or bh < (or_l - tol)
    
    highs = [b['h'] for b in boxes]
    lows = [b['l'] for b in boxes]
    size = len(boxes)
    
    broke_or = False
    broke_or_idx = -1
    touch_count = 0
    returned = False
    ret_idx = -1
    
    # Mirror Pine logic exactly
    for i in range(size):
        if broke(highs[i], lows[i]):
            if not broke_or:
                broke_or = True
                broke_or_idx = i
                broke_up = lows[i] > (or_h + tol)
        else:
            if touches(highs[i], lows[i]):
                touch_count += 1
                
    if broke_or and broke_or_idx < size - 1:
        for i in range(broke_or_idx + 1, size):
            if touches(highs[i], lows[i]):
                returned = True
                ret_idx = i
                touch_count += 1
                break
                
    has_pb = False
    if broke_or and not returned:
        pb_end = size - 2
        if pb_end > broke_or_idx:
            if lows[broke_or_idx] > (or_h + tol): # UP
                hl = lows[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if lows[i] < hl: has_pb = True; break
                    hl = max(hl, lows[i])
            else: # DOWN
                lh = highs[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if highs[i] > lh: has_pb = True; break
                    lh = min(lh, highs[i])

    # Precedence R2 > R1 per table matches
    is_r2 = broke_or and returned and ret_idx >= r2_win_start_idx and (ret_idx - broke_or_idx) >= min_sep_r2
    is_r1 = touch_count >= min_touches_r1
    
    if is_r2: return "R2"
    if is_r1: return "R1"
    if not broke_or: return "R1"
    return "DWP" if has_pb else "DNP"

def run():
    df_1m = load_data_1m("NQ1")
    ref = {
        "2025-10-06": "R2", "2025-10-15": "R2", "2025-12-26": "R2", 
        "2026-01-05": "R2", "2026-01-07": "R2", "2026-01-08": "R2",
        "2026-01-14": "DWP", "2026-01-13": "R1"
    }
    print(f"{'Date':<12} | {'Out':<4} | {'Ref':<4}")
    for d_str, r in ref.items():
        out = analyze_parity_fixed(pd.to_datetime(d_str).date(), df_1m)
        print(f"{d_str:<12} | {out:<4} | {r:<4} | {'OK' if out == r else ''}")

if __name__ == "__main__":
    run()
