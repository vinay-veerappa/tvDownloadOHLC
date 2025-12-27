
import pandas as pd
import numpy as np
import os
from datetime import time, timedelta

def compare_strategies(ticker="NQ1", days=200):
    print(f"Comparing 9:30 Strategy Variants (200 Day Analysis) for {ticker}...")
    
    # --- CONFIG ---
    TPS = {'10bps': 0.0010, '20bps': 0.0020, '30bps': 0.0030}
    HARD_EXIT = time(10, 0)
    FVG_SCAN_MINS = 5 
    HUGE_DISP_PCT = 0.0020 
    CSV_PATH = "reports/930_backtest_all_trades.csv"
    os.makedirs("reports", exist_ok=True)
    
    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path): return
    df = pd.read_parquet(data_path)
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        elif 'datetime' in df.columns: df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    df = df.sort_index()
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
        r_close = c930['close'].iloc[0]; r_open = c930['open'].iloc[0]
        r_size_pct = ((r_high - r_low) / r_open) * 100
        
        common_meta = { 'Date': d.date(), 'Range_High': r_high, 'Range_Low': r_low, 'Range_Pct': r_size_pct }
        
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        window = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        if window.empty: continue

        # Global SL (Range Opposite)
        sl_long_glob = r_low; sl_short_glob = r_high

        # 1. ORIGINAL
        s1 = run_trade_logic(window, r_high, r_low, None, HARD_EXIT, sl_long_glob, sl_short_glob)
        # Original has no FVG notion, so FVG_Location is N/A
        if s1: record_trade(all_trades, common_meta, 'Original', s1, t930, TPS, 'N/A')

        # 2. IDENTIFY FVG
        fvg_dir = None; fvg_entry = 0; fvg_time = None; fvg_inv = 0
        fvg_top = 0; fvg_bot = 0; fvg_loc = "N/A"
        
        body_pct = abs(r_close - r_open) / r_open
        if body_pct > HUGE_DISP_PCT:
            fvg_time = t930
            if r_close > r_open: fvg_dir = 'LONG'; fvg_entry = r_high; fvg_inv = r_low; fvg_top = r_high; fvg_bot = r_low
            else: fvg_dir = 'SHORT'; fvg_entry = r_low; fvg_inv = r_high; fvg_top = r_high; fvg_bot = r_low
            fvg_loc = "HUGE_CANDLE"
        else:
            scan_end = d + pd.Timedelta(hours=9, minutes=30 + FVG_SCAN_MINS)
            scan_data = day_data[(day_data.index >= t930) & (day_data.index <= scan_end)]
            largest_gap = 0
            s_row = day_data.index.get_loc(t930); e_row = day_data.index.get_loc(scan_data.index[-1])
            
            for i in range(s_row + 1, e_row + 1):
                if i < 2: continue
                curr = day_data.iloc[i]; prev2 = day_data.iloc[i-2]
                
                # Bullish
                if curr['low'] > prev2['high']:
                    if prev2['high'] >= r_high or curr['close'] > r_high:
                        gap = curr['low'] - prev2['high']
                        if gap > largest_gap:
                            largest_gap = gap; fvg_dir = 'LONG'; fvg_entry = prev2['high']
                            fvg_inv = curr['low']; fvg_time = day_data.index[i]
                            fvg_top = curr['low']; fvg_bot = prev2['high']
                # Bearish
                elif curr['high'] < prev2['low']:
                    if prev2['low'] <= r_low or curr['close'] < r_low:
                        gap = prev2['low'] - curr['high']
                        if gap > largest_gap:
                            largest_gap = gap; fvg_dir = 'SHORT'; fvg_entry = prev2['low']
                            fvg_inv = curr['high']; fvg_time = day_data.index[i]
                            fvg_top = prev2['low']; fvg_bot = curr['high']
            
            # Determine Location
            if fvg_dir:
                # Inside if FVG Top <= Range High AND FVG Bot >= Range Low
                # Actually, FVG is the GAP itself.
                # Bullish GAP: Bot=Prev2_High, Top=Curr_Low.
                # Bearish GAP: Top=Prev2_Low, Bot=Curr_High (inverted terminology in var names above but logic holds)
                
                # Check Overlap
                # If Gap is fully inside Range
                is_below_top = fvg_top <= r_high
                is_above_bot = fvg_bot >= r_low
                
                # Correct logic for Bearish vars above:
                # Bearish: fvg_top was set to Prev2 Low (Top of Gap). fvg_bot set to Curr High (Bot of Gap).
                # Wait, "prev2['low'] - curr['high']" -> Gap is between Curr_High and Prev2_Low.
                # Prev2_Low is higher value. Curr_High is lower value.
                # So Top = prev2['low'], Bot = curr['high']. Correct.
                
                if fvg_dir == 'SHORT':
                    # Swap vars for consistent checking if needed? No, logic holds.
                    pass
                
                # Check strictly inside
                if fvg_bot >= r_low and fvg_top <= r_high:
                    fvg_loc = "Inside"
                else:
                    fvg_loc = "Outside"

        # 2. OPTION A (Limit)
        if fvg_dir:
            trade_window = window[window.index > fvg_time]
            if not trade_window.empty:
                s2 = run_limit_logic(trade_window, fvg_dir, fvg_entry, sl_long_glob, sl_short_glob, fvg_inv, HARD_EXIT)
                if s2: record_trade(all_trades, common_meta, 'OptA_Limit', s2, t930, TPS, fvg_loc)
        
        # 3. OPTION B (Market)
        if fvg_dir:
            market_time = fvg_time + pd.Timedelta(minutes=1)
            trade_window = window[window.index >= market_time]
            if not trade_window.empty:
                mkt_price = trade_window.iloc[0]['open']
                s3 = run_market_logic(trade_window, fvg_dir, mkt_price, sl_long_glob, sl_short_glob, fvg_inv, HARD_EXIT)
                if s3: record_trade(all_trades, common_meta, 'OptB_Market', s3, t930, TPS, fvg_loc)

    # --- EXPORT & SUMMARY ---
    df_exp = pd.DataFrame(all_trades)
    if not df_exp.empty:
        df_exp.to_csv(CSV_PATH, index=False)
        print("Detailed CSV saved.")
        
        # Summary
        summary = df_exp.groupby('Variant').agg({
            'Result': 'count',
            'Hit_10bps': 'mean',
            'Hit_20bps': 'mean',
            'Hit_30bps': 'mean',
            'PnL_Pct': 'mean'
        })
        for c in ['Hit_10bps', 'Hit_20bps', 'Hit_30bps', 'PnL_Pct']: summary[c] = summary[c] * 100
        print("\n--- 200 DAY SUMMARY ---")
        print(summary.to_string())
        
        # FVG LOCATION ANALYSIS (For Option B - Market)
        print("\n--- FVG LOCATION ANALYSIS (Option B Market) ---")
        opt_b = df_exp[df_exp['Variant'] == 'OptB_Market']
        if not opt_b.empty:
            loc_sum = opt_b.groupby('FVG_Location').agg({
                'Result': 'count',
                'Hit_10bps': 'mean',
                'Hit_30bps': 'mean',
                'PnL_Pct': 'mean'
            })
            for c in ['Hit_10bps', 'Hit_30bps', 'PnL_Pct']: loc_sum[c] = loc_sum[c] * 100
            print(loc_sum.to_string())
        
    else:
        print("No trades found.")

def record_trade(log_list, meta, variant, res, open_time, tps, fvg_loc):
    is_outside = False
    if res['Direction'] == 'LONG': is_outside = res['Entry'] > meta['Range_High']
    else: is_outside = res['Entry'] < meta['Range_Low']
    
    mfe_pct = res['MFE_Pct'] / 100.0
    hits = {k: (mfe_pct >= v) for k, v in tps.items()}
    
    row = meta.copy()
    row.update({
        'Variant': variant, 'Direction': res['Direction'], 'Result': res['Result'],
        'PnL_Pct': res['PnL_Pct'], 'MAE_Pct': res['MAE_Pct'], 'MFE_Pct': res['MFE_Pct'],
        'Entry_Time': res['EntryTime'].strftime('%H:%M:%S'), 'Exit_Time': res['ExitTime'].strftime('%H:%M:%S'),
        'Entry_Delay_Sec': (res['EntryTime'] - open_time).total_seconds(), 
        'Outside_Range': is_outside, 'FVG_Location': fvg_loc, 'Exit_Reason': res['Reason'],
        'Hit_10bps': hits['10bps'], 'Hit_20bps': hits['20bps'], 'Hit_30bps': hits['30bps']
    })
    log_list.append(row)

# --- CORE TRADING LOGIC (Same as before) ---
def run_trade_logic(window, r_high, r_low, tp_pct, hard_exit, sl_long, sl_short):
    pos = None; entry=0; sl=0; mae=0; mfe=0; entry_t=None
    for t, row in window.iterrows():
        if t.time() >= hard_exit: 
             if pos: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "TIME")
             else: return None
        if pos is None:
            if row['close'] > r_high: pos = 'LONG'; entry = row['close']; sl = sl_long; mae = entry; mfe = entry; entry_t = t
            elif row['close'] < r_low: pos = 'SHORT'; entry = row['close']; sl = sl_short; mae = entry; mfe = entry; entry_t = t
        else:
            mae, mfe = update_mae_mfe(pos, row, mae, mfe)
            if check_sl(pos, row, sl): return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL")
    return None

def run_limit_logic(window, direction, limit_price, sl_long, sl_short, inv_price, hard_exit):
    pos = None; entry=0; sl = sl_long if direction == 'LONG' else sl_short
    mae=0; mfe=0; entry_t=None
    for t, row in window.iterrows():
        if t.time() >= hard_exit: 
            if pos: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "TIME")
            else: return None
        if pos is None:
            filled = (row['low'] <= limit_price) if direction == 'LONG' else (row['high'] >= limit_price)
            if filled: pos = direction; entry = limit_price; mae = entry; mfe = entry; entry_t = t
        else:
            mae, mfe = update_mae_mfe(pos, row, mae, mfe)
            if check_inv(pos, row['close'], inv_price): return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "FVG_INV")
            if check_sl(pos, row, sl): return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL")
    return None

def run_market_logic(window, direction, open_price, sl_long, sl_short, inv_price, hard_exit):
    pos = direction; entry = open_price; mae = entry; mfe = entry; entry_t = window.index[0]
    sl = sl_long if direction == 'LONG' else sl_short
    for t, row in window.iterrows():
        if t.time() >= hard_exit: return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "TIME")
        mae, mfe = update_mae_mfe(pos, row, mae, mfe)
        if check_inv(pos, row['close'], inv_price): return close_trade(pos, row['close'], t, entry, entry_t, mae, mfe, "FVG_INV")
        if check_sl(pos, row, sl): return close_trade(pos, sl, t, entry, entry_t, mae, mfe, "SL")
    return None

def check_inv(pos, close, inv_level): return (close < inv_level) if pos == 'LONG' else (close > inv_level)
def update_mae_mfe(pos, row, mae, mfe):
    if pos == 'LONG': mae = min(mae, row['low']); mfe = max(mfe, row['high'])
    else: mae = max(mae, row['high']); mfe = min(mfe, row['low'])
    return mae, mfe
def check_sl(pos, row, sl): return (row['low'] <= sl) if pos == 'LONG' else (row['high'] >= sl)
def close_trade(pos, exit_price, exit_time, entry, entry_time, mae, mfe, reason):
    pnl_pts = exit_price - entry if pos == 'LONG' else entry - exit_price
    mae_pts = (entry - mae) if pos == 'LONG' else (mae - entry)
    mfe_pts = (mfe - entry) if pos == 'LONG' else (entry - mfe)
    return {
        'Result': 'WIN' if pnl_pts > 0 else 'LOSS',
        'PnL_Pct': (pnl_pts / entry) * 100,
        'MAE_Pct': (max(0, mae_pts) / entry) * 100,
        'MFE_Pct': (max(0, mfe_pts) / entry) * 100,
        'Reason': reason, 'Direction': pos, 'Entry': entry, 'EntryTime': entry_time, 'ExitTime': exit_time
    }

if __name__ == "__main__":
    compare_strategies()
