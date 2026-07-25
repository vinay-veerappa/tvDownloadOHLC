"""Cross-instrument validation of fixed calibration."""
import pandas as pd
import numpy as np

for sym in ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]:
    res = pd.read_parquet(f"data/derived/ib_breakout_filter_{sym}.parquet")
    strict = res[res["strict_filter_pass"] == 1].copy()
    strict["actual_win"] = (strict["target_play3_result"] > 0).astype(float)
    base = strict["actual_win"].mean()
    corr = strict["empirical_win_rate_strict"].corr(strict["actual_win"])

    print(f"\n{'='*60}")
    print(f"{sym}: n_strict={len(strict)}  base_rate={base:.4f}  corr={corr:.4f}")
    print(f"{'='*60}")
    for bucket in ["high", "medium", "low"]:
        sub = strict[strict["expectation_bucket"] == bucket]
        if len(sub) == 0:
            print(f"  {bucket}: n=0")
            continue
        actual = sub["actual_win"].mean()
        emp = sub["empirical_win_rate_strict"].mean()
        print(f"  {bucket}: n={len(sub):5d}  empirical_wr={emp:.4f}  actual_play3_wr={actual:.4f}")

    # Decile check
    strict["decile"] = pd.qcut(
        strict["empirical_win_rate_strict"], 5, labels=False, duplicates="drop"
    )
    print("  Quintiles:")
    for d in sorted(strict["decile"].unique()):
        sub = strict[strict["decile"] == d]
        actual = sub["actual_win"].mean()
        print(f"    Q{d}: n={len(sub):5d}  actual_play3={actual:.4f}")