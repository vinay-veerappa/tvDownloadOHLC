
import pandas as pd
import numpy as np
import json
import os

def analyze_all_magnets(ticker="NQ1", output_path=None):
    print(f"--- Starting Expanded Magnet Analysis for {ticker} ---")
    
    # 1. Load Data
    base_dir = "c:/Users/vinay/tvDownloadOHLC/data"
    parquet_path = f"{base_dir}/{ticker}_1m.parquet"
    sessions_path = f"{base_dir}/sessions/{ticker}_sessions.json"
    
    print("Loading 1m Data...")
    df_1m = pd.read_parquet(parquet_path)
    
    # Timezone Handling
    if not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m.index = pd.to_datetime(df_1m['datetime'])
    try:
        df_1m.index = df_1m.index.tz_localize('UTC').tz_convert('US/Eastern')
    except TypeError:
        df_1m.index = df_1m.index.tz_convert('US/Eastern')
    
    df_1m['date'] = df_1m.index.date
    df_1m['mod'] = df_1m.index.hour * 60 + df_1m.index.minute
    
    # 2. Derive Key Levels
    print("Pre-computing Historical Levels (PDH/L, PWH/L)...")
    
    # Daily Aggregation (RTH + Overnight included? Usually Daily Levels refer to Full Session)
    # Let's use Full Daily Candle (00:00 - 23:59) for PDH/PDL/PDC
    daily = df_1m.groupby('date').agg({
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    # Shift to get Previous Values
    daily['PDH'] = daily['high'].shift(1)
    daily['PDL'] = daily['low'].shift(1)
    daily['PDC'] = daily['close'].shift(1) # Gap Fill Level
    
    # Weekly Aggregation
    daily.index = pd.to_datetime(daily.index)
    weekly = daily.resample('W-FRI').agg({
        'high': 'max',
        'low': 'min'
    })
    # Shift Logic: For any day in Week X, PWH is High of Week X-1
    weekly['PWH'] = weekly['high'].shift(1)
    weekly['PWL'] = weekly['low'].shift(1)
    weekly['PW_Mid'] = (weekly['PWH'] + weekly['PWL']) / 2
    
    # Map back to Daily
    daily_weekly = hourly_merge(daily, weekly)
    
    # Merge Levels into main Daily DataFrame
    levels_df = daily_weekly[['PDH', 'PDL', 'PDC', 'PWH', 'PWL', 'PW_Mid']].copy()
    levels_df['PD_Mid'] = (levels_df['PDH'] + levels_df['PDL']) / 2
    levels_df.index = levels_df.index.date
    
    
    # Load Session Data (Moved up for use here)
    with open(sessions_path, 'r') as f:
        sess_data = json.load(f)
    df_sess = pd.DataFrame(sess_data)
    # Fix: JSON uses 'start_time', not 'start_ts'
    if 'start_time' in df_sess.columns:
        df_sess['start_time'] = pd.to_datetime(df_sess['start_time'], format='mixed', utc=True)
        df_sess = df_sess.sort_values('start_time')
    
    # 4. Load Session Levels (London/Asia)
    # Pivot to get access to all session prices by date
    # We need 'GlobexOpen' specifically for NDOG
    pivoted = df_sess.pivot_table(index='date', columns='session', values=['high', 'low', 'price', 'mid'], aggfunc='first')
    pivoted.columns = [f"{c[0]}_{c[1]}" for c in pivoted.columns]
    pivoted.index = pd.to_datetime(pivoted.index).date
    
    # NDOG/NWOG Logic Refined
    print("Calculating NDOG and NWOG details...")
    
    # NDOG = Range(Prior Day Close, Current Globex Open)
    # Using 'PDC' from daily levels and 'price_GlobexOpen' from session data
    # Align indices
    common_idx = levels_df.index.intersection(pivoted.index)
    
    ndog_series = pd.Series(index=levels_df.index, dtype=float)
    
    if 'price_GlobexOpen' in pivoted.columns:
        # Calculate NDOG Mid
        # Ensure numeric type
        pdc = levels_df['PDC']
        g_open = pivoted['price_GlobexOpen']
        
        # We need to match dates. 
        # Note: 'PDC' for date X is Close of Day X-1.
        # 'GlobexOpen' for date X is Open of Day X (starts prev evening).
        # So for Trade Date X, NDOG is between PDC(X) and GlobexOpen(X).
        # This seems correct for "Opening Gap" of the current day.
        
        ndog_series = (pdc + g_open) / 2
    else:
        print("Warning: 'price_GlobexOpen' not found in session data. NDOG will be NaN.")

    # NWOG: The NDOG of the first trading day of the week (Monday)
    # We take the NDOG series, filter for Mondays (or first available), and ffill for the week.
    # Convert index to datetime for resampling
    ndog_dt = ndog_series.copy()
    ndog_dt.index = pd.to_datetime(ndog_dt.index)
    
    # Resample W-MON (Weekly starting Monday)
    # Take the 'first' value of the week
    nwog_weekly = ndog_dt.resample('W-MON').first()
    
    # Reindex back to daily to broadcast
    nwog_daily = nwog_weekly.reindex(pd.to_datetime(levels_df.index), method='ffill')
    nwog_daily.index = nwog_daily.index.date
    
    # 3. Identify AM Reversals (Same logic as before)
    print("Identifying AM Reversals...")
    
    rth_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 960)
    filtered_rth = df_1m[rth_mask]
    if filtered_rth.empty:
        print("No RTH data found.")
        return

    daily_rth = filtered_rth.groupby('date').agg({'open':'first', 'close':'last'})
    daily_rth['Color'] = np.where(daily_rth['close'] > daily_rth['open'], 'Green', 'Red')
    
    # Finding Extremes
    am_mask = (df_1m['mod'] >= 570) & (df_1m['mod'] < 720) # 09:30 - 12:00
    am_data = df_1m[am_mask].copy()
    
    am_lows = am_data.groupby('date')['low'].agg(['min', 'idxmin'])
    am_lows.columns = ['AM_Low', 'AM_Low_Time']
    
    am_highs = am_data.groupby('date')['high'].agg(['max', 'idxmax'])
    am_highs.columns = ['AM_High', 'AM_High_Time']
    
    # 4. Load Session Levels (London/Asia)
    pivoted = df_sess.pivot_table(index='date', columns='session', values=['high', 'low', 'price', 'mid'], aggfunc='first')
    pivoted.columns = [f"{c[0]}_{c[1]}" for c in pivoted.columns]
    pivoted.index = pd.to_datetime(pivoted.index).date
    
    # Midnight Open
    midnight_mask = (df_1m.index.hour == 0) & (df_1m.index.minute == 0)
    midnight_opens = df_1m[midnight_mask].groupby('date')['open'].first().rename("Midnight_Open")
    
    # 5. Master Merge
    
    reversal_events = []
    
    print("analyzing Confluences...")
    
    for date, row in daily_rth.iterrows():
        # Get AM Extreme Price & Time
        event_time = None
        if row['Color'] == 'Green':
            if date not in am_lows.index: continue
            event_price = am_lows.loc[date, 'AM_Low']
            event_time = am_lows.loc[date, 'AM_Low_Time']
            reversal_type = "AM Low (Green Day)"
        else:
            if date not in am_highs.index: continue
            event_price = am_highs.loc[date, 'AM_High']
            event_time = am_highs.loc[date, 'AM_High_Time']
            reversal_type = "AM High (Red Day)"
            
        # Basic Fetches
        if date not in levels_df.index: continue
        d_lev = levels_df.loc[date]
        
        s_lev = pivoted.loc[date] if date in pivoted.index else pd.Series()
        mid_open = midnight_opens.loc[date] if date in midnight_opens.index else np.nan
        
        # --- NEW CALCULATIONS ---
        
        # 1. Gap Percentiles (RTH Gap)
        
        rth_open = row['open']
        prev_close = d_lev['PDC']
        
        # Gap is between PDC (Prior Daily Close - usually RTH close) and Today Open (RTH Open)
        # row['open'] is RTH Open. d_lev['PDC'] is Prior Close.
        # Note: 'daily' agg was 00:00-23:59. So PDC is "Close of electronic session".
        # User defined Gap Fill = Prior Close. 
        # "Gap 50%" usually means RTH Gap. 
        # Gap = (RTH Open - Prior RTH Close). We don't have Prior RTH Close easily here (d_lev is full day).
        # Estimation: Use d_lev['PDC'] as proxy.
        
        gap_mid = np.nan
        gap_25 = np.nan
        
        if pd.notna(rth_open) and pd.notna(prev_close):
            gap_mid = (rth_open + prev_close) / 2
            # 25% from Close to Open? Or Open to Close? 
            # Usually strict numbers: 0.25 * Gap + Min(Open, Close)
            gap_range = abs(rth_open - prev_close)
            if gap_range > 0:
                lower = min(rth_open, prev_close)
                gap_25 = lower + (0.25 * gap_range)
        
        # 2. Time-Based Opens (1H, 4H)
        # Find 1H Open: Open of the hour containing event_time? No, "Open of the PREVIOUS hour" often used as support.
        # Or simply: The Open of the Hour candle `event_time` falls into.
        # Example: Reversal at 09:45. 1H Open = 09:00 Open. 4H Open = 06:00 Open (or 10:00 Open if >10).
        # Let's normalize 1H to standard top-of-hour.
        
        open_1h = np.nan
        open_4h = np.nan
        
        if event_time is not None:
            # 1H Open
            # Construct timestamp: Date + Hour + 00:00
            t1h = event_time.replace(minute=0, second=0, microsecond=0)
            # Fetch price
            # Need to query 1m df again...
            # Optimization: Use global lookup?
            # Or just filter small slice
            try:
                # 1 Minute slice at t1h
                slice_1h = df_1m.loc[t1h : t1h + pd.Timedelta(minutes=1)]
                if not slice_1h.empty:
                    open_1h = slice_1h['open'].iloc[0]
                    
                # 4H Open
                # Standard buckets: 02, 06, 10, 14, 18, 22
                h = event_time.hour
                # Find bucket
                buckets = [2, 6, 10, 14, 18, 22]
                # Filter buckets <= h
                past_buckets = [b for b in buckets if b <= h]
                if not past_buckets: 
                     # Previous day 22? Handle edge case or ignore
                     target_h = 22 # simple fallback
                else:
                    target_h = past_buckets[-1]
                
                t4h = event_time.replace(hour=target_h, minute=0, second=0)
                slice_4h = df_1m.loc[t4h : t4h + pd.Timedelta(minutes=1)]
                if not slice_4h.empty:
                    open_4h = slice_4h['open'].iloc[0]
            except:
                pass

        # 3. Rolling 12H Mid (P12 Approximation)
        p12_mid = np.nan
        if event_time is not None:
            start_window = event_time - pd.Timedelta(hours=12)
            try:
                window_slice = df_1m.loc[start_window:event_time]
                if not window_slice.empty:
                    p12_mid = (window_slice['high'].max() + window_slice['low'].min()) / 2
            except:
                pass

        # Build Magnets
        magnets = {
            '07:30 Open': s_lev.get('price_Open730', np.nan),
            'Midnight Open': mid_open,
            'Asia Mid': s_lev.get('mid_Asia', np.nan),
            'PDH': d_lev['PDH'],
            'PDL': d_lev['PDL'],
            'PD Mid': d_lev['PD_Mid'],
            'Gap Fill (PDC)': d_lev['PDC'],
            'Gap 50%': gap_mid,
            'Gap 25%': gap_25,
            'PWH': d_lev['PWH'],
            'PWL': d_lev['PWL'],
            'PW Mid': d_lev['PW_Mid'],
            'London High': s_lev.get('high_London', np.nan),
            'London Low': s_lev.get('low_London', np.nan),
            '12H Mid': p12_mid,
            'NDOG': ndog_series.get(date, np.nan),
            'NWOG': nwog_daily.get(date, np.nan),
            '1H Open': open_1h,
            '4H Open': open_4h
        }
        
        # Add Round Numbers (Dynamic)
        # Check nearest 100 and nearest 50
        nearest_100 = round(event_price / 100) * 100
        nearest_50 = round(event_price / 50) * 50
        
        # Only add if very close prevents pollution, but effectively we check distance anyway
        magnets['Round 100'] = nearest_100
        magnets['Round 50'] = nearest_50
        
        # Find Closest
        best_magnet = "None"
        min_dist = 999
        
        for name, price in magnets.items():
            if pd.isna(price): continue
            
            # Distance as percentage
            dist_pct = abs(event_price - price) / price * 100
            
            if dist_pct < min_dist:
                min_dist = dist_pct
                best_magnet = name
                
        # Threshold: 0.1% (Standard "Touch" definition)
        hit = (min_dist <= 0.10)
        
        reversal_events.append({
            'Date': date,
            'Type': reversal_type,
            'Price': event_price,
            'Closest Magnet': best_magnet if hit else "Random/Unexplained",
            'Dist %': min_dist if hit else None
        })
        
    res = pd.DataFrame(reversal_events)
    
    # 6. Report
    lines = []
    lines.append(f"# {ticker} Expanded Reversal Analysis (n={len(res)})")
    
    counts = res['Closest Magnet'].value_counts(normalize=True) * 100
    lines.append("\n### Reversal Drivers (What caused the turn?)")
    lines.append("| Magnet | Probability (%) |")
    lines.append("| :--- | :--- |")
    for idx, val in counts.items():
        lines.append(f"| {idx} | {val:.1f}% |")
    
    # Grouping categories
    # Sessions: 07:30, Midnight, Asia Mid, London H/L
    # Daily: PDH, PDL, Gap Fill
    # Weekly: PWH, PWL
    
    def categorize(m):
        if m in ['07:30 Open', 'Midnight Open', 'Asia Mid', 'London High', 'London Low']: return 'Session Levels'
        if m in ['PDH', 'PDL', 'Gap Fill (PDC)', 'PD Mid']: return 'Prior Day Levels'
        if m in ['PWH', 'PWL', 'PW Mid']: return 'Weekly Levels'
        if m in ['1H Open', '4H Open', '12H Mid']: return 'Time Structures'
        if m in ['NDOG', 'NWOG', 'Gap 25%', 'Gap 50%']: return 'Gap Mechanics'
        if 'Round' in m: return 'Round Numbers'
        return 'Unexplained'
        
    res['Category'] = res['Closest Magnet'].apply(categorize)
    cat_counts = res['Category'].value_counts(normalize=True) * 100
    
    lines.append("\n### Driver Categories")
    lines.append("| Category | Probability (%) |")
    lines.append("| :--- | :--- |")
    for idx, val in cat_counts.items():
        lines.append(f"| {idx} | {val:.1f}% |")
        
    report = "\n".join(lines)
    print(report)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {output_path}")

def hourly_merge(daily, weekly):
    # Backward fill weekly into daily?
    # Week ending Friday 2024-01-12.
    # Mon 2024-01-15 starts New Week.
    # We want: On Mon Jan 15, PWH = High of Week ending Jan 12.
    # The 'weekly' df index is Fridays.
    # We can perform an asof merge or forward fill.
    
    # Reindex weekly to daily range and ffill
    full_idx = daily.index
    weekly_reindexed = weekly.reindex(full_idx, method='ffill')
    
    # Merge
    return daily.join(weekly_reindexed, rsuffix='_W')

import sys

if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "NQ1"
    output_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    analyze_all_magnets(ticker_arg, output_arg)
