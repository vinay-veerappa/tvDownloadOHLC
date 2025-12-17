
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

def compare_runners(ticker="NQ1", days=200):
    print(f"Running RUNNER & BE SCENARIO Analysis for {ticker} (Last {days} Days)...")
    
    # --- CONFIG ---
    BE_TRIGGER = 0.0015         # 15 bps trigger to move to BE
    TP_1 = 0.0015               # Take 50% off here
    HARD_STOP = 0.0020          # Initial Risk
    ENTRY_CUTOFF = time(9, 35)
    EOD_EXIT = time(16, 0)      # Runner runs to EOD
    SESSION_EXIT = time(10, 0)  # Baseline exits here
    
    CSV_PATH = "reports/930_runners_comparison.csv"
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
        
        if c930.empty:
            # print(f"DEBUG: {d.date()} - No 9:30 candle found.")
            continue
        
        r_high = c930['high'].iloc[0]; r_low = c930['low'].iloc[0]
        common_meta = { 'Date': d.date() }
        
        # We need EOD data for runners
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=16, minutes=0)
        window = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        
        if window.empty: 
            print(f"DEBUG: {d.date()} - Window empty (09:31-16:00).")
            continue
        
        sl_long_str = r_low; sl_short_str = r_high

        # -------------------------------------------------------------
        # 1. BASELINE (Optimized Breakout: Exit 10am)
        # -------------------------------------------------------------
        # For baseline, limit window to 10am using robust datetime comparison
        limit_time = d + pd.Timedelta(hours=10, minutes=0)
        win_base = window[window.index <= limit_time]
        if not win_base.empty:
            s1 = run_baseline(win_base, r_high, r_low, sl_long_str, sl_short_str, HARD_STOP, ENTRY_CUTOFF, SESSION_EXIT)
            if s1: record_trade(all_trades, common_meta, '1. Baseline (Exit 10am)', s1)

        # -------------------------------------------------------------
        # 2. BE_HOLD (Hit 15bps -> Move SL to BE -> Hold to EOD)
        # -------------------------------------------------------------
        s2 = run_be_hold(window, r_high, r_low, sl_long_str, sl_short_str, HARD_STOP, ENTRY_CUTOFF, EOD_EXIT, BE_TRIGGER)
        if s2: record_trade(all_trades, common_meta, '2. BE & Hold (to EOD)', s2)
        
        # -------------------------------------------------------------
        # 3. RUNNER (50% at 15bps -> SL to BE -> Hold 50% EOD)
        # -------------------------------------------------------------
        s3 = run_runner(window, r_high, r_low, sl_long_str, sl_short_str, HARD_STOP, ENTRY_CUTOFF, EOD_EXIT, TP_1)
        if s3: record_trade(all_trades, common_meta, '3. Runner (50/50 Split)', s3)


    # --- REPORTING ---
    df_exp = pd.DataFrame(all_trades)
    if not df_exp.empty:
        df_exp.to_csv(CSV_PATH, index=False)
        
        stats = df_exp.groupby('Variant').agg({
            'Result': 'count',
            'Win': 'mean',
            'PnL_Pct': ['sum', 'mean', 'median'],
            'Stopped_BE': 'mean' # % of trades stopped at BE
        })
        
        stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
        stats = stats.rename(columns={'Result_count': 'Trades', 'Win_mean': 'Win%', 'PnL_Pct_sum': 'TotPnL', 
                                    'Stopped_BE_mean': 'BE_Rate'})
        
        stats['Win%'] *= 100; stats['BE_Rate'] *= 100
        
        print("\n" + stats.round(4).to_string())
        
        # Analysis of Losers
        print("\n--- LOSS ANALYSIS ---")
        losers = df_exp[df_exp['Result'] == 'LOSS']
        if not losers.empty:
            l_stats = losers.groupby(['Variant', 'Exit_Reason']).size().unstack(fill_value=0)
            print(l_stats.to_string())

    else:
        print("No trades found.")

def record_trade(log_list, meta, variant, res):
    row = meta.copy()
    row.update(res)
    row.update({'Variant': variant, 'Win': 1 if res['Result'] == 'WIN' else 0})
    log_list.append(row)

# --- BASELINE LOGIC ---
def run_baseline(window, r_high, r_low, sl_l, sl_s, hard, cutoff, hard_exit):
    tp_pct = 0.0015 
    pos=None; entry=0; sl=0; tp=0
    
    for t, row in window.iterrows():
        if t.time() >= hard_exit: 
            if pos: return close(pos, row['close'], entry, "TIME", False)
            return None
        if pos is None and t.time() > cutoff: return None
        
        if pos is None:
            if row['close'] > r_high: pos='LONG'; entry=row['close']; sl=sl_l
            elif row['close'] < r_low: pos='SHORT'; entry=row['close']; sl=sl_s
            
            if pos:
                risk = entry*hard; hsl = (entry-risk) if pos=='LONG' else (entry+risk)
                sl = max(sl, hsl) if pos=='LONG' else min(sl, hsl)
                tp = entry*(1+tp_pct) if pos=='LONG' else entry*(1-tp_pct)
        else:
            if check_sl(pos, row, sl): return close(pos, sl, entry, "SL", False)
            if check_tp(pos, row, tp): return close(pos, tp, entry, "TP", False)
    return None

# --- BE & HOLD LOGIC ---
def run_be_hold(window, r_high, r_low, sl_l, sl_s, hard, cutoff, eod_exit, be_trigger):
    pos=None; entry=0; sl=0; is_be=False
    
    for t, row in window.iterrows():
        if t.time() >= eod_exit: 
             if pos: return close(pos, row['close'], entry, "TIME", is_be)
             return None
        if pos is None and t.time() > cutoff: return None
        
        if pos is None:
            if row['close'] > r_high: pos='LONG'; entry=row['close']; sl=sl_l
            elif row['close'] < r_low: pos='SHORT'; entry=row['close']; sl=sl_s
            if pos:
                risk = entry*hard; hsl = (entry-risk) if pos=='LONG' else (entry+risk)
                sl = max(sl, hsl) if pos=='LONG' else min(sl, hsl)
        else:
            # Check BE Trigger
            curr_profit = (row['high'] - entry) if pos=='LONG' else (entry - row['low'])
            if not is_be and (curr_profit / entry) >= be_trigger:
                sl = entry # Move to Breakeven
                is_be = True
            
            if check_sl(pos, row, sl): 
                reason = "BE_STOP" if is_be else "SL"
                return close(pos, sl, entry, reason, is_be)
            # NO TP - Hold to EOD 
    return None

# --- RUNNER LOGIC (50/50) ---
def run_runner(window, r_high, r_low, sl_l, sl_s, hard, cutoff, eod_exit, tp1_val):
    pos=None; entry=0; sl=0; took_tp1=False
    
    for t, row in window.iterrows():
        if t.time() >= eod_exit: 
             if pos: return close_runner(pos, row['close'], entry, "TIME", took_tp1, tp1_val)
             return None
        if pos is None and t.time() > cutoff: return None
        
        if pos is None:
            if row['close'] > r_high: pos='LONG'; entry=row['close']; sl=sl_l
            elif row['close'] < r_low: pos='SHORT'; entry=row['close']; sl=sl_s
            if pos:
                risk = entry*hard; hsl = (entry-risk) if pos=='LONG' else (entry+risk)
                sl = max(sl, hsl) if pos=='LONG' else min(sl, hsl)
                tp1 = entry*(1+tp1_val) if pos=='LONG' else entry*(1-tp1_val)
        else:
            # Check TP1
            if not took_tp1:
                 if check_tp(pos, row, tp1):
                     took_tp1 = True
                     sl = entry # Move remainder to BE
            
            if check_sl(pos, row, sl):
                reason = "BE_STOP" if took_tp1 else "SL"
                return close_runner(pos, sl, entry, reason, took_tp1, tp1_val)
    return None

def close(pos, price, entry, reason, stopped_be):
    pnl = price - entry if pos=='LONG' else entry - price
    return { 
        'Result': 'WIN' if pnl > 0 or stopped_be else 'LOSS', # BE is technically not a loss? Or 0 PnL
        'PnL_Pct': (pnl/entry)*100, 
        'Exit_Reason': reason, 'Stopped_BE': 1 if stopped_be and reason in ['BE_STOP', 'SL'] else 0
    }

def close_runner(pos, final_price, entry, reason, took_tp1, tp1_pct):
    # PnL Calculation
    # Part 1: Half sold at TP1 (if taken)
    pnl_1 = tp1_pct if took_tp1 else 0
    
    # Part 2: Half sold at final_price
    # If not took_tp1, then FULL position sold at final_price (SL or Time)
    final_pnl_raw = (final_price - entry) if pos=='LONG' else (entry - final_price)
    pnl_2_pct = (final_pnl_raw / entry)
    
    if took_tp1:
        total_pnl = (0.5 * pnl_1) + (0.5 * pnl_2_pct)
        # Even if runner stops at BE (pnl_2 = 0), total is positive
    else:
        total_pnl = pnl_2_pct # Full position took loss
        
    return {
        'Result': 'WIN' if total_pnl > 0 else 'LOSS',
        'PnL_Pct': total_pnl * 100,
        'Exit_Reason': reason, 'Stopped_BE': 1 if reason == 'BE_STOP' else 0
    }

def check_sl(pos, row, sl): return (row['low'] <= sl) if pos == 'LONG' else (row['high'] >= sl)
def check_tp(pos, row, tp): return (row['high'] >= tp) if pos == 'LONG' else (row['low'] <= tp)

if __name__ == "__main__":
    compare_runners()
