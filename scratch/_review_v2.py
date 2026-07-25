"""Critical review v2: validate fixed calibration predictiveness."""
import pandas as pd
import numpy as np

res = pd.read_parquet("data/derived/ib_breakout_filter_NQ1.parquet")
strict = res[res["strict_filter_pass"] == 1].copy()

# Win is now play3_result > 0
strict["actual_win"] = (strict["target_play3_result"] > 0).astype(float)

print("=== Calibration v2: actual play3 win rate by bucket (strict-pass rows) ===")
for bucket in ["high", "medium", "low"]:
    sub = strict[strict["expectation_bucket"] == bucket]
    if len(sub) == 0:
        continue
    actual = sub["actual_win"].mean()
    emp = sub["empirical_win_rate_strict"].mean()
    print(f"  {bucket}: n={len(sub):5d}  empirical_wr={emp:.4f}  actual_play3_wr={actual:.4f}")

print("\n=== Decile monotonicity (empirical vs actual play3 win) ===")
strict["decile"] = pd.qcut(
    strict["empirical_win_rate_strict"], 10, labels=False, duplicates="drop"
)
for d in sorted(strict["decile"].unique()):
    sub = strict[strict["decile"] == d]
    actual = sub["actual_win"].mean()
    lo = sub["empirical_win_rate_strict"].min()
    hi = sub["empirical_win_rate_strict"].max()
    print(f"  D{d}: n={len(sub):5d}  emp=[{lo:.4f},{hi:.4f}]  actual_play3={actual:.4f}")

print("\n=== Correlation ===")
corr = strict["empirical_win_rate_strict"].corr(strict["actual_win"])
print(f"  Correlation(empirical_wr, actual_play3_win): {corr:.4f}")

print("\n=== Base rate ===")
base = strict["actual_win"].mean()
print(f"  Overall strict-pass play3 win rate: {base:.4f}")

# Leakage check: verify first row per trading_day has NaN or 0 (no same-day leak)
print("\n=== Leakage check: first row per day ===")
sorted_res = res.sort_values(["trading_day", "session_slot"]).reset_index(drop=True)
first_rows = sorted_res.groupby("trading_day").first().reset_index()
print(f"  First-row-per-day count: {len(first_rows)}")
print(f"  First-row NaN empirical_wr: {first_rows['empirical_win_rate_strict'].isna().sum()}")
print(first_rows[["trading_day", "session_slot", "empirical_win_rate_strict"]].head(15).to_string())

# Same-day leakage: check if any row shares empirical info with another same-day row
print("\n=== Same-day leakage verification ===")
# For each trading_day with multiple rows, check if row 2+ has different lag than row 1
multi_days = sorted_res.groupby("trading_day").filter(lambda g: len(g) > 1)
if len(multi_days) > 0:
    # Pick a sample day
    sample_day = multi_days["trading_day"].iloc[0]
    sample = sorted_res[sorted_res["trading_day"] == sample_day]
    print(f"  Sample day {sample_day}: {len(sample)} rows")
    print(sample[["session_slot", "empirical_win_rate_strict", "target_play3_result"]].to_string())