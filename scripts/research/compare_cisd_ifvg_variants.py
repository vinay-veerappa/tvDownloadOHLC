"""
========================================================================================
CISD / iFVG / BPR Strategy Variants & Multi-Timeframe Comparison Suite
========================================================================================
Automates rigorous, side-by-side empirical comparison across:
1. Three Strategy Variants:
   - Baseline: 5m IFVG + CISD (ATR Stop)
   - Variant 1: [BPR or (IFVG + FVG)] @ CISD Entry (CISD Low/High Stop)
   - Variant 2: [No IFVG + 2x FVG] @ 2nd FVG Entry (CISD Low/High Stop)
2. Multiple Detection Timeframes:
   - 1-Minute, 2-Minute, 3-Minute, 4-Minute, 5-Minute
3. Multi-Asset Validation:
   - NQ (Nasdaq-100 Futures) & ES (E-mini S&P 500 Futures)
4. Trade Management Models:
   - Cover The Queen (50% @ 1.0R + BE lock + 50% @ 2.5R)
   - Fixed 1.5R, Fixed 2.0R

Usage:
    python scripts/research/compare_cisd_ifvg_variants.py --symbol NQ
    python scripts/research/compare_cisd_ifvg_variants.py --symbol ES
    python scripts/research/compare_cisd_ifvg_variants.py --all

Author: Institutional Research Suite / Antigravity
========================================================================================
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# Bootstrap root path
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.ifvg_cisd.core.cisd_variants_strategy import CISDVariantsStrategy
from scripts.research.run_strategy_filter_ablation import simulate_trade_policy


def get_dataset_path(symbol: str) -> str:
    """Finds the best available 1m dataset for the specified symbol."""
    sym = symbol.upper()
    if sym in ["NQ", "NQ1", "MNQ"]:
        if os.path.exists("data/-NQ_1m.parquet"):
            return "data/-NQ_1m.parquet"
        if os.path.exists("data/NQ1_1m.parquet"):
            return "data/NQ1_1m.parquet"
    elif sym in ["ES", "ES1", "MES"]:
        if os.path.exists("data/ES1_1m.parquet"):
            return "data/ES1_1m.parquet"
        if os.path.exists("data/ES_1m.parquet"):
            return "data/ES_1m.parquet"
    raise FileNotFoundError(f"No suitable 1m dataset found for symbol '{symbol}' in data/")


def run_comprehensive_comparison(
    symbol: str = "NQ",
    data_path: Optional[str] = None,
    timeframes: Optional[List[str]] = None,
    variants: Optional[List[str]] = None,
    policies: Optional[List[str]] = None,
    max_bars: Optional[int] = None,
) -> pd.DataFrame:
    """
    Executes an exhaustive matrix comparison across variants, timeframes, and policies.
    """
    sym = symbol.upper()
    resolved_path = data_path or get_dataset_path(sym)

    print("=" * 115)
    print(f"RUNNING CISD / iFVG / BPR MULTI-TIMEFRAME VARIANT COMPARISON: {sym}")
    print(f"Data Source: {resolved_path}")
    print("=" * 115)

    df_1m = pd.read_parquet(resolved_path)
    df_1m.columns = [c.lower() for c in df_1m.columns]
    if max_bars is not None and len(df_1m) > max_bars:
        df_1m = df_1m.tail(max_bars)

    print(f"Loaded {len(df_1m):,} bars spanning {df_1m.index[0]} to {df_1m.index[-1]}\n")

    tfs = timeframes or ["1min", "2min", "3min", "4min", "5min"]
    var_list = variants or [
        "baseline",
        "variant1_bpr_or_ifvg_fvg",
        "variant2_double_fvg_no_ifvg",
    ]
    pol_list = policies or [
        "CoverTheQueen_1.0R_2.5R",
        "FixedTarget_1.5R",
        "FixedTarget_2.0R",
    ]

    # Instrument specs
    is_es = "ES" in sym or "MES" in sym
    point_val = 12.5 if is_es else 2.0  # MES ($12.5/pt for 2 contracts = $25/pt total) / MNQ ($2/pt for 2 contracts = $4/pt total)
    full_mult = 4.0 if is_es else 10.0  # E-mini ES is $50/pt (4x MES), E-mini NQ is $20/pt (10x MNQ)
    comm = 1.05

    strat = CISDVariantsStrategy(ticker=sym)
    results: List[Dict[str, Any]] = []

    for tf in tfs:
        for var in var_list:
            t0 = time.perf_counter()
            params = {
                "resample_tf": tf,
                "variant": var,
                "max_trades_per_day": 2,
                "filter_lunch": True,
                "rth_only": True,
                "entry_style": "cisd_level" if var == "variant1_bpr_or_ifvg_fvg" else "fvg_boundary",
            }

            signals = strat.hunt(df_1m, params)
            elapsed = (time.perf_counter() - t0) * 1000

            var_label = {
                "baseline": "Baseline (IFVG+CISD)",
                "variant1_bpr_or_ifvg_fvg": "V1: BPR/(IFVG+FVG) @ CISD",
                "variant2_double_fvg_no_ifvg": "V2: 2x FVG (No IFVG) @ 2nd FVG",
            }.get(var, var)

            if signals.empty:
                for pol in pol_list:
                    results.append({
                        "Symbol": sym,
                        "Timeframe": tf,
                        "Variant": var_label,
                        "Policy": pol.replace("CoverTheQueen_1.0R_2.5R", "CoverTheQueen (1.0R/2.5R)"),
                        "Trades": 0,
                        "Win Rate %": "0.0%",
                        "Profit Factor": "0.00",
                        "Net PnL (Micro)": "$0.00",
                        "Net PnL (Full)": "$0.00",
                        "Max DD (Micro)": "$0.00",
                        "Sharpe": "0.00",
                        "Avg Trade": "$0.00",
                        "Avg Risk Pts": "0.0 pts",
                    })
                continue

            avg_risk = signals["risk_pts"].mean()

            for pol in pol_list:
                sim = simulate_trade_policy(
                    signals=signals,
                    data=df_1m,
                    policy_name=pol,
                    contracts=2,
                    point_value=point_val,
                    commission_per_contract=comm,
                    slippage_ticks=1,
                )

                micro_pnl = sim.get("total_net_pnl_usd", 0.0)
                full_pnl = micro_pnl * full_mult
                micro_dd = sim.get("max_drawdown_usd", 0.0)

                results.append({
                    "Symbol": sym,
                    "Timeframe": tf,
                    "Variant": var_label,
                    "Policy": pol.replace("CoverTheQueen_1.0R_2.5R", "CoverTheQueen (1.0R/2.5R)"),
                    "Trades": sim.get("num_trades", 0),
                    "Win Rate %": f"{sim.get('win_rate_%', 0.0):.1f}%",
                    "Profit Factor": f"{sim.get('profit_factor', 0.0):.2f}",
                    "Net PnL (Micro)": f"${micro_pnl:,.2f}",
                    "Net PnL (Full)": f"${full_pnl:,.2f}",
                    "Max DD (Micro)": f"${micro_dd:,.2f}",
                    "Sharpe": f"{sim.get('sharpe_ratio', 0.0):.2f}",
                    "Avg Trade": f"${sim.get('avg_trade_usd', 0.0):,.2f}",
                    "Avg Risk Pts": f"{avg_risk:.1f} pts",
                })

    res_df = pd.DataFrame(results)

    print("\n" + "=" * 135)
    print(f"EMPIRICAL RESULTS SUMMARY: {sym} (RTH 09:45-15:30, Lunch Filter, 2 Contracts)")
    print("=" * 135)
    print(res_df.to_string(index=False))
    print("=" * 135)

    return res_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CISD/iFVG/BPR Strategy Variants Comparison Runner")
    parser.add_argument("--symbol", type=str, default="NQ", choices=["NQ", "ES", "ALL"], help="Symbol to test")
    parser.add_argument("--tf", type=str, default=None, help="Specific timeframe (e.g. 5min, 3min, 1min) or None for all")
    parser.add_argument("--max-bars", type=int, default=None, help="Max bars to process")
    args = parser.parse_args()

    tfs = [args.tf] if args.tf else ["1min", "2min", "3min", "4min", "5min"]

    if args.symbol == "ALL":
        df_nq = run_comprehensive_comparison(symbol="NQ", timeframes=tfs, max_bars=args.max_bars)
        print("\n\n")
        df_es = run_comprehensive_comparison(symbol="ES", timeframes=tfs, max_bars=args.max_bars)
    else:
        run_comprehensive_comparison(symbol=args.symbol, timeframes=tfs, max_bars=args.max_bars)
