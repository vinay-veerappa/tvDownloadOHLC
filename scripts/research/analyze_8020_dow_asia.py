#!/usr/bin/env python3
"""
analyze_8020_dow_asia.py - Deep-Dive Temporal Breakdown for 80/20 Level Sniping:
1. Day of Week Analysis (Monday - Friday)
2. Asia Session Hour-by-Hour Breakdown (18:00 - 03:00 ET)
"""

import os
import sys
from pathlib import Path
from typing import Dict

# Ensure UTF-8 console output
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

from scripts.libs_py.data.loader import DataLoader
from scripts.libs_py.data.session_tagger import tag_sessions
from scripts.trading_framework.config.config_loader import load_config

def analyze_instrument(symbol: str, db_symbol: str, u: float, stop_pts: float, target_pts: float, pt_val: float):
    app_cfg = load_config()
    loader = DataLoader(app_cfg)
    
    print(f"\n================================================================================")
    print(f"📊 DEEP-DIVE TEMPORAL ANALYSIS: {symbol} ({db_symbol})")
    print(f"   Primary Grid: {u:g} pts | Stop: {stop_pts:g} pts | Target: {target_pts:g} pts (R:R 1:{target_pts/stop_pts:.2f})")
    print(f"================================================================================")

    try:
        df = loader.load_price(db_symbol)
    except Exception:
        df = pd.read_parquet(f"data/{db_symbol}_1m.parquet")
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df = df.tz_convert("America/New_York")

    df = tag_sessions(df, app_cfg.sessions)
    
    # Filter to last 5 years
    cutoff = df.index.max() - pd.DateOffset(years=5)
    df = df[df.index >= cutoff]
    
    df["hour"] = df.index.hour
    df["day_name"] = df.index.day_name()
    df["day_of_week"] = df.index.dayofweek # 0=Mon, 4=Fri
    df["date"] = df.index.date
    
    close_vals = df["close"].values
    high_vals = df["high"].values
    low_vals = df["low"].values
    hours = df["hour"].values
    days = df["day_name"].values
    dows = df["day_of_week"].values
    n = len(df)

    p20 = 0.20 * u
    p80 = 0.80 * u
    lookforward = 60
    
    trades = []
    last_trade_bar = -100
    
    for i in range(100, n - lookforward):
        if i - last_trade_bar < 5:
            continue
            
        cur_l, cur_h, cur_c = low_vals[i], high_vals[i], close_vals[i]
        base = np.floor(cur_c / u) * u
        lvl_20 = base + p20
        lvl_80 = base + p80
        
        # Bullish 20 Touch
        if cur_l <= lvl_20 <= cur_h and cur_c >= lvl_20:
            entry_p = lvl_20
            sl = entry_p - stop_pts
            tp = entry_p + target_pts
            
            f_highs = high_vals[i+1 : i+1+lookforward]
            f_lows = low_vals[i+1 : i+1+lookforward]
            
            hit_tp = False
            hit_sl = False
            bars_held = lookforward
            
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
                "hour": int(hours[i]),
                "day_name": str(days[i]),
                "day_of_week": int(dows[i]),
                "win": 1 if hit_tp else 0,
                "loss": 1 if hit_sl else 0,
                "timeout": 1 if (not hit_tp and not hit_sl) else 0,
                "bars_held": bars_held
            })
            last_trade_bar = i
            
        # Bearish 80 Touch
        elif cur_l <= lvl_80 <= cur_h and cur_c <= lvl_80:
            entry_p = lvl_80
            sl = entry_p + stop_pts
            tp = entry_p - target_pts
            
            f_highs = high_vals[i+1 : i+1+lookforward]
            f_lows = low_vals[i+1 : i+1+lookforward]
            
            hit_tp = False
            hit_sl = False
            bars_held = lookforward
            
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
                "hour": int(hours[i]),
                "day_name": str(days[i]),
                "day_of_week": int(dows[i]),
                "win": 1 if hit_tp else 0,
                "loss": 1 if hit_sl else 0,
                "timeout": 1 if (not hit_tp and not hit_sl) else 0,
                "bars_held": bars_held
            })
            last_trade_bar = i

    trades_df = pd.DataFrame(trades)
    decisive = trades_df[trades_df["timeout"] == 0]
    breakeven_wr = (stop_pts / (stop_pts + target_pts)) * 100.0
    
    # -------------------------------------------------------------
    # 1. Day of Week Breakdown
    # -------------------------------------------------------------
    print("\n📅 1. DAY OF WEEK PERFORMANCE BREAKDOWN:")
    print("--------------------------------------------------------------------------------")
    print(f"{'Day of Week':<12} | {'Trades':<8} | {'Win Rate':<9} | {'Profit Factor':<14} | {'Exp (pts)':<10} | {'Exp ($)':<10}")
    print("--------------------------------------------------------------------------------")
    
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for day in day_order:
        grp = decisive[decisive["day_name"] == day]
        cnt = len(grp)
        if cnt == 0:
            continue
        wr = (grp["win"].sum() / cnt) * 100.0
        gw = grp["win"].sum() * target_pts
        gl = grp["loss"].sum() * stop_pts
        pf = gw / gl if gl > 0 else 0
        ev_pts = (gw - gl) / cnt
        ev_dlr = ev_pts * pt_val
        tag = "🔥 BEST" if pf >= 1.95 else "✅ STRONG" if pf >= 1.70 else "⚖️ SOLID"
        print(f"{day:<12} | {cnt:8,d} | {wr:8.2f}% | {pf:10.3f} {tag:<4} | {ev_pts:+9.2f}p | ${ev_dlr:+8.2f}")
        
    # -------------------------------------------------------------
    # 2. Asia & Overnight Session Hour-by-Hour Breakdown
    # -------------------------------------------------------------
    print("\n🌏 2. ASIA & OVERNIGHT SESSION HOUR-BY-HOUR BREAKDOWN (ET):")
    print("--------------------------------------------------------------------------------")
    print(f"{'Hour (ET)':<14} | {'Market Context':<24} | {'Trades':<8} | {'Win Rate':<9} | {'PF':<7} | {'Avg Held':<9}")
    print("--------------------------------------------------------------------------------")
    
    asia_hours = [
        (18, "Globex Re-Open / Sydney"),
        (19, "Tokyo Equities Open"),
        (20, "Tokyo / Seoul Active"),
        (21, "Hong Kong / Shanghai Open"),
        (22, "Asian Peak Flow"),
        (23, "Pre-Midnight Drift"),
        (0,  "Midnight Open (Algo Pivot)"),
        (1,  "Late Asia / Europe Prep"),
        (2,  "Pre-London Frankfurt Open"),
    ]
    
    for hr, ctx in asia_hours:
        grp = decisive[decisive["hour"] == hr]
        cnt = len(grp)
        if cnt == 0:
            continue
        wr = (grp["win"].sum() / cnt) * 100.0
        gw = grp["win"].sum() * target_pts
        gl = grp["loss"].sum() * stop_pts
        pf = gw / gl if gl > 0 else 0
        avg_bars = grp["bars_held"].mean()
        
        tag = "🔥 PRIME" if pf >= 1.75 else "✅ CLEAN" if pf >= 1.60 else "⚠️ SLOW"
        print(f"{hr:02d}:00 - {hr:02d}:59 ET | {ctx:<24} | {cnt:8,d} | {wr:8.2f}% | {pf:6.2f} | {avg_bars:5.1f} mins {tag}")

def main():
    analyze_instrument("NQ", "NQ1", u=100.0, stop_pts=10.0, target_pts=12.5, pt_val=20.0)
    analyze_instrument("ES", "ES1", u=25.0, stop_pts=2.5, target_pts=3.125, pt_val=50.0)

if __name__ == "__main__":
    main()
