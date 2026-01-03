
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

def verify_judas(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    # Iterate Days
    daily_groups = df.groupby(df.index.date)
    
    results = []
    
    for date, day_data in daily_groups:
        # Timestamps: 09:30, 09:40, 10:00
        t_930 = pd.Timestamp.combine(date, time(9,30)).tz_localize('US/Eastern')
        t_940 = pd.Timestamp.combine(date, time(9,40)).tz_localize('US/Eastern')
        t_1000 = pd.Timestamp.combine(date, time(10,0)).tz_localize('US/Eastern')
        
        # Get Prices (Open/Close)
        # Using .asof or specific loc if available, but simplest is to grab the specific 1m candle
        # Logic: "Move between 9:30 and 9:40".
        # Does this mean (9:40 Close - 9:30 Open)? Or 9:40 Open?
        # Standard interpretation: The "10 minute bar" from 9:30 to 9:40.
        # So Start = 9:30 Open. End = 9:40 Close (Bar 09:39).
        # Let's use exact times for precision.
        
        try:
            p_930 = day_data.loc[t_930]['open'] # Opening bell price
            # 9:40 Price: The price AT 9:40:00 (which is the Open of the 9:40 candle or Close of 9:39)
            # Let's use Close of 09:39 (The end of the first 10 mins).
            p_940 = day_data.loc[t_940 - timedelta(minutes=1)]['close'] 
            # 10:00 Price: Close of 09:59 (End of first 30 mins)
            p_1000 = day_data.loc[t_1000 - timedelta(minutes=1)]['close']
        except KeyError:
            continue
            
        # Determine 9:30-9:40 Move
        initial_move = p_940 - p_930
        
        scenario = None
        is_continuation = False
        is_reversal = False
        
        if initial_move > 0: # UP Move
            scenario = 'UP'
            # Continuation: 10:00 > 9:40 (Did it go higher?)
            if p_1000 > p_940: is_continuation = True
            # Reversal: 10:00 < 9:30 (Did it go below the start?)
            if p_1000 < p_930: is_reversal = True
            
        elif initial_move < 0: # DOWN Move
            scenario = 'DOWN'
            # Continuation: 10:00 < 9:40 (Did it go lower?)
            if p_1000 < p_940: is_continuation = True
            # Reversal: 10:00 > 9:30 (Did it go above start?)
            if p_1000 > p_930: is_reversal = True
            
        if scenario:
            results.append({
                'Scenario': scenario,
                'Continuation': is_continuation,
                'Reversal': is_reversal
            })
            
    res_df = pd.DataFrame(results)
    if res_df.empty: return None
    
    summary = []
    
    # Analyze UP
    up_df = res_df[res_df['Scenario'] == 'UP']
    if len(up_df) > 0:
        cont_rate = up_df['Continuation'].mean()
        rev_rate = up_df['Reversal'].mean()
        summary.append({'Move': '9:30-9:40 UP', 'Continuation > 9:40': cont_rate, 'Reversal < 9:30': rev_rate})
        
    # Analyze DOWN
    down_df = res_df[res_df['Scenario'] == 'DOWN']
    if len(down_df) > 0:
        cont_rate = down_df['Continuation'].mean()
        rev_rate = down_df['Reversal'].mean()
        summary.append({'Move': '9:30-9:40 DOWN', 'Continuation < 9:40': cont_rate, 'Reversal > 9:30': rev_rate})
        
    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_res = []
    print("Verifying Morning Judas (9:30-9:40 vs 10:00)...")
    for t in TICKERS:
        res = verify_judas(t)
        if res is not None:
            all_res.append(res)
            print(f"--- {t} ---")
            print(res.to_string(index=False))
            
    if all_res:
        pd.concat(all_res).to_csv('scripts/nqstats/results/judas_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/judas_verification.csv")

if __name__ == "__main__":
    main()
