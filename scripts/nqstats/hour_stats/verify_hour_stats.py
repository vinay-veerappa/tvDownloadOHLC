
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

def verify_hour_stats(ticker):
    df = load_data(ticker)
    if df is None: return None
    
    # We analyze hours 08:00 to 16:00
    # For each date, loop hours 8, 9, 10... 16
    
    # Efficient way: Resample by Hour? 
    # We need intra-hour action. 
    # Use GroupBy (Date, Hour)
    
    # But we need "Prior Hour" High/Low.
    # GroupBy Hour is okay if we can shift metrics.
    
    # Vectorized approch:
    # 1. Resample to 1H to get Open, High, Low per hour.
    # 2. Shift to get Prior High/Low.
    # 3. Join back to 1M data? Or iterate?
    
    # Hybrid:
    # 1. Get Hourly OHLC
    hourly = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
    hourly['Prior_High'] = hourly['high'].shift(1)
    hourly['Prior_Low'] = hourly['low'].shift(1)
    
    # Filter for US Session Hours (8 to 16)
    # Actually, we need to carefully handle the Timezone.
    # index is US/Eastern.
    
    results = []
    
    # Iterate through target hours (data is large, but limited to US session helps)
    # Let's iterate days for safety
    daily_groups = df.groupby(df.index.date)
    
    target_hours = [8, 9, 10, 11, 12, 13, 14, 15] # 16 is close? Usually up to 15:00-16:00 candle.
    
    for date, day_data in daily_groups:
        if len(day_data) < 100: continue
        
        # Get hourly stats for this day
        # Re-calc locally for precision
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
                
                # Get the 1m data for current hour
                curr_data = day_data.loc[curr_hour_ts : curr_hour_ts + pd.Timedelta(minutes=59)]
                
                if curr_data.empty: continue
                
                # Check for Sweep
                # Sweep High: Price > Prior High
                # Sweep Low: Price < Prior Low
                
                swept_high = False
                swept_low = False
                
                # Find time of sweep
                # First occurrence where High > Prior High
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
                    
                # We analyze ONLY if a sweep happened
                # If both happened? Analyze the FIRST one.
                
                events = []
                if swept_high: events.append((high_sweep_time, 'High', prior_high))
                if swept_low: events.append((low_sweep_time, 'Low', prior_low))
                
                if not events: continue
                
                events.sort(key=lambda x: x[0])
                first_sweep = events[0]
                
                sweep_ts = first_sweep[0]
                sweep_type = first_sweep[1]
                
                # Calculate Segment (0-20, 20-40, 40-60)
                minutes_into_hour = (sweep_ts - curr_hour_ts).seconds // 60
                segment = ""
                if minutes_into_hour < 20: segment = "0-20"
                elif minutes_into_hour < 40: segment = "20-40"
                else: segment = "40-60"
                
                # Check Return to Open
                # Look at data *after* the sweep time
                post_sweep_data = curr_data.loc[sweep_ts:]
                
                # Did price touch Open?
                # If Sweep High, we want Price <= Open
                # If Sweep Low, we want Price >= Open
                
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

            except Exception as e:
                # print(e)
                continue

    results_df = pd.DataFrame(results)
    if results_df.empty: return None
    
    # Aggregation
    summary = []
    
    # Overall
    total = len(results_df)
    wins = results_df['Returned'].sum()
    summary.append({'Metric': 'Overall', 'Count': total, 'WinRate': wins/total})
    
    # By Segment
    for seg in ['0-20', '20-40', '40-60']:
        seg_df = results_df[results_df['Segment'] == seg]
        cnt = len(seg_df)
        if cnt > 0:
            summary.append({'Metric': f'Seg {seg}', 'Count': cnt, 'WinRate': seg_df['Returned'].sum()/cnt})
            
    # By Hour (First 20 mins only per hour - usually the best stats)
    seg1_df = results_df[results_df['Segment'] == '0-20']
    for h in target_hours:
        h_df = seg1_df[seg1_df['Hour'] == h]
        cnt = len(h_df)
        if cnt > 0:
            summary.append({'Metric': f'Hour {h} (Seg 1)', 'Count': cnt, 'WinRate': h_df['Returned'].sum()/cnt})

    return pd.DataFrame(summary).assign(Ticker=ticker)

def main():
    all_summaries = []
    for t in TICKERS:
        print(f"Verifying Hour Stats for {t}...")
        res = verify_hour_stats(t)
        if res is not None:
            all_summaries.append(res)
            print(res.to_string())
            
    if all_summaries:
        final_df = pd.concat(all_summaries)
        final_df.to_csv('scripts/nqstats/results/hour_stats_verification.csv', index=False)
        print("\nSaved to scripts/nqstats/results/hour_stats_verification.csv")

if __name__ == "__main__":
    main()
