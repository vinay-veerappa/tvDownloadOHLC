
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

def test_pullback_efficiency(ticker="NQ1", years=5):
    days = years * 365
    print(f"Testing 9:30 Pullback Efficiency ({years} Year Analysis) for {ticker}...")
    
    # --- CONFIG ---
    HARD_EXIT = time(10, 0)
    CSV_PATH = "scripts/backtest/9_30_breakout/results/pullback_test_results.csv"
    os.makedirs("scripts/backtest/9_30_breakout/results", exist_ok=True)
    
    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path):
        print(f"Data not found at {data_path}")
        return
    df = pd.read_parquet(data_path)
    
    # TZ Handling
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df = df.tz_convert('US/Eastern')
    df = df.sort_index()

    start_date = df.index[-1] - pd.Timedelta(days=days)
    df = df[df.index >= start_date]
    df['date_only'] = df.index.normalize()
    dates = df['date_only'].unique()
    all_trades = [] 

    for d in dates:
        day_data = df[df['date_only'] == d]
        t930 = d + pd.Timedelta(hours=9, minutes=30)
        c930 = day_data[day_data.index == t930]
        if c930.empty: continue
        
        r_high = c930['high'].iloc[0]; r_low = c930['low'].iloc[0]
        r_open = c930['open'].iloc[0]
        if r_open == 0: continue
        r_size = r_high - r_low
        
        common_meta = { 'Date': d.date(), 'Range_High': r_high, 'Range_Low': r_low, 'Range_Size': r_size }
        
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        window = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        if window.empty: continue

        # VARIANTS TO TEST:
        # 1. Base (Breakout Cluster)
        # 2. PB_Retest (Entry at Range Boundary after breakout)
        # 3. PB_Midpoint (Entry at 50% of 9:30 candle)
        # 4. PB_Shallow_25 (Entry at 25% penetration into range)
        
        configs = [
            {'name': 'Base_Breakout', 'type': 'breakout', 'level': 0, 'sl_type': 'full'},
            {'name': 'PB_Retest', 'type': 'pullback', 'level': 0, 'sl_type': 'full'}, 
            {'name': 'PB_Midpoint', 'type': 'pullback', 'level': 0.5, 'sl_type': 'full'}, 
            {'name': 'PB_Shallow_25', 'type': 'pullback', 'level': 0.25, 'sl_type': 'full'},
            {'name': 'PB_Shallow_TightSL', 'type': 'pullback', 'level': 0.25, 'sl_type': 'half'} # Stop at 50% of range
        ]

        for cfg in configs:
            res = run_strategy(window, r_high, r_low, HARD_EXIT, cfg)
            if res:
                record_trade(all_trades, common_meta, cfg['name'], res)

    # Export & Summary
    df_exp = pd.DataFrame(all_trades)
    if not df_exp.empty:
        df_exp.to_csv(CSV_PATH, index=False)
        summary = df_exp.groupby('Variant').agg({
            'Result': 'count',
            'PnL_Pts': 'sum',
            'Win': 'mean',
            'MAE_Pts': 'mean',
            'MFE_Pts': 'mean'
        }).round(2)
        summary['Pts_Per_Trade'] = (summary['PnL_Pts'] / summary['Result']).round(2)
        print(f"\n--- {years} YEAR PULLBACK SUMMARY ---")
        print(summary.to_string())
        
        # Calculate Fill Rate relative to Base Breakout
        base_count = len(df_exp[df_exp['Variant'] == 'Base_Breakout'])
        print("\nFill Rates (vs Base Breakout):")
        for v in df_exp['Variant'].unique():
            if v == 'Base_Breakout': continue
            v_count = len(df_exp[df_exp['Variant'] == v])
            print(f"{v}: {v_count/base_count:.1%}")
    else:
        print("No trades found.")

def run_strategy(window, r_high, r_low, hard_exit, cfg):
    pos = None; entry=0; sl=0; mae=0; mfe=0; entry_t=None
    r_size = r_high - r_low
    
    state = 'WAIT_BREAK' if cfg['type'] == 'pullback' else 'ACTIVE'
    pb_level_long = r_high - (r_size * cfg['level'])
    pb_level_short = r_low + (r_size * cfg['level'])
    
    # SL Logic
    if cfg['sl_type'] == 'half':
        sl_long = r_high - (r_size * 0.5)
        sl_short = r_low + (r_size * 0.5)
    else:
        sl_long = r_low
        sl_short = r_high

    potential_pos = None

    for t, row in window.iterrows():
        if t.time() >= hard_exit: 
            if pos: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "TIME")
            else: return None

        if pos is None:
            if state == 'WAIT_BREAK':
                if row['close'] > r_high: 
                    potential_pos = 'LONG'; state = 'WAIT_PB'
                elif row['close'] < r_low: 
                    potential_pos = 'SHORT'; state = 'WAIT_PB'
            elif state == 'WAIT_PB':
                if potential_pos == 'LONG':
                    if row['low'] <= pb_level_long:
                        pos = 'LONG'; entry = pb_level_long
                        sl = sl_long; mae = entry; mfe = entry; entry_t = t
                else:
                    if row['high'] >= pb_level_short:
                        pos = 'SHORT'; entry = pb_level_short
                        sl = sl_short; mae = entry; mfe = entry; entry_t = t
                
                # Check if trade failed before filling (hit original SL)
                if potential_pos == 'LONG' and row['low'] <= r_low: return None
                if potential_pos == 'SHORT' and row['high'] >= r_high: return None
                
            else: # ACTIVE (Base Breakout)
                if row['close'] > r_high: 
                    pos = 'LONG'; entry = row['close']
                    sl = r_low; mae = entry; mfe = entry; entry_t = t
                elif row['close'] < r_low: 
                    pos = 'SHORT'; entry = row['close']
                    sl = r_high; mae = entry; mfe = entry; entry_t = t
        else:
            # Update MAE/MFE
            if pos == 'LONG': 
                mae = min(mae, row['low']); mfe = max(mfe, row['high'])
                if row['low'] <= sl: return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL")
            else: 
                mae = max(mae, row['high']); mfe = min(mfe, row['low'])
                if row['high'] >= sl: return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL")
                
    return None

def close_trade(pos, exit_price, exit_time, entry, entry_time, mae, mfe, reason):
    return {
        'Direction': pos, 'Entry': entry, 'Exit': exit_price, 'EntryTime': entry_time, 'ExitTime': exit_time,
        'MAE': mae, 'MFE': mfe, 'Reason': reason
    }

def record_trade(log_list, meta, variant, res):
    pos = res['Direction']
    entry = res['Entry']
    exit_p = res['Exit']
    pts = (exit_p - entry) if pos == 'LONG' else (entry - exit_p)
    
    mae_pts = (entry - res['MAE']) if pos == 'LONG' else (res['MAE'] - entry)
    mfe_pts = (res['MFE'] - entry) if pos == 'LONG' else (entry - res['MFE'])

    row = meta.copy()
    row.update({
        'Variant': variant, 'Direction': pos, 'Result': 'WIN' if pts > 0 else 'LOSS',
        'PnL_Pts': pts, 'MAE_Pts': mae_pts, 'MFE_Pts': mfe_pts,
        'Win': 1 if pts > 0 else 0
    })
    log_list.append(row)

if __name__ == "__main__":
    test_pullback_efficiency()
