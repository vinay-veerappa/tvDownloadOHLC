"""
Phase 5.1 — MAE-Calibrated Stop Levels (PRD FR-7).

For each (symbol, session_slot, time_basis, play), compute the P95 and P99 of
MAE among *winning* trades (result == 1). The optimal stop is the level that
captures winners while cutting the largest adverse excursions.

Reads:  data/derived/ib_play_detail_{SYM}.parquet
Writes: data/derived/ib_optimal_stops.parquet
        columns: symbol, session_slot, time_basis, play, target_lvl,
                 p95_mae_winners, p99_mae_winners, optimal_stop_r,
                 wr_at_optimal_stop, expectancy_at_optimal_stop, n_winners, n_trades
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
GROUP_COLS = ["symbol", "session_slot", "time_basis", "play", "target_lvl"]


def compute_optimal_stops(df: pd.DataFrame) -> pd.DataFrame:
    """Per-group MAE percentiles of winners + stop-out stats.

    optimal_stop_r = p95_mae_winners normalized by the group's median |mae|
    (a proxy for stop distance in R when ib_range isn't available here).
    """
    rows = []
    for key, g in df.groupby(GROUP_COLS, sort=False):
        winners = g[g["result"] == 1]
        n_win = len(winners)
        n_total = len(g)
        if n_win < 30:
            continue
        mae_win = winners["mae"].astype(float)
        # MAE is signed (negative = adverse). Use abs for percentile distance.
        mae_abs = mae_win.abs()
        p95 = float(mae_abs.quantile(0.95))
        p99 = float(mae_abs.quantile(0.99))
        # WR if we had used p95 as the stop: trades whose |mae| <= p95 and result==1
        # Approximation: winners below p95 would have hit target; losers above p95 stopped out
        wr_at_p95 = float((g["result"] == 1).sum() / n_total) if n_total else np.nan
        exp_at_p95 = float(g.loc[g["mae"].abs() <= p95, "realized_r"].mean()) if (g["mae"].abs() <= p95).any() else np.nan
        median_mae = float(g["mae"].abs().median()) or 1.0
        rows.append({
            **dict(zip(GROUP_COLS, key)),
            "p95_mae_winners": p95, "p99_mae_winners": p99,
            "optimal_stop_r": round(p95 / median_mae, 4),
            "wr_at_optimal_stop": round(wr_at_p95, 4),
            "expectancy_at_optimal_stop": round(exp_at_p95, 4) if pd.notna(exp_at_p95) else np.nan,
            "n_winners": n_win, "n_trades": n_total,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    frames = []
    for sym in symbols:
        path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        out = compute_optimal_stops(df)
        print(f"[{sym}] {len(out)} stop rows")
        frames.append(out)
    if frames:
        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(DERIVED / "ib_optimal_stops.parquet", index=False)
        print(f"[ALL] wrote {len(final)} rows to {DERIVED/'ib_optimal_stops.parquet'}")


if __name__ == "__main__":
    main()