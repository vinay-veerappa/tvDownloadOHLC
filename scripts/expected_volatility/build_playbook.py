"""Trade-level statistics for the Expected Volatility percentile ladder.

Turns the measured baselines (`measure_baselines.py`, DATA_PLAN §10) into
day-trading evidence: for every rung of the percentile ladder, what happens
*after* price touches it, in both directions.

Method
------
The ladder is fit by inverting the empirical excursion CDF on a **train fold**;
every statistic is reported on train *and* on a chronological **holdout**
(DATA_PLAN §4.5). Nothing is fit on the holdout.

For each session and rung:

  * find the FIRST touch of the level inside the RTH window
  * open a position at the level — ``fade`` (against the touch) or ``breakout``
    (with it)
  * walk the 1m path bar by bar to a bracket or to the session close

**Brackets are expressed in EV units, not fixed basis points.** The levels are
volatility-scaled, so a fixed-bps bracket is a different trade on a VIX-12 day
than on a VIX-30 day. An earlier version of this script used the repo's default
10/15/30 bps bracket and measured `P(stop) = 40-68%` — the stop was simply
tighter than the noise at the level, with MAE p75 running 50-110 bps. Fixed-bps
results remain available via ``--bracket bps`` for comparison against the Pack
Trading standard, but the EV bracket is the specified default.

MFE/MAE are reported in **basis points** across p10/p25/p50/p75/p90/p95 as the
repo statistics standard requires
(`.agents/rules/universal_basis_points_and_statistics.md`).

Caveats that belong in any read of the output
---------------------------------------------
* Entry is assumed **at the level**, on the touching bar. Real fills are worse,
  and for ``breakout`` they are worse in the direction that matters. Subtract at
  least a tick.
* A bar that spans both target and stop resolves **against** the position.
* Sessions are not independent (volatility clusters), so binomial standard
  errors are optimistic — DATA_PLAN §10.9 lists block bootstrap as open work.
* With a symmetric stop and target, ``fade`` and ``breakout`` are exact
  complements: one being positive *is* the other being negative, not a second
  independent finding.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.build_playbook
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.build_playbook \\
        --ticker NQ1 --stop-ev 0.5 --target-ev 0.5
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .features import ODTE_START, OUT_DIR, TARGET_P, percentile_ladder
from .measure_baselines import build_frame

PCTILES = (10, 25, 50, 75, 90, 95)
HOLDOUT_START = "2025-10-21"  # DATA_PLAN §4.5, last 20% of the common window

# Pack Trading bracket in bps, retained for the --bracket bps comparison.
BPS_T1, BPS_STOP = 10.0, 15.0


@dataclass
class RungStats:
    fold: str
    direction: str
    side: str
    target_p: float
    c: float
    n_sessions: int
    n_trades: int
    p_touch: float
    win_rate: float
    p_target_first: float
    p_stop_first: float
    p_open_at_close: float
    expectancy_ev: float  # per trade, in units of the 1-sigma expected move
    median_touch_min: float
    mfe_bps: dict = field(default_factory=dict)
    mae_bps: dict = field(default_factory=dict)


def _paths(bars: pd.DataFrame, sess: pd.DataFrame) -> dict:
    rth = bars.between_time("09:30", "15:59")
    wanted = set(sess.index.date)
    return {
        day: (
            b["high"].to_numpy(dtype=float),
            b["low"].to_numpy(dtype=float),
            b["close"].to_numpy(dtype=float),
        )
        for day, b in rth.groupby(rth.index.date)
        if day in wanted
    }


def _walk(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    start: int,
    level: float,
    is_short: bool,
    stop_pts: float,
    target_pts: float,
) -> tuple[str, float, float, float]:
    """Resolve one trade. Returns (outcome, pnl_pts, mfe_pts, mae_pts).

    A trade still open at the session close is marked at the closing print, not
    at its MFE — the rule does not take a perfect exit.
    """
    h, l, c = highs[start:], lows[start:], closes[start:]
    if h.size == 0:
        return "open", 0.0, 0.0, 0.0
    if is_short:
        fav, adv = level - l, h - level
    else:
        fav, adv = h - level, level - l
    mfe = float(np.maximum(fav, 0.0).max())
    mae = float(np.maximum(adv, 0.0).max())

    for f, a in zip(fav, adv):
        if a >= stop_pts:  # a bar spanning both resolves against us
            return "stop", -stop_pts, mfe, mae
        if f >= target_pts:
            return "target", target_pts, mfe, mae
    last = float(c[-1])
    pnl = (level - last) if is_short else (last - level)
    return "open", pnl, mfe, mae


def rung_stats(
    sess: pd.DataFrame,
    paths: dict,
    c: float,
    side: str,
    direction: str,
    fold: str,
    target_p: float,
    stop_ev: float,
    target_ev: float,
    bracket: str,
) -> RungStats:
    # side = which level is touched; direction = what we do about it.
    is_short = (side == "up") if direction == "fade" else (side == "dn")
    outcomes: list[str] = []
    pnl_ev: list[float] = []
    mfe_bps: list[float] = []
    mae_bps: list[float] = []
    touch_min: list[float] = []

    for ts, row in sess.iterrows():
        day = ts.date()
        if day not in paths:
            continue
        highs, lows, closes = paths[day]
        anchor, exp_move = float(row["S"]), float(row["EV"])
        if exp_move <= 0:
            continue
        level = anchor + exp_move * c if side == "up" else anchor - exp_move * c
        if level <= 0:
            continue
        hits = (
            np.flatnonzero(highs >= level)
            if side == "up"
            else np.flatnonzero(lows <= level)
        )
        if hits.size == 0:
            continue
        i = int(hits[0])
        if bracket == "ev":
            stop_pts, target_pts = exp_move * stop_ev, exp_move * target_ev
        else:
            stop_pts = level * BPS_STOP / 10_000
            target_pts = level * BPS_T1 / 10_000
        outcome, pnl, mfe, mae = _walk(
            highs, lows, closes, i, level, is_short, stop_pts, target_pts
        )
        outcomes.append(outcome)
        pnl_ev.append(pnl / exp_move)
        mfe_bps.append(mfe / level * 10_000)
        mae_bps.append(mae / level * 10_000)
        touch_min.append(float(i))

    n = len(outcomes)
    pct = lambda v: {f"p{p}": round(float(np.percentile(v, p)), 1) for p in PCTILES}
    if n == 0:
        nan = float("nan")
        empty = {f"p{p}": nan for p in PCTILES}
        return RungStats(
            fold, direction, side, target_p, round(c, 4), len(sess), 0, 0.0,
            nan, nan, nan, nan, nan, nan, empty, empty,
        )
    arr = np.array(outcomes)
    pnl = np.array(pnl_ev)
    return RungStats(
        fold=fold,
        direction=direction,
        side=side,
        target_p=target_p,
        c=round(c, 4),
        n_sessions=len(sess),
        n_trades=n,
        p_touch=n / len(sess),
        win_rate=float((pnl > 0).mean()),
        p_target_first=float((arr == "target").mean()),
        p_stop_first=float((arr == "stop").mean()),
        p_open_at_close=float((arr == "open").mean()),
        expectancy_ev=round(float(pnl.mean()), 4),
        median_touch_min=float(np.median(touch_min)),
        mfe_bps=pct(mfe_bps),
        mae_bps=pct(mae_bps),
    )


def touch_clock(
    sess: pd.DataFrame, paths: dict, c: float, direction: str,
    stop_ev: float, target_ev: float,
) -> dict:
    """First-touch clock for the UP level, in 30-minute buckets (09:30 = 570)."""
    rows = []
    is_short = direction == "fade"
    for ts, row in sess.iterrows():
        day = ts.date()
        if day not in paths:
            continue
        highs, lows, closes = paths[day]
        anchor, exp_move = float(row["S"]), float(row["EV"])
        if exp_move <= 0:
            continue
        level = anchor + exp_move * c
        hits = np.flatnonzero(highs >= level)
        if hits.size == 0:
            continue
        i = int(hits[0])
        _, pnl, mfe, mae = _walk(
            highs, lows, closes, i, level, is_short,
            exp_move * stop_ev, exp_move * target_ev,
        )
        minute = 570 + i
        rows.append(
            {
                "bucket": f"{minute // 60:02d}:{(minute % 60) // 30 * 30:02d}",
                "pnl_ev": pnl / exp_move,
                "mfe": mfe / level * 10_000,
                "mae": mae / level * 10_000,
            }
        )
    if not rows:
        return {}
    g = pd.DataFrame(rows).groupby("bucket")
    sizes = g.size()
    win = g["pnl_ev"].apply(lambda s: float((s > 0).mean()))
    exp_ = g["pnl_ev"].mean()
    mfe_ = g["mfe"].median()
    mae_ = g["mae"].median()
    return {
        k: {
            "n": int(sizes[k]),
            "win_rate": round(float(win[k]), 4),
            "expectancy_ev": round(float(exp_[k]), 4),
            "median_mfe_bps": round(float(mfe_[k]), 1),
            "median_mae_bps": round(float(mae_[k]), 1),
        }
        for k in sizes.index
    }


def build(
    ticker: str,
    stop_ev: float,
    target_ev: float,
    bracket: str,
    anchor: str = "prev_close",
    vol_input: str = "vix_prev_close",
) -> dict:
    frame = build_frame(ticker, "2006-01-01")
    if anchor == "prev_close" and vol_input == "vix_prev_close":
        odte = frame.sessions[frame.sessions.index >= ODTE_START]
    else:
        # Imported lazily: compare_variants reads HOLDOUT_START from this module,
        # so a top-level import here would be circular.
        from .compare_variants import build_variants

        variants, _, _ = build_variants(ticker)
        odte = variants[(anchor, vol_input)].sessions
    train = odte[odte.index < HOLDOUT_START]
    test = odte[odte.index >= HOLDOUT_START]
    if train.empty or test.empty:
        raise ValueError(f"{ticker}: empty train or holdout fold")

    ladder = percentile_ladder(train)  # FIT ON TRAIN ONLY
    paths = _paths(frame.bars, odte)

    rungs: list[dict] = []
    for fold_name, fold in (("train", train), ("holdout", test)):
        for direction in ("fade", "breakout"):
            for i, p in enumerate(TARGET_P):
                for side, col in (("up", "c_up"), ("dn", "c_dn")):
                    c = float(ladder[col][i])
                    if c <= 0.05:
                        continue
                    rungs.append(
                        asdict(
                            rung_stats(
                                fold, paths, c, side, direction, fold_name, p,
                                stop_ev, target_ev, bracket,
                            )
                        )
                    )
    mid = float(ladder["c_up"][list(TARGET_P).index(0.35)])
    return {
        "ticker": frame.ticker,
        "vol": frame.vol_name,
        "regime_start": ODTE_START,
        "holdout_start": HOLDOUT_START,
        "n_train": len(train),
        "n_holdout": len(test),
        "anchor": anchor,
        "vol_input": vol_input,
        "bracket": bracket,
        "stop_ev": stop_ev,
        "target_ev": target_ev,
        "ladder": ladder.to_dict("records"),
        "rungs": rungs,
        "clock_c": round(mid, 4),
        "clock_breakout": touch_clock(train, paths, mid, "breakout", stop_ev, target_ev),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--stop-ev", type=float, default=0.35)
    ap.add_argument("--target-ev", type=float, default=0.35)
    ap.add_argument("--bracket", choices=("ev", "bps"), default="ev")
    ap.add_argument(
        "--anchor",
        choices=("prev_close", "rth_open"),
        default="prev_close",
        help="level origin; rth_open is the day-trader frame and the negative "
        "control for the inner-rung edge (RESEARCH_REPORT 3.7)",
    )
    ap.add_argument(
        "--vol-input",
        choices=("vix_prev_close", "vix_open", "har_rv", "blend"),
        default="vix_prev_close",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    payload = build(
        args.ticker, args.stop_ev, args.target_ev, args.bracket,
        anchor=args.anchor, vol_input=args.vol_input,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.anchor == "prev_close" else f"_{args.anchor}"
    dest = (
        Path(args.out) if args.out
        else OUT_DIR / f"playbook_{args.ticker}{suffix}.json"
    )
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {dest}")
    print(
        f"{payload['ticker']} x {payload['vol']}: train {payload['n_train']} / "
        f"holdout {payload['n_holdout']} sessions, anchor={args.anchor} "
        f"vol={args.vol_input} bracket={args.bracket} "
        f"stop={args.stop_ev} target={args.target_ev} EV"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
