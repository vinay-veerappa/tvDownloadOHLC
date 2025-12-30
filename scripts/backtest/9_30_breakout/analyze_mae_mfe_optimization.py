"""
MAE/MFE Analysis for Optimal TP/SL Levels
==========================================
Analyzes trade-level MAE/MFE data to determine:
1. Optimal Stop Loss level (based on MAE distribution)
2. Optimal Take Profit level (based on MFE distribution)
3. Risk/Reward optimization
4. Entry mode performance comparison
"""

import pandas as pd
import numpy as np
import os

# Load the baseline trades which has full MAE/MFE data
trades_file = "scripts/backtest/9_30_breakout/results/v6_backtest_details.csv"

if not os.path.exists(trades_file):
    # Try optimization combined file as backup
    trades_file = "scripts/backtest/9_30_breakout/results/optimization/all_trades_combined.csv"

df = pd.read_csv(trades_file)
print(f"Loaded {len(df)} trades from {trades_file}")

# Basic Stats
print("\n" + "="*60)
print("BASIC STATISTICS")
print("="*60)
print(f"Total Trades: {len(df)}")
print(f"Win Rate: {(df['PnL_Pct'] > 0).mean():.2%}")
print(f"Gross PnL: {df['PnL_Pct'].sum():.2f}%")

winners = df[df['PnL_Pct'] > 0]
losers = df[df['PnL_Pct'] <= 0]

print(f"\nWinners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
print(f"Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")

# MAE Analysis
print("\n" + "="*60)
print("MAE (MAX ADVERSE EXCURSION) ANALYSIS")
print("="*60)
print("\nMAE Distribution (% from Entry):")
print(df['MAE_Pct'].describe())

print("\nMAE by Outcome:")
print(f"  Winners Avg MAE: {winners['MAE_Pct'].mean():.4f}%")
print(f"  Losers Avg MAE:  {losers['MAE_Pct'].mean():.4f}%")

print("\nMAE Percentiles:")
for pct in [50, 75, 90, 95, 99]:
    val = df['MAE_Pct'].quantile(pct/100)
    print(f"  {pct}th percentile: {val:.4f}%")

# MFE Analysis
print("\n" + "="*60)
print("MFE (MAX FAVORABLE EXCURSION) ANALYSIS")
print("="*60)
print("\nMFE Distribution (% from Entry):")
print(df['MFE_Pct'].describe())

print("\nMFE by Outcome:")
print(f"  Winners Avg MFE: {winners['MFE_Pct'].mean():.4f}%")
print(f"  Losers Avg MFE:  {losers['MFE_Pct'].mean():.4f}%")

print("\nMFE Percentiles:")
for pct in [50, 75, 90, 95, 99]:
    val = df['MFE_Pct'].quantile(pct/100)
    print(f"  {pct}th percentile: {val:.4f}%")

# Profit Leakage Analysis
print("\n" + "="*60)
print("PROFIT LEAKAGE ANALYSIS")
print("="*60)
# Trades that were winners but MFE was much higher than final PnL
winners_with_leakage = winners[winners['MFE_Pct'] > winners['PnL_Pct'] * 2]
print(f"Winners with >50% leakage: {len(winners_with_leakage)} / {len(winners)} ({len(winners_with_leakage)/len(winners)*100:.1f}%)")
avg_leakage = (winners['MFE_Pct'] - winners['PnL_Pct']).mean()
print(f"Average Leakage (MFE - Final PnL): {avg_leakage:.4f}%")
print(f"Total Leaked Profit: {(winners['MFE_Pct'] - winners['PnL_Pct']).sum():.2f}%")

# SL Optimization
print("\n" + "="*60)
print("STOP LOSS OPTIMIZATION")
print("="*60)
print("\nTesting various SL levels (% from Entry):")
print(f"{'SL Level':<12} {'Stopped Out':<15} {'Remaining':<12} {'Est. PnL':<12}")
print("-" * 55)

for sl_pct in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]:
    stopped = (df['MAE_Pct'] >= sl_pct).sum()
    remaining = len(df) - stopped
    # Rough estimate: stopped trades = loss of sl_pct, remaining = original PnL
    est_pnl = df[df['MAE_Pct'] < sl_pct]['PnL_Pct'].sum() - (stopped * sl_pct)
    print(f"{sl_pct:.2f}%        {stopped:<15} {remaining:<12} {est_pnl:.2f}%")

# TP Optimization
print("\n" + "="*60)
print("TAKE PROFIT OPTIMIZATION")
print("="*60)
print("\nTesting various TP levels (% from Entry):")
print(f"{'TP Level':<12} {'Would Hit':<15} {'Capture Rate':<15} {'Est. Profit':<12}")
print("-" * 60)

for tp_pct in [0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
    would_hit = (df['MFE_Pct'] >= tp_pct).sum()
    capture_rate = would_hit / len(df)
    est_profit = would_hit * tp_pct
    print(f"{tp_pct:.2f}%        {would_hit:<15} {capture_rate:.1%}            {est_profit:.2f}%")

# Risk/Reward Analysis
print("\n" + "="*60)
print("RISK/REWARD OPTIMIZATION")
print("="*60)
print("\nOptimal R:R based on MAE/MFE distribution:")
avg_mae = df['MAE_Pct'].mean()
avg_mfe = df['MFE_Pct'].mean()
print(f"  Average MAE (Risk): {avg_mae:.4f}%")
print(f"  Average MFE (Reward): {avg_mfe:.4f}%")
print(f"  Natural R:R Ratio: 1:{avg_mfe/avg_mae:.2f}")

# Suggested levels
suggested_sl = df['MAE_Pct'].quantile(0.75)  # 75th percentile
suggested_tp = df['MFE_Pct'].quantile(0.50)  # 50th percentile
print(f"\n  Suggested SL (75th MAE): {suggested_sl:.4f}%")
print(f"  Suggested TP (50th MFE): {suggested_tp:.4f}%")
print(f"  Implied R:R: 1:{suggested_tp/suggested_sl:.2f}")

# Save analysis results
output = {
    'Metric': ['Total Trades', 'Win Rate', 'Gross PnL', 'Avg MAE', 'Avg MFE', 
               'Winners Avg MAE', 'Losers Avg MAE', 'Winners Avg MFE', 'Losers Avg MFE',
               'Suggested SL', 'Suggested TP'],
    'Value': [len(df), f"{(df['PnL_Pct'] > 0).mean():.2%}", f"{df['PnL_Pct'].sum():.2f}%",
              f"{avg_mae:.4f}%", f"{avg_mfe:.4f}%",
              f"{winners['MAE_Pct'].mean():.4f}%", f"{losers['MAE_Pct'].mean():.4f}%",
              f"{winners['MFE_Pct'].mean():.4f}%", f"{losers['MFE_Pct'].mean():.4f}%",
              f"{suggested_sl:.4f}%", f"{suggested_tp:.4f}%"]
}
pd.DataFrame(output).to_csv('scripts/backtest/9_30_breakout/results/mae_mfe_analysis.csv', index=False)
print("\n\nSaved: mae_mfe_analysis.csv")
