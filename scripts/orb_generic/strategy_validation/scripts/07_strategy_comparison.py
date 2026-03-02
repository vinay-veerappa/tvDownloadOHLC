#!/usr/bin/env python3
"""
07_strategy_comparison.py v6 — Zone-based strategy comparison
==============================================================
Usage:
    python 07_strategy_comparison.py --symbol NQ1
    python 07_strategy_comparison.py --symbol NQ1 --use-ib-bias
    python 07_strategy_comparison.py --symbol NQ1 --use-ib-bias --strategies choch_fade fib_discount
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.signal_generators import (
    STRATEGIES, ALL_STRATEGY_NAMES, StrategySignal, compute_ib_bias
)
from scripts.market_structure import pct_of_price


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
        try:
            rth.index = pd.to_datetime(rth.index, utc=True).tz_convert("US/Eastern")
        except Exception:
            pass
    return {td: grp for td, grp in rth.groupby("_td_norm")}


def log(msg):
    import time
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def simulate_trade(sig: StrategySignal, day_bars: pd.DataFrame,
                   point_value: float, tick_size: float,
                   slippage_ticks: int = 1, commission: float = 0.62) -> dict:
    slip = slippage_ticks * tick_size
    entry_mask = day_bars.index.astype(str) >= sig.entry_time
    trade_bars = day_bars[entry_mask]
    if len(trade_bars) == 0:
        return None

    entry = sig.entry_price + (slip if sig.direction == "long" else -slip)
    mae = mfe = 0.0
    exit_price = exit_time = None
    exit_reason = "eod"
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
        "trade_date": sig.trade_date, "signal_name": sig.signal_name,
        "direction": sig.direction, "entry_price": entry, "exit_price": exit_price,
        "stop_price": sig.stop_price, "target_price": sig.target_price,
        "pnl_pts": pnl_pts, "pnl_dollars": pnl_dollars,
        "pnl_pct": pct_of_price(pnl_pts, ref),
        "risk_pct": sig.risk_pct, "reward_pct": sig.reward_pct, "rr_ratio": sig.rr_ratio,
        "mae_pts": mae, "mfe_pts": mfe,
        "mae_pct": pct_of_price(mae, ref), "mfe_pct": pct_of_price(mfe, ref),
        "exit_reason": exit_reason, "confidence": sig.confidence,
        "ib_bias": sig.ib_bias, "first_formed": sig.first_formed,
        "zones_hit": sig.zones_hit, "entry_time": sig.entry_time, "exit_time": exit_time,
    }


def compute_summary(trades: pd.DataFrame, strategy_name: str) -> dict:
    n = len(trades)
    if n == 0:
        return {"strategy": strategy_name, "total_trades": 0}
    wins = trades[trades["pnl_dollars"] > 0]
    losses = trades[trades["pnl_dollars"] <= 0]
    pnls = trades["pnl_dollars"].values

    # Max losing streak
    streak = max_streak = 0
    for p in pnls:
        if p <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    max_dd = np.max(peak - cum) if len(cum) > 0 else 0

    return {
        "strategy": strategy_name, "total_trades": n,
        "wins": len(wins), "losses": len(losses),
        "win_rate_pct": len(wins) / n * 100,
        "avg_win_dollars": wins["pnl_dollars"].mean() if len(wins) > 0 else 0,
        "avg_loss_dollars": losses["pnl_dollars"].mean() if len(losses) > 0 else 0,
        "profit_factor": abs(wins["pnl_dollars"].sum() / losses["pnl_dollars"].sum())
            if len(losses) > 0 and losses["pnl_dollars"].sum() != 0 else float("inf"),
        "total_pnl_dollars": trades["pnl_dollars"].sum(),
        "avg_rr_ratio": trades["rr_ratio"].mean(),
        "pct_target_hit": (trades["exit_reason"] == "target").mean() * 100,
        "pct_stop_hit": (trades["exit_reason"] == "stop").mean() * 100,
        "pct_eod_exit": trades["exit_reason"].isin(["eod", "time_cutoff"]).mean() * 100,
        "max_drawdown_dollars": max_dd,
        "longest_losing_streak": max_streak,
    }


def main():
    parser = argparse.ArgumentParser(description="Strategy Comparison v6 (Zone-Based)")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--strategies", nargs="*", default=None)
    parser.add_argument("--or-duration", type=int, default=30)
    parser.add_argument("--instrument", default=None)
    parser.add_argument("--or-min-pct", type=float, default=0.05)
    parser.add_argument("--or-max-pct", type=float, default=0.5)
    parser.add_argument("--use-ib-bias", action="store_true")
    parser.add_argument("--ib-bias-minutes", type=int, default=15)
    parser.add_argument("--ib-min-width-pct", type=float, default=0.20)
    parser.add_argument("--swing-lookback", type=int, default=2)
    parser.add_argument("--target-rr", type=float, default=1.5)
    parser.add_argument("--max-risk-pct", type=float, default=0.20)
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    instruments = config["instruments"]

    strategies = args.strategies or ALL_STRATEGY_NAMES
    log(f"Strategies: {strategies}")
    log(f"IB Bias: {'ON ('+str(args.ib_bias_minutes)+'min)' if args.use_ib_bias else 'OFF'}")
    log(f"Zone-based architecture v6")

    inst_key = args.instrument or args.symbol
    for try_key in [inst_key, inst_key.rstrip("1"), f"M{inst_key.rstrip('1')}", "MNQ"]:
        if try_key in instruments:
            inst_key = try_key
            break
    instrument = instruments[inst_key]
    log(f"Instrument: {instrument.symbol} (${instrument.point_value}/pt)")

    from scripts.utils import load_derived
    rth = load_derived(f"{args.symbol}_rth_1min", cfg_data)
    or_data = load_derived(f"{args.symbol}_opening_ranges", cfg_data)
    if "trade_date" not in rth.columns:
        rth["trade_date"] = rth.index.date

    daily_dict = build_daily_dict(rth)
    or_dates = normalize_trade_date(or_data.index)
    or_start_min = 9 * 60 + 30
    or_end_min = or_start_min + args.or_duration
    max_entry_min = 11 * 60 + 30

    all_trades = {s: [] for s in strategies}

    log(f"Processing {len(or_data)} trading days...")
    for i in range(len(or_data)):
        td_str = or_dates.iloc[i]
        or_h = or_data.iloc[i].get(f"or_{args.or_duration}_high", np.nan)
        or_l = or_data.iloc[i].get(f"or_{args.or_duration}_low", np.nan)
        if pd.isna(or_h) or pd.isna(or_l):
            continue

        day_bars = daily_dict.get(td_str)
        if day_bars is None or len(day_bars) < 30:
            continue

        bar_minutes = day_bars.index.hour * 60 + day_bars.index.minute
        or_start_indices = np.where(bar_minutes.values >= or_start_min)[0]
        or_end_indices = np.where(bar_minutes.values >= or_end_min)[0]
        if len(or_start_indices) == 0 or len(or_end_indices) == 0:
            continue

        or_start_idx = or_start_indices[0]
        or_end_idx = or_end_indices[0]

        or_width = or_h - or_l
        ref = (or_h + or_l) / 2
        or_width_pct = pct_of_price(or_width, ref)
        if or_width_pct < args.or_min_pct or or_width_pct > args.or_max_pct:
            continue

        # Determine IB bias
        if args.use_ib_bias and or_width_pct >= args.ib_min_width_pct:
            ib_dir, _ = compute_ib_bias(day_bars["high"].values, day_bars["low"].values,
                                         or_start_idx, or_end_idx, args.ib_bias_minutes)
            bias = ib_dir if ib_dir else None
        else:
            bias = None

        # Build ctx_args for the new API
        ctx_args = {
            "day_bars": day_bars,
            "or_high": or_h,
            "or_low": or_l,
            "or_start_idx": or_start_idx,
            "or_end_idx": or_end_idx,
            "swing_lookback": args.swing_lookback,
            "bias_minutes": args.ib_bias_minutes,
        }

        for strat_name in strategies:
            gen_func = STRATEGIES[strat_name]
            try:
                sigs = gen_func(ctx_args, td_str, bias=bias,
                                params={"max_risk_pct": args.max_risk_pct,
                                        "target_rr": args.target_rr})
            except Exception as e:
                continue

            for sig in sigs[:1]:
                if sig.entry_bar_idx < len(day_bars):
                    entry_min = day_bars.index[sig.entry_bar_idx].hour * 60 + \
                                day_bars.index[sig.entry_bar_idx].minute
                    if entry_min <= max_entry_min:
                        result = simulate_trade(sig, day_bars, instrument.point_value,
                                                instrument.tick_size)
                        if result:
                            all_trades[strat_name].append(result)

        if (i + 1) % 1000 == 0:
            log(f"  Processed {i+1}/{len(or_data)} days")

    cfg_data.ensure_dirs()
    summaries = []
    suffix = "_ib" if args.use_ib_bias else ""

    for strat_name in strategies:
        trades = all_trades[strat_name]
        if trades:
            df = pd.DataFrame(trades)
            df.to_csv(Path(cfg_data.results_dir) / f"{args.symbol}_{strat_name}{suffix}_v6_trades.csv",
                      index=False)
            summary = compute_summary(df, strat_name)
        else:
            summary = {"strategy": strat_name, "total_trades": 0}
        summaries.append(summary)
        log(f"\n  {strat_name}: {summary.get('total_trades', 0)} trades, "
            f"WR {summary.get('win_rate_pct', 0):.1f}%, "
            f"PF {summary.get('profit_factor', 0):.2f}, "
            f"P&L ${summary.get('total_pnl_dollars', 0):.0f}, "
            f"MaxDD ${summary.get('max_drawdown_dollars', 0):.0f}")

    comp_df = pd.DataFrame(summaries)
    comp_path = Path(cfg_data.results_dir) / f"{args.symbol}_comparison{suffix}_v6.csv"
    comp_df.to_csv(comp_path, index=False)

    log(f"\n{'='*80}")
    log(f"STRATEGY COMPARISON v6 — {args.symbol}" + (" [IB BIAS]" if args.use_ib_bias else ""))
    log(f"{'='*80}")
    if not comp_df.empty:
        cols = ["strategy", "total_trades", "win_rate_pct", "profit_factor",
                "total_pnl_dollars", "avg_rr_ratio", "pct_target_hit", "pct_stop_hit",
                "pct_eod_exit", "max_drawdown_dollars", "longest_losing_streak"]
        available = [c for c in cols if c in comp_df.columns]
        print(comp_df[available].to_string(index=False))

    log(f"\nSaved: {comp_path}")


if __name__ == "__main__":
    main()
