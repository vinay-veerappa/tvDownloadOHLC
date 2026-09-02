"""
Debug Signal Parity between NT8 and Python
"""

import json
import pandas as pd
import numpy as np

def main():
    nt8_json_path = "C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/.system_generated/steps/723/output.txt"
    with open(nt8_json_path, "r") as f:
        nt8_raw = json.load(f)

    df_nt = pd.DataFrame(nt8_raw["trades"])
    df_nt["entryTime"] = pd.to_datetime(df_nt["entryTime"])
    nt_entries = df_nt.groupby("entryTime").agg(
        direction=("marketPosition", "first"),
        entry_price=("entryPrice", "first"),
        pnl_usd=("profitCurrency", "sum"),
        points=("profitPoints", "sum"),
        exit_names=("exitName", lambda x: list(x)),
    ).reset_index()

    csv_path = r"C:\Users\vinay\Documents\NinjaTrader 8\mcp_bars_NQ_09_26_Minute5.csv"
    df_bars = pd.read_csv(csv_path)
    df_bars.columns = [c.strip().lower() for c in df_bars.columns]
    df_bars["time"] = pd.to_datetime(df_bars["time"])
    df_bars = df_bars.set_index("time").sort_index()

    print("First 10 NT8 entries:")
    for idx, r in nt_entries.head(10).iterrows():
        t = r["entryTime"]
        bar = df_bars.loc[t] if t in df_bars.index else None
        print(f"  {t} | {r['direction']:<5} @ {r['entry_price']:<8.2f} | Close: {bar['close'] if bar is not None else 'N/A'}")


if __name__ == "__main__":
    main()
