"""
High-Performance Backtest Runner for IFVG + CISD with Volume Imbalance (VI) Merger.
===================================================================================
Evaluates:
1. Timeframes: 5-Minute vs 15-Minute HTF
2. Modes: Strict IFVG Only vs IFVG + FVG Combined
3. Volume Imbalance: With VI Merger vs Without VI Merger
4. Risk Policies: Cover The Queen (1.0R/2.5R), Fixed 1.5R, Fixed 2.0R, BE Trail
"""
from __future__ import annotations

import argparse
import sys
from datetime import time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd

_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy
from scripts.research.run_strategy_filter_ablation import simulate_trade_policy


def run_full_backtest_suite(data_path: str = "data/-NQ_1m.parquet"):
    print("=" * 105)
    print(f"RUNNING INSTITUTIONAL IFVG + CISD + VI BACKTEST ON {data_path}")
    print("=" * 105)

    df_1m = pd.read_parquet(data_path)
    # Ensure lowercase standard columns
    df_1m.columns = [c.lower() for c in df_1m.columns]
    print(f"Dataset Loaded: {len(df_1m):,} bars spanning {df_1m.index[0]} to {df_1m.index[-1]}\n")

    strat = IFVGCISDStrategy(ticker="NQ")

    configurations = [
        # 1. 5m Configurations
        {"name": "5m Strict IFVG (No VI)", "tf": "5min", "strict": True, "vi": False},
        {"name": "5m Strict IFVG + VI", "tf": "5min", "strict": True, "vi": True},
        {"name": "5m IFVG + FVG (No VI)", "tf": "5min", "strict": False, "vi": False},
        {"name": "5m IFVG + FVG + VI", "tf": "5min", "strict": False, "vi": True},
        
        # 2. 15m Configurations
        {"name": "15m Strict IFVG (No VI)", "tf": "15min", "strict": True, "vi": False},
        {"name": "15m Strict IFVG + VI", "tf": "15min", "strict": True, "vi": True},
        {"name": "15m IFVG + FVG (No VI)", "tf": "15min", "strict": False, "vi": False},
        {"name": "15m IFVG + FVG + VI", "tf": "15min", "strict": False, "vi": True},
    ]

    policies = [
        "CoverTheQueen_1.0R_2.5R",
        "BaseHits_FixedPoints",
        "FixedTarget_1.5R",
        "FixedTarget_2.0R",
        "BreakevenTrail",
    ]

    results: List[Dict[str, Any]] = []

    for cfg in configurations:
        params = {
            "resample_tf": cfg["tf"],
            "strict_ifvg_only": cfg["strict"],
            "include_vi": cfg["vi"],
            "max_trades_per_day": 1,
            "filter_lunch": True,
            "atr_risk_mult": 2.0,
        }
        
        signals = strat.hunt(df_1m, params)

        for pol in policies:
            sim = simulate_trade_policy(
                signals=signals,
                data=df_1m,
                policy_name=pol,
                contracts=2,
                point_value=2.0, # MNQ ($2/pt per contract, 2 contracts = $4/pt total)
                commission_per_contract=1.05,
                slippage_ticks=1,
            )

            # E-mini NQ calculation ($20/pt per contract)
            nq_pnl = sim.get("total_net_pnl_usd", 0.0) * 10.0
            nq_dd = sim.get("max_drawdown_usd", 0.0) * 10.0

            results.append({
                "Configuration": cfg["name"],
                "Policy": pol.replace("CoverTheQueen_1.0R_2.5R", "CoverTheQueen (1.0R/2.5R)"),
                "Trades": sim.get("num_trades", 0),
                "Win Rate %": f"{sim.get('win_rate_%', 0.0):.1f}%",
                "Profit Factor": f"{sim.get('profit_factor', 0.0):.2f}",
                "MNQ Net PnL": f"${sim.get('total_net_pnl_usd', 0.0):,.2f}",
                "NQ Net PnL": f"${nq_pnl:,.2f}",
                "Max DD (MNQ)": f"${sim.get('max_drawdown_usd', 0.0):,.2f}",
                "Sharpe": f"{sim.get('sharpe_ratio', 0.0):.2f}",
                "Avg Trade": f"${sim.get('avg_trade_usd', 0.0):,.2f}",
            })

    res_df = pd.DataFrame(results)
    
    print("\n" + "=" * 125)
    print(f"BACKTEST COMPARISON RESULTS ({data_path}) (2 Contracts, $50,000 Account, RTH 09:45-15:30, Lunch Filter)")
    print("=" * 125)
    print(res_df.to_string(index=False))
    print("=" * 125)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="data/-NQ_1m.parquet")
    args = parser.parse_args()
    run_full_backtest_suite(args.data)
