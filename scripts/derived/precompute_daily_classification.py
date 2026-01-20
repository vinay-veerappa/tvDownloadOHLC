import pandas as pd
import numpy as np
import pytz
import os
import argparse
from datetime import time, datetime
from pathlib import Path
from tqdm import tqdm

# Constants
DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
# Create output dir if it doesn't exist
OUTPUT_DIR = DATA_DIR / "derived"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NY_TZ = pytz.timezone("America/New_York")

def load_data_1m(ticker: str):
    path = DATA_DIR / f"{ticker}_1m.parquet"
    if not path.exists():
        print(f"Error: {path} not found.")
        return None
    df = pd.read_parquet(path)
    # Ensure index is localized to NY Time
    if df.index.tz is None:
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY_TZ)
    else:
        df.index = df.index.tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def get_session_boxes(df_1m_day):
    """
    Constructs hourly boxes mirroring the PineScript indicator:
    Box 1: 09:30 - 10:00
    Box 2: 10:00 - 11:00
    ...
    Box 7: 15:00 - 16:00
    """
    boxes = []
    # Box 0: 09:30 to 09:59
    b0 = df_1m_day.between_time('09:30', '09:59')
    if not b0.empty:
        boxes.append({'h': b0['high'].max(), 'l': b0['low'].min(), 't': time(9, 30)})
    
    # Boxes 1-5: 10:00 to 14:00
    for h in range(10, 15):
        bh = df_1m_day.between_time(f"{h:02d}:00", f"{h:02d}:59")
        if not bh.empty:
            boxes.append({'h': bh['high'].max(), 'l': bh['low'].min(), 't': time(h, 0)})
    
    # Box 6: 15:00 to 15:59
    b6 = df_1m_day.between_time('15:00', '15:59')
    if not b6.empty:
        boxes.append({'h': b6['high'].max(), 'l': b6['low'].min(), 't': time(15, 0)})
        
    return boxes

def analyze_day(d, m, ticker):
    """
    Core Classification Logic (Mirrors PineScript v2)
    """
    # 1. Opening Range Detection (9:30 1m bar)
    or_candle = m[m['time_only'] == time(9, 30)]
    if or_candle.empty: return None
    or_h, or_l = or_candle.iloc[0]['high'], or_candle.iloc[0]['low']
    
    # 2. Reconstruct Boxes
    boxes = get_session_boxes(m)
    if not boxes: return None
    
    # Settings (mirrored from Pine)
    tol_ticks = 2.0
    
    # Determined Tick Size
    if "CL" in ticker: tick_size = 0.01
    elif "GC" in ticker: tick_size = 0.1
    elif "RTY" in ticker: tick_size = 0.1
    elif "YM" in ticker: tick_size = 1.0
    else: tick_size = 0.25 # Default for ES, NQ
    
    tolerance = tol_ticks * tick_size
    min_touches_r1 = 4
    min_sep_r2 = 1
    r2_window_start_idx = 2 # 11:00 AM NY
    
    highs = [b['h'] for b in boxes]
    lows = [b['l'] for b in boxes]
    size = len(boxes)
    
    def touch_check(h, l): return h >= (or_l - tolerance) and l <= (or_h + tolerance)
    def break_check(h, l): return l > (or_h + tolerance) or h < (or_l - tolerance)
    
    broke_or = False
    broke_or_idx = -1
    broke_up = False
    touch_count = 0
    returned = False
    ret_idx = -1
    
    # Analysis Phase 1: Breaks & Touches
    for i in range(size):
        if break_check(highs[i], lows[i]):
            if not broke_or:
                broke_or = True
                broke_or_idx = i
                broke_up = lows[i] > (or_h + tolerance)
        else:
            if touch_check(highs[i], lows[i]):
                touch_count += 1
                
    # Analysis Phase 2: Returns (for R2)
    if broke_or and broke_or_idx < size - 1:
        for i in range(broke_or_idx + 1, size):
            if touch_check(highs[i], lows[i]):
                returned = True
                ret_idx = i
                touch_count += 1
                break
                
    # Analysis Phase 3: Pullbacks (for DWP/DNP)
    has_pb = False
    if broke_or and not returned:
        pb_end = size - 2 # Exclude final hourly bar
        if pb_end > broke_or_idx:
            if broke_up:
                highest_low = lows[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if lows[i] < highest_low:
                        has_pb = True
                        break
                    highest_low = max(highest_low, lows[i])
            else:
                lowest_high = highs[broke_or_idx]
                for i in range(broke_or_idx + 1, pb_end + 1):
                    if highs[i] > lowest_high:
                        has_pb = True
                        break
                    lowest_high = min(lowest_high, highs[i])

    # 3. Final Classification (Priority: R2 > R1 > Trail)
    is_r2 = broke_or and returned and ret_idx >= r2_window_start_idx and (ret_idx - broke_or_idx) >= min_sep_r2
    is_r1 = touch_count >= min_touches_r1
    
    classification = "Range 1"
    if is_r2: 
        classification = "R2"
    elif is_r1:
        classification = "R1"
    elif broke_or:
        classification = "DWP" if has_pb else "DNP"
    else:
        classification = "R1"
        
    return {
        'date': d,
        'type': classification,
        'or_high': or_h,
        'or_low': or_l,
        'touches': touch_count,
        'broke': broke_or,
        'returned': returned
    }

def process_ticker(ticker):
    print(f"\nProcessing {ticker}...")
    df_1m = load_data_1m(ticker)
    if df_1m is None: return
    
    dates = df_1m['date'].unique()
    results = []
    
    # Optimized: Group by date first
    grouped = df_1m.groupby('date')
    
    for d, m in tqdm(grouped, desc=f"Analyzing {ticker}"):
        # m is the daily dataframe
        res = analyze_day(d, m, ticker)
        if res:
            results.append(res)
            
    res_df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / f"{ticker}_daily_classification.parquet"
    res_df.to_parquet(output_path)
    print(f"Saved {len(res_df)} classifications to {output_path}")

def run_precompute(ticker):
    process_ticker(ticker)

def main():
    parser = argparse.ArgumentParser(description="Precompute Daily Action Classifications (R1, R2, DWP, DNP)")
    parser.add_argument("--tickers", nargs="+", default=["NQ1", "ES1"], help="Tickers to process")
    args = parser.parse_args()
    
    for ticker in args.tickers:
        run_precompute(ticker)

if __name__ == "__main__":
    main()
