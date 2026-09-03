import pandas as pd
import numpy as np
from pathlib import Path

# Load NT8 trades
df_trades = pd.read_parquet("data/research/nt8_4y_all_trades.parquet")
df_trades["entry_time"] = pd.to_datetime(df_trades["entry_time"])
df_trades["year"] = df_trades["entry_time"].dt.year

# Longs in Bull regimes (2023-2026) + Shorts in Bear regimes (2022)
macro_regime_trades = []
for idx, r in df_trades.iterrows():
    yr = r["year"]
    direction = r["direction"]
    
    # 2022 was Bear regime: trade Shorts only
    if yr == 2022 and direction == "SHORT":
        macro_regime_trades.append(r)
    # 2023-2026 was Bull regime: trade Longs only
    elif yr >= 2023 and direction == "LONG":
        macro_regime_trades.append(r)

df_regime = pd.DataFrame(macro_regime_trades)
print("=" * 80)
print("MACRO-ALIGNED REGIME AUDIT (Shorts in 2022 Bear + Longs in 2023-2026 Bull)")
print("=" * 80)
print(f"Total Trade Legs:           {len(df_regime):,d}")
print(f"Net Realized PnL (Micros):  ${df_regime['pnl'].sum():,.2f}")
print(f"Net Realized PnL (E-minis): ${df_regime['pnl'].sum() * 10:,.2f}")
gp = df_regime[df_regime["pnl"] > 0]["pnl"].sum()
gl = abs(df_regime[df_regime["pnl"] < 0]["pnl"].sum())
pf = gp / gl if gl > 0 else 0
wr = (df_regime["pnl"] > 0).mean() * 100.0
print(f"Win Rate:                   {wr:.1f}%")
print(f"Profit Factor:              {pf:.3f}")
print(f"Gross Profit:               ${gp:,.2f}")
print(f"Gross Loss:                -${gl:,.2f}")

print("\nYearly Breakdown with Macro Regime Alignment:")
for yr, grp in df_regime.groupby("year"):
    yr_pnl = grp["pnl"].sum()
    yr_gp = grp[grp["pnl"] > 0]["pnl"].sum()
    yr_gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    yr_pf = yr_gp / yr_gl if yr_gl > 0 else 0
    yr_wr = (grp["pnl"] > 0).mean() * 100.0
    side = "SHORTS ONLY" if yr == 2022 else "LONGS ONLY"
    print(f"Year {yr} ({side:11s}): Trades: {len(grp):4d} | WR: {yr_wr:5.1f}% | Net PnL: ${yr_pnl:10,.2f} | PF: {yr_pf:5.2f} (E-mini: ${yr_pnl*10:11,.2f})")
