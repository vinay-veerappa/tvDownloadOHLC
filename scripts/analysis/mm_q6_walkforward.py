"""Q6 — Walk-forward gate on E34L (the family's best arm, ES, 298 trades).

Anchored split consistent with house convention (E33's half-year cuts): train
2025H1 (in-sample intuition only — NO re-fit here, E34 params were fixed a
priori at design time) → evaluate 2025H2 / 2026H1 / 2026H2 out-of-sample.
Walk-forward pass bar: positive PF in every OOS window OR PF>1 with DD bounded
(< 1.5x in-sample DD) in >= 2 of 3 windows.

Usage: .\\.venv\\Scripts\\python.exe scripts\\analysis\\mm_q6_walkforward.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
warnings.filterwarnings("ignore")

import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.mm_e34_battery import run_arm, MMConfig, summarize


def main():
    df1, df5 = load_nt("ES")
    e34l = run_arm("ES", MMConfig("E34L", "long-only", dir_filter="LONG"),
                   {"ES": df1}, {"ES": df5})
    e35c = None
    from scripts.analysis.mm_e35_exit_battery import simulate_exit_variant
    e35c = simulate_exit_variant(e34l, df5, pt_val=5.0, exit_mode="bb_exhaustion")
    e35c["total_pnl_dollars"] = e35c["pnl_pts"] * 5.0

    windows = [
        ("2025H1", "2025-01-01", "2025-06-30"),
        ("2025H2", "2025-07-01", "2025-12-31"),
        ("2026H1", "2026-01-01", "2026-06-30"),
        ("2026H2", "2026-07-01", "2026-12-31"),
    ]
    for label, tdf, col in [("E34L", e34l, "total_pnl_dollars"),
                            ("E35c", e35c, "total_pnl_dollars")]:
        print(f"\n=== Q6 walk-forward: {label} ===")
        t = tdf.copy()
        t["exit_time"] = pd.to_datetime(t["exit_time"])
        for wname, wstart, wend in windows:
            sub = t[(t["exit_time"] >= wstart) & (t["exit_time"] < wend)]
            s = summarize(sub)
            print(f"  {wname}: {s['trades']:>4} tr  WR{s['wr']:>5.1f}%  PF{s['pf']:>5.2f}  "
                  f"Net${s['net']:>6.0f}  DD${s['dd']:>5.0f}")


if __name__ == "__main__":
    main()