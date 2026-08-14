"""
Institutional VWAP Validation & Reporting Suite (NQ1 / ES1).
============================================================
Runs 10-year full historical backtests comparing:
1. Multi-Timeframe Institutional VWAP (Retest + Fade + Sweep)
2. Single-Target Execution vs Cover the Queen Multi-Contract Scale-Out
3. Prop Firm Sizing & Drawdown Compliance Matrix (MNQ / MES)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[4])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.vwap_reclaim.core.vwap_institutional import VWAPInstitutionalStrategy
from scripts.trading_framework.core.multi_contract_backtester import MultiContractBacktester


def run_validation(symbol: str = "NQ1"):
    print(f"\n================================================================================")
    print(f"       INSTITUTIONAL VWAP VALIDATION REPORT — {symbol} (10-YEAR DATASET)")
    print(f"================================================================================\n")

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    print(f"Loading {symbol} enriched data...")
    df = loader.load_enriched(symbol)
    print(f"Data loaded: {len(df):,} bars from {df.index.min()} to {df.index.max()}\n")

    point_val = 2.0 if "NQ" in symbol else 5.0
    strat = VWAPInstitutionalStrategy(ticker=symbol)

    scenarios = [
        {
            "name": "1. All Models (Retest + Fade + Sweep) [Single 2.0R Target]",
            "params": {"model_mode": "all", "sl_atr_mult": 1.8, "tp1_r_mult": 2.0, "tp2_r_mult": 2.0, "filter_lunch": True},
            "move_be": False,
        },
        {
            "name": "2. Dynamic Retest Only [Cover the Queen: 50% @ 1.0R, 50% @ 2.0R]",
            "params": {"model_mode": "retest", "sl_atr_mult": 1.8, "tp1_r_mult": 1.0, "tp2_r_mult": 2.0, "filter_lunch": True},
            "move_be": False,
        },
        {
            "name": "3. All Models [Cover the Queen: 50% @ 1.0R, 50% @ 2.5R Runner]",
            "params": {"model_mode": "all", "sl_atr_mult": 1.8, "tp1_r_mult": 1.0, "tp2_r_mult": 2.5, "filter_lunch": True},
            "move_be": False,
        },
        {
            "name": "4. All Models [Cover the Queen: 50% @ 1.0R, 50% @ 3.0R Runner]",
            "params": {"model_mode": "all", "sl_atr_mult": 1.8, "tp1_r_mult": 1.0, "tp2_r_mult": 3.0, "filter_lunch": True},
            "move_be": False,
        },
        {
            "name": "5. All Models [Cover the Queen + BE Trail @ 1.0R]",
            "params": {"model_mode": "all", "sl_atr_mult": 1.8, "tp1_r_mult": 1.0, "tp2_r_mult": 2.5, "filter_lunch": True},
            "move_be": True,
        },
    ]

    report_rows = []

    for sc in scenarios:
        print(f"Evaluating Scenario: {sc['name']}...")
        sigs = strat.hunt(df, params=sc["params"])
        
        backtester = MultiContractBacktester(
            contracts=2,
            tp1_qty_pct=0.5,
            point_value=point_val,
            account_size=50000.0,
            max_daily_loss=1000.0,
            max_trailing_drawdown=2000.0,
        )

        res = backtester.run(sigs, df, risk_params={"ticker": symbol, "move_to_be_on_tp1": sc["move_be"]})

        report_rows.append({
            "Scenario": sc["name"],
            "Trades": res["num_trades"],
            "Win Rate %": res["win_rate_%"],
            "TP1 Hit %": res["tp1_reach_rate_%"],
            "TP2 Hit %": res["tp2_reach_rate_%"],
            "Profit Factor": res["profit_factor"],
            "Net PnL ($)": f"${res['total_net_pnl_usd']:,.2f}",
            "Total Ret %": f"{res['total_return_%']:.1f}%",
            "Max DD ($)": f"${res['max_drawdown_usd']:,.2f}",
            "Max DD %": f"{res['max_drawdown_%']:.1f}%",
            "Worst Day ($)": f"${res['worst_day_usd']:,.2f}",
            "Sharpe": res["sharpe_ratio"],
        })

    summary_df = pd.DataFrame(report_rows)
    print("\n" + "=" * 120)
    print("                                      SUMMARY PERFORMANCE MATRIX (2 MNQ MICROS / $50K ACCOUNT)")
    print("=" * 120)
    print(summary_df.to_string(index=False))
    print("=" * 120 + "\n")

    out_path = Path(PROJECT_ROOT) / "reports" / "research" / f"vwap_institutional_{symbol.lower()}_report.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(out_path, index=False)
    print(f"Report saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="NQ1", choices=["NQ1", "ES1"])
    args = parser.parse_args()
    run_validation(args.symbol)
