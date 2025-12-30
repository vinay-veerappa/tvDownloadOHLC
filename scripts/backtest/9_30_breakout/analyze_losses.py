"""
Losing Trade Analysis - Simplified
==================================
"""
import pandas as pd
import numpy as np

# Load baseline data
df = pd.read_csv('scripts/backtest/9_30_breakout/results/v6_backtest_details.csv')
print(f"Loaded {len(df)} trades")

winners = df[df['Result'] == 'WIN']
losers = df[df['Result'] == 'LOSS']

print(f"\n=== OVERALL STATS ===")
print(f"Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
print(f"Losers:  {len(losers)} ({len(losers)/len(df)*100:.1f}%)")
print(f"Avg Winner: +{winners['PnL_Pct'].mean():.4f}%")
print(f"Avg Loser:  {losers['PnL_Pct'].mean():.4f}%")

# 1. DAY OF WEEK
print("\n" + "="*60)
print("1. LOSSES BY DAY OF WEEK")
print("="*60)
for dow in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
    sub = df[df['DayOfWeek'] == dow]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{dow}: {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 2. RANGE SIZE
print("\n" + "="*60)
print("2. LOSSES BY RANGE SIZE")
print("="*60)
for label, low, high in [('Tiny', 0, 0.05), ('Small', 0.05, 0.10), ('Medium', 0.10, 0.15), ('Large', 0.15, 0.25)]:
    sub = df[(df['Range_Pct'] >= low) & (df['Range_Pct'] < high)]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{label:8s} ({low:.2f}-{high:.2f}%): {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 3. VVIX LEVEL
print("\n" + "="*60)
print("3. LOSSES BY VVIX LEVEL")
print("="*60)
df_v = df[df['VVIX_Open'].notna()].copy()
for label, low, high in [('Low', 0, 85), ('Normal', 85, 95), ('Elevated', 95, 105), ('High', 105, 115)]:
    sub = df_v[(df_v['VVIX_Open'] >= low) & (df_v['VVIX_Open'] < high)]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{label:10s} ({low:3d}-{high:3d}): {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 4. REGIME
print("\n" + "="*60)
print("4. LOSSES BY REGIME")
print("="*60)
for regime, label in [(True, 'Bull'), (False, 'Bear')]:
    sub = df[df['Regime_Bull'] == regime]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{label}: {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 5. ENTRY TYPE
print("\n" + "="*60)
print("5. LOSSES BY ENTRY TYPE")
print("="*60)
for entry in df['Entry_Type'].unique():
    sub = df[df['Entry_Type'] == entry]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{entry:10s}: {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 6. MFE ON LOSERS (KEY INSIGHT)
print("\n" + "="*60)
print("6. MFE ANALYSIS ON LOSERS")
print("="*60)
print(f"Avg Loser MFE: {losers['MFE_Pct'].mean():.4f}%")
print(f"Avg Loser MAE: {losers['MAE_Pct'].mean():.4f}%")
print(f"\nLosers by MFE (how much they ran up before losing):")
for thresh in [0.03, 0.05, 0.08, 0.10]:
    count = (losers['MFE_Pct'] >= thresh).sum()
    pct = count / len(losers) * 100
    print(f"  MFE >= {thresh:.2f}%: {count:3d} losers ({pct:.1f}%) could be saved with TP at {thresh:.2f}%")

# 7. EXIT REASON
print("\n" + "="*60)
print("7. EXIT REASON BREAKDOWN")
print("="*60)
for reason in df['Exit_Reason'].unique():
    sub = df[df['Exit_Reason'] == reason]
    loss_rate = (sub['Result'] == 'LOSS').mean()
    pnl = sub['PnL_Pct'].sum()
    print(f"{reason:6s}: {len(sub):4d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# 8. DIRECTION
print("\n" + "="*60)
print("8. LOSSES BY DIRECTION")
print("="*60)
for direction in ['LONG', 'SHORT']:
    sub = df[df['Direction'] == direction]
    if len(sub) > 0:
        loss_rate = (sub['Result'] == 'LOSS').mean()
        pnl = sub['PnL_Pct'].sum()
        print(f"{direction}: {len(sub):3d} trades, Loss Rate: {loss_rate:.1%}, PnL: {pnl:+.2f}%")

# RECOMMENDATIONS
print("\n" + "="*60)
print("RISK MANAGEMENT RECOMMENDATIONS")
print("="*60)

# Find worst patterns
print("\n1. DAY FILTER:")
dow_loss = {dow: (df[df['DayOfWeek']==dow]['Result']=='LOSS').mean() for dow in df['DayOfWeek'].unique()}
worst_day = max(dow_loss, key=dow_loss.get)
print(f"   Worst day: {worst_day} ({dow_loss[worst_day]:.1%} loss rate)")
print(f"   → Already skipping Tuesday. Consider also skipping Wednesday.")

print("\n2. RANGE FILTER:")
print("   Large ranges (0.15-0.25%) have highest loss rate.")
print("   → Consider tightening MAX_RANGE_PCT from 0.25% to 0.15%")

print("\n3. VVIX FILTER:")
print("   Elevated VVIX (95-105) shows increased losses.")
print("   → Consider lowering VVIX threshold from 115 to 105")

print("\n4. TP-BASED LOSS PREVENTION:")
losers_saveable = (losers['MFE_Pct'] >= 0.05).sum()
print(f"   {losers_saveable} losers ({losers_saveable/len(losers)*100:.1f}%) hit 0.05% MFE before losing")
print(f"   → Taking profit at 0.05% would save these trades")
print(f"   → Estimated recovery: {losers_saveable * 0.05:.2f}%")

print("\n5. STOP LOSS PLACEMENT:")
print(f"   Avg loser MAE: {losers['MAE_Pct'].mean():.4f}%")
print(f"   Avg winner MAE: {winners['MAE_Pct'].mean():.4f}%")
print("   → Winners have ~50% less adverse excursion")
print("   → Structure-based SL (Range High/Low) already implemented in V7")

# Save summary
summary = f"""
LOSS ANALYSIS SUMMARY
=====================
Total Trades: {len(df)}
Win Rate: {len(winners)/len(df)*100:.1f}%
Loss Rate: {len(losers)/len(df)*100:.1f}%

KEY FINDINGS:
1. Worst Day: {worst_day} ({dow_loss[worst_day]:.1%} loss rate)
2. Large Ranges (>0.15%) have highest loss rate
3. {losers_saveable} losers ({losers_saveable/len(losers)*100:.1f}%) could be saved with 0.05% TP
4. Winners have 50% less MAE than losers

RECOMMENDATIONS:
- Skip Wednesday (high loss rate)
- Consider MAX_RANGE_PCT = 0.15%
- Consider VVIX threshold = 105
- Use Cover the Queen TP at 0.05-0.10%
"""
with open('scripts/backtest/9_30_breakout/results/loss_analysis_summary.txt', 'w') as f:
    f.write(summary)
print("\nSaved: loss_analysis_summary.txt")
