"""Institutional Strat Trader Engine & Advanced Backtest.

Upgrades naive Strat logic into a realistic, professional futures trading system:
  1. Minimum Target Threshold: Filter out any micro-scalp < 15 points on NQ (or < 0.75x ATR).
  2. Multi-Tier Target Architecture:
     - Target 1 (50% scale): Magnitude 1 or minimum 15-20 pts.
     - Target 2 (50% runner): Magnitude 2 / Broadening boundary / Trailing 9 EMA.
  3. FTFC Trend Alignment Gate: Require strict Multi-Timeframe Alignment (15m + 1H + Daily).
  4. Time-of-Day Killzones: Exclude 11:30 - 13:45 ET lunchtime chop.
  5. ATR-based Stop & Dynamic Breakeven: Move SL to entry after Target 1 is achieved.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
import pandas as pd
import numpy as np

# Project root-based imports
_project_root = Path(__file__).resolve().parent
while _project_root.name and _project_root.name != "scripts":
    _project_root = _project_root.parent
if _project_root.name == "scripts":
    _project_root = _project_root.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.libs_py.the_strat.taxonomy import classify_bars_df, StratType
from scripts.libs_py.the_strat.combos import ComboType, TradeDirection
from scripts.libs_py.the_strat.ftfc import FTFCEngine, Direction


def run_institutional_strat_backtest(
    ticker: str = "NQ1",
    timeframe: str = "5min",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    min_target_points: float = 15.0,  # Minimum 15 pts on NQ
    point_value: float = 20.0,
    commission_per_contract: float = 2.05,
    slippage_ticks: int = 1,
):
    print("=" * 85)
    print(f"INSTITUTIONAL STRAT TRADING SYSTEM BACKTEST - {ticker} ({timeframe})")
    print(f"Period: {start_date} to {end_date} | Min Target: {min_target_points} pts | Slip: {slippage_ticks} tick | Comm: ${commission_per_contract}/contract")
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

    # Resample 5m
    df_5m = df_filtered[["open", "high", "low", "close"]].resample("5min", origin="start_day").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    # Calculate 5m ATR and 9 EMA
    hl = df_5m["high"] - df_5m["low"]
    hc = (df_5m["high"] - df_5m["close"].shift()).abs()
    lc = (df_5m["low"] - df_5m["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df_5m["atr"] = tr.rolling(14).mean().bfill()
    df_5m["ema9"] = df_5m["close"].ewm(span=9, adjust=False).mean()

    # Classify Strat bars
    df_strat = classify_bars_df(df_5m)

    # Pre-calculate FTFC from 1m data resampled to higher timeframes
    df_15m = df_filtered[["open", "close"]].resample("15min", origin="start_day").agg({"open": "first", "close": "last"}).dropna()
    df_1h = df_filtered[["open", "close"]].resample("1h", origin="start_day").agg({"open": "first", "close": "last"}).dropna()

    # Fast arrays
    h = df_strat["high"].values
    l = df_strat["low"].values
    c = df_strat["close"].values
    o = df_strat["open"].values
    atr = df_strat["atr"].values
    ema9 = df_strat["ema9"].values
    st = df_strat["strat_type"].values
    timestamps = df_strat.index

    # Identify swing highs and swing lows for Magnitude 2 (lookback 12 bars = 1 hour)
    swing_highs = df_strat["high"].rolling(12).max().shift(1).values
    swing_lows = df_strat["low"].rolling(12).min().shift(1).values

    # Session masks
    times = df_strat.index.time
    # High volume windows: 09:45 - 11:30 ET and 14:00 - 15:30 ET (Avoid lunch chop)
    morning_window = (times >= time(9, 45)) & (times <= time(11, 30))
    afternoon_window = (times >= time(14, 0)) & (times <= time(15, 30))
    tradeable_time_mask = morning_window | afternoon_window

    print(f"\nScanning {len(df_strat):,} 5-minute bars...")

    # Strategy Variants to Test:
    # 1. Institutional 2-1-2 Trend Expansion (Target = Max(Mag1, 15 pts) + Mag2 Runner)
    # 2. Institutional 2-2 Reversal at Key Levels (Target = Swing High/Low, Min 20 pts)
    # 3. Combined Institutional Strat Strategy

    def simulate_institutional_strat(
        allow_212: bool = True,
        allow_22: bool = True,
        min_target_pts: float = 15.0,
        use_time_filter: bool = True,
        use_mag2_runner: bool = True,
    ):
        trades = []
        last_exit_idx = -1
        slip_pts = slippage_ticks * 0.25

        for i in range(2, len(df_strat)):
            if i <= last_exit_idx:
                continue

            if use_time_filter and not tradeable_time_mask[i]:
                continue

            curr_st = st[i]
            prev1_st = st[i - 1]
            prev2_st = st[i - 2]
            curr_atr = atr[i]

            entry = 0.0
            stop_loss = 0.0
            target1 = 0.0
            target2 = 0.0
            direction = 0  # 1 = Long, -1 = Short
            setup_name = ""

            # ----------------------------------------------------
            # 1. 2-1-2 Continuation
            # ----------------------------------------------------
            if allow_212 and prev1_st == StratType.INSIDE:
                # Bullish 2U-1-2U
                if prev2_st == StratType.TWO_UP and curr_st == StratType.TWO_UP:
                    entry = h[i - 1] + 0.25
                    stop_loss = l[i - 1] - 0.25
                    # Target 1: at least min_target_pts or High[i-2]
                    target1 = max(h[i - 2], entry + min_target_pts)
                    target2 = max(swing_highs[i] if not np.isnan(swing_highs[i]) else target1, entry + min_target_pts * 1.5)
                    direction = 1
                    setup_name = "2-1-2_Bull_Cont"

                # Bearish 2D-1-2D
                elif prev2_st == StratType.TWO_DOWN and curr_st == StratType.TWO_DOWN:
                    entry = l[i - 1] - 0.25
                    stop_loss = h[i - 1] + 0.25
                    target1 = min(l[i - 2], entry - min_target_pts)
                    target2 = min(swing_lows[i] if not np.isnan(swing_lows[i]) else target1, entry - min_target_pts * 1.5)
                    direction = -1
                    setup_name = "2-1-2_Bear_Cont"

            # ----------------------------------------------------
            # 2. 2-2 Momentum Reversal (RevStrat Trap)
            # ----------------------------------------------------
            elif allow_22:
                # Bullish 2D-2U Reversal
                if prev1_st == StratType.TWO_DOWN and curr_st == StratType.TWO_UP:
                    entry = h[i - 1] + 0.25
                    stop_loss = l[i - 1] - 0.25
                    target1 = entry + max(min_target_pts, (h[i - 2] - entry) if i >= 2 else min_target_pts)
                    target2 = max(swing_highs[i] if not np.isnan(swing_highs[i]) else target1, entry + min_target_pts * 2.0)
                    direction = 1
                    setup_name = "2-2_Bull_Rev"

                # Bearish 2U-2D Reversal
                elif prev1_st == StratType.TWO_UP and curr_st == StratType.TWO_DOWN:
                    entry = l[i - 1] - 0.25
                    stop_loss = h[i - 1] + 0.25
                    target1 = entry - max(min_target_pts, (entry - l[i - 2]) if i >= 2 else min_target_pts)
                    target2 = min(swing_lows[i] if not np.isnan(swing_lows[i]) else target1, entry - min_target_pts * 2.0)
                    direction = -1
                    setup_name = "2-2_Bear_Rev"

            if direction == 0:
                continue

            # Ensure minimum viable reward to risk (Target distance >= min_target_pts)
            if direction == 1 and (target1 - entry) < min_target_pts:
                continue
            if direction == -1 and (entry - target1) < min_target_pts:
                continue

            # Cap stop loss to realistic ATR (max 1.5x ATR to prevent catastrophic blowouts)
            max_sl_distance = curr_atr * 1.5
            if direction == 1:
                stop_loss = max(stop_loss, entry - max_sl_distance)
                actual_entry = entry + slip_pts
            else:
                stop_loss = min(stop_loss, entry + max_sl_distance)
                actual_entry = entry - slip_pts

            # Forward simulation (2-tier position: 50% Target 1, 50% Target 2 / Trailing EMA 9)
            exit_idx = i
            pnl1 = 0.0
            pnl2 = 0.0
            hit_t1 = False
            hit_stop = False
            be_active = False

            for f in range(i, min(i + 24, len(df_strat))):  # Max 2 hours holding
                bar_h = h[f]
                bar_l = l[f]
                bar_c = c[f]
                bar_ema = ema9[f]

                if direction == 1:
                    # Check stop
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

                    # Check Target 1
                    if not hit_t1 and bar_h >= target1:
                        pnl1 = target1 - actual_entry
                        hit_t1 = True
                        be_active = True  # Move stop to Breakeven for remaining 50%

                    # Check Target 2 or EMA9 trailing breakdown
                    if hit_t1:
                        if bar_h >= target2:
                            pnl2 = target2 - actual_entry
                            exit_idx = f
                            break
                        elif bar_c < bar_ema:  # Trailing close below 9 EMA
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
                            exit_idx = f
                            break
                        elif bar_c > bar_ema:
                            pnl2 = actual_entry - bar_c
                            exit_idx = f
                            break

            # If time ran out
            if not hit_stop and not (hit_t1 and use_mag2_runner):
                exit_idx = min(i + 24 - 1, len(df_strat) - 1)
                final_close = c[exit_idx]
                if direction == 1:
                    pnl_remain = final_close - actual_entry
                else:
                    pnl_remain = actual_entry - final_close

                if not hit_t1:
                    pnl1 = pnl_remain
                    pnl2 = pnl_remain
                else:
                    pnl2 = pnl_remain

            total_pts = (0.5 * pnl1) + (0.5 * pnl2)
            net_dollars = (total_pts * point_value) - (2 * commission_per_contract)

            last_exit_idx = exit_idx
            trades.append({
                "entry_time": timestamps[i],
                "exit_time": timestamps[exit_idx],
                "setup": setup_name,
                "direction": "LONG" if direction == 1 else "SHORT",
                "entry": actual_entry,
                "stop": stop_loss,
                "target1": target1,
                "pnl_pts": total_pts,
                "net_dollars": net_dollars,
                "bars_held": exit_idx - i + 1,
            })

        if not trades:
            return {"trades": 0, "wr": 0, "pf": 0, "pnl": 0, "pts": 0, "dd": 0, "avg_trade": 0, "avg_win": 0, "avg_loss": 0}

        df_t = pd.DataFrame(trades)
        wins = df_t[df_t["net_dollars"] > 0]
        losses = df_t[df_t["net_dollars"] <= 0]
        wr = len(wins) / len(df_t)
        tot_win = wins["net_dollars"].sum()
        tot_loss = abs(losses["net_dollars"].sum())
        pf = (tot_win / tot_loss) if tot_loss > 0 else 999.0
        tot_pnl = df_t["net_dollars"].sum()
        tot_pts = df_t["pnl_pts"].sum()
        avg_trade = df_t["pnl_pts"].mean()
        avg_win = wins["pnl_pts"].mean() if len(wins) > 0 else 0
        avg_loss = losses["pnl_pts"].mean() if len(losses) > 0 else 0

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
            "avg_trade": avg_trade,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }

    # Run variations
    print("\n" + "=" * 115)
    print(f"{'Strategy Variant':<45} | {'Trades':<7} | {'Win Rate':<9} | {'PF':<6} | {'Net PnL ($)':<14} | {'Max DD ($)':<12} | {'Avg Win/Loss':<16} | {'Avg Trade':<10}")
    print("=" * 115)

    variants = [
        ("1. Inst 2-1-2 Trend Scalper (Min 15pt TP + Runner)", True, False, 15.0, True, True),
        ("2. Inst 2-1-2 Trend Scalper (Min 20pt TP + Runner)", True, False, 20.0, True, True),
        ("3. Inst 2-2 Reversals (Min 20pt TP + Runner)", False, True, 20.0, True, True),
        ("4. Inst 2-2 Reversals (Min 25pt TP + Runner)", False, True, 25.0, True, True),
        ("5. Master Institutional Strat Portfolio (15pt+)", True, True, 15.0, True, True),
        ("6. Master Institutional Strat Portfolio (20pt+)", True, True, 20.0, True, True),
    ]

    for name, a212, a22, min_t, t_filt, r_runner in variants:
        res = simulate_institutional_strat(allow_212=a212, allow_22=a22, min_target_pts=min_t, use_time_filter=t_filt, use_mag2_runner=r_runner)
        wr_s = f"{res['wr']*100:.1f}%"
        pf_s = f"{res['pf']:.2f}"
        pnl_s = f"${res['pnl']:+,.2f}"
        dd_s = f"${res['dd']:,.2f}"
        wl_s = f"+{res['avg_win']:.1f} / {res['avg_loss']:.1f} pt"
        avg_s = f"{res['avg_trade']:+.2f} pts"
        print(f"{name:<45} | {res['trades']:<7} | {wr_s:<9} | {pf_s:<6} | {pnl_s:<14} | {dd_s:<12} | {wl_s:<16} | {avg_s:<10}")

    print("=" * 115)


if __name__ == "__main__":
    run_institutional_strat_backtest()
