import pandas as pd
import numpy as np
import pytz
import json
from datetime import time, datetime
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

def analyze_day(d, df_1m, df_1h, tolerance_ticks=2.0, min_touches_r1=4, min_sep_r2=1, return_window_start=11):
    m = df_1m[df_1m['date'] == d]
    if m.empty: return None
    
    # Opening Range (09:30 candle)
    or_candle = m[m['time_only'] == time(9, 30)]
    if or_candle.empty: return None
    or_h = or_candle.iloc[0]['high']
    or_l = or_candle.iloc[0]['low']
    
    # Hourly data for this day
    h = df_1h[df_1h['date'] == d]
    rth_h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(15, 0))]
    
    # 09:30 range in price (with tolerance)
    tolerance = tolerance_ticks * 0.25 # NQ tick is 0.25? Actually check syminfo.mintick. NQ is 0.25.
    
    # PineScript logic mirror
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
    
    # Step 1: Find where price first breaks OR and count initial touches
    for i in range(size):
        hh, hl = hourly_highs[i], hourly_lows[i]
        if broke_or(hh, hl):
            if not broke_or_flag:
                broke_or_flag = True
                broke_or_idx = i
                broke_up = hl > (or_h + tolerance)
            # PineScript break logic stops counting initial touches once broken
            # BUT it allows counting the touch at the break? 
            # Actually PineScript: "else if touchesOR..." so it doesn't touch if it breaks.
        else:
            if touches_or(hh, hl):
                or_touch_count += 1
                
    # Step 2: If broke OR, check for return to OR after the break
    if broke_or_flag and broke_or_idx < size - 1:
        for i in range(broke_or_idx + 1, size):
            hh, hl = hourly_highs[i], hourly_lows[i]
            if touches_or(hh, hl):
                returned_to_or = True
                return_hour_idx = i
                or_touch_count += 1
                break
                
    # Step 3: Check for pullbacks (only if broke OR)
    # pullbackEndIndex = size - 2 (pine script excludes final 15:00 hour)
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
        else: # broke down
            lowest_high = hourly_highs[broke_or_idx]
            for i in range(broke_or_idx + 1, pullback_end_idx + 1):
                ch = hourly_highs[i]
                if ch > lowest_high:
                    has_pullback = True
                    break
                lowest_high = min(lowest_high, ch)
                
    # Step 4: Classification Precedence
    ret_after_window = (return_hour_idx >= (return_window_start - 9)) # 9 is start hour
    separation = return_hour_idx - broke_or_idx
    enough_sep = (separation >= min_sep_r2)
    
    is_r2_candidate = broke_or_flag and returned_to_or and ret_after_window and enough_sep
    is_r1_candidate = (or_touch_count >= min_touches_r1)
    
    is_directional = broke_or_flag and not is_r2_candidate and not is_r1_candidate
    
    classification = "Range 1"
    if is_r1_candidate and not is_r2_candidate:
        classification = "Range 1"
    elif is_r2_candidate:
        classification = "Range 2"
    elif is_directional:
        classification = "DWP" if has_pullback else "DNP"
    elif not broke_or_flag:
        classification = "Range 1"
    else:
        classification = "Range 1"
        
    return {
        'date': str(d),
        'classification': classification,
        'touches': or_touch_count,
        'broke': broke_or_flag,
        'returned': returned_to_or,
        'ret_idx': return_hour_idx,
        'sep': separation
    }

def run_report():
    df_1m = load_data("NQ1", "1m")
    df_1h = load_data("NQ1", "1h")
    
    dates = df_1m[(df_1m['date'] >= pd.to_datetime("2025-12-20").date()) & (df_1m['date'] <= pd.to_datetime("2026-01-15").date())]['date'].unique()
    
    results = []
    for d in dates:
        res = analyze_day(d, df_1m, df_1h)
        if res:
            results.append(res)
            
    print("\nFINAL CLASSIFICATION REPORT (Pinescript Mirror):")
    for r in results:
        print(f"{r['date']}: {r['classification']} (Touches={r['touches']}, Broke={r['broke']}, Ret={r['returned']}, Sep={r['sep']})")

if __name__ == "__main__":
    run_report()
