
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

# --- Configuration ---
TICKERS = ['GC1', 'CL1', 'ES1'] # Added ES as control
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

def test_judas_time(day_data, start_hour, start_minute):
    # Judas Window: Start to Start+10m
    # Resolution: Start+30m
    
    t_start = pd.Timestamp.combine(day_data.name, time(start_hour, start_minute)).tz_localize('US/Eastern')
    t_end_move = t_start + timedelta(minutes=10)
    t_resolution = t_start + timedelta(minutes=30)
    
    try:
        p_start = day_data.loc[t_start]['open']
        p_end_move = day_data.loc[t_end_move - timedelta(minutes=1)]['close'] 
        p_res = day_data.loc[t_resolution - timedelta(minutes=1)]['close']
    except KeyError:
        return None
        
    initial_move = p_end_move - p_start
    
    res = {'Scenario': None, 'Continuation': False, 'Reversal': False}
    
    if initial_move > 0: # UP
        res['Scenario'] = 'UP'
        if p_res > p_end_move: res['Continuation'] = True
        if p_res < p_start: res['Reversal'] = True
    elif initial_move < 0: # DOWN
        res['Scenario'] = 'DOWN'
        if p_res < p_end_move: res['Continuation'] = True
        if p_res > p_start: res['Reversal'] = True
        
    return res

def optimize_judas(ticker):
    df = load_data(ticker)
    if df is None: return
    
    daily_groups = df.groupby(df.index.date)
    
    # Test times: 08:00, 08:30, 09:00, 09:30, 10:00
    times_to_test = [ (8,0), (8,20), (8,30), (9,0), (9,30) ]
    
    summary = []
    
    for h, m in times_to_test:
        results = []
        for date, day_data in daily_groups:
            # Pass date as name for helper
            day_data.name = date 
            r = test_judas_time(day_data, h, m)
            if r and r['Scenario']: results.append(r)
            
        res_df = pd.DataFrame(results)
        if not res_df.empty:
            cont_rate = res_df['Continuation'].mean()
            rev_rate = res_df['Reversal'].mean()
            # Combined Rate (UP and DOWN)
            summary.append({
                'Time': f"{h:02d}:{m:02d}",
                'Continuation': cont_rate,
                'Reversal': rev_rate,
                'Count': len(res_df)
            })
            
    print(f"\n--- Optimization for {ticker} ---")
    print(pd.DataFrame(summary).to_string(index=False))

def main():
    print("Optimizing Morning Judas Times...")
    for t in TICKERS:
        optimize_judas(t)

if __name__ == "__main__":
    main()
