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

def analyze_gap_history(ticker="NQ1"):
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
    
    print(f"[{ticker}] Loading 1m Price Data...")
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=True)
    if 'datetime' in df_1m.columns:
        df_1m['datetime'] = pd.to_datetime(df_1m['datetime'], utc=True)
        df_1m.set_index('datetime', inplace=True)
    try:
        df_1m = df_1m.tz_convert('US/Eastern')
    except:
        df_1m = df_1m.tz_localize('UTC').tz_convert('US/Eastern')
        
    # Load VIX for Context if available
    print(f"[{ticker}] Loading VIX Data for Context...")
    vix_df = load_fused_data("VIX", timeframe="1m", require_historical=True)
    if not vix_df.empty:
        if 'datetime' in vix_df.columns:
            vix_df['datetime'] = pd.to_datetime(vix_df['datetime'], utc=True)
            vix_df.set_index('datetime', inplace=True)
        try:
             vix_df = vix_df.tz_convert('US/Eastern')
        except:
             vix_df = vix_df.tz_localize('UTC').tz_convert('US/Eastern')
    
    # Pre-process Data Groups
    price_mini = df_1m[['open', 'high', 'low', 'close']].copy()
    day_groups = {str(k): v for k, v in price_mini.groupby(price_mini.index.date)}
    
    # Pre-process VIX (Daily Mean VIX or VIX at Open?)
    # VIX at 09:30 is most relevant context for the session.
    vix_at_open = {}
    if not vix_df.empty:
        # Resample to 1min to align, then get 09:30
        vix_opens = vix_df.at_time('09:30')
        # Map date_str -> VIX Close
        for ts, row in vix_opens.iterrows():
            vix_at_open[str(ts.date())] = row['close']
            
    sorted_dates = sorted(day_groups.keys())
    date_map = {curr: prev for prev, curr in zip(sorted_dates, sorted_dates[1:])}
    
    results = []
    
    for idx, row in gaps_df.iterrows():
        date_str = row['date']
        gap_type = row['gap_direction']
        prev_close = row['prev_close_price']
        gap_size = abs(row['gap_size'])
        open_price = row['curr_open_price']
        
        if date_str not in day_groups: continue
        day_data = day_groups[date_str]
        
        # --- 1. Basic Gap Metrics ---
        # Percentage Gap
        gap_pct = (gap_size / prev_close) * 100.0 if prev_close else 0
        
        # --- 2. Context Metrics ---
        # Day of Week
        dt_obj = pd.Timestamp(date_str)
        day_of_week = dt_obj.day_name()
        
        # VIX Context
        vix_val = vix_at_open.get(date_str, None)
        vol_regime = "Unknown"
        if vix_val:
            if vix_val < 15: vol_regime = "Low"
            elif vix_val < 25: vol_regime = "Normal"
            else: vol_regime = "High"
            
        # Overnight Context
        # Range of 18:00 (Prev Day) to 09:30 (Current Day)
        # Approximate: Look at Pre-Market data in current day_data IF it starts at 00:00 or 18:00
        # fused_data_loader typically gives us 24h data for futures.
        # Find High/Low BEFORE 09:30
        pre_market = day_data[day_data.index < (dt_obj + pd.Timedelta(hours=9, minutes=30)).tz_localize("US/Eastern")]
        if not pre_market.empty:
            pm_high = pre_market['high'].max()
            pm_low = pre_market['low'].min()
            globex_range = pm_high - pm_low
            globex_range_pct = (globex_range / open_price) * 100
        else:
            globex_range = None
            globex_range_pct = None

        # --- 3. RTH Session Analysis ---
        rth_start = (dt_obj + pd.Timedelta(hours=9, minutes=30)).tz_localize("US/Eastern")
        day_rth = day_data[day_data.index >= rth_start]
        if day_rth.empty: continue
        
        # Fill Logic
        is_filled = False
        time_to_fill = None
        max_retrace_pct = 0.0
        
        if gap_type == "UP":
            fill_mask = day_rth['low'] <= prev_close
            min_low = day_rth['low'].min()
            # Retracement = Distance from Open DOWN to Low
            # Gap Size = Open - PrevClose
            dist_covered = open_price - min_low
            max_retrace_pct = (dist_covered / gap_size) * 100.0 if gap_size > 0 else 0
        else:
            fill_mask = day_rth['high'] >= prev_close
            max_high = day_rth['high'].max()
            # Retracement = Distance from Open UP to High
            # Gap Size = PrevClose - Open
            dist_covered = max_high - open_price
            max_retrace_pct = (dist_covered / gap_size) * 100.0 if gap_size > 0 else 0
            
        if fill_mask.any():
            is_filled = True
            first_fill = day_rth[fill_mask].index[0]
            time_to_fill = (first_fill - rth_start).total_seconds() / 60.0 # Mins
            max_retrace_pct = 100.0
            
        # Trend / Continuation Logic
        session_close = day_rth.iloc[-1]['close']
        session_move = session_close - open_price
        
        # Did it trend in gap direction?
        # Gap UP -> Session UP (session_move > 0)
        # Gap DOWN -> Session DOWN (session_move < 0)
        trend_continuation = False
        if gap_type == "UP" and session_move > 0: trend_continuation = True
        if gap_type == "DOWN" and session_move < 0: trend_continuation = True
        
        # Extension: How far did it go BEYOND the open in gap direction?
        # Gap Up: Max High - Open
        # Gap Down: Open - Min Low
        extension_pts = 0
        if gap_type == "UP":
            extension_pts = day_rth['high'].max() - open_price
        else:
            extension_pts = open_price - day_rth['low'].min()
            
        extension_ratio = (extension_pts / gap_size) if gap_size > 0 else 0

        # RTH Break Defense
        far_side_held = None
        if date_str in date_map:
            p_date = date_map[date_str]
            if p_date in day_groups:
                p_data = day_groups[p_date]
                # Prev RTH
                p_start = (pd.Timestamp(p_date) + pd.Timedelta(hours=9, minutes=30)).tz_localize("US/Eastern")
                p_end = (pd.Timestamp(p_date) + pd.Timedelta(hours=16, minutes=15)).tz_localize("US/Eastern")
                p_rth = p_data[(p_data.index >= p_start) & (p_data.index <= p_end)]
                
                if not p_rth.empty:
                    held = True
                    if gap_type == "UP":
                         if day_rth['low'].min() < p_rth['low'].min(): held = False
                    else:
                         if day_rth['high'].max() > p_rth['high'].max(): held = False
                    far_side_held = held

        results.append({
            "date": date_str,
            "day": day_of_week,
            "vix": vix_val,
            "vol_regime": vol_regime,
            "globex_range_pct": globex_range_pct,
            "gap_pct": gap_pct,
            "is_filled": is_filled,
            "time_to_fill": time_to_fill,
            "retrace_pct": max_retrace_pct,
            "trend_continuation": trend_continuation,
            "extension_ratio": extension_ratio,
            "far_side_held": far_side_held
        })
        
    df_res = pd.DataFrame(results)
    
    # --- REPORT GENERATION ---
    print("\n" + "="*50)
    print(f"🧬 EXPANDED GAP ANALYSIS: {ticker}")
    print("="*50)
    
    # 1. Day of Week Stats
    print("\n📅 1. Day of Week Analysis (Fill Rates)")
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    df_res['day'] = pd.Categorical(df_res['day'], categories=dow_order, ordered=True)
    dow_stats = df_res.groupby('day', observed=False).agg({
        'is_filled': 'mean',
        'trend_continuation': 'mean',
        'gap_pct': 'mean' # Avg gap size per day
    }) * 100
    print(dow_stats.to_string(float_format="{:.1f}%".format))
    
    # 2. Volatility Regime
    print("\n🌊 2. VIX Regime Impact")
    vix_stats = df_res.groupby('vol_regime', observed=False).agg({
        'is_filled': 'mean',
        'far_side_held': 'mean'
    }) * 100
    print(vix_stats.to_string(float_format="{:.1f}%".format))
    
    # 3. Partial Fill Precision (Bucket fill %)
    # Only for UNFILLED gaps
    unfilled = df_res[~df_res['is_filled']].copy()
    if not unfilled.empty:
        print("\n🔎 3. Partial Fill Precision (Unfilled Gaps)")
        # Bucket retrace pct: 0-25, 25-50, 50-75, 75-99
        unfilled['fill_bucket'] = pd.cut(unfilled['retrace_pct'], bins=[0, 25, 50, 75, 100], labels=["0-25%", "25-50%", "50-75%", "75-99%"])
        fill_dist = unfilled['fill_bucket'].value_counts(normalize=True).sort_index() * 100
        print(fill_dist.to_string(float_format="{:.1f}%".format))
        print(f"Median Retrace: {unfilled['retrace_pct'].median():.1f}% | Mean: {unfilled['retrace_pct'].mean():.1f}%")

    # 4. Continuation When Not Filling
    print("\n🚀 4. Continuation Logic (When Gap Holds)")
    # Filter: Gap > 0.25% (Medium/Large) AND Not Filled
    trend_candidates = df_res[(df_res['gap_pct'] > 0.25) & (~df_res['is_filled'])]
    if not trend_candidates.empty:
        trend_prob = trend_candidates['trend_continuation'].mean() * 100
        avg_ext = trend_candidates['extension_ratio'].median()
        print(f"Scenario: Gap > 0.25% AND Holds")
        print(f" -> Probability of Trend Day (Gap & Go): {trend_prob:.1f}%")
        print(f" -> Median Extension Ratio: {avg_ext:.2f}x (Price runs {avg_ext:.2f}x the gap size)")

    # 5. Fill Timing Histograms
    filled = df_res[df_res['is_filled']].copy()
    if not filled.empty:
        print("\n⏱️ 5. Fill Timing Distribution")
        filled['time_bucket'] = pd.cut(filled['time_to_fill'], bins=[0, 15, 30, 60, 120, 9999], labels=["0-15m", "15-30m", "30-60m", "1-2h", ">2h"])
        time_dist = filled['time_bucket'].value_counts(normalize=True).sort_index() * 100
        print(time_dist.to_string(float_format="{:.1f}%".format))
        print(f"Median Time: {filled['time_to_fill'].median():.0f}m | Mean: {filled['time_to_fill'].mean():.0f}m")

if __name__ == "__main__":
    analyze_gap_history(ticker="NQ1")
