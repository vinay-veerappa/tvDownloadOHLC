import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# Set style
plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")

# 1. Load NinjaTrader output JSON
json_path = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/.system_generated/steps/2803/output.txt")
with open(json_path) as f:
    nt_data = json.load(f)

trades_raw = nt_data["trades"]
df_nt = pd.DataFrame(trades_raw)
df_nt["entryTime"] = pd.to_datetime(df_nt["entryTime"])
df_nt["exitTime"] = pd.to_datetime(df_nt["exitTime"])
df_nt["date"] = df_nt["entryTime"].dt.date
df_nt["cum_profit"] = df_nt["profitCurrency"].cumsum()

# Save NT8 trades
out_dir = Path("data/research")
out_dir.mkdir(parents=True, exist_ok=True)
df_nt.to_csv(out_dir / "nt8_ict_backtest_trades.csv", index=False)
df_nt.to_parquet(out_dir / "nt8_ict_backtest_trades.parquet", index=False)
print(f"Saved {len(df_nt)} NT8 trade legs to {out_dir / 'nt8_ict_backtest_trades.csv'}")

# Group into 2-pack rounds
rounds = []
for i in range(0, len(df_nt), 2):
    t1 = df_nt.iloc[i]
    t2 = df_nt.iloc[i+1] if i+1 < len(df_nt) else None
    
    entry_t = t1["entryTime"]
    pos = t1["marketPosition"]
    entry_p = t1["entryPrice"]
    q_pts = t1["profitPoints"]
    q_pnl = t1["profitCurrency"]
    q_exit = t1["exitName"]
    
    r_pts = t2["profitPoints"] if t2 is not None else 0.0
    r_pnl = t2["profitCurrency"] if t2 is not None else 0.0
    r_exit = t2["exitName"] if t2 is not None else "N/A"
    
    total_pnl = q_pnl + r_pnl
    total_pts = q_pts + r_pts
    
    rounds.append({
        "round_id": (i // 2) + 1,
        "date": t1["date"],
        "entry_time": entry_t,
        "position": pos,
        "entry_price": entry_p,
        "queen_pts": q_pts,
        "queen_exit": q_exit,
        "queen_pnl": q_pnl,
        "runner_pts": r_pts,
        "runner_exit": r_exit,
        "runner_pnl": r_pnl,
        "total_pts": total_pts,
        "total_pnl": total_pnl,
        "is_win": total_pnl > 0
    })

df_rounds = pd.DataFrame(rounds)
df_rounds["cum_pnl"] = df_rounds["total_pnl"].cumsum()

# 2. Performance Metrics
total_rounds = len(df_rounds)
wins = df_rounds[df_rounds["is_win"]]
losses = df_rounds[~df_rounds["is_win"]]
win_rate = len(wins) / total_rounds * 100.0
gross_profit = wins["total_pnl"].sum()
gross_loss = abs(losses["total_pnl"].sum())
profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
net_pnl = df_rounds["total_pnl"].sum()

# Max Drawdown
cum_max = df_rounds["cum_pnl"].cummax()
drawdown = df_rounds["cum_pnl"] - cum_max
max_dd = drawdown.min()

print("=" * 75)
print("NINJATRADER 8 STRATEGY ANALYZER AUDIT: ICTFVGCISDBot")
print("=" * 75)
print(f"Instrument:             MNQ SEP26 (Micro E-mini NQ)")
print(f"Date Range:             {df_rounds['date'].min()} to {df_rounds['date'].max()}")
print(f"Total Execution Rounds: {total_rounds} (88 contract legs)")
print(f"Win Rate:               {win_rate:.1f}% ({len(wins)} W / {len(losses)} L)")
print(f"Gross Profit:           ${gross_profit:,.2f}")
print(f"Gross Loss:            -${gross_loss:,.2f}")
print(f"Profit Factor:          {profit_factor:.2f}")
print(f"Net Realized Profit:    ${net_pnl:,.2f}")
print(f"Max Strategy Drawdown:  ${max_dd:,.2f}")
print(f"Average Trade Round:    ${df_rounds['total_pnl'].mean():.2f}")
print(f"Largest Win Round:      ${df_rounds['total_pnl'].max():.2f}")
print(f"Largest Loss Round:     ${df_rounds['total_pnl'].min():.2f}")

# 3. Generate 4-Panel Verification Dashboard
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle(f"NinjaTrader 8 ICT CISD Bot Verification (MNQ SEP26) | Net PnL: +${net_pnl:,.2f} | PF: {profit_factor:.2f}", fontsize=15, fontweight="bold")

# Panel 1: Cumulative Equity Curve
ax1 = axes[0, 0]
ax1.plot(df_rounds.index + 1, df_rounds["cum_pnl"], color="#00ff88", lw=2.2, label="Cumulative Realized PnL ($)")
ax1.fill_between(df_rounds.index + 1, 0, df_rounds["cum_pnl"], color="#00ff88", alpha=0.15)
ax1.set_title("NinjaTrader 8 Cumulative Equity Curve", fontsize=12, fontweight="bold")
ax1.set_xlabel("Trade Round #")
ax1.set_ylabel("Realized PnL ($)")
ax1.legend(loc="upper left")
ax1.grid(True, alpha=0.3)

# Panel 2: Daily PnL Distribution
ax2 = axes[0, 1]
daily_pnl = df_rounds.groupby("date")["total_pnl"].sum()
colors = ["#00ff88" if x > 0 else "#ff4444" for x in daily_pnl.values]
ax2.bar([str(d)[5:] for d in daily_pnl.index], daily_pnl.values, color=colors, alpha=0.85, edgecolor="black")
ax2.axhline(0, color="gray", lw=1)
ax2.set_title("Daily Realized PnL ($)", fontsize=12, fontweight="bold")
ax2.set_xlabel("Date (MM-DD)")
ax2.set_ylabel("PnL ($)")
for i, v in enumerate(daily_pnl.values):
    ax2.text(i, v + (15 if v >= 0 else -30), f"${v:,.0f}", ha="center", fontsize=8, fontweight="bold")
ax2.grid(True, alpha=0.3)

# Panel 3: Contract Leg PnL Breakdown (Queen +10 bps vs. Runner +30 bps)
ax3 = axes[1, 0]
q_wins = (df_rounds["queen_pnl"] > 0).sum()
r_wins = (df_rounds["runner_pnl"] > 0).sum()
ax3.bar(["Queen (TP1)", "Runner (TP2)"], [df_rounds["queen_pnl"].sum(), df_rounds["runner_pnl"].sum()], color=["#00bfff", "#ffaa00"], edgecolor="black", alpha=0.85)
ax3.set_title(f"Pack Contribution: Queen TP1 ({q_wins}/{total_rounds}) vs. Runner TP2 ({r_wins}/{total_rounds})", fontsize=12, fontweight="bold")
ax3.set_ylabel("Total Profit Contribution ($)")
for i, v in enumerate([df_rounds["queen_pnl"].sum(), df_rounds["runner_pnl"].sum()]):
    ax3.text(i, v / 2, f"${v:,.2f}", ha="center", va="center", color="black", fontweight="bold", fontsize=11)
ax3.grid(True, alpha=0.3)

# Panel 4: August 24 Case Study Trade Walkthrough
ax4 = axes[1, 1]
aug24_trades = df_rounds[df_rounds["date"] == pd.to_datetime("2026-08-24").date()]
trade_labels = [f"#{r['round_id']} {r['entry_time'].strftime('%H:%M')} {r['position']}" for _, r in aug24_trades.iterrows()]
pnls = aug24_trades["total_pnl"].values
bar_cols = ["#00ff88" if x > 0 else "#ff4444" for x in pnls]
ax4.bar(trade_labels, pnls, color=bar_cols, edgecolor="black", alpha=0.85)
ax4.axhline(0, color="gray", lw=1)
ax4.set_title(f"August 24 User Case Study: 10:16 AM Master Long (+${aug24_trades['total_pnl'].sum():,.2f})", fontsize=12, fontweight="bold")
ax4.set_ylabel("Round PnL ($)")
for i, v in enumerate(pnls):
    ax4.text(i, v + (10 if v >= 0 else -15), f"${v:,.2f}", ha="center", fontweight="bold", fontsize=10)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
dashboard_path = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/ninjatrader_ict_validation_dashboard.png")
plt.savefig(dashboard_path, dpi=180)
plt.close()
print(f"Saved dashboard to {dashboard_path}")
