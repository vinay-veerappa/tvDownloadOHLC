"""Optimized IB backtest runner with cached precomputation.

Speed optimization: hunt() takes ~9s per call because it recomputes IB ranges,
FVGs, and bias on the 3.5M-row DataFrame every time. But candidates sharing the
same (session_preset, ib_duration_min) have identical precomputed columns.

This runner splits hunt() into:
  1. _precompute(session, duration) — heavy, cached per (session, duration) combo
  2. _extract_signals(precomputed, params) — lightweight, called per candidate

With 6 unique (session, duration) combos in the moderate grid, this reduces
432 × 9s = 65min to 6 × 9s + 432 × 0.1s = 1min (60x speedup).

Usage:
    python -m scripts.knowledge_bridge.ib_backtest_fast --ticker NQ1 --moderate
    python -m scripts.knowledge_bridge.ib_backtest_fast --ticker NQ1 --smoke
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.knowledge_bridge.strategy_candidates import (
    CandidateStatus,
    StrategyCandidate,
)
from scripts.knowledge_bridge.ib_backtest_runner import (
    build_candidates,
    _candidate_id,
    _candidate_name,
)
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.ml.prop_firm_simulator import (
    PropFirmSimulator,
    FIRM_PROFILES,
)
from scripts.utils.vectorized_indicators import VectorizedIndicators
from scripts.trading_framework.config.config_loader import load_config
from scripts.libs_py.data.loader import DataLoader


class CachedIBHunter:
    """Cached IB Pullback signal generator.

    Precomputes IB ranges, FVGs, and bias columns per (session, duration) combo,
    then extracts signals for varying params in O(n_bars) per call.
    """

    def __init__(self, data: pd.DataFrame, ticker: str = "NQ1"):
        self.data = data
        self.ticker = ticker
        self._cache: Dict[Tuple[str, int], pd.DataFrame] = {}

    def _precompute(self, session: str, ib_dur: int) -> pd.DataFrame:
        """Precompute session/duration-dependent columns (heavy, cached)."""
        cache_key = (session, ib_dur)
        if cache_key in self._cache:
            return self._cache[cache_key]

        from datetime import time as dtime, datetime, timedelta

        df = self.data

        # 1. Resolve session windows
        if session == "RTH":
            ib_start = dtime(9, 30)
            fvg_start = dtime(10, 0)
            fvg_end = dtime(11, 0)
            entry_end = dtime(15, 30)
        elif session == "Globex":
            ib_start = dtime(18, 0)
            fvg_start = dtime(19, 0)
            fvg_end = dtime(20, 0)
            entry_end = dtime(6, 0)
        elif session == "Tokyo":
            ib_start = dtime(19, 0)
            fvg_start = dtime(20, 0)
            fvg_end = dtime(21, 0)
            entry_end = dtime(2, 0)
        else:
            raise ValueError(f"Unknown session: {session}")

        ib_end_dt = datetime.combine(datetime.min, ib_start) + timedelta(minutes=ib_dur)
        ib_end = ib_end_dt.time()

        # 2. Trading day normalization
        if ib_start > ib_end or session in ["Globex", "Tokyo"]:
            df = df.assign(
                trading_date=np.where(
                    df.index.time >= ib_start,
                    df.index.normalize() + pd.Timedelta(days=1),
                    df.index.normalize(),
                )
            )
        else:
            df = df.assign(trading_date=df.index.normalize())

        # 3. IB range
        ib_mask = (df.index.time >= ib_start) & (df.index.time <= ib_end)
        ib_data = df[ib_mask]
        if ib_data.empty:
            empty = pd.DataFrame(columns=["trading_date", "ib_high", "ib_low", "ib_range"])
            self._cache[cache_key] = empty
            return empty

        daily_ib_high = ib_data.groupby("trading_date")["high"].max()
        daily_ib_low = ib_data.groupby("trading_date")["low"].min()
        daily_ib_close = ib_data.groupby("trading_date")["close"].last()

        df = df.copy()  # need copy to add columns
        df["ib_high"] = df["trading_date"].map(daily_ib_high)
        df["ib_low"] = df["trading_date"].map(daily_ib_low)
        df["ib_close"] = df["trading_date"].map(daily_ib_close)
        df["ib_range"] = df["ib_high"] - df["ib_low"]

        # 4. IB bias
        df["ib_pos"] = (df["ib_close"] - df["ib_low"]) / df["ib_range"]
        df["ib_bias"] = np.where(df["ib_pos"] >= 0.50, "long", "short")

        # 5. FVG + inversion bias
        fvg_df = VectorizedIndicators.find_fvgs(df)
        df = pd.concat([df, fvg_df], axis=1)

        fvg_window_mask = (df.index.time >= fvg_start) & (df.index.time <= fvg_end)
        fvg_window_data = df[fvg_window_mask]

        daily_fvg_type = fvg_window_data.groupby("trading_date")["fvg_type"].first()
        df["daily_fvg_type"] = df["trading_date"].map(daily_fvg_type).fillna(0)
        df["fvg_bias"] = np.where(
            df["daily_fvg_type"] == 1, "long",
            np.where(df["daily_fvg_type"] == -1, "short", "neutral"),
        )

        daily_fvg_top = (
            fvg_window_data[fvg_window_data["fvg_type"] != 0]
            .groupby("trading_date")["fvg_top"].first()
        )
        daily_fvg_bottom = (
            fvg_window_data[fvg_window_data["fvg_type"] != 0]
            .groupby("trading_date")["fvg_bottom"].first()
        )
        df["daily_fvg_top"] = df["trading_date"].map(daily_fvg_top)
        df["daily_fvg_bottom"] = df["trading_date"].map(daily_fvg_bottom)

        df["is_bull_inverted"] = (df["close"] < df["daily_fvg_bottom"]) & (df["daily_fvg_type"] == 1)
        df["is_bear_inverted"] = (df["close"] > df["daily_fvg_top"]) & (df["daily_fvg_type"] == -1)
        df["has_inverted_bull"] = df["is_bull_inverted"].groupby(df["trading_date"]).cummax()
        df["has_inverted_bear"] = df["is_bear_inverted"].groupby(df["trading_date"]).cummax()
        df["fvg_inversion_bias"] = df["fvg_bias"]
        df.loc[df["has_inverted_bull"] == 1, "fvg_inversion_bias"] = "short"
        df.loc[df["has_inverted_bear"] == 1, "fvg_inversion_bias"] = "long"

        # 6. Breakout status (session/duration dependent)
        df["has_broken_high"] = (df["high"] > df["ib_high"]).groupby(df["trading_date"]).cummax()
        df["has_broken_low"] = (df["low"] < df["ib_low"]).groupby(df["trading_date"]).cummax()

        # Store entry window mask
        from datetime import time as dtime2
        if ib_end > entry_end:
            df["_entry_window"] = (df.index.time > ib_end) | (df.index.time <= entry_end)
        else:
            df["_entry_window"] = (df.index.time > ib_end) & (df.index.time <= entry_end)

        self._cache[cache_key] = df
        return df

    def generate_signals(self, params: Dict[str, Any]) -> pd.DataFrame:
        """Extract signals for given params using cached precomputed data."""
        output_cols = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

        session = params.get("session_preset", "RTH")
        ib_dur = int(params.get("ib_duration_min", 45))
        entry_var = params.get("entry_variant", "post_break")
        pullback_lvl = params.get("pullback_level", "fib_382")
        sl_type = params.get("stop_loss_type", "ib_opposite")
        bias_src = params.get("bias_source", "ib_close")
        tp_mult = float(params.get("tp_r_mult", 1.0))

        df = self._precompute(session, ib_dur)
        if df.empty or "ib_high" not in df.columns:
            return pd.DataFrame(columns=output_cols)

        # 7. Bias synthesis (param-dependent but cheap)
        if bias_src == "ib_close":
            bias = df["ib_bias"]
        elif bias_src == "fvg":
            bias = df["fvg_bias"]
        elif bias_src == "fvg_inversion":
            bias = df["fvg_inversion_bias"]
        elif bias_src == "confluence":
            bias = np.where(df["ib_bias"] == df["fvg_bias"], df["ib_bias"], "neutral")
        else:
            bias = df["ib_bias"]

        # 8. Pullback entry levels (param-dependent, vectorized)
        ib_range = df["ib_range"]
        ib_high = df["ib_high"]
        ib_low = df["ib_low"]

        if pullback_lvl == "fib_382":
            entry_long = ib_high - 0.382 * ib_range
            entry_short = ib_low + 0.382 * ib_range
        elif pullback_lvl == "fib_50":
            entry_long = ib_high - 0.50 * ib_range
            entry_short = ib_low + 0.50 * ib_range
        elif pullback_lvl == "fib_618":
            entry_long = ib_high - 0.618 * ib_range
            entry_short = ib_low + 0.618 * ib_range
        elif pullback_lvl == "q_25":
            entry_long = ib_high - 0.25 * ib_range
            entry_short = ib_low + 0.25 * ib_range
        elif pullback_lvl == "q_75":
            entry_long = ib_high - 0.75 * ib_range
            entry_short = ib_low + 0.75 * ib_range
        elif pullback_lvl == "ib_edge":
            entry_long = ib_high
            entry_short = ib_low
        else:
            raise ValueError(f"Unknown pullback: {pullback_lvl}")

        # 9. Entry triggers (param-dependent)
        entry_window = df["_entry_window"]
        if entry_var == "pre_break":
            long_trigger = (~df["has_broken_high"]) & (df["low"].values <= entry_long.values)
            short_trigger = (~df["has_broken_low"]) & (df["high"].values >= entry_short.values)
        else:  # post_break
            long_trigger = df["has_broken_high"] & (df["low"].values <= entry_long.values)
            short_trigger = df["has_broken_low"] & (df["high"].values >= entry_short.values)

        # Direction assignment
        direction = np.full(len(df), np.nan, dtype=object)
        long_mask = long_trigger & entry_window & (bias == "long")
        short_mask = short_trigger & entry_window & (bias == "short")
        direction[long_mask.values] = "long"
        direction[short_mask.values] = "short"

        sig_mask = pd.notna(direction)
        if not sig_mask.any():
            return pd.DataFrame(columns=output_cols)

        signals = pd.DataFrame({
            "trading_date": df["trading_date"][sig_mask],
            "direction": direction[sig_mask],
            "entry_long": entry_long[sig_mask],
            "entry_short": entry_short[sig_mask],
            "ib_high": ib_high[sig_mask],
            "ib_low": ib_low[sig_mask],
            "ib_range": ib_range[sig_mask],
            "signal_time": df.index[sig_mask],
        }, index=df.index[sig_mask])

        # First signal per trading day
        signals = signals.groupby("trading_date").head(1)

        # 10. Entries, stops, TP
        is_long = signals["direction"] == "long"
        signals["entry_price"] = np.where(is_long, signals["entry_long"], signals["entry_short"])

        if sl_type == "ib_opposite":
            signals["stop_price"] = np.where(is_long, signals["ib_low"], signals["ib_high"])
        elif sl_type == "ib_edge":
            signals["stop_price"] = np.where(
                is_long,
                signals["entry_price"] - 0.05 * signals["ib_range"],
                signals["entry_price"] + 0.05 * signals["ib_range"],
            )
        elif sl_type == "fixed_pct":
            signals["stop_price"] = np.where(
                is_long,
                signals["entry_price"] * 0.9975,
                signals["entry_price"] * 1.0025,
            )
        else:
            signals["stop_price"] = np.where(is_long, signals["ib_low"], signals["ib_high"])

        risk = (signals["entry_price"] - signals["stop_price"]).abs()
        signals["target1_price"] = np.where(
            is_long,
            signals["entry_price"] + risk * tp_mult,
            signals["entry_price"] - risk * tp_mult,
        )

        return signals[output_cols].reset_index(drop=True)


def run_fast_backtest(
    ticker: str,
    candidates: List[StrategyCandidate],
    profiles: Optional[List[str]] = None,
    n_simulations: int = 200,
    pass_threshold_pct: float = 65.0,
    output_dir: str = "results/ib_backtest",
) -> str:
    """Run optimized backtest with cached precomputation."""
    print(f"\n{'='*60}")
    print(f"Fast BacktestLoop for {ticker}")
    print(f"  Candidates: {len(candidates)}")
    print(f"  Profiles: {profiles or '(from config)'}")
    print(f"  MC simulations: {n_simulations}")
    print(f"{'='*60}")

    # Load data once
    t0 = time.time()
    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    data = loader.load_enriched(ticker)
    print(f"  Data loaded: {data.shape} in {time.time()-t0:.1f}s")

    # Get point value and account size
    point_value = (
        config.execution.point_value.get(ticker, 2.0)
        if hasattr(config, "execution")
        else 2.0
    )
    account_size = (
        config.account_risk.starting_equity
        if hasattr(config, "account_risk")
        else 50_000.0
    )

    # Create cached hunter
    hunter = CachedIBHunter(data, ticker=ticker)
    engine = VectorizedBacktester()
    pf_sim = PropFirmSimulator(account_size=account_size, point_value=point_value)

    # Resolve profiles
    if profiles is None:
        profiles = ["apex_50k", "topstep_50k", "ftmo_50k"]

    # Track unique (session, duration) combos for cache stats
    combos_seen = set()

    results = []
    for i, cand in enumerate(candidates):
        params = cand.metadata.get("params", {})
        combo = (params.get("session_preset"), params.get("ib_duration_min"))
        combos_seen.add(combo)

        t1 = time.time()
        # 1. Generate signals (cached)
        signals = hunter.generate_signals(params)
        n_sigs = len(signals)

        # 2. Backtest
        if n_sigs == 0:
            results.append({
                "candidate_id": cand.candidate_id,
                "strategy_key": "ib_pullback",
                "ticker": ticker,
                "n_signals": 0,
                "n_trades": 0,
                "total_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "avg_mae_pct": 0.0,
                "passed": False,
                "grade": "F",
                "profiles": [],
                "error": "0 signals",
            })
            continue

        bt = engine.run(signals, data, {"leverage": 1.0, "ticker": ticker})
        trades_detailed = bt.get("trades_detailed")

        if trades_detailed is None or len(trades_detailed) == 0:
            results.append({
                "candidate_id": cand.candidate_id,
                "strategy_key": "ib_pullback",
                "ticker": ticker,
                "n_signals": n_sigs,
                "n_trades": 0,
                "total_return_pct": 0.0,
                "passed": False,
                "grade": "F",
                "profiles": [],
                "error": "0 trades",
            })
            continue

        # 3. Prop firm simulation
        profile_results = []
        primary_passed = False
        primary_grade = "F"

        for pk in profiles:
            prof = FIRM_PROFILES.get(pk)
            if prof is None:
                continue
            det = pf_sim.run_deterministic(trades_detailed, prof)
            mc = pf_sim.run_monte_carlo(trades_detailed, prof, n_simulations=n_simulations)

            pr = {
                "profile_name": prof.name,
                "passed": det.passed,
                "blown": det.blown,
                "final_equity_delta": det.final_equity_delta,
                "max_drawdown_used": det.max_drawdown_used,
                "win_rate": det.win_rate,
                "profit_factor": det.profit_factor,
                "total_trades": det.total_trades,
                "trading_days": det.trading_days,
                "mc_pass_rate_pct": mc.pass_rate_pct,
                "mc_blow_rate_pct": mc.blow_rate_pct,
                "mc_grade": mc.grade,
                "avg_days_to_pass": mc.avg_days_to_pass,
                "p50_final_equity": mc.p50_final_equity,
            }
            profile_results.append(pr)

            if pk == profiles[0]:
                primary_passed = mc.pass_rate_pct >= pass_threshold_pct
                primary_grade = mc.grade

        elapsed = time.time() - t1
        ret = float(bt.get("total_return_%", 0))
        wr = float(bt.get("win_rate_%", 0))
        n_trades = int(bt.get("num_trades", 0))

        result = {
            "candidate_id": cand.candidate_id,
            "strategy_key": "ib_pullback",
            "ticker": ticker,
            "n_signals": n_sigs,
            "n_trades": n_trades,
            "total_return_pct": ret,
            "sharpe_ratio": float(bt.get("sharpe_ratio", 0)),
            "max_drawdown_pct": float(bt.get("max_drawdown_%", 0)),
            "win_rate_pct": wr,
            "avg_mae_pct": float(bt.get("avg_mae_%", 0)),
            "passed": primary_passed,
            "grade": primary_grade,
            "profiles": profile_results,
            "error": None,
        }
        results.append(result)

        # Print progress
        status = "[PASS]" if primary_passed else "[FAIL]"
        print(f"  [{i+1}/{len(candidates)}] {cand.name} ({elapsed:.1f}s)")
        print(f"    {status} Grade: {primary_grade} | Trades: {n_trades} | "
              f"Ret: {ret:.2f}% | WR: {wr:.1f}%")
        for pr in profile_results:
            print(f"    {pr['profile_name']}: MC={pr['mc_pass_rate_pct']:.1f}% "
                  f"(grade {pr['mc_grade']}) det={'PASS' if pr['passed'] else 'FAIL'} "
                  f"delta=${pr['final_equity_delta']:,.0f}")

    # Export
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / f"ib_backtest_{ticker}.json"
    export_data = {
        "version": "0.2.0",
        "exported_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "result_count": len(results),
        "unique_combos": len(combos_seen),
        "results": results,
    }
    out_path.write_text(json.dumps(export_data, indent=2, default=str), encoding="utf-8")
    print(f"\n[OK] Results exported to {out_path}")
    print(f"  Unique (session, duration) combos: {len(combos_seen)}")
    print(f"  Total time: {time.time()-t0:.1f}s")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Fast IB backtest with cached precomputation")
    parser.add_argument("--ticker", type=str, default="NQ1")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated")
    parser.add_argument("--all-tickers", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--moderate", action="store_true")
    parser.add_argument("--tp-mults", type=str, default=None)
    parser.add_argument("--profiles", type=str, default=None)
    parser.add_argument("--n-simulations", type=int, default=200)
    parser.add_argument("--pass-threshold", type=float, default=65.0)
    parser.add_argument("--output-dir", type=str, default="results/ib_backtest")
    args = parser.parse_args()

    if args.all_tickers:
        tickers = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]
    elif args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        tickers = [args.ticker]

    tp_mults = [float(x) for x in args.tp_mults.split(",")] if args.tp_mults else None
    profiles = [p.strip() for p in args.profiles.split(",")] if args.profiles else None

    for ticker in tickers:
        cands = build_candidates(ticker, smoke=args.smoke, moderate=args.moderate, tp_mults=tp_mults)
        print(f"\nBuilt {len(cands)} candidates for {ticker}")
        run_fast_backtest(
            ticker=ticker,
            candidates=cands,
            profiles=profiles,
            n_simulations=args.n_simulations,
            pass_threshold_pct=args.pass_threshold,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()