
import pandas as pd
import numpy as np
import os
import pytz
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['NQ1', 'ES1', 'YM1', 'RTY1', 'GC1', 'CL1']
DATA_DIR = 'data'
START_YEAR = 2015

def load_data(ticker):
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    if not os.path.exists(path): return None
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('datetime', inplace=True)
    df = df.tz_convert('US/Eastern')
    return df[df.index.year >= START_YEAR]

def verify_1h_continuation(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    # Iterate Days
    daily_groups = df.groupby(df.index.date)
    
    results = []
    
    for date, day_data in daily_groups:
        # Define 9AM Hour (09:00 - 10:00)
        h9_start = pd.Timestamp.combine(date, time(9,0)).tz_localize('US/Eastern')
        h9_end = pd.Timestamp.combine(date, time(10,0)).tz_localize('US/Eastern')
        
        h9_data = day_data.loc[h9_start:h9_end]
        if len(h9_data) < 2: continue
        
        # 9AM Open and 10AM Close (or last tick of 9:59)
        # Using .iloc[0] and .iloc[-1]
        h9_open = h9_data.iloc[0]['open']
        h9_close = h9_data.iloc[-1]['close'] # Approx 10:00
        
        is_green_9am = h9_close > h9_open
        is_red_9am = h9_close < h9_open
        if not is_green_9am and not is_red_9am: continue # Doji
        
        # Define NY Session (09:30 - 16:00)
        ny_start = pd.Timestamp.combine(date, time(9,30)).tz_localize('US/Eastern')
        ny_end = pd.Timestamp.combine(date, time(16,0)).tz_localize('US/Eastern')
        
        ny_data = day_data.loc[ny_start:ny_end]
        if len(ny_data) < 10: continue
        
        ny_open = ny_data.iloc[0]['open'] # 9:30 Open
        ny_close = ny_data.iloc[-1]['close'] # 16:00 Close
        
        ny_green = ny_close > ny_open
        ny_red = ny_close < ny_open
        
        # Define Full Session (Daily Candle)
        # Assuming Data is continuous, Daily Open might be 18:00 prev day or 00:00?
        # The logic usually implies the "RTH" or "Full Electronic" session.
        # Image says "Full Session 6pm-5pm".
        # Let's approximate Full Session as simple (Session Open -> Session Close).
        # We'll use the day_data.iloc[0] and [-1] roughly?
        # Actually, let's stick to the NY Session claim as it's the strongest (70%).
        
        res = {
            'Date': date,
            '9AM_Green': is_green_9am,
            '9AM_Red': is_red_9am,
            'NY_Green': ny_green,
            'NY_Red': ny_red
        }
        results.append(res)
        
    res_df = pd.DataFrame(results)
    if res_df.empty: return None

    summary = []
    
    # 1. 9AM Green -> NY Green
    green_samples = res_df[res_df['9AM_Green']]
    if len(green_samples) > 0:
        win_rate = green_samples['NY_Green'].mean()
        summary.append({'Scenario': '9AM Green -> NY Green', 'Count': len(green_samples), 'WinRate': win_rate})
        
    # 2. 9AM Red -> NY Red
    red_samples = res_df[res_df['9AM_Red']]
    if len(red_samples) > 0:
        win_rate = red_samples['NY_Red'].mean()
        summary.append({'Scenario': '9AM Red -> NY Red', 'Count': len(red_samples), 'WinRate': win_rate})
        
    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_res = []
    print("Verifying 1H Continuation (9AM Candle -> NY Session)...")
    for t in TICKERS:
        res = verify_1h_continuation(t)
        if res is not None:
            all_res.append(res)
            print(f"--- {t} ---")
            print(res.to_string(index=False))
            
    if all_res:
        pd.concat(all_res).to_csv('scripts/nqstats/results/1h_continuation_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/1h_continuation_verification.csv")

if __name__ == "__main__":
    main()
