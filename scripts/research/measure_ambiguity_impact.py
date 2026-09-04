r"""Measure what the intrabar ambiguity policy is worth on real bars.

A 1-minute OHLC bar records four prices, not a path. When the stop and a target both
lie inside [low, high], the engine must assume an order. This script runs the SAME
signals through the SAME engine under both assumptions and reports the gap, so the
size of the assumption is a measured number rather than an argument.

Signal synthesis is deliberately identical to `crates/gate2_parity.py` (deterministic,
every 15th bar, alternating direction, limit 2 ticks inside, stop 6 ticks beyond) so
this is comparable to the engine-parity gate and reproducible without a strategy.

Note the direction of the reported gap: `favourable` is what this engine did
unconditionally before the policy existed, so `gap` is how much every prior Python
result on this shape was flattered.

Run:
  .venv\Scripts\python.exe -m scripts.research.measure_ambiguity_impact
  .venv\Scripts\python.exe -m scripts.research.measure_ambiguity_impact --start 2023-01-01 --end 2024-01-01
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from scripts.execution.nt8_parity_engine import (
    AMBIGUITY_ADVERSE,
    AMBIGUITY_FAVOURABLE,
    NT8ParityEngine,
)

DEFAULT_PARQUET = r"C:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"


def synth_signals(df: pd.DataFrame):
    """Deterministic signals - identical to crates/gate2_parity.py."""
    n = len(df)
    signals = np.zeros(n, dtype=np.int32)
    limit_prices = df["close"].to_numpy(dtype=np.float64).copy()
    stop_losses = df["close"].to_numpy(dtype=np.float64).copy()
    idx = np.arange(0, n, 15)
    dirs = np.where((np.arange(0, n, 15) // 15) % 2 == 0, 1, -1).astype(np.int32)
    signals[idx] = dirs
    for k, i in enumerate(idx):
        if dirs[k] == 1:
            limit_prices[i] = limit_prices[i] - 0.50
            stop_losses[i] = limit_prices[i] - 1.50
        else:
            limit_prices[i] = limit_prices[i] + 0.50
            stop_losses[i] = limit_prices[i] + 1.50
    return signals, limit_prices, stop_losses


def summarise(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    pts = trades["total_points"].to_numpy(dtype=np.float64)
    wins = pts > 0
    gross_win = pts[wins].sum()
    gross_loss = -pts[~wins].sum()
    equity = np.cumsum(pts)
    peak = np.maximum.accumulate(equity)
    return {
        "trades": len(trades),
        "win_rate_pct": 100.0 * wins.mean(),
        "total_points": pts.sum(),
        "avg_points": pts.mean(),
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "max_drawdown_pts": float((peak - equity).max()),
        "worst_trade_pts": float(pts.min()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=DEFAULT_PARQUET)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2024-01-01")
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet).loc[args.start:args.end].copy()
    print(f"bars: {len(df):,} ({df.index[0]} -> {df.index[-1]})\n")

    engine = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)
    signals, limits, stops = synth_signals(df)
    sig = pd.Series(signals, index=df.index)
    lmt = pd.Series(limits, index=df.index)
    sl = pd.Series(stops, index=df.index)

    out = {}
    for policy in (AMBIGUITY_ADVERSE, AMBIGUITY_FAVOURABLE):
        out[policy] = summarise(
            engine.simulate(df, sig, lmt, sl, ambiguity_policy=policy)
        )

    adv, fav = out[AMBIGUITY_ADVERSE], out[AMBIGUITY_FAVOURABLE]
    keys = ["trades", "win_rate_pct", "total_points", "avg_points",
            "profit_factor", "max_drawdown_pts", "worst_trade_pts"]

    print(f"{'metric':<20} | {'adverse':>14} | {'favourable':>14} | {'gap':>14}")
    print("-" * 72)
    for k in keys:
        a, f = adv.get(k), fav.get(k)
        if a is None or f is None:
            continue
        gap = f - a
        print(f"{k:<20} | {a:>14.2f} | {f:>14.2f} | {gap:>+14.2f}")

    print()
    if adv["trades"] and fav["trades"]:
        pf_a, pf_f = adv["profit_factor"], fav["profit_factor"]
        print(f"Profit factor moves {pf_a:.3f} -> {pf_f:.3f} purely by assuming the")
        print("favourable intrabar sequence. Neither is observed; only tick data settles it.")
        if pf_a < 1.0 <= pf_f:
            print("\n  *** The sign of the edge is decided by the assumption, not the data. ***")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
