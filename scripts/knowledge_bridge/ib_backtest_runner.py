#!/usr/bin/env python
"""Build IB StrategyCandidate grid and run through BacktestLoop.

Expands IBPullbackStrategy.get_param_grid() into StrategyCandidate objects,
runs them through BacktestLoop (VectorizedBacktester → PropFirmSimulator),
and exports results.

Usage
-----
Smoke test (single ticker, small grid):
    python -m scripts.knowledge_bridge.ib_backtest_runner --ticker NQ1 --smoke

Full batch (all 6 tickers, full grid):
    python -m scripts.knowledge_bridge.ib_backtest_runner --all-tickers

Custom:
    python -m scripts.knowledge_bridge.ib_backtest_runner \
        --tickers NQ1,ES1 \
        --tp-mults 0.5,1.0,2.0 \
        --profiles apex_50k,topstep_50k,ftmo_50k
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root on sys.path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.knowledge_bridge.strategy_candidates import (
    CandidateStatus,
    DetectionStep,
    StrategyCandidate,
)
from scripts.knowledge_bridge.backtest_loop import (
    BacktestLoop,
    export_backtest_results,
)


# ── Param grid definition ────────────────────────────────────────────────────

# Full grid from IBPullbackStrategy.get_param_grid()
SESSIONS = ["RTH", "Globex", "Tokyo"]
IB_DURATIONS = [30, 45, 60]
ENTRY_VARIANTS = ["pre_break", "post_break"]
PULLBACK_LEVELS = ["fib_382", "fib_50", "fib_618", "q_25", "q_75", "ib_edge"]
STOP_LOSS_TYPES = ["ib_opposite", "ib_edge", "fixed_pct"]
BIAS_SOURCES = ["ib_close", "fvg", "fvg_inversion", "confluence"]

# Curated TP multipliers (representative subset of 0.5–3.0 range)
TP_MULTS_FULL = [0.5, 1.0, 1.5, 2.0, 3.0]
TP_MULTS_SMOKE = [1.0]

# Moderate grid — curated subset based on STRATEGY_STATISTICS findings
# Best sessions: RTH (primary) + Tokyo (high WR for NQ1)
# Top durations: 45, 60 min
# Both entry variants (pre/post break)
# Top 3 pullback levels from filter analysis
# All 3 stop types (for comparison)
# 2 bias sources (ib_close baseline + confluence filtered)
# 3 TP multipliers
MODERATE_SESSIONS = ["RTH", "Tokyo"]
MODERATE_DURATIONS = [45, 60]
MODERATE_PULLBACKS = ["fib_382", "fib_50", "ib_edge"]
MODERATE_BIAS = ["ib_close", "confluence"]
MODERATE_TPS = [0.5, 1.0, 2.0]

# Smoke test subset (reduced grid for fast validation)
SMOKE_SESSIONS = ["RTH"]
SMOKE_DURATIONS = [45]
SMOKE_PULLBACKS = ["fib_382", "ib_edge"]
SMOKE_STOPS = ["ib_opposite"]
SMOKE_BIAS = ["ib_close", "confluence"]


def _candidate_id(params: Dict[str, Any], ticker: str) -> str:
    """Stable hash ID for a candidate."""
    raw = json.dumps({"p": params, "t": ticker}, sort_keys=True)
    h = hashlib.md5(raw.encode()).hexdigest()[:10]
    return f"ib_cand_{h}"


def _candidate_name(params: Dict[str, Any]) -> str:
    """Human-readable name."""
    return (
        f"IB-{params['session_preset']}-{params['ib_duration_min']}min-"
        f"{params['entry_variant']}-{params['pullback_level']}-"
        f"{params['stop_loss_type']}-{params['bias_source']}-"
        f"tp{params['tp_r_mult']}"
    )


def build_candidates(
    ticker: str,
    smoke: bool = False,
    moderate: bool = False,
    tp_mults: Optional[List[float]] = None,
) -> List[StrategyCandidate]:
    """Build IB StrategyCandidate grid from param combinations.

    Parameters
    ----------
    ticker : str
        Instrument (e.g., "NQ1").
    smoke : bool
        If True, use reduced grid for fast validation.
    moderate : bool
        If True, use curated moderate grid (576 candidates).
    tp_mults : list[float], optional
        Override TP multipliers. Ignored if smoke=True.

    Returns
    -------
    list[StrategyCandidate]
    """
    if smoke:
        sessions = SMOKE_SESSIONS
        durations = SMOKE_DURATIONS
        entry_variants = ENTRY_VARIANTS  # keep both
        pullbacks = SMOKE_PULLBACKS
        stops = SMOKE_STOPS
        biases = SMOKE_BIAS
        tps = TP_MULTS_SMOKE
    elif moderate:
        sessions = MODERATE_SESSIONS
        durations = MODERATE_DURATIONS
        entry_variants = ENTRY_VARIANTS
        pullbacks = MODERATE_PULLBACKS
        stops = STOP_LOSS_TYPES
        biases = MODERATE_BIAS
        tps = MODERATE_TPS
    else:
        sessions = SESSIONS
        durations = IB_DURATIONS
        entry_variants = ENTRY_VARIANTS
        pullbacks = PULLBACK_LEVELS
        stops = STOP_LOSS_TYPES
        biases = BIAS_SOURCES
        tps = tp_mults or TP_MULTS_FULL

    candidates: List[StrategyCandidate] = []

    for combo in itertools.product(
        sessions, durations, entry_variants, pullbacks, stops, biases, tps
    ):
        params = {
            "session_preset": combo[0],
            "ib_duration_min": combo[1],
            "entry_variant": combo[2],
            "pullback_level": combo[3],
            "stop_loss_type": combo[4],
            "bias_source": combo[5],
            "tp_r_mult": combo[6],
        }

        cand = StrategyCandidate(
            candidate_id=_candidate_id(params, ticker),
            name=_candidate_name(params),
            source_unit_ids=[],
            direction="both",
            strategy_key="ib_pullback",
            entry_rule=f"Pullback to {params['pullback_level']} after {params['entry_variant']} IB break",
            invalidation_rule=f"Stop at {params['stop_loss_type']}",
            target_rule=f"TP at {params['tp_r_mult']}R",
            max_exit_time="16:00 ET",
            status=CandidateStatus.REVIEWED,
            created_at="",
            epistemic_status="unvalidated",
            metadata={"params": params, "ticker": ticker},
        )
        candidates.append(cand)

    return candidates


def run_backtest(
    ticker: str,
    candidates: List[StrategyCandidate],
    profiles: Optional[List[str]] = None,
    n_simulations: int = 5000,
    pass_threshold_pct: float = 65.0,
    output_dir: str = "results/ib_backtest",
) -> str:
    """Run BacktestLoop for a list of candidates and export results.

    Parameters
    ----------
    ticker : str
    candidates : list[StrategyCandidate]
    profiles : list[str], optional
        Prop firm profile keys. Default: from sessions.yaml.
    n_simulations : int
    pass_threshold_pct : float
    output_dir : str

    Returns
    -------
    str
        Path to the exported JSON results file.
    """
    print(f"\n{'='*60}")
    print(f"Running BacktestLoop for {ticker}")
    print(f"  Candidates: {len(candidates)}")
    print(f"  Profiles: {profiles or '(from config)'}")
    print(f"  MC simulations: {n_simulations}")
    print(f"  Pass threshold: {pass_threshold_pct}%")
    print(f"{'='*60}")

    loop = BacktestLoop(
        ticker=ticker,
        profiles=profiles,
        n_simulations=n_simulations,
        pass_threshold_pct=pass_threshold_pct,
        auto_status_update=False,  # don't mutate candidates
    )

    # Pass params from candidate metadata to run_candidate
    results = []
    for i, cand in enumerate(candidates):
        params = cand.metadata.get("params", {})
        print(f"\n[{i+1}/{len(candidates)}] {cand.name}...")
        result = loop.run_candidate(cand, params=params)
        results.append(result)
        _print_result_summary(result)

    # Export
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / f"ib_backtest_{ticker}.json"
    export_backtest_results(results, out_path)
    print(f"\n[OK] Results exported to {out_path}")
    return str(out_path)


def _print_result_summary(result) -> None:
    """Print a one-line summary of a backtest result."""
    if result.error:
        print(f"  [ERROR] {result.error}")
        return

    grade = result.grade
    passed = "[PASS]" if result.passed else "[FAIL]"
    print(f"  {passed} | Grade: {grade} | "
          f"Trades: {result.n_trades} | "
          f"Return: {result.total_return_pct:.2f}% | "
          f"WR: {result.win_rate_pct:.1f}% | "
          f"MaxDD: {result.max_drawdown_pct:.2f}%")

    for pr in result.profiles:
        print(f"    {pr.profile_name}: "
              f"MC pass={pr.mc_pass_rate_pct:.1f}% "
              f"(grade {pr.mc_grade}), "
              f"det={'PASS' if pr.passed else 'FAIL'} "
              f"delta=${pr.final_equity_delta:,.0f}")


def main():
    parser = argparse.ArgumentParser(
        description="Run IB strategy backtest through BacktestLoop"
    )
    parser.add_argument(
        "--ticker", type=str, default=None,
        help="Single ticker (e.g., NQ1)"
    )
    parser.add_argument(
        "--tickers", type=str, default=None,
        help="Comma-separated tickers (e.g., NQ1,ES1)"
    )
    parser.add_argument(
        "--all-tickers", action="store_true",
        help="Run all 6 IB instruments"
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Use reduced grid for fast validation"
    )
    parser.add_argument(
        "--moderate", action="store_true",
        help="Use curated moderate grid (576 candidates) based on stats findings"
    )
    parser.add_argument(
        "--tp-mults", type=str, default=None,
        help="Comma-separated TP multipliers (e.g., 0.5,1.0,2.0)"
    )
    parser.add_argument(
        "--profiles", type=str, default=None,
        help="Comma-separated prop firm profiles"
    )
    parser.add_argument(
        "--n-simulations", type=int, default=1000,
        help="MC simulations (default 1000 for speed; use 5000 for final)"
    )
    parser.add_argument(
        "--pass-threshold", type=float, default=65.0,
        help="MC pass rate threshold (default 65.0)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="results/ib_backtest",
        help="Output directory for results JSON"
    )
    args = parser.parse_args()

    # Resolve tickers
    if args.all_tickers:
        tickers = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
    elif args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    elif args.ticker:
        tickers = [args.ticker]
    else:
        print("Error: specify --ticker, --tickers, or --all-tickers")
        sys.exit(1)

    # Resolve TP multipliers
    tp_mults = None
    if args.tp_mults:
        tp_mults = [float(x) for x in args.tp_mults.split(",")]

    # Resolve profiles
    profiles = None
    if args.profiles:
        profiles = [p.strip() for p in args.profiles.split(",")]

    # Run
    all_outputs = []
    for ticker in tickers:
        candidates = build_candidates(
            ticker, smoke=args.smoke, moderate=args.moderate, tp_mults=tp_mults
        )
        print(f"\nBuilt {len(candidates)} candidates for {ticker}")
        out = run_backtest(
            ticker=ticker,
            candidates=candidates,
            profiles=profiles,
            n_simulations=args.n_simulations,
            pass_threshold_pct=args.pass_threshold,
            output_dir=args.output_dir,
        )
        all_outputs.append(out)

    print(f"\n{'='*60}")
    print(f"[OK] All complete. Results:")
    for o in all_outputs:
        print(f"  {o}")


if __name__ == "__main__":
    main()