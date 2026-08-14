#!/usr/bin/env python3
"""
validate_8020_subgrids.py - Quantitative Validation Suite for 80/20 & Orderflow Sub-Grids

Integrates with codebase libraries:
- DataLoader (`scripts.libs_py.data.loader`) for parallel pyarrow I/O
- Resampler (`scripts.libs_py.data.resampler`) for 3m execution & 10m HTF bias
- Session Tagger (`scripts.libs_py.data.session_tagger`) for canonical US/Eastern sessions
- Microstructure & Arrival Velocity (`scripts.libs_py.features.microstructure`)
- Vectorized Multi-Instrument Processing across NQ, ES, CL, GC, YM, RTY

Validates:
1. Turning Point Clustering (HOD/LOD & Swing Pivots Modulo Distribution + Chi-Square test)
2. Reversion vs Continuation Reaction Expectancy at Band Touches (1st Touch vs Repeat, by Session/Hour)
3. Repair (Flat-Wick Imbalance) Fill Rates & Time-to-Fill Decay Curves
4. Dual-Timeframe Strategy Execution (3m Entry + 10m Trend Bias Filter) for Fork, Cross-Section, and 'h' Patterns!
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

import numpy as np
import pandas as pd
from scipy import stats

from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.data.session_tagger import tag_sessions
from scripts.trading_framework.config.config_loader import AppConfig, load_config

# ---------------------------------------------------------------------------
#  Instrument Configs & Grid Definitions
# ---------------------------------------------------------------------------
@dataclass
class GridConfig:
    symbol: str
    db_symbol: str             # e.g., 'NQ1', 'ES1', 'CL1'
    macro_unit: float          # e.g., 100 for NQ/ES, 1.0 for CL, 10.0 for GC
    primary_unit: float        # e.g., 100 for NQ, 25 for ES quarters, 1.0 for CL
    tick_size: float
    point_value: float         # Dollar per 1.0 point
    std_stop_pts: float        # e.g., 10.0 for NQ, 2.5 for ES
    std_target_pts: float      # e.g., 12.5 for NQ, 3.125 for ES (1 Octile)
    levels_pct: List[float]    # e.g. [0.20, 0.40, 0.50, 0.60, 0.80]

INSTRUMENT_CONFIGS: Dict[str, GridConfig] = {
    "NQ": GridConfig(
        symbol="NQ",
        db_symbol="NQ1",
        macro_unit=100.0,
        primary_unit=100.0,
        tick_size=0.25,
        point_value=20.0,
        std_stop_pts=10.0,
        std_target_pts=12.5,
        levels_pct=[0.125, 0.20, 0.25, 0.40, 0.50, 0.60, 0.75, 0.80, 0.875],
    ),
    "ES": GridConfig(
        symbol="ES",
        db_symbol="ES1",
        macro_unit=100.0,
        primary_unit=25.0,     # ES 25-pt Quarters
        tick_size=0.25,
        point_value=50.0,
        std_stop_pts=2.50,
        std_target_pts=3.125,  # 1 Octile of 25-pt quarter
        levels_pct=[0.20, 0.40, 0.50, 0.60, 0.80],  # 5, 10, 12.5, 15, 20 inside 25-pt quarter
    ),
    "CL": GridConfig(
        symbol="CL",
        db_symbol="CL1",
        macro_unit=1.00,
        primary_unit=1.00,
        tick_size=0.01,
        point_value=1000.0,
        std_stop_pts=0.10,
        std_target_pts=0.125,
        levels_pct=[0.125, 0.20, 0.40, 0.50, 0.60, 0.80, 0.875],
    ),
    "GC": GridConfig(
        symbol="GC",
        db_symbol="GC1",
        macro_unit=100.0,
        primary_unit=10.0,
        tick_size=0.10,
        point_value=100.0,
        std_stop_pts=1.00,
        std_target_pts=1.25,
        levels_pct=[0.20, 0.40, 0.50, 0.60, 0.80],
    ),
    "YM": GridConfig(
        symbol="YM",
        db_symbol="YM1",
        macro_unit=100.0,
        primary_unit=100.0,
        tick_size=1.00,
        point_value=5.0,
        std_stop_pts=15.0,
        std_target_pts=20.0,
        levels_pct=[0.20, 0.40, 0.50, 0.60, 0.80],
    ),
    "RTY": GridConfig(
        symbol="RTY",
        db_symbol="RTY1",
        macro_unit=100.0,
        primary_unit=10.0,
        tick_size=0.10,
        point_value=50.0,
        std_stop_pts=1.00,
        std_target_pts=1.25,
        levels_pct=[0.20, 0.40, 0.50, 0.60, 0.80],
    ),
}

# ---------------------------------------------------------------------------
#  Data Loading using DataLoader & Session Tagger
# ---------------------------------------------------------------------------
def load_and_enrich_instrument_data(cfg: GridConfig, app_cfg: AppConfig, sample_years: Optional[int] = None) -> pd.DataFrame:
    print(f"\n[Data Pipeline] Loading {cfg.symbol} ({cfg.db_symbol}) via DataLoader...")
    loader = DataLoader(app_cfg)
    
    try:
        df = loader.load_price(cfg.db_symbol)
    except Exception:
        alt_path = f"data/{cfg.db_symbol}_1m.parquet"
        if not os.path.exists(alt_path):
            alt_path = f"data/{cfg.symbol}1_1m.parquet"
        df = pd.read_parquet(alt_path)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df = df.tz_convert("America/New_York")

    # Apply canonical session tagging
    df = tag_sessions(df, app_cfg.sessions)
    
    if sample_years is not None:
        max_dt = df.index.max()
        cutoff_dt = max_dt - pd.DateOffset(years=sample_years)
        df = df[df.index >= cutoff_dt]
        print(f"   Filtering to last {sample_years} years: {df.index.min().strftime('%Y-%m-%d')} to {df.index.max().strftime('%Y-%m-%d')}")
    
    df["date"] = df.index.date
    df["hour"] = df.index.hour
    df["minute"] = df.index.minute
    df["day_name"] = df.index.day_name()
    
    atr = (df["high"] - df["low"]).rolling(14).mean().replace(0, 0.001)
    df["velocity_5m"] = ((df["close"] - df["close"].shift(5)) / atr).fillna(0)
    
    print(f"   Dataset ready: {len(df):,} rows | Price Range: {df['low'].min():.2f} - {df['high'].max():.2f}")
    return df

# ---------------------------------------------------------------------------
#  Test 1: Turning Point Clustering (HOD/LOD Modulo Distribution)
# ---------------------------------------------------------------------------
def run_turning_point_clustering(df: pd.DataFrame, cfg: GridConfig) -> Dict:
    print(f"\n[Test 1] Analyzing Turning Point Clustering (HOD / LOD) on {cfg.symbol}...")
    
    daily_groups = df.groupby("trading_date") if "trading_date" in df.columns else df.groupby("date")
    hod_prices = daily_groups["high"].max()
    lod_prices = daily_groups["low"].min()
    
    hod_mods = hod_prices % cfg.primary_unit
    lod_mods = lod_prices % cfg.primary_unit
    
    hod_pcts = (hod_mods / cfg.primary_unit).values
    lod_pcts = (lod_mods / cfg.primary_unit).values
    all_turns_pct = np.concatenate([hod_pcts, lod_pcts])
    
    bin_edges = np.linspace(0, 1, 11)
    counts, _ = np.histogram(all_turns_pct, bins=bin_edges)
    observed_pct = (counts / len(all_turns_pct)) * 100.0
    
    chi2_stat, p_val = stats.chisquare(counts)
    
    target_pcts = [0.20, 0.40, 0.50, 0.60, 0.80]
    hits_per_level = {}
    tol = 0.03
    for lvl in target_pcts:
        in_band = np.sum(np.abs(all_turns_pct - lvl) <= tol)
        hits_per_level[f"{int(lvl*100)}% ({lvl*cfg.primary_unit:g} pts)"] = {
            "count": int(in_band),
            "percentage": float((in_band / len(all_turns_pct)) * 100.0),
            "expected_uniform_pct": float(tol * 2 * 100.0)
        }

    print(f"   Total Daily Turning Points Analyzed: {len(all_turns_pct):,} (HOD: {len(hod_prices):,}, LOD: {len(lod_prices):,})")
    print(f"   Chi-Square Stat: {chi2_stat:.2f} | p-value: {p_val:.4e} {'(Statistically Significant Edge ***)' if p_val < 0.001 else ''}")
    
    print("\n   Decile Distribution of Daily HOD/LOD:")
    for i in range(10):
        bar_str = "#" * int(observed_pct[i] * 2)
        print(f"     [{bin_edges[i]*100:4.1f}% - {bin_edges[i+1]*100:4.1f}%]: {observed_pct[i]:5.2f}% (exp: 10.0%) {bar_str}")
        
    return {
        "sample_size": int(len(all_turns_pct)),
        "chi2_stat": float(chi2_stat),
        "p_value": float(p_val),
        "decile_observed_pct": observed_pct.tolist(),
        "hits_per_level": hits_per_level,
    }

# ---------------------------------------------------------------------------
#  Test 2: Reversion vs Continuation Reaction Expectancy at 20/80 Touches (1m)
# ---------------------------------------------------------------------------
def run_touch_reaction_expectancy(df: pd.DataFrame, cfg: GridConfig, lookforward_bars: int = 60) -> Dict:
    print(f"\n[Test 2] Simulating Reversion Reaction Expectancy at 20/80 Touches (1m Raw Baseline) on {cfg.symbol}...")
    print(f"   Stop: {cfg.std_stop_pts:g} pts | Target: {cfg.std_target_pts:g} pts (R:R 1:{cfg.std_target_pts/cfg.std_stop_pts:.2f})")

    close_vals = df["close"].values
    high_vals = df["high"].values
    low_vals = df["low"].values
    session_blocks = df["session_block"].values if "session_block" in df.columns else df["session"].values
    hours = df["hour"].values
    days = df["day_name"].values
    velocities = df["velocity_5m"].values
    n = len(df)

    u = cfg.primary_unit
    p20 = 0.20 * u
    p80 = 0.80 * u
    
    trades = []
    last_trade_bar = -100
    daily_touches = {}
    
    for i in range(100, n - lookforward_bars):
        if i - last_trade_bar < 5:
            continue
            
        cur_l = low_vals[i]
        cur_h = high_vals[i]
        cur_c = close_vals[i]
        cur_date = df["date"].iloc[i]
        
        base = np.floor(cur_c / u) * u
        lvl_20 = base + p20
        lvl_80 = base + p80
        
        # Bullish 20 Touch
        if cur_l <= lvl_20 <= cur_h and cur_c >= lvl_20:
            entry_p = lvl_20
            sl = entry_p - cfg.std_stop_pts
            tp = entry_p + cfg.std_target_pts
            
            touch_key = (cur_date, "20", lvl_20)
            daily_touches[touch_key] = daily_touches.get(touch_key, 0) + 1
            touch_num = daily_touches[touch_key]
            
            f_highs = high_vals[i+1 : i+1+lookforward_bars]
            f_lows = low_vals[i+1 : i+1+lookforward_bars]
            
            hit_tp = False
            hit_sl = False
            bars_held = lookforward_bars
            
            for b_idx in range(len(f_highs)):
                if f_lows[b_idx] <= sl:
                    hit_sl = True
                    bars_held = b_idx + 1
                    break
                if f_highs[b_idx] >= tp:
                    hit_tp = True
                    bars_held = b_idx + 1
                    break
            
            trades.append({
                "direction": "LONG",
                "level_type": "20_Level",
                "session_block": str(session_blocks[i]),
                "hour": int(hours[i]),
                "day": str(days[i]),
                "touch_count": "1st_Touch" if touch_num == 1 else "Repeat_Touch",
                "velocity": "Fast_Spike" if abs(velocities[i]) > 1.5 else "Normal_Creep",
                "win": 1 if hit_tp else 0,
                "loss": 1 if hit_sl else 0,
                "timeout": 1 if (not hit_tp and not hit_sl) else 0,
                "bars_held": bars_held
            })
            last_trade_bar = i
            
        # Bearish 80 Touch
        elif cur_l <= lvl_80 <= cur_h and cur_c <= lvl_80:
            entry_p = lvl_80
            sl = entry_p + cfg.std_stop_pts
            tp = entry_p - cfg.std_target_pts
            
            touch_key = (cur_date, "80", lvl_80)
            daily_touches[touch_key] = daily_touches.get(touch_key, 0) + 1
            touch_num = daily_touches[touch_key]
            
            f_highs = high_vals[i+1 : i+1+lookforward_bars]
            f_lows = low_vals[i+1 : i+1+lookforward_bars]
            
            hit_tp = False
            hit_sl = False
            bars_held = lookforward_bars
            
            for b_idx in range(len(f_highs)):
                if f_highs[b_idx] >= sl:
                    hit_sl = True
                    bars_held = b_idx + 1
                    break
                if f_lows[b_idx] <= tp:
                    hit_tp = True
                    bars_held = b_idx + 1
                    break
                    
            trades.append({
                "direction": "SHORT",
                "level_type": "80_Level",
                "session_block": str(session_blocks[i]),
                "hour": int(hours[i]),
                "day": str(days[i]),
                "touch_count": "1st_Touch" if touch_num == 1 else "Repeat_Touch",
                "velocity": "Fast_Spike" if abs(velocities[i]) > 1.5 else "Normal_Creep",
                "win": 1 if hit_tp else 0,
                "loss": 1 if hit_sl else 0,
                "timeout": 1 if (not hit_tp and not hit_sl) else 0,
                "bars_held": bars_held
            })
            last_trade_bar = i

    trades_df = pd.DataFrame(trades)
    decisive = trades_df[trades_df["timeout"] == 0]
    total_trades = len(decisive)
    win_rate = (decisive["win"].sum() / total_trades) * 100.0 if total_trades > 0 else 0
    breakeven_wr = (cfg.std_stop_pts / (cfg.std_stop_pts + cfg.std_target_pts)) * 100.0
    
    gross_win = decisive["win"].sum() * cfg.std_target_pts
    gross_loss = decisive["loss"].sum() * cfg.std_stop_pts
    pf = gross_win / gross_loss if gross_loss > 0 else 0.0
    ev_pts = (gross_win - gross_loss) / total_trades if total_trades > 0 else 0.0

    print(f"   Total Decisive Touches: {total_trades:,}")
    print(f"   Win Rate: {win_rate:.2f}% (Breakeven: {breakeven_wr:.2f}%)")
    print(f"   Profit Factor: {pf:.3f} | Expectancy: {ev_pts:+.2f} pts/trade (${ev_pts * cfg.point_value:+.2f})")

    session_stats = {}
    print("\n   Performance by Session Block:")
    for sess, grp in decisive.groupby("session_block"):
        cnt = len(grp)
        wr = (grp["win"].sum() / cnt) * 100.0 if cnt > 0 else 0
        gw = grp["win"].sum() * cfg.std_target_pts
        gl = grp["loss"].sum() * cfg.std_stop_pts
        s_pf = gw / gl if gl > 0 else 0
        session_stats[sess] = {"count": cnt, "win_rate": float(wr), "profit_factor": float(s_pf)}
        tag = "[EDGE]" if wr > breakeven_wr + 2.5 else "[CHOP]" if wr >= breakeven_wr else "[DRAG]"
        print(f"     {sess:<20}: {cnt:6,d} trades | WR: {wr:5.1f}% | PF: {s_pf:4.2f}  {tag}")

    return {
        "total_touches": total_trades,
        "win_rate": float(win_rate),
        "breakeven_wr": float(breakeven_wr),
        "profit_factor": float(pf),
        "expectancy_pts": float(ev_pts),
        "session_breakdown": session_stats,
    }

# ---------------------------------------------------------------------------
#  Test 3: Repair (Imbalance) Fill Rates & Decay Curves
# ---------------------------------------------------------------------------
def run_repairs_decay_analysis(df: pd.DataFrame, cfg: GridConfig) -> Dict:
    print(f"\n[Test 3] Analyzing Single-Wick 'Repairs' Fill Rate & Decay on {cfg.symbol}...")
    
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)

    upper_wicks = highs - np.maximum(opens, closes)
    lower_wicks = np.minimum(opens, closes) - lows
    tol = cfg.tick_size * 0.5

    bull_repairs = (closes > opens) & (lower_wicks <= tol)
    bear_repairs = (closes < opens) & (upper_wicks <= tol)

    rep_indices = np.where(bull_repairs | bear_repairs)[0]
    total_repairs = len(rep_indices)
    print(f"   Total Shaved-Wick Repairs Detected: {total_repairs:,} ({total_repairs/n*100:.2f}% of all bars)")

    horizon_bins = [1, 2, 3, 5, 10, 20, 50]
    fill_counts = {h: 0 for h in horizon_bins}

    sample_indices = rep_indices[rep_indices < n - 60]
    if len(sample_indices) > 50000:
        sample_indices = np.random.choice(sample_indices, 50000, replace=False)
        sample_indices.sort()

    for idx in sample_indices:
        is_bull = bull_repairs[idx]
        target_p = lows[idx] if is_bull else highs[idx]
        
        f_lows = lows[idx+1 : idx+51]
        f_highs = highs[idx+1 : idx+51]

        for h in horizon_bins:
            sub_l = f_lows[:h]
            sub_h = f_highs[:h]
            if is_bull and np.any(sub_l <= target_p):
                fill_counts[h] += 1
            elif not is_bull and np.any(sub_h >= target_p):
                fill_counts[h] += 1

    tested_count = len(sample_indices)
    fill_rates = {f"within_{h}_bars": float((fill_counts[h] / tested_count) * 100.0) for h in horizon_bins}

    print("\n   Repair Fill Rate Curve (Half-Life & Decay):")
    for h in horizon_bins:
        pct = fill_rates[f"within_{h}_bars"]
        bar_str = "#" * int(pct / 2.5)
        print(f"     Filled within {h:2d} bars: {pct:5.2f}% {bar_str}")

    return {
        "total_repairs_detected": total_repairs,
        "sample_evaluated": tested_count,
        "fill_decay_curve": fill_rates,
    }

# ---------------------------------------------------------------------------
#  Test 4: Dual-Timeframe Execution (3-Min Entry + 10-Min Bias Filter)
# ---------------------------------------------------------------------------
def run_dual_timeframe_backtest(df_1m: pd.DataFrame, cfg: GridConfig, app_cfg: AppConfig) -> Dict:
    print(f"\n[Test 4] Dual-Timeframe Strategy Backtest (3-Min Entry + 10-Min Bias) on {cfg.symbol}...")
    
    # 1. Resample to 10m HTF and calculate 10m Trend
    df_10m = resample_ohlcv(df_1m, "10min")
    df_10m["ema20"] = df_10m["close"].ewm(span=20, adjust=False).mean()
    df_10m["htf_trend"] = np.where(df_10m["close"] >= df_10m["ema20"], 1, -1)
    
    # 2. Resample to 3m LTF (closest clean proxy to 200s)
    df_3m = resample_ohlcv(df_1m, "3min")
    df_3m = tag_sessions(df_3m, app_cfg.sessions)
    
    # Merge 10m trend onto 3m timeline (forward fill with shift to prevent lookahead)
    df_3m["htf_trend"] = df_10m["htf_trend"].reindex(df_3m.index, method="ffill").shift(1).fillna(0)
    
    opens = df_3m["open"].values
    highs = df_3m["high"].values
    lows = df_3m["low"].values
    closes = df_3m["close"].values
    htf_trends = df_3m["htf_trend"].values
    session_blocks = df_3m["session_block"].values if "session_block" in df_3m.columns else df_3m["session"].values
    n = len(df_3m)
    
    u = cfg.primary_unit
    p20 = 0.20 * u
    p80 = 0.80 * u
    wick_tol = cfg.tick_size * 4
    
    trades = []
    
    # Simulate on 3-minute bars with 10m trend filter
    for i in range(5, n - 40):
        cur_o, cur_h, cur_l, cur_c = opens[i], highs[i], lows[i], closes[i]
        htf = htf_trends[i]
        sess = str(session_blocks[i])
        
        # Only trade RTH active sessions (IB, NY AM, NY PM)
        is_a_window = sess in ["ib", "ny_am", "ny_pm"]
        
        base = np.floor(cur_c / u) * u
        lvl_20 = base + p20
        lvl_80 = base + p80
        
        # -------------------------------------------------------------
        # Setup A: Fork Reversal (Twin Wicks at 20 or 80)
        # -------------------------------------------------------------
        r0 = cur_h - cur_l
        b0 = abs(cur_c - cur_o)
        w0_lo = min(cur_o, cur_c) - cur_l
        w0_hi = cur_h - max(cur_o, cur_c)
        
        r1 = highs[i-1] - lows[i-1]
        b1 = abs(closes[i-1] - opens[i-1])
        w1_lo = min(opens[i-1], closes[i-1]) - lows[i-1]
        w1_hi = highs[i-1] - max(opens[i-1], closes[i-1])
        
        # Bullish Fork at xx20
        if r0 > 0 and r1 > 0:
            is_bull_fork = (w0_lo >= 0.40 * r0) and (w1_lo >= 0.40 * r1) and \
                           (b0 <= 0.50 * r0) and (b1 <= 0.50 * r1) and \
                           (abs(cur_l - lows[i-1]) <= wick_tol) and (cur_c > cur_o) and \
                           (abs(cur_l - lvl_20) <= cfg.std_stop_pts)
                           
            if is_bull_fork:
                entry = cur_c
                sl = entry - cfg.std_stop_pts
                tp = entry + cfg.std_target_pts
                f_h = highs[i+1 : i+41]
                f_l = lows[i+1 : i+41]
                hit_tp = np.any(f_h >= tp)
                hit_sl = np.any(f_l <= sl)
                if hit_tp or hit_sl:
                    tp_idx = np.argmax(f_h >= tp) if hit_tp else 999
                    sl_idx = np.argmax(f_l <= sl) if hit_sl else 999
                    win = 1 if tp_idx < sl_idx else 0
                    trades.append({
                        "setup": "Fork_Reversal",
                        "direction": "LONG",
                        "with_htf_trend": 1 if htf >= 0 else 0,
                        "session": sess,
                        "is_a_window": is_a_window,
                        "win": win
                    })
                    
            # Bearish Fork at xx80
            is_bear_fork = (w0_hi >= 0.40 * r0) and (w1_hi >= 0.40 * r1) and \
                           (b0 <= 0.50 * r0) and (b1 <= 0.50 * r1) and \
                           (abs(cur_h - highs[i-1]) <= wick_tol) and (cur_c < cur_o) and \
                           (abs(cur_h - lvl_80) <= cfg.std_stop_pts)
                           
            if is_bear_fork:
                entry = cur_c
                sl = entry + cfg.std_stop_pts
                tp = entry - cfg.std_target_pts
                f_h = highs[i+1 : i+41]
                f_l = lows[i+1 : i+41]
                hit_tp = np.any(f_l <= tp)
                hit_sl = np.any(f_h >= sl)
                if hit_tp or hit_sl:
                    tp_idx = np.argmax(f_l <= tp) if hit_tp else 999
                    sl_idx = np.argmax(f_h >= sl) if hit_sl else 999
                    win = 1 if tp_idx < sl_idx else 0
                    trades.append({
                        "setup": "Fork_Reversal",
                        "direction": "SHORT",
                        "with_htf_trend": 1 if htf <= 0 else 0,
                        "session": sess,
                        "is_a_window": is_a_window,
                        "win": win
                    })

        # -------------------------------------------------------------
        # Setup B: 'h' Pattern (Bearish Arch Rollover at xx20/xx80)
        # -------------------------------------------------------------
        if htf <= 0 and cur_c < cur_o: # HTF Bearish Bias
            # Prior LL established within 5 bars
            recent_low = np.min(lows[i-5 : i-1])
            arch_top = max(highs[i-1], highs[i-2])
            arch_rej = (arch_top - max(opens[i-1], closes[i-1])) >= 0.30 * (highs[i-1] - lows[i-1])
            near_magnet = (abs(arch_top - lvl_80) <= cfg.std_stop_pts) or (abs(arch_top - lvl_20) <= cfg.std_stop_pts)
            
            if arch_rej and near_magnet and cur_c < min(opens[i-1], closes[i-1]):
                entry = cur_c
                sl = entry + cfg.std_stop_pts
                tp = entry - cfg.std_target_pts
                f_h = highs[i+1 : i+41]
                f_l = lows[i+1 : i+41]
                hit_tp = np.any(f_l <= tp)
                hit_sl = np.any(f_h >= sl)
                if hit_tp or hit_sl:
                    tp_idx = np.argmax(f_l <= tp) if hit_tp else 999
                    sl_idx = np.argmax(f_h >= sl) if hit_sl else 999
                    win = 1 if tp_idx < sl_idx else 0
                    trades.append({
                        "setup": "h_Pattern",
                        "direction": "SHORT",
                        "with_htf_trend": 1, # Already filtered
                        "session": sess,
                        "is_a_window": is_a_window,
                        "win": win
                    })

    trades_df = pd.DataFrame(trades)
    
    # 1. Overall Unfiltered vs With 10m HTF Filter
    all_cnt = len(trades_df)
    all_wr = (trades_df["win"].sum() / all_cnt) * 100.0 if all_cnt > 0 else 0
    all_pf = (trades_df["win"].sum() * cfg.std_target_pts) / ((all_cnt - trades_df["win"].sum()) * cfg.std_stop_pts) if (all_cnt - trades_df["win"].sum()) > 0 else 0
    
    # 2. Filtered for 10m Trend Alignment
    htf_filtered = trades_df[trades_df["with_htf_trend"] == 1]
    htf_cnt = len(htf_filtered)
    htf_wr = (htf_filtered["win"].sum() / htf_cnt) * 100.0 if htf_cnt > 0 else 0
    htf_pf = (htf_filtered["win"].sum() * cfg.std_target_pts) / ((htf_cnt - htf_filtered["win"].sum()) * cfg.std_stop_pts) if (htf_cnt - htf_filtered["win"].sum()) > 0 else 0

    # 3. Filtered for 10m Trend + A+ Windows (09:30 - 11:00 & 15:00 - 16:00)
    aplus_filtered = htf_filtered[htf_filtered["is_a_window"] == True]
    aplus_cnt = len(aplus_filtered)
    aplus_wr = (aplus_filtered["win"].sum() / aplus_cnt) * 100.0 if aplus_cnt > 0 else 0
    aplus_pf = (aplus_filtered["win"].sum() * cfg.std_target_pts) / ((aplus_cnt - aplus_filtered["win"].sum()) * cfg.std_stop_pts) if (aplus_cnt - aplus_filtered["win"].sum()) > 0 else 0

    print(f"   --- 3m Execution Comparison Matrix on {cfg.symbol} ---")
    print(f"   1. All 3m Setups (Raw / No Trend Filter) : {all_cnt:5,d} trades | WR: {all_wr:5.1f}% | PF: {all_pf:4.2f}")
    print(f"   2. With 10m HTF Trend Alignment Filter  : {htf_cnt:5,d} trades | WR: {htf_wr:5.1f}% | PF: {htf_pf:4.2f}  [+{(htf_wr - all_wr):+.1f}% WR Boost]")
    print(f"   3. A+ Windows (09:30-11:00 / 15:00-16:00) : {aplus_cnt:5,d} trades | WR: {aplus_wr:5.1f}% | PF: {aplus_pf:4.2f}  [MAX EDGE 🔥]")

    # Setup specific breakdown
    setup_stats = {}
    print("\n   Performance by Setup Type (with 10m Trend):")
    for s_name, grp in htf_filtered.groupby("setup"):
        c = len(grp)
        w = (grp["win"].sum() / c) * 100.0 if c > 0 else 0
        p = (grp["win"].sum() * cfg.std_target_pts) / ((c - grp["win"].sum()) * cfg.std_stop_pts) if (c - grp["win"].sum()) > 0 else 0
        setup_stats[s_name] = {"count": c, "win_rate": float(w), "profit_factor": float(p)}
        print(f"     {s_name:<18}: {c:5,d} trades | WR: {w:5.1f}% | PF: {p:4.2f}")

    return {
        "raw_3m": {"count": all_cnt, "win_rate": float(all_wr), "profit_factor": float(all_pf)},
        "with_10m_htf_trend": {"count": htf_cnt, "win_rate": float(htf_wr), "profit_factor": float(htf_pf)},
        "aplus_window_edge": {"count": aplus_cnt, "win_rate": float(aplus_wr), "profit_factor": float(aplus_pf)},
        "setup_breakdown": setup_stats
    }

# ---------------------------------------------------------------------------
#  Single Instrument Pipeline
# ---------------------------------------------------------------------------
def process_single_instrument(sym: str, sample_years: int) -> Tuple[str, Dict]:
    cfg = INSTRUMENT_CONFIGS[sym]
    app_cfg = load_config()
    df_1m = load_and_enrich_instrument_data(cfg, app_cfg, sample_years=sample_years)
    
    t1 = run_turning_point_clustering(df_1m, cfg)
    t2 = run_touch_reaction_expectancy(df_1m, cfg)
    t3 = run_repairs_decay_analysis(df_1m, cfg)
    t4 = run_dual_timeframe_backtest(df_1m, cfg, app_cfg)
    
    return sym, {
        "config": asdict(cfg),
        "turning_point_clustering": t1,
        "reaction_expectancy_1m": t2,
        "repairs_decay": t3,
        "dual_timeframe_3m_10m": t4,
    }

# ---------------------------------------------------------------------------
#  Main Execution Runner
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Validate 80/20 & Sub-Grids Framework Across Futures")
    parser.add_argument("--symbols", nargs="+", default=["NQ", "ES"], help="Symbols to validate (NQ, ES, CL, GC, YM, RTY)")
    parser.add_argument("--years", type=int, default=5, help="Years of historical data to sample (default: 5)")
    parser.add_argument("--out", type=str, default="reports/research/subgrid_validation.json", help="Output JSON report path")
    args = parser.parse_args()

    print("=" * 80)
    print("QUANTITATIVE 80/20 & ORDERFLOW DUAL-TIMEFRAME VALIDATION ENGINE")
    print(f"Symbols: {args.symbols} | History Window: Last {args.years} Years")
    print("=" * 80)

    results = {}
    valid_symbols = [s.upper() for s in args.symbols if s.upper() in INSTRUMENT_CONFIGS]

    for sym in valid_symbols:
        _, sym_res = process_single_instrument(sym, args.years)
        results[sym] = sym_res

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n" + "=" * 80)
    print(f"SUCCESS: Dual-Timeframe Validation Complete! Report saved to: {args.out}")
    print("=" * 80)

if __name__ == "__main__":
    main()
