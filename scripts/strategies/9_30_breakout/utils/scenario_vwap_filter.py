"""
Scenario: V3 Strategy + VWAP Trend Filter
=========================================
Hypothesis: 40% of losers are "Fighting the Trend" (Price < VWAP for Longs).
Filter Logic:
- Long Entry: ONLY if Close > VWAP
- Short Entry: ONLY if Close < VWAP

Base: V3 Local Backtester (Verified)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from api.features.shared.data_loader import load_parquet

# --- CONFIGURATION (Match User's Verified Settings) ---
TICKER = "NQ1"
TIMEFRAME = "1m" 

# Strategy Params
SESSION_START_TIME = time(9, 30) 
TRADING_START_TIME = time(9, 31)
TRADING_END_TIME = time(15, 0)
HARD_EXIT_TIME = time(15, 55)

# Filters
MIN_RANGE_PCT = 0.03  
MAX_RANGE_PCT = 0.25  
MIN_DISPLACEMENT_PCT = 0.0 

# VVIX Filter
USE_VVIX_FILTER = True
VVIX_MAX = 108.0

# MAE Heat Filter
USE_MAE_FILTER = True
MAE_THRESHOLD_PCT = 0.10

# Targets (3 TPs)
TP_LEVELS = [0.0015, 0.0025, 0.0050] 
TP_WEIGHTS = [0.50, 0.25, 0.25]
MO_SL_TO_BE_AFTER_TP1 = True 

def load_vvix():
    try:
        path = r"c:\Users\vinay\tvDownloadOHLC\data\VVIX_1d.parquet"
        if not os.path.exists(path): return None
        v_df = pd.read_parquet(path)
        v_df = v_df.reset_index()
        time_col = v_df.columns[0]
        if pd.api.types.is_datetime64_any_dtype(v_df[time_col]):
            v_df['dt'] = v_df[time_col].dt.tz_localize('UTC').dt.tz_convert('America/New_York') if v_df[time_col].dt.tz is None else v_df[time_col].dt.tz_convert('America/New_York')
        else:
            v_df['dt'] = pd.to_datetime(v_df[time_col], utc=True).dt.tz_convert('America/New_York')
        v_df['date'] = v_df['dt'].dt.date
        if 'open' in v_df.columns: return v_df[['date', 'open']].rename(columns={'open': 'vvix_open'})
    except: return None
    return None


def load_vwap():
    # Load Precomputed VWAP
    try:
        path = r"c:\Users\vinay\tvDownloadOHLC\data\indicators\NQ1_1m_vwap.parquet"
        if not os.path.exists(path):
            print("VWAP file not found.")
            return None
        v_df = pd.read_parquet(path)
        # Ensure time alignment
        # Assuming matching timestamps with main file
        # Rename 'vwap' to stick
        return v_df[['time', 'vwap']]
    except Exception as e:
        print(f"Error loading VWAP: {e}")
        return None

def run_backtest():
    print(f"Loading {TICKER} {TIMEFRAME}...")
    df = load_parquet(TICKER, TIMEFRAME)
    if df is None: return

    # 1. Pre-process Time
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
    df['date'] = df['dt'].dt.date
    df['time_only'] = df['dt'].dt.time
    
    # Load VVIX
    if USE_VVIX_FILTER:
        vvix_df = load_vvix()
        if vvix_df is not None:
            df = pd.merge(df, vvix_df, on='date', how='left')
            df['vvix_open'] = df['vvix_open'].fillna(0)
            
    # Load VWAP
    print("Loading VWAP Data...")
    vwap_df = load_vwap()
    if vwap_df is not None:
        # Merge on 'time' (Unix timestamp match)
        df = pd.merge(df, vwap_df, on='time', how='left')
        # Fill NA VWAP with Close? Or leave NaN
        df['vwap'] = df['vwap'].fillna(df['close'])
    else:
        print("WARNING: VWAP not loaded. Filter will fail.")
        return

    # 2. Filter for 2023+
    start_date = pd.to_datetime("2023-01-01").date()
    df = df[df['date'] >= start_date].copy()
    df = df.sort_values('dt').reset_index(drop=True)
    
    days = df['date'].unique()
    trades = []
    
    print(f"Simulating {len(days)} days (2023-Present) with VWAP FILTER...")
    
    day_groups = df.groupby('date')
    
    for d, day_data in day_groups:
        if len(day_data) < 10: continue

        rows = list(day_data.itertuples(index=False))
        
        if USE_VVIX_FILTER and hasattr(rows[0], 'vvix_open'):
            day_vvix = rows[0].vvix_open
            if day_vvix > VVIX_MAX:
                continue 

        # Identify OR
        or_candle = None
        start_idx = -1
        for i, row in enumerate(rows):
            if row.time_only == SESSION_START_TIME:
                or_candle = row
                start_idx = i + 1
                break
        if not or_candle: continue
        
        r_high = or_candle.high
        r_low = or_candle.low
        r_size = r_high - r_low
        r_pct = (r_size / or_candle.close) * 100
        
        if r_pct < MIN_RANGE_PCT or r_pct > MAX_RANGE_PCT:
            continue
            
        disp_high = r_high * (1 + MIN_DISPLACEMENT_PCT)
        disp_low = r_low * (1 - MIN_DISPLACEMENT_PCT)
        
        in_trade = False
        direction = 0 
        entry_price = 0.0
        entry_time = None
        sl_price = 0.0
        tp_hits = [False, False, False]
        
        attempts = 0
        MAX_ATTEMPTS = 10 
        price_returned_to_range = True 
        
        if start_idx > 0: prev_close = rows[start_idx-1].close
        else: prev_close = rows[start_idx].open
        
        for i in range(start_idx, len(rows)):
            bar = rows[i]
            t = bar.time_only
            current_close = bar.close
            current_vwap = bar.vwap
            
            if t >= HARD_EXIT_TIME:
                if in_trade:
                    exit_price = bar.close
                    pnl_pct = (exit_price - entry_price) / entry_price * direction
                    trades.append({'Entry Time': entry_time, 'Exit Time': t, 'Type': 'Hard Exit', 'Entry Price': entry_price, 'Exit Price': exit_price, 'Gross P&L %': pnl_pct, 'Direction': direction})
                break
            
            if t > TRADING_END_TIME and not in_trade:
                break
            
            if not in_trade:
                if r_low <= current_close <= r_high:
                    price_returned_to_range = True
                
            if not in_trade:
                if attempts >= MAX_ATTEMPTS:
                    pass
                else:
                    # Breakout
                    breakout_long = (prev_close <= r_high) and (current_close > r_high) and (current_close >= disp_high)
                    breakout_short = (prev_close >= r_low) and (current_close < r_low) and (current_close <= disp_low)
                    
                    # APPLY VWAP FILTER
                    # Long: Price must be ABOVE VWAP
                    if breakout_long and (current_close < current_vwap):
                        breakout_long = False # Filtered Out
                        
                    # Short: Price must be BELOW VWAP
                    if breakout_short and (current_close > current_vwap):
                        breakout_short = False # Filtered Out
                    
                    is_eligible = True
                    
                    if (breakout_long or breakout_short) and is_eligible:
                        in_trade = True
                        attempts += 1
                        direction = 1 if breakout_long else -1
                        entry_price = current_close
                        entry_time = bar.dt
                        sl_price = r_low if direction == 1 else r_high
                        price_returned_to_range = False
                        tp_hits = [False, False, False] 
                        
            else:
                row_high = bar.high
                row_low = bar.low
                
                mae_hit = False
                if USE_MAE_FILTER:
                    mae_dist = entry_price * MAE_THRESHOLD_PCT 
                    if direction == 1 and row_low < (entry_price - mae_dist): mae_hit = True
                    if direction == -1 and row_high > (entry_price + mae_dist): mae_hit = True
                    
                if mae_hit:
                    exit_price = (entry_price - mae_dist) if direction == 1 else (entry_price + mae_dist)
                    trades.append({'Entry Time': entry_time, 'Exit Time': t, 'Type': 'MAE Exit', 'Entry Price': entry_price, 'Exit Price': exit_price, 'Gross P&L %': (exit_price - entry_price)/entry_price * direction, 'Direction': direction})
                    in_trade = False
                
                else:
                    sl_hit = False
                    if direction == 1 and row_low <= sl_price: sl_hit = True
                    if direction == -1 and row_high >= sl_price: sl_hit = True
                        
                    if sl_hit:
                        trades.append({'Entry Time': entry_time, 'Exit Time': t, 'Type': 'SL Hit', 'Entry Price': entry_price, 'Exit Price': sl_price, 'Gross P&L %': (sl_price - entry_price)/entry_price * direction, 'Direction': direction})
                        in_trade = False
                    
                    else:
                        tps = []
                        for pct in TP_LEVELS:
                            if direction == 1: tps.append(entry_price * (1 + pct))
                            else: tps.append(entry_price * (1 - pct))
                            
                        for idx, target in enumerate(tps):
                            if tp_hits[idx]: continue 
                            hit = False
                            if direction == 1 and row_high >= target: hit = True
                            if direction == -1 and row_low <= target: hit = True
                            
                            if hit:
                                tp_hits[idx] = True
                                if idx == 0 and MO_SL_TO_BE_AFTER_TP1:
                                    sl_price = entry_price 
                                
                                trades.append({'Entry Time': entry_time, 'Exit Time': t, 'Type': f'TP{idx+1}', 'Entry Price': entry_price, 'Exit Price': target, 'Gross P&L %': (target - entry_price)/entry_price * direction, 'Direction': direction})
                                
                        if all(tp_hits):
                            in_trade = False
            
            prev_close = current_close


    if not trades:
        print("No trades generated.")
        return
        
    res_df = pd.DataFrame(trades)
    print(f"Generated {len(res_df)} sub-trades.")
    unique_trades = res_df['Entry Time'].nunique()
    print(f"Unique Trades: {unique_trades}")
    res_df.to_csv("scenario_vwap_results.csv", index=False)
    print("Saved to scenario_vwap_results.csv")

if __name__ == "__main__":
    run_backtest()
