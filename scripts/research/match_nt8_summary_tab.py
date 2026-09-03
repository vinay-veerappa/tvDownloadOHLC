import pandas as pd
import numpy as np

csv_path = "NinjaTrader Grid 2026-09-03 04-18 AM.csv"
df = pd.read_csv(csv_path)
df.columns = [c.strip() for c in df.columns]

# NinjaTrader exports execution grid in reverse chronological order.
# Reversing it gives exact FIFO chronological execution order:
df = df.iloc[::-1].reset_index(drop=True)
df["Time"] = pd.to_datetime(df["Time"])

# Parse all completed trade legs
open_positions = []
completed_trades = []

for idx, row in df.iterrows():
    ex = row["E/X"].strip()
    action = row["Action"].strip()
    qty = int(row["Quantity"])
    price = float(row["Price"])
    name = str(row["Name"]).strip()
    t = row["Time"]
    
    if ex == "Entry":
        open_positions.append(row)
    elif ex == "Exit":
        if open_positions:
            ent = open_positions.pop(0)
            dir_mult = 1 if ent["Action"].strip() == "Buy" else -1
            pts = (price - float(ent["Price"])) * dir_mult
            pnl = pts * 2.0 * qty  # $2 per pt for MNQ
            completed_trades.append({
                "entry_time": ent["Time"],
                "exit_time": t,
                "entry_year": ent["Time"].year,
                "exit_year": t.year,
                "direction": "LONG" if dir_mult == 1 else "SHORT",
                "entry_price": float(ent["Price"]),
                "exit_price": price,
                "points": pts,
                "pnl": pnl,
                "exit_name": name,
                "contract": str(ent["Name"]).strip()
            })

df_trades = pd.DataFrame(completed_trades)

print("=" * 85)
print("NINJATRADER 8 SUMMARY TAB AUDIT (EXACT FIFO MATCH)")
print("=" * 85)

# Overall Summary
gp = df_trades[df_trades["pnl"] > 0]["pnl"].sum()
gl = abs(df_trades[df_trades["pnl"] < 0]["pnl"].sum())
pf = gp / gl if gl > 0 else 0
pnl = df_trades["pnl"].sum()
wr = (df_trades["pnl"] > 0).mean() * 100.0

print(f"Overall (All Years Combined):")
print(f"  Total Trades:     {len(df_trades):,d} legs ({len(df_trades)//2:,d} rounds)")
print(f"  Net Realized PnL: ${pnl:,.2f} (Micro MNQ) | ${pnl * 10:,.2f} (E-mini NQ)")
print(f"  Gross Profit:     ${gp:,.2f}")
print(f"  Gross Loss:      -${gl:,.2f}")
print(f"  Profit Factor:    {pf:.3f}")
print(f"  Win Rate:         {wr:.1f}%")

print("\n--- Year-by-Year Performance (by Exit Year) ---")
print(f"{'Year':<6s} | {'Legs':<6s} | {'Win Rate':<9s} | {'Gross Profit':<14s} | {'Gross Loss':<14s} | {'Net PnL (MNQ)':<14s} | {'PF':<6s}")
print("-" * 85)

for yr, grp in df_trades.groupby("exit_year"):
    yr_pnl = grp["pnl"].sum()
    yr_gp = grp[grp["pnl"] > 0]["pnl"].sum()
    yr_gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    yr_pf = yr_gp / yr_gl if yr_gl > 0 else 0
    yr_wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"{yr:<6d} | {len(grp):<6d} | {yr_wr:<8.1f}% | ${yr_gp:<13,.2f} | -${yr_gl:<12,.2f} | ${yr_pnl:<13,.2f} | {yr_pf:<6.2f}")

print("\n--- Direction Breakdown (Longs vs Shorts) ---")
for d, grp in df_trades.groupby("direction"):
    d_pnl = grp["pnl"].sum()
    d_gp = grp[grp["pnl"] > 0]["pnl"].sum()
    d_gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    d_pf = d_gp / d_gl if d_gl > 0 else 0
    d_wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"{d:5s} | Legs: {len(grp):<5d} | Win Rate: {d_wr:.1f}% | Gross Profit: ${d_gp:,.2f} | Gross Loss: -${d_gl:,.2f} | Net PnL: ${d_pnl:,.2f} | PF: {d_pf:.2f}")
