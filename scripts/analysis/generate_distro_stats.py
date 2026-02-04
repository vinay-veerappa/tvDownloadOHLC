import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import argparse

# Configuration
DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"
OUTPUT_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\derived"
TICKER = "-NQ" # Live storage uses -NQ
LOOKBACK_SAMPLES = 16 

SESSION_DEFS = {
    "ASIA": {"start": "18:00", "end": "02:30"},
    "LONDON": {"start": "02:30", "end": "07:30"}, 
    "NY1": {"start": "07:30", "end": "11:30"},
    "NY2": {"start": "11:30", "end": "17:00"},
    "0930": {"start": "09:30", "end": "09:31"}, # 1m
    "0930-1000": {"start": "09:30", "end": "10:00"} # 30m
}

def load_data(ticker):
    # Adjust for live storage naming convention 'live_storage_{ticker}.parquet'
    path = os.path.join(DATA_DIR, f"live_storage_{ticker}.parquet")
    if not os.path.exists(path):
        # Fallback to NQ1 if -NQ fails or vice versa? 
        # User script uses NQ1 usually but live is -NQ.
        path = os.path.join(DATA_DIR, f"live_storage_-NQ.parquet") # Force for now
    
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return None
    
    df = pd.read_parquet(path)
    # The parquet file already has datetime index
    if 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df = df.set_index('datetime')
    # If index is not datetime, try to convert it? usually parquet stores index correctly.
    # Assuming index is already datetime based on debug output.
    
    # Ensure TZ is standard (US/Eastern)
    if df.index.tz is None:
         # Assume UTC if naive, or just localize? 
         # Debug output showed '2006-01-05 13:55:00' - could be naive.
         # Let's assume input is already localized or UTC.
         # If data is from TV download, it might be UTC.
         df.index = df.index.tz_localize('UTC')
         
    df.index = df.index.tz_convert('US/Eastern')
    return df.sort_index()

def calculate_medians(metrics_list):
    if not metrics_list:
        return {"range": 0, "pct": 0, "count": 0}
    
    ranges = [m['range'] for m in metrics_list]
    pcts = [m['pct'] for m in metrics_list]
    
    return {
        "range": float(np.median(ranges)),
        "pct": float(np.median(pcts)),
        "count": len(ranges)
    }

def process_ticker(ticker):
    print(f"Processing {ticker}...")
    df = load_data(ticker)
    if df is None:
        return

    # 1. Calculate Daily Stats (Global) using Trading Date (18:00 split)
    # Define Trading Day: 18:00 Prev Day to 17:59 Curr Day
    # We assign each row a 'trading_date'
    
    # Helper for trading date
    # If hour >= 18, it belongs to next day
    def get_trading_date(ts):
        if ts.hour >= 18:
            return (ts + timedelta(days=1)).date()
        return ts.date()
        
    # Create copy for manipulation
    df_daily = df.copy()
    
    # Vectorized trading date assignment is harder with map, but loop is slow?
    # Index is DatetimeIndex US/Eastern
    # Use pandas vectorization:
    # shift -6 hours? 18:00 -> 12:00. No.
    # Add 6 hours? 18:00 + 6h = 00:00 (Next Day). 
    # 17:59 + 6h = 23:59 (Current Day).
    # Yes! shifting +6h makes 18:00 the start of the next day in date terms.
    
    trading_dates = df_daily.index + timedelta(hours=6)
    df_daily['trading_date'] = trading_dates.date
    
    # Group by trading_date
    grouped = df_daily.groupby('trading_date')
    daily_aggs = grouped.agg(
        open=('open', 'first'),
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
        count=('close', 'count')
    )
    
    # Filter incomplete days? (e.g. weekends might have small count)
    # For now, just calc range
    daily_aggs['range'] = daily_aggs['high'] - daily_aggs['low']
    daily_aggs['pct'] = (daily_aggs['range'] / daily_aggs['open']) * 100
    daily_aggs.index = pd.to_datetime(daily_aggs.index)
    
    # Sort
    daily_aggs = daily_aggs.sort_index()
    
    # Global 10-Day Median
    # Use LAST 10 Completed Days. Exclude Today (last row).
    # Assuming the last row is "Today" (incomplete)
    last_10 = daily_aggs.iloc[-11:-1] 
    
    global_median_range = float(last_10['range'].median())
    
    # Today's Current Daily Stats
    today = daily_aggs.iloc[-1]
    today_stats = {
        "range": float(today['range']),
        "pct": float(today['pct'])
    }

    # 2. Session Analysis
    # We need to iterate sessions. 
    # For efficiency, we can iterate days and extract sessions.
    
    # Filter last year for processing
    # Ensure start_date is timezone aware to match df.index
    start_date = df.index[-1] - timedelta(days=365)
    df_year = df[df.index >= start_date] # Restored df_year
    
    # df.index is US/Eastern (tz-aware)
    # daily_aggs.index works with naive dates for grouping
    
    # Fix: Convert start_date to naive for comparison with daily_aggs (which uses dates)
    start_date_naive = start_date.replace(tzinfo=None)
    
    session_history = {k: {d: [] for d in range(7)} for k in SESSION_DEFS.keys()}
    current_session_stats = {}

    # Gather data
    # Use key dates from the daily_aggs (Trading Dates)
    # daily_aggs.index is datetime (representing the date, time=00:00)
    # We compare with start_date_naive
    dates = daily_aggs[daily_aggs.index >= start_date_naive].index
    
    # Get Timezone from df
    tz_info = df.index.tz
    
    for date in dates:
        date_str = date.strftime('%Y-%m-%d')
        dow = date.dayofweek # 0=Mon, 6=Sun
        
        for sess_name, times in SESSION_DEFS.items():
            # Construct Naive then Localize
            start_naive = datetime.strptime(f"{date_str} {times['start']}", "%Y-%m-%d %H:%M")
            end_naive = datetime.strptime(f"{date_str} {times['end']}", "%Y-%m-%d %H:%M")
            
            # Apply offsets if needed (e.g. Asia starts day before)
            # Actually, our dates are "Trading Dates".
            # Asia (18:00 - 02:30) belongs to "Next Day" trading wise? 
            # In 'profiler_service.py', Asia starts 18:00 on (Date - 1).
            # If 'date' is the Trading Date (e.g. Wed), Asia is Tue 18:00.
            # 18:00 > EndTime(02:30). So Start is Date-1.
            
            # Let's check logic:
            # If simple parse: Wed 18:00 -> Wed 02:00. End < Start. End += 1 day -> Thu 02:00.
            # But Asia is Tue 18:00 -> Wed 02:30.
            # So if we are processing "Wed", we want Tue 18:00.
            
            # Standard logic: 
            # If Start Hour >= 18: Start is Date - 1. (18:00 Tue)
            # End is... Date? (02:30 Wed).
            
            # Or use the generic crossover check:
            # Parse as Current Date first.
            # If End < Start: End += 1 day.
            # NOW check if this window matches the "Trading Date" concept.
            # "Trading Date" means valid session for that day.
            
            # Revert to V2 Logic from profiler_service (implied):
            # Asia: Start 18:00 (-1 Day). End 02:30.
            # London: Start 02:30. End 07:30.
            # NY: Start 07:30.
            
            s_dt = start_naive
            e_dt = end_naive
            
            s_hour = int(times['start'].split(':')[0])
            if s_hour >= 18:
                s_dt -= timedelta(days=1)
                # If e_dt was parsed as Same Day, and s_dt moved back, e_dt might be correct (02:30 Same Day)
                # But wait, original logic was: parse both on same day. If end < start, end += 1.
                # If we move start back, we must check end.
                
                # Let's reset:
                # Target: Asia = Tue 18:00 to Wed 02:30.
                # If date=Wed.
                # start_naive = Wed 18:00. end_naive = Wed 02:30.
                # We want Tue 18:00.
                s_dt = start_naive - timedelta(days=1)
                # We want Wed 02:30.
                e_dt = end_naive # Already Wed 02:30
                
            else:
                # London/NY (02:30, 07:30...)
                # Start on Date.
                # If End < Start (e.g. 23:00 to 02:00 next)? No, these are intraday.
                # end_naive is correct.
                if e_dt < s_dt:
                    e_dt += timedelta(days=1)

            # Localize
            start_time = pd.Timestamp(s_dt).tz_localize(tz_info)
            end_time = pd.Timestamp(e_dt).tz_localize(tz_info)
                
            mask = (df_year.index >= start_time) & (df_year.index < end_time)
            sess_data = df_year[mask]
            
            if not sess_data.empty:
                s_open = sess_data.iloc[0]['open']
                s_high = sess_data['high'].max()
                s_low = sess_data['low'].min()
                s_range = s_high - s_low
                s_pct = (s_range / s_open) * 100
                
                metric = {"range": s_range, "pct": s_pct, "date": date_str}
                
                # Check if this is the "Current" (last available) session for this type
                # We overwrite so the last one remains
                current_session_stats[sess_name] = metric
                
                # Add to history (excluding current day if incomplete? Distro usually implies completed sessions history)
                # Let's include all for now, filter later
                session_history[sess_name][dow].append(metric)

    # 3. Calculate Derived Metrics (Medians of last N matches)
    derived_data = {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "globalMedianRange": global_median_range,
        "today": today_stats,
        "sessions": {}
    }

    dow_names = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

    for sess_name in SESSION_DEFS.keys():
        row_data = {
            "label": sess_name, # or map to display label
            "current": current_session_stats.get(sess_name),
            "history": {}
        }
        
        # Calculate medians for each DOW based on last N samples
        for dow_idx in range(5): # Mon-Fri
            dow_name = dow_names[dow_idx]
            history = session_history[sess_name][dow_idx]
            
            # Exclude the very last one if it matches "today" to avoid self-bias? 
            # User wants "look back", typically excludes current developing session.
            # Assuming 'current_session_stats' holds the developing/last one.
            # Let's verify dates.
            
            valid_history = history
            if current_session_stats.get(sess_name):
                curr_date = current_session_stats[sess_name]['date']
                valid_history = [h for h in history if h['date'] != curr_date]
            
            # Take last N
            recent_N = valid_history[-LOOKBACK_SAMPLES:]
            
            row_data["history"][dow_name] = calculate_medians(recent_N)
            
        derived_data["sessions"][sess_name] = row_data

    # Output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"distro_stats_{ticker}.json")
    with open(out_path, 'w') as f:
        json.dump(derived_data, f, indent=2)
    
    print(f"Saved stats to {out_path}")
    
    # Print Verification Table
    print("\n--- Distro Verification (Last 16 samples) ---")
    print(f"Global 10-Day Median: {global_median_range:.2f}")
    print(f"Today Daily: {today_stats['range']:.2f} ({today_stats['pct']:.2f}%)")
    print("\nSession | Today | MON Median (N) | TUE Median (N) ...")
    
    for sess_name, data in derived_data["sessions"].items():
        curr = data.get("current")
        curr_str = f"{curr['range']:.2f} ({curr['pct']:.2f}%)" if curr else "N/A"
        
        h_strs = []
        for day in ['MON', 'TUE', 'WED', 'THU', 'FRI']:
            h = data['history'][day]
            h_strs.append(f"{h['range']:.2f} ({h['pct']:.2f}%) [{h['count']}]")
            
        print(f"{sess_name:<8} | {curr_str:<16} | {' | '.join(h_strs)}")

    # Detailed Verification Output (matches --verify implied intent)
    print("\n--- Detailed Audit: Global 10-Day Median ---")
    print("Dates used (Last 10 completed days):")
    for idx, row in last_10.iterrows():
        print(f"  {idx.strftime('%Y-%m-%d')}: {row['range']:.2f}")

    print("\n--- Detailed Audit: WEDNESDAY Median (NY1) ---")
    wed_stats = session_history['NY1'][2] # 0=Mon, 2=Wed
    # Filter out today if present
    curr_date = current_session_stats.get('NY1', {}).get('date')
    valid_wed = [x for x in wed_stats if x['date'] != curr_date][-LOOKBACK_SAMPLES:]
    
    for m in valid_wed:
        print(f"  {m['date']}: {m['range']:.2f}")
    
    calc_med = np.median([m['range'] for m in valid_wed]) if valid_wed else 0
    print(f"  > Calculated Median: {calc_med:.2f}")

if __name__ == "__main__":
    process_ticker(TICKER)
