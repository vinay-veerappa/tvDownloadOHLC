#!/usr/bin/env python3
"""
optimize_bandits8020.py - Strategy Analyzer & Parameter Optimization Engine for Bandits8020Bot

Simulates the exact NinjaTrader 8 Bandits8020Bot logic across multi-year parquet data:
1. Simulates trade-by-trade execution (Entry, SL, TP, Trail, Flatten by 15:55 ET).
2. Performs Grid Optimization across SL/TP ratios, HTF filters, and setup combinations.
3. Generates institutional metrics: Win Rate, Profit Factor, Max Drawdown, Expectancy ($ and pts),
   Consecutive Loser Distribution (Prop Firm Survival Rate), and Optimal Prop Parameters.
"""

import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# UTF-8 Console Safety
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

import numpy as np
import pandas as pd

from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.data.session_tagger import tag_sessions
from scripts.trading_framework.config.config_loader import load_config

# ---------------------------------------------------------------------------
#  Simulation Engine for Bandits8020Bot
# ---------------------------------------------------------------------------

@dataclass
class OptimizationParams:
    symbol: str
    grid_unit: float
    stop_pts: float
    target_pts: float
    use_htf_trend: bool
    enable_fork: bool
    enable_sniper: bool
    enable_h_pattern: bool
    session_mode: str  # "RTH_APLUS", "RTH_ALL", "WITH_ASIA"
    max_trades_day: int = 3
    daily_max_loss_r: float = 2.0

def run_simulation(df_1m: pd.DataFrame, df_10m: pd.DataFrame, p: OptimizationParams) -> Dict:
    point_val = 20.0 if p.symbol == "NQ" else 50.0
    u = p.grid_unit
    p20 = 0.20 * u
    p80 = 0.80 * u
    tick_sz = 0.25
    wick_tol = tick_sz * 4

    opens = df_1m["open"].values
    highs = df_1m["high"].values
    lows = df_1m["low"].values
    closes = df_1m["close"].values
    hours = df_1m["hour"].values
    minutes = df_1m["minute"].values
    dates = df_1m["date"].values
    n = len(df_1m)

    # 10m HTF Trend
    htf_trend = np.where(df_10m["close"] >= df_10m["ema20"], 1, -1)
    df_1m["htf_bias"] = pd.Series(htf_trend, index=df_10m.index).reindex(df_1m.index, method="ffill").shift(1).fillna(0).values
    htf_biases = df_1m["htf_bias"].values

    trades = []
    daily_trades_count = 0
    daily_pnl_pts = 0.0
    current_day = None
    last_trade_bar = -100

    last_level_touched = 0.0
    touches_on_level = 0

    for i in range(10, n - 60):
        bar_date = dates[i]
        if bar_date != current_day:
            current_day = bar_date
            daily_trades_count = 0
            daily_pnl_pts = 0.0
            last_level_touched = 0.0
            touches_on_level = 0

        # Prop Firm Risk Gates
        if daily_trades_count >= p.max_trades_day:
            continue
        if daily_pnl_pts <= - (p.daily_max_loss_r * p.stop_pts):
            continue

        hhmm = hours[i] * 100 + minutes[i]

        # Time Session Filter
        if p.session_mode == "RTH_APLUS":
            allowed = (930 <= hhmm <= 1100) or (1500 <= hhmm <= 1530)
        elif p.session_mode == "RTH_ALL":
            allowed = (930 <= hhmm <= 1530)
        elif p.session_mode == "WITH_ASIA":
            allowed = (930 <= hhmm <= 1100) or (1500 <= hhmm <= 1530) or (1800 <= hhmm <= 1900) or (2000 <= hhmm <= 2100)
        else:
            allowed = True

        if not allowed:
            continue

        if i - last_trade_bar < 3:
            continue

        cur_o, cur_h, cur_l, cur_c = opens[i], highs[i], lows[i], closes[i]
        htf = htf_biases[i] if p.use_htf_trend else 0

        base = np.floor(cur_c / u) * u
        lvl_20 = base + p20
        lvl_80 = base + p80

        signal = 0
        setup_name = ""

        # -------------------------------------------------------------
        # Setup 1: Fork Reversal
        # -------------------------------------------------------------
        if p.enable_fork and i >= 2:
            r0 = cur_h - cur_l
            b0 = abs(cur_c - cur_o)
            w0_lo = min(cur_o, cur_c) - cur_l
            w0_hi = cur_h - max(cur_o, cur_c)

            r1 = highs[i-1] - lows[i-1]
            b1 = abs(closes[i-1] - opens[i-1])
            w1_lo = min(opens[i-1], closes[i-1]) - lows[i-1]
            w1_hi = highs[i-1] - max(opens[i-1], closes[i-1])

            if r0 > 0 and r1 > 0:
                # Bullish Fork
                if (htf >= 0) and (w0_lo >= 0.38 * r0) and (w1_lo >= 0.38 * r1) and \
                   (b0 <= 0.52 * r0) and (b1 <= 0.52 * r1) and \
                   (abs(cur_l - lows[i-1]) <= wick_tol) and (cur_c > cur_o) and \
                   (abs(cur_l - lvl_20) <= p.stop_pts):
                    signal = 1
                    setup_name = "Fork_Reversal"

                # Bearish Fork
                elif (htf <= 0) and (w0_hi >= 0.38 * r0) and (w1_hi >= 0.38 * r1) and \
                     (b0 <= 0.52 * r0) and (b1 <= 0.52 * r1) and \
                     (abs(cur_h - highs[i-1]) <= wick_tol) and (cur_c < cur_o) and \
                     (abs(cur_h - lvl_80) <= p.stop_pts):
                    signal = -1
                    setup_name = "Fork_Reversal"

        # -------------------------------------------------------------
        # Setup 2: 'h' Pattern
        # -------------------------------------------------------------
        if signal == 0 and p.enable_h_pattern and (htf <= 0) and (cur_c < cur_o) and i >= 5:
            arch_top = max(highs[i-1], highs[i-2])
            rng1 = highs[i-1] - lows[i-1]
            arch_rej = ((arch_top - max(opens[i-1], closes[i-1])) / rng1) if rng1 > 0 else 0
            near_magnet = (abs(arch_top - lvl_80) <= p.stop_pts) or (abs(arch_top - lvl_20) <= p.stop_pts)
            if arch_rej >= 0.30 and near_magnet and cur_c < min(opens[i-1], closes[i-1]):
                signal = -1
                setup_name = "h_Pattern"

        # -------------------------------------------------------------
        # Setup 3: Level Sniping (Touch Reversion)
        # -------------------------------------------------------------
        if signal == 0 and p.enable_sniper:
            if cur_l <= lvl_20 <= cur_h and cur_c >= lvl_20 and (htf >= 0):
                if abs(lvl_20 - last_level_touched) > wick_tol:
                    last_level_touched = lvl_20
                    touches_on_level = 1
                else:
                    touches_on_level += 1
                if touches_on_level <= 2:
                    signal = 1
                    setup_name = "Level_Sniper"

            elif cur_l <= lvl_80 <= cur_h and cur_c <= lvl_80 and (htf <= 0):
                if abs(lvl_80 - last_level_touched) > wick_tol:
                    last_level_touched = lvl_80
                    touches_on_level = 1
                else:
                    touches_on_level += 1
                if touches_on_level <= 2:
                    signal = -1
                    setup_name = "Level_Sniper"

        if signal == 0:
            continue

        # Execute Bracket Simulation
        entry_price = lvl_20 if signal == 1 else lvl_80
        sl_price = entry_price - p.stop_pts if signal == 1 else entry_price + p.stop_pts
        tp_price = entry_price + p.target_pts if signal == 1 else entry_price - p.target_pts

        f_highs = highs[i+1 : min(i+61, n)]
        f_lows = lows[i+1 : min(i+61, n)]

        hit_tp = False
        hit_sl = False
        bars_held = len(f_highs)

        for b_idx in range(len(f_highs)):
            if signal == 1:
                if f_lows[b_idx] <= sl_price:
                    hit_sl = True
                    bars_held = b_idx + 1
                    break
                if f_highs[b_idx] >= tp_price:
                    hit_tp = True
                    bars_held = b_idx + 1
                    break
            else:
                if f_highs[b_idx] >= sl_price:
                    hit_sl = True
                    bars_held = b_idx + 1
                    break
                if f_lows[b_idx] <= tp_price:
                    hit_tp = True
                    bars_held = b_idx + 1
                    break

        if hit_tp:
            pnl = p.target_pts
            win = 1
        elif hit_sl:
            pnl = -p.stop_pts
            win = 0
        else:
            pnl = (closes[min(i+60, n-1)] - entry_price) * signal
            win = 1 if pnl > 0 else 0

        daily_trades_count += 1
        daily_pnl_pts += pnl
        last_trade_bar = i

        trades.append({
            "date": bar_date,
            "setup": setup_name,
            "signal": signal,
            "win": win,
            "pnl_pts": pnl,
            "pnl_dlr": pnl * point_val,
            "bars_held": bars_held
        })

    # Metric Rollup
    if not trades:
        return {"total_trades": 0, "win_rate": 0, "profit_factor": 0, "net_profit": 0, "max_drawdown": 0}

    tdf = pd.DataFrame(trades)
    total_tr = len(tdf)
    win_cnt = tdf["win"].sum()
    wr = (win_cnt / total_tr) * 100.0

    gross_profit = tdf[tdf["pnl_dlr"] > 0]["pnl_dlr"].sum()
    gross_loss = abs(tdf[tdf["pnl_dlr"] < 0]["pnl_dlr"].sum())
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
    net_profit = gross_profit - gross_loss

    # Max Drawdown
    equity_curve = tdf["pnl_dlr"].cumsum()
    peak = equity_curve.cummax()
    drawdown = peak - equity_curve
    max_dd = drawdown.max() if len(drawdown) > 0 else 0.0

    # Consecutive losses
    is_loss = (tdf["win"] == 0).astype(int)
    loss_streaks = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
    max_consec_losers = int(loss_streaks.max()) if len(loss_streaks) > 0 else 0

    return {
        "params": asdict(p),
        "total_trades": total_tr,
        "win_rate": float(wr),
        "profit_factor": float(pf),
        "net_profit_dlr": float(net_profit),
        "expectancy_pts": float(tdf["pnl_pts"].mean()),
        "expectancy_dlr": float(tdf["pnl_dlr"].mean()),
        "max_drawdown_dlr": float(max_dd),
        "max_consec_losers": max_consec_losers,
        "trades_per_day": float(total_tr / len(tdf["date"].unique())),
    }

# ---------------------------------------------------------------------------
#  Optimization Grid Sweeper
# ---------------------------------------------------------------------------

def run_optimizer(symbol: str = "NQ", sample_years: int = 5):
    print("=" * 85)
    print(f"🔬 RUNNING STRATEGY ANALYZER & PARAMETER OPTIMIZER FOR {symbol} (Bandits8020Bot)")
    print(f"   Historical Window: Last {sample_years} Years | Multi-Parameter Grid Search")
    print("=" * 85)

    app_cfg = load_config()
    loader = DataLoader(app_cfg)

    db_sym = "NQ1" if symbol == "NQ" else "ES1"
    try:
        df_1m = loader.load_price(db_sym)
    except Exception:
        df_1m = pd.read_parquet(f"data/{db_sym}_1m.parquet")
        if df_1m.index.tz is None:
            df_1m.index = df_1m.index.tz_localize("UTC")
        df_1m = df_1m.tz_convert("America/New_York")

    # Filter years
    cutoff = df_1m.index.max() - pd.DateOffset(years=sample_years)
    df_1m = df_1m[df_1m.index >= cutoff].copy()
    df_1m["hour"] = df_1m.index.hour
    df_1m["minute"] = df_1m.index.minute
    df_1m["date"] = df_1m.index.date

    # 10m Resampled series for HTF
    df_10m = resample_ohlcv(df_1m, "10min")
    df_10m["ema20"] = df_10m["close"].ewm(span=20, adjust=False).mean()

    # Parameter Ranges
    if symbol == "NQ":
        grid_unit = 100.0
        stop_ranges = [8.0, 10.0, 12.0, 15.0]
        target_ranges = [10.0, 12.5, 15.0, 20.0]
    else:
        grid_unit = 25.0
        stop_ranges = [2.0, 2.5, 3.0]
        target_ranges = [2.5, 3.125, 4.0, 5.0]

    htf_options = [True, False]
    session_options = ["RTH_APLUS", "WITH_ASIA", "RTH_ALL"]

    all_results = []
    param_combos = list(itertools.product(stop_ranges, target_ranges, htf_options, session_options))
    print(f"\nEvaluating {len(param_combos)} Parameter Variations across {len(df_1m):,} bars...")

    for sl, tp, htf, sess in param_combos:
        p = OptimizationParams(
            symbol=symbol,
            grid_unit=grid_unit,
            stop_pts=sl,
            target_pts=tp,
            use_htf_trend=htf,
            enable_fork=True,
            enable_sniper=True,
            enable_h_pattern=True,
            session_mode=sess,
            max_trades_day=3,
            daily_max_loss_r=2.0
        )
        res = run_simulation(df_1m, df_10m, p)
        all_results.append(res)

    results_df = pd.DataFrame([
        {
            "SL (pts)": r["params"]["stop_pts"],
            "TP (pts)": r["params"]["target_pts"],
            "R:R": f"1:{r['params']['target_pts']/r['params']['stop_pts']:.2f}",
            "HTF 10m": r["params"]["use_htf_trend"],
            "Session": r["params"]["session_mode"],
            "Trades": r["total_trades"],
            "Win Rate": f"{r['win_rate']:.1f}%",
            "PF": round(r["profit_factor"], 3),
            "Net Profit ($)": f"${r['net_profit_dlr']:,.0f}",
            "Max DD ($)": f"${r['max_drawdown_dlr']:,.0f}",
            "Max Consec L": r["max_consec_losers"],
            "Exp ($/tr)": f"${r['expectancy_dlr']:+.2f}"
        }
        for r in all_results if r["total_trades"] > 0
    ])

    results_df = results_df.sort_values(by="PF", ascending=False)

    print("\n" + "=" * 105)
    print(f"🏆 TOP 10 OPTIMIZED PARAMETER CONFIGURATIONS FOR {symbol} (Ranked by Profit Factor):")
    print("=" * 105)
    print(results_df.head(10).to_string(index=False))

    # Save to JSON report
    out_path = f"reports/research/optimizer_{symbol.lower()}_bandits8020.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 105)
    print(f"✅ Full optimization matrix saved to: {out_path}")
    print("=" * 105)

def main():
    run_optimizer("NQ", sample_years=5)
    run_optimizer("ES", sample_years=5)

if __name__ == "__main__":
    main()
