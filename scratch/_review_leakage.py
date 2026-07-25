"""Critical review: same-day leakage verification."""
import pandas as pd
import numpy as np

res = pd.read_parquet("data/derived/ib_breakout_filter_NQ1.parquet")

# The sort in _walk_forward_calibration is by trading_day only.
# shift(1) is applied after sort, so rows from the same trading_day
# can see each other's outcomes (same-day leakage).
# Check: how many rows have a different trading_day at position i-1?

# Sort by trading_day (as the code does)
sorted_df = res.sort_values(["trading_day"]).reset_index(drop=True)
same_day_as_prev = (sorted_df["trading_day"] == sorted_df["trading_day"].shift(1)).sum()
print(f"Rows where same trading_day as previous row: {same_day_as_prev} / {len(sorted_df)}")
print(f"  => These rows can see same-day outcomes from a different session slot")

# Check: how many strict-pass rows have same-day leakage?
strict = sorted_df[sorted_df["strict_filter_pass"] == 1].copy()
strict_sorted = strict.sort_values(["trading_day"]).reset_index(drop=True)
strict_same_day = (strict_sorted["trading_day"] == strict_sorted["trading_day"].shift(1)).sum()
print(f"Strict-pass rows with same-day predecessor: {strict_same_day} / {len(strict_sorted)}")

# Check: does empirical_win_rate_strict correlate with target_play3_result?
print("\n=== Correlation: empirical_win_rate_strict vs play3_result ===")
strict_pass = res[res["strict_filter_pass"] == 1].copy()
corr_wr = strict_pass["empirical_win_rate_strict"].corr(
    (strict_pass["target_realized_dir_ext"] == strict_pass["break_direction"]).astype(float)
)
corr_p3 = strict_pass["empirical_win_rate_strict"].corr(strict_pass["target_play3_result"])
print(f"  Correlation(empirical_wr, actual_win): {corr_wr:.4f}")
print(f"  Correlation(empirical_wr, play3_result): {corr_p3:.4f}")

# Check: actual win rate is nearly constant — base rate dominance
print("\n=== Base rate dominance ===")
all_strict_wr = (strict_pass["target_realized_dir_ext"] == strict_pass["break_direction"]).mean()
print(f"  Overall strict-pass win rate: {all_strict_wr:.4f}")
print(f"  If we predict 'win' for all strict-pass rows, accuracy: {all_strict_wr:.4f}")
print(f"  Calibration needs to beat this base rate to be useful")

# Check: what if we use play3_result > 0 as the win definition?
print("\n=== Alternative win definition: play3_result > 0 ===")
strict_pass["win_play3"] = (strict_pass["target_play3_result"] > 0).astype(float)
for bucket in ["high", "medium", "low"]:
    sub = strict_pass[strict_pass["expectation_bucket"] == bucket]
    if len(sub) == 0:
        continue
    actual_p3 = sub["win_play3"].mean()
    emp = sub["empirical_win_rate_strict"].mean()
    print(f"  {bucket}: n={len(sub):5d}  empirical_wr={emp:.4f}  actual_play3_win={actual_p3:.4f}")

# Check: what does range_bucket_full look like in strict-pass rows?
print("\n=== Range bucket distribution (strict-pass) ===")
print(strict_pass["range_bucket_full"].value_counts())
print(f"\n=== Session slot distribution (strict-pass) ===")
print(strict_pass["session_slot"].value_counts())