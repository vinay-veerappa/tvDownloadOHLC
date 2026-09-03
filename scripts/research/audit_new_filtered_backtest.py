import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

csv_new = Path("NinjaTrader Grid 2026-09-03 04-18 AM.csv")
csv_old = Path("NinjaTrader Grid 2026-09-03 03-59 AM.csv")

def parse_nt_grid(csv_path):
    print(f"Parsing {csv_path.name}...")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    df["Time"] = pd.to_datetime(df["Time"])
    df = df.sort_values("Time", ascending=True).reset_index(drop=True)
    
    long_entries = []
    short_entries = []
    completed = []
    
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
            if action == "Sell":
                if long_entries:
                    entry = long_entries.pop(0)
                    pts = price - entry["price"]
                    pnl = pts * 2.0 * qty
                    bps = (pts / entry["price"]) * 10000.0
                    completed.append({
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
            elif action == "Buy":
                if short_entries:
                    entry = short_entries.pop(0)
                    pts = entry["price"] - price
                    pnl = pts * 2.0 * qty
                    bps = (pts / entry["price"]) * 10000.0
                    completed.append({
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
    df_res = pd.DataFrame(completed)
    df_res["year"] = df_res["entry_time"].dt.year
    df_res["date"] = df_res["entry_time"].dt.date
    return df_res

df_new = parse_nt_grid(csv_new)
df_old = parse_nt_grid(csv_old)

# Summary comparison
def get_metrics(df_trades):
    n_legs = len(df_trades)
    n_rounds = n_legs // 2
    pnl = df_trades["pnl"].sum()
    gp = df_trades[df_trades["pnl"] > 0]["pnl"].sum()
    gl = abs(df_trades[df_trades["pnl"] < 0]["pnl"].sum())
    pf = gp / gl if gl > 0 else 0
    wr = (df_trades["pnl"] > 0).mean() * 100.0
    
    # Drawdown
    # Group by round
    df_trades["cum_pnl"] = df_trades["pnl"].cumsum()
    cum_max = df_trades["cum_pnl"].cummax()
    max_dd = (df_trades["cum_pnl"] - cum_max).min()
    
    # Long vs Short
    long_pnl = df_trades[df_trades["direction"] == "LONG"]["pnl"].sum()
    short_pnl = df_trades[df_trades["direction"] == "SHORT"]["pnl"].sum()
    long_wr = (df_trades[df_trades["direction"] == "LONG"]["pnl"] > 0).mean() * 100.0
    short_wr = (df_trades[df_trades["direction"] == "SHORT"]["pnl"] > 0).mean() * 100.0
    
    return {
        "legs": n_legs,
        "rounds": n_rounds,
        "net_pnl": pnl,
        "gp": gp,
        "gl": gl,
        "pf": pf,
        "wr": wr,
        "max_dd": max_dd,
        "long_pnl": long_pnl,
        "short_pnl": short_pnl,
        "long_wr": long_wr,
        "short_wr": short_wr
    }

m_new = get_metrics(df_new)
m_old = get_metrics(df_old)

print("=" * 80)
print("COMPARATIVE AUDIT: FILTERED VS UNFILTERED NINJATRADER BACKTEST")
print("=" * 80)
print(f"{'Metric':<30s} | {'Unfiltered (Previous)':<22s} | {'Filtered (New)':<22s} | {'Delta / Improvement'}")
print("-" * 95)
print(f"{'Total Trade Legs':<30s} | {m_old['legs']:<22,d} | {m_new['legs']:<22,d} | {m_new['legs'] - m_old['legs']:,d} ({((m_new['legs']/m_old['legs'])-1)*100:.1f}%)")
print(f"{'Total Execution Rounds':<30s} | {m_old['rounds']:<22,d} | {m_new['rounds']:<22,d} | {m_new['rounds'] - m_old['rounds']:,d}")
print(f"{'Net Realized PnL (Micro MNQ)':<30s} | ${m_old['net_pnl']:<21,.2f} | ${m_new['net_pnl']:<21,.2f} | ${m_new['net_pnl'] - m_old['net_pnl']:+,.2f}")
print(f"{'Net Realized PnL (E-mini NQ)':<30s} | ${m_old['net_pnl']*10:<21,.2f} | ${m_new['net_pnl']*10:<21,.2f} | ${((m_new['net_pnl'] - m_old['net_pnl'])*10):+,.2f}")
print(f"{'Profit Factor':<30s} | {m_old['pf']:<22.3f} | {m_new['pf']:<22.3f} | {m_new['pf'] - m_old['pf']:+.3f}")
print(f"{'Leg Win Rate %':<30s} | {m_old['wr']:<21.1f}% | {m_new['wr']:<21.1f}% | {m_new['wr'] - m_old['wr']:+.1f}%")
print(f"{'Max Drawdown (MNQ)':<30s} | ${m_old['max_dd']:<21,.2f} | ${m_new['max_dd']:<21,.2f} | ${m_new['max_dd'] - m_old['max_dd']:+,.2f}")
print(f"{'Long Realized PnL':<30s} | ${m_old['long_pnl']:<21,.2f} | ${m_new['long_pnl']:<21,.2f} | ${m_new['long_pnl'] - m_old['long_pnl']:+,.2f}")
print(f"{'Short Realized PnL':<30s} | ${m_old['short_pnl']:<21,.2f} | ${m_new['short_pnl']:<21,.2f} | ${m_new['short_pnl'] - m_old['short_pnl']:+,.2f}")

print("\n=== YEARLY BREAKDOWN (NEW FILTERED BACKTEST) ===")
for yr, grp in df_new.groupby("year"):
    yr_pnl = grp["pnl"].sum()
    yr_gp = grp[grp["pnl"] > 0]["pnl"].sum()
    yr_gl = abs(grp[grp["pnl"] < 0]["pnl"].sum())
    yr_pf = yr_gp / yr_gl if yr_gl > 0 else 0
    yr_wr = (grp["pnl"] > 0).mean() * 100.0
    l_pnl = grp[grp["direction"] == "LONG"]["pnl"].sum()
    s_pnl = grp[grp["direction"] == "SHORT"]["pnl"].sum()
    print(f"Year {yr}: Legs: {len(grp):4d} | WR: {yr_wr:5.1f}% | Net PnL: ${yr_pnl:10,.2f} | PF: {yr_pf:5.2f} (E-mini: ${yr_pnl*10:11,.2f}) | Long: ${l_pnl:9,.2f} | Short: ${s_pnl:9,.2f}")

# Save filtered trades
df_new.to_parquet("data/research/nt8_filtered_trades.parquet", index=False)
df_new.to_csv("data/research/nt8_filtered_trades.csv", index=False)

# 4-Panel Visualization
fig, axes = plt.subplots(2, 2, figsize=(18, 11))
fig.suptitle(f"NinjaTrader 8 Filtered Strategy Audit | Net PnL: +${m_new['net_pnl']:,.2f} (+${m_new['net_pnl']*10:,.2f} E-mini) | PF: {m_new['pf']:.2f}", fontsize=14, fontweight="bold")

# Panel 1: Equity Curve Comparison (Filtered vs Unfiltered)
ax1 = axes[0, 0]
df_old["cum_pnl"] = df_old["pnl"].cumsum()
df_new["cum_pnl"] = df_new["pnl"].cumsum()
ax1.plot(df_old["entry_time"], df_old["cum_pnl"], color="gray", alpha=0.6, lw=1.5, label=f"Unfiltered (+${m_old['net_pnl']:,.0f})")
ax1.plot(df_new["entry_time"], df_new["cum_pnl"], color="#00ff88", lw=2.2, label=f"Filtered (+${m_new['net_pnl']:,.0f})")
ax1.axhline(0, color="gray", linestyle=":", lw=0.8)
ax1.set_title("Cumulative Equity Curve: Filtered vs. Unfiltered", fontsize=12, fontweight="bold")
ax1.set_ylabel("PnL ($)")
ax1.legend()
ax1.grid(True, alpha=0.3)

# Panel 2: Yearly Comparison Bar Chart
ax2 = axes[0, 1]
years = sorted(list(set(df_new["year"]).union(set(df_old["year"]))))
x = np.arange(len(years))
width = 0.35
old_yr_pnl = [df_old[df_old["year"] == y]["pnl"].sum() for y in years]
new_yr_pnl = [df_new[df_new["year"] == y]["pnl"].sum() for y in years]
ax2.bar(x - width/2, old_yr_pnl, width, label="Unfiltered PnL ($)", color="#ff5555", alpha=0.75, edgecolor="black")
ax2.bar(x + width/2, new_yr_pnl, width, label="Filtered PnL ($)", color="#00ff88", alpha=0.85, edgecolor="black")
ax2.axhline(0, color="black", lw=1)
ax2.set_xticks(x)
ax2.set_xticklabels(years)
ax2.set_title("Year-by-Year Realized PnL Comparison", fontsize=12, fontweight="bold")
ax2.set_ylabel("PnL ($)")
ax2.legend()
ax2.grid(True, alpha=0.3)

# Panel 3: Long vs Short in Filtered
ax3 = axes[1, 0]
ax3.bar(["Long Legs", "Short Legs"], [m_new["long_pnl"], m_new["short_pnl"]], color=["#00bfff", "#ff9900" if m_new["short_pnl"]>=0 else "#ff4444"], edgecolor="black", alpha=0.85)
ax3.axhline(0, color="black", lw=1)
ax3.set_title(f"Filtered Direction Breakdown: Long (+${m_new['long_pnl']:,.0f}) vs. Short (-${abs(m_new['short_pnl']):,.0f})", fontsize=12, fontweight="bold")
ax3.set_ylabel("PnL ($)")
for i, v in enumerate([m_new["long_pnl"], m_new["short_pnl"]]):
    ax3.text(i, v/2 if abs(v) > 5000 else v + (1000 if v>=0 else -2000), f"${v:,.2f}", ha="center", va="center", color="black" if abs(v) > 5000 else "white", fontweight="bold", fontsize=11)
ax3.grid(True, alpha=0.3)

# Panel 4: Filter Cut Efficiency (Noise Reduction)
ax4 = axes[1, 1]
cut_trades = m_old["legs"] - m_new["legs"]
pct_cut = (cut_trades / m_old["legs"]) * 100.0
ax4.pie([m_new["legs"], cut_trades], labels=[f"Kept Clean\n{m_new['legs']:,d} legs ({100-pct_cut:.1f}%)", f"Filtered Out Noise\n{cut_trades:,d} legs ({pct_cut:.1f}%)"], colors=["#00ff88", "#ff4444"], autopct="%1.1f%%", startangle=90, explode=[0.05, 0], textprops={"fontsize": 11, "fontweight": "bold"})
ax4.set_title(f"Noise Filtering Efficiency ({cut_trades:,d} Low-Quality Trades Cut)", fontsize=12, fontweight="bold")

plt.tight_layout()
out_chart = Path("C:/Users/vinay/.gemini/antigravity/brain/4c21dcc0-89c9-42df-8e6a-fc48ef5552a9/nt8_filtered_vs_unfiltered_audit.png")
plt.savefig(out_chart, dpi=180)
plt.close()
print(f"Saved comparison dashboard to {out_chart}")
