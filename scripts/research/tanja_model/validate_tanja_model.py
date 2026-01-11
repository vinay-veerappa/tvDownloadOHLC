"""
930 Tanja Model Validation (Vectorized)
=======================================
Validates the strategy rules from Model_930_Tanja.pdf using efficient vectorization.

Rules to test:
1. 8:50-9:10 macro as consolidation/liquidity zone
2. 9:20-9:29 range predicts Judas delivery timing
3. 9:28 directional candle
4. 932 relationship to 928

Key Concepts:
- Judas = False move that traps traders before real direction
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, time

DATA_DIR = Path("data")
TICKER = "NQ1"


def load_1m_data():
    """Load 1-minute OHLC data."""
    file_path = DATA_DIR / f"{TICKER}_1m.parquet"
    print(f"Loading {file_path}...")
    df = pd.read_parquet(file_path)
    
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
        df = df.set_index('datetime')
    
    return df


def main():
    print("="*70)
    print("930 TANJA MODEL VALIDATION (VECTORIZED)")
    print("="*70)
    
    # Load data
    df = load_1m_data()
    print(f"Loaded {len(df)} bars")
    
    # Add grouping columns
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    
    # Filter to 2008-2025 range
    start_date = date(2008, 1, 1)
    end_date = date(2025, 12, 31)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    print(f"Analyzing {df['date'].nunique()} trading days (2008-2025)")

    # -------------------------------------------------------------
    # 1. Pre-Open Analysis (9:20 - 9:29)
    # -------------------------------------------------------------
    mask_pre = (df['time_only'] >= time(9, 20)) & (df['time_only'] <= time(9, 29))
    df_pre = df[mask_pre].copy()
    
    pre_stats = df_pre.groupby('date').agg(
        pre_open=('open', 'first'),
        pre_close=('close', 'last'),
        pre_high=('high', 'max'),
        pre_low=('low', 'min')
    )
    
    # Direction
    pre_stats['preopen_dir'] = np.where(pre_stats['pre_close'] > pre_stats['pre_open'], 'BULLISH',
                               np.where(pre_stats['pre_close'] < pre_stats['pre_open'], 'BEARISH', 'NEUTRAL'))
    
    # Close Position (0=Low, 1=High)
    pre_range = pre_stats['pre_high'] - pre_stats['pre_low']
    # Avoid div by zero
    pre_stats['preopen_close_pos'] = np.where(pre_range > 0, 
                                             (pre_stats['pre_close'] - pre_stats['pre_low']) / pre_range, 
                                             0.5)

    # -------------------------------------------------------------
    # 2. Session Analysis (9:30 - 9:59)
    # -------------------------------------------------------------
    mask_sess = (df['time_only'] >= time(9, 30)) & (df['time_only'] <= time(9, 59))
    df_sess = df[mask_sess].copy()
    
    sess_stats = df_sess.groupby('date').agg(
        sess_open=('open', 'first'),
        sess_close=('close', 'last'),
        sess_high=('high', 'max'),
        sess_low=('low', 'min'),
        idx_high=('high', 'idxmax'), # Timestamp of high
        idx_low=('low', 'idxmin')   # Timestamp of low
    )
    
    # Direction
    sess_stats['session_dir'] = np.where(sess_stats['sess_close'] > sess_stats['sess_open'], 'BULLISH',
                                np.where(sess_stats['sess_close'] < sess_stats['sess_open'], 'BEARISH', 'NEUTRAL'))
    
    # First Move (High vs Low timestamp)
    sess_stats['first_move'] = np.where(sess_stats['idx_high'] < sess_stats['idx_low'], 'UP', 'DOWN')
    
    # -------------------------------------------------------------
    # 3. Judas Detection
    # -------------------------------------------------------------
    # Merge
    results = pre_stats.join(sess_stats).dropna()
    
    # Logic:
    # Bearish Judas: First Move UP, but Session Ends BEARISH
    # Bullish Judas: First Move DOWN, but Session Ends BULLISH
    
    cond_bear_judas = (results['first_move'] == 'UP') & (results['session_dir'] == 'BEARISH')
    cond_bull_judas = (results['first_move'] == 'DOWN') & (results['session_dir'] == 'BULLISH')
    
    results['is_judas'] = cond_bear_judas | cond_bull_judas
    results['judas_type'] = np.select([cond_bear_judas, cond_bull_judas], 
                                      ['BEARISH_JUDAS', 'BULLISH_JUDAS'], 
                                      default=None)
                                      
    print(f"\nAnalyzed {len(results)} valid trading days")
    
    # -------------------------------------------------------------
    # 4. Reports
    # -------------------------------------------------------------
    
    # Analysis 1: Pre-open direction predicts session direction?
    print("\n" + "="*70)
    print("1. DOES 9:20-9:29 DIRECTION PREDICT 9:30-9:59 DIRECTION?")
    print("="*70)
    
    for preopen_dir in ['BULLISH', 'BEARISH']:
        subset = results[results['preopen_dir'] == preopen_dir]
        if len(subset) == 0: continue
        
        same_dir = (subset['preopen_dir'] == subset['session_dir']).sum()
        rate = same_dir / len(subset) * 100
        print(f"\n9:20-9:29 {preopen_dir}: {len(subset)} days")
        print(f"  Session same direction: {same_dir} ({rate:.1f}%)")
    
    # Analysis 2: Judas Frequency
    print("\n" + "="*70)
    print("2. JUDAS MOVE FREQUENCY (Do we reverse?)")
    print("="*70)
    
    judas_count = results['is_judas'].sum()
    print(f"\nTotal Judas days: {judas_count} / {len(results)} ({judas_count/len(results)*100:.1f}%)")
    
    # Analysis 3: First Move Reliability
    print("\n" + "="*70)
    print("3. FIRST MOVE RELIABILITY (Is the first move real?)")
    print("="*70)
    
    for first_move in ['UP', 'DOWN']:
        subset = results[results['first_move'] == first_move]
        count = len(subset)
        if count == 0: continue
        
        # Continuation (First Move = Session Dir)
        # Reversal (First Move != Session Dir)
        if first_move == 'UP':
            continuation = (subset['session_dir'] == 'BULLISH').sum()
        else:
            continuation = (subset['session_dir'] == 'BEARISH').sum()
            
        cont_rate = continuation / count * 100
        rev_rate = 100 - cont_rate
        
        print(f"\nFirst move {first_move}: {count} days")
        print(f"  CONTINUATION (Real Move): {continuation} ({cont_rate:.1f}%)")
        print(f"  REVERSAL (False/Judas):   {count - continuation} ({rev_rate:.1f}%)")

    # Save
    output_path = Path("docs/strategies/9_30_breakout/tanja_model/output/tanja_model_validation_results.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path)
    print(f"\nResults saved to: {output_path}")

if __name__ == "__main__":
    main()
