import json
import pandas as pd
import numpy as np
import os
import sys

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
try:
    from fused_data_loader import load_fused_data
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'utils'))
    from fused_data_loader import load_fused_data

GAP_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived', 'rth_gaps.json')

def analyze_gap_fills(ticker="NQ1"):
    print(f"[{ticker}] Loading Gaps...")
    if not os.path.exists(GAP_FILE):
        print("Gap file not found.")
        return

    with open(GAP_FILE, 'r') as f:
        all_gaps = json.load(f)
        
    gaps = all_gaps.get(ticker, [])
    if not gaps:
        print(f"No gaps found for {ticker}")
        return

    gaps_df = pd.DataFrame(gaps)
    # Filter recent years for speed? No, let's try full history but optimized.
    # Actually, we need to load 1m data to check for fills.
    
    print(f"[{ticker}] Loading Intraday Data (1m)...")
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=True)
    
    if df_1m.empty: 
        print("No intraday data.")
        return

    # Ensure datetime index
    if 'datetime' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['datetime'], utc=True)
        df_1m.set_index('datetime', inplace=True)
        
    try:
        df_1m = df_1m.tz_convert('US/Eastern')
    except:
        df_1m = df_1m.tz_localize('UTC').tz_convert('US/Eastern')
        
    # Pre-compute daily high/lows TO SPEED UP? 
    # Actually we need TIME of fill. So we generally need to search the day's data.
    
    # Optimization: Group 1m data by date
    # df_1m['date_str'] = df_1m.index.strftime('%Y-%m-%d')
    # grouped = df_1m.groupby(df_1m.index.date) 
    # Iterating groups is faster than 6000 searches on full index
    
    print(f"[{ticker}] analyzing {len(gaps_df)} gaps against intraday price action...")
    
    results = []
    
    # We only care about the RTH session for fills? 
    # Usually "Gap Fill" implies filling during the RTH session of that day.
    # If it fills next week, it's not a "Gap Fill" event in the day trading context.
    
    cutoff_time = pd.Timedelta(hours=16, minutes=15) # Only checking until 16:15 ET ??
    # Or just check the whole trading day (until 17:00 or next open).
    # Let's check until 16:15 ET (Close).
    
    # Iterate through gaps
    # Doing this in a loop for 5000 days might be slow but acceptable for analysis script.
    
    # To speed up: extract only needed columns
    df_mini = df_1m[['high', 'low', 'open', 'close']].copy()
    
    # Group by date for O(1) lookup
    # Group by date for O(1) lookup
    day_groups = {str(k): v for k, v in df_mini.groupby(df_mini.index.date)}
    
    # Optimization: Sorted Dates map
    sorted_dates = sorted(day_groups.keys())
    date_map = {curr: prev for prev, curr in zip(sorted_dates, sorted_dates[1:])}

    for idx, row in gaps_df.iterrows():
        date_str = row['date']
        gap_type = row['gap_direction']
        target_price = row['prev_close_price']
        gap_size = abs(row['gap_size'])

        if date_str not in day_groups: continue
        day_data = day_groups[date_str]
        
        # Calculate Percentage
        gap_pct_val = (gap_size / row['prev_close_price']) * 100.0 if row['prev_close_price'] else 0

        # RTH Logic
        rth_start = pd.Timestamp(date_str + " 09:30:00").tz_localize("US/Eastern")
        day_rth = day_data[day_data.index >= rth_start]
        if day_rth.empty: continue

        # Check Fill
        is_filled = False
        time_to_fill = None
        if gap_type == "UP":
            fill_mask = day_rth['low'] <= target_price
        else:
            fill_mask = day_rth['high'] >= target_price
            
        if fill_mask.any():
            is_filled = True
            first_fill = day_rth[fill_mask].index[0]
            time_to_fill = (first_fill - rth_start).total_seconds() / 60.0
            
        # Fill %
        if is_filled:
            fill_pct = 100.0
        else:
            if gap_type == "UP":
                retrace = row['curr_open_price'] - day_rth['low'].min()
            else:
                retrace = day_rth['high'].max() - row['curr_open_price']
            fill_pct = (retrace / gap_size) * 100.0 if gap_size > 0 else 0

        # Trend Aligned
        session_change = day_rth.iloc[-1]['close'] - row['curr_open_price']
        trend_aligned = (gap_type == "UP" and session_change > 0) or (gap_type == "DOWN" and session_change < 0)

        # Far Side Defense (RTH Breaks)
        far_side_held = None
        if date_str in date_map:
            prev_date_str = date_map[date_str]
            prev_day_data = day_groups[prev_date_str]
            
            # Prev RTH
            p_start = pd.Timestamp(prev_date_str + " 09:30:00").tz_localize("US/Eastern")
            p_end = pd.Timestamp(prev_date_str + " 16:15:00").tz_localize("US/Eastern")
            prev_rth = prev_day_data[(prev_day_data.index >= p_start) & (prev_day_data.index <= p_end)]
            
            if not prev_rth.empty:
                held = True
                if gap_type == "UP":
                    # Did we break PREV LOW?
                    prev_low = prev_rth['low'].min()
                    if day_rth['low'].min() < prev_low: held = False
                else:
                    # Did we break PREV HIGH?
                    prev_high = prev_rth['high'].max()
                    if day_rth['high'].max() > prev_high: held = False
                far_side_held = held

        results.append({
            "gap_size": gap_size,
            "gap_pct": gap_pct_val,
            "gap_dir": gap_type,
            "is_filled": is_filled,
            "time_to_fill": time_to_fill,
            "fill_pct": fill_pct,
            "session_change": session_change,
            "trend_aligned": trend_aligned,
            "far_side_held": far_side_held
        })
        
    # --- Statistics ---
    res_df = pd.DataFrame(results)
    
    print(f"\n[{ticker}] Analysis of {len(res_df)} RTH Sessions with Gaps:\n")
    
    # 1. Fill Rate
    fill_rate = (res_df['is_filled'].sum() / len(res_df)) * 100
    print(f"Overall Fill Rate: {fill_rate:.1f}%")
    
    # 2. RTH Defense Rate (Far Side Held)
    if 'far_side_held' in res_df.columns:
        valid_defense = res_df.dropna(subset=['far_side_held'])
        if not valid_defense.empty:
            defense_rate = (valid_defense['far_side_held'].sum() / len(valid_defense)) * 100
            print(f"Gap Defense Rate (Held Far Side): {defense_rate:.1f}%")
    
    # 3. Time to Fill (Median)
    filled_only = res_df[res_df['is_filled']]
    median_time = filled_only['time_to_fill'].median()
    print(f"Median Time to Fill: {median_time:.0f} minutes")

    
    # 3. Fill Rate by Gap Size % (Deciles)
    # Bucket gap Pct
    # Use qcut on pct
    res_df['size_bucket'] = pd.qcut(res_df['gap_pct'], q=5, labels=["Very Small", "Small", "Medium", "Large", "Very Large"])
    
    # Get thresholds for buckets
    thresholds = res_df.groupby('size_bucket', observed=False)['gap_pct'].max()
    
    print("\n-- Fill Probability by Gap Size (Relative %) --")
    fill_by_size = res_df.groupby('size_bucket', observed=False)['is_filled'].mean() * 100
    
    # specific formatting to show range
    summary = pd.concat([fill_by_size, thresholds], axis=1)
    summary.columns = ['Fill Rate', 'Max Pct']
    print(summary.to_string(float_format="{:.2f}%".format))
    
    # 4. Correlation: Gap Size vs Session Trend
    print("\n-- 'Gap & Go' Probability (Trend Aligned) --")
    trend_by_size = res_df.groupby('size_bucket', observed=False)['trend_aligned'].mean() * 100
    print(trend_by_size.to_string(float_format="{:.1f}%".format))
    
    # 5. Average Fill % for Unfilled
    unfilled = res_df[~res_df['is_filled']]
    if not unfilled.empty:
        avg_partial = unfilled['fill_pct'].median()
        print(f"\nWhen NOT filled, median retracement is: {avg_partial:.1f}%")
        
if __name__ == "__main__":
    analyze_gap_fills(ticker="NQ1")
