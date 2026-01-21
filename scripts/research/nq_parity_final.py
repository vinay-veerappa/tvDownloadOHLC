import pandas as pd
import numpy as np
import pytz
from datetime import time, timedelta
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data_1m(ticker: str):
    path = DATA_DIR / f"{ticker}_1m.parquet"
    df = pd.read_parquet(path)
    # Convert index to UTC then NY
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def get_parity_boxes(df_1m_day):
    """
    Mirror PineScript box construction:
    Index 0: 09:30 - 09:59 (The first hour change happens at 10:00)
    Index 1: 10:00 - 10:59
    Index 2: 11:00 - 11:59
    Index 3: 12:00 - 12:59
    Index 4: 13:00 - 13:59
    Index 5: 14:00 - 14:59
    Index 6: 15:00 (The session end evaluates at 15:00:00, but Pine includes the 15:00 candle?)
    Wait, if i_sessionEndHour is 15, Pine sessionStr is "0930-1600".
    But evaluation happens at endOfSession (first bar after 15:00 session window).
    Let's check the size of the array in Pine.
    """
    boxes = []
    # Index 0: 09:30 to 09:59
    b0 = df_1m_day.between_time('09:30', '09:59')
    if not b0.empty:
        boxes.append({'h': b0['high'].max(), 'l': b0['low'].min()})
    
    # Indices 1 to 5: 10:00 to 14:59
    for h in range(10, 15):
        bh = df_1m_day.between_time(f"{h:02d}:00", f"{h:02d}:59")
        if not bh.empty:
            boxes.append({'h': bh['high'].max(), 'l': bh['low'].min()})
    
    # Index 6: 15:00 - 15:00 (Only the 15:00 candle if session end is 15:00)
    # Actually Pine sessionStr is "0930-1600" if i_sessionEndHour=15.
    # So it includes the entire 15:XX hour.
    b6 = df_1m_day.between_time('15:00', '15:59')
    if not b6.empty:
        boxes.append({'h': b6['high'].max(), 'l': b6['low'].min()})
        
    return boxes

def analyze_parity(d, df_1m, tol_ticks=2.0, min_touches_r1=4, min_sep_r2=1, r2_win_start_idx=2):
    m = df_1m[df_1m['date'] == d]
    if m.empty: return None
    
    # OR: 9:30 1m candle
    or_candle = m[m['time_only'] == time(9, 30)]
    if or_candle.empty: return None
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    
    # Reconstruct boxes
    boxes = get_parity_boxes(m)
    if not boxes: return None
    
    tol = tol_ticks * 0.25
    def touches(bh, bl): return bh >= (or_l - tol) and bl <= (or_h + tol)
    def broke(bh, bl): return bl > (or_h + tol) or bh < (or_l - tol)
    
    highs = [b['h'] for b in boxes]
    lows = [b['l'] for b in boxes]
    size = len(boxes)
    
    broke_or = False
    broke_or_idx = -1
    broke_up = False
    touch_count = 0
    returned = False
    ret_idx = -1
    
    # Step 1: Find Break and count initial touches
    for i in range(size):
        if broke(highs[i], lows[i]):
            broke_or = True
            broke_or_idx = i
            broke_up = lows[i] > (or_h + tol)
            break
        elif touches(highs[i], lows[i]):
            touch_count += 1
            
    # Step 2: Check for Return
    if broke_or and broke_or_idx < size - 1:
        for i in range(broke_or_idx + 1, size):
            if touches(highs[i], lows[i]):
                returned = True
                ret_idx = i
                touch_count += 1
                break
                
    # Step 3: Pullbacks
    has_pb = False
    if broke_or and not returned: # and not R1/R2
        pb_end = size - 2
        if pb_end > broke_or_idx:
            if broke_up:
                hl = lows[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if lows[i] < hl: has_pb = True; break
                    hl = max(hl, lows[i])
            else:
                lh = highs[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if highs[i] > lh: has_pb = True; break
                    lh = min(lh, highs[i])

    # Step 4: Classification Precedence (Table behavior R2 > R1)
    is_r2 = broke_or and returned and ret_idx >= r2_win_start_idx and (ret_idx - broke_or_idx) >= min_sep_r2
    is_r1 = touch_count >= min_touches_r1
    
    if is_r2: return "R2"
    if is_r1: return "R1"
    if not broke_or: return "R1"
    
    return "DWP" if has_pb else "DNP"

def run_parity():
    df_1m = load_data_1m("NQ1")
    
    ref = {
        "2025-10-06": "R2", "2025-10-07": "DNP", "2025-10-08": "DNP", "2025-10-09": "DWP", "2025-10-10": "DNP",
        "2025-10-13": "DNP", "2025-10-14": "DNP", "2025-10-15": "R2", "2025-10-16": "DNP", "2025-10-17": "DWP",
        "2025-10-20": "DWP", "2025-10-21": "R2", "2025-10-22": "DNP", "2025-10-23": "DNP", "2025-10-24": "DWP",
        "2025-10-27": "DNP", "2025-10-28": "R2", "2025-10-29": "R2", "2025-10-30": "R1", "2025-10-31": "DWP",
        "2025-11-03": "DWP", "2025-11-04": "R2", "2025-11-05": "DNP", "2025-11-06": "DWP", "2025-11-07": "R2",
        "2025-11-10": "R2", "2025-11-11": "R2", "2025-11-12": "DWP", "2025-11-13": "DNP", "2025-11-14": "DWP",
        "2025-11-17": "R1", "2025-11-18": "R2", "2025-11-19": "R2", "2025-11-20": "DNP", "2025-11-21": "R2",
        "2025-11-24": "DWP", "2025-11-25": "DWP", "2025-11-26": "DWP", "2025-11-27": "DNP", "2025-12-01": "DWP",
        "2025-12-02": "R2", "2025-12-03": "DNP", "2025-12-04": "R1", "2025-12-05": "R2", "2025-12-08": "DWP",
        "2025-12-09": "DWP", "2025-12-10": "R1", "2025-12-11": "R1", "2025-12-12": "DWP", "2025-12-15": "DWP",
        "2025-12-16": "R1", "2025-12-17": "DNP", "2025-12-18": "R2", "2025-12-19": "DWP", "2025-12-22": "R1",
        "2025-12-23": "DNP", "2025-12-26": "R2", "2025-12-29": "R1", "2025-12-30": "R1", "2025-12-31": "DWP",
        "2026-01-02": "DWP", "2026-01-05": "R2", "2026-01-06": "DNP", "2026-01-07": "R2", "2026-01-08": "R2",
        "2026-01-09": "DWP", "2026-01-12": "DWP", "2026-01-13": "R1", "2026-01-14": "DWP", "2026-01-15": "R1",
        "2026-01-16": "DWP"
    }
    
    results = []
    correct = 0
    total = 0
    print(f"{'Date':<12} | {'Out':<4} | {'Ref':<4} | Status")
    print("-" * 35)
    for d_str, r in ref.items():
        d = pd.to_datetime(d_str).date()
        out = analyze_parity(d, df_1m)
        total += 1
        if out == r:
            correct += 1
            print(f"{d_str:<12} | {out:<4} | {r:<4} | OK")
        else:
            print(f"{d_str:<12} | {out:<4} | {r:<4} | MISMATCH")
            
    print("-" * 35)
    print(f"Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")

if __name__ == "__main__":
    run_parity()
