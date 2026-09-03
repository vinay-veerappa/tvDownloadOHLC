import pandas as pd

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
        for ent, ext in zip(cur_round_entries, cur_round_exits):
            pts = (float(ext["Price"]) - float(ent["Price"])) * dir_mult
            pnl = pts * 2.0 * int(ent["Quantity"])
            round_pnl += pnl
            round_pts += pts
        rounds.append({
            "year": cur_round_entries[0]["Time"].year,
            "direction": "LONG" if dir_mult == 1 else "SHORT",
            "pnl": round_pnl,
            "pts": round_pts
        })
        cur_round_entries = []
        cur_round_exits = []

df_rounds = pd.DataFrame(rounds)

print("=" * 85)
print("EXACT NINJATRADER SUMMARY TAB AUDIT (BY YEAR)")
print("=" * 85)
for yr, grp in df_rounds.groupby("year"):
    gp = grp[grp["pnl"] > 0]["pnl"].sum()
    gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    pnl = grp["pnl"].sum()
    pf = gp / gl if gl > 0 else 0
    wr = (grp["pnl"] > 0).mean() * 100.0
    l_pnl = grp[grp["direction"] == "LONG"]["pnl"].sum()
    s_pnl = grp[grp["direction"] == "SHORT"]["pnl"].sum()
    print(f"Year {yr}: Rounds: {len(grp):4d} | WR: {wr:5.1f}% | Net PnL: ${pnl:10,.2f} | GP: ${gp:10,.2f} | GL: -${gl:10,.2f} | PF: {pf:5.2f} | Long: ${l_pnl:9,.2f} | Short: ${s_pnl:9,.2f}")

overall_gp = df_rounds[df_rounds["pnl"] > 0]["pnl"].sum()
overall_gl = abs(df_rounds[df_rounds["pnl"] < 0]["pnl"].sum())
overall_pnl = df_rounds["pnl"].sum()
overall_pf = overall_gp / overall_gl if overall_gl > 0 else 0
overall_wr = (df_rounds["pnl"] > 0).mean() * 100.0
print("-" * 85)
print(f"OVERALL:   Rounds: {len(df_rounds):4d} | WR: {overall_wr:5.1f}% | Net PnL: ${overall_pnl:10,.2f} | GP: ${overall_gp:10,.2f} | GL: -${overall_gl:10,.2f} | PF: {overall_pf:5.2f}")
