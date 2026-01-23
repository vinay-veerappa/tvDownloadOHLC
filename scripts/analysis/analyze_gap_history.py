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

        # Percents relative to PRICE level (from Open)
        retrace_price_pct = (retrace_pts / open_price) * 100.0 if open_price > 0 else 0
        fakeout_price_pct = (fakeout_pts / open_price) * 100.0 if open_price > 0 else 0
        extension_price_pct = (extension_pts / open_price) * 100.0 if open_price > 0 else 0

        results.append({
            "date": date_str,
            "day": day_of_week,
            "gap_dir": gap_type,
            "prev_close": prev_close,
            "vol_regime": vol_regime,
            "vvix_regime": vvix_regime,
            "atr_pct_val": atr_pct,
            "gap_pct": gap_pct,
            "is_filled": is_filled,
            "time_to_fill": time_to_fill,
            # Gap Relative %
            "retrace_pct": retrace_pct, 
            "fakeout_pct": fakeout_pct, 
            "trend_continuation": trend_continuation,
            "extension_ratio": extension_ratio,
            # Price Relative %
            "retrace_price_pct": retrace_price_pct,
            "fakeout_price_pct": fakeout_price_pct,
            "extension_price_pct": extension_price_pct,
            "far_side_held": far_side_held,
            "days_to_fill": 0 if is_filled else None
        })
        
    print(f"[{ticker}] Scanning forward for Deferred Fills (Multi-Day)...")
    # For each gap that wasn't filled on Day 0, check subsequent days (up to 20)
    for i, result in enumerate(results):
        if result['is_filled']: continue
        
        target = result['prev_close']
        g_dir = result['gap_dir']
        start_date = result['date']
        
        # Find index in sorted_dates
        try:
            start_idx = sorted_dates.index(start_date)
        except ValueError: continue
        
        # Check next 60 trading days (IPDA Windows)
        for day_offset in range(1, 61):
            if start_idx + day_offset >= len(sorted_dates): break
            next_date = sorted_dates[start_idx + day_offset]
            if next_date not in day_groups: continue
            
            future_day = day_groups[next_date]
            fill_found = False
            if g_dir == "UP":
                if future_day['low'].min() <= target: fill_found = True
            else:
                if future_day['high'].max() >= target: fill_found = True
                
            if fill_found:
                result['days_to_fill'] = day_offset
                break
                
    df_res = pd.DataFrame(results)
    
    def get_stats(series, precision=1):
        if series.empty: return "N/A"
        mean_val = series.mean()
        med_val = series.median()
        # Mode calculation: round to specified precision to group values
        mode_val = series.round(precision).mode().iloc[0] if not series.empty else 0
        return f"Mean: {mean_val:.{precision}f} | Med: {med_val:.{precision}f} | Mode: {mode_val:.{precision}f}"

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
        time_stats = get_stats(day_df[day_df['is_filled']]['time_to_fill'], precision=0)
        print(f"{d:10} | Fill Rate: {fill_rate:5.1f}% | Time to Fill (min) -> {time_stats}")

    # 2. MAE / MFE Statistics
    print("\n📐 2. MAE / MFE Precision (% of Gap Size)")
    print("--------------------------------------------------")
    print(f"MAE (Retrace %):   {get_stats(df_res['retrace_pct'])}")
    print(f"MFE (Fakeout %):   {get_stats(df_res['fakeout_pct'])}  <-- Extension BEFORE fill")
    print(f"MFE (Extension %): {get_stats(df_res['extension_ratio'] * 100)}  <-- Total Session Extension")

    print("\n📐 3. Pure Price Percentage Levels (Move / Price %)")
    print("--------------------------------------------------")
    print(f"MAE (Retrace Pct):   {get_stats(df_res['retrace_price_pct'], precision=2)}%")
    print(f"MFE (Fakeout Pct):   {get_stats(df_res['fakeout_price_pct'], precision=2)}%  <-- Extension BEFORE fill")
    print(f"MFE (Extension Pct): {get_stats(df_res['extension_price_pct'], precision=2)}%  <-- Total Session Extension")

    # 3. Volatility Regime Impact
    print("\n🌊 4. Volatility Regime Impact")
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

    # 6. Deferred Fill Analysis (Multi-Day IPDA Windows)
    print("\n🧲 6. Deferred Fill Analysis (IPDA Windows: 20, 40, 60 Day)")
    print("--------------------------------------------------")
    unfilled_day0 = df_res[~df_res['is_filled']].copy()
    if not unfilled_day0.empty:
        # Overall Stats
        count_day0 = len(unfilled_day0)
        filled_1d = (unfilled_day0['days_to_fill'] == 1).sum()
        filled_20d = (unfilled_day0['days_to_fill'] <= 20).sum()
        filled_40d = (unfilled_day0['days_to_fill'] <= 40).sum()
        filled_60d = (unfilled_day0['days_to_fill'] <= 60).sum()
        
        print(f"Total gaps NOT filled on Day 0: {count_day0}")
        print(f" -> Overall Filled on Day 1:       {(filled_1d/count_day0)*100:.1f}%")
        print(f" -> IPDA 20-Day (Short Term):     {(filled_20d/count_day0)*100:.1f}%")
        print(f" -> IPDA 40-Day (Med Term):       {(filled_40d/count_day0)*100:.1f}%")
        print(f" -> IPDA 60-Day (Long Term):      {(filled_60d/count_day0)*100:.1f}%")

        # DOW Segmentation for Deferred Fills
        print("\n📅 Deferred Fill Probabilities by Gap Creation Day:")
        print(f"{'Creation Day':13} | {'Unfilled':8} | {'Fill Day 1':10} | {'3-Day Cum':9}")
        print("-" * 50)
        
        for d in dow_order:
            day_unfilled = unfilled_day0[unfilled_day0['day'] == d]
            if day_unfilled.empty: continue
            
            n_unfilled = len(day_unfilled)
            f1 = (day_unfilled['days_to_fill'] == 1).sum() / n_unfilled * 100
            f3 = (day_unfilled['days_to_fill'] <= 3).sum() / n_unfilled * 100
            
            print(f"{d:13} | {n_unfilled:8} | {f1:9.1f}% | {f3:8.1f}%")

        # Time to Fill (for those that eventually fill)
        eventual_fills = unfilled_day0.dropna(subset=['days_to_fill'])
        if not eventual_fills.empty:
             print(f"\nDays to Fill (Med/Mean):  {get_stats(eventual_fills['days_to_fill'], precision=0)}")
    else:
        print("No unfilled Day-0 gaps found.")

if __name__ == "__main__":
    analyze_gap_history(ticker="NQ1")
