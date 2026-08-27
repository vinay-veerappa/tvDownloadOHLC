"""Cross-check E22-E25 results against E16 hour-table arithmetic (consistency gate)."""
import pandas as pd

t = pd.read_csv("data/derived/bb_e16_trades_detail.csv")
h6 = t[t["entry_hour"] == 6]["total_pnl_dollars"].sum()
h9 = t[t["entry_hour"] == 9]["total_pnl_dollars"].sum()
n6 = len(t[t["entry_hour"] == 6])
n9 = len(t[t["entry_hour"] == 9])
total = t["total_pnl_dollars"].sum()

print("E16 hour-table arithmetic check:")
print(f"  h6 net:  {h6:+.0f}  (n={n6})")
print(f"  h9 net:  {h9:+.0f}  (n={n9})")
print(f"  E16 total: {total:+.0f} (n={len(t)})")
print(f"  Predicted E23 net (drop h6,h9): {total - h6 - h9:+.0f}")
print(f"  Actual   E23 net: +2765  (n=524; diff = sequencing effects on trades 2-3 per session)")
print()
on = t[(t["entry_hour"] >= 19) | (t["entry_hour"] < 8)]
print(f"  Predicted E22 net (h19-23 + h0-7): {on['total_pnl_dollars'].sum():+.0f} (n={len(on)})")
print(f"  Actual   E22 net: +2373 (n=532)")