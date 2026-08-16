"""
========================================================================================
Long-Horizon Multi-Era Institutional Backtester (2006–2026)
========================================================================================
Executes full multi-decade validation of the master modular institutional strategy:
- SMT Divergence Engine
- First Presented FVG Rule
- 1-Hour HTF Order Flow Trend Alignment
- 2-Contract Pack (Cover The Queen @ 10 bps -> Breakeven Stop -> Runner @ 40/60 bps)
- Failed CISD Trapped Liquidity Re-Expansion (Alpha 1)

Generates full year-by-year performance metrics, Max Drawdown, Profit Factor, and Payoff Ratio.
========================================================================================
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.backtests.run_master_institutional_strategy import run_master_backtest

if __name__ == "__main__":
    df_nq = pd.read_parquet(_root / "data" / "NQ1_5m.parquet")
    df_es = pd.read_parquet(_root / "data" / "ES1_5m.parquet")

    for d in (df_nq, df_es):
        if not isinstance(d.index, pd.DatetimeIndex):
            d["datetime"] = pd.to_datetime(d["datetime"])
            d.set_index("datetime", inplace=True)

    common = df_nq.index.intersection(df_es.index)
    df_nq = df_nq.loc[common].sort_index()
    df_es = df_es.loc[common].sort_index()

    start_date = df_nq.index.min().date()
    end_date = df_nq.index.max().date()
    total_bars = len(df_nq)

    print(f"Loaded {total_bars:,} bars across {start_date} to {end_date} ({(end_date - start_date).days / 365.25:.1f} Years)")
    print("Running Full Long-Horizon Master Institutional Backtest...")

    trades_df, stats = run_master_backtest(
        df_nq=df_nq,
        df_es=df_es,
        symbol="NQ",
        point_value=2.0,            # Micro MNQ ($2/pt). For NQ ($20/pt), multiply by 10
        comm_per_contract=0.52,
        enable_trap_reexpansion=True,
        queen_bps=10.0,
        runner_bps=40.0,
        runner_pm_bps=60.0,
        max_risk_bps=12.0,
    )

    if len(trades_df) == 0:
        print("No trades generated.")
        sys.exit(0)

    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
    trades_df["year"] = trades_df["entry_time"].dt.year
    trades_df["cum_pnl"] = trades_df["net_pnl_usd"].cumsum()
    trades_df["peak"] = trades_df["cum_pnl"].cummax()
    trades_df["drawdown"] = trades_df["cum_pnl"] - trades_df["peak"]
    max_dd = abs(trades_df["drawdown"].min())

    print("\n" + "=" * 95)
    print(f"       LONG-HORIZON MASTER INSTITUTIONAL SYSTEM METRICS ({start_date} to {end_date})       ")
    print("=" * 95)
    print(f"Total Completed Trades:   {stats['trades']:,}")
    print(f"Win Rate:                 {stats['win_rate']:.1f}%")
    print(f"Profit Factor:            {stats['profit_factor']:.2f}")
    print(f"Total Net PnL (Micro MNQ): ${stats['net_pnl']:,.2f}")
    print(f"Total Net PnL (1 Full NQ): +${stats['net_pnl'] * 10:,.2f}")
    print(f"Gross Profit:             ${stats['gross_profit']:,.2f}")
    print(f"Gross Loss:               ${stats['gross_loss']:,.2f}")
    print(f"Average Win:              ${stats['avg_win']:.2f}")
    print(f"Average Loss:             ${stats['avg_loss']:.2f}")
    print(f"Payoff Ratio:             {stats['payoff_ratio']:.2f} : 1")
    print(f"Max Equity Drawdown:      ${max_dd:,.2f}  (Micro MNQ)")
    print(f"Return on Max Drawdown:   {stats['net_pnl'] / max_dd:.2f}x")

    # Annual Breakdown
    def calc_year_metrics(g):
        w = g[g["net_pnl_usd"] > 0]
        l = g[g["net_pnl_usd"] < 0]
        gp = w["net_pnl_usd"].sum()
        gl = abs(l["net_pnl_usd"].sum())
        pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
        return pd.Series({
            "Trades": len(g),
            "Win Rate (%)": f"{(len(w) / len(g)) * 100:.1f}%",
            "Profit Factor": f"{pf:.2f}",
            "Net PnL ($)": f"${g['net_pnl_usd'].sum():,.2f}",
            "1 NQ PnL ($)": f"${g['net_pnl_usd'].sum() * 10:,.2f}",
            "Avg Win ($)": f"${w['net_pnl_usd'].mean():.2f}" if len(w) > 0 else "$0.00",
            "Avg Loss ($)": f"${l['net_pnl_usd'].mean():.2f}" if len(l) > 0 else "$0.00",
            "Payoff": f"{abs(w['net_pnl_usd'].mean() / l['net_pnl_usd'].mean()):.2f} : 1" if len(l) > 0 and len(w) > 0 else "N/A",
        })

    year_summary = trades_df.groupby("year").apply(calc_year_metrics)
    print("\n" + "=" * 95)
    print("                              ANNUAL PERFORMANCE BREAKDOWN                              ")
    print("=" * 95)
    print(year_summary.to_string())

    # Modern Era Slice (2020-2026)
    modern_df = trades_df[trades_df["year"] >= 2020]
    w_m = modern_df[modern_df["net_pnl_usd"] > 0]
    l_m = modern_df[modern_df["net_pnl_usd"] < 0]
    gp_m = w_m["net_pnl_usd"].sum()
    gl_m = abs(l_m["net_pnl_usd"].sum())
    pf_m = (gp_m / gl_m) if gl_m > 0 else 0.0

    print("\n" + "=" * 95)
    print("                     MODERN ALGORITHMIC REGIME BREAKDOWN (2020–2026)                    ")
    print("=" * 95)
    print(f"Modern Era Trades:        {len(modern_df):,}")
    print(f"Modern Era Win Rate:      {(len(w_m) / len(modern_df)) * 100:.1f}%")
    print(f"Modern Era Profit Factor: {pf_m:.2f}")
    print(f"Modern Era Net PnL (MNQ): ${modern_df['net_pnl_usd'].sum():,.2f}")
    print(f"Modern Era Net PnL (1 NQ):+${modern_df['net_pnl_usd'].sum() * 10:,.2f}")
    print(f"Modern Era Payoff Ratio:  {abs(w_m['net_pnl_usd'].mean() / l_m['net_pnl_usd'].mean()):.2f} : 1")
