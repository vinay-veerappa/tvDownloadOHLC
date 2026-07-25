"""Critical review: validate calibration predictiveness."""
import pandas as pd
import numpy as np

res = pd.read_parquet("data/derived/ib_breakout_filter_NQ1.parquet")
strict = res[res["strict_filter_pass"] == 1].copy()

# Win = target_realized_dir_ext == break_direction
# break_direction is the column name (first_break_dir in code, break_direction in output)

# 1. Actual win rate by bucket
print("=== Calibration sanity: actual win rate by bucket (strict-pass rows) ===")
for bucket in ["high", "medium", "low"]:
    sub = strict[strict["expectation_bucket"] == bucket]
    if len(sub) == 0:
        continue
    actual = (sub["target_realized_dir_ext"] == sub["break_direction"]).mean()
    emp = sub["empirical_win_rate_strict"].mean()
    print(f"  {bucket}: n={len(sub):5d}  empirical_wr={emp:.4f}  actual_wr={actual:.4f}")

# 2. Decile monotonicity
print("\n=== Decile monotonicity ===")
strict["decile"] = pd.qcut(
    strict["empirical_win_rate_strict"], 10, labels=False, duplicates="drop"
)
for d in sorted(strict["decile"].unique()):
    sub = strict[strict["decile"] == d]
    actual = (sub["target_realized_dir_ext"] == sub["break_direction"]).mean()
    lo = sub["empirical_win_rate_strict"].min()
    hi = sub["empirical_win_rate_strict"].max()
    print(f"  D{d}: n={len(sub):5d}  emp=[{lo:.4f},{hi:.4f}]  actual={actual:.4f}")

# 3. Leakage check: does empirical_win_rate_strict use current-row outcome?
print("\n=== Leakage check: first 10 rows ===")
cols = [
    "trading_day",
    "session_slot",
    "empirical_win_rate_strict",
    "target_realized_dir_ext",
    "break_direction",
]
print(res[cols].head(10).to_string())

# 4. NaN key handling
print("\n=== NaN key handling ===")
nan_strict = strict["empirical_win_rate_strict"].isna().sum()
print(f"  NaN empirical_win_rate_strict in strict-pass rows: {nan_strict}")

# 5. Sort stability: trading_day may have duplicates (multiple sessions per day)
print("\n=== Sort stability: duplicate trading_days ===")
dup_days = res.groupby("trading_day").size()
print(f"  Max rows per trading_day: {dup_days.max()}")
print(f"  Trading days with >1 row: {(dup_days > 1).sum()}")
print(f"  Total rows: {len(res)}, Unique trading_days: {res['trading_day'].nunique()}")

# 6. Session slot distribution within duplicate trading_days
print("\n=== Session slots per duplicate trading_day ===")
multi = dup_days[dup_days > 1].index[:5]
for day in multi:
    sub = res[res["trading_day"] == day]
    print(f"  {day}: slots={sub['session_slot'].tolist()}")