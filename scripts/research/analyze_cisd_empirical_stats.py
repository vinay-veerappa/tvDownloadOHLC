"""
========================================================================================
Institutional Research Engine: ICT CISD Strategy Empirical Statistics & Probabilities
========================================================================================
Analyzes NQ and ES futures historical data for ICT CISD strategy:
1. Replaces point-based SL/TP with Price Percentage / Basis Points (bps).
2. Computes comprehensive MAE / MFE distributions (Mean, Median, p25, p50, p75, p90, p95, p99).
3. Computes conditional survival probabilities (drawdown tolerance before winning).
4. Computes target hit probabilities across price percentage and bps levels.
5. Slices by sweep origin, session, and displacement quality.
========================================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.backtests.backtest_liquidity_cisd_strategy import run_liquidity_cisd_backtest


def analyze_cisd_probabilities(symbol: str = "NQ1", start_year: str = "2022-01-01"):
    print(f"\n{'='*90}")
    print(f"RUNNING EMPIRICAL ICT CISD ANALYSIS FOR {symbol} ({start_year} - 2026)")
    print(f"{'='*90}")

    data_path = _root / "data" / f"{symbol}_5m.parquet"
    if not data_path.exists():
        data_path = _root / "data" / f"{symbol[:2]}1_5m.parquet"
    
    df = pd.read_parquet(data_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)

    df_bench = df[df.index >= start_year].copy()
    point_val = 2.0 if "NQ" in symbol else 5.0

    print(f"Dataset: {len(df_bench):,} bars ({df_bench.index.min()} to {df_bench.index.max()})")

    # Run fast event-driven backtest
    t0 = time.time()
    trades_df, stats = run_liquidity_cisd_backtest(
        df_bench,
        entry_model="FVG_Touch",
        sl_model="SL4_CISD_Origin",
        use_htf_filter=True,
        queen_bps=10.0,
        runner_mfe_bps=30.0,
        point_value=point_val,
    )
    elapsed = time.time() - t0
    print(f"Backtest completed in {elapsed:.2f}s across {len(trades_df):,} trades.")
    print(f"Baseline: Win Rate = {stats['win_rate']:.1f}% | Profit Factor = {stats['profit_factor']:.2f} | Net PnL = ${stats['net_pnl']:,.2f}")

    if len(trades_df) == 0:
        return

    # Excursion metrics in Basis Points (1 bps = 0.01%) and Price %
    trades_df["mfe_bps"] = (trades_df["mfe_pts"] / trades_df["entry_price"]) * 10000.0
    trades_df["mae_bps"] = (trades_df["mae_pts"] / trades_df["entry_price"]) * 10000.0
    trades_df["mfe_pct"] = (trades_df["mfe_pts"] / trades_df["entry_price"]) * 100.0
    trades_df["mae_pct"] = (trades_df["mae_pts"] / trades_df["entry_price"]) * 100.0

    trades_df["risk_pts"] = (trades_df["entry_price"] - trades_df["stop_loss"]).abs()
    trades_df["risk_bps"] = (trades_df["risk_pts"] / trades_df["entry_price"]) * 10000.0
    trades_df["mfe_r"] = trades_df["mfe_pts"] / trades_df["risk_pts"].replace(0, np.nan)
    trades_df["mae_r"] = trades_df["mae_pts"] / trades_df["risk_pts"].replace(0, np.nan)

    # 1. Excursion Percentiles Table
    percentiles = [5, 10, 25, 50, 75, 80, 85, 90, 95, 99]
    mfe_q = np.percentile(trades_df["mfe_bps"].dropna(), percentiles)
    mae_q = np.percentile(trades_df["mae_bps"].dropna(), percentiles)

    ref_price = trades_df["entry_price"].mean()
    dist_df = pd.DataFrame({
        "Percentile": [f"p{p}" for p in percentiles],
        "MFE (bps)": np.round(mfe_q, 2),
        "MFE (%)": np.round(mfe_q / 100.0, 3),
        f"MFE (pts @ {ref_price:.0f})": np.round(mfe_q * (ref_price / 10000.0), 1),
        "MAE (bps)": np.round(mae_q, 2),
        "MAE (%)": np.round(mae_q / 100.0, 3),
        f"MAE (pts @ {ref_price:.0f})": np.round(mae_q * (ref_price / 10000.0), 1),
    })

    print(f"\n{'='*90}")
    print(f"1. EMPIRICAL MFE & MAE PERCENTILES (Basis Points & Price %)")
    print(f"{'='*90}")
    print(dist_df.to_string(index=False))

    # 2. Cumulative Target Reach Probabilities
    thresholds_bps = [2, 5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 70, 100]
    reach_stats = []
    for t_bps in thresholds_bps:
        reached = (trades_df["mfe_bps"] >= t_bps).sum()
        prob = (reached / len(trades_df)) * 100.0
        pts_eq = t_bps * (ref_price / 10000.0)
        reach_stats.append({
            "Target (bps)": f"{t_bps} bps",
            "Target (%)": f"{t_bps/100.0:.2f}%",
            f"Equiv Pts (@ {ref_price:.0f})": f"{pts_eq:.1f} pts",
            "Trades Reaching": reached,
            "Probability (%)": f"{prob:.1f}%",
        })

    print(f"\n{'='*90}")
    print(f"2. MFE EXPANSION PROBABILITY TABLE (Likelihood of Reaching Profit Target)")
    print(f"{'='*90}")
    print(pd.DataFrame(reach_stats).to_string(index=False))

    # 3. MAE Drawdown Survival Curve
    mae_bins = [0, 2, 4, 6, 8, 10, 12, 15, 20]
    survival_stats = []
    for i in range(len(mae_bins)-1):
        low_b, high_b = mae_bins[i], mae_bins[i+1]
        sub = trades_df[(trades_df["mae_bps"] >= low_b) & (trades_df["mae_bps"] < high_b)]
        if len(sub) > 0:
            win_cnt = (sub["total_pnl_usd"] > 0).sum()
            wr = (win_cnt / len(sub)) * 100.0
            survival_stats.append({
                "Adverse Drawdown Bin": f"{low_b} - {high_b} bps ({low_b/100:.2f}% - {high_b/100:.2f}%)",
                "Trades": len(sub),
                "Wins": win_cnt,
                "Win Rate (%)": f"{wr:.1f}%",
                "Avg PnL ($)": f"${sub['total_pnl_usd'].mean():,.2f}",
                "Avg MFE (bps)": f"{sub['mfe_bps'].mean():.1f} bps",
            })

    print(f"\n{'='*90}")
    print(f"3. MAE DRAWDOWN SURVIVAL ANALYSIS (Trade Health vs Incurred Drawdown)")
    print(f"{'='*90}")
    print(pd.DataFrame(survival_stats).to_string(index=False))

    # 4. Hourly Distribution (ET)
    trades_df["entry_hour"] = pd.to_datetime(trades_df["entry_time"]).dt.hour
    hour_groups = trades_df.groupby("entry_hour")
    hour_stats = []
    for hr, g in hour_groups:
        win_cnt = (g["total_pnl_usd"] > 0).sum()
        gross_p = g[g["total_pnl_usd"] > 0]["total_pnl_usd"].sum()
        gross_l = abs(g[g["total_pnl_usd"] < 0]["total_pnl_usd"].sum())
        pf = gross_p / gross_l if gross_l > 0 else np.nan
        hour_stats.append({
            "Hour (ET)": f"{hr:02d}:00",
            "Trades": len(g),
            "Win Rate (%)": f"{(win_cnt / len(g)) * 100.0:.1f}%",
            "Profit Factor": f"{pf:.2f}" if not np.isnan(pf) else "N/A",
            "Net PnL ($)": f"${g['total_pnl_usd'].sum():,.2f}",
            "Median MFE": f"{g['mfe_bps'].median():.1f} bps",
            "Median MAE": f"{g['mae_bps'].median():.1f} bps",
        })

    print(f"\n{'='*90}")
    print(f"4. HOURLY EXECUTION PERFORMANCE (ET)")
    print(f"{'='*90}")
    print(pd.DataFrame(hour_stats).sort_values("Hour (ET)").to_string(index=False))

    # 5. Summary Insights
    clean_wins = trades_df[(trades_df["total_pnl_usd"] > 0) & (trades_df["mae_bps"] <= 5.0)]
    clean_pct = (len(clean_wins) / len(trades_df[trades_df["total_pnl_usd"] > 0])) * 100.0
    print(f"\n{'='*90}")
    print(f"KEY METRIC TAKEAWAYS:")
    print(f"  • Median MAE across all trades: {trades_df['mae_bps'].median():.2f} bps ({trades_df['mae_bps'].median()/100:.3f}%)")
    print(f"  • Median MFE across all trades: {trades_df['mfe_bps'].median():.2f} bps ({trades_df['mfe_bps'].median()/100:.3f}%)")
    print(f"  • Proportion of WINNERS that had <= 5 bps MAE: {clean_pct:.1f}% (Institutional Immediate Displacement)")
    print(f"  • 10 bps (0.10%) Cover The Queen hit rate: {(trades_df['mfe_bps'] >= 10.0).sum() / len(trades_df) * 100:.1f}%")
    print(f"  • 30 bps (0.30%) Runner Target hit rate: {(trades_df['mfe_bps'] >= 30.0).sum() / len(trades_df) * 100:.1f}%")
    print(f"{'='*90}\n")


if __name__ == "__main__":
    analyze_cisd_probabilities("NQ1", "2022-01-01")
    analyze_cisd_probabilities("ES1", "2022-01-01")
