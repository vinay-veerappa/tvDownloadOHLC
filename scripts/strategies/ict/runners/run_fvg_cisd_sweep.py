r"""
FVG+CISD Rejection - Sweep Runner
===================================
Iterates all config combinations, runs each through the
VectorizedBacktester, collects metrics, and produces a comparison report.

Usage:
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py --quick
    .\.venv\Scripts\python.exe scripts/strategies/ict/runners/run_fvg_cisd_sweep.py --ticker ES1 --htf 15m --ltf 5m

Output:
    results/RESEARCH/fvg_cisd_sweep/
    sweep_results.csv          - one row per arm, all metrics
    sweep_results_sorted.md    - markdown table sorted by Sharpe
    best_arms.md               - top 10 arms by various metrics
    per_trade_detail.parquet   - all trades across all arms
    config.json                - sweep config used
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

# Add project root to sys.path
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.ict.strategies.ict_fvg_cisd_rejection import ICTFVGCISDRejectionStrategy
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester


# -- Default sweep grid --
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

# Quick grid - subset for fast iteration
QUICK_GRID = {
    "htf_tf": ["15m", "1h"],
    "ltf_tf": ["5m"],
    "require_rejection_fvg": [True, False],
    "cisd_impl": ["sweep_open"],
    "entry_method": ["2nd_fvg", "cisd_close"],
    "sl_method": ["swing_extreme"],
    "tp_rr": [2],
    "fvg_freshness": ["fresh"],
}

# Fixed params
FIXED_PARAMS = {
    "require_mss": True,
    "swing_length": 5,
    "tick_size": 0.25,
    "stop_ticks": 2,
    "use_precomputed": True,
}

OUTPUT_DIR = Path(_root_dir) / "results" / "RESEARCH" / "fvg_cisd_sweep"


def load_ohlc(ticker: str) -> pd.DataFrame:
    """Load 1-minute OHLC data for the ticker."""
    fp = Path(_root_dir) / "data" / f"{ticker}_1m.parquet"
    if not fp.exists():
        raise FileNotFoundError(f"OHLC data not found: {fp}")
    df = pd.read_parquet(fp)
    # Ensure index is datetime and tz-naive (ET)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def generate_combos(grid: dict) -> list:
    """Generate all parameter combinations from grid."""
    keys = list(grid.keys())
    values = list(grid.values())
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos


def run_single_arm(
    strategy: ICTFVGCISDRejectionStrategy,
    data: pd.DataFrame,
    params: dict,
    backtester: VectorizedBacktester,
) -> dict:
    """Run a single arm and return metrics + extended info."""
    arm_id = (
        f"{params['htf_tf']}_{params['ltf_tf']}"
        f"_{'req' if params['require_rejection_fvg'] else 'noreq'}"
        f"_{params['cisd_impl']}_{params['entry_method']}"
        f"_{params['sl_method']}_{params['tp_rr']}R"
        f"_{params['fvg_freshness']}"
    )

    try:
        signals = strategy.hunt(data, params=params)
    except Exception as e:
        return {
            "arm_id": arm_id,
            "config": params,
            "error": str(e),
            "num_trades": 0,
        }

    if signals.empty or len(signals) < 5:
        return {
            "arm_id": arm_id,
            "config": params,
            "num_trades": len(signals),
            "error": "insufficient_trades" if not signals.empty else "no_signals",
        }

    # Run backtest
    risk_params = {
        "ticker": strategy.ticker,
        "risk_reward": params["tp_rr"],
    }

    try:
        metrics = backtester.run(signals, data, risk_params)
    except Exception as e:
        return {
            "arm_id": arm_id,
            "config": params,
            "num_trades": len(signals),
            "error": f"backtest_error: {e}",
        }

    # Extract extended metrics from signals
    trades_detailed = metrics.get("trades_detailed", pd.DataFrame())

    result = {
        "arm_id": arm_id,
        "config": params,
        "num_trades": int(metrics.get("num_trades", 0)),
        "total_return_pct": float(metrics.get("total_return_%", 0.0)),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_%", 0.0)),
        "win_rate_pct": float(metrics.get("win_rate_%", 0.0)),
        "avg_mae_pct": float(metrics.get("avg_mae_%", 0.0)),
        "equity_curve": metrics.get("equity_curve"),
        "trades_detailed": trades_detailed,
        "signals": signals,
    }

    # Extended metrics from signals
    if not signals.empty:
        result["avg_fvg_fill_pct"] = float(
            signals["fvg_fill_pct_at_rejection"].mean()
        ) if "fvg_fill_pct_at_rejection" in signals.columns else 0.0
        result["avg_fvg_age_bars"] = float(
            signals["fvg_age_bars"].mean()
        ) if "fvg_age_bars" in signals.columns else 0.0
        result["avg_rejection_fvg_count"] = float(
            signals["rejection_fvg_count"].mean()
        ) if "rejection_fvg_count" in signals.columns else 0.0
        result["avg_time_to_cisd_bars"] = float(
            signals["time_to_cisd_bars"].mean()
        ) if "time_to_cisd_bars" in signals.columns else 0.0
        result["avg_confluence_count"] = float(
            signals["confluence_count"].mean()
        ) if "confluence_count" in signals.columns else 0.0
        result["pre_fvg_sweep_rate"] = float(
            signals["pre_fvg_sweep"].mean() * 100
        ) if "pre_fvg_sweep" in signals.columns else 0.0
        result["avg_htf_fvg_size_pct"] = float(
            signals["htf_fvg_size_pct"].mean()
        ) if "htf_fvg_size_pct" in signals.columns else 0.0

        # R-multiple distribution
        if not trades_detailed.empty and "pnl_pct" in trades_detailed.columns:
            # Compute risk per trade from signals
            risk = np.abs(
                signals["entry_price"].values - signals["stop_price"].values
            )
            risk_pct = (risk / signals["entry_price"].values) * 100
            pnl_pct = trades_detailed["pnl_pct"].values
            r_multiples = np.where(risk_pct > 0, pnl_pct / risk_pct, 0)
            result["avg_r_multiple"] = float(np.mean(r_multiples))
            result["median_r_multiple"] = float(np.median(r_multiples))
            result["profit_factor"] = float(
                np.sum(r_multiples[r_multiples > 0]) / max(abs(np.sum(r_multiples[r_multiples < 0])), 1e-9)
            )
            result["expectancy_r"] = float(np.mean(r_multiples))
            result["mae_in_r"] = float(
                np.mean(trades_detailed["mae_pct"].values / np.where(risk_pct > 0, risk_pct, 1e-9))
            ) if "mae_pct" in trades_detailed.columns else 0.0
            result["mfe_in_r"] = float(
                np.mean(trades_detailed["mfe_pct"].values / np.where(risk_pct > 0, risk_pct, 1e-9))
            ) if "mfe_pct" in trades_detailed.columns else 0.0

            # Win rate by day of week
            if "day_of_week" in signals.columns:
                dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
                dow_winrates = {}
                for dow in range(5):
                    mask = signals["day_of_week"].values == dow
                    if mask.any():
                        dow_pnl = trades_detailed["pnl_pct"].values[mask]
                        dow_winrates[dow_names[dow]] = float(
                            (dow_pnl > 0).mean() * 100
                        )
                result["win_rate_by_dow"] = dow_winrates

    return result


def run_sweep(ticker: str, grid: dict, quick: bool = False, verbose: bool = True):
    """Run the full sweep and produce reports."""
    print(f"\n{'='*80}")
    print(f"FVG+CISD Rejection Sweep - {ticker}")
    print(f"{'='*80}")

    # Load data once
    print(f"\nLoading {ticker} 1-min OHLC...")
    data = load_ohlc(ticker)
    print(f"  Loaded {len(data):,} bars ({data.index.min()} to {data.index.max()})")

    # Generate combos
    combos = generate_combos(grid)
    total = len(combos)
    print(f"\nTotal arms to test: {total}")
    if total == 0:
        print("No combinations to test.")
        return

    # Initialize
    strategy = ICTFVGCISDRejectionStrategy(ticker=ticker)
    backtester = VectorizedBacktester()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run each arm
    all_results = []
    all_trades = []
    errors = []
    start_time = time.time()

    for i, combo in enumerate(combos):
        params = {**FIXED_PARAMS, **combo}

        if verbose:
            elapsed = time.time() - start_time
            print(f"\r[{i+1}/{total}] {combo['htf_tf']}/{combo['ltf_tf']}"
                  f" req={'Y' if combo['require_rejection_fvg'] else 'N'}"
                  f" {combo['cisd_impl'][:4]}"
                  f" {combo['entry_method'][:6]}"
                  f" {combo['sl_method'][:5]}"
                  f" {combo['tp_rr']}R"
                  f" {combo['fvg_freshness'][:5]}"
                  f"  ({elapsed:.0f}s)", end="", flush=True)

        result = run_single_arm(strategy, data, params, backtester)

        if "error" in result:
            errors.append({"arm_id": result["arm_id"], "error": result["error"], "config": combo})
            continue

        # Collect summary row
        row = {
            "arm_id": result["arm_id"],
            "htf_tf": combo["htf_tf"],
            "ltf_tf": combo["ltf_tf"],
            "require_rejection_fvg": combo["require_rejection_fvg"],
            "cisd_impl": combo["cisd_impl"],
            "entry_method": combo["entry_method"],
            "sl_method": combo["sl_method"],
            "tp_rr": combo["tp_rr"],
            "fvg_freshness": combo["fvg_freshness"],
            "num_trades": result.get("num_trades", 0),
            "total_return_pct": result.get("total_return_pct", 0.0),
            "sharpe_ratio": result.get("sharpe_ratio", 0.0),
            "max_drawdown_pct": result.get("max_drawdown_pct", 0.0),
            "win_rate_pct": result.get("win_rate_pct", 0.0),
            "avg_mae_pct": result.get("avg_mae_pct", 0.0),
            "avg_r_multiple": result.get("avg_r_multiple", 0.0),
            "median_r_multiple": result.get("median_r_multiple", 0.0),
            "profit_factor": result.get("profit_factor", 0.0),
            "expectancy_r": result.get("expectancy_r", 0.0),
            "mae_in_r": result.get("mae_in_r", 0.0),
            "mfe_in_r": result.get("mfe_in_r", 0.0),
            "avg_fvg_fill_pct": result.get("avg_fvg_fill_pct", 0.0),
            "avg_fvg_age_bars": result.get("avg_fvg_age_bars", 0.0),
            "avg_rejection_fvg_count": result.get("avg_rejection_fvg_count", 0.0),
            "avg_time_to_cisd_bars": result.get("avg_time_to_cisd_bars", 0.0),
            "avg_confluence_count": result.get("avg_confluence_count", 0.0),
            "pre_fvg_sweep_rate": result.get("pre_fvg_sweep_rate", 0.0),
            "avg_htf_fvg_size_pct": result.get("avg_htf_fvg_size_pct", 0.0),
        }
        all_results.append(row)

        # Collect trades
        if "trades_detailed" in result and not result["trades_detailed"].empty:
            td = result["trades_detailed"].copy()
            td["arm_id"] = result["arm_id"]
            td["htf_tf"] = combo["htf_tf"]
            td["ltf_tf"] = combo["ltf_tf"]
            all_trades.append(td)

    print(f"\n\nSweep complete in {time.time() - start_time:.1f}s")
    print(f"  Successful arms: {len(all_results)}")
    print(f"  Errors: {len(errors)}")

    if not all_results:
        print("\nNo successful arms. Check errors.")
        for e in errors[:5]:
            print(f"  {e['arm_id']}: {e['error']}")
        return

    # -- Save results --
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(OUTPUT_DIR / "sweep_results.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'sweep_results.csv'}")

    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=False)
        all_trades_df.to_parquet(OUTPUT_DIR / "per_trade_detail.parquet")
        print(f"Saved: {OUTPUT_DIR / 'per_trade_detail.parquet'}")

    # Config
    with open(OUTPUT_DIR / "config.json", "w") as f:
        json.dump({"grid": grid, "fixed": FIXED_PARAMS, "ticker": ticker, "total_arms": total}, f, indent=2, default=str)

    # -- Sorted results markdown --
    sorted_df = results_df.sort_values("sharpe_ratio", ascending=False)
    md_lines = [
        "# FVG+CISD Rejection Sweep - Results",
        f"\n**Ticker**: {ticker}  ",
        f"**Total arms**: {total}  ",
        f"**Successful**: {len(all_results)}  ",
        f"**Errors**: {len(errors)}\n",
        "## Top 20 Arms by Sharpe Ratio\n",
        "| Rank | Arm | HTF | LTF | Req FVG | CISD | Entry | SL | TP | Fresh | Trades | Sharpe | Win% | Avg R | PF | MFE(R) | MAE(R) |",
        "|------|-----|-----|-----|---------|------|-------|-----|-----|-------|--------|--------|------|--------|-----|--------|--------|",
    ]
    for rank, (_, row) in enumerate(sorted_df.head(20).iterrows(), 1):
        md_lines.append(
            f"| {rank} | {row['arm_id']} | {row['htf_tf']} | {row['ltf_tf']} | "
            f"{'Y' if row['require_rejection_fvg'] else 'N'} | {row['cisd_impl']} | "
            f"{row['entry_method']} | {row['sl_method']} | {row['tp_rr']}R | "
            f"{row['fvg_freshness']} | {row['num_trades']} | {row['sharpe_ratio']:.2f} | "
            f"{row['win_rate_pct']:.1f} | {row['avg_r_multiple']:.2f} | "
            f"{row['profit_factor']:.2f} | {row['mfe_in_r']:.2f} | {row['mae_in_r']:.2f} |"
        )

    # -- Best arms by dimension --
    md_lines.append("\n## Best Arms by Dimension\n")
    for dim_name, group_col in [
        ("HTF Timeframe", "htf_tf"),
        ("LTF Timeframe", "ltf_tf"),
        ("Require Rejection FVG", "require_rejection_fvg"),
        ("CISD Implementation", "cisd_impl"),
        ("Entry Method", "entry_method"),
        ("SL Method", "sl_method"),
        ("TP (R)", "tp_rr"),
        ("FVG Freshness", "fvg_freshness"),
    ]:
        md_lines.append(f"\n### By {dim_name}\n")
        md_lines.append(f"| {dim_name} | Arms | Avg Sharpe | Avg Win% | Avg R | Avg PF | Best Sharpe |")
        md_lines.append(f"|-----------|------|-----------|---------|-------|--------|------------|")
        for val, grp in results_df.groupby(group_col):
            md_lines.append(
                f"| {val} | {len(grp)} | {grp['sharpe_ratio'].mean():.2f} | "
                f"{grp['win_rate_pct'].mean():.1f} | {grp['avg_r_multiple'].mean():.2f} | "
                f"{grp['profit_factor'].mean():.2f} | {grp['sharpe_ratio'].max():.2f} |"
            )

    # -- Errors --
    if errors:
        md_lines.append("\n## Errors\n")
        md_lines.append("| Arm | Error |")
        md_lines.append("|-----|-------|")
        for e in errors[:20]:
            md_lines.append(f"| {e['arm_id']} | {e['error'][:80]} |")

    with open(OUTPUT_DIR / "sweep_results_sorted.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Saved: {OUTPUT_DIR / 'sweep_results_sorted.md'}")

    # -- Best arms summary --
    best_lines = [
        "# FVG+CISD Rejection — Best Arms\n",
        f"**Ticker**: {ticker}\n",
        "## Top 10 by Sharpe\n",
        "| Rank | Arm | Trades | Sharpe | Win% | Avg R | PF | Return% | MaxDD% |",
        "|------|-----|--------|--------|------|-------|-----|---------|--------|",
    ]
    for rank, (_, row) in enumerate(sorted_df.head(10).iterrows(), 1):
        best_lines.append(
            f"| {rank} | {row['arm_id']} | {row['num_trades']} | {row['sharpe_ratio']:.2f} | "
            f"{row['win_rate_pct']:.1f} | {row['avg_r_multiple']:.2f} | {row['profit_factor']:.2f} | "
            f"{row['total_return_pct']:.1f} | {row['max_drawdown_pct']:.1f} |"
        )

    best_lines.append("\n## Top 10 by Win Rate\n")
    best_lines.append("| Rank | Arm | Trades | Win% | Sharpe | Avg R | PF |")
    best_lines.append("|------|-----|--------|------|--------|-------|-----|")
    for rank, (_, row) in enumerate(
        results_df.sort_values("win_rate_pct", ascending=False).head(10).iterrows(), 1
    ):
        best_lines.append(
            f"| {rank} | {row['arm_id']} | {row['num_trades']} | {row['win_rate_pct']:.1f} | "
            f"{row['sharpe_ratio']:.2f} | {row['avg_r_multiple']:.2f} | {row['profit_factor']:.2f} |"
        )

    best_lines.append("\n## Top 10 by Expectancy (R)\n")
    best_lines.append("| Rank | Arm | Trades | Exp R | Sharpe | Win% | PF |")
    best_lines.append("|------|-----|--------|-------|--------|------|-----|")
    for rank, (_, row) in enumerate(
        results_df.sort_values("expectancy_r", ascending=False).head(10).iterrows(), 1
    ):
        best_lines.append(
            f"| {rank} | {row['arm_id']} | {row['num_trades']} | {row['expectancy_r']:.2f} | "
            f"{row['sharpe_ratio']:.2f} | {row['win_rate_pct']:.1f} | {row['profit_factor']:.2f} |"
        )

    with open(OUTPUT_DIR / "best_arms.md", "w", encoding="utf-8") as f:
        f.write("\n".join(best_lines))
    print(f"Saved: {OUTPUT_DIR / 'best_arms.md'}")

    # ── Console summary ──────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("TOP 5 ARMS BY SHARPE:")
    print(f"{'='*80}")
    for rank, (_, row) in enumerate(sorted_df.head(5).iterrows(), 1):
        print(
            f"  {rank}. {row['arm_id']:50s}  "
            f"Trades={row['num_trades']:4d}  "
            f"Sharpe={row['sharpe_ratio']:6.2f}  "
            f"Win={row['win_rate_pct']:5.1f}%  "
            f"R={row['avg_r_multiple']:.2f}  "
            f"PF={row['profit_factor']:.2f}"
        )
    print(f"\nResults saved to: {OUTPUT_DIR}")


def main():
    parser = argparse.ArgumentParser(description="FVG+CISD Rejection Sweep Runner")
    parser.add_argument("--ticker", default="ES1", help="Ticker symbol (default: ES1)")
    parser.add_argument("--quick", action="store_true", help="Run quick subset")
    parser.add_argument("--htf", default=None, help="Filter HTF TF (e.g. 15m)")
    parser.add_argument("--ltf", default=None, help="Filter LTF TF (e.g. 5m)")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    args = parser.parse_args()

    grid = QUICK_GRID if args.quick else dict(FULL_GRID)

    # Apply filters
    if args.htf:
        grid["htf_tf"] = [args.htf]
    if args.ltf:
        grid["ltf_tf"] = [args.ltf]

    run_sweep(args.ticker, grid, quick=args.quick, verbose=not args.quiet)


if __name__ == "__main__":
    main()