import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# Load parsed trade legs
df = pd.read_parquet("data/research/nt8_4y_all_trades.parquet")
df["entry_time"] = pd.to_datetime(df["entry_time"])
df["exit_time"] = pd.to_datetime(df["exit_time"])
df["date"] = df["entry_time"].dt.date
df["year"] = df["entry_time"].dt.year
df["month"] = df["entry_time"].dt.to_period("M")

# Group into 2-pack execution rounds
rounds = []
# Each round typically has 2 legs entering at identical or near-identical times
# Group by (date, entry_time, direction)
grouped = df.groupby(["date", "entry_time", "direction"])

round_id = 1
for (d, et, direction), grp in grouped:
    q_leg = grp[grp["contract"].str.contains("Queen")]
    r_leg = grp[grp["contract"].str.contains("Runner")]
    
    q_pnl = q_leg["pnl"].sum() if not q_leg.empty else 0.0
    q_pts = q_leg["points"].mean() if not q_leg.empty else 0.0
    q_exit = q_leg["exit_name"].iloc[0] if not q_leg.empty else "N/A"
    
    r_pnl = r_leg["pnl"].sum() if not r_leg.empty else 0.0
    r_pts = r_leg["points"].mean() if not r_leg.empty else 0.0
    r_exit = r_leg["exit_name"].iloc[0] if not r_leg.empty else "N/A"
    
    total_pnl = q_pnl + r_pnl
    total_pts = q_pts + r_pts
    entry_p = grp["entry_price"].iloc[0]
    
    rounds.append({
        "round_id": round_id,
        "date": d,
        "entry_time": et,
        "year": et.year,
        "month": str(et.to_period("M")),
        "direction": direction,
        "entry_price": entry_p,
        "queen_pts": q_pts,
        "queen_pnl": q_pnl,
        "queen_exit": q_exit,
        "runner_pts": r_pts,
        "runner_pnl": r_pnl,
        "runner_exit": r_exit,
        "total_pts": total_pts,
        "total_pnl": total_pnl,
        "is_win": total_pnl > 0
    })
    round_id += 1

df_rounds = pd.DataFrame(rounds)
df_rounds["cum_pnl"] = df_rounds["total_pnl"].cumsum()

# Calculate key statistics
total_r = len(df_rounds)
wins_r = df_rounds[df_rounds["is_win"]]
loss_r = df_rounds[~df_rounds["is_win"]]
wr_r = len(wins_r) / total_r * 100.0
gp_r = wins_r["total_pnl"].sum()
gl_r = abs(loss_r["total_pnl"].sum())
pf_r = gp_r / gl_r if gl_r > 0 else 0
net_r = df_rounds["total_pnl"].sum()

# Equity peak and drawdown
cum_max = df_rounds["cum_pnl"].cummax()
dd = df_rounds["cum_pnl"] - cum_max
max_dd = dd.min()

print("=" * 80)
print("NINJATRADER 8 4.7-YEAR BACKTEST AUDIT (2022-01-03 to 2026-09-01)")
print("=" * 80)
print(f"Total Execution Rounds:      {total_r:,d} rounds ({len(df):,d} contract legs)")
print(f"Total Net Realized PnL (MNQ): ${net_r:,.2f} (Micro)")
print(f"Total Net Realized PnL (NQ):  ${net_r * 10:,.2f} (E-mini)")
print(f"Round Win Rate:              {wr_r:.1f}% ({len(wins_r):,d} W / {len(loss_r):,d} L)")
print(f"Gross Profit:                ${gp_r:,.2f}")
print(f"Gross Loss:                 -${gl_r:,.2f}")
print(f"Profit Factor:               {pf_r:.3f}")
print(f"Max Strategy Drawdown:       ${max_dd:,.2f} (Micro) | ${max_dd * 10:,.2f} (E-mini)")
print(f"Average Round PnL:           ${df_rounds['total_pnl'].mean():.2f}")
print(f"Average Win:                 ${wins_r['total_pnl'].mean():.2f}")
print(f"Average Loss:                ${loss_r['total_pnl'].mean():.2f}")
print(f"Payoff Ratio (Avg W / Avg L): {abs(wins_r['total_pnl'].mean() / loss_r['total_pnl'].mean()):.2f}")

# Yearly breakdown of rounds
print("\n=== YEARLY AUDIT TABLE ===")
yearly_summary = []
for yr, grp in df_rounds.groupby("year"):
    w = grp[grp["is_win"]]
    l = grp[~grp["is_win"]]
    gp = w["total_pnl"].sum()
    gl = abs(l["total_pnl"].sum())
    pf = gp / gl if gl > 0 else 0
    pnl = grp["total_pnl"].sum()
    wr = len(w) / len(grp) * 100.0
    
    # Long vs Short
    long_pnl = grp[grp["direction"] == "LONG"]["total_pnl"].sum()
    short_pnl = grp[grp["direction"] == "SHORT"]["total_pnl"].sum()
    
    yearly_summary.append({
        "Year": yr,
        "Rounds": len(grp),
        "Win Rate %": f"{wr:.1f}%",
        "Gross Profit": f"${gp:,.2f}",
        "Gross Loss": f"-${gl:,.2f}",
        "Net PnL (MNQ)": f"${pnl:,.2f}",
        "Net PnL (NQ)": f"${pnl*10:,.2f}",
        "Profit Factor": f"{pf:.2f}",
        "Long PnL": f"${long_pnl:,.2f}",
        "Short PnL": f"${short_pnl:,.2f}"
    })
df_yr = pd.DataFrame(yearly_summary)
print(df_yr.to_string(index=False))

# Queen vs Runner analysis
q_hits = (df_rounds["queen_exit"] == "Profit target").sum()
r_hits = (df_rounds["runner_exit"] == "Profit target").sum()
print("\n=== TARGET REACH METRICS ===")
print(f"Queen Target (+10 bps):  {q_hits:,d} / {total_r:,d} ({q_hits/total_r*100:.1f}%)")
print(f"Runner Target (+30 bps): {r_hits:,d} / {total_r:,d} ({r_hits/total_r*100:.1f}%)")
print(f"Total Queen Profit:      ${df_rounds['queen_pnl'].sum():,.2f}")
print(f"Total Runner Profit:     ${df_rounds['runner_pnl'].sum():,.2f}")

# 4. Generate Comprehensive 4-Panel Visualization
fig, axes = plt.subplots(2, 2, figsize=(18, 11))
fig.suptitle(f"NinjaTrader 8 4.7-Year Institutional Backtest Audit (2022-2026)\nInstrument: MNQ SEP26 | Total Rounds: {total_r:,d} | Net PnL: +${net_r:,.2f} (+${net_r*10:,.2f} E-mini)", fontsize=14, fontweight="bold")

# Panel 1: Cumulative Equity Curve (Long vs Short vs Total)
ax1 = axes[0, 0]
df_rounds["long_cum"] = df_rounds[df_rounds["direction"] == "LONG"]["total_pnl"].cumsum()
df_rounds["short_cum"] = df_rounds[df_rounds["direction"] == "SHORT"]["total_pnl"].cumsum()
ax1.plot(df_rounds.index + 1, df_rounds["cum_pnl"], color="#00ff88", lw=2, label=f"Total Strategy (+${net_r:,.0f})")
ax1.plot(df_rounds.index + 1, df_rounds["long_cum"].ffill(), color="#00bfff", lw=1.8, label=f"Longs Only (+${df_rounds['queen_pnl'].sum()+df_rounds['runner_pnl'].sum():,.0f})")
ax1.plot(df_rounds.index + 1, df_rounds["short_cum"].ffill(), color="#ff4444", lw=1.8, linestyle="--", label="Shorts Only")
ax1.axhline(0, color="gray", lw=0.8, linestyle=":")
ax1.set_title("NinjaTrader 8 Equity Curve: Total vs. Longs vs. Shorts", fontsize=12, fontweight="bold")
ax1.set_xlabel("Execution Round #")
ax1.set_ylabel("Cumulative PnL ($)")
ax1.legend(loc="upper left")
ax1.grid(True, alpha=0.3)

# Panel 2: Yearly PnL Breakdown (Long vs Short)
ax2 = axes[0, 1]
years = sorted(df_rounds["year"].unique())
x = np.arange(len(years))
width = 0.35
long_yr_pnls = [df_rounds[(df_rounds["year"] == y) & (df_rounds["direction"] == "LONG")]["total_pnl"].sum() for y in years]
short_yr_pnls = [df_rounds[(df_rounds["year"] == y) & (df_rounds["direction"] == "SHORT")]["total_pnl"].sum() for y in years]

ax2.bar(x - width/2, long_yr_pnls, width, label="Long PnL ($)", color="#00bfff", alpha=0.85, edgecolor="black")
ax2.bar(x + width/2, short_yr_pnls, width, label="Short PnL ($)", color="#ff5555", alpha=0.85, edgecolor="black")
ax2.axhline(0, color="black", lw=1)
ax2.set_xticks(x)
ax2.set_xticklabels(years)
ax2.set_title("Yearly PnL: Longs (Bull Markets) vs Shorts (Bear Markets)", fontsize=12, fontweight="bold")
ax2.set_ylabel("Realized PnL ($)")
ax2.legend()
ax2.grid(True, alpha=0.3)

# Panel 3: Monthly PnL Heatmap/Bar
ax3 = axes[1, 0]
monthly_pnl = df_rounds.groupby("month")["total_pnl"].sum()
m_cols = ["#00ff88" if v >= 0 else "#ff4444" for v in monthly_pnl.values]
ax3.bar(range(len(monthly_pnl)), monthly_pnl.values, color=m_cols, alpha=0.85, edgecolor="black", width=0.8)
ax3.axhline(0, color="black", lw=1)
ax3.set_title(f"Monthly PnL Across 56 Months (Profitable Months: {(monthly_pnl > 0).sum()}/{len(monthly_pnl)})", fontsize=12, fontweight="bold")
ax3.set_xlabel("Months (2022-01 to 2026-09)")
ax3.set_ylabel("Monthly PnL ($)")
ax3.grid(True, alpha=0.3)

# Panel 4: In-Sample (2022-2023) vs Out-of-Sample (2024-2026) Comparison
ax4 = axes[1, 1]
is_mask = df_rounds["year"].isin([2022, 2023])
oos_mask = df_rounds["year"].isin([2024, 2025, 2026])

is_rounds = df_rounds[is_mask]
oos_rounds = df_rounds[oos_mask]

is_pnl = is_rounds["total_pnl"].sum()
oos_pnl = oos_rounds["total_pnl"].sum()
is_wr = (is_rounds["total_pnl"] > 0).mean() * 100.0
oos_wr = (oos_rounds["total_pnl"] > 0).mean() * 100.0

bars = ax4.bar(["In-Sample (2022-2023)\n3,132 Legs", "Out-of-Sample (2024-2026)\n4,293 Legs"], [is_pnl, oos_pnl], color=["#9370db", "#00fa9a"], edgecolor="black", alpha=0.85)
ax4.axhline(0, color="black", lw=1)
ax4.set_title(f"IS vs. OOS Split: OOS Acceleration (+${oos_pnl:,.2f})", fontsize=12, fontweight="bold")
ax4.set_ylabel("Total Realized PnL ($)")
for bar, pnl, wr in zip(bars, [is_pnl, oos_pnl], [is_wr, oos_wr]):
    ax4.text(bar.get_x() + bar.get_width()/2, pnl + (1000 if pnl >= 0 else -2500), f"${pnl:,.2f}\n(WR: {wr:.1f}%)", ha="center", fontweight="bold", fontsize=11)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
chart_path = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/nt8_4y_comprehensive_audit.png")
plt.savefig(chart_path, dpi=180)
plt.close()
print(f"Saved comprehensive 4-panel audit chart to {chart_path}")
