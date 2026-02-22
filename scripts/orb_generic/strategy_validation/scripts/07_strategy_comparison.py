#!/usr/bin/env python3
"""
07_strategy_comparison.py — Head-to-head comparison of all entry strategies
============================================================================
Runs each signal generator against the same data with identical risk mgmt,
then produces a comparison table.

Usage:
    python 07_strategy_comparison.py --symbol NQ1
    python 07_strategy_comparison.py --symbol NQ1 --strategies choch_fade fib_discount
    python 07_strategy_comparison.py --symbol NQ1 --walk-forward

Output:
    {symbol}_strategy_comparison.csv
    {symbol}_{strategy}_trades.csv (per strategy)
    {symbol}_comparison_summary.json
"""

import argparse
import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import asdict
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.signal_generators import (
    STRATEGIES, ALL_STRATEGY_NAMES, StrategySignal, get_day_context, make_signal
)
from scripts.market_structure import pct_of_price


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_trade_date(series_or_index):
    s = pd.Series(series_or_index)
    try:
        return pd.to_datetime(s).dt.strftime("%Y-%m-%d")
    except Exception:
        return s.astype(str).str[:10]


def build_daily_dict(rth: pd.DataFrame) -> dict:
    rth = rth.copy()
    rth["_td_norm"] = normalize_trade_date(rth["trade_date"]).values
    if not isinstance(rth.index, pd.DatetimeIndex):
        rth.index = pd.to_datetime(rth.index, utc=True)
        try:
            rth.index = rth.index.tz_convert("US/Eastern")
        except Exception:
            pass
    return {td: grp for td, grp in rth.groupby("_td_norm")}


def log(msg):
    import time
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


# ---------------------------------------------------------------------------
# Trade simulator (same as Script 06 but percentage-aware)
# ---------------------------------------------------------------------------

def simulate_trade(sig: StrategySignal, day_bars: pd.DataFrame,
                   point_value: float, tick_size: float,
                   slippage_ticks: int = 1, commission: float = 0.62) -> dict:
    """Simulate a single trade bar-by-bar. Returns trade result dict."""
    slip = slippage_ticks * tick_size

    entry_mask = day_bars.index.astype(str) >= sig.entry_time
    trade_bars = day_bars[entry_mask]
    if len(trade_bars) == 0:
        return None

    entry = sig.entry_price + (slip if sig.direction == "long" else -slip)
    mae = 0.0
    mfe = 0.0
    exit_price = None
    exit_time = None
    exit_reason = "eod"

    # Time cutoff: no trade running past 15:45
    cutoff_min = 15 * 60 + 45

    for bar_time, bar in trade_bars.iterrows():
        bar_min = bar_time.hour * 60 + bar_time.minute
        if bar_min >= cutoff_min:
            exit_price = bar["close"] + (slip if sig.direction == "short" else -slip)
            exit_time = str(bar_time)
            exit_reason = "time_cutoff"
            break

        if sig.direction == "long":
            if bar["low"] <= sig.stop_price:
                exit_price = sig.stop_price - slip
                exit_time = str(bar_time)
                exit_reason = "stop"
                break
            if bar["high"] >= sig.target_price:
                exit_price = sig.target_price - slip
                exit_time = str(bar_time)
                exit_reason = "target"
                break
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

    if exit_price is None:
        last = trade_bars.iloc[-1]
        exit_price = last["close"] + (slip if sig.direction == "short" else -slip)
        exit_time = str(trade_bars.index[-1])

    pnl_pts = (exit_price - entry) if sig.direction == "long" else (entry - exit_price)
    pnl_dollars = pnl_pts * point_value - (commission * 2)
    ref = sig.entry_price

    return {
        "trade_date": sig.trade_date,
        "signal_name": sig.signal_name,
        "direction": sig.direction,
        "entry_price": entry,
        "exit_price": exit_price,
        "stop_price": sig.stop_price,
        "target_price": sig.target_price,
        "pnl_pts": pnl_pts,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pct_of_price(pnl_pts, ref),
        "risk_pct": sig.risk_pct,
        "reward_pct": sig.reward_pct,
        "rr_ratio": sig.rr_ratio,
        "mae_pts": mae,
        "mfe_pts": mfe,
        "mae_pct": pct_of_price(mae, ref),
        "mfe_pct": pct_of_price(mfe, ref),
        "exit_reason": exit_reason,
        "confidence": sig.confidence,
        "entry_time": sig.entry_time,
        "exit_time": exit_time,
    }


# ---------------------------------------------------------------------------
# Run all strategies on a single day
# ---------------------------------------------------------------------------

def run_day(td_str: str, day_bars: pd.DataFrame, or_high: float, or_low: float,
            or_end_min: int, strategies: list, bias: str = None,
            or_width_pct_range: tuple = (0.05, 0.5)) -> Dict[str, List[StrategySignal]]:
    """Run all strategies for one day. Returns {strategy_name: [signals]}."""

    # Find OR end index
    bar_minutes = day_bars.index.hour * 60 + day_bars.index.minute
    or_end_indices = np.where(bar_minutes.values >= or_end_min)[0]
    if len(or_end_indices) == 0:
        return {}
    or_end_idx = or_end_indices[0]

    or_width = or_high - or_low
    ref = (or_high + or_low) / 2
    or_width_pct = pct_of_price(or_width, ref)

    # Filter by OR width percentage
    if or_width_pct < or_width_pct_range[0] or or_width_pct > or_width_pct_range[1]:
        return {}

    # Entry time cutoff: no entries after 11:30 AM (690 min from midnight)
    max_entry_min = 11 * 60 + 30

    # Build context
    ctx = get_day_context(day_bars, or_high, or_low, or_end_idx)

    results = {}
    for strat_name in strategies:
        gen_func = STRATEGIES[strat_name]
        try:
            sigs = gen_func(ctx, td_str, bias=bias)
        except Exception as e:
            continue

        # Filter: only keep signals before entry cutoff
        valid_sigs = []
        for sig in sigs:
            if sig.entry_bar_idx < len(day_bars):
                entry_min = day_bars.index[sig.entry_bar_idx].hour * 60 + \
                            day_bars.index[sig.entry_bar_idx].minute
                if entry_min <= max_entry_min:
                    valid_sigs.append(sig)

        results[strat_name] = valid_sigs

    return results


# ---------------------------------------------------------------------------
# Compute summary statistics
# ---------------------------------------------------------------------------

def compute_summary(trades: pd.DataFrame, strategy_name: str) -> dict:
    """Compute comprehensive summary stats for a strategy."""
    n = len(trades)
    if n == 0:
        return {"strategy": strategy_name, "total_trades": 0}

    wins = trades[trades["pnl_dollars"] > 0]
    losses = trades[trades["pnl_dollars"] <= 0]

    return {
        "strategy": strategy_name,
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": len(wins) / n * 100,
        "avg_win_dollars": wins["pnl_dollars"].mean() if len(wins) > 0 else 0,
        "avg_loss_dollars": losses["pnl_dollars"].mean() if len(losses) > 0 else 0,
        "profit_factor": abs(wins["pnl_dollars"].sum() / losses["pnl_dollars"].sum())
            if len(losses) > 0 and losses["pnl_dollars"].sum() != 0 else float("inf"),
        "total_pnl_dollars": trades["pnl_dollars"].sum(),
        "avg_pnl_pct": trades["pnl_pct"].mean(),
        "avg_risk_pct": trades["risk_pct"].mean(),
        "avg_reward_pct": trades["reward_pct"].mean(),
        "avg_rr_ratio": trades["rr_ratio"].mean(),
        "median_rr_ratio": trades["rr_ratio"].median(),
        "avg_mae_pct": trades["mae_pct"].mean(),
        "avg_mfe_pct": trades["mfe_pct"].mean(),
        "pct_target_hit": (trades["exit_reason"] == "target").mean() * 100,
        "pct_stop_hit": (trades["exit_reason"] == "stop").mean() * 100,
        "pct_eod_exit": (trades["exit_reason"].isin(["eod", "time_cutoff"])).mean() * 100,
        "longest_losing_streak": _max_streak(trades["pnl_dollars"].values, negative=True),
        "longest_winning_streak": _max_streak(trades["pnl_dollars"].values, negative=False),
        "max_drawdown_dollars": _max_drawdown(trades["pnl_dollars"].values),
        "avg_confidence": trades["confidence"].mean() if "confidence" in trades.columns else 1.0,
    }


def _max_streak(pnls, negative=True):
    mask = pnls <= 0 if negative else pnls > 0
    max_s = current = 0
    for m in mask:
        if m:
            current += 1
            max_s = max(max_s, current)
        else:
            current = 0
    return max_s


def _max_drawdown(pnls):
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    return np.max(dd) if len(dd) > 0 else 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Strategy Comparison")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--strategies", nargs="*", default=None,
                        help="Specific strategies (default: all)")
    parser.add_argument("--or-duration", type=int, default=30)
    parser.add_argument("--instrument", default=None)
    parser.add_argument("--or-min-pct", type=float, default=0.05,
                        help="Min OR width as %% of price")
    parser.add_argument("--or-max-pct", type=float, default=0.5,
                        help="Max OR width as %% of price")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    instruments = config["instruments"]

    strategies = args.strategies or ALL_STRATEGY_NAMES
    log(f"Running strategies: {strategies}")

    # Load instrument
    inst_key = args.instrument or args.symbol
    for try_key in [inst_key, inst_key.rstrip("1"), f"M{inst_key.rstrip('1')}", "MNQ"]:
        if try_key in instruments:
            inst_key = try_key
            break
    instrument = instruments[inst_key]
    log(f"Instrument: {instrument.symbol} (${instrument.point_value}/pt)")

    # Load data
    from scripts.utils import load_derived
    rth = load_derived(f"{args.symbol}_rth_1min", cfg_data)
    or_data = load_derived(f"{args.symbol}_opening_ranges", cfg_data)

    if "trade_date" not in rth.columns:
        rth["trade_date"] = rth.index.date

    daily_dict = build_daily_dict(rth)
    or_dates = normalize_trade_date(or_data.index)
    or_end_min = 9 * 60 + 30 + args.or_duration

    # Run all strategies across all days
    all_trades = {s: [] for s in strategies}

    log(f"Processing {len(or_data)} trading days...")
    for i in range(len(or_data)):
        td_str = or_dates.iloc[i]
        or_h_col = f"or_{args.or_duration}_high"
        or_l_col = f"or_{args.or_duration}_low"

        or_h = or_data.iloc[i].get(or_h_col, np.nan)
        or_l = or_data.iloc[i].get(or_l_col, np.nan)
        if pd.isna(or_h) or pd.isna(or_l):
            continue

        day_bars = daily_dict.get(td_str)
        if day_bars is None or len(day_bars) < 30:
            continue

        # Run strategies
        day_signals = run_day(
            td_str, day_bars, or_h, or_l, or_end_min, strategies,
            bias=None,
            or_width_pct_range=(args.or_min_pct, args.or_max_pct),
        )

        # Simulate each signal
        for strat_name, sigs in day_signals.items():
            for sig in sigs[:1]:  # max 1 trade per strategy per day
                result = simulate_trade(
                    sig, day_bars, instrument.point_value, instrument.tick_size)
                if result:
                    all_trades[strat_name].append(result)

        if (i + 1) % 1000 == 0:
            log(f"  Processed {i+1}/{len(or_data)} days")

    # Compute summaries
    cfg_data.ensure_dirs()
    summaries = []

    for strat_name in strategies:
        trades = all_trades[strat_name]
        if trades:
            df = pd.DataFrame(trades)
            df.to_csv(Path(cfg_data.results_dir) / f"{args.symbol}_{strat_name}_trades.csv",
                      index=False)
            summary = compute_summary(df, strat_name)
        else:
            summary = {"strategy": strat_name, "total_trades": 0}

        summaries.append(summary)
        log(f"\n  {strat_name}: {summary.get('total_trades', 0)} trades, "
            f"WR {summary.get('win_rate_pct', 0):.1f}%, "
            f"PF {summary.get('profit_factor', 0):.2f}, "
            f"P&L ${summary.get('total_pnl_dollars', 0):.0f}")

    # Save comparison table
    comp_df = pd.DataFrame(summaries)
    comp_path = Path(cfg_data.results_dir) / f"{args.symbol}_strategy_comparison.csv"
    comp_df.to_csv(comp_path, index=False)
    log(f"\nComparison saved: {comp_path}")

    # Print comparison
    log(f"\n{'='*80}")
    log(f"STRATEGY COMPARISON — {args.symbol}")
    log(f"{'='*80}")
    if not comp_df.empty:
        display_cols = ["strategy", "total_trades", "win_rate_pct", "profit_factor",
                        "total_pnl_dollars", "avg_rr_ratio", "median_rr_ratio",
                        "pct_target_hit", "pct_stop_hit", "pct_eod_exit",
                        "max_drawdown_dollars", "longest_losing_streak"]
        available = [c for c in display_cols if c in comp_df.columns]
        print(comp_df[available].to_string(index=False))


if __name__ == "__main__":
    main()
