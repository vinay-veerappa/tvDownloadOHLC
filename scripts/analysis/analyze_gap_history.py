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
        
    # Load VIX and VVIX for Context
    print(f"[{ticker}] Loading Volatility Data (VIX/VVIX)...")
    vix_df = load_fused_data("VIX", timeframe="1m", require_historical=True)
    vvix_df = load_fused_data("VVIX", timeframe="1d", require_historical=True)  # Daily data
    
    # Process VIX
    vix_at_open = {}
    if not vix_df.empty:
        if 'datetime' in vix_df.columns:
            vix_df['datetime'] = pd.to_datetime(vix_df['datetime'], utc=True)
            vix_df.set_index('datetime', inplace=True)
        try: vix_df = vix_df.tz_convert('US/Eastern')
        except: vix_df = vix_df.tz_localize('UTC').tz_convert('US/Eastern')
        # Get 09:30 values
        vix_opens = vix_df.at_time('09:30')
        for ts, row in vix_opens.iterrows():
            vix_at_open[str(ts.date())] = row['close']
            
    # Process VVIX (Daily)
    vvix_by_date = {}
    if not vvix_df.empty:
        if 'datetime' in vvix_df.columns:
            vvix_df['datetime'] = pd.to_datetime(vvix_df['datetime'], utc=True)
            vvix_df.set_index('datetime', inplace=True)
        # Map date -> VVIX close (or open, both work for daily)
        for ts, row in vvix_df.iterrows():
            vvix_by_date[str(ts.date())] = row['close']
            
    # Calculate ATR (14-day) 
    # We need daily data for ATR. We can resample 1m data to daily.
    print(f"[{ticker}] Calculating ATR-14...")
    daily_ohlc = df_1m.resample('D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    # Simple TR calculation
    daily_ohlc['prev_close'] = daily_ohlc['close'].shift(1)
    daily_ohlc['tr0'] = abs(daily_ohlc['high'] - daily_ohlc['low'])
    daily_ohlc['tr1'] = abs(daily_ohlc['high'] - daily_ohlc['prev_close'])
    daily_ohlc['tr2'] = abs(daily_ohlc['low'] - daily_ohlc['prev_close'])
    daily_ohlc['tr'] = daily_ohlc[['tr0', 'tr1', 'tr2']].max(axis=1)
    daily_ohlc['atr'] = daily_ohlc['tr'].rolling(window=14).mean()
    
    # Map ATR to date string
    atr_map = {str(ts.date()): val for ts, val in daily_ohlc['atr'].items()}

    # Pre-process Data Groups
    price_mini = df_1m[['open', 'high', 'low', 'close']].copy()
    day_groups = {str(k): v for k, v in price_mini.groupby(price_mini.index.date)}
    
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
            if vix_val < 15: vol_regime = "Low VIX"
            elif vix_val < 25: vol_regime = "Normal VIX"
            else: vol_regime = "High VIX"
            
        # VVIX Context 
        vvix_val = vvix_by_date.get(date_str, None)
        vvix_regime = "Unknown"
        if vvix_val:
            if vvix_val < 90: vvix_regime = "Low VVIX"
            elif vvix_val < 110: vvix_regime = "Normal VVIX"
            else: vvix_regime = "High VVIX"
            
        # ATR Context
        atr_val = atr_map.get(date_str, None)
        atr_pct = (atr_val / open_price) * 100.0 if atr_val and open_price else None
        
            
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
        retrace_pts = 0.0
        fakeout_pts = 0.0 # Extension BEFORE fill (if filled) or total extension (if not)
        
        if gap_type == "UP":
            # Retracement (Towards Prev Close)
            fill_mask = day_rth['low'] <= prev_close
            min_low = day_rth['low'].min()
            retrace_pts = max(0, open_price - min_low)
            
            # Extension (Away from Prev Close)
            if fill_mask.any():
                is_filled = True
                first_fill = day_rth[fill_mask].index[0]
                time_to_fill = (first_fill - rth_start).total_seconds() / 60.0 # Mins
                # Fakeout: Max high BEFORE first fill
                pre_fill_data = day_rth[day_rth.index <= first_fill]
                fakeout_pts = pre_fill_data['high'].max() - open_price
            else:
                fakeout_pts = day_rth['high'].max() - open_price
                
        else: # Gap DOWN
            # Retracement (Towards Prev Close)
            fill_mask = day_rth['high'] >= prev_close
            max_high = day_rth['high'].max()
            retrace_pts = max(0, max_high - open_price)
            
            # Extension (Away from Prev Close)
            if fill_mask.any():
                is_filled = True
                first_fill = day_rth[fill_mask].index[0]
                time_to_fill = (first_fill - rth_start).total_seconds() / 60.0
                # Fakeout: Max low BEFORE first fill
                pre_fill_data = day_rth[day_rth.index <= first_fill]
                fakeout_pts = open_price - pre_fill_data['low'].min()
            else:
                fakeout_pts = open_price - day_rth['low'].min()
            
        # Percents relative to gap size
        retrace_pct = (retrace_pts / gap_size) * 100.0 if gap_size > 0 else 0
        fakeout_pct = (fakeout_pts / gap_size) * 100.0 if gap_size > 0 else 0
        if is_filled: retrace_pct = 100.0

        # Trend / Continuation Logic (Total Session Extension)
        extension_pts = 0
        if gap_type == "UP":
            extension_pts = day_rth['high'].max() - open_price
        else:
            extension_pts = open_price - day_rth['low'].min()
        extension_ratio = (extension_pts / gap_size) if gap_size > 0 else 0

        # Trend result (Closes in gap direction)
        session_close = day_rth.iloc[-1]['close']
        trend_continuation = (gap_type == "UP" and session_close > open_price) or (gap_type == "DOWN" and session_close < open_price)

        # RTH Break Defense
        far_side_held = None
        if date_str in date_map:
            p_date = date_map[date_str]
            if p_date in day_groups:
                p_data = day_groups[p_date]
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
            "vvix": vvix_val,
            "vvix_regime": vvix_regime,
            "atr_pct_val": atr_pct,
            "gap_pct": gap_pct,
            "is_filled": is_filled,
            "time_to_fill": time_to_fill,
            "retrace_pct": retrace_pct, # MAE for Trend / Progress for Fill
            "fakeout_pct": fakeout_pct, # Heat before Fill / Signal for Trend
            "trend_continuation": trend_continuation,
            "extension_ratio": extension_ratio,
            "far_side_held": far_side_held
        })
        
    df_res = pd.DataFrame(results)
    
    def get_stats(series):
        if series.empty: return "N/A"
        mean_val = series.mean()
        med_val = series.median()
        # Mode on rounded integers
        mode_val = series.round().mode().iloc[0] if not series.empty else 0
        return f"Mean: {mean_val:.1f} | Med: {med_val:.1f} | Mode: {mode_val:.0f}"

    # --- REPORT GENERATION ---
    print("\n" + "="*50)
    print(f"🧬 EXPANDED GAP ANALYSIS: {ticker}")
    print("="*50)
    
    # 1. Day of Week Stats
    print("\n📅 1. Day of Week Analysis (Fill Rates & Timing)")
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    df_res['day'] = pd.Categorical(df_res['day'], categories=dow_order, ordered=True)
    
    for d in dow_order:
        day_df = df_res[df_res['day'] == d]
        if day_df.empty: continue
        fill_rate = day_df['is_filled'].mean() * 100
        time_stats = get_stats(day_df[day_df['is_filled']]['time_to_fill'])
        print(f"{d:10} | Fill Rate: {fill_rate:5.1f}% | Time to Fill (min) -> {time_stats}")

    # 2. MAE / MFE Statistics
    print("\n📐 2. MAE / MFE Precision (% of Gap Size)")
    print("--------------------------------------------------")
    print(f"MAE (Retrace %):   {get_stats(df_res['retrace_pct'])}")
    print(f"MFE (Fakeout %):   {get_stats(df_res['fakeout_pct'])}  <-- Extension BEFORE fill")
    print(f"MFE (Extension %): {get_stats(df_res['extension_ratio'] * 100)}  <-- Total Session Extension")

    # 3. Volatility Regime Impact
    print("\n🌊 3. Volatility Regime Impact")
    print("--- VIX Regimes ---")
    vix_stats = df_res.groupby('vol_regime', observed=False).agg({
        'is_filled': ['mean', 'count'],
        'far_side_held': 'mean'
    })
    vix_stats.columns = ['is_filled', 'Days', 'far_side_held']
    vix_stats[['is_filled', 'far_side_held']] = vix_stats[['is_filled', 'far_side_held']] * 100
    print(vix_stats[['Days', 'is_filled', 'far_side_held']].to_string(float_format="{:.1f}%".format))
    
    print("\n--- VVIX Regimes ---")
    vvix_stats = df_res.groupby('vvix_regime', observed=False).agg({
        'is_filled': ['mean', 'count'],
        'far_side_held': 'mean'
    })
    vvix_stats.columns = ['is_filled', 'Days', 'far_side_held']
    vvix_stats[['is_filled', 'far_side_held']] = vvix_stats[['is_filled', 'far_side_held']] * 100
    print(vvix_stats[['Days', 'is_filled', 'far_side_held']].to_string(float_format="{:.1f}%".format))
    
    # ATR Correlation
    print("\n--- Correlation with Daily ATR % ---")
    if 'atr_pct_val' in df_res.columns:
        df_res['atr_bucket'] = pd.qcut(df_res['atr_pct_val'], 3, labels=["Low ATR", "Normal ATR", "High ATR"])
        atr_stats = df_res.groupby('atr_bucket', observed=False).agg({
            'is_filled': 'mean',
            'far_side_held': 'mean',
            'gap_pct': 'mean'
        }) * 100
        print(atr_stats.to_string(float_format="{:.1f}%".format))

    # 4. Continuation When Not Filling
    print("\n🚀 4. Continuation Logic (When Gap Holds)")
    trend_candidates = df_res[(df_res['gap_pct'] > 0.25) & (~df_res['is_filled'])]
    if not trend_candidates.empty:
        trend_prob = trend_candidates['trend_continuation'].mean() * 100
        ext_stats = get_stats(trend_candidates['extension_ratio'])
        print(f"Scenario: Gap > 0.25% AND Holds")
        print(f" -> Probability of Trend Day (Gap & Go): {trend_prob:.1f}%")
        print(f" -> Extension Ratio (Multiple of Gap):  {ext_stats}")

    # 5. Fill Timing Histograms
    filled = df_res[df_res['is_filled']].copy()
    if not filled.empty:
        print("\n⏱️ 5. Fill Timing Distribution")
        filled['time_bucket'] = pd.cut(filled['time_to_fill'], bins=[0, 15, 30, 60, 120, 9999], labels=["0-15m", "15-30m", "30-60m", "1-2h", ">2h"])
        time_dist = filled['time_bucket'].value_counts(normalize=True).sort_index() * 100
        print(time_dist.to_string(float_format="{:.1f}%".format))

if __name__ == "__main__":
    analyze_gap_history(ticker="NQ1")
