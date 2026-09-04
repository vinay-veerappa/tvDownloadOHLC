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


def synth_signals(df: pd.DataFrame, stop_pts: float = 1.50):
    """Deterministic signals - identical to crates/gate2_parity.py at the default stop.

    `stop_pts` is the only knob, because it is half of what drives the whole effect:
    ambiguity needs the stop AND a target inside ONE bar, so it scales with
    (stop + target) / bar range.
    """
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
            stop_losses[i] = limit_prices[i] - stop_pts
        else:
            limit_prices[i] = limit_prices[i] + 0.50
            stop_losses[i] = limit_prices[i] + stop_pts
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


def run_pair(engine, df, stop_pts: float, queen_bps: float, runner_bps: float):
    """Run both policies on identical inputs and return (adverse_df, favourable_df)."""
    signals, limits, stops = synth_signals(df, stop_pts=stop_pts)
    sig = pd.Series(signals, index=df.index)
    lmt = pd.Series(limits, index=df.index)
    sl = pd.Series(stops, index=df.index)
    out = {}
    for policy in (AMBIGUITY_ADVERSE, AMBIGUITY_FAVOURABLE):
        out[policy] = engine.simulate(
            df, sig, lmt, sl,
            queen_bps=queen_bps, runner_bps=runner_bps,
            ambiguity_policy=policy,
        )
    return out[AMBIGUITY_ADVERSE], out[AMBIGUITY_FAVOURABLE]


def count_flips(adv: pd.DataFrame, fav: pd.DataFrame) -> tuple:
    """How many trades did the ASSUMPTION decide?

    Both policies see identical signals and take the same entries, so the frames align
    row-for-row; a differing total_points on the same row means that trade's outcome was
    chosen by the assumption rather than by the data. This is the mechanism itself, and
    it is far more diagnostic than an aggregate PF delta - a large flip count can still
    average out to a small PF gap, and that averaging is exactly what hid the effect the
    first time this was measured.
    """
    if adv.empty or fav.empty or len(adv) != len(fav):
        return 0, len(adv), 0.0
    a = adv["total_points"].to_numpy(dtype=np.float64)
    f = fav["total_points"].to_numpy(dtype=np.float64)
    flips = int((~np.isclose(a, f)).sum())
    return flips, len(adv), (100.0 * flips / len(adv) if len(adv) else 0.0)


def sweep(engine, df) -> int:
    """Map where the assumption actually decides outcomes."""
    stops = [0.75, 1.50, 3.00, 6.00, 12.00, 25.00]
    queens = [5.0, 10.0, 20.0]

    print("Ambiguity is only possible when the stop AND a target fall inside ONE bar.")
    print("`flips` = trades whose outcome the ASSUMPTION decided, not the data.\n")
    print(f"{'stop pts':>9} | {'queen bps':>9} | {'trades':>7} | {'flips':>6} | {'flip %':>7} "
          f"| {'PF adv':>7} | {'PF fav':>7} | {'PF gap':>7}")
    print("-" * 88)

    worst = (0.0, None)
    for stop_pts in stops:
        for qb in queens:
            adv, fav = run_pair(engine, df, stop_pts, qb, qb * 3.0)
            flips, n, pct = count_flips(adv, fav)
            sa, sf = summarise(adv), summarise(fav)
            pfa = sa.get("profit_factor", float("nan"))
            pff = sf.get("profit_factor", float("nan"))
            gap = pff - pfa if n else float("nan")
            print(f"{stop_pts:>9.2f} | {qb:>9.0f} | {n:>7} | {flips:>6} | {pct:>6.2f}% "
                  f"| {pfa:>7.3f} | {pff:>7.3f} | {gap:>+7.3f}")
            if pct > worst[0]:
                worst = (pct, (stop_pts, qb, flips, n, pfa, pff))

    if worst[1]:
        sp, qb, flips, n, pfa, pff = worst[1]
        print(f"\nWorst case in this grid: stop {sp} pts / queen {qb} bps -> "
              f"{flips}/{n} trades ({worst[0]:.2f}%) decided by the assumption, "
              f"PF {pfa:.3f} -> {pff:.3f}.")
    print("\nRead this as a map, not a verdict: find YOUR strategy's stop and target on it.")
    print("A geometry whose flip % is high is one where 1m OHLC cannot settle the outcome,")
    print("and only tick resolution can. A low flip % means the assumption barely matters.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=DEFAULT_PARQUET)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2024-01-01")
    ap.add_argument("--sweep", action="store_true",
                    help="map flip rate across a stop/target grid instead of one geometry")
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet).loc[args.start:args.end].copy()
    print(f"bars: {len(df):,} ({df.index[0]} -> {df.index[-1]})\n")

    engine = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)

    if args.sweep:
        return sweep(engine, df)

    adv_df, fav_df = run_pair(engine, df, stop_pts=1.50, queen_bps=10.0, runner_bps=30.0)
    flips, n, pct = count_flips(adv_df, fav_df)
    adv, fav = summarise(adv_df), summarise(fav_df)
    print(f"trades whose outcome the ASSUMPTION decided: {flips}/{n} ({pct:.2f}%)\n")
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
