import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

csv_path = Path("NinjaTrader Grid 2026-09-03 03-59 AM.csv")
print(f"Reading {csv_path}...")
df = pd.read_csv(csv_path)
df.columns = [c.strip() for c in df.columns]
# Sort chronologically (earliest to latest)
df["Time"] = pd.to_datetime(df["Time"])
df = df.sort_values("Time", ascending=True).reset_index(drop=True)

print(f"Total records: {len(df)}")
print(f"Date range:    {df['Time'].min()} to {df['Time'].max()}")

# Pair Entries and Exits
# Track open positions by contract name
# Queen leg and Runner leg
trades = []
open_trades = {} # name -> row

# In NinjaTrader, positions are tracked by contract.
# For each round, there are 2 entries: ICT_CISD_Long_Queen and ICT_CISD_Long_Runner (or Short)
# And exits with Name = 'Profit target' or 'Stop loss'

# Let's track using FIFO queue for Long and Short
long_entries = []
short_entries = []
completed_trades = []

for idx, row in df.iterrows():
    ex = row["E/X"].strip()
    action = row["Action"].strip()
    qty = int(row["Quantity"])
    price = float(row["Price"])
    t = row["Time"]
    name = str(row["Name"]).strip()
    
    if ex == "Entry":
        if action == "Buy":
            long_entries.append({"time": t, "price": price, "name": name, "qty": qty})
        elif action == "Sell":
            short_entries.append({"time": t, "price": price, "name": name, "qty": qty})
    elif ex == "Exit":
        if action == "Sell": # Closing Long
            if long_entries:
                entry = long_entries.pop(0)
                pts = price - entry["price"]
                pnl = pts * 2.0 * qty # $2 per pt for MNQ
                bps = (pts / entry["price"]) * 10000.0
                completed_trades.append({
                    "entry_time": entry["time"],
                    "exit_time": t,
                    "direction": "LONG",
                    "contract": entry["name"],
                    "entry_price": entry["price"],
                    "exit_price": price,
                    "exit_name": name,
                    "points": pts,
                    "pnl": pnl,
                    "bps": bps
                })
        elif action == "Buy": # Closing Short
            if short_entries:
                entry = short_entries.pop(0)
                pts = entry["price"] - price
                pnl = pts * 2.0 * qty
                bps = (pts / entry["price"]) * 10000.0
                completed_trades.append({
                    "entry_time": entry["time"],
                    "exit_time": t,
                    "direction": "SHORT",
                    "contract": entry["name"],
                    "entry_price": entry["price"],
                    "exit_price": price,
                    "exit_name": name,
                    "points": pts,
                    "pnl": pnl,
                    "bps": bps
                })

df_comp = pd.DataFrame(completed_trades)
print(f"Total Completed Trade Legs: {len(df_comp)}")
print(f"Net Realized PnL (Micros):   ${df_comp['pnl'].sum():,.2f}")
print(f"Net Realized PnL (Minis):    ${df_comp['pnl'].sum() * 10:,.2f}")
print(f"Gross Profit:                ${df_comp[df_comp['pnl'] > 0]['pnl'].sum():,.2f}")
print(f"Gross Loss:                 -${abs(df_comp[df_comp['pnl'] < 0]['pnl'].sum()):,.2f}")
profit_factor = df_comp[df_comp['pnl'] > 0]['pnl'].sum() / abs(df_comp[df_comp['pnl'] < 0]['pnl'].sum())
print(f"Profit Factor:               {profit_factor:.3f}")
win_rate = (df_comp['pnl'] > 0).mean() * 100.0
print(f"Leg Win Rate:                {win_rate:.1f}%")

# Save trades
df_comp.to_parquet("data/research/nt8_4y_all_trades.parquet", index=False)
df_comp.to_csv("data/research/nt8_4y_all_trades.csv", index=False)

# Breakdown by Year
df_comp["year"] = df_comp["entry_time"].dt.year
print("\n=== PERFORMANCE BY YEAR (Micros) ===")
for yr, grp in df_comp.groupby("year"):
    yr_pnl = grp["pnl"].sum()
    yr_gp = grp[grp["pnl"] > 0]["pnl"].sum()
    yr_gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    yr_pf = yr_gp / yr_gl if yr_gl > 0 else np.nan
    yr_wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"Year {yr}: Trades: {len(grp):4d} | WR: {yr_wr:5.1f}% | Net PnL: ${yr_pnl:10,.2f} | PF: {yr_pf:5.2f} (E-mini: ${yr_pnl*10:11,.2f})")

# Breakdown by Contract (Queen vs Runner)
print("\n=== PERFORMANCE BY CONTRACT LEG ===")
for cname, grp in df_comp.groupby("contract"):
    c_pnl = grp["pnl"].sum()
    c_wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"Leg: {cname:25s} | Trades: {len(grp):4d} | WR: {c_wr:5.1f}% | Net PnL: ${c_pnl:10,.2f}")
