"""
Cross-Platform Trade-by-Trade Reconciler: NinjaTrader 8 vs Python Parity Engine
Target: NQ 09-26 (June 1, 2026 to August 25, 2026)
"""

import json
import pandas as pd
import numpy as np
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def main():
    # 1. Load NT8 trade log
    nt8_json_path = "C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/.system_generated/steps/723/output.txt"
    with open(nt8_json_path, "r") as f:
        nt8_raw = json.load(f)

    nt8_trades = nt8_raw["trades"]
    df_nt = pd.DataFrame(nt8_trades)
    df_nt["entryTime"] = pd.to_datetime(df_nt["entryTime"])
    df_nt["exitTime"] = pd.to_datetime(df_nt["exitTime"])

    # Aggregate by entryTime
    nt_entries = df_nt.groupby("entryTime").agg(
        direction=("marketPosition", "first"),
        entry_price=("entryPrice", "first"),
        pnl_usd=("profitCurrency", "sum"),
        points=("profitPoints", "sum"),
        exit_names=("exitName", lambda x: list(x)),
        exit_times=("exitTime", lambda x: list(x)),
    ).reset_index()

    print(f"Total NT8 Entries: {len(nt_entries)}")
    print(f"NT8 Total P&L: ${nt_entries['pnl_usd'].sum():,.2f}")
    print(f"NT8 Win Rate: {(nt_entries['pnl_usd'] > 0).mean()*100:.1f}%")

    # 2. Load exact bars
    csv_path = r"C:\Users\vinay\Documents\NinjaTrader 8\mcp_bars_NQ_09_26_Minute5.csv"
    df_bars = pd.read_csv(csv_path)
    df_bars.columns = [c.strip().lower() for c in df_bars.columns]
    df_bars["time"] = pd.to_datetime(df_bars["time"])
    df_bars = df_bars.set_index("time").sort_index()
    print(f"Loaded {len(df_bars)} bars from {df_bars.index[0]} to {df_bars.index[-1]}")

    # Check NT8 entry timestamps against df_bars
    matched = 0
    for idx, row in nt_entries.iterrows():
        t = row["entryTime"]
        if t in df_bars.index:
            matched += 1
        else:
            print(f"NT8 entry time {t} not in bar index!")
    print(f"Matched {matched}/{len(nt_entries)} NT8 entry timestamps in bar data.")


if __name__ == "__main__":
    main()
