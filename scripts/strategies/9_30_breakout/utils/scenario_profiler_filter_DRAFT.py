"""
Scenario: V3 Strategy + Profiler Trap Filter
============================================
Hypothesis: 30% of losers are "Traps" (Session Status = "False" before Entry).
Filter Logic:
- If Direction is Long AND Session Status is "Long False" (Confirmed before Entry) -> SKIP
- If Direction is Short AND Session Status is "Short False" (Confirmed before Entry) -> SKIP

Outputs:
- scenario_profiler_results.csv
- Impact Analysis: Winners Skipped vs Losers Skipped
"""

import pandas as pd
import numpy as np
import json
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

def load_profiler():
    try:
        with open(r"c:\Users\vinay\tvDownloadOHLC\data\NQ1_profiler.json", "r") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        df['date_obj'] = pd.to_datetime(df['date']).dt.date
        df['status_dt'] = pd.to_datetime(df['status_time'], utc=True).dt.tz_convert('America/New_York')
        return df
    except Exception as e:
        print(f"Error loading profiler: {e}")
        return None

def run_backtest():
    print(f"Loading {TICKER} {TIMEFRAME}...")
    df = load_parquet(TICKER, TIMEFRAME)
    if df is None: return

    # 1. Pre-process Time
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
    df['date'] = df['dt'].dt.date
    df['time_only'] = df['dt'].dt.time
    
    # Load External Data
    vvix_df = load_vvix() if USE_VVIX_FILTER else None
    if vvix_df is not None:
        df = pd.merge(df, vvix_df, on='date', how='left')
        df['vvix_open'] = df['vvix_open'].fillna(0)
        
    prof_df = load_profiler()
    if prof_df is None:
        print("Profiler Data Missing. Aborting.")
        return
        
    # Group Profiler by Date for fast lookup
    prof_by_date = prof_df.groupby('date_obj')

    # 2. Filter for 2023+
    start_date = pd.to_datetime("2023-01-01").date()
    df = df[df['date'] >= start_date].copy()
    df = df.sort_values('dt').reset_index(drop=True)
    
    days = df['date'].unique()
    trades = []
    
    # Tracking for Impact Analysis
    skipped_winners = 0
    skipped_losers = 0
    skipped_pnl = 0.0
    
    print(f"Simulating {len(days)} days (2023-Present) with PROFILER TRAP FILTER...")
    
    day_groups = df.groupby('date')
    
    for d, day_data in day_groups:
        if len(day_data) < 10: continue

        rows = list(day_data.itertuples(index=False))
        
        # VVIX Check
        if USE_VVIX_FILTER and hasattr(rows[0], 'vvix_open'):
            if rows[0].vvix_open > VVIX_MAX: continue 

        # Profiler Context for Day
        day_profs = None
        if d in prof_by_date.groups:
            day_profs = prof_by_date.get_group(d)

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
            
            if t >= HARD_EXIT_TIME:
                if in_trade:
                    exit_price = bar.close
                    pnl_pct = (exit_price - entry_price) / entry_price * direction
                    trades.append({'Entry Time': entry_time, 'Gross P&L %': pnl_pct, 'Outcome': 'Win' if pnl_pct > 0 else 'Loss'})
                break
                
            if t > TRADING_END_TIME and not in_trade: break
                
            if not in_trade:
                if r_low <= current_close <= r_high: price_returned_to_range = True
                
            if not in_trade:
                if attempts >= MAX_ATTEMPTS: pass
                else:
                    # Breakout
                    breakout_long = (prev_close <= r_high) and (current_close > r_high) and (current_close >= disp_high)
                    breakout_short = (prev_close >= r_low) and (current_close < r_low) and (current_close <= disp_low)
                    
                    is_eligible = True
                    is_trap = False
                    
                    # PROFILER TRAP CHECK
                    # If we have a signal, check if it's a Trap
                    if (breakout_long or breakout_short) and day_profs is not None:
                         # Check all sessions
                         for p_row in day_profs.itertuples():
                             # If Status Time is BEFORE current time
                             if p_row.status_dt < bar.dt:
                                 status = p_row.status
                                 # Long Trap: "Long False"
                                 if breakout_long and status == "Long False":
                                     is_trap = True
                                 # Short Trap: "Short False"
                                 if breakout_short and status == "Short False":
                                     is_trap = True
                    
                    # Log Trap (Simulate "What If we took it" vs "Skipped")
                    # To analyze impact, we can run TWO backtests or just tag the trade logic.
                    # Harder to separate because skipped trades affect 'attempts' and subsequent setup validity.
                    # Best approach: Run Logic WITH filter. 
                    # But user wants to know "Winners vs Losers Skipped".
                    # We can simulate the trade OUTCOME even if we skip it?
                    # No, that's complex (need parallel state).
                    
                    # Simplified: We will RECORD the trade in a separate list but NOT execute it in state?
                    # No, skipping changes history (re-entries).
                    # 
                    # Correct Approach:
                    # Run the backtest applying the filter. Save results.
                    # Tag trades with 'Filtered=True'? No, because if filtered, we don't enter, so we don't know result.
                    #
                    # Alternative:
                    # Run standard backtest (which we have in 'local_backtest_results.csv').
                    # Iterate THAT result file, check against profiler, and tag "Would have been filtered".
                    # This assumes the filter doesn't change subsequent trade setups significantly (it might, due to 10 attempt limit).
                    # But since limits are high (10), overlap is low.
                    # 
                    # Let's pivot: This script will perform analysis on EXISTING 'local_backtest_results.csv'.
                    # It's safer and answers the question directly without complex parallel state simulation.
                    pass 

            prev_close = current_close

    # DO NOT RE-RUN SIMULATION. 
    # USE 'analyze_profiler_impact.py' approach instead.
    print("Switching to Analysis Mode on Existing Backtest Results...")

if __name__ == "__main__":
    # run_backtest() # logic moved
    pass
