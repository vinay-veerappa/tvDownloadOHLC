
import pandas as pd
import numpy as np
import os
from datetime import time

def compare_full_evolution(ticker="NQ1", years=5):
    print(f"Comparing V0 (Original) vs V1 (Baseline) vs V2 (Optimized) over {years} Years...")
    
    DATA_PATH = f"data/{ticker}_1m.parquet"
    if not os.path.exists(DATA_PATH): return
    df = pd.read_parquet(DATA_PATH)
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: 
            df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
            df = df.set_index('datetime')
    df = df.sort_index()
    if df.index.tz is not None: df = df.tz_convert('US/Eastern')
    
    start_date = df.index[-1] - pd.Timedelta(days=years*365)
    df = df[df.index >= start_date]
    
    df_930 = df.between_time('09:30', '09:30').copy()
    df_930['range_pct'] = (df_930['high'] - df_930['low']) / df_930['open']
    df_930['extreme_thresh'] = df_930['range_pct'].rolling(20).quantile(0.75)
    
    dates = df_930.index
    results = []
    df_by_day = df.groupby(df.index.normalize())
    
    for t930 in dates:
        d = t930.normalize()
        try: day_data = df_by_day.get_group(d)
        except KeyError: continue
        
        c930 = df_930.loc[t930]
        if isinstance(c930, pd.DataFrame): c930 = c930.iloc[0]
        
        # --- 0. ORIGINAL (RAW) ---
        # No TP, Structural SL, 9:44 Exit
        s0 = run_logic(day_data, c930, exit_t=time(9,44), tp_mode='NONE', tp_val=0, sl_mode='STRUCT', avoid_tue=False, extreme_filter=False)
        if s0: s0.update({'Variant': '0. Original (Raw)', 'Date': d.date()}); results.append(s0)
        
        # --- 1. V1: BASELINE (Optimized Exit) ---
        # 0.15% TP, Structural SL, 10:00 Exit
        s1 = run_logic(day_data, c930, exit_t=time(10,0), tp_mode='FIXED', tp_val=0.0015, sl_mode='STRUCT', avoid_tue=False, extreme_filter=False)
        if s1: s1.update({'Variant': '1. V1_Baseline', 'Date': d.date()}); results.append(s1)
        
        # --- 2. V2: OPTIMIZED ---
        # No Tue, 0.20% Stop, 80% Range TP, Extreme Filter, 10:00 Exit
        s2 = run_logic(day_data, c930, exit_t=time(10,0), tp_mode='DYNAMIC', tp_val=0.8, sl_mode='HYBRID', avoid_tue=True, extreme_filter=True, extreme_val=c930['extreme_thresh'])
        if s2: s2.update({'Variant': '2. V2_Optimized', 'Date': d.date()}); results.append(s2)

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        summary = res_df.groupby('Variant').agg({'PnL_Pct': ['sum', 'mean'], 'Win': 'mean', 'Date': 'count'}).round(4)
        summary.columns = ['_'.join(col).strip() for col in summary.columns.values]
        print("\nSUMMARY (5 YEARS):")
        print(summary.to_string())
        
        res_df['Year'] = pd.to_datetime(res_df['Date']).dt.year
        yearly = res_df.groupby(['Year', 'Variant'])['PnL_Pct'].sum().unstack()
        print("\nYEARLY PnL SUM:")
        print(yearly.to_string())
    else:
        print("No trades found.")

def run_logic(day_data, c930, exit_t, tp_mode, tp_val, sl_mode, avoid_tue, extreme_filter, extreme_val=0):
    d = day_data.index[0].normalize()
    if avoid_tue and d.dayofweek == 1: return None
    
    r_open = c930['open']; r_high = c930['high']; r_low = c930['low']
    r_range = r_high - r_low
    
    if extreme_filter and extreme_val > 0 and (r_range/r_open) > extreme_val: return None
    
    # Entry Window
    entry_win = day_data[(day_data.index.time >= time(9, 31)) & (day_data.index.time <= time(9, 35))]
    pos=None; entry=0; sl=0; tp=0
    
    for t, row in entry_win.iterrows():
        if row['close'] > r_high: 
            pos='LONG'; entry=row['close']
            sl = r_low if sl_mode == 'STRUCT' else max(r_low, entry*(1-0.0020))
            if tp_mode == 'FIXED': tp = entry * (1 + tp_val)
            elif tp_mode == 'DYNAMIC': tp = entry + r_range * tp_val
            else: tp = 9999999 # No TP
            break
        elif row['close'] < r_low: 
            pos='SHORT'; entry=row['close']
            sl = r_high if sl_mode == 'STRUCT' else min(r_high, entry*(1+0.0020))
            if tp_mode == 'FIXED': tp = entry * (1 - tp_val)
            elif tp_mode == 'DYNAMIC': tp = entry - r_range * tp_val
            else: tp = 0 # No TP
            break
    if not pos: return None
    
    # Management
    mgmt_win = day_data[(day_data.index.time >= time(9, 31)) & (day_data.index.time <= exit_t)]
    pnl = 0
    for t, row in mgmt_win.iterrows():
        if t.time() < time(9, 31): continue
        if t.time() >= exit_t:
            pnl = (row['close']-entry) if pos=='LONG' else (entry-row['close'])
            break
        if pos == 'LONG':
            if row['low'] <= sl: pnl = sl - entry; break
            if row['high'] >= tp: pnl = tp - entry; break
        else:
            if row['high'] >= sl: pnl = entry - sl; break
            if row['low'] <= tp: pnl = entry - tp; break
    return {'PnL_Pct': (pnl/entry)*100, 'Win': 1 if pnl > 0 else 0}

if __name__ == "__main__":
    compare_full_evolution()
