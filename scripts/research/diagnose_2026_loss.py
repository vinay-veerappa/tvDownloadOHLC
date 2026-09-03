import pandas as pd
import numpy as np

df = pd.read_csv("NinjaTrader Grid 2026-09-03 04-18 AM.csv")
df.columns = [c.strip() for c in df.columns]
df = df.iloc[::-1].reset_index(drop=True)
df["Time"] = pd.to_datetime(df["Time"])

rounds = []
cur_round_entries = []
cur_round_exits = []

for idx, row in df.iterrows():
    ex = row["E/X"].strip()
    pos = str(row["Position"]).strip()
    if ex == "Entry": cur_round_entries.append(row)
    elif ex == "Exit": cur_round_exits.append(row)
    if pos == "-" and (cur_round_entries or cur_round_exits):
        dir_mult = 1 if cur_round_entries[0]["Action"].strip() == "Buy" else -1
        round_pnl = 0.0
        round_pts = 0.0
        exit_names = [e["Name"] for e in cur_round_exits]
        entry_prices = [float(e["Price"]) for e in cur_round_entries]
        exit_prices = [float(e["Price"]) for e in cur_round_exits]
        
        for ent, ext in zip(cur_round_entries, cur_round_exits):
            pts = (float(ext["Price"]) - float(ent["Price"])) * dir_mult
            pnl = pts * 2.0 * int(ent["Quantity"])
            round_pnl += pnl
            round_pts += pts
            
        rounds.append({
            "entry_time": cur_round_entries[0]["Time"],
            "exit_time": cur_round_exits[-1]["Time"],
            "year": cur_round_entries[0]["Time"].year,
            "direction": "LONG" if dir_mult == 1 else "SHORT",
            "entry_price": entry_prices[0],
            "pnl": round_pnl,
            "pts": round_pts,
            "exit_names": exit_names,
            "target_hit": any("Profit target" in str(x) for x in exit_names),
            "stopped_out": any("Stop loss" in str(x) for x in exit_names)
        })
        cur_round_entries = []
        cur_round_exits = []

df_rounds = pd.DataFrame(rounds)
df_2026 = df_rounds[df_rounds["year"] == 2026].copy()

print("=" * 80)
print("DEEP FORENSIC AUTOPSY: YEAR 2026 (-$483.50, PF 0.93)")
print("=" * 80)
print(f"Total Rounds:               {len(df_2026)}")
print(f"Net Realized PnL:           ${df_2026['pnl'].sum():,.2f}")
print(f"Gross Profit:               ${df_2026[df_2026['pnl'] > 0]['pnl'].sum():,.2f}")
print(f"Gross Loss:                -${abs(df_2026[df_2026['pnl'] < 0]['pnl'].sum()):,.2f}")
print(f"Profit Factor:              {df_2026[df_2026['pnl'] > 0]['pnl'].sum() / abs(df_2026[df_2026['pnl'] < 0]['pnl'].sum()):.3f}")

# Long vs Short in 2026
print("\n--- Long vs Short in 2026 ---")
for d, grp in df_2026.groupby("direction"):
    gp = grp[grp["pnl"] > 0]["pnl"].sum()
    gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    pnl = grp["pnl"].sum()
    pf = gp / gl if gl > 0 else 0
    wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"{d:5s}: Rounds: {len(grp):3d} | WR: {wr:5.1f}% | Net PnL: ${pnl:8,.2f} | GP: ${gp:8,.2f} | GL: -${gl:8,.2f} | PF: {pf:.2f}")

# Target reaches in 2026
target_rounds = df_2026[df_2026["target_hit"]]
pure_stops = df_2026[~df_2026["target_hit"]]
print(f"\nRounds with at least 1 Target Hit: {len(target_rounds)} ({len(target_rounds)/len(df_2026)*100:.1f}%) | Net PnL: ${target_rounds['pnl'].sum():,.2f}")
print(f"Rounds with Pure Stop Outs:        {len(pure_stops)} ({len(pure_stops)/len(df_2026)*100:.1f}%) | Net PnL: ${pure_stops['pnl'].sum():,.2f}")

# Loss sizes
print(f"\nAverage Winning Round:  +${df_2026[df_2026['pnl'] > 0]['pnl'].mean():.2f}")
print(f"Average Losing Round:   -${abs(df_2026[df_2026['pnl'] < 0]['pnl'].mean()):.2f}")
print(f"Payoff Ratio (W / L):    {abs(df_2026[df_2026['pnl'] > 0]['pnl'].mean() / df_2026[df_2026['pnl'] < 0]['pnl'].mean()):.2f}")

# Monthly distribution in 2026
df_2026["month"] = df_2026["entry_time"].dt.month_name()
print("\n--- Monthly Performance in 2026 ---")
for m, grp in df_2026.groupby("month", sort=False):
    gp = grp[grp["pnl"] > 0]["pnl"].sum()
    gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    pnl = grp["pnl"].sum()
    pf = gp / gl if gl > 0 else 0
    wr = (grp["pnl"] > 0).mean() * 100.0
    print(f"{m:9s}: Rounds: {len(grp):2d} | WR: {wr:5.1f}% | Net PnL: ${pnl:8,.2f} | PF: {pf:.2f}")
