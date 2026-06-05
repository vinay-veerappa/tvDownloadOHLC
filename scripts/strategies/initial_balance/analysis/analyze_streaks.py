"""
Initial Balance Streak Analysis Tool
Calculates rolling win rates, win/loss streak stats, and transition probabilities.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.libs_py.nqstats.ib import calculate_streaks, calculate_rolling_win_rate

def run_streak_analysis(csv_path: str = 'scripts/strategies/initial_balance/data/backtest_results_45min.csv'):
    """
    Analyzes historical win/loss streaks and rolling performance.
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"[ERROR] Backtest results not found at {path}. Please run backtests first.")
        return
        
    df = pd.read_csv(path)
    if df.empty or 'pnl_pct' not in df.columns:
        print(f"[ERROR] Invalid or empty backtest results in {path}.")
        return
        
    # Convert PnL to wins (1) and losses (-1), flat/no-trade is 0
    df['outcome'] = np.where(df['pnl_pct'] > 0, 1, np.where(df['pnl_pct'] < 0, -1, 0))
    df = df[df['outcome'] != 0].copy().reset_index(drop=True)
    
    # Calculate streaks
    df['play_streak'] = calculate_streaks(df['outcome'])
    
    # Calculate rolling win rates (ignore NaNs)
    win_bools = (df['outcome'] == 1).astype(float)
    df['rolling_wr_5'] = calculate_rolling_win_rate(win_bools, 5)
    df['rolling_wr_10'] = calculate_rolling_win_rate(win_bools, 10)
    df['rolling_wr_20'] = calculate_rolling_win_rate(win_bools, 20)
    
    # Transition probabilities: P(Win | prior streak length)
    df['prior_streak'] = df['play_streak'].shift(1)
    
    print("\n" + "="*80)
    print(f"INITIAL BALANCE STREAK & ROLLING PERFORMANCE REPORT")
    print(f"Source: {path.name}")
    print("="*80 + "\n")
    
    print(f"Total Trades Analyzed: {len(df)}")
    print(f"Overall Win Rate: {(df['outcome']==1).mean()*100:.1f}%\n")
    
    # Streak metrics
    pos_streaks = df['play_streak'][df['play_streak'] > 0]
    neg_streaks = df['play_streak'][df['play_streak'] < 0].abs()
    
    print("--- Streak Statistics ---")
    print(f"Max Winning Streak: {pos_streaks.max() if not pos_streaks.empty else 0} consecutive trades")
    print(f"Max Losing Streak: {neg_streaks.max() if not neg_streaks.empty else 0} consecutive trades")
    print(f"Average Win Streak Length: {pos_streaks[df['outcome'] == 1].mean():.1f} trades")
    print(f"Average Loss Streak Length: {neg_streaks[df['outcome'] == -1].mean():.1f} trades\n")
    
    print("--- Conditional Probabilities (After Streak) ---")
    print(f"{'Prior Streak Length':<25} | {'Next Trade Win Rate':<22} | {'Sample Size'}")
    print("-" * 65)
    
    # We analyze streaks of size 1 to 4 for wins (+val) and losses (-val)
    streak_levels = [-4, -3, -2, -1, 1, 2, 3, 4]
    for lvl in streak_levels:
        subset = df[df['prior_streak'] == lvl]
        sample_size = len(subset)
        if sample_size > 0:
            win_rate = (subset['outcome'] == 1).mean() * 100
            label = f"{abs(lvl)} consecutive {'wins' if lvl > 0 else 'losses'}"
            print(f"After {label:<19} | {win_rate:>19.1f}% | {sample_size:>11} trades")
        else:
            label = f"{abs(lvl)} consecutive {'wins' if lvl > 0 else 'losses'}"
            print(f"After {label:<19} | {'No sample':>19} | {sample_size:>11} trades")
            
    print("\n--- Recent Rolling Win Rates ---")
    print(f"Last 5 Trades: {df['rolling_wr_5'].iloc[-1]:.1f}%")
    print(f"Last 10 Trades: {df['rolling_wr_10'].iloc[-1]:.1f}%")
    print(f"Last 20 Trades: {df['rolling_wr_20'].iloc[-1]:.1f}%")
    print("\n" + "="*80)

if __name__ == '__main__':
    # Locate best result file
    run_streak_analysis()
