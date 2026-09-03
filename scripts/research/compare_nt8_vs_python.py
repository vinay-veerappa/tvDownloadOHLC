import json
import pandas as pd
from pathlib import Path

nt_json_file = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/.system_generated/steps/2803/output.txt")
with open(nt_json_file) as f:
    nt_data = json.load(f)

nt_trades = pd.DataFrame(nt_data["trades"])
nt_trades["entryTime"] = pd.to_datetime(nt_trades["entryTime"])
nt_trades["date"] = nt_trades["entryTime"].dt.date

py_trades = pd.read_csv("data/research/ict_ipda_trade_log.csv")
py_trades["fill_time"] = pd.to_datetime(py_trades["fill_time"])
py_trades["date"] = py_trades["fill_time"].dt.date

min_d = nt_trades["date"].min()
max_d = nt_trades["date"].max()
py_sub = py_trades[(py_trades["date"] >= min_d) & (py_trades["date"] <= max_d)]

print(f"=== CROSS-PLATFORM RECONCILIATION ({min_d} to {max_d}) ===")
print(f"NinjaTrader Strategy Analyzer Summary:")
print(f"  Total Trades (contracts):      {nt_data['metrics']['totalTrades']}")
print(f"  Total Execution Sets (2-Pack): {len(nt_trades)//2}")
print(f"  Gross Profit:                  ${nt_data['metrics']['grossProfit']:,.2f}")
print(f"  Gross Loss:                   -${abs(nt_data['metrics']['grossLoss']):,.2f}")
print(f"  Profit Factor:                 {nt_data['metrics']['profitFactor']}")
print(f"  Net Realized Profit:           ${nt_data['metrics']['netProfit']:,.2f}")
print(f"  Max Drawdown:                  ${nt_data['metrics']['maxDrawdown']:,.2f}")
print(f"  Win Rate (Trades):             {nt_data['metrics']['tradeWinRatePct']:.1f}%")

print("\n--- Daily Trade Frequency Comparison ---")
nt_daily = nt_trades.groupby("date")["quantity"].count() // 2
py_daily = py_sub.groupby("date")["direction"].count()
comp = pd.DataFrame({"NinjaTrader (RTH Only)": nt_daily, "Python (Full Engine)": py_daily}).fillna(0).astype(int)
print(comp)

print("\n--- August 24 Master Setup Verification ---")
print("NinjaTrader Trades on 2026-08-24:")
print(nt_trades[nt_trades["date"] == pd.to_datetime("2026-08-24").date()][["entryTime", "marketPosition", "quantity", "entryPrice", "exitPrice", "profitCurrency", "profitPoints", "exitName"]])

print("\nPython Trades on 2026-08-24 (RTH Window 09:45-15:30):")
rth_py = py_sub[(py_sub["date"] == pd.to_datetime("2026-08-24").date()) & (py_sub["fill_time"].dt.hour >= 9) & (py_sub["fill_time"].dt.hour < 16)]
print(rth_py[["fill_time", "direction", "fill_price", "exit_price", "net_pts", "result", "attempt"]])

