"""E32 diagnostic — exit-structure comparison between E22 (winner) and E32 T-arms (losers)."""
import pandas as pd

t = pd.read_csv("data/derived/bb_e16_trades_detail.csv")
print("E22 actual exits (band-touch entries, band/midband targets):")
print("  t1_hit rate:", round((t["t1_hit"] == True).mean() * 100, 1), "%")
print("  t2_hit rate:", round((t["t2_hit"] == True).mean() * 100, 1), "%")
print("  stopped rate:", round((t["stopped_out"] == True).mean() * 100, 1), "%")
print("  avg win :", round(t[t["total_pnl_dollars"] > 0]["total_pnl_dollars"].mean(), 1))
print("  avg loss:", round(t[t["total_pnl_dollars"] < 0]["total_pnl_dollars"].mean(), 1))
print("  avg risk pts:", round(t["risk_points"].mean(), 2))
print("  avg R:", round(t["r_multiple"].mean(), 3))

# E32 trade-level: how do the T-arms distribute?
t32 = pd.read_csv("data/derived/bb_e32_trades_detail.csv")
print("\nE32 T2_full (BB arm) exits:")
sub = t32[t32["strategy_name"] == "T2_full"]
print("  t1_hit:", round((sub["t1_hit"] == True).mean() * 100, 1), "%",
      " t2_hit:", round((sub["t2_hit"] == True).mean() * 100, 1), "%",
      " stopped:", round((sub["stopped_out"] == True).mean() * 100, 1), "%")
print("  avg win :", round(sub[sub["total_pnl_dollars"] > 0]["total_pnl_dollars"].mean(), 1))
print("  avg loss:", round(sub[sub["total_pnl_dollars"] < 0]["total_pnl_dollars"].mean(), 1))
print("  avg risk pts:", round(sub["risk_points"].mean(), 2))