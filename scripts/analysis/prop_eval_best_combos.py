"""
Prop Firm Evaluation of Best Combos
=====================================
Runs PropFirmSimulator on the three best strategy combos from the experiments.
"""
import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd, numpy as np
from scripts.trading_framework.ml.prop_firm_simulator import PropFirmSimulator, FIRM_PROFILES
from scripts.analysis.comprehensive_experiments import (
    load_data, run_bb_variant, run_st_variant, compute_mfe_mae
)
from scripts.analysis.range_strategy_comparison import _wilder_rsi
from scripts.libs_py.adaptive_rsi_variants import kaufman_er_rsi
from pathlib import Path
from datetime import datetime

def main():
    print("=" * 80)
    print("PROP FIRM EVALUATION — BEST COMBOS")
    print("=" * 80)

    df1, df5, daily_atr = load_data("ES")
    htf_df = pd.read_parquet("data/derived/ICT/ES1_htf_levels.parquet")

    # ─── Run the three best combos ───────────────────────────────────────
    print("\n[1] BB Kaufman ER + 2-bar hook...")
    bb_kaufman = run_bb_variant(df1, df5, daily_atr, lambda c: kaufman_er_rsi(c), "BB_Kaufman_2bar",
                                 67, 33, hook_bars=2)
    print(f"  Trades: {len(bb_kaufman)}  WR: {(bb_kaufman['pnl_dollars']>0).mean()*100:.1f}%  Net: ${bb_kaufman['pnl_dollars'].sum():.0f}")

    print("\n[2] BB Wilder SHORT-only...")
    bb_short = run_bb_variant(df1, df5, daily_atr, lambda c: _wilder_rsi(c, 14), "BB_Wilder_SHORT",
                              67, 33, hook_bars=1, direction_filter="SHORT")
    print(f"  Trades: {len(bb_short)}  WR: {(bb_short['pnl_dollars']>0).mean()*100:.1f}%  Net: ${bb_short['pnl_dollars'].sum():.0f}")

    print("\n[3] ST ATR+time+1.0trail...")
    st_filtered = run_st_variant(df1, df5, daily_atr, atr_regime_filter=True, time_filter=True,
                                 htf_skip=False, htf_df=None, trail_mult=1.0)
    print(f"  Trades: {len(st_filtered)}  WR: {(st_filtered['pnl_dollars']>0).mean()*100:.1f}%  Net: ${st_filtered['pnl_dollars'].sum():.0f}")

    # Also test 2xMES sizing for ST
    st_2x = st_filtered.copy()
    st_2x["pnl_dollars"] = st_2x["pnl_dollars"] * 2

    # Combined portfolio: BB Kaufman + ST filtered
    bb_k = bb_kaufman.copy()
    bb_k["strategy"] = "Portfolio_BB"
    st_p = st_filtered.copy()
    st_p["strategy"] = "Portfolio_ST"
    portfolio = pd.concat([bb_k, st_p], ignore_index=True)

    # Combined at 2x MES for ST + 1x MES for BB
    portfolio_2x = pd.concat([bb_k, st_2x], ignore_index=True)

    # ─── Run PropFirmSimulator ───────────────────────────────────────────
    sim = PropFirmSimulator(account_size=50_000, point_value=5.0)
    all_reports = []

    configs = [
        ("BB_Kaufman_2bar (1xMES)", bb_kaufman),
        ("BB_Wilder_SHORT (1xMES)", bb_short),
        ("ST_filtered_1.0trail (1xMES)", st_filtered),
        ("ST_filtered_1.0trail (2xMES)", st_2x),
        ("Portfolio BB+ST (1xMES each)", portfolio),
        ("Portfolio BB(1x)+ST(2x)", portfolio_2x),
    ]

    for name, trades_df in configs:
        if trades_df.empty:
            continue
        print(f"\n{'='*80}")
        print(f"  {name}")
        print(f"{'='*80}")

        results = {}
        for key, profile in FIRM_PROFILES.items():
            trades_detailed = pd.DataFrame({
                "exit_time": pd.to_datetime(trades_df["exit_time"]),
                "pnl_pct": trades_df["pnl_dollars"].values / profile.account_size * 100,
            })
            det = sim.run_deterministic(trades_detailed, profile)
            mc = sim.run_monte_carlo(trades_detailed, profile, n_simulations=3000)
            results[key] = (det, mc)
            print(f"  {profile.name:<30} Pass: {mc.pass_rate_pct:>5.1f}%  Grade: {mc.grade}  Blow: {mc.blow_rate_pct:.1f}%  P50: ${mc.p50_final_equity:+.0f}")

        all_reports.append((name, results, trades_df))

    # ─── Write full report ───────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("WRITING REPORT")
    print(f"{'='*80}")

    report_lines = [
        "# Prop Firm Evaluation — Best Strategy Combos",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        f"\n_Engine: 1xMES $5/pt (2xMES noted), $1.20/rt commission, 1-tick slippage_",
        f"\n_MC: 3000 permutations per profile_",
        "\n---\n",
        "## Viability Summary\n",
        "| Strategy | Firm | MC Pass% | Grade | Blow% | P50 Equity | Max DD |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for name, results, trades_df in all_reports:
        n_trades = len(trades_df)
        net = trades_df["pnl_dollars"].sum()
        wr = (trades_df["pnl_dollars"] > 0).mean() * 100
        gp = trades_df.loc[trades_df["pnl_dollars"]>0, "pnl_dollars"].sum()
        gl = abs(trades_df.loc[trades_df["pnl_dollars"]<0, "pnl_dollars"].sum())
        pf = gp/gl if gl > 0 else 999
        report_lines.append(f"\n### {name} ({n_trades} trades, WR {wr:.1f}%, PF {pf:.2f}, Net ${net:+.0f})\n")

        for key, (det, mc) in results.items():
            report_lines.append(
                f"| {name} | {det.profile_name} | {mc.pass_rate_pct:.1f}% | "
                f"{mc.grade} | {mc.blow_rate_pct:.1f}% | ${mc.p50_final_equity:+.0f} | ${det.max_drawdown_used:.0f} |"
            )

        # Detailed per-profile
        report_lines.append(f"\n**Detailed ({name}):**\n")
        report_lines.append("| Firm | Outcome | Final P&L | Max DD | Trades | WR | PF | Pass% | Grade |")
        report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for key, (det, mc) in results.items():
            outcome = "PASSED" if det.passed else "BLOWN" if det.blown else "TIMEOUT"
            report_lines.append(
                f"| {det.profile_name} | {outcome} | ${det.final_equity_delta:+.0f} | "
                f"${det.max_drawdown_used:.0f} | {det.total_trades} | {det.win_rate:.1f}% | "
                f"{det.profit_factor:.2f} | {mc.pass_rate_pct:.1f}% | {mc.grade} |"
            )

    # Bootstrap CI
    report_lines.append("\n## Bootstrap Confidence Intervals\n")
    report_lines.append("| Strategy | Mean/Session | CI Low | CI High | Verdict |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: |")

    for name, results, trades_df in all_reports:
        if trades_df.empty:
            continue
        daily = trades_df.groupby("date")["pnl_dollars"].sum().values
        if len(daily) < 10:
            report_lines.append(f"| {name} | ${daily.mean():.2f} | - | - | INSUFFICIENT DATA |")
            continue
        boots = np.random.choice(daily, size=(5000, len(daily)), replace=True).mean(axis=1)
        ci_lo = float(np.percentile(boots, 2.5))
        ci_hi = float(np.percentile(boots, 97.5))
        verdict = "NOISE" if ci_lo <= 0 <= ci_hi else "EDGE"
        report_lines.append(f"| {name} | ${daily.mean():.2f} | ${ci_lo:.2f} | ${ci_hi:.2f} | {verdict} |")

    report_path = Path("docs/research/PROP_FIRM_BEST_COMBOS.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    main()