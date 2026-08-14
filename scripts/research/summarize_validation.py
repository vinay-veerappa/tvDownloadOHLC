import json
from pathlib import Path

report_path = Path("reports/research/subgrid_validation.json")
if not report_path.exists():
    print("Report not found")
    exit(1)

with open(report_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 125)
print(f"{'SYM':<5} | {'ASSET CLASS':<14} | {'GRID':<6} | {'STOP':<6} | {'TARG':<6} | {'TOUCHES':<8} | {'WIN RATE':<9} | {'PF':<6} | {'IB WR':<7} | {'IB PF':<6} | {'REP 5M':<7} | {'REP 50M':<7} | {'CHI2 P-VAL':<10}")
print("=" * 125)

asset_names = {
    "NQ": "Nasdaq-100",
    "ES": "S&P 500",
    "YM": "Dow Jones",
    "RTY": "Russell 2000",
    "CL": "Crude Oil",
    "GC": "Gold Futures"
}

for sym, d in data.items():
    cfg = d["config"]
    t1 = d["turning_point_clustering"]
    t2 = d["reaction_expectancy_1m"]
    t3 = d["repairs_decay"]
    ib = t2["session_breakdown"].get("ib", {})
    
    asset = asset_names.get(sym, sym)
    grid = cfg["primary_unit"]
    sl = cfg["std_stop_pts"]
    tp = cfg["std_target_pts"]
    touches = t2["total_touches"]
    wr = t2["win_rate"]
    pf = t2["profit_factor"]
    ib_wr = ib.get("win_rate", 0)
    ib_pf = ib.get("profit_factor", 0)
    rep5 = t3["fill_decay_curve"]["within_5_bars"]
    rep50 = t3["fill_decay_curve"]["within_50_bars"]
    p_val = t1["p_value"]
    
    print(f"{sym:<5} | {asset:<14} | {grid:>6.2f} | {sl:>6.2f} | {tp:>6.2f} | {touches:>8,d} | {wr:>8.2f}% | {pf:>6.3f} | {ib_wr:>6.1f}% | {ib_pf:>6.2f} | {rep5:>6.1f}% | {rep50:>6.1f}% | {p_val:>10.4e}")

print("=" * 125)
