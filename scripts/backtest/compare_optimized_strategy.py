
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

def compare_optimized(ticker="NQ1", days=200):
    print(f"Running MFE TIMING ANALYSIS for {ticker} (Last {days} Days)...")
    
    # --- CONFIG ---
    TP_PCT = 0.0015
    HARD_EXIT = time(10, 0)
    MAX_ENTRY_TIME = time(9, 35) 
    HARD_STOP_PCT = 0.0020
    EOD_EXIT = time(16, 0)
    
    CSV_PATH = "reports/930_optimized_comparison.csv"
    os.makedirs("reports", exist_ok=True)
    
    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path): return
    df = pd.read_parquet(data_path)
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        elif 'datetime' in df.columns: df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    df = df.sort_index(); 
    if df.index.tz is None: pass 
    else: df = df.tz_convert('US/Eastern')

    start_date = df.index[-1] - pd.Timedelta(days=days)
    df = df[df.index >= start_date]
    dates = df.index.normalize().unique()
    all_trades = [] 

    for d in dates:
        day_data = df[df.index.normalize() == d]
        t930 = d + pd.Timedelta(hours=9, minutes=30)
        c930 = day_data[day_data.index == t930]
        if c930.empty: continue
        
        r_high = c930['high'].iloc[0]; r_low = c930['low'].iloc[0]
        common_meta = { 'Date': d.date() }
        
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=EOD_EXIT.hour, minutes=EOD_EXIT.minute)
        window = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        if window.empty: continue
        
        sl_long_glob = r_low; sl_short_glob = r_high

        # 1. BASELINE
        s1 = run_trade_logic(window, r_high, r_low, TP_PCT, HARD_EXIT, sl_long_glob, sl_short_glob, False, 0, None)
        if s1: record_trade(all_trades, common_meta, '1. Baseline', s1)

        # 2. OPTIMIZED BREAKOUT
        s2 = run_trade_logic(window, r_high, r_low, TP_PCT, HARD_EXIT, sl_long_glob, sl_short_glob, True, HARD_STOP_PCT, MAX_ENTRY_TIME)
        if s2: record_trade(all_trades, common_meta, '2. Opt_Breakout', s2)
        
        # 3. OPTIMIZED FVG
        scan_end = d + pd.Timedelta(hours=9, minutes=35)
        scan_data = day_data[(day_data.index >= t930) & (day_data.index <= scan_end)]
        fvg_dir = None; fvg_top = 0; fvg_bot = 0; fvg_time = None
        s_row = day_data.index.get_loc(t930); e_row = day_data.index.get_loc(scan_data.index[-1])
        largest_gap = 0
        for i in range(s_row + 1, e_row + 1):
            if i < 2: continue
            curr = day_data.iloc[i]; prev2 = day_data.iloc[i-2]
            if curr['low'] > prev2['high']:
                 if prev2['high'] >= r_high or curr['close'] > r_high:
                     gap = curr['low'] - prev2['high']
                     if gap > largest_gap: largest_gap = gap; fvg_dir = 'LONG'; fvg_top = curr['low']; fvg_bot = prev2['high']; fvg_time = day_data.index[i]
            elif curr['high'] < prev2['low']:
                 if prev2['low'] <= r_low or curr['close'] < r_low:
                     gap = prev2['low'] - curr['high']
                     if gap > largest_gap: largest_gap = gap; fvg_dir = 'SHORT'; fvg_top = prev2['low']; fvg_bot = curr['high']; fvg_time = day_data.index[i]
        
        if fvg_dir and (fvg_bot >= r_low and fvg_top <= r_high):
            market_time = fvg_time + pd.Timedelta(minutes=1)
            t_win = window[window.index >= market_time]
            if not t_win.empty:
                mkt_price = t_win.iloc[0]['open']
                s3 = run_market_logic(t_win, fvg_dir, mkt_price, sl_long_glob, sl_short_glob, TP_PCT, HARD_EXIT, True, HARD_STOP_PCT, MAX_ENTRY_TIME)
                if s3: record_trade(all_trades, common_meta, '3. Opt_FVG (Inside)', s3)

    # --- REPORTING ---
    df_exp = pd.DataFrame(all_trades)
    if not df_exp.empty:
        df_exp.to_csv(CSV_PATH, index=False)
        
        stats = df_exp.groupby('Variant').agg({
            'Result': 'count',
            'Win': 'mean',
            'MFE_Pct': 'median',       # Realized Profit Pct
            'MFE_Delay_Mins': 'median',# Time to Realized Peak
            'MFE_EOD_Pct': 'median',   # Potential Profit Pct
            'MFE_EOD_Delay_Mins': 'median' # Time to Potential Peak
        })
        stats['Win'] *= 100
        stats = stats.rename(columns={'Result': 'Trades', 'Win': 'Win%'})
        
        print("\n| Variant | MedMFE (Real) | **Time to Peak (Real)** | MedMFE (Potential) | **Time to Peak (EOD)** |")
        print("|---|---|---|---|---|---|")
        for idx, row in stats.iterrows():
            print(f"| {idx} | {row['MFE_Pct']:.3f}% | {row['MFE_Delay_Mins']:.1f} min | {row['MFE_EOD_Pct']:.3f}% | {row['MFE_EOD_Delay_Mins']:.1f} min |")

    else:
        print("No trades found.")

def record_trade(log_list, meta, variant, res):
    row = meta.copy()
    row.update({
        'Variant': variant, 'Result': res['Result'], 'Win': 1 if res['Result'] == 'WIN' else 0,
        'MFE_Pct': res['MFE_Pct'], 'MFE_Delay_Mins': res['MFE_Delay_Mins'],
        'MFE_EOD_Pct': res['MF_EOD'], 'MFE_EOD_Delay_Mins': res['MF_EOD_Delay_Mins']
    })
    log_list.append(row)

# --- TRACKING LOGIC ---
def run_trade_logic(window, r_high, r_low, tp_pct, hard_exit_time, sl_long, sl_short, use_hard, hard_val, cutoff):
    pos = None; entry=0; sl=0; tp=0
    
    curr_mfe = 0; realized_mfe = 0; mf_eod = 0
    mfe_time = None; real_mfe_time = None; eod_mfe_time = None
    
    status = 'OPEN'; res_result = None
    
    for t, row in window.iterrows():
        # ENTRY
        if pos is None:
            if status == 'CLOSED': break 
            if cutoff and t.time() > cutoff: return None
            if t.time() >= hard_exit_time: return None
            
            if row['close'] > r_high: pos = 'LONG'; entry = row['close']; sl = sl_long
            elif row['close'] < r_low: pos = 'SHORT'; entry = row['close']; sl = sl_short
            
            if pos:
                curr_mfe = entry; mfe_time = t
                tp = entry * (1 + tp_pct) if pos == 'LONG' else entry * (1 - tp_pct)
                if use_hard:
                    risk = entry * hard_val
                    hsl = (entry - risk) if pos == 'LONG' else (entry + risk)
                    sl = max(sl, hsl) if pos == 'LONG' else min(sl, hsl)

        # MANAGEMENT
        else:
            # Update MFE
            if pos == 'LONG':
                if row['high'] > curr_mfe: curr_mfe = row['high']; mfe_time = t
            else:
                if row['low'] < curr_mfe: curr_mfe = row['low']; mfe_time = t
            
            # Realized Logic
            if status == 'OPEN':
                realized_mfe = curr_mfe; real_mfe_time = mfe_time
                
                exit_price = 0; reason = None
                if t.time() >= hard_exit_time: exit_price = row['close']; reason = "TIME"
                elif check_sl(pos, row, sl): exit_price = sl; reason = "SL"
                elif check_tp(pos, row, tp): exit_price = tp; reason = "TP"
                
                if reason:
                    pnl = exit_price - entry if pos == 'LONG' else entry - exit_price
                    res_result = 'WIN' if pnl > 0 else 'LOSS'; status = 'CLOSED'

    if pos is None: return None
    
    # Defaults if never closed (shouldnt happen with EOD window but safety)
    if status == 'OPEN': 
        realized_mfe = curr_mfe; real_mfe_time = mfe_time; res_result = 'LOSS'

    # Delays
    start_t = window.index[0] # Approx entry time? No, need actual entry time
    # We don't have exact entry time var stored in scope clearly (it was t in the loop)
    # Let's approximate Entry Time as MFE Time if realized delay is 0?
    # Better: store entry_t
    
    # FIX: Need correct entry time for calc.
    # Quick hack: If realized_mfe_time is None (instant loss?), use start.
    # Actually, let's just calc relative to *something* consistent if entry_t lost.
    # But wait, I can store entry_t!
    pass # See revised logic below to insert entry_t tracking properly

# Revised Logic Block for correct Time Tracking
def run_trade_logic_fixed(window, r_high, r_low, tp_pct, hard_exit_time, sl_long, sl_short, use_hard, hard_val, cutoff):
    pos = None; entry=0; sl=0; tp=0; entry_t = None
    
    curr_mfe = 0; realized_mfe = 0
    mfe_time = None; real_mfe_time = None
    
    status = 'OPEN'; res_result = None
    
    for t, row in window.iterrows():
        # ENTRY
        if pos is None:
            if status == 'CLOSED': break 
            if cutoff and t.time() > cutoff: return None
            if t.time() >= hard_exit_time: return None
            
            if row['close'] > r_high: pos = 'LONG'; entry = row['close']; sl = sl_long
            elif row['close'] < r_low: pos = 'SHORT'; entry = row['close']; sl = sl_short
            
            if pos:
                entry_t = t
                curr_mfe = entry; mfe_time = t
                tp = entry * (1 + tp_pct) if pos == 'LONG' else entry * (1 - tp_pct)
                if use_hard:
                    risk = entry * hard_val
                    hsl = (entry - risk) if pos == 'LONG' else (entry + risk)
                    sl = max(sl, hsl) if pos == 'LONG' else min(sl, hsl)

        # MANAGEMENT
        else:
            if pos == 'LONG':
                if row['high'] > curr_mfe: curr_mfe = row['high']; mfe_time = t
            else:
                if row['low'] < curr_mfe: curr_mfe = row['low']; mfe_time = t
            
            if status == 'OPEN':
                realized_mfe = curr_mfe; real_mfe_time = mfe_time
                exit_price = 0; reason = None
                if t.time() >= hard_exit_time: exit_price = row['close']; reason = "TIME"
                elif check_sl(pos, row, sl): exit_price = sl; reason = "SL"
                elif check_tp(pos, row, tp): exit_price = tp; reason = "TP"
                if reason:
                    pnl = exit_price - entry if pos == 'LONG' else entry - exit_price
                    res_result = 'WIN' if pnl > 0 else 'LOSS'; status = 'CLOSED'

    if pos is None: return None
    if status == 'OPEN': serialized_mfe = curr_mfe; real_mfe_time = mfe_time; res_result = 'LOSS'

    def calc_pct(price):
        if price == 0: return 0
        dist = (price - entry) if pos == 'LONG' else (entry - price)
        return (max(0, dist) / entry) * 100
    
    real_delay = (real_mfe_time - entry_t).total_seconds() / 60.0 if real_mfe_time else 0
    eod_delay = (mfe_time - entry_t).total_seconds() / 60.0 if mfe_time else 0

    return {
        'Result': res_result,
        'MFE_Pct': calc_pct(realized_mfe), 'MFE_Delay_Mins': real_delay,
        'MF_EOD': calc_pct(curr_mfe), 'MF_EOD_Delay_Mins': eod_delay
    }

def run_market_logic_fixed(window, direction, open_price, sl_long, sl_short, tp_pct, hard_exit, use_hard, hard_val, cutoff):
    if cutoff and window.index[0].time() > cutoff: return None
    pos = direction; entry = open_price; entry_t = window.index[0]
    curr_mfe = entry; realized_mfe = entry; mfe_time = entry_t; real_mfe_time = entry_t
    
    sl = sl_long if direction == 'LONG' else sl_short
    tp = entry * (1 + tp_pct) if pos == 'LONG' else entry * (1 - tp_pct)

    if use_hard:
        risk = entry * hard_val
        hsl = (entry - risk) if pos == 'LONG' else (entry + risk)
        sl = max(sl, hsl) if pos == 'LONG' else min(sl, hsl)

    status = 'OPEN'; res_result = None
    for t, row in window.iterrows():
        if pos == 'LONG':
            if row['high'] > curr_mfe: curr_mfe = row['high']; mfe_time = t
        else:
            if row['low'] < curr_mfe: curr_mfe = row['low']; mfe_time = t
            
        if status == 'OPEN':
            realized_mfe = curr_mfe; real_mfe_time = mfe_time
            exit_price = 0; reason = None
            if t.time() >= hard_exit: exit_price = row['close']; reason = "TIME"
            elif check_sl(pos, row, sl): exit_price = sl; reason = "SL"
            elif check_tp(pos, row, tp): exit_price = tp; reason = "TP"
            if reason:
                pnl = exit_price - entry if pos == 'LONG' else entry - exit_price
                res_result = 'WIN' if pnl > 0 else 'LOSS'; status = 'CLOSED'
                
    if status == 'OPEN': res_result = 'LOSS' # Default

    def calc_pct(price):
        if price == 0: return 0
        dist = (price - entry) if pos == 'LONG' else (entry - price)
        return (max(0, dist) / entry) * 100

    real_delay = (real_mfe_time - entry_t).total_seconds() / 60.0 if real_mfe_time else 0
    eod_delay = (mfe_time - entry_t).total_seconds() / 60.0 if mfe_time else 0

    return {
        'Result': res_result,
        'MFE_Pct': calc_pct(realized_mfe), 'MFE_Delay_Mins': real_delay,
        'MF_EOD': calc_pct(curr_mfe), 'MF_EOD_Delay_Mins': eod_delay
    }

def check_sl(pos, row, sl): return (row['low'] <= sl) if pos == 'LONG' else (row['high'] >= sl)
def check_tp(pos, row, tp): return (row['high'] >= tp) if pos == 'LONG' else (row['low'] <= tp)

# Re-map the functions to use fixed versions
run_trade_logic = run_trade_logic_fixed
run_market_logic = run_market_logic_fixed

if __name__ == "__main__":
    compare_optimized()
