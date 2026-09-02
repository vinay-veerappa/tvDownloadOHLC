"""
Compare trade-by-trade outcomes between NT8 and Python
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
    df_nt["exitTime"] = pd.to_datetime(df_nt["exitTime"])

    nt_entries = df_nt.groupby("entryTime").agg(
        direction=("marketPosition", "first"),
        entry_price=("entryPrice", "first"),
        pnl_usd=("profitCurrency", "sum"),
        points=("profitPoints", "sum"),
        exit_names=("exitName", lambda x: list(x)),
        exit_times=("exitTime", lambda x: list(x)),
    ).reset_index()

    print("="*120)
    print("NINJATRADER 8 GROUND-TRUTH ENTRY LOG (ALL 46 ENTRIES)")
    print("="*120)
    print(f"{'Idx':<4} {'Entry Time':<20} {'Dir':<5} {'Entry Px':<10} {'NT8 P&L':<12} {'NT8 Exits'}")
    print("-" * 120)
    for idx, r in nt_entries.iterrows():
        print(f"{idx+1:<4} {str(r['entryTime']):<20} {r['direction']:<5} {r['entry_price']:<10.2f} ${r['pnl_usd']:<11,.2f} {r['exit_names']}")


if __name__ == "__main__":
    main()
