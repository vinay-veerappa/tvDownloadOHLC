import json
import pandas as pd
import numpy as np
from pathlib import Path

# Load NT8 ES backtest results
json_path = Path(r"C:\Users\vinay\.gemini\antigravity\brain\4c21dcc0-89c9-42df-8e6a-fc48ef5552a9\.system_generated\steps\867\output.txt")
with open(json_path) as f:
    nt8_data = json.load(f)

nt8_metrics = nt8_data["metrics"]
nt8_trades = nt8_data["trades"]
df_nt = pd.DataFrame(nt8_trades)
df_nt["entryTime"] = pd.to_datetime(df_nt["entryTime"])

nt_entries = df_nt.groupby("entryTime").agg(
    direction=("marketPosition", "first"),
    entry_price=("entryPrice", "first"),
    total_pnl_usd=("profitCurrency", "sum"),
    total_points=("profitPoints", "sum"),
    exit_names=("exitName", lambda x: list(x))
).reset_index()

print("=========================================================================")
print("NINJATRADER 8 STRATEGY ANALYZER VERIFICATION: ES 09-26 (5-Minute)")
print("=========================================================================")
print(f"Total Completed Entries : {len(nt_entries)}")
print(f"Total Executed Orders   : {nt8_metrics['totalTrades']} (Queen + Runner legs)")
print(f"Entry Win Rate          : {nt8_metrics['entryWinRatePct']:.1f}%")
print(f"Trade Win Rate          : {nt8_metrics['tradeWinRatePct']:.1f}%")
print(f"Profit Factor           : {nt8_metrics['profitFactor']:.3f}")
print(f"Gross Profit            : ${nt8_metrics['grossProfit']:,.2f}")
print(f"Gross Loss              : ${nt8_metrics['grossLoss']:,.2f}")
print(f"Net Profit              : ${nt8_metrics['netProfit']:,.2f}")
print(f"Max Drawdown            : ${nt8_metrics['maxDrawdown']:,.2f}")
print(f"Max Loss per Entry      : ${nt8_metrics['maxLossEntry']:,.2f} (Strict 5.0 bps stop!)")
print(f"Largest Single Winner   : ${nt8_metrics['largestWinner']:,.2f}")

print("\n--- Top Winning Entries in NT8 ---")
winners = nt_entries[nt_entries["total_pnl_usd"] > 0].sort_values("total_pnl_usd", ascending=False)
for idx, r in winners.head(6).iterrows():
    t_str = str(r["entryTime"])
    d_str = r["direction"]
    px = r["entry_price"]
    pnl = r["total_pnl_usd"]
    pts = r["total_points"]
    ex = r["exit_names"]
    print(f"  {t_str} | {d_str:5} @ {px:7.2f} -> PnL: ${pnl:+8.2f} ({pts:+.2f} pts) | Exits: {ex}")
