r"""Measure what the broken CV objective was actually optimising.

`ResearchLifecycleRunner._optimize_params` generated signals on a PurgedKFold
train fold and scored them against the test fold:

    signals = strategy.generate_signals(fold_train, params)
    metrics = backtester.run(signals, fold_test, {'leverage': 1.0})

Two different frames. `Index.get_indexer(..., method='bfill')` snaps an
out-of-range timestamp to the next available bar with no distance limit and
returns -1 only when no later bar exists at all, so every train-fold signal
mapped to index 0 of the test frame and passed the engine's `!= -1` validity
check. The objective was "score N signals as if all of them entered on the first
bar of the test window", and Optuna maximised it.

This script runs BOTH constructions on the same data and the same parameters so
the difference is a measured number rather than an argument. It reports, per
fold, how many signals were collapsed onto a single bar -- which is the
mechanism -- alongside the Sharpe each construction produced.

Run:
  set PYTHONIOENCODING=utf-8
  .venv\Scripts\python.exe -m scripts.research.measure_cv_objective_defect
  .venv\Scripts\python.exe -m scripts.research.measure_cv_objective_defect --strategy ema_pullback
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.ml.walk_forward import sequential_evaluation_folds
from scripts.trading_framework.strategies.registry import get_strategy

EXIT_BUFFER = 1440
EMBARGO = 1440


def mid_grid(grid: dict) -> dict:
    """A single fixed parameter point, so the two constructions differ only in framing."""
    out = {}
    for k, v in grid.items():
        if isinstance(v, tuple) and v and v[0] == "float":
            out[k] = (float(v[1]) + float(v[2])) / 2.0
        elif isinstance(v, tuple) and v and v[0] == "int":
            out[k] = int((int(v[1]) + int(v[2])) // 2)
        elif isinstance(v, tuple) and v and v[0] == "categorical":
            out[k] = v[1][0]
        elif isinstance(v, (list, tuple)) and v:
            out[k] = v[0]
        else:
            out[k] = v
    return out


def old_construction(strategy, engine, data, params, n_splits=3):
    """Verbatim reproduction of the shape that shipped."""
    rows = []
    kf = KFold(n_splits=n_splits, shuffle=False)
    idx = np.arange(len(data))
    for fold, (train_idx, test_idx) in enumerate(kf.split(idx)):
        fold_train = data.iloc[train_idx]
        fold_test = data.iloc[test_idx]

        signals = strategy.generate_signals(fold_train, params)
        if signals is None or len(signals) == 0:
            rows.append({"fold": fold, "sharpe": -1.0, "signals": 0,
                         "collapsed_to_bar0": 0, "trades": 0})
            continue

        # what get_indexer did, before the bound existed
        raw = fold_test.index.get_indexer(
            pd.to_datetime(signals["signal_time"]), method="bfill")
        collapsed = int((raw == 0).sum())

        # `max_snap_seconds=inf` restores the original unbounded behaviour so
        # the OLD number is reproducible on the PATCHED engine.
        m = engine.run(signals, fold_test, {
            "leverage": 1.0, "ticker": "NQ1", "max_snap_seconds": float("inf")})
        rows.append({
            "fold": fold,
            "sharpe": float(m.get("sharpe_ratio", -1.0)),
            "signals": int(len(signals)),
            "collapsed_to_bar0": collapsed,
            "trades": int(m.get("num_trades", 0)),
        })
    return rows


def new_construction(strategy, engine, data, params, n_splits=3):
    rows = []
    folds = sequential_evaluation_folds(
        len(data), n_splits=n_splits, exit_buffer=EXIT_BUFFER, embargo=EMBARGO)
    for f in folds:
        gen_df = data.iloc[: f["gen_end"]]
        signals = strategy.generate_signals(gen_df, params)
        if signals is None or len(signals) == 0:
            rows.append({"fold": f["fold"], "sharpe": -1.0, "signals": 0,
                         "in_window": 0, "trades": 0})
            continue

        w_start = data.index[f["test_start"]]
        w_end = data.index[f["test_end"] - 1]
        st = pd.to_datetime(signals["signal_time"])
        in_win = signals[(st >= w_start) & (st <= w_end)]
        if in_win.empty:
            rows.append({"fold": f["fold"], "sharpe": -1.0,
                         "signals": int(len(signals)), "in_window": 0, "trades": 0})
            continue

        score_df = data.iloc[f["score_start"]: f["score_end"]]
        m = engine.run(in_win, score_df, {
            "leverage": 1.0, "ticker": "NQ1", "strict_alignment": True})
        rows.append({
            "fold": f["fold"],
            "sharpe": float(m.get("sharpe_ratio", -1.0)),
            "signals": int(len(signals)),
            "in_window": int(len(in_win)),
            "trades": int(m.get("num_trades", 0)),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="mean_reversion")
    ap.add_argument("--ticker", default="NQ1")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default="2024-01-01")
    ap.add_argument("--splits", type=int, default=3)
    args = ap.parse_args()

    df = DataLoader(load_config()).load_enriched(args.ticker)
    data = df.loc[args.start:args.end].copy()
    print(f"{args.ticker} {args.strategy}: {len(data):,} bars "
          f"({data.index[0]} -> {data.index[-1]})\n")

    strategy = get_strategy(args.strategy, args.ticker)
    params = mid_grid(strategy.get_param_grid())
    print(f"fixed params: {params}\n")
    engine = VectorizedBacktester()

    old = old_construction(strategy, engine, data, params, args.splits)
    new = new_construction(strategy, engine, data, params, args.splits)

    print("OLD construction -- signals from TRAIN fold, scored on TEST fold")
    print(f"{'fold':>5} | {'signals':>8} | {'-> bar 0':>9} | {'trades':>7} | {'sharpe':>9}")
    print("-" * 52)
    for r in old:
        print(f"{r['fold']:>5} | {r['signals']:>8} | {r['collapsed_to_bar0']:>9} "
              f"| {r['trades']:>7} | {r['sharpe']:>9.4f}")
    old_obj = float(np.mean([r["sharpe"] for r in old]))
    print(f"{'':>5} | {'':>8} | {'':>9} | {'objective':>7} | {old_obj:>9.4f}\n")

    print("NEW construction -- signals generated causally, scored on their own window")
    print(f"{'fold':>5} | {'signals':>8} | {'in window':>9} | {'trades':>7} | {'sharpe':>9}")
    print("-" * 52)
    for r in new:
        print(f"{r['fold']:>5} | {r['signals']:>8} | {r['in_window']:>9} "
              f"| {r['trades']:>7} | {r['sharpe']:>9.4f}")
    new_obj = float(np.mean([r["sharpe"] for r in new]))
    print(f"{'':>5} | {'':>8} | {'':>9} | {'objective':>7} | {new_obj:>9.4f}\n")

    tot_collapsed = sum(r["collapsed_to_bar0"] for r in old)
    tot_signals = sum(r["signals"] for r in old)
    pct = 100.0 * tot_collapsed / tot_signals if tot_signals else 0.0
    print(f"Signals the old objective placed on a single bar: "
          f"{tot_collapsed}/{tot_signals} ({pct:.1f}%).")
    print(f"Objective moves {old_obj:+.4f} -> {new_obj:+.4f} at IDENTICAL parameters.")
    print("\nThe number that matters is the collapse count, not the Sharpe gap. A gap")
    print("can be small by luck on one parameter point while the objective is still a")
    print("function of the wrong thing -- which is what Optuna was ranking candidates by.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
