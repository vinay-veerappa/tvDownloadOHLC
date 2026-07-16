
import pandas as pd
import numpy as np
import os
from datetime import time


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.nine_thirty_breakout.core.nine_thirty_strategy import NineThirtyStrategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

def compare_full_evolution(ticker="NQ1", years=5):
    print(f"Comparing V0 (Original) vs V1 (Baseline) vs V2 (Optimized) over {years} Years...")
    
    DATA_PATH = f"data/{ticker}_1m.parquet"
    if not os.path.exists(DATA_PATH): return
    df = pd.read_parquet(DATA_PATH)
    
    # Standard Preprocessing
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'time' in df.columns: 
            df['datetime'] = pd.to_datetime(df['time'], unit='s' if df['time'].iloc[0] > 1e10 else 'ms')
            df = df.set_index('datetime')
    df = df.sort_index()
    if df.index.tz is not None: df = df.tz_convert('US/Eastern')
    
    start_date = df.index[-1] - pd.Timedelta(days=years*365)
    df = df[df.index >= start_date]
    
    # Initialize Engine (ADR-009)
    engine = VectorizedBacktester(slippage_pct=0.0001)
    results = []

    # --- 0. ORIGINAL (RAW) ---
    v0_hunter = NineThirtyStrategy(variant='v0')
    v0_signals = v0_hunter.hunt(df, params={'sl_mode': 'STRUCT', 'tp_mode': 'NONE', 'exit_t': time(9,44)})
    v0_res = engine.run(v0_signals, df, {})
    results.append({'Variant': '0. Original (Raw)', 'PnL_Sum': v0_res['total_return_%'], 'Trades': v0_res['num_trades']})
    
    # --- 1. V1: BASELINE (Optimized Exit) ---
    v1_hunter = NineThirtyStrategy(variant='v1')
    v1_signals = v1_hunter.hunt(df, params={'sl_mode': 'STRUCT', 'tp_mode': 'FIXED', 'tp_pct': 0.0015, 'exit_t': time(10,0)})
    v1_res = engine.run(v1_signals, df, {})
    results.append({'Variant': '1. V1_Baseline', 'PnL_Sum': v1_res['total_return_%'], 'Trades': v1_res['num_trades']})
    
    # --- 2. V2: OPTIMIZED ---
    v2_hunter = NineThirtyStrategy(variant='v2')
    v2_signals = v2_hunter.hunt(df, params={'sl_mode': 'HYBRID', 'tp_mode': 'DYNAMIC', 'tp_mult': 0.8, 'avoid_tue': True, 'use_extreme_filter': True})
    v2_res = engine.run(v2_signals, df, {})
    results.append({'Variant': '2. V2_Optimized', 'PnL_Sum': v2_res['total_return_%'], 'Trades': v2_res['num_trades']})

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        print("\nSUMMARY (5 YEARS - VECTORIZED):")
        print(res_df.to_string())
    else:
        print("No trades found.")

if __name__ == "__main__":
    compare_full_evolution()

if __name__ == "__main__":
    compare_full_evolution()
