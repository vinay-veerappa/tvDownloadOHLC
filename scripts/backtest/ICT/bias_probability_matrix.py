
import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import timedelta, time

# Define paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(ROOT_DIR, "data")

def load_data(ticker, timeframe):
    path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
    # Fallbacks
    if not os.path.exists(path):
        if timeframe == "1d": path = os.path.join(DATA_DIR, f"{ticker}_1D.parquet")
        if timeframe == "1h": path = os.path.join(DATA_DIR, f"{ticker}_1H.parquet")
        
    if not os.path.exists(path):
        # Create empty if not found? No, critical.
        return pd.DataFrame()
        
    df = pd.read_parquet(path)
    if isinstance(df.index, pd.DatetimeIndex): df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    
    if 'time' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
    elif 'datetime' not in df.columns:
         df.rename(columns={df.columns[0]: 'datetime'}, inplace=True)
         
    # Timezone handling
    if df['datetime'].dt.tz is None:
        # Assume generic, but for alignment with hardcoded times we might need to be careful
        pass
        
    df = df.sort_values('datetime').reset_index(drop=True)
    return df

def find_fvgs(df, tf_label):
    fvgs = []
    # Identify all FVGs historically
    for i in range(2, len(df)):
        dt = df['datetime'].iloc[i]
        # Bullish
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'tf': tf_label,
                'top': df['low'].iloc[i],
                'bottom': df['high'].iloc[i-2],
                'created_at': dt
            })
        # Bearish
        if df['high'].iloc[i] < df['low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'tf': tf_label,
                'top': df['low'].iloc[i-2],
                'bottom': df['high'].iloc[i],
                'created_at': dt
            })
    return fvgs

def get_p12_levels(df_1h, target_date):
    # P12: First 12 Hours (18:00 Prev Day to 06:00 Current Day)
    # Be careful with 18:00 Prev Day logic.
    
    # prev_date = target_date - timedelta(days=1) ? 
    # Not always - weekends.
    # Look for data in window.
    
    # Construct timestamps (Naive or Aware depending on df)
    # Assume dataframe has tz or correct local time.
    
    start_dt = pd.Timestamp.combine(target_date - timedelta(days=1), time(18, 0))
    end_dt = pd.Timestamp.combine(target_date, time(6, 0))
    
    # Localize if needed
    if df_1h['datetime'].dt.tz is not None:
        if start_dt.tzinfo is None:
             start_dt = start_dt.tz_localize(df_1h['datetime'].dt.tz)
             end_dt = end_dt.tz_localize(df_1h['datetime'].dt.tz)
    
    # Window 
    # Use <= end_dt? candle 05:00-06:00 closes at 06:00.
    mask = (df_1h['datetime'] >= start_dt) & (df_1h['datetime'] < end_dt) # End exclusive typically for start time?
    # 1H bars start time?
    # If 18:00 bar exists, it covers 18-19.
    # We want up to 06:00.
    
    p12_data = df_1h[mask]
    
    if p12_data.empty: return None
    
    high = p12_data['high'].max()
    low = p12_data['low'].min()
    mid = (high + low) / 2
    
    return {'P12_High': high, 'P12_Low': low, 'P12_Mid': mid}

def calculate_probability_matrix(ticker):
    print(f"Building Probability Matrix for {ticker}...")
    
    # Load Data
    df_15m = load_data(ticker, "15m")
    df_1h = load_data(ticker, "1h")
    df_4h = load_data(ticker, "4h")
    df_1d = load_data(ticker, "1d")
    
    if df_15m.empty: 
        print("No 15m data.")
        return

    # Filter 2022+
    start_date = pd.Timestamp("2022-01-01")
    if df_15m['datetime'].dt.tz is not None:
        start_date = start_date.tz_localize(df_15m['datetime'].dt.tz)
    
    df_15m = df_15m[df_15m['datetime'] >= start_date].reset_index(drop=True)
    
    # Pre-calculate Daily High/Low from 15m to ensure consistency
    daily_agg = {}
    temp_dates = df_15m['datetime'].dt.date
    unique_dates_all = temp_dates.unique()
    
    for d in unique_dates_all:
         # Filter bars for this day
         mask = temp_dates == d
         day_df = df_15m[mask]
         if not day_df.empty:
             daily_agg[d] = {
                 'high': day_df['high'].max(),
                 'low': day_df['low'].min()
             }

    # Pre-calc FVGs
    fvgs_1d = find_fvgs(df_1d, "1D")
    fvgs_4h = find_fvgs(df_4h, "4H")
    fvgs_1h = find_fvgs(df_1h, "1H") # Maybe too heavy?
    
    # Sort FVGs by time for fast lookup (or filter loop)
    # Optimization: Sort reversed to find recent quickly
    fvgs_1d.sort(key=lambda x: x['created_at'], reverse=True)
    fvgs_4h.sort(key=lambda x: x['created_at'], reverse=True)
    fvgs_1h.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Metrics Storage
    # List of dictionaries, each row is a DAY
    observations = []
    
    unique_dates = df_15m['datetime'].dt.date.unique()
    
    # Time Constants
    t_0930 = time(9, 30)
    t_1200 = time(12, 0) # User Request: Analyze NY AM Session only
    
    for date_obj in unique_dates:
        # Define NY Session (AM)
        ny_start_dt = pd.Timestamp.combine(date_obj, t_0930)
        ny_end_dt = pd.Timestamp.combine(date_obj, t_1200)
        
        # Localize
        if df_15m['datetime'].dt.tz is not None:
             if ny_start_dt.tzinfo is None:
                 ny_start_dt = ny_start_dt.tz_localize(df_15m['datetime'].dt.tz)
                 ny_end_dt = ny_end_dt.tz_localize(df_15m['datetime'].dt.tz)

        # Get NY Price Action (Outcome)
        ny_data = df_15m[(df_15m['datetime'] >= ny_start_dt) & (df_15m['datetime'] <= ny_end_dt)]
        if ny_data.empty: continue
        
        ny_open = ny_data['open'].iloc[0]
        ny_close = ny_data['close'].iloc[-1]
        ny_direction = "Bullish" if ny_close > ny_open else "Bearish"
        
        # --- FEATURE ENGINEERING (Context before 09:30) ---
        
        features = {}
        
        # 1. P12 Analysis
        p12 = get_p12_levels(df_1h, date_obj)
        if p12:
            features['Above_P12_Mid'] = ny_open > p12['P12_Mid']
            features['Above_P12_High'] = ny_open > p12['P12_High']
            features['Below_P12_Low'] = ny_open < p12['P12_Low']
        else:
            features['Above_P12_Mid'] = None
            
        # 2. FVG Context (Where are we at NY Open?)
        # Check active FVGs
        # Helper inner function
        def check_fvg_status(price, fvgs, current_dt):
            # Check recent FVGs based on Time, not List Index
            inside_bull = False
            inside_bear = False
            
            # Optimization: fvgs are sorted Newest -> Oldest
            # Iterate until we find one created before current_dt
            # Then check a window of "recency" (e.g. last 20 days)
            
            count_checked = 0
            for f in fvgs:
                if f['created_at'] >= current_dt: continue # Future FVG (skip)
                
                # If FVG is too old? (Optional, but let's keep all active unmitigated technically)
                # For performance, maybe stop if > 60 days old? 
                if (current_dt - f['created_at']).days > 60: break
                
                count_checked += 1
                
                # Check Overlap
                if f['type'] == 'Bullish':
                     if price <= f['top'] and price >= f['bottom']: inside_bull = True
                if f['type'] == 'Bearish':
                     if price >= f['bottom'] and price <= f['top']: inside_bear = True
                
                if inside_bull or inside_bear: break
                
                # Limit depth of search per timeframe to keep it "Recent" context
                if count_checked > 50: break
                
            return inside_bull, inside_bear

        # Daily FVGs
        in_d_bull, in_d_bear = check_fvg_status(ny_open, fvgs_1d, ny_start_dt)
        features['Inside_Daily_Bull_FVG'] = in_d_bull
        features['Inside_Daily_Bear_FVG'] = in_d_bear
        
        # 4H FVGs
        in_4h_bull, in_4h_bear = check_fvg_status(ny_open, fvgs_4h, ny_start_dt)
        features['Inside_4H_Bull_FVG'] = in_4h_bull
        features['Inside_4H_Bear_FVG'] = in_4h_bear
        
        # 1H FVGs
        in_1h_bull, in_1h_bear = check_fvg_status(ny_open, fvgs_1h, ny_start_dt)
        features['Inside_1H_Bull_FVG'] = in_1h_bull
        features['Inside_1H_Bear_FVG'] = in_1h_bear
        
        # 3. Liquidity Sweeps
        # Did Pre-Market (00:00 - 09:30) sweep yesterday's levels?
        
        # Determine Prev Day High/Low from 15m Data (Self-Sufficient)
        # Find 15m data for the previous date
        # Assuming date_obj is consecutive, look back 1-3 days
        
        # Optimization: Build a daily lookup dict once at start
        # Use existing `observations`? No, that's forward pass.
        # Do it once before loop.
        
        # Placeholder for lookup (implemented below, outside loop)
        prev_date_lookup = date_obj - timedelta(days=1)
        
        pdh = None; pdl = None
        # Try finding previous trading day (look back 5 days max)
        for d in range(1, 5):
            lookback = date_obj - timedelta(days=d)
            if lookback in daily_agg:
                pdh = daily_agg[lookback]['high']
                pdl = daily_agg[lookback]['low']
                break
                
        # London Session Calculation (02:00 - 05:00 ET) for CURRENT Day
        # We need data for 02:00-05:00 today.
        
        london_start = pd.Timestamp.combine(date_obj, time(2, 0))
        london_end = pd.Timestamp.combine(date_obj, time(5, 0))
        # Localization
        if df_15m['datetime'].dt.tz is not None and london_start.tzinfo is None:
             london_start = london_start.tz_localize(df_15m['datetime'].dt.tz)
             london_end = london_end.tz_localize(df_15m['datetime'].dt.tz)
             
        london_data = df_15m[(df_15m['datetime'] >= london_start) & (df_15m['datetime'] < london_end)]
        london_high = None; london_low = None
        if not london_data.empty:
            london_high = london_data['high'].max()
            london_low = london_data['low'].min()
                
        # Get Pre-Market Data (00:00 to 09:30)
        day_start_dt = pd.Timestamp.combine(date_obj, time(0,0))
        if df_15m['datetime'].dt.tz is not None and day_start_dt.tzinfo is None:
            day_start_dt = day_start_dt.tz_localize(df_15m['datetime'].dt.tz)
            
        pre_market = df_15m[(df_15m['datetime'] >= day_start_dt) & (df_15m['datetime'] < ny_start_dt)]
        
        if not pre_market.empty:
            pm_high = pre_market['high'].max()
            pm_low = pre_market['low'].min()
            
            # PDH/PDL Sweep
            if pdh is not None:
                features['Swept_PDH'] = pm_high > pdh
                features['Swept_PDL'] = pm_low < pdl
            else:
                features['Swept_PDH'] = False
                features['Swept_PDL'] = False
                
            # London Sweep (Pre-Market vs NY Session)
            if london_high is not None:
                # PM Sweep (05:00 - 09:30)
                post_london_pm = pre_market[pre_market['datetime'] >= london_end]
                if not post_london_pm.empty:
                    features['Swept_London_High_PM'] = post_london_pm['high'].max() > london_high
                    features['Swept_London_Low_PM'] = post_london_pm['low'].min() < london_low
                else:
                    features['Swept_London_High_PM'] = False
                    features['Swept_London_Low_PM'] = False
                    
                # NY Sweep (09:30 - 16:00)
                if not ny_data.empty:
                    ny_high = ny_data['high'].max()
                    ny_low = ny_data['low'].min()
                    features['Swept_London_High_NY'] = ny_high > london_high
                    features['Swept_London_Low_NY'] = ny_low < london_low
                else:
                    features['Swept_London_High_NY'] = False
                    features['Swept_London_Low_NY'] = False
            else:
                features['Swept_London_High_PM'] = False
                features['Swept_London_Low_PM'] = False
                features['Swept_London_High_NY'] = False
                features['Swept_London_Low_NY'] = False

        # 4. Key Open Levels (Midnight, 07:30, Globex)
        # Midnight (00:00)
        midnight_dt = pd.Timestamp.combine(date_obj, time(0, 0))
        if df_15m['datetime'].dt.tz is not None and midnight_dt.tzinfo is None:
            midnight_dt = midnight_dt.tz_localize(df_15m['datetime'].dt.tz)
        
        # 07:30
        open_0730_dt = pd.Timestamp.combine(date_obj, time(7, 30))
        if df_15m['datetime'].dt.tz is not None and open_0730_dt.tzinfo is None:
            open_0730_dt = open_0730_dt.tz_localize(df_15m['datetime'].dt.tz)
            
        # Globex (18:00 Prev Day)
        # Use simple logic: 18:00 yesterday
        globex_dt = pd.Timestamp.combine(date_obj - timedelta(days=1), time(18, 0))
        if df_15m['datetime'].dt.tz is not None and globex_dt.tzinfo is None:
            globex_dt = globex_dt.tz_localize(df_15m['datetime'].dt.tz)
            
        # Get Prices for these times
        # Helper to find exact or nearest price
        def get_price_at(dt, df_source):
             # Exact match
             match = df_source[df_source['datetime'] == dt]
             if not match.empty: return match['open'].iloc[0]
             # Nearest before?
             # If exact minute missing, take the open of the bar covering it
             # OR nearest after
             return None # simplified
             
        # Optimized: We already sliced df_15m or can slice small window
        # Get 00:00 Open
        midnight_open = None
        mo_row = df_15m[df_15m['datetime'] == midnight_dt]
        if not mo_row.empty: midnight_open = mo_row['open'].iloc[0]
        
        # Get 07:30 Open
        open_0730 = None
        o730_row = df_15m[df_15m['datetime'] == open_0730_dt]
        if not o730_row.empty: open_0730 = o730_row['open'].iloc[0]
        
        # Get Globex Open (might need 1d or check 15m prev day)
        globex_open = None
        go_row = df_1h[df_1h['datetime'] == globex_dt] # Use 1H for 18:00
        if not go_row.empty: globex_open = go_row['open'].iloc[0]
        
        # Weekly Close
        # Find last Friday close. Expensive to search every time?
        # Use a simple approximation: Close of 2 days ago? No.
        # Use pandas resample ('W-FRI') on 1D data then shift?
        # Let's do a quick lookup on df_1d
        weekly_close = None
        # Go back day by day until we hit a Friday (weekday=4)
        for d in range(1, 10):
            past_date = date_obj - timedelta(days=d)
            if past_date.weekday() == 4: # Friday
                # Find this date in daily_agg or df_1d
                # daily_agg has high/low, we need close.
                # Look in df_1d
                mask = df_1d['datetime'].dt.date == past_date
                if mask.any():
                    weekly_close = df_1d[mask].iloc[-1]['close']
                break
        
        # Feature Logic: Above/Below at NY Open (09:30)
        # This determines "Trend" relative to open.
        if midnight_open:
            features['Above_Midnight_Open'] = ny_open > midnight_open
            features['Below_Midnight_Open'] = ny_open < midnight_open
            
        if open_0730:
            features['Above_0730_Open'] = ny_open > open_0730
            features['Below_0730_Open'] = ny_open < open_0730
            
        if globex_open:
            features['Above_Globex_Open'] = ny_open > globex_open
            features['Below_Globex_Open'] = ny_open < globex_open
            
        if weekly_close:
            features['Above_Weekly_Close'] = ny_open > weekly_close
            features['Below_Weekly_Close'] = ny_open < weekly_close

        # Record Observation
        obs = features
        obs['Outcome'] = ny_direction
        obs['Date'] = date_obj
        observations.append(obs)
        
    # --- PROBABILITY CALCULATION (COMBINATIONS) ---
    df_obs = pd.DataFrame(observations)
    if df_obs.empty:
        print("No observations.")
        return
        
    # --- PROBABILITY CALCULATION (REVERSAL COMBINATIONS) ---
    df_obs = pd.DataFrame(observations)
    if df_obs.empty:
        print("No observations.")
        return
        
    print("\nReversal Probability Matrix (FVG + Level Confluence):")
    
    base_features = [c for c in df_obs.columns if c not in ['Outcome', 'Date']]
    
    # Separate into Categories
    fvg_bull = [f for f in base_features if "Bull_FVG" in f]
    fvg_bear = [f for f in base_features if "Bear_FVG" in f]
    
    levels_low = [f for f in base_features if any(x in f for x in ["Below", "Swept_PDL", "Swept_London_Low"])]
    levels_high = [f for f in base_features if any(x in f for x in ["Above", "Swept_PDH", "Swept_London_High"])]
    
    results = []
    
    # 1. Bullish Reversals (Bull FVG + Low Context)
    import itertools
    
    # Iterate Bull FVGs vs Low Levels
    for fvg in fvg_bull:
        for lvl in levels_low:
            # Check Combo
            mask = (df_obs[fvg] == True) & (df_obs[lvl] == True)
            subset = df_obs[mask]
            count = len(subset)
            if count < 10: continue
            
            bull_wins = len(subset[subset['Outcome'] == 'Bullish'])
            rev_prob = (bull_wins / count) * 100
            
            results.append({
                "Setup": f"{fvg} + {lvl}",
                "Type": "Bullish Reversal",
                "Count": count,
                "Prob": rev_prob
            })
            
    # 2. Bearish Reversals (Bear FVG + High Context)
    for fvg in fvg_bear:
        for lvl in levels_high:
            # Check Combo
            mask = (df_obs[fvg] == True) & (df_obs[lvl] == True)
            subset = df_obs[mask]
            count = len(subset)
            if count < 10: continue
            
            bear_wins = len(subset[subset['Outcome'] == 'Bearish'])
            rev_prob = (bear_wins / count) * 100
            
            results.append({
                "Setup": f"{fvg} + {lvl}",
                "Type": "Bearish Reversal",
                "Count": count,
                "Prob": rev_prob
            })
            
    # Sort by Probability
    results.sort(key=lambda x: x['Prob'], reverse=True)
    
    print(f"{'Setup':<70} | {'Type':<18} | {'Count':<6} | {'Win Rate'}")
    print("-" * 110)
    for r in results[:50]:
        print(f"{r['Setup']:<70} | {r['Type']:<18} | {r['Count']:<6} | {r['Prob']:.1f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="NQ1", help="Ticker")
    args = parser.parse_args()
    calculate_probability_matrix(args.ticker)
