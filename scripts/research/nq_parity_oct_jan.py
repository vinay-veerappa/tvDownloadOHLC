import pandas as pd
import numpy as np
import pytz
from datetime import time
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker: str, tf: str):
    path = DATA_DIR / f"{ticker}_{tf}.parquet"
    if not path.exists(): return pd.DataFrame()
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

def analyze_day(d, df_1m, df_1h, tolerance_ticks=2.0, min_touches_r1=4, min_sep_r2=1, return_window_start=11, session_start=9):
    m = df_1m[df_1m['date'] == d]
    if m.empty: return None
    
    or_candle = m[m['time_only'] == time(9, 30)]
    if or_candle.empty: return None
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    
    h = df_1h[df_1h['date'] == d]
    # PineScript: session starts 09:30. Hourly boxes are added at hour changes.
    # The first box (idx 0) covers 09:30 to 10:00.
    rth_h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(15, 0))]
    
    tolerance = tolerance_ticks * 0.25 # NQ tick 0.25
    
    def touches_or(bh, bl):
        return bh >= (or_l - tolerance) and bl <= (or_h + tolerance)
    
    def broke_or(bh, bl):
        return bl > (or_h + tolerance) or bh < (or_l - tolerance)

    hourly_highs = rth_h['high'].tolist()
    hourly_lows = rth_h['low'].tolist()
    size = len(hourly_highs)
    
    broke_or_flag = False
    broke_or_idx = -1
    broke_up = False
    or_touch_count = 0
    returned_to_or = False
    return_hour_idx = -1
    has_pullback = False
    
    # Step 1: Find break and count touches
    for i in range(size):
        hh, hl = hourly_highs[i], hourly_lows[i]
        if broke_or(hh, hl):
            if not broke_or_flag:
                broke_or_flag = True
                broke_or_idx = i
                broke_up = hl > (or_h + tolerance)
        else:
            if touches_or(hh, hl):
                or_touch_count += 1
                
    # Step 2: Return after break
    if broke_or_flag and broke_or_idx < size - 1:
        for i in range(broke_or_idx + 1, size):
            hh, hl = hourly_highs[i], hourly_lows[i]
            if touches_or(hh, hl):
                returned_to_or = True
                return_hour_idx = i
                or_touch_count += 1
                break
                
    # Step 3: Pullbacks
    pullback_end_idx = size - 2
    if broke_or_flag and broke_or_idx >= 0 and pullback_end_idx > broke_or_idx:
        if broke_up:
            highest_low = hourly_lows[broke_or_idx]
            for i in range(broke_or_idx + 1, pullback_end_idx + 1):
                cl = hourly_lows[i]
                if cl < highest_low:
                    has_pullback = True
                    break
                highest_low = max(highest_low, cl)
        else:
            lowest_high = hourly_highs[broke_or_idx]
            for i in range(broke_or_idx + 1, pullback_end_idx + 1):
                ch = hourly_highs[i]
                if ch > lowest_high:
                    has_pullback = True
                    break
                lowest_high = min(lowest_high, ch)
                
    # Step 4: Classification
    # win_start_idx = return_window_start - session_start
    # Session starts at 09:30. idx 0 = 09:00 candle (9:30-10:00). 
    # idx 1 = 10:00 (10:00-11:00). idx 2 = 11:00 (11:00-12:00).
    # So 11:00 window starts at Index 2.
    win_start_idx = return_window_start - session_start # 11 - 9 = 2
    ret_after_window = (return_hour_idx >= win_start_idx)
    separation = return_hour_idx - broke_or_idx
    enough_sep = (separation >= min_sep_r2)
    
    is_r2_candidate = broke_or_flag and returned_to_or and ret_after_window and enough_sep
    
    # R1 Rule
    max_continuous = 0
    curr_continuous = 0
    for i in range(size):
        if touches_or(hourly_highs[i], hourly_lows[i]):
            curr_continuous += 1
            max_continuous = max(max_continuous, curr_continuous)
        else:
            curr_continuous = 0
            
    is_r1_candidate = (or_touch_count >= min_touches_r1) or (max_continuous >= 4)
    
    is_directional = broke_or_flag and not is_r1_candidate and not is_r2_candidate
    
    if is_r2_candidate:
        classification = "R2"
    elif is_r1_candidate:
        classification = "R1"
    elif is_directional:
        classification = "DWP" if has_pullback else "DNP"
    elif not broke_or_flag:
        classification = "R1"
    else:
        classification = "R1"
        
    return classification

def run_parity_test():
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    # Oct 06 to Jan 16
    start = pd.to_datetime("2025-10-06").date()
    end = pd.to_datetime("2026-01-16").date()
    dates = df_1m[(df_1m['date'] >= start) & (df_1m['date'] <= end)]['date'].unique()
    
    # Reference from image (Full Table)
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
    
    mismatches = 0
    total = 0
    print(f"{'Date':<12} | {'Output':<6} | {'Ref':<6} | {'Status'}")
    print("-" * 40)
    for d in dates:
        out = analyze_day(d, df_1m, df_1h)
        r = ref.get(str(d), "")
        if r != "":
            total += 1
            status = "OK"
            if out != r:
                status = "MISMATCH"
                mismatches += 1
            print(f"{str(d):<12} | {out:<6} | {r:<6} | {status}")
    
    print("-" * 40)
    print(f"Total: {total}, Mismatches: {mismatches}, Accuracy: {(total-mismatches)/total*100:.1f}%")

if __name__ == "__main__":
    run_parity_test()
