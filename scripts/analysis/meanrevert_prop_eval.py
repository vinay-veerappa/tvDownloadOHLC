"""Prop firm MC eval on MeanRevert v3 (locked config)."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from scripts.analysis.three_archetype_v3 import (
    df, df5, daily_atr, unique_dates, build_day_context,
    run_meanrevert_v3, POINT_VAL
)
from scripts.trading_framework.ml.prop_firm_simulator import (
    PropFirmSimulator, FIRM_PROFILES
)

htf_df2 = pd.read_parquet('data/derived/ICT/ES1_htf_levels.parquet')
htf_df2['trading_date'] = pd.to_datetime(htf_df2['trading_date'])

all_trades = []
for i, t_date in enumerate(unique_dates):
    if i % 100 == 0: print(f"  Day {i}/{len(unique_dates)}...")
    ts = pd.Timestamp(t_date)
    if ts.weekday() >= 5: continue
    ctx = build_day_context(ts, df, df5, daily_atr, ib_minutes=30)
    if ctx is None: continue
    htf_row_data = htf_df2[htf_df2['trading_date'] == ts]
    htf_row = htf_row_data.iloc[0] if len(htf_row_data) > 0 else None

    after_time = None
    for _ in range(3):
        t = run_meanrevert_v3(ctx, 'NY_PM', htf_row, after_time=after_time)
        if t is None: break
        all_trades.append(t)
        after_time = t.exit_time

print(f"\nMeanRevert trades: {len(all_trades)}")

# Build trades_detailed for PropFirmSimulator
# pnl_pct = percent of account (e.g., 0.5% = 0.5, not 0.005)
trades_data = []
for t in all_trades:
    trades_data.append({
        'pnl_pct': t.pnl / 50000 * 100,  # percent of $50k account
        'exit_time': t.exit_time,
    })

trades_df = pd.DataFrame(trades_data)
net_dollars = sum(t.pnl for t in all_trades)
print(f"Net: ${net_dollars:.0f}")
print(f"WR: {sum(1 for t in all_trades if t.pnl>0)/len(all_trades)*100:.1f}%")

# Run PropFirmSimulator
sim = PropFirmSimulator(account_size=50000, point_value=5.0)  # 1x MES base

# Scale P&L for different contract counts
for n_mes in [1, 2, 3, 4]:
    trades_scaled = trades_df.copy()
    trades_scaled['pnl_pct'] = trades_scaled['pnl_pct'] * n_mes

    print(f"\n{'='*70}")
    print(f"PROP FIRM EVAL — MeanRevert v3 @ {n_mes}x MES (${n_mes*5}/pt)")
    print(f"  Net: ${net_dollars*n_mes:.0f}")
    print(f"{'='*70}")

    results = sim.run_all_profiles(trades_scaled, n_simulations=2000)
    for profile_name, (det, mc) in results.items():
        print(f"  {profile_name:<20} Pass: {mc.pass_rate_pct:>5.1f}%  "
              f"Grade: {mc.grade}  Blow: {mc.blow_rate_pct:.1f}%")