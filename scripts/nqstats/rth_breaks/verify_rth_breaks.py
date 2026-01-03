
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

def verify_rth_breaks(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    # Logic:
    # 1. Identify "Trading Days".
    # 2. Get RTH (9:30-16:00) High/Low for Day T-1.
    # 3. Get Open Price at 9:30 for Day T.
    # 4. Check interaction.
    
    # Resample to Daily RTH Stats
    # Filter 9:30-16:00 data only for the RTH params
    rth_data = df.between_time(time(9,30), time(16,0))
    
    # Aggregates for RTH
    daily_rth = rth_data.resample('1D').agg({
        'high': 'max', 
        'low': 'min', 
        'close': 'last'
    }).dropna()
    
    # Normalize index to Date for easy lookup
    daily_rth.index = daily_rth.index.date
    
    # We need the "Open" of the *Day*.
    # Actually, RTH Open (9:30) is the Opening Price we care about.
    # Let's get the 9:30 open explicitly.
    
    # To be precise, let's iterate days in the main DF to match T and T-1 correctly.
    
    results = []
    dates = daily_rth.index
    
    for i in range(1, len(dates)):
        curr_date = dates[i]
        prev_date = dates[i-1]
        
        # Check consecutive safety
        if (curr_date - prev_date).days > 3: continue
        
        # T-1 RTH Params
        try:
            prev_row = daily_rth.loc[prev_date]
            prev_high = prev_row['high']
            prev_low = prev_row['low']
        except KeyError:
            continue
            
        # T Params
        # Open at 9:30
        t_open_ts = pd.Timestamp.combine(curr_date, time(9,30)).tz_localize('US/Eastern')
        
        # Get data for Day T (9:30 to 16:00)
        t_data = df.loc[t_open_ts : t_open_ts + pd.Timedelta(hours=6, minutes=30)]
        if t_data.empty: continue
        
        open_price = t_data.iloc[0]['open'] # The 9:30 open
        
        # Determine Open Type
        open_type = "Inside"
        if open_price > prev_high: open_type = "Outside_Above"
        elif open_price < prev_low: open_type = "Outside_Below"
        
        # Check Outcomes
        broken_high = t_data['high'].max() > prev_high
        broken_low = t_data['low'].min() < prev_low
        
        res = {
            'Date': curr_date,
            'Open_Type': open_type,
            'Broken_High': broken_high,
            'Broken_Low': broken_low
        }
        results.append(res)
        
    res_df = pd.DataFrame(results)
    if res_df.empty: return None

    summary = []
    
    # Analyze Inside Opens
    inside = res_df[res_df['Open_Type'] == 'Inside']
    if len(inside) > 0:
        break_one = inside[(inside['Broken_High'] | inside['Broken_Low']) & ~(inside['Broken_High'] & inside['Broken_Low'])]
        break_both = inside[inside['Broken_High'] & inside['Broken_Low']]
        stay_inside = inside[~inside['Broken_High'] & ~inside['Broken_Low']]
        
        summary.append({'Scenario': 'Open Inside', 'Total': len(inside), 
                        'Break_One_Side %': len(break_one)/len(inside),
                        'Break_Both %': len(break_both)/len(inside),
                        'Stay_Inside %': len(stay_inside)/len(inside)})
                        
    # Analyze Outside Opens (Gap Hold Rule)
    # Open Above -> Don't break Low
    outside_above = res_df[res_df['Open_Type'] == 'Outside_Above']
    if len(outside_above) > 0:
        held_low = outside_above[~outside_above['Broken_Low']]
        summary.append({'Scenario': 'Open Outside Above', 'Total': len(outside_above),
                        'Held_Opposite (Low) %': len(held_low)/len(outside_above)})
                        
    # Open Below -> Don't break High
    outside_below = res_df[res_df['Open_Type'] == 'Outside_Below']
    if len(outside_below) > 0:
        held_high = outside_below[~outside_below['Broken_High']]
        summary.append({'Scenario': 'Open Outside Below', 'Total': len(outside_below),
                        'Held_Opposite (High) %': len(held_high)/len(outside_below)})
                        
    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_res = []
    for t in TICKERS:
        print(f"Verifying RTH Breaks for {t}...")
        res = verify_rth_breaks(t)
        if res is not None:
            all_res.append(res)
            print(res.to_string())
            
    if all_res:
        pd.concat(all_res).to_csv('scripts/nqstats/results/rth_breaks_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/rth_breaks_verification.csv")

if __name__ == "__main__":
    main()
