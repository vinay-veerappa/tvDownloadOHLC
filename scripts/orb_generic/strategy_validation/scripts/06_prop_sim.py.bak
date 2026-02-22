#!/usr/bin/env python3
# strategy_validation/scripts/06_prop_sim.py
"""
Study 6: Prop Firm Viability Simulation
========================================
Takes strategy parameters derived from Studies 1-5 and simulates
prop firm account performance with realistic constraints.

This script is a FRAMEWORK — you plug in the strategy parameters
after reviewing study results. The actual entry/exit logic is
defined in the StrategySignal dataclass and generate_signals() function.

Usage:
    python 06_prop_sim.py --symbol NQ --strategy or_fade
    python 06_prop_sim.py --symbol ES --strategy or_fade --monte-carlo 1000

Outputs:
    {symbol}_{strategy}_equity_curve.csv
    {symbol}_{strategy}_trade_log.csv
    {symbol}_{strategy}_sim_summary.json
    {symbol}_{strategy}_monte_carlo.json
"""

import argparse
import sys
import os
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config, InstrumentConfig
from scripts.utils import load_derived, save_results, save_results_json, log, timer


# ---------------------------------------------------------------------------
# Trade and strategy signal definitions
# ---------------------------------------------------------------------------

@dataclass
class StrategySignal:
    """A trading signal with defined entry, stop, and target."""
    trade_date: str
    entry_time: str
    direction: str         # "long" or "short"
    entry_price: float
    stop_price: float
    target_price: float
    signal_name: str = ""  # which sub-strategy generated this


@dataclass
class TradeResult:
    """Result of executing a signal."""
    trade_date: str
    entry_time: str
    exit_time: str
    direction: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    pnl_pts: float
    pnl_dollars: float
    mae_pts: float         # max adverse excursion
    mfe_pts: float         # max favorable excursion
    exit_reason: str       # "target", "stop", "eod" (end of day)
    signal_name: str


# ---------------------------------------------------------------------------
# Strategy signal generators — CUSTOMIZE THESE after reviewing study results
# ---------------------------------------------------------------------------

def generate_signals_or_fade(rth: pd.DataFrame, or_data: pd.DataFrame,
                              daily_levels: pd.DataFrame,
                              or_duration: int = 30,
                              params: dict = None) -> List[StrategySignal]:
    """Opening Range Fade (Judas Swing) strategy.

    Logic: After the OR is established, wait for a breakout of one side.
    If that breakout shows signs of failure (price returns inside OR),
    enter in the opposite direction targeting the other side of the OR.

    params dict allows tuning without code changes:
        - or_duration: which OR to use (default 30)
        - min_or_width: minimum OR width to trade (filter noise)
        - max_or_width: maximum OR width (too wide = too much risk)
        - entry_offset: points beyond OR level to confirm failure
        - stop_buffer: points beyond the false breakout extreme
    """
    if params is None:
        params = {
            "min_or_width": 5.0,
            "max_or_width": 50.0,
            "entry_offset": 2.0,
            "stop_buffer": 3.0,
        }

    signals = []
    or_h_col = f"or_{or_duration}_high"
    or_l_col = f"or_{or_duration}_low"

    if or_h_col not in or_data.columns:
        log(f"WARNING: {or_h_col} not found in OR data")
        return signals

    or_end_min = 9 * 60 + 30 + or_duration

    for td in or_data.index:
        h = or_data.loc[td, or_h_col]
        l = or_data.loc[td, or_l_col]
        width = h - l

        if pd.isna(h) or pd.isna(l):
            continue
        if width < params["min_or_width"] or width > params["max_or_width"]:
            continue

        # Get post-OR bars
        td_str = str(td)
        day_bars = rth[rth["trade_date"].astype(str) == td_str]
        rth_min = day_bars.index.hour * 60 + day_bars.index.minute
        post_or = day_bars[rth_min >= or_end_min]

        if len(post_or) < 10:
            continue

        # Look for breakout then failure
        highs = post_or["high"].values
        lows = post_or["low"].values
        closes = post_or["close"].values
        times = post_or.index

        # Check for upside breakout then failure (short signal)
        h_break = np.where(highs > h)[0]
        if len(h_break) > 0:
            break_idx = h_break[0]
            # Look for close back below OR high (failure)
            after_break = closes[break_idx:]
            fail_idx = np.where(after_break < h - params["entry_offset"])[0]
            if len(fail_idx) > 0:
                entry_bar = break_idx + fail_idx[0]
                if entry_bar < len(post_or) - 5:  # enough time left in day
                    false_extreme = highs[:entry_bar + 1].max()
                    signals.append(StrategySignal(
                        trade_date=td_str,
                        entry_time=str(times[entry_bar]),
                        direction="short",
                        entry_price=closes[entry_bar],
                        stop_price=false_extreme + params["stop_buffer"],
                        target_price=l,
                        signal_name="or_fade_short",
                    ))
                    continue  # one signal per day

        # Check for downside breakout then failure (long signal)
        l_break = np.where(lows < l)[0]
        if len(l_break) > 0:
            break_idx = l_break[0]
            after_break = closes[break_idx:]
            fail_idx = np.where(after_break > l + params["entry_offset"])[0]
            if len(fail_idx) > 0:
                entry_bar = break_idx + fail_idx[0]
                if entry_bar < len(post_or) - 5:
                    false_extreme = lows[:entry_bar + 1].min()
                    signals.append(StrategySignal(
                        trade_date=td_str,
                        entry_time=str(times[entry_bar]),
                        direction="long",
                        entry_price=closes[entry_bar],
                        stop_price=false_extreme - params["stop_buffer"],
                        target_price=h,
                        signal_name="or_fade_long",
                    ))

    log(f"  Generated {len(signals)} signals ({len([s for s in signals if s.direction=='long'])} long, "
        f"{len([s for s in signals if s.direction=='short'])} short)")
    return signals


# Registry of strategies
STRATEGIES = {
    "or_fade": generate_signals_or_fade,
    # Add more strategy generators here as studies reveal edges
}


# ---------------------------------------------------------------------------
# Trade execution simulator
# ---------------------------------------------------------------------------

@timer
def simulate_trades(signals: List[StrategySignal], rth: pd.DataFrame,
                    instrument: InstrumentConfig, slippage_ticks: int = 1,
                    commission_per_side: float = 0.62) -> List[TradeResult]:
    """Simulate trade execution bar-by-bar with realistic assumptions."""
    results = []
    slip = slippage_ticks * instrument.tick_size

    for sig in signals:
        day_bars = rth[rth["trade_date"].astype(str) == sig.trade_date]
        if len(day_bars) == 0:
            continue

        # Find entry bar
        entry_mask = day_bars.index.astype(str) >= sig.entry_time
        trade_bars = day_bars[entry_mask]
        if len(trade_bars) == 0:
            continue

        # Apply slippage to entry
        if sig.direction == "long":
            entry = sig.entry_price + slip
        else:
            entry = sig.entry_price - slip

        # Walk forward bar by bar
        mae = 0.0
        mfe = 0.0
        exit_price = None
        exit_time = None
        exit_reason = "eod"

        for bar_time, bar in trade_bars.iterrows():
            if sig.direction == "long":
                # Check stop
                if bar["low"] <= sig.stop_price:
                    exit_price = sig.stop_price - slip
                    exit_time = str(bar_time)
                    exit_reason = "stop"
                    break
                # Check target
                if bar["high"] >= sig.target_price:
                    exit_price = sig.target_price - slip  # conservative: slip on limit too
                    exit_time = str(bar_time)
                    exit_reason = "target"
                    break
                # Track MAE/MFE
                mae = max(mae, entry - bar["low"])
                mfe = max(mfe, bar["high"] - entry)
            else:
                if bar["high"] >= sig.stop_price:
                    exit_price = sig.stop_price + slip
                    exit_time = str(bar_time)
                    exit_reason = "stop"
                    break
                if bar["low"] <= sig.target_price:
                    exit_price = sig.target_price + slip
                    exit_time = str(bar_time)
                    exit_reason = "target"
                    break
                mae = max(mae, bar["high"] - entry)
                mfe = max(mfe, entry - bar["low"])

        # End of day exit
        if exit_price is None:
            last_bar = trade_bars.iloc[-1]
            exit_price = last_bar["close"] + (slip if sig.direction == "short" else -slip)
            exit_time = str(trade_bars.index[-1])

        # Calculate P&L
        if sig.direction == "long":
            pnl_pts = exit_price - entry
        else:
            pnl_pts = entry - exit_price

        pnl_dollars = pnl_pts * instrument.point_value - (commission_per_side * 2)

        results.append(TradeResult(
            trade_date=sig.trade_date,
            entry_time=sig.entry_time,
            exit_time=exit_time,
            direction=sig.direction,
            entry_price=entry,
            exit_price=exit_price,
            stop_price=sig.stop_price,
            target_price=sig.target_price,
            pnl_pts=pnl_pts,
            pnl_dollars=pnl_dollars,
            mae_pts=mae,
            mfe_pts=mfe,
            exit_reason=exit_reason,
            signal_name=sig.signal_name,
        ))

    return results


# ---------------------------------------------------------------------------
# Prop firm equity simulation
# ---------------------------------------------------------------------------

@timer
def simulate_prop_account(trades: List[TradeResult],
                          max_drawdown: float = 2000,
                          daily_loss_limit: float = 300,
                          trailing: bool = True,
                          max_trades_per_day: int = 3) -> dict:
    """Simulate a prop firm account with realistic rules."""
    equity = 0.0
    peak_equity = 0.0
    max_dd_used = 0.0
    daily_pnl = 0.0
    current_date = None
    trades_today = 0
    blown = False

    equity_curve = []
    accepted_trades = []

    for t in trades:
        # New day?
        if t.trade_date != current_date:
            if current_date is not None:
                equity_curve.append({
                    "date": current_date,
                    "daily_pnl": daily_pnl,
                    "equity": equity,
                    "peak": peak_equity,
                    "drawdown": peak_equity - equity if trailing else -min(0, equity),
                })
            current_date = t.trade_date
            daily_pnl = 0.0
            trades_today = 0

        # Check daily limits
        if trades_today >= max_trades_per_day:
            continue
        if daily_pnl <= -daily_loss_limit:
            continue

        # Check account blown
        if trailing:
            dd = peak_equity - equity
        else:
            dd = -equity if equity < 0 else 0

        if dd >= max_drawdown:
            blown = True
            break

        # Execute trade
        equity += t.pnl_dollars
        daily_pnl += t.pnl_dollars
        trades_today += 1
        peak_equity = max(peak_equity, equity)

        current_dd = peak_equity - equity if trailing else (-equity if equity < 0 else 0)
        max_dd_used = max(max_dd_used, current_dd)

        accepted_trades.append(t)

    # Final day
    if current_date and not blown:
        equity_curve.append({
            "date": current_date,
            "daily_pnl": daily_pnl,
            "equity": equity,
            "peak": peak_equity,
            "drawdown": peak_equity - equity if trailing else -min(0, equity),
        })

    # Compute summary
    df_eq = pd.DataFrame(equity_curve)
    df_trades = pd.DataFrame([vars(t) for t in accepted_trades])

    n_trades = len(df_trades)
    wins = df_trades[df_trades["pnl_dollars"] > 0] if n_trades > 0 else pd.DataFrame()
    losses = df_trades[df_trades["pnl_dollars"] <= 0] if n_trades > 0 else pd.DataFrame()

    summary = {
        "total_trades": n_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / n_trades * 100 if n_trades > 0 else 0,
        "avg_win": wins["pnl_dollars"].mean() if len(wins) > 0 else 0,
        "avg_loss": losses["pnl_dollars"].mean() if len(losses) > 0 else 0,
        "profit_factor": abs(wins["pnl_dollars"].sum() / losses["pnl_dollars"].sum()) if len(losses) > 0 and losses["pnl_dollars"].sum() != 0 else float("inf"),
        "total_pnl": equity,
        "max_drawdown_used": max_dd_used,
        "max_drawdown_limit": max_drawdown,
        "blown": blown,
        "trading_days": len(df_eq),
        "avg_daily_pnl": df_eq["daily_pnl"].mean() if len(df_eq) > 0 else 0,
        "avg_trades_per_day": n_trades / len(df_eq) if len(df_eq) > 0 else 0,
        "longest_losing_streak": _max_streak(df_trades["pnl_dollars"].values, negative=True) if n_trades > 0 else 0,
        "longest_winning_streak": _max_streak(df_trades["pnl_dollars"].values, negative=False) if n_trades > 0 else 0,
    }

    # Consistency check: no single day > 30% of total profit
    if len(df_eq) > 0 and equity > 0:
        max_day = df_eq["daily_pnl"].max()
        summary["max_day_pct_of_total"] = max_day / equity * 100
        summary["passes_consistency"] = max_day / equity < 0.30
    else:
        summary["max_day_pct_of_total"] = 0
        summary["passes_consistency"] = False

    return summary, df_eq, df_trades


def _max_streak(pnls: np.ndarray, negative: bool = True) -> int:
    """Find longest consecutive losing (or winning) streak."""
    if negative:
        mask = pnls <= 0
    else:
        mask = pnls > 0

    max_streak = 0
    current = 0
    for m in mask:
        if m:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------

@timer
def monte_carlo(trades: List[TradeResult], n_sims: int = 1000,
                eval_target: float = 3000, max_drawdown: float = 2000,
                daily_loss_limit: float = 300, trailing: bool = True) -> dict:
    """Run Monte Carlo permutations of trade sequence.

    Randomly reorder trades and simulate prop account for each permutation.
    Measures probability of passing eval vs blowing account.
    """
    pnls = np.array([t.pnl_dollars for t in trades])
    n = len(pnls)

    if n == 0:
        return {"error": "No trades to simulate"}

    passed = 0
    blown = 0
    max_dds = []
    final_equities = []
    days_to_pass = []

    for _ in range(n_sims):
        perm = np.random.permutation(pnls)
        equity = 0.0
        peak = 0.0
        sim_blown = False
        sim_passed = False

        for i, pnl in enumerate(perm):
            equity += pnl
            peak = max(peak, equity)
            dd = peak - equity if trailing else max(0, -equity)

            if dd >= max_drawdown:
                sim_blown = True
                break

            if equity >= eval_target and not sim_passed:
                sim_passed = True
                days_to_pass.append(i + 1)

        if sim_passed and not sim_blown:
            passed += 1
        if sim_blown:
            blown += 1

        max_dds.append(peak - equity if not sim_blown else max_drawdown)
        final_equities.append(equity if not sim_blown else -max_drawdown)

    return {
        "n_simulations": n_sims,
        "n_trades_per_sim": n,
        "eval_target": eval_target,
        "max_drawdown": max_drawdown,
        "pass_rate_pct": passed / n_sims * 100,
        "blow_rate_pct": blown / n_sims * 100,
        "avg_final_equity": np.mean(final_equities),
        "median_final_equity": np.median(final_equities),
        "avg_max_drawdown": np.mean(max_dds),
        "avg_days_to_pass": np.mean(days_to_pass) if days_to_pass else None,
        "median_days_to_pass": np.median(days_to_pass) if days_to_pass else None,
        "p10_final_equity": np.percentile(final_equities, 10),
        "p90_final_equity": np.percentile(final_equities, 90),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Study 6: Prop Firm Simulation")
    parser.add_argument("--symbol", required=True, help="Symbol to simulate")
    parser.add_argument("--strategy", default="or_fade", choices=list(STRATEGIES.keys()))
    parser.add_argument("--instrument", default=None, help="Instrument for sizing (default: same as symbol)")
    parser.add_argument("--or-duration", type=int, default=30, help="OR duration for OR-based strategies")
    parser.add_argument("--monte-carlo", type=int, default=1000, help="Number of Monte Carlo simulations")
    parser.add_argument("--eval-target", type=float, default=3000, help="Eval profit target")
    parser.add_argument("--max-drawdown", type=float, default=2000, help="Max drawdown")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    cfg_strat = config["strategy"]
    instruments = config["instruments"]

    inst_key = args.instrument or args.symbol
    if inst_key not in instruments:
        # Try with M prefix for micro
        if f"M{inst_key}" in instruments:
            inst_key = f"M{inst_key}"
        else:
            log(f"WARNING: Instrument {inst_key} not found, using NQ defaults")
            inst_key = "MNQ"

    instrument = instruments[inst_key]
    log(f"Using instrument: {instrument.symbol} (${instrument.point_value}/pt)")

    # Load data
    rth = load_derived(f"{args.symbol}_rth_1min", cfg_data)
    or_data = load_derived(f"{args.symbol}_opening_ranges", cfg_data)
    daily_levels = load_derived(f"{args.symbol}_daily_levels", cfg_data)

    # Generate signals
    log(f"\nGenerating signals: {args.strategy}")
    gen_func = STRATEGIES[args.strategy]
    signals = gen_func(rth, or_data, daily_levels, or_duration=args.or_duration)

    if not signals:
        log("ERROR: No signals generated. Check strategy parameters.")
        sys.exit(1)

    # Simulate trades
    log(f"\nSimulating {len(signals)} trades...")
    trades = simulate_trades(signals, rth, instrument,
                             slippage_ticks=cfg_strat.slippage_ticks,
                             commission_per_side=cfg_strat.commission_per_side)

    # Run prop account simulation
    log("\nRunning prop account simulation...")
    summary, eq_curve, trade_log = simulate_prop_account(
        trades,
        max_drawdown=args.max_drawdown,
        daily_loss_limit=cfg_strat.daily_loss_limit,
        trailing=cfg_strat.trailing_drawdown,
        max_trades_per_day=cfg_strat.max_trades_per_day,
    )

    prefix = f"{args.symbol}_{args.strategy}"
    save_results(eq_curve, f"{prefix}_equity_curve", cfg_data)
    save_results(trade_log, f"{prefix}_trade_log", cfg_data)
    save_results_json(summary, f"{prefix}_sim_summary", cfg_data)

    log("\n--- SIMULATION RESULTS ---")
    for k, v in summary.items():
        if isinstance(v, float):
            log(f"  {k}: {v:.2f}")
        else:
            log(f"  {k}: {v}")

    # Monte Carlo
    if args.monte_carlo > 0:
        log(f"\nRunning {args.monte_carlo} Monte Carlo simulations...")
        mc = monte_carlo(
            trades, n_sims=args.monte_carlo,
            eval_target=args.eval_target,
            max_drawdown=args.max_drawdown,
            trailing=cfg_strat.trailing_drawdown,
        )
        save_results_json(mc, f"{prefix}_monte_carlo", cfg_data)

        log("\n--- MONTE CARLO RESULTS ---")
        for k, v in mc.items():
            if isinstance(v, float):
                log(f"  {k}: {v:.2f}")
            else:
                log(f"  {k}: {v}")

    log(f"\n{'='*60}")
    log("SIMULATION COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
