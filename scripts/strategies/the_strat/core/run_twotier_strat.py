"""Two-Tier Hybrid Strat Engine (Scale at +18 pts, Runner to 50+ pts).

Combines:
  1. Scale 1 (50% position): Take profit at +18 to +20 points (high win rate, locks in $360-$400).
  2. Breakeven Trigger: Instantly move stop to Entry + 1 tick.
  3. Runner (50% position): Rides to Magnitude 2 / 3-hour swing level (40-80+ pts) or 9 EMA trail.
  4. FTFC + VWAP alignment filter.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
import pandas as pd
import numpy as np

_project_root = Path(__file__).resolve().parent
while _project_root.name and _project_root.name != "scripts":
    _project_root = _project_root.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.libs_py.the_strat.taxonomy import classify_bars_df, StratType


def run_twotier_strat_backtest(
    ticker: str = "NQ1",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    scale_target_pts: float = 18.0,
    runner_target_pts: float = 50.0,
    max_risk_pts: float = 16.0,
    point_value: float = 20.0,
    commission_per_contract: float = 2.05,
    slippage_ticks: int = 1,
):
    print("=" * 85)
    print(f"TWO-TIER HYBRID STRAT ENGINE (Scale 50% @ +{scale_target_pts} pts, Runner to +{runner_target_pts} pts)")
    print(f"Period: {start_date} to {end_date} | Ticker: {ticker}")
    print("=" * 85)

    data_file = _project_root / "data" / f"{ticker}_1m.parquet"
    if not data_file.exists():
        data_file = _project_root / "data" / f"{ticker.replace('1', '')}_1m.parquet"

    df_1m = pd.read_parquet(data_file)
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_1m.index = df_1m.index.tz_convert("America/New_York")

    df_1m = df_1m.sort_index()
    df_filtered = df_1m[(df_1m.index >= start_date) & (df_1m.index <= end_date)]

    df_5m = df_filtered[["open", "high", "low", "close"]].resample("5min", origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_5m["ema9"] = df_5m["close"].ewm(span=9, adjust=False).mean()
    dates = df_5m.index.date
    typical_price = (df_5m["high"] + df_5m["low"] + df_5m["close"]) / 3.0
    df_5m["tp"] = typical_price
    df_5m["tp_cum"] = df_5m.groupby(dates)["tp"].cumsum()
    df_5m["count"] = df_5m.groupby(dates).cumcount() + 1
    df_5m["vwap"] = df_5m["tp_cum"] / df_5m["count"]

    # 3-hour swing extremes
    df_5m["swing_high_3h"] = df_5m["high"].rolling(36).max().shift(1)
    df_5m["swing_low_3h"] = df_5m["low"].rolling(36).min().shift(1)

    df_strat = classify_bars_df(df_5m)

    h = df_strat["high"].values
    l = df_strat["low"].values
    c = df_strat["close"].values
    vwap = df_strat["vwap"].values
    ema9 = df_strat["ema9"].values
    st = df_strat["strat_type"].values
    sh3 = df_strat["swing_high_3h"].values
    sl3 = df_strat["swing_low_3h"].values
    timestamps = df_strat.index
    times = df_strat.index.time

    tradeable_mask = ((times >= time(9, 45)) & (times <= time(11, 30))) | ((times >= time(14, 0)) & (times <= time(15, 30)))
    slip_pts = slippage_ticks * 0.25

    trades = []
    trades_today = 0
    current_day = None
    last_exit_idx = -1

    for i in range(36, len(df_strat)):
        if i <= last_exit_idx:
            continue

        bar_date = timestamps[i].date()
        if bar_date != current_day:
            current_day = bar_date
            trades_today = 0

        if trades_today >= 2 or not tradeable_mask[i]:
            continue

        curr_st = st[i]
        prev1_st = st[i - 1]
        prev2_st = st[i - 2]
        curr_vwap = vwap[i]

        entry = 0.0
        stop_loss = 0.0
        target1 = 0.0
        target2 = 0.0
        direction = 0
        setup_name = ""

        # 2-1-2 Setup
        if prev1_st == StratType.INSIDE:
            if prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_UP:
                if c[i] > curr_vwap:
                    entry = h[i - 1] + 0.25
                    inside_sl = l[i - 1] - 0.25
                    stop_loss = max(inside_sl, entry - max_risk_pts)
                    target1 = entry + scale_target_pts
                    target2 = max(sh3[i] if not np.isnan(sh3[i]) else (entry + runner_target_pts), entry + runner_target_pts)
                    direction = 1
                    setup_name = "2-1-2_Bull"

            elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_DOWN:
                if c[i] < curr_vwap:
                    entry = l[i - 1] - 0.25
                    inside_sl = h[i - 1] + 0.25
                    stop_loss = min(inside_sl, entry + max_risk_pts)
                    target1 = entry - scale_target_pts
                    target2 = min(sl3[i] if not np.isnan(sl3[i]) else (entry - runner_target_pts), entry - runner_target_pts)
                    direction = -1
                    setup_name = "2-1-2_Bear"

        # 2-2 Reversals
        elif prev1_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
            if c[i] >= curr_vwap:
                entry = h[i - 1] + 0.25
                inside_sl = l[i - 1] - 0.25
                stop_loss = max(inside_sl, entry - max_risk_pts)
                target1 = entry + scale_target_pts
                target2 = max(sh3[i] if not np.isnan(sh3[i]) else (entry + runner_target_pts), entry + runner_target_pts)
                direction = 1
                setup_name = "2-2_Bull_Rev"

        elif prev1_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
            if c[i] <= curr_vwap:
                entry = l[i - 1] - 0.25
                inside_sl = h[i - 1] + 0.25
                stop_loss = min(inside_sl, entry + max_risk_pts)
                target1 = entry - scale_target_pts
                target2 = min(sl3[i] if not np.isnan(sl3[i]) else (entry - runner_target_pts), entry - runner_target_pts)
                direction = -1
                setup_name = "2-2_Bear_Rev"

        if direction == 0:
            continue

        if direction == 1:
            actual_entry = entry + slip_pts
        else:
            actual_entry = entry - slip_pts

        # Simulation
        exit_idx = i
        pnl1 = 0.0
        pnl2 = 0.0
        hit_t1 = False
        hit_t2 = False
        hit_stop = False
        be_active = False

        for f in range(i, min(i + 36, len(df_strat))):
            bar_h = h[f]
            bar_l = l[f]
            bar_c = c[f]
            bar_ema = ema9[f]

            if direction == 1:
                current_sl = actual_entry if be_active else stop_loss
                if bar_l <= current_sl:
                    exit_idx = f
                    exit_price = current_sl - slip_pts
                    if not hit_t1:
                        pnl1 = exit_price - actual_entry
                        pnl2 = exit_price - actual_entry
                    else:
                        pnl2 = exit_price - actual_entry
                    hit_stop = True
                    break

                if not hit_t1 and bar_h >= target1:
                    pnl1 = target1 - actual_entry
                    hit_t1 = True
                    be_active = True  # Breakeven stop active

                if hit_t1:
                    if bar_h >= target2:
                        pnl2 = target2 - actual_entry
                        hit_t2 = True
                        exit_idx = f
                        break
                    elif bar_c < bar_ema:
                        pnl2 = bar_c - actual_entry
                        exit_idx = f
                        break

            else:  # Short
                current_sl = actual_entry if be_active else stop_loss
                if bar_h >= current_sl:
                    exit_idx = f
                    exit_price = current_sl + slip_pts
                    if not hit_t1:
                        pnl1 = actual_entry - exit_price
                        pnl2 = actual_entry - exit_price
                    else:
                        pnl2 = actual_entry - exit_price
                    hit_stop = True
                    break

                if not hit_t1 and bar_l <= target1:
                    pnl1 = actual_entry - target1
                    hit_t1 = True
                    be_active = True

                if hit_t1:
                    if bar_l <= target2:
                        pnl2 = actual_entry - target2
                        hit_t2 = True
                        exit_idx = f
                        break
                    elif bar_c > bar_ema:
                        pnl2 = actual_entry - bar_c
                        exit_idx = f
                        break

        if not hit_stop and not hit_t2:
            exit_idx = min(i + 36 - 1, len(df_strat) - 1)
            final_c = c[exit_idx]
            rem_pnl = (final_c - actual_entry) if direction == 1 else (actual_entry - final_c)
            if not hit_t1:
                pnl1 = rem_pnl
                pnl2 = rem_pnl
            else:
                pnl2 = rem_pnl

        total_pts = (0.5 * pnl1) + (0.5 * pnl2)
        net_dollars = (total_pts * point_value) - (2 * commission_per_contract)

        last_exit_idx = exit_idx
        trades_today += 1

        trades.append({
            "entry_time": timestamps[i],
            "exit_time": timestamps[exit_idx],
            "setup": setup_name,
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry": actual_entry,
            "pnl_pts": total_pts,
            "net_dollars": net_dollars,
            "hit_t1": hit_t1,
            "hit_t2": hit_t2,
            "bars_held": exit_idx - i + 1,
        })

    if not trades:
        print("No trades found.")
        return

    df_t = pd.DataFrame(trades)
    wins = df_t[df_t["net_dollars"] > 0]
    losses = df_t[df_t["net_dollars"] <= 0]
    wr = len(wins) / len(df_t)
    tot_win = wins["net_dollars"].sum()
    tot_loss = abs(losses["net_dollars"].sum())
    pf = (tot_win / tot_loss) if tot_loss > 0 else 999.0
    tot_pnl = df_t["net_dollars"].sum()
    tot_pts = df_t["pnl_pts"].sum()
    avg_win_pts = wins["pnl_pts"].mean() if len(wins) > 0 else 0
    avg_loss_pts = losses["pnl_pts"].mean() if len(losses) > 0 else 0
    avg_trade_pts = df_t["pnl_pts"].mean()

    cum = df_t["net_dollars"].cumsum()
    peak = cum.cummax()
    dd = (peak - cum).max()

    print("\n" + "-" * 85)
    print("TWO-TIER HYBRID STRAT PERFORMANCE SUMMARY")
    print("-" * 85)
    print(f"Total Trades: {len(df_t)} (Avg {len(df_t)/500:.2f} trades/day)")
    print(f"Win Rate: {wr * 100:.2f}% (Wins: {len(wins)}, Losses: {len(losses)})")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Net Points: {tot_pts:+,.2f} pts (${tot_pnl:+,.2f})")
    print(f"Max Drawdown: ${dd:,.2f}")
    print(f"Average Win: {avg_win_pts:+.2f} pts (${avg_win_pts * point_value:,.2f})")
    print(f"Average Loss: {avg_loss_pts:+.2f} pts (${avg_loss_pts * point_value:,.2f})")
    print(f"Payoff Ratio (Win/Loss): {abs(avg_win_pts / avg_loss_pts):.2f}:1")
    print(f"Expectancy Per Trade: {avg_trade_pts:+.2f} pts (${avg_trade_pts * point_value:,.2f})")
    print(f"Target 1 Hit Rate: {df_t['hit_t1'].mean()*100:.1f}% | Big Runner (T2) Hit Rate: {df_t['hit_t2'].mean()*100:.1f}%")
    print("-" * 85)


if __name__ == "__main__":
    run_twotier_strat_backtest(scale_target_pts=18.0, runner_target_pts=50.0, max_risk_pts=16.0)
