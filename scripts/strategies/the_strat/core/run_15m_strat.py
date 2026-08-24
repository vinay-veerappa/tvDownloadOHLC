"""15-Minute Strat Trend Runner Engine (Aiming for 40-100+ Points on NQ).

Testing 15-minute Strat structure:
  - 15m Inside Bar (1) compression -> 15m 2-1-2 breakout.
  - 15m 2-2 Reversals at Session Extremes.
  - Targets: 40 - 100+ points.
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


def run_15m_strat_backtest(
    ticker: str = "NQ1",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    target_pts: float = 50.0,
    point_value: float = 20.0,
    commission_per_contract: float = 2.05,
    slippage_ticks: int = 1,
):
    print("=" * 85)
    print(f"15-MINUTE STRAT RUNNER ENGINE (Target = +{target_pts} pts) - {ticker}")
    print(f"Period: {start_date} to {end_date}")
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

    # Resample 15m
    df_15m = df_filtered[["open", "high", "low", "close"]].resample("15min", origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    dates = df_15m.index.date
    typical_price = (df_15m["high"] + df_15m["low"] + df_15m["close"]) / 3.0
    df_15m["tp"] = typical_price
    df_15m["tp_cum"] = df_15m.groupby(dates)["tp"].cumsum()
    df_15m["count"] = df_15m.groupby(dates).cumcount() + 1
    df_15m["vwap"] = df_15m["tp_cum"] / df_15m["count"]

    hl = df_15m["high"] - df_15m["low"]
    hc = (df_15m["high"] - df_15m["close"].shift()).abs()
    lc = (df_15m["low"] - df_15m["close"].shift()).abs()
    df_15m["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean().bfill()

    df_strat = classify_bars_df(df_15m)

    h = df_strat["high"].values
    l = df_strat["low"].values
    c = df_strat["close"].values
    vwap = df_strat["vwap"].values
    atr = df_strat["atr"].values
    st = df_strat["strat_type"].values
    timestamps = df_strat.index
    times = df_strat.index.time

    # Trade window: 09:45 - 15:00 ET
    tradeable_mask = (times >= time(9, 45)) & (times <= time(15, 0))
    slip_pts = slippage_ticks * 0.25

    def simulate_variant(allow_212=True, allow_22=False, use_vwap=True, tp_multiple_atr=1.5, sl_multiple_atr=1.0):
        trades = []
        last_exit_idx = -1
        current_day = None
        trades_today = 0

        for i in range(2, len(df_strat)):
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
            curr_atr = atr[i]

            entry = 0.0
            stop_loss = 0.0
            target = 0.0
            direction = 0
            setup_name = ""

            # 2-1-2 Setup on 15m
            if allow_212 and prev1_st == StratType.INSIDE:
                if prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_UP:
                    if not use_vwap or c[i] > curr_vwap:
                        entry = h[i - 1] + 0.25
                        stop_loss = entry - (curr_atr * sl_multiple_atr)
                        target = entry + (curr_atr * tp_multiple_atr)
                        direction = 1
                        setup_name = "15m_212_Bull"

                elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_DOWN:
                    if not use_vwap or c[i] < curr_vwap:
                        entry = l[i - 1] - 0.25
                        stop_loss = entry + (curr_atr * sl_multiple_atr)
                        target = entry - (curr_atr * tp_multiple_atr)
                        direction = -1
                        setup_name = "15m_212_Bear"

            # 2-2 Reversals on 15m
            elif allow_22:
                if prev1_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
                    if not use_vwap or c[i] >= curr_vwap:
                        entry = h[i - 1] + 0.25
                        stop_loss = entry - (curr_atr * sl_multiple_atr)
                        target = entry + (curr_atr * tp_multiple_atr)
                        direction = 1
                        setup_name = "15m_22_Bull_Rev"

                elif prev1_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
                    if not use_vwap or c[i] <= curr_vwap:
                        entry = l[i - 1] - 0.25
                        stop_loss = entry + (curr_atr * sl_multiple_atr)
                        target = entry - (curr_atr * tp_multiple_atr)
                        direction = -1
                        setup_name = "15m_22_Bear_Rev"

            if direction == 0:
                continue

            actual_entry = (entry + slip_pts) if direction == 1 else (entry - slip_pts)
            exit_idx = i
            exit_price = actual_entry
            hit_target = False
            hit_stop = False

            # Forward hold max 16 bars (4 hours)
            for f in range(i, min(i + 16, len(df_strat))):
                bar_h = h[f]
                bar_l = l[f]

                if direction == 1:
                    if bar_l <= stop_loss:
                        exit_idx = f
                        exit_price = stop_loss - slip_pts
                        hit_stop = True
                        break
                    if bar_h >= target:
                        exit_idx = f
                        exit_price = target
                        hit_target = True
                        break
                else:
                    if bar_h >= stop_loss:
                        exit_idx = f
                        exit_price = stop_loss + slip_pts
                        hit_stop = True
                        break
                    if bar_l <= target:
                        exit_idx = f
                        exit_price = target
                        hit_target = True
                        break

            if not hit_target and not hit_stop:
                exit_idx = min(i + 16 - 1, len(df_strat) - 1)
                exit_price = c[exit_idx]

            pnl_pts = (exit_price - actual_entry) if direction == 1 else (actual_entry - exit_price)
            net_dollars = (pnl_pts * point_value) - (2 * commission_per_contract)

            last_exit_idx = exit_idx
            trades_today += 1
            trades.append({
                "entry_time": timestamps[i],
                "exit_time": timestamps[exit_idx],
                "setup": setup_name,
                "direction": "LONG" if direction == 1 else "SHORT",
                "pnl_pts": pnl_pts,
                "net_dollars": net_dollars,
                "hit_target": hit_target,
            })

        if not trades:
            return {"trades": 0, "wr": 0, "pf": 0, "pnl": 0, "pts": 0, "dd": 0, "avg_win": 0, "avg_loss": 0, "avg_trade": 0}

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

        return {
            "trades": len(df_t),
            "wr": wr,
            "pf": pf,
            "pnl": tot_pnl,
            "pts": tot_pts,
            "dd": dd,
            "avg_win": avg_win_pts,
            "avg_loss": avg_loss_pts,
            "avg_trade": avg_trade_pts,
        }

    print("\n" + "=" * 115)
    print(f"{'15-Minute Strategy Configuration':<45} | {'Trades':<7} | {'Win Rate':<9} | {'PF':<6} | {'Net PnL ($)':<14} | {'Max DD ($)':<12} | {'Avg Win/Loss':<18} | {'Avg Trade':<10}")
    print("=" * 115)

    tests = [
        ("1. 15m 2-1-2 Trend (TP=1.5x ATR, SL=1.0x ATR)", True, False, True, 1.5, 1.0),
        ("2. 15m 2-1-2 Trend (TP=2.0x ATR, SL=1.0x ATR)", True, False, True, 2.0, 1.0),
        ("3. 15m 2-1-2 Trend (TP=2.5x ATR, SL=1.0x ATR)", True, False, True, 2.5, 1.0),
        ("4. 15m 2-2 Reversals (TP=2.0x ATR, SL=1.0x ATR)", False, True, True, 2.0, 1.0),
        ("5. 15m Multi-Setup (TP=2.0x ATR, SL=1.0x ATR)", True, True, True, 2.0, 1.0),
    ]

    for name, a212, a22, vwap_f, tp_m, sl_m in tests:
        res = simulate_variant(allow_212=a212, allow_22=a22, use_vwap=vwap_f, tp_multiple_atr=tp_m, sl_multiple_atr=sl_m)
        wr_s = f"{res['wr']*100:.1f}%"
        pf_s = f"{res['pf']:.2f}"
        pnl_s = f"${res['pnl']:+,.2f}"
        dd_s = f"${res['dd']:,.2f}"
        wl_s = f"+{res['avg_win']:.1f} / {res['avg_loss']:.1f} pt"
        avg_s = f"{res['avg_trade']:+.2f} pts"
        print(f"{name:<45} | {res['trades']:<7} | {wr_s:<9} | {pf_s:<6} | {pnl_s:<14} | {dd_s:<12} | {wl_s:<18} | {avg_s:<10}")

    print("=" * 115)


if __name__ == "__main__":
    run_15m_strat_backtest()
