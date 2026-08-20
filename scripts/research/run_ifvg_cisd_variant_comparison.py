r"""
IFVG/CISD Variant Comparison using the standard institutional backtest engine.
=============================================================================
Compares the three C#-mirrored variants across higher timeframes for NQ1 and ES1.

Usage:
    .\.venv\Scripts\python.exe -m scripts.research.run_ifvg_cisd_variant_comparison --symbol NQ1
    .\.venv\Scripts\python.exe -m scripts.research.run_ifvg_cisd_variant_comparison --symbol ES1
"""
from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
_root_dir = str(_current_dir.parent) if _current_dir.name == "scripts" else str(Path(__file__).resolve().parents[2])
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy
from scripts.research.run_strategy_filter_ablation import simulate_trade_policy


VARIANTS = {
    "baseline": {"variant": "baseline", "strict_ifvg_only": True},
    "variant1": {"variant": "variant1"},
    "variant2": {"variant": "variant2"},
}

TIMEFRAMES = ["3min", "5min", "15min"]

POLICIES = [
    "CoverTheQueen_1.0R_2.5R",
    "FixedTarget_1.5R",
    "FixedTarget_2.0R",
    "FixedTarget_3.0R",
    "BreakevenTrail",
]


def run_variant_comparison(symbol: str = "NQ1", since: str | None = None) -> pd.DataFrame:
    print("=" * 110)
    print(f"IFVG/CISD VARIANT COMPARISON ({symbol}) — Standard Institutional Backtest Engine")
    print("=" * 110)

    config = load_config("scripts/trading_framework/config/sessions.yaml")
    loader = DataLoader(config)
    print(f"Loading enriched 1m data for {symbol}...")
    df = loader.load_enriched(symbol)
    if since:
        df = df[df.index >= since].copy()
    print(f"Loaded {len(df):,d} bars ({df.index[0].date()} to {df.index[-1].date()})")

    point_value = 2.0 if "NQ" in symbol else 12.5  # Micro contracts
    tick_size = 0.25 if "NQ" in symbol else 0.25

    strategy = IFVGCISDStrategy(ticker=symbol)
    records: List[Dict[str, Any]] = []

    for tf in TIMEFRAMES:
        print(f"\nHigher timeframe: {tf}")
        print("-" * 110)
        for variant_name, variant_params in VARIANTS.items():
            params = {
                "resample_tf": tf,
                "filter_lunch": True,
                "max_trades_per_day": 1,
                "r_mult_tp1": 1.0,
                "r_mult_tp2": 2.5,
                "atr_risk_mult": 1.8,
                **variant_params,
            }

            signals = strategy.hunt(df, params)
            n_signals = len(signals)
            print(f"  {variant_name:<10}: {n_signals:>4} raw signals", end="")

            if n_signals == 0:
                for pol in POLICIES:
                    records.append({
                        "symbol": symbol,
                        "timeframe": tf,
                        "variant": variant_name,
                        "policy": pol,
                        "trades": 0,
                        "win_rate_%": 0.0,
                        "profit_factor": 0.0,
                        "net_pnl_usd": 0.0,
                        "max_drawdown_usd": 0.0,
                        "max_drawdown_%": 0.0,
                        "sharpe": 0.0,
                        "payoff_ratio": 0.0,
                        "avg_trade_usd": 0.0,
                    })
                print()
                continue

            for pol in POLICIES:
                metrics = simulate_trade_policy(
                    signals,
                    df,
                    policy_name=pol,
                    contracts=2,
                    point_value=point_value,
                    commission_per_contract=1.05,
                    slippage_ticks=1,
                    tick_size=tick_size,
                    account_size=50_000.0,
                    max_forward_bars=240,
                )
                records.append({
                    "symbol": symbol,
                    "timeframe": tf,
                    "variant": variant_name,
                    "policy": pol,
                    "trades": metrics["num_trades"],
                    "win_rate_%": metrics["win_rate_%"],
                    "profit_factor": metrics["profit_factor"],
                    "net_pnl_usd": metrics["total_net_pnl_usd"],
                    "max_drawdown_usd": metrics["max_drawdown_usd"],
                    "max_drawdown_%": metrics["max_drawdown_%"],
                    "sharpe": metrics["sharpe_ratio"],
                    "payoff_ratio": metrics["payoff_ratio"],
                    "avg_trade_usd": metrics["avg_trade_usd"],
                })

            primary = next(r for r in records if r["symbol"] == symbol and r["timeframe"] == tf and r["variant"] == variant_name and r["policy"] == "CoverTheQueen_1.0R_2.5R")
            print(
                f" | CTQ: trades={primary['trades']:<4} WR={primary['win_rate_%']:5.1f}% "
                f"PF={primary['profit_factor']:5.2f} PnL=${primary['net_pnl_usd']:>9,.2f} "
                f"MaxDD=${primary['max_drawdown_usd']:>8,.2f} Sharpe={primary['sharpe']:4.2f}"
            )

    results_df = pd.DataFrame(records)

    reports_dir = Path(_root_dir) / "reports" / "research"
    reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = reports_dir / f"ifvg_cisd_variant_comparison_{symbol.lower()}.csv"
    results_df.to_csv(csv_path, index=False)

    md_path = reports_dir / f"ifvg_cisd_variant_comparison_{symbol.lower()}.md"
    _write_markdown_report(results_df, md_path, symbol)

    print(f"\nSaved CSV: {csv_path}")
    print(f"Saved report: {md_path}")

    return results_df


def _write_markdown_report(df: pd.DataFrame, out_path: Path, symbol: str):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# IFVG/CISD Variant Comparison — {symbol}\n\n")
        f.write(f"> Standard institutional backtest engine (2 micro contracts, $1.05/contract commission, 1-tick slippage, $50k account).\n\n")

        for tf in df["timeframe"].unique():
            f.write(f"## Higher Timeframe: {tf}\n\n")
            df_tf = df[df["timeframe"] == tf]
            pivot = df_tf.pivot_table(
                index="policy",
                columns="variant",
                values=["trades", "win_rate_%", "profit_factor", "net_pnl_usd", "max_drawdown_usd", "sharpe"],
            )
            f.write(pivot.to_markdown())
            f.write("\n\n")


def main():
    parser = argparse.ArgumentParser(description="Compare IFVG/CISD variants using the standard backtest engine")
    parser.add_argument("--symbol", default="NQ1", choices=["NQ1", "ES1", "NQ", "ES"])
    parser.add_argument("--since", default="2025-01-01", help="Start date for backtest window (YYYY-MM-DD)")
    args = parser.parse_args()
    sym = "NQ1" if "NQ" in args.symbol else "ES1"

    df = run_variant_comparison(sym, since=args.since)

    # Print concise summary table for primary policy
    print("\n" + "=" * 110)
    print("SUMMARY — CoverTheQueen_1.0R_2.5R")
    print("=" * 110)
    summary = df[df["policy"] == "CoverTheQueen_1.0R_2.5R"][[
        "symbol", "timeframe", "variant", "trades", "win_rate_%",
        "profit_factor", "net_pnl_usd", "max_drawdown_usd", "sharpe"
    ]]
    print(summary.to_markdown(index=False, floatfmt=".2f"))


if __name__ == "__main__":
    main()
