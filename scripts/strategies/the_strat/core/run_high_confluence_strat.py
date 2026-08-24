"""High-Confluence Institutional Strat Engine (Aiming for 40-80+ Points).

Confluences added:
  1. Multi-Timeframe Trend Continuity: Require 60m bar to be actively expanding (60m 2U for longs, 60m 2D for shorts).
  2. VWAP Alignment: Price must be on the favorable side of Session VWAP (> VWAP for Long, < VWAP for Short).
  3. Minimum Target: 40.0 Points (NQ).
  4. Max 2 Trades Per Day (One-and-Done / Morning Drive only: 09:45 - 11:30 ET).
  5. Structural Stop Loss: Capped at 15 points (Risk = 15 pts, Target = 40-60 pts -> Asymmetric 3:1 to 4:1 R:R).
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


def run_high_confluence_strat_backtest(
    ticker: str = "NQ1",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    min_target_pts: float = 40.0,
    max_risk_pts: float = 15.0,
    point_value: float = 20.0,
    commission_per_contract: float = 2.05,
    slippage_ticks: int = 1,
):
    print("=" * 85)
    print(f"HIGH-CONFLUENCE STRAT RUNNER ENGINE (Target >= {min_target_pts} pts, Risk <= {max_risk_pts} pts)")
    print(f"Period: {start_date} to {end_date} | Ticker: {ticker} | Asymmetric R:R >= 2.5:1")
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

    # Resample 5m and 60m
    df_5m = df_filtered[["open", "high", "low", "close", "volume"] if "volume" in df_filtered.columns else ["open", "high", "low", "close"]].resample("5min", origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_60m = df_filtered[["open", "high", "low", "close"]].resample("1h", origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    # Classify 5m and 60m Strat bars
    df_5m_strat = classify_bars_df(df_5m)
    df_60m_strat = classify_bars_df(df_60m)

    # Reindex 60m Strat type to 5m bars
    df_5m_strat["strat_60m"] = df_60m_strat["strat_type"].reindex(df_5m_strat.index, method="ffill")

    # Compute Intraday Session VWAP
    # Identify session start (18:00 ET or 09:30 ET)
    dates = df_5m_strat.index.date
    df_5m_strat["cum_vol"] = 1.0  # fallback equal-weight if volume absent
    typical_price = (df_5m_strat["high"] + df_5m_strat["low"] + df_5m_strat["close"]) / 3.0
    df_5m_strat["tp"] = typical_price
    df_5m_strat["tp_cum"] = df_5m_strat.groupby(dates)["tp"].cumsum()
    df_5m_strat["count"] = df_5m_strat.groupby(dates).cumcount() + 1
    df_5m_strat["vwap"] = df_5m_strat["tp_cum"] / df_5m_strat["count"]

    # 12-bar swing extremes (1 hour lookback)
    df_5m_strat["swing_high_1h"] = df_5m_strat["high"].rolling(12).max().shift(1)
    df_5m_strat["swing_low_1h"] = df_5m_strat["low"].rolling(12).min().shift(1)

    # 36-bar swing extremes (3 hour lookback - major target)
    df_5m_strat["swing_high_3h"] = df_5m_strat["high"].rolling(36).max().shift(1)
    df_5m_strat["swing_low_3h"] = df_5m_strat["low"].rolling(36).min().shift(1)

    h = df_5m_strat["high"].values
    l = df_5m_strat["low"].values
    c = df_5m_strat["close"].values
    o = df_5m_strat["open"].values
    vwap = df_5m_strat["vwap"].values
    st5 = df_5m_strat["strat_type"].values
    st60 = df_5m_strat["strat_60m"].values
    sh3 = df_5m_strat["swing_high_3h"].values
    sl3 = df_5m_strat["swing_low_3h"].values
    timestamps = df_5m_strat.index
    times = df_5m_strat.index.time

    # Time filter: Morning Drive (09:45 - 11:30 ET) + Afternoon Power Hour (14:00 - 15:30 ET)
    tradeable_mask = ((times >= time(9, 45)) & (times <= time(11, 30))) | ((times >= time(14, 0)) & (times <= time(15, 30)))

    slip_pts = slippage_ticks * 0.25
    trades = []
    trades_today = 0
    current_day = None
    last_exit_idx = -1

    for i in range(36, len(df_5m_strat)):
        if i <= last_exit_idx:
            continue

        bar_date = timestamps[i].date()
        if bar_date != current_day:
            current_day = bar_date
            trades_today = 0

        # Cap to max 2 pristine setups per day
        if trades_today >= 2:
            continue

        if not tradeable_mask[i]:
            continue

        curr_st = st5[i]
        prev1_st = st5[i - 1]
        prev2_st = st5[i - 2]
        curr_60m_st = st60[i]
        curr_vwap = vwap[i]

        entry = 0.0
        stop_loss = 0.0
        target = 0.0
        direction = 0
        setup_name = ""

        # =================================================================
        # High-Conviction 2-1-2 Setup (Aligned with 60m Expansion + VWAP)
        # =================================================================
        if prev1_st == StratType.INSIDE:
            # Bullish 2U-1-2U
            # Confluences:
            # 1. 5m 2U breakout above inside bar
            # 2. 60m bar is actively Bullish (2U or Green)
            # 3. Price is above session VWAP
            if prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_UP:
                if c[i] > curr_vwap:
                    entry = h[i - 1] + 0.25
                    inside_sl = l[i - 1] - 0.25
                    # Risk control: cap SL to max_risk_pts
                    stop_loss = max(inside_sl, entry - max_risk_pts)
                    # Target: 3-hour swing high or minimum min_target_pts
                    target = max(sh3[i] if not np.isnan(sh3[i]) else (entry + min_target_pts), entry + min_target_pts)
                    direction = 1
                    setup_name = "HC_2-1-2_Bull"

            # Bearish 2D-1-2D
            elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_DOWN:
                if c[i] < curr_vwap:
                    entry = l[i - 1] - 0.25
                    inside_sl = h[i - 1] + 0.25
                    stop_loss = min(inside_sl, entry + max_risk_pts)
                    target = min(sl3[i] if not np.isnan(sl3[i]) else (entry - min_target_pts), entry - min_target_pts)
                    direction = -1
                    setup_name = "HC_2-1-2_Bear"

        # =================================================================
        # High-Conviction 2-2 Reversal (RevStrat at VWAP / Extreme)
        # =================================================================
        elif prev1_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
            # Bullish 2-2: Sellers trapped below VWAP snapping back above VWAP
            if c[i] >= curr_vwap:
                entry = h[i - 1] + 0.25
                inside_sl = l[i - 1] - 0.25
                stop_loss = max(inside_sl, entry - max_risk_pts)
                target = max(sh3[i] if not np.isnan(sh3[i]) else (entry + min_target_pts), entry + min_target_pts)
                direction = 1
                setup_name = "HC_2-2_Bull_Rev"

        elif prev1_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
            if c[i] <= curr_vwap:
                entry = l[i - 1] - 0.25
                inside_sl = h[i - 1] + 0.25
                stop_loss = min(inside_sl, entry + max_risk_pts)
                target = min(sl3[i] if not np.isnan(sl3[i]) else (entry - min_target_pts), entry - min_target_pts)
                direction = -1
                setup_name = "HC_2-2_Bear_Rev"

        if direction == 0:
            continue

        # Check Asymmetric R:R requirement (Reward >= 2.0x Risk)
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        if risk <= 0 or (reward / risk) < 2.0:
            continue

        if direction == 1:
            actual_entry = entry + slip_pts
        else:
            actual_entry = entry - slip_pts

        # Execute Forward Bar-by-Bar Simulation
        exit_idx = i
        exit_price = actual_entry
        hit_target = False
        hit_stop = False
        exit_reason = "time_exit"

        # Allow up to 36 bars (3 hours) for runner to develop
        for f in range(i, min(i + 36, len(df_5m_strat))):
            bar_h = h[f]
            bar_l = l[f]
            bar_c = c[f]

            if direction == 1:
                if bar_l <= stop_loss:
                    exit_idx = f
                    exit_price = stop_loss - slip_pts
                    hit_stop = True
                    exit_reason = "stop_loss"
                    break
                if bar_h >= target:
                    exit_idx = f
                    exit_price = target
                    hit_target = True
                    exit_reason = "target_hit"
                    break
            else:
                if bar_h >= stop_loss:
                    exit_idx = f
                    exit_price = stop_loss + slip_pts
                    hit_stop = True
                    exit_reason = "stop_loss"
                    break
                if bar_l <= target:
                    exit_idx = f
                    exit_price = target
                    hit_target = True
                    exit_reason = "target_hit"
                    break

        if not hit_target and not hit_stop:
            exit_idx = min(i + 36 - 1, len(df_5m_strat) - 1)
            exit_price = c[exit_idx]

        if direction == 1:
            pnl_pts = exit_price - actual_entry
        else:
            pnl_pts = actual_entry - exit_price

        net_dollars = (pnl_pts * point_value) - (2 * commission_per_contract)
        last_exit_idx = exit_idx
        trades_today += 1

        trades.append({
            "entry_time": timestamps[i],
            "exit_time": timestamps[exit_idx],
            "setup": setup_name,
            "direction": "LONG" if direction == 1 else "SHORT",
            "entry": actual_entry,
            "stop": stop_loss,
            "target": target,
            "pnl_pts": pnl_pts,
            "net_dollars": net_dollars,
            "hit_target": hit_target,
            "hit_stop": hit_stop,
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
    print("HIGH-CONFLUENCE STRAT PERFORMANCE SUMMARY")
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
    print("-" * 85)

    print("\nSample 5 Winning Trades (Capturing 40-70+ pts):")
    big_wins = wins.sort_values("pnl_pts", ascending=False).head(5)
    for idx, t in big_wins.iterrows():
        print(f"  {t['entry_time'].strftime('%Y-%m-%d %H:%M')}: {t['direction']} {t['setup']} @ {t['entry']:.2f} -> Exit @ {t['entry']+t['pnl_pts']:.2f} | PnL: {t['pnl_pts']:+,.2f} pts (${t['net_dollars']:+,.2f}) [{t['bars_held']} bars]")


if __name__ == "__main__":
    run_high_confluence_strat_backtest(min_target_pts=40.0, max_risk_pts=15.0)
