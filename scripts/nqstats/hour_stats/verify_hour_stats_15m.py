
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

def verify_hour_stats_15m(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    daily_groups = df.groupby(df.index.date)
    target_hours = [8, 9, 10, 11, 12, 13, 14, 15] 
    
    results = []
    
    for date, day_data in daily_groups:
        if len(day_data) < 100: continue
        
        # Get hourly stats for this day
        day_hourly = day_data.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min'})
        
        for h in target_hours:
            try:
                curr_hour_ts = pd.Timestamp.combine(date, time(h,0)).tz_localize('US/Eastern')
                prev_hour_ts = curr_hour_ts - pd.Timedelta(hours=1)
                
                if curr_hour_ts not in day_hourly.index or prev_hour_ts not in day_hourly.index:
                    continue
                    
                prior_high = day_hourly.loc[prev_hour_ts, 'high']
                prior_low = day_hourly.loc[prev_hour_ts, 'low']
                curr_open = day_hourly.loc[curr_hour_ts, 'open']
                
                curr_data = day_data.loc[curr_hour_ts : curr_hour_ts + pd.Timedelta(minutes=59)]
                if curr_data.empty: continue
                
                # Check for Sweep
                swept_high = False
                swept_low = False
                
                high_sweep_mask = curr_data['high'] > prior_high
                low_sweep_mask = curr_data['low'] < prior_low
                
                high_sweep_time = None
                low_sweep_time = None
                
                if high_sweep_mask.any():
                    high_sweep_time = high_sweep_mask.idxmax()
                    swept_high = True
                if low_sweep_mask.any():
                    low_sweep_time = low_sweep_mask.idxmax()
                    swept_low = True
                    
                events = []
                if swept_high: events.append((high_sweep_time, 'High', prior_high))
                if swept_low: events.append((low_sweep_time, 'Low', prior_low))
                if not events: continue
                
                events.sort(key=lambda x: x[0])
                first_sweep = events[0]
                sweep_ts = first_sweep[0]
                sweep_type = first_sweep[1]
                
                # --- MODIFICATION: 15 Minute Quarters ---
                minutes_into_hour = (sweep_ts - curr_hour_ts).seconds // 60
                segment = ""
                if minutes_into_hour < 15: segment = "0-15"
                elif minutes_into_hour < 30: segment = "15-30" # Note: Original 20-40, here 15-30
                elif minutes_into_hour < 45: segment = "30-45"
                else: segment = "45-60"
                # ----------------------------------------
                
                post_sweep_data = curr_data.loc[sweep_ts:]
                
                returned = False
                if sweep_type == 'High':
                    if (post_sweep_data['low'] <= curr_open).any():
                        returned = True
                else: # Low
                    if (post_sweep_data['high'] >= curr_open).any():
                        returned = True
                        
                results.append({
                    'Hour': h,
                    'Segment': segment,
                    'Sweep_Type': sweep_type,
                    'Returned': returned
                })
            except: continue
 
    results_df = pd.DataFrame(results)
    if results_df.empty: return None
    
    summary = []
    
    # By Segment (15m Quarters)
    for seg in ['0-15', '15-30', '30-45', '45-60']:
        seg_df = results_df[results_df['Segment'] == seg]
        cnt = len(seg_df)
        if cnt > 0:
            summary.append({'Metric': f'Seg {seg}', 'Count': cnt, 'WinRate': seg_df['Returned'].sum()/cnt})
            
    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_summaries = []
    print("Verifying Hour Stats (15-Minute Quarters)...")
    for t in TICKERS:
        res = verify_hour_stats_15m(t)
        if res is not None:
            all_summaries.append(res)
            print(f"--- {t} ---")
            print(res.to_string(index=False))
            
    if all_summaries:
        pd.concat(all_summaries).to_csv('scripts/nqstats/results/hour_stats_15m.csv', index=False)

if __name__ == "__main__":
    main()
