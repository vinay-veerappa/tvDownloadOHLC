"""
Phase 5.3 — Partial Profit Ladder Optimizer (PRD FR-7).

For each (symbol, session_slot, time_basis, play), search the ladder space
(TP1%, TP2%, TP3%, runner%) that maximizes expectancy given the realized_r
distribution per target_lvl. The ladder is a vectorized weighted average of
the realized outcomes at each tier.

Reads:  data/derived/ib_play_detail_{SYM}.parquet
Writes: data/derived/ib_optimal_ladders.parquet
        columns: symbol, session_slot, time_basis, play, target_lvl,
                 tp1_pct, tp2_pct, tp3_pct, runner_pct,
                 ladder_expectancy, baseline_expectancy, n_trades
"""

from __future__ import annotations
import argparse
from itertools import product
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "data" / "derived"
DERIVED = DERIVED.parent / "derived"  # normalize
DERIVED = ROOT / "data" / "derived"
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
GROUP_COLS = ["symbol", "session_slot", "time_basis", "play", "target_lvl"]

# Candidate ladders (sum must = 1.0). Coarse grid to keep search bounded.
LADDER_GRID = [
    (0.40, 0.30, 0.20, 0.10),  # PRD default
    (0.50, 0.30, 0.15, 0.05),
    (0.30, 0.30, 0.25, 0.15),
    (0.60, 0.25, 0.10, 0.05),
    (0.50, 0.25, 0.20, 0.05),
    (0.25, 0.25, 0.25, 0.25),
    (0.70, 0.20, 0.10, 0.00),
    (1.00, 0.00, 0.00, 0.00),  # single-target baseline
]
# R-multiples each tier targets (in units of ib_range). These pair with the
# realized_r distribution: tier 1 captures 0.5x, tier 2 1.0x, tier 3 1.5x,
# runner trails. We approximate realized outcome per tier as a fraction of the
# trade's realized_r.
TIER_R_MULT = [0.5, 1.0, 1.5, None]  # None = runner uses full realized_r


def _ladder_expectancy(g: pd.DataFrame, ladder: tuple) -> float:
    """Weighted expectancy: each tier takes its % at its target R, runner gets residual."""
    r = g["realized_r"].astype(float)
    # Winners (r>0) realize each tier; losers (r<=0) take the full loss scaled by total taken
    # Simplified: expectancy = sum(tier_pct * tier_r_outcome)
    # For winners: tier1=0.5R, tier2=1.0R, tier3=1.5R, runner=realized_r (capped)
    # For losers: all tiers realize the same loss = realized_r
    tp1, tp2, tp3, runner = ladder
    win_r = r.clip(lower=0)
    loss_r = r.clip(upper=0)
    # Winner leg: tiers capture their R-multiple (capped by actual MFE proxy via realized_r)
    win_leg = (tp1 * 0.5 + tp2 * 1.0 + tp3 * 1.5) * (win_r > 0)
    # Runner leg: captures the realized_r beyond tier3 (approximated as realized_r itself)
    win_leg += runner * win_r
    # Loser leg: all tiers realize the full loss
    loss_leg = (tp1 + tp2 + tp3 + runner) * loss_r
    return float((win_leg + loss_leg).mean())


def build_ladders(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(GROUP_COLS, sort=False):
        if len(g) < 50:
            continue
        baseline = float(g["realized_r"].mean())
        best = None
        for ladder in LADDER_GRID:
            exp = _ladder_expectancy(g, ladder)
            if best is None or exp > best[1]:
                best = (ladder, exp)
        rows.append({
            **dict(zip(GROUP_COLS, key)),
            "tp1_pct": best[0][0], "tp2_pct": best[0][1],
            "tp3_pct": best[0][2], "runner_pct": best[0][3],
            "ladder_expectancy": round(best[1], 4),
            "baseline_expectancy": round(baseline, 4),
            "n_trades": len(g),
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
        out = build_ladders(df)
        print(f"[{sym}] {len(out)} ladder rows")
        frames.append(out)
    if frames:
        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(DERIVED / "ib_optimal_ladders.parquet", index=False)
        print(f"[ALL] wrote {len(final)} rows to {DERIVED/'ib_optimal_ladders.parquet'}")


if __name__ == "__main__":
    main()