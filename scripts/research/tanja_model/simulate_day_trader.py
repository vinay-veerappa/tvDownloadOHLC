"""
Day Trader Simulation: Tanja 9:30 Breakout
==========================================
Simulates two distinct trading behaviors using the 9:30 1-minute candle as the range.

Strategy 1: TREND FOLLOWER
- Entry: Breakout of 9:30 Range in the direction of the CANDLE COLOR.
- Logic: "The move is real."
- Stop Loss: Opposite end of 9:30 Range.

Strategy 2: REVERSAL TRADER (Judas)
- Entry: Breakout of 9:30 Range ... FADE IT.
- Logic: "They are trapping breakout traders."
- Stop Loss: Fixed width (equivalent to range size) or standard points.

The Simulation:
- "Taking a portion of the move": 
  We check if the price hits 1R (1x Range Risk), 2R, and 3R targets.
  We calculate the "Bankable Opportunity" for each strategy.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import time, timedelta

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
    print("DAY TRADER SIMULATION: TREND vs REVERSAL (Vectorized)")
    print("="*70)
    
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    print(f"Data Loaded: {len(df)} rows")
    
    # 1. 9:30 Candle Data
    df['is_930'] = (df['time_only'] == time(9, 30))
    c930 = df[df['is_930']].copy()
    
    # Calculate Range & Direction
    c930['range_pts'] = c930['high'] - c930['low']
    c930['dir_930'] = np.where(c930['close'] > c930['open'], 'BULLISH',
                      np.where(c930['close'] < c930['open'], 'BEARISH', 'DOJI'))
    
    # Drop invalid
    c930 = c930[(c930['range_pts'] > 0) & (c930['dir_930'] != 'DOJI')]
    c930 = c930[['date', 'dir_930', 'range_pts', 'high', 'low']].set_index('date')
    c930 = c930.rename(columns={'high': 'h930', 'low': 'l930'})
    
    # 2. Session Data (9:31 - 12:00)
    session_mask = (df['time_only'] > time(9, 30)) & (df['time_only'] <= time(12, 0))
    session = df[session_mask].copy()
    
    # Group by Date to get Max High / Min Low
    session_stats = session.groupby('date').agg(
        s_high=('high', 'max'),
        s_low=('low', 'min')
    )
    
    # 3. Merge
    res = c930.join(session_stats).dropna()
    print(f"Simulating {len(res)} valid sessions...")
    
    # 4. Calculate Extensions (R-Multiples)
    # Move Up from High, Move Down from Low
    # Using .values for speed, though vectorization handles Series fine
    range_pts = res['range_pts']
    move_up = (res['s_high'] - res['h930']).clip(lower=0)
    move_down = (res['l930'] - res['s_low']).clip(lower=0)
    
    # Trend Strategy
    # If Bullish: Long break of High -> Profit is Up, Risk is Down
    # If Bearish: Short break of Low -> Profit is Down, Risk is Up
    
    is_bull = (res['dir_930'] == 'BULLISH')
    
    res['trend_mfe_R'] = np.where(is_bull, move_up, move_down) / range_pts
    res['trend_mae_R'] = np.where(is_bull, move_down, move_up) / range_pts
    
    # Reversal Strategy (Fade)
    # If Bullish (Trend): We Short -> Profit is Down, Risk is Up
    # (Inverse of Trend)
    res['rev_mfe_R'] = res['trend_mae_R']
    res['rev_mae_R'] = res['trend_mfe_R']
    
    # 5. Analyze Hits
    targets = [0.5, 1.0, 1.5, 2.0, 3.0]
    
    print(f"\n{'Target (R)':<12} | {'TREND Win%':>12} | {'REVERSAL Win%':>15} | {'Edge Difference':>15}")
    print("-" * 60)
    
    stats_out = []
    
    for t in targets:
        # Trend Stats (Stop 1R)
        trend_wins = ((res['trend_mae_R'] < 1.0) & (res['trend_mfe_R'] >= t)).sum()
        trend_rate = trend_wins / len(res) * 100
        
        # Reversal Stats (Stop 1R)
        rev_wins = ((res['rev_mae_R'] < 1.0) & (res['rev_mfe_R'] >= t)).sum()
        rev_rate = rev_wins / len(res) * 100
        
        diff = trend_rate - rev_rate
        indicator = "TREND >>>" if diff > 5 else "REVERSAL >>>" if diff < -5 else "NEUTRAL"
        
        print(f"{t:<4}R ({t*100:>3.0f}%)  | {trend_rate:>11.1f}% | {rev_rate:>14.1f}% | {diff:>+14.1f}% {indicator}")
        
        stats_out.append({
            'Target_R': t,
            'Trend_Win_Rate': trend_rate,
            'Reversal_Win_Rate': rev_rate,
            'Diff': diff
        })
        
    # Save
    pd.DataFrame(stats_out).to_csv(DOCS_DIR / "day_trader_sim_results.csv", index=False)
    print(f"\nSimulation saved to {DOCS_DIR / 'day_trader_sim_results.csv'}")

if __name__ == "__main__":
    main()
