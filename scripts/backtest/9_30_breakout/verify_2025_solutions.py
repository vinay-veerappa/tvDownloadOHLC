import pandas as pd
import numpy as np

def load_data():
    file_path = "data/NinjaTrader/24Dec2025/NQ Thursday 90.csv"
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, parse_dates=[['Date', 'Time']], usecols=[0,1,2,3,4,5], names=['Date', 'Time', 'Open', 'High', 'Low', 'Close'], header=0, on_bad_lines='skip')
    df.rename(columns={'Date_Time': 'datetime', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'}, inplace=True)
    df.set_index('datetime', inplace=True)
    df = df.sort_index()
    df = df['2025-01-01':]
    print(f"Loaded {len(df)} bars from 2025.")
    return df

def run_strategy(df, entry_mode="Immediate", confirm_pct=0.10, tp1_level=0.15, stop_after_win=True, start_time="09:31"):
    session_start_time = pd.Timestamp("09:30").time()
    session_end_time = pd.Timestamp("09:31").time()
    hard_exit_time = pd.Timestamp("11:00").time()
    trade_start_dt = pd.Timestamp(start_time).time()
    
    tp1_qty = 0.5
    runner_qty = 0.5
    
    trades = []
    
    for date, day_data in df.groupby(df.index.date):
        orb_data = day_data.between_time(session_start_time, session_end_time)
        if len(orb_data) == 0: continue
        
        r_high = orb_data['high'].max()
        r_low = orb_data['low'].min()
        r_size = r_high - r_low
        
        conf_long = r_high * (1 + confirm_pct/100)
        conf_short = r_low * (1 - confirm_pct/100)
        pb_long = r_high - (r_size * 0.25)
        pb_short = r_low + (r_size * 0.25)
        
        # Trade Logic
        trade_data = day_data.between_time(trade_start_dt, hard_exit_time)
        position = 0
        entry_price = 0
        sl_price = 0
        tp1_price = 0
        tp1_hit = False
        
        pending_long = False
        pending_short = False
        
        day_pnl_val = 0.0
        has_won_today = False
        
        for t, bar in trade_data.iterrows():
            if stop_after_win and has_won_today:
                if position == 0: break 
                
            if position != 0:
                if t.time() >= hard_exit_time:
                    pnl = (bar['close'] - entry_price) * position * (runner_qty if tp1_hit else 1.0)
                    trades.append({'PnL': pnl * 20})
                    day_pnl_val += pnl * 20
                    position = 0
                    if day_pnl_val > 10: has_won_today = True
                    continue

                if (position == 1 and bar['low'] <= sl_price) or (position == -1 and bar['high'] >= sl_price):
                    loss = abs(entry_price - sl_price) * -1
                    qty_left = runner_qty if tp1_hit else 1.0
                    trades.append({'PnL': loss * 20 * qty_left})
                    day_pnl_val += loss * 20 * qty_left
                    position = 0
                    if day_pnl_val > 10: has_won_today = True
                    continue
                
                if not tp1_hit:
                    if (position == 1 and bar['high'] >= tp1_price) or (position == -1 and bar['low'] <= tp1_price):
                        tp1_hit = True
                        gain = abs(tp1_price - entry_price)
                        trades.append({'PnL': gain * 20 * tp1_qty})
                        day_pnl_val += gain * 20 * tp1_qty
                        
            if position == 0 and not has_won_today:
                if entry_mode == "Immediate":
                    if bar['close'] > conf_long:
                         position = 1; entry_price = bar['close']; sl_price = r_low; tp1_price = entry_price * (1 + tp1_level/100); tp1_hit = False
                    elif bar['close'] < conf_short:
                         position = -1; entry_price = bar['close']; sl_price = r_high; tp1_price = entry_price * (1 - tp1_level/100); tp1_hit = False
                
                elif entry_mode == "Pullback":
                    if not pending_long and not pending_short:
                        if bar['close'] > conf_long and bar['close'] >= pb_long: pending_long = True
                        elif bar['close'] < conf_short and bar['close'] <= pb_short: pending_short = True
                    
                    if pending_long:
                        if bar['close'] < pb_long: pending_long = False
                        elif bar['low'] <= pb_long and bar['close'] > pb_long:
                            position = 1; entry_price = bar['close']; sl_price = r_low; tp1_price = entry_price * (1 + tp1_level/100); tp1_hit = False; pending_long = False
                            
                    if pending_short:
                        if bar['close'] > pb_short: pending_short = False
                        elif bar['high'] >= pb_short and bar['close'] < pb_short:
                            position = -1; entry_price = bar['close']; sl_price = r_high; tp1_price = entry_price * (1 - tp1_level/100); tp1_hit = False; pending_short = False

    total_pnl = sum([t['PnL'] for t in trades])
    count = len(trades)
    wr = len([t for t in trades if t['PnL'] > 0]) / count * 100 if count > 0 else 0
    
    print(f"--- {entry_mode} (TP1={tp1_level}%, Start={start_time}) ---")
    print(f"Net Profit: ${total_pnl:,.2f}")
    print(f"Trades: {count}")
    print(f"Win Rate: {wr:.2f}%")
    return total_pnl

if __name__ == "__main__":
    df = load_data()
    print("\nRunning Backtests for 2025...")
    run_strategy(df, entry_mode="Immediate", confirm_pct=0.10, tp1_level=0.15, stop_after_win=True, start_time="09:31")
    run_strategy(df, entry_mode="Immediate", confirm_pct=0.10, tp1_level=0.15, stop_after_win=True, start_time="10:00")
