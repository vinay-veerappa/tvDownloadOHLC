import pandas as pd
import numpy as np

df = pd.read_parquet("data/research/nt8_4y_all_trades.parquet")
df["year"] = pd.to_datetime(df["entry_time"]).dt.year

print("=== LONG-ONLY PERFORMANCE BY YEAR (Micros) ===")
df_long = df[df["direction"] == "LONG"]
for yr, grp in df_long.groupby("year"):
    pnl = grp["pnl"].sum()
    wr = (grp["pnl"] > 0).mean() * 100.0
    gp = grp[grp["pnl"] > 0]["pnl"].sum()
    gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    pf = gp / gl if gl > 0 else 0
    print(f"Year {yr}: Trades: {len(grp):4d} | WR: {wr:5.1f}% | Net PnL: ${pnl:10,.2f} | PF: {pf:5.2f} (E-mini: ${pnl*10:11,.2f})")

gp_l = df_long[df_long["pnl"] > 0]["pnl"].sum()
gl_l = abs(df_long[df_long["pnl"] < 0]["pnl"].sum())
pf_l = gp_l / gl_l if gl_l > 0 else 0
wr_l = (df_long["pnl"] > 0).mean() * 100.0
print(f"TOTAL LONG:  Trades: {len(df_long):4d} | WR: {wr_l:5.1f}% | Net PnL: ${df_long['pnl'].sum():10,.2f} | PF: {pf_l:5.2f} (E-mini: ${df_long['pnl'].sum()*10:11,.2f})")

print("\n=== SHORT-ONLY PERFORMANCE BY YEAR (Micros) ===")
df_short = df[df["direction"] == "SHORT"]
for yr, grp in df_short.groupby("year"):
    pnl = grp["pnl"].sum()
    wr = (grp["pnl"] > 0).mean() * 100.0
    gp = grp[grp["pnl"] > 0]["pnl"].sum()
    gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    pf = gp / gl if gl > 0 else 0
    print(f"Year {yr}: Trades: {len(grp):4d} | WR: {wr:5.1f}% | Net PnL: ${pnl:10,.2f} | PF: {pf:5.2f} (E-mini: ${pnl*10:11,.2f})")

gp_s = df_short[df_short["pnl"] > 0]["pnl"].sum()
gl_s = abs(df_short[df_short["pnl"] < 0]["pnl"].sum())
pf_s = gp_s / gl_s if gl_s > 0 else 0
wr_s = (df_short["pnl"] > 0).mean() * 100.0
print(f"TOTAL SHORT: Trades: {len(df_short):4d} | WR: {wr_s:5.1f}% | Net PnL: ${df_short['pnl'].sum():10,.2f} | PF: {pf_s:5.2f} (E-mini: ${df_short['pnl'].sum()*10:11,.2f})")
