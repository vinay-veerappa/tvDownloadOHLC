"""
Smart Mode Simulation: Pattern Priority
=======================================
Tests the "Smart Mode" hypothesis for the Tanja 9:30 Breakout.

Strategies Compared:
1. TREND (Baseline): Follow 9:30 Candle Color.
2. INVERSE (Reversal): Fade 9:30 Candle Color.
3. SMART (Hybrid): 
   - Uses 9:28 and 9:32 candles to define a "Pattern" (Gap Up/Down).
   - If Pattern says UP -> Bias is LONG.
   - If Pattern says DOWN -> Bias is SHORT.
   - If Pattern is Neutral -> Follow 9:30 Trend.
   - CRITICAL: If Pattern Bias CONTRADICTS 9:30 Candle, we fade the 9:30 candle (Reversal).

Data:
- NQ 1-minute data (2008-2025)
- Session: 9:33 - 12:00 (Smart Mode starts at 9:33)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time

DATA_DIR = Path("data")
DOCS_DIR = Path("docs/strategies/9_30_breakout/tanja_model/output")
TICKER = "NQ1"

def load_data():
    df = pd.read_parquet(DATA_DIR / f"{TICKER}_1m.parquet")
    df['datetime'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
    df = df.set_index('datetime')
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def main():
    print("="*70)
    print("SMART MODE SIMULATION: PATTERN PRIORITY")
    print("="*70)
    
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    print(f"Data Loaded: {len(df)} rows")
    
    # -------------------------------------------------------------------------
    # 1. EXTRACT CANDLES (9:28, 9:30, 9:32)
    # -------------------------------------------------------------------------
    times_needed = [time(9, 28), time(9, 30), time(9, 32)]
    mask = df['time_only'].isin(times_needed)
    candles = df[mask].copy()
    
    # Pivot to get one row per day with columns per time
    # This gives us: open_09:28:00, close_09:30:00, etc.
    pivoted = candles.pivot_table(index='date', columns='time_only', values=['open', 'high', 'low', 'close'])
    
    # Flatten columns
    pivoted.columns = [f"{col[0]}_{col[1].strftime('%H%M')}" for col in pivoted.columns]
    
    # Drop days with missing candles (incomplete setup)
    pivoted = pivoted.dropna()
    print(f"Valid Trading Days: {len(pivoted)}")
    
    # -------------------------------------------------------------------------
    # 2. DEFINE PATTERNS & TRIGGERS
    # -------------------------------------------------------------------------
    res = pivoted.copy()
    
    # 9:30 Candle (The Trigger)
    res['h930'] = res['high_0930']
    res['l930'] = res['low_0930']
    res['range_pts'] = res['h930'] - res['l930']
    res['trigger_dir'] = np.where(res['close_0930'] > res['open_0930'], 'BULL',
                         np.where(res['close_0930'] < res['open_0930'], 'BEAR', 'DOJI'))
    
    # 9:28 vs 9:32 Pattern (The Setup)
    # Gap Up: 9:32 Low > 9:28 High
    # Gap Down: 9:32 High < 9:28 Low
    res['pattern'] = 'NEUTRAL'
    
    # Strong Bull Pattern
    res.loc[res['low_0932'] > res['high_0928'], 'pattern'] = 'GAP_UP'
    
    # Strong Bear Pattern
    res.loc[res['high_0932'] < res['low_0928'], 'pattern'] = 'GAP_DOWN'
    
    # Filter valid
    res = res[(res['range_pts'] > 0) & (res['trigger_dir'] != 'DOJI')]
    
    # -------------------------------------------------------------------------
    # 3. DEFINE STRATEGY BIAS
    # -------------------------------------------------------------------------
    
    # A. TREND STRATEGY: Always follow Trigger
    res['bias_trend'] = res['trigger_dir']
    
    # B. INVERSE STRATEGY: Always fade Trigger
    res['bias_inverse'] = np.where(res['trigger_dir'] == 'BULL', 'BEAR', 'BULL')
    
    # C. SMART STRATEGY (Pattern Priority)
    # If Gap Up -> Must be BULL (even if Trigger is Bear -> Flip to Bull)
    # If Gap Down -> Must be BEAR (even if Trigger is Bull -> Flip to Bear)
    # Else -> Follow Trend
    
    conditions = [
        (res['pattern'] == 'GAP_UP'),
        (res['pattern'] == 'GAP_DOWN')
    ]
    choices = ['BULL', 'BEAR']
    
    # np.select applies the choices, defaulting to trend bias if no pattern matches
    res['bias_smart'] = np.select(conditions, choices, default=res['bias_trend'])
    
    # Track "Flips" (Where Smart != Trend)
    res['is_flip'] = (res['bias_smart'] != res['bias_trend'])
    print(f"Smart Mode Flips: {res['is_flip'].sum()} sessions ({res['is_flip'].mean()*100:.1f}%)")
    
    # -------------------------------------------------------------------------
    # 4. SIMULATE OUTCOMES (9:33 - 12:00)
    # -------------------------------------------------------------------------
    
    # Get Max/Min for the session STARTING AT 9:33 (Smart Mode Entry Time)
    session_mask = (df['time_only'] >= time(9, 33)) & (df['time_only'] <= time(12, 0))
    session = df[session_mask].copy()
    
    session_stats = session.groupby('date').agg(
        s_high=('high', 'max'),
        s_low=('low', 'min')
    )
    
    # Join outcome data
    res = res.join(session_stats).dropna()
    
    # Calculate MFE/MAE for each bias type
    # If Bias is BULL -> MFE = Up move, MAE = Down move
    # If Bias is BEAR -> MFE = Down move, MAE = Up move
    
    # Potential Moves
    move_up = (res['s_high'] - res['h930']).clip(lower=0)
    move_down = (res['l930'] - res['s_low']).clip(lower=0)
    
    # Helper to calc results
    def calc_results(bias_col):
        is_bull = (res[bias_col] == 'BULL')
        mfe = np.where(is_bull, move_up, move_down) / res['range_pts']
        mae = np.where(is_bull, move_down, move_up) / res['range_pts']
        return mfe, mae
    
    res['trend_mfe'], res['trend_mae'] = calc_results('bias_trend')
    res['smart_mfe'], res['smart_mae'] = calc_results('bias_smart')
    res['inv_mfe'], res['inv_mae'] = calc_results('bias_inverse')
    
    # -------------------------------------------------------------------------
    # 5. REPORTING
    # -------------------------------------------------------------------------
    targets = [0.5, 1.0, 1.5, 2.0, 3.0]
    
    print(f"\n{'Target':<6} | {'TREND Win%':>10} | {'SMART Win%':>10} | {'INVERSE Win%':>12} | {'Smart Edge':>10}")
    print("-" * 65)
    
    stats_out = []
    
    for t in targets:
        # Win = MFE >= Target AND MAE < 1.0 (Stop hit)
        
        def get_win_rate(mfe_col, mae_col):
            wins = ((mae_col < 1.0) & (mfe_col >= t)).sum()
            return wins / len(res) * 100
        
        trend_rate = get_win_rate(res['trend_mfe'], res['trend_mae'])
        smart_rate = get_win_rate(res['smart_mfe'], res['smart_mae'])
        inv_rate = get_win_rate(res['inv_mfe'], res['inv_mae'])
        
        edge = smart_rate - trend_rate
        
        print(f"{t:<4}R  | {trend_rate:>9.1f}% | {smart_rate:>9.1f}% | {inv_rate:>11.1f}% | {edge:>+9.1f}%")
        
        stats_out.append({
            'Target': t,
            'Trend_Win': trend_rate,
            'Smart_Win': smart_rate,
            'Inverse_Win': inv_rate,
            'Smart_Edge': edge
        })
        
    print("-" * 65)
    
    # Analyze Flips Only
    flips = res[res['is_flip']]
    if len(flips) > 0:
        print(f"\nAnalysis of {len(flips)} FLIP ONLY Sessions (Mismatch Days):")
        print(f"{'Target':<6} | {'Trend (Fail)':>12} | {'Smart (Success)':>15} | {'Improvement':>12}")
        for t in targets:
            # Re-calc for subset
            
            # Trend MFE/MAE on these days
            t_wins = ((flips['trend_mae'] < 1.0) & (flips['trend_mfe'] >= t)).sum()
            t_rate = t_wins / len(flips) * 100
            
            # Smart MFE/MAE on these days
            s_wins = ((flips['smart_mae'] < 1.0) & (flips['smart_mfe'] >= t)).sum()
            s_rate = s_wins / len(flips) * 100
            
            print(f"{t:<4}R  | {t_rate:>11.1f}% | {s_rate:>14.1f}% | {s_rate - t_rate:>+11.1f}%")

    # Save
    pd.DataFrame(stats_out).to_csv(DOCS_DIR / "smart_mode_results.csv", index=False)
    print(f"\nSaved results to {DOCS_DIR / 'smart_mode_results.csv'}")

if __name__ == "__main__":
    main()
