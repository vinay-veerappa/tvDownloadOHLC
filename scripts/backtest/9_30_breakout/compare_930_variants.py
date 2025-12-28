
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

def compare_strategies(ticker="NQ1", years=5):
    days = years * 365
    print(f"Comparing 9:30 Strategy Variants ({years} Year Analysis) for {ticker}...")
    
    # --- CONFIG ---
    TPS = {'10bps': 0.0010, '20bps': 0.0020, '30bps': 0.0030}
    HARD_EXIT = time(10, 0)
    MAX_ATTEMPTS = 3
    PENETRATION_THH = 0.0 # Strict Exit (Close inside range)
    CSV_PATH = "scripts/backtest/9_30_breakout/results/930_backtest_all_trades.csv"
    os.makedirs("scripts/backtest/9_30_breakout/results", exist_ok=True)
    
    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path):
        print(f"Data not found at {data_path}")
        return
    df = pd.read_parquet(data_path)
    
    # Robust TZ Handling
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            # Unix timestamp check
            first_val = df['time'].iloc[0]
            unit = 's' if first_val < 1e11 else 'ms'
            df['datetime'] = pd.to_datetime(df['time'], unit=unit)
            df = df.set_index('datetime')
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
    
    if df.index.tz is None:
        # If naive, assume it's UTC (standard for our parquets)
        df.index = df.index.tz_localize('UTC')
    
    # Final convert to ET
    df = df.tz_convert('US/Eastern')
    df = df.sort_index()

    start_date = df.index[-1] - pd.Timedelta(days=days)
    df = df[df.index >= start_date]
    df['date_only'] = df.index.normalize()
    dates = df['date_only'].unique()
    all_trades = [] 

    print(f"Backtesting from {df.index[0]} to {df.index[-1]}")

    for d in dates:
        day_data = df[df['date_only'] == d]
        t930 = d + pd.Timedelta(hours=9, minutes=30)
        c930 = day_data[day_data.index == t930]
        if c930.empty: continue
        
        r_high = c930['high'].iloc[0]; r_low = c930['low'].iloc[0]
        r_open = c930['open'].iloc[0]
        r_size_pts = r_high - r_low
        if r_open == 0: continue
        r_size_pct = (r_size_pts / r_open) * 100
        
        common_meta = { 'Date': d.date(), 'Range_High': r_high, 'Range_Low': r_low, 'Range_Pct': r_size_pct }
        
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        window = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        if window.empty: continue

        # 1. RUN BASE STRATEGY (1 Attempt, No Scale-out)
        s1_results = run_multi_attempt_logic(window, r_high, r_low, HARD_EXIT, max_attempts=1, scale_out=False, penetration=PENETRATION_THH)
        for res in s1_results: record_trade(all_trades, common_meta, 'Base_1Att', res, t930, TPS)

        # 2. RUN BASE STRATEGY (1 Attempt, NO EARLY EXIT)
        s1b_results = run_multi_attempt_logic(window, r_high, r_low, HARD_EXIT, max_attempts=1, scale_out=False, penetration=None)
        for res in s1b_results: record_trade(all_trades, common_meta, 'Base_NoEarlyExit', res, t930, TPS)

        # 3. RUN ENHANCED STRATEGY (3 Attempts, Scale-out 'Covering the Queen')
        s2_results = run_multi_attempt_logic(window, r_high, r_low, HARD_EXIT, max_attempts=MAX_ATTEMPTS, scale_out=True, penetration=PENETRATION_THH)
        for res in s2_results: record_trade(all_trades, common_meta, 'Enhanced_3Att_CTQ', res, t930, TPS)

    # --- EXPORT & SUMMARY ---
    df_exp = pd.DataFrame(all_trades)
    if not df_exp.empty:
        df_exp.to_csv(CSV_PATH, index=False)
        print(f"Detailed CSV saved to {CSV_PATH}")
        
        # Summary
        summary = df_exp.groupby('Variant').agg({
            'Result': 'count',
            'PnL_Pct': 'sum',
            'Win': 'mean',
            'MAE_Pct': 'mean',
            'MFE_Pct': 'mean'
        }).round(6)
        print(f"\n--- {years} YEAR SUMMARY ---")
        print(summary.to_string())
    else:
        print("No trades found.")

def run_multi_attempt_logic(window, r_high, r_low, hard_exit, max_attempts, scale_out, penetration):
    results = []
    attempts = 0
    current_idx = 0
    
    while attempts < max_attempts and current_idx < len(window):
        # Look for next entry
        res = run_single_trade(window.iloc[current_idx:], r_high, r_low, hard_exit, scale_out, penetration)
        if res:
            results.append(res)
            attempts += 1
            # Advance index to after this trade's exit
            # Find the index of ExitTime in window
            exit_time = res['ExitTime']
            try:
                # Use searchsorted if possibly faster, but bit complex with DatetimeIndex
                # Let's use get_loc or simple comparison
                current_idx = window.index.get_loc(exit_time) + 1
            except:
                # If exit_time is last, loop will break
                break
        else:
            break
    return results

def run_single_trade(sub_window, r_high, r_low, hard_exit, scale_out, penetration):
    pos = None; entry=0; sl=0; mae=0; mfe=0; entry_t=None
    tp1 = 0; tp1_hit = False
    r_size = r_high - r_low
    
    for t, row in sub_window.iterrows():
        if t.time() >= hard_exit: 
             if pos: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "TIME", tp1_hit)
             else: return None
             
        if pos is None:
            if row['close'] > r_high: 
                pos = 'LONG'; entry = row['close']
                sl = r_low; mae = entry; mfe = entry; entry_t = t
                tp1 = entry + r_size # 1R Target
            elif row['close'] < r_low: 
                pos = 'SHORT'; entry = row['close']
                sl = r_high; mae = entry; mfe = entry; entry_t = t
                tp1 = entry - r_size # 1R Target
        else:
            # Update MAE/MFE
            if pos == 'LONG': 
                mae = min(mae, row['low']); mfe = max(mfe, row['high'])
            else: 
                mae = max(mae, row['high']); mfe = min(mfe, row['low'])
            
            # Check Scale-out (Cover the Queen)
            if scale_out and not tp1_hit:
                hit = (row['high'] >= tp1) if pos == 'LONG' else (row['low'] <= tp1)
                if hit:
                    tp1_hit = True
                    sl = entry # Move SL to Break-even
            
            # Check SL (Wick based)
            is_sl = (row['low'] <= sl) if pos == 'LONG' else (row['high'] >= sl)
            if is_sl: return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL", tp1_hit)
            
            # Check Early Exit (Close inside penetration zone)
            if penetration is not None:
                if pos == 'LONG':
                    thresh = r_high - (r_size * penetration)
                    if row['close'] <= thresh: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "EARLY_EXIT", tp1_hit)
                else:
                    thresh = r_low + (r_size * penetration)
                    if row['close'] >= thresh: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "EARLY_EXIT", tp1_hit)
                
    return None

def close_trade(pos, exit_price, exit_time, entry, entry_time, mae, mfe, reason, tp1_hit):
    return {
        'Direction': pos, 'Entry': entry, 'Exit': exit_price, 'EntryTime': entry_time, 'ExitTime': exit_time,
        'MAE': mae, 'MFE': mfe, 'Reason': reason, 'TP1_Hit': tp1_hit
    }

def record_trade(log_list, meta, variant, res, open_time, tps):
    pos = res['Direction']
    entry = res['Entry']
    exit_p = res['Exit']
    tp1_hit = res['TP1_Hit']
    
    # Calculate PnL (Accounting for "Covering the Queen")
    r_size = meta['Range_High'] - meta['Range_Low']
    if pos == 'LONG':
        tp1_price = entry + r_size
        if tp1_hit:
            pnl_pts = 0.5 * (tp1_price - entry) + 0.5 * (exit_p - entry)
        else:
            pnl_pts = exit_p - entry
        mae_pts = entry - res['MAE']
        mfe_pts = res['MFE'] - entry
    else:
        tp1_price = entry - r_size
        if tp1_hit:
            pnl_pts = 0.5 * (entry - tp1_price) + 0.5 * (entry - exit_p)
        else:
            pnl_pts = entry - exit_p
        mae_pts = res['MAE'] - entry
        mfe_pts = entry - res['MFE']
        
    pnl_pct = (pnl_pts / entry) * 100 if entry != 0 else 0
    mae_pct = (max(0, mae_pts) / entry) * 100 if entry != 0 else 0
    mfe_pct = (max(0, mfe_pts) / entry) * 100 if entry != 0 else 0
    
    row = meta.copy()
    row.update({
        'Variant': variant, 'Direction': pos, 'Result': 'WIN' if pnl_pts > 0 else 'LOSS',
        'PnL_Pts': pnl_pts, 'PnL_Pct': pnl_pct, 'MAE_Pct': mae_pct, 'MFE_Pct': mfe_pct,
        'Entry_Time': res['EntryTime'].strftime('%H:%M:%S'), 'Exit_Time': res['ExitTime'].strftime('%H:%M:%S'),
        'Exit_Reason': res['Reason'], 'TP1_Hit': tp1_hit, 'Win': 1 if pnl_pts > 0 else 0
    })
    log_list.append(row)

if __name__ == "__main__":
    compare_strategies()
