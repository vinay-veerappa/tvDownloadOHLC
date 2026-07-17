"""
FVG+CISD Rejection — Parallel Sweep Runner (GPU + CPU parallel)
=================================================================
Uses:
  - joblib for arm-level parallelism (24 CPU cores)
  - Numba JIT for the FVG mitigation loop
  - CuPy for GPU-accelerated cummin/cummax/searchsorted

Usage:
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep_parallel.py
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep_parallel.py --workers 24
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

# Numba JIT
from numba import njit, prange

# ── Numba-accelerated FVG mitigation detection ──────────────────────

@njit(cache=True)
def _compute_mitigation_positions_numba(
    fvg_create_pos: np.ndarray,
    fvg_levels: np.ndarray,
    cum_arr: np.ndarray,
    n_exec: int,
    is_bull: bool,
) -> np.ndarray:
    """Numba JIT: compute mitigation bar for each FVG using binary search
    on the cumulative min/max array.

    For bull (is_bull=True): cum_arr = cummin(low), mitigation when cum_arr <= level
    For bear (is_bull=False): cum_arr = cummax(high), mitigation when cum_arr >= level
    """
    n_fvg = len(fvg_create_pos)
    mitigation_pos = np.full(n_fvg, n_exec, dtype=np.int64)

    for fi in range(n_fvg):
        start = fvg_create_pos[fi]
        if start >= n_exec:
            continue

        level = fvg_levels[fi]

        if is_bull:
            # cum_arr is non-increasing. Find first pos where cum_arr[pos] <= level
            # Binary search on non-increasing array
            lo, hi = start, n_exec - 1
            found = False
            while lo <= hi:
                mid = (lo + hi) // 2
                if cum_arr[mid] <= level:
                    # Check if this is the first occurrence
                    if mid == start or cum_arr[mid - 1] > level:
                        mitigation_pos[fi] = mid
                        found = True
                        break
                    hi = mid - 1
                else:
                    lo = mid + 1
            if not found:
                mitigation_pos[fi] = n_exec
        else:
            # cum_arr is non-decreasing. Find first pos where cum_arr[pos] >= level
            lo, hi = start, n_exec - 1
            found = False
            while lo <= hi:
                mid = (lo + hi) // 2
                if cum_arr[mid] >= level:
                    if mid == start or cum_arr[mid - 1] < level:
                        mitigation_pos[fi] = mid
                        found = True
                        break
                    hi = mid - 1
                else:
                    lo = mid + 1
            if not found:
                mitigation_pos[fi] = n_exec

    return mitigation_pos


@njit(cache=True)
def _fill_active_fvgs_numba(
    fvg_create_pos: np.ndarray,
    fvg_mitigation_pos: np.ndarray,
    fvg_tops: np.ndarray,
    fvg_bots: np.ndarray,
    fvg_create_ns: np.ndarray,
    n_exec: int,
) -> tuple:
    """Numba JIT: fill the active FVG arrays by iterating FVGs in order."""
    top_arr = np.full(n_exec, np.nan)
    bot_arr = np.full(n_exec, np.nan)
    create_arr = np.full(n_exec, np.nan)

    n_fvg = len(fvg_create_pos)
    for fi in range(n_fvg):
        start = fvg_create_pos[fi]
        end = min(fvg_mitigation_pos[fi], n_exec)
        if start < n_exec and start < end:
            top_arr[start:end] = fvg_tops[fi]
            bot_arr[start:end] = fvg_bots[fi]
            create_arr[start:end] = float(fvg_create_ns[fi])

    return top_arr, bot_arr, create_arr


def build_active_fvgs_fresh_fast(
    fvg_df: pd.DataFrame,
    exec_index: pd.DatetimeIndex,
    exec_ohlc: pd.DataFrame,
) -> pd.DataFrame:
    """Fast fresh-mode FVG mapping using Numba JIT + GPU cummin/cummax."""
    n = len(exec_index)
    exec_ns = exec_index.asi8
    exec_low = exec_ohlc["low"].values.astype(np.float64)
    exec_high = exec_ohlc["high"].values.astype(np.float64)

    # GPU-accelerated cummin/cummax (CuPy)
    try:
        import cupy as cp
        gpu_low = cp.asarray(exec_low)
        gpu_high = cp.asarray(exec_high)
        # cummin: reverse, cummax, reverse
        cummin_low = cp.asnumpy(cp.minimum.accumulate(gpu_low))
        cummax_high = cp.asnumpy(cp.maximum.accumulate(gpu_high))
    except Exception:
        # Fallback to NumPy
        cummin_low = np.minimum.accumulate(exec_low)
        cummax_high = np.maximum.accumulate(exec_high)

    result = {}
    for fvg_type, label, level_col, cum_arr, is_bull in [
        (1, "bull", "fvg_bottom", cummin_low, True),
        (-1, "bear", "fvg_top", cummax_high, False),
    ]:
        fvg_subset = fvg_df[fvg_df["fvg_type"] == fvg_type].sort_index()
        n_fvg = len(fvg_subset)
        top_arr = np.full(n, np.nan)
        bot_arr = np.full(n, np.nan)
        create_arr = np.full(n, np.nan)

        if n_fvg == 0:
            result[f"{label}_top"] = top_arr
            result[f"{label}_bot"] = bot_arr
            result[f"{label}_create_ns"] = create_arr
            continue

        fvg_create_ns = fvg_subset.index.asi8
        fvg_tops = fvg_subset["fvg_top"].values.astype(np.float64)
        fvg_bots = fvg_subset["fvg_bottom"].values.astype(np.float64)
        fvg_levels = fvg_subset[level_col].values.astype(np.float64)

        # Compute creation positions
        fvg_create_pos = np.searchsorted(exec_ns, fvg_create_ns, side="right")

        # Numba-accelerated mitigation detection
        mitigation_pos = _compute_mitigation_positions_numba(
            fvg_create_pos, fvg_levels, cum_arr, n, is_bull
        )

        # Numba-accelerated fill
        top_arr, bot_arr, create_arr = _fill_active_fvgs_numba(
            fvg_create_pos, mitigation_pos, fvg_tops, fvg_bots, fvg_create_ns, n
        )

        result[f"{label}_top"] = top_arr
        result[f"{label}_bot"] = bot_arr
        result[f"{label}_create_ns"] = create_arr

    return pd.DataFrame({
        "bull_top": result["bull_top"],
        "bull_bot": result["bull_bot"],
        "bull_create_ns": result["bull_create_ns"],
        "bear_top": result["bear_top"],
        "bear_bot": result["bear_bot"],
        "bear_create_ns": result["bear_create_ns"],
    }, index=exec_index)


# ── Data cache (shared across workers) ─────────────────────────────

_DATA_CACHE = {}


def load_ohlc(ticker: str) -> pd.DataFrame:
    """Load 1-min OHLC — cached."""
    if ticker not in _DATA_CACHE:
        fp = Path(_root_dir) / "data" / f"{ticker}_1m.parquet"
        df = pd.read_parquet(fp)
        _DATA_CACHE[ticker] = df
    return _DATA_CACHE[ticker]


# ── Single arm runner ──────────────────────────────────────────────

def run_single_arm(args):
    """Run a single arm — designed for joblib parallel execution."""
    ticker, params = args

    from scripts.strategies.ict.strategies.ict_fvg_cisd_rejection import (
        ICTFVGCISDRejectionStrategy,
        _DERIVED_ICT_DIR,
    )
    from scripts.trading_framework.core.backtest_engine import VectorizedBacktester

    # Patch the fresh-mode FVG builder with our Numba version
    import types
    strategy_cls = ICTFVGCISDRejectionStrategy

    # Monkey-patch the fresh builder with the fast version
    strategy_cls._build_active_fvgs_fresh = staticmethod(build_active_fvgs_fresh_fast)

    arm_id = (
        f"{params['htf_tf']}_{params['ltf_tf']}"
        f"_{'req' if params['require_rejection_fvg'] else 'noreq'}"
        f"_{params['cisd_impl']}_{params['entry_method']}"
        f"_{params['sl_method']}_{params['tp_rr']}R"
        f"_{params['fvg_freshness']}"
    )

    try:
        data = load_ohlc(ticker)
        strategy = strategy_cls(ticker=ticker)
        signals = strategy.hunt(data, params=params)
    except Exception as e:
        return {"arm_id": arm_id, "error": str(e), "num_trades": 0}

    if signals.empty or len(signals) < 5:
        return {"arm_id": arm_id, "num_trades": len(signals), "error": "insufficient"}

    bt = VectorizedBacktester()
    try:
        metrics = bt.run(signals, data, {"ticker": ticker, "risk_reward": params["tp_rr"]})
    except Exception as e:
        return {"arm_id": arm_id, "num_trades": len(signals), "error": f"bt: {e}"}

    td = metrics.get("trades_detailed", pd.DataFrame())
    risk = np.abs(signals["entry_price"].values - signals["stop_price"].values)
    risk_pct = (risk / signals["entry_price"].values) * 100

    if not td.empty and "pnl_pct" in td.columns:
        r_mult = np.where(risk_pct > 0, td["pnl_pct"].values / risk_pct, 0)
        avg_r = float(np.mean(r_mult))
        pf = float(np.sum(r_mult[r_mult > 0]) / max(abs(np.sum(r_mult[r_mult < 0])), 1e-9))
        mae_in_r = float(np.mean(td["mae_pct"].values / np.where(risk_pct > 0, risk_pct, 1e-9))) if "mae_pct" in td.columns else 0
        mfe_in_r = float(np.mean(td["mfe_pct"].values / np.where(risk_pct > 0, risk_pct, 1e-9))) if "mfe_pct" in td.columns else 0
    else:
        avg_r = 0.0
        pf = 0.0
        mae_in_r = 0.0
        mfe_in_r = 0.0

    return {
        "arm_id": arm_id,
        "htf_tf": params["htf_tf"],
        "ltf_tf": params["ltf_tf"],
        "require_rejection_fvg": params["require_rejection_fvg"],
        "cisd_impl": params["cisd_impl"],
        "entry_method": params["entry_method"],
        "sl_method": params["sl_method"],
        "tp_rr": params["tp_rr"],
        "fvg_freshness": params["fvg_freshness"],
        "num_trades": int(metrics.get("num_trades", 0)),
        "total_return_pct": float(metrics.get("total_return_%", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_%", 0.0)),
        "win_rate_pct": float(metrics.get("win_rate_%", 0.0)),
        "avg_mae_pct": float(metrics.get("avg_mae_%", 0.0)),
        "avg_r_multiple": avg_r,
        "median_r_multiple": float(np.median(r_mult)) if not td.empty else 0.0,
        "profit_factor": pf,
        "expectancy_r": avg_r,
        "mae_in_r": mae_in_r,
        "mfe_in_r": mfe_in_r,
    }


# ── Sweep grid ─────────────────────────────────────────────────────

FULL_GRID = {
    "htf_tf": ["15m", "1h", "1d"],
    "ltf_tf": ["5m", "1m"],
    "require_rejection_fvg": [True, False],
    "cisd_impl": ["sweep_open", "delivery_series"],
    "entry_method": ["2nd_fvg", "1st_fvg", "fvg_50pct", "cisd_close"],
    "sl_method": ["swing_extreme", "htf_fvg_boundary"],
    "tp_rr": [1, 2, 3],
    "fvg_freshness": ["fresh", "multi"],
}

FIXED_PARAMS = {
    "require_mss": True,
    "swing_length": 5,
    "tick_size": 0.25,
    "stop_ticks": 2,
    "use_precomputed": True,
}

OUTPUT_DIR = Path(_root_dir) / "results" / "RESEARCH" / "fvg_cisd_sweep"


def main():
    parser = argparse.ArgumentParser(description="Parallel FVG+CISD Sweep")
    parser.add_argument("--ticker", default="ES1")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    # Warm up Numba JIT
    print("Warming up Numba JIT...")
    _warmup = np.zeros(10, dtype=np.float64)
    _compute_mitigation_positions_numba(np.array([0], dtype=np.int64), _warmup, _warmup, 10, True)
    _fill_active_fvgs_numba(np.array([0], dtype=np.int64), np.array([10], dtype=np.int64), _warmup, _warmup, _warmup, 10)
    print("JIT compiled.")

    # Generate combos
    grid = dict(FULL_GRID)
    if args.quick:
        grid = {
            "htf_tf": ["15m", "1h"],
            "ltf_tf": ["5m"],
            "require_rejection_fvg": [True, False],
            "cisd_impl": ["sweep_open"],
            "entry_method": ["2nd_fvg", "cisd_close"],
            "sl_method": ["swing_extreme"],
            "tp_rr": [2],
            "fvg_freshness": ["fresh", "multi"],
        }

    keys = list(grid.keys())
    values = list(grid.values())
    combos = []
    for combo in itertools.product(*values):
        params = {**FIXED_PARAMS, **dict(zip(keys, combo))}
        combos.append((args.ticker, params))

    total = len(combos)
    print(f"\n{'='*80}")
    print(f"Parallel FVG+CISD Sweep - {args.ticker}")
    print(f"{'='*80}")
    print(f"Total arms: {total}")
    print(f"Workers: {args.workers}")
    print(f"Data: loading...")

    # Pre-load data into cache
    load_ohlc(args.ticker)
    data = _DATA_CACHE[args.ticker]
    print(f"  {len(data):,} bars ({data.index.min()} to {data.index.max()})")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run with joblib
    from joblib import Parallel, delayed

    print(f"\nRunning {total} arms with {args.workers} workers...")
    start_time = time.time()

    results = Parallel(n_jobs=args.workers, verbose=10, backend="loky")(
        delayed(run_single_arm)(combo) for combo in combos
    )

    elapsed = time.time() - start_time
    print(f"\nSweep complete in {elapsed:.1f}s")

    # Filter results
    successful = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    print(f"  Successful: {len(successful)}  Errors: {len(errors)}")

    if not successful:
        print("No successful arms!")
        for e in errors[:5]:
            print(f"  {e['arm_id']}: {e['error'][:80]}")
        return

    # Save
    results_df = pd.DataFrame(successful)
    results_df.to_csv(OUTPUT_DIR / "sweep_results_v2.csv", index=False)
    print(f"Saved: {OUTPUT_DIR / 'sweep_results_v2.csv'}")

    # Top by expectancy
    sorted_df = results_df.sort_values("expectancy_r", ascending=False)
    print(f"\n{'='*80}")
    print("TOP 10 BY EXPECTANCY (R):")
    for rank, (_, row) in enumerate(sorted_df.head(10).iterrows(), 1):
        print(f"  {rank}. {row['arm_id'][:55]:55s} Trades={row['num_trades']:6d} "
              f"R={row['expectancy_r']:.2f} Sharpe={row['sharpe_ratio']:.2f} "
              f"Win={row['win_rate_pct']:.1f}% PF={row['profit_factor']:.2f}")

    # Dimension comparisons
    print(f"\n{'='*80}")
    print("DIMENSION COMPARISONS:")
    for dim in ["htf_tf", "ltf_tf", "require_rejection_fvg", "cisd_impl",
                "entry_method", "sl_method", "tp_rr", "fvg_freshness"]:
        print(f"\n  By {dim}:")
        for val, grp in results_df.groupby(dim):
            print(f"    {str(val):20s} Arms={len(grp):4d} AvgR={grp['expectancy_r'].mean():.3f} "
                  f"Sharpe={grp['sharpe_ratio'].mean():.2f} Win={grp['win_rate_pct'].mean():.1f}% "
                  f"PF={grp['profit_factor'].mean():.2f}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  {e['arm_id']}: {e['error'][:80]}")


if __name__ == "__main__":
    main()