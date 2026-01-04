
import pandas as pd
import numpy as np
import os
import argparse
from datetime import time, timedelta

# --- Configuration ---
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

def get_stats_for_period(df, timeframe='1h', first_n_minutes=5, origin='start_day'):
    print(f"Resampling to {timeframe} (Origin: {origin})...")
    
    # 1. Resample
    try:
        if origin == 'start_day':
            period_df = df.resample(timeframe).agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            })
        else:
             # origin can be a string like '06:00'
             # If it is just a time string, we need to make it compatible with the index.
             # Actually, pandas defaults origin to 'start_day' (midnight) locally.
             # If we provide a generic time string, pandas might panic on TZ-aware index.
             # Let's try converting string to a Timestamp on the first day of data.
             if isinstance(origin, str) and ':' in origin:
                  # Construct a timestamp for the first day
                  first_day = df.index[0].date()
                  h, m = map(int, origin.split(':'))
                  # Create naive then localize
                  origin_ts = pd.Timestamp.combine(first_day, time(h, m)).tz_localize('US/Eastern')
                  period_df = df.resample(timeframe, origin=origin_ts).agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                  })
             else:
                  period_df = df.resample(timeframe, origin=origin).agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                  })
    except Exception as e:
        print(f"Resample Error: {e}")
        return pd.DataFrame()

    period_df.dropna(inplace=True)
    
    period_df['Color'] = np.where(period_df['close'] > period_df['open'], 'Green', 'Red')
    period_df['Mid'] = (period_df['high'] + period_df['low']) / 2
    period_df['Range'] = period_df['high'] - period_df['low']
    period_df['Prev_Color'] = period_df['Color'].shift(1)
    
    stats = []
    
    print("Calculating Intra-Period Stats...")
    
    for idx, row in period_df.iterrows():
        start_time = idx
        try:
           # Approximate end time calculation
           # Check for 'h' or 't' or 'min'
           if 'h' in timeframe.lower():
               h = int(timeframe.lower().replace('h',''))
               end_time = start_time + timedelta(hours=h)
           elif 'min' in timeframe.lower() or 't' in timeframe.lower():
               m_str = timeframe.lower().replace('min','').replace('t','')
               m = int(m_str)
               end_time = start_time + timedelta(minutes=m)
           else: 
               # Default fallback 1h
               end_time = start_time + timedelta(hours=1)
        except: continue

        try:
            slice_df = df.loc[start_time:end_time - timedelta(minutes=1)]
        except: continue
        if slice_df.empty: continue
        
        # --- Quarterly Timing ---
        total_mins = len(slice_df)
        q_len = total_mins / 4.0
        
        if q_len == 0: continue
        
        t_high = slice_df['high'].idxmax()
        t_low = slice_df['low'].idxmax()
        
        mins_to_high = (t_high - start_time).total_seconds() / 60
        mins_to_low = (t_low - start_time).total_seconds() / 60
        
        high_quarter = int(mins_to_high // q_len)
        low_quarter = int(mins_to_low // q_len)
        
        high_quarter = min(max(high_quarter, 0), 3)
        low_quarter = min(max(low_quarter, 0), 3)
        
        # --- ORB Analysis ---
        orb_end = start_time + timedelta(minutes=first_n_minutes)
        orb_slice = slice_df.loc[:orb_end - timedelta(minutes=1)]
        
        orb_bias = "Neutral"
        orb_success = False # Predicitng Close Color
        
        if not orb_slice.empty:
            orb_open = orb_slice.iloc[0]['open']
            orb_close = orb_slice.iloc[-1]['close']
            orb_bias = "Bullish" if orb_close > orb_open else "Bearish"
            
            if orb_bias == "Bullish" and row['close'] > row['open']: orb_success = True
            elif orb_bias == "Bearish" and row['close'] < row['open']: orb_success = True
            
        # --- Midpoint Analysis ---
        # 1. Close Strength: Did we close > Mid (Bullish Hold) or < Mid (Bearish Hold)?
        upper_half_close = row['close'] > row['Mid']
        
        # 2. Mid Touch? (If Open was far from Mid)
        # Check if slice crossed Mid. (High >= Mid and Low <= Mid)
        touched_mid = (row['high'] >= row['Mid']) and (row['low'] <= row['Mid']) # Always True by definition of Mid
        
        # Maybe "Reversion to Mean": If Open is High/Low, do we touch Mid? 
        # Actually, Mid is calculated FROM High/Low, so Price MUST touch Mid at some point between H and L. 
        # User defined Mid as "previous hour high, low, mid open and close". 
        # Ah, PREVIOUS Mid? No "midpoints of each hour". 
        # The midpoint of the current range is always touched.
        
        # Let's verify correlation between ORB direction and Closing Half.
        # If ORB Bullish -> Close Upper Half?
        orb_matches_half = False
        if orb_bias == "Bullish" and upper_half_close: orb_matches_half = True
        elif orb_bias == "Bearish" and not upper_half_close: orb_matches_half = True

        stats.append({
            'Datetime': start_time,
            'Hour': start_time.hour,
            'High_Quarter': high_quarter,
            'Low_Quarter': low_quarter,
            'ORB_Bias': orb_bias,
            'ORB_Win': orb_success,
            'ORB_Half_Win': orb_matches_half,
            'Upper_Half_Close': upper_half_close,
            'Prev_Match': (row['Prev_Color'] == row['Color'])
        })
        
    return pd.DataFrame(stats)

def analyze_hour_personalities(stats_df):
    hours = sorted(stats_df['Hour'].unique())
    profile = []
    
    for h in hours:
        # Filter for relevant windows (optional, but good for summary)
        # Keep all available start hours
        
        h_df = stats_df[stats_df['Hour'] == h]
        count = len(h_df)
        if count == 0: continue
        
        h_q_dist = h_df['High_Quarter'].value_counts(normalize=True).sort_index()
        l_q_dist = h_df['Low_Quarter'].value_counts(normalize=True).sort_index()
        
        orb_win = h_df['ORB_Win'].mean()
        orb_half_win = h_df['ORB_Half_Win'].mean() # New Metric
        
        profile.append({
            'Start_Hour': h,
            'Count': count,
            'ORB_5m_Predicts_Color': orb_win,
            'ORB_5m_Predicts_Half': orb_half_win,
            'High_Q1': h_q_dist.get(0, 0),
            'High_Q4': h_q_dist.get(3, 0),
            'Low_Q1': l_q_dist.get(0, 0),
            'Low_Q4': l_q_dist.get(3, 0)
        })
        
    return pd.DataFrame(profile)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker', type=str, help='Ticker symbol (e.g., NQ1)')
    parser.add_argument('--timeframe', type=str, default='1h', help='Timeframe (e.g., 3h, 4h)')
    parser.add_argument('--origin', type=str, default='start_day', help='Resample origin (e.g. 06:00)')
    args = parser.parse_args()
    
    print(f"Analyzing {args.ticker} on {args.timeframe} (Origin: {args.origin})...")
    df = load_data(args.ticker)
    if df is None: return
        
    stats_df = get_stats_for_period(df, timeframe=args.timeframe, origin=args.origin)
    if not stats_df.empty:
        profile = analyze_hour_personalities(stats_df)
        print("\n--- Period Personalities ---")
        print(profile.round(3).to_string(index=False))
        
        # Save
        t_str = args.timeframe
        o_str = args.origin.replace(':','')
        profile.to_csv(f'scripts/nqstats/results/{args.ticker}_{t_str}_{o_str}_stats.csv', index=False)

if __name__ == "__main__":
    main()
