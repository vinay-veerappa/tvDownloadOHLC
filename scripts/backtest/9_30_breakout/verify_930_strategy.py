
import pandas as pd
import numpy as np
import os
from datetime import time

def backtest_930_strategy(ticker="NQ1", days=30):
    print(f"Running 9:30 Breakout Backtest for {ticker} (Last {days} Days)...")
    
    # Load Data
    data_path = f"data/{ticker}_1m.parquet"
    if not os.path.exists(data_path):
        print(f"Data not found: {data_path}")
        return

    df = pd.read_parquet(data_path)
    
    # Ensure Datetime and Sort
    # (Assuming index is datetime or column exists)
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    
    df = df.sort_index()
    
    # Filter Last N Days
    end_date = df.index[-1]
    start_date = end_date - pd.Timedelta(days=days)
    df = df[df.index >= start_date]
    
    if df.empty:
        print("No data in range.")
        return

    print(f"Data Range: {df.index[0]} to {df.index[-1]}")
    
    # Strategy Params
    TP_R = 2.0
    HARD_EXIT = time(9, 44)
    
    trades = []
    
    # Group by Date
    # Need to handle Timezone? Assuming data is ET or we convert.
    # Check TZ
    if df.index.tz is None:
        pass # Assume ET or source TZ
    else:
        df = df.tz_convert('US/Eastern')
        
    dates = df.index.normalize().unique()
    
    for d in dates:
        day_data = df[df.index.normalize() == d]
        
        # 1. Define Range (09:30 Candle)
        t930 = d + pd.Timedelta(hours=9, minutes=30)
        candle_930 = day_data[day_data.index == t930]
        
        if candle_930.empty: continue
        
        range_high = candle_930['high'].iloc[0]
        range_low = candle_930['low'].iloc[0]
        range_size = range_high - range_low
        
        # 2. Execution Window (09:31 to Exit)
        exec_start = d + pd.Timedelta(hours=9, minutes=31)
        exec_end = d + pd.Timedelta(hours=HARD_EXIT.hour, minutes=HARD_EXIT.minute)
        
        window_data = day_data[(day_data.index >= exec_start) & (day_data.index <= exec_end)]
        
        position = None # 'LONG' or 'SHORT'
        entry_price = 0
        stop_loss = 0
        take_profit = 0
        entry_time = None
        
        for t, row in window_data.iterrows():
            # Check Entry
            if position is None:
                # 09:44 is hard exit, don't enter ON the hard exit candle if logic forbids (TS logic: if isHardExitTime, skip entry)
                if t.time() >= HARD_EXIT: break
                
                # Check Breakout
                if row['close'] > range_high:
                    position = 'LONG'
                    entry_price = row['close']
                    stop_loss = range_low
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * TP_R)
                    entry_time = t
                elif row['close'] < range_low:
                    position = 'SHORT'
                    entry_price = row['close']
                    stop_loss = range_high
                    risk = stop_loss - entry_price
                    take_profit = entry_price - (risk * TP_R)
                    entry_time = t
            
            # Manage Position
            else:
                # Check Exit
                exit_price = 0
                reason = ""
                pnl = 0
                
                # SL/TP logic (Simplistic: High/Low check within candle)
                
                if position == 'LONG':
                    if row['low'] <= stop_loss:
                        exit_price = stop_loss
                        pnl = exit_price - entry_price
                        reason = "SL"
                    elif row['high'] >= take_profit:
                        exit_price = take_profit
                        pnl = exit_price - entry_price
                        reason = "TP"
                    elif t.time() >= HARD_EXIT:
                        exit_price = row['close']
                        pnl = exit_price - entry_price
                        reason = "TIME"
                        
                elif position == 'SHORT':
                    if row['high'] >= stop_loss:
                        exit_price = stop_loss
                        pnl = entry_price - exit_price
                        reason = "SL"
                    elif row['low'] <= take_profit:
                        exit_price = take_profit
                        pnl = entry_price - exit_price
                        reason = "TP"
                    elif t.time() >= HARD_EXIT:
                        exit_price = row['close']
                        pnl = entry_price - exit_price
                        reason = "TIME"
                        
                if reason:
                    trades.append({
                        'EntryTime': entry_time,
                        'ExitTime': t,
                        'Direction': position,
                        'Entry': entry_price,
                        'Exit': exit_price,
                        'PnL': pnl,
                        'Result': 'WIN' if pnl > 0 else 'LOSS',
                        'Reason': reason
                    })
                    break # One trade per day
                    
    # Results
    if not trades:
        print("No trades found.")
        return

    df_res = pd.DataFrame(trades)
    print("\n--- Backtest Results ---")
    print(df_res.to_string(index=False))
    print("\nSummary:")
    print(f"Total Trades: {len(df_res)}")
    print(f"Win Rate: {(len(df_res[df_res['Result']=='WIN']) / len(df_res) * 100):.1f}%")
    print(f"Total PnL: {df_res['PnL'].sum():.2f}")

if __name__ == "__main__":
    backtest_930_strategy()
