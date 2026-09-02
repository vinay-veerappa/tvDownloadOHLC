import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from scripts.research.test_institutional_ict_filters import run_ict_ablation

df_nq = pd.read_parquet('data/NQ1_5m.parquet')
df_nq = df_nq[df_nq.index >= '2022-01-01'].copy()
if df_nq.index.tz is None:
    df_nq.index = df_nq.index.tz_localize('UTC').tz_convert('America/New_York')
else:
    df_nq.index = df_nq.index.tz_convert('America/New_York')

# 1. Test 5 bps Stop
trades_5bps = run_ict_ablation(df_nq, use_htf_filter=True, filter_lunch=True, stop_bps=5.0)

# 2. Test 8 bps Stop
trades_8bps = run_ict_ablation(df_nq, use_htf_filter=True, filter_lunch=True, stop_bps=8.0)

def print_audit(trades, stop_name):
    n = len(trades)
    full_losses = trades[trades['pnl_bps'] <= -0.5]
    queen_only = trades[(trades['queen_hit'] == True) & (trades['runner_hit'] == False)]
    both_hits = trades[trades['runner_hit'] == True]
    win_trades = trades[trades['pnl_bps'] > 0]
    losing_trades = trades[trades['pnl_bps'] <= 0]

    print(f"\n=========================================================================")
    print(f"DIAGNOSTIC AUDIT: {stop_name} (Total Trades: {n:,d})")
    print(f"=========================================================================")
    print(f"1. Net Win Rate (P&L > 0)    : {len(win_trades)/n*100:.1f}%")
    print(f"2. Full Stop-Outs            : {len(full_losses)/n*100:.1f}%")
    print(f"3. Queen Hit (+10bps) Only   : {len(queen_only)/n*100:.1f}% (Locked +10bps, Runner BE Scratch)")
    print(f"4. Full Runner Hit (+30bps)  : {len(both_hits)/n*100:.1f}%")
    print(f"5. Total Queen Touched Rate  : {trades['queen_hit'].mean()*100:.1f}%")
    print(f"6. Avg Profit Factor         : {trades[trades['pnl_bps']>0]['pnl_bps'].sum() / abs(trades[trades['pnl_bps']<0]['pnl_bps'].sum()):.2f}")
    
    mfe_ge_3 = (losing_trades['mfe_bps'] >= 3.0).mean() * 100
    mfe_ge_5 = (losing_trades['mfe_bps'] >= 5.0).mean() * 100
    mfe_ge_7 = (losing_trades['mfe_bps'] >= 7.0).mean() * 100
    avg_mfe = losing_trades['mfe_bps'].mean()
    print(f"\n--- Losing Trades Behavior (Before hitting Stop) ---")
    print(f"• Avg Max Favorable Run (MFE): +{avg_mfe:.2f} bps")
    print(f"• Reached >= +3.0 bps profit : {mfe_ge_3:.1f}% of losing trades")
    print(f"• Reached >= +5.0 bps profit : {mfe_ge_5:.1f}% of losing trades")
    print(f"• Reached >= +7.0 bps profit : {mfe_ge_7:.1f}% of losing trades (almost hit Queen!)")

print_audit(trades_5bps, "5.0 bps Stop Loss (Strict FVG Stop)")
print_audit(trades_8bps, "8.0 bps Stop Loss (Structural Pivot Stop)")
