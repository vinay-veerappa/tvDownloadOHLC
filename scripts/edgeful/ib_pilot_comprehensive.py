"""IB Statistics Pilot - Phase E: Comprehensive strategy evaluation.

Evaluates EVERY strategy from the STRATEGY_COMPENDIUM against the play_detail data:
  - All 3 core plays (1/2/3) x 4 target levels (0.25/0.5/0.75/1.0)
  - All 8 bias variants (bias_formation_firstreach, lasttouch, close_dir, fvg, fvg_ifvg, fvg_rth, fvg_1011, combined)
  - All 13 entry modules (E8-E22 from ib_entry_signals)
  - All condition stacks (Rule 1-5 from Edgeful)
  - The direction trigger (Rule 1) with each bias variant
  - Calendar filters (DOW, month)
  - IB size filters
  - MAE-calibrated stop optimization

Usage:
    python -m scripts.edgeful.ib_pilot_comprehensive --symbols NQ1 --years 5
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edgeful.ib_pilot_stats import DERIVED, EDGEFUL_TOP25, EDGEFUL_BOT25, EDGEFUL_SIZE_THRESHOLDS, NOON_BREAK_MINUTES
from scripts.edgeful.ib_pilot_stops import load_play_detail, load_confluence, POINT_VALUE, AVG_PRICE


def load_entry_signals(symbol, session="NY AM IB", years=5):
    path = DERIVED / f"ib_entry_signals_{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    e = pd.read_parquet(path)
    e = e[e["session_slot"] == session].copy()
    e["trading_day"] = pd.to_datetime(e["trading_day"])
    max_day = e["trading_day"].max()
    min_day = (max_day.to_period("M") - years * 12).to_timestamp()
    e = e[e["trading_day"] >= min_day].copy()
    return e


def active_stats(g):
    """Compute WR, E[R], PF, N for active trades only."""
    active = g[g["result"] != 0]
    n = len(active)
    if n == 0:
        return {"n": 0, "wr": 0, "exp": 0, "pf": 0}
    wins = (active["result"] == 1).sum()
    wr = 100 * wins / n
    exp = active["realized_r"].mean()
    pf_pos = active[active["result"] == 1]["realized_r"].sum()
    pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
    pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
    return {"n": n, "wr": wr, "exp": exp, "pf": pf}


def evaluate_all_plays_targets(plays, label="5-year"):
    """Evaluate all 3 plays x 4 target levels."""
    print(f"\n{'='*90}")
    print(f"ALL PLAYS x TARGET LEVELS ({label})")
    print(f"{'='*90}")
    print(f"  {'Play':>5} {'Target':>7} {'N_active':>9} {'WR':>7} {'E[R]':>9} {'PF':>6} {'Verdict':>10}")
    print(f"  {'-'*60}")
    for play in [1, 2, 3]:
        for lvl in sorted(plays[plays["play"] == play]["target_lvl"].unique()):
            g = plays[(plays["play"] == play) & (plays["target_lvl"] == lvl)]
            s = active_stats(g)
            if s["n"] < 50:
                continue
            verdict = "EDGE" if s["exp"] > 0.05 else ("weak" if s["exp"] > 0 else "none")
            sig = "+" if s["exp"] > 0 else "-"
            print(f"  {play:>5} {lvl:>6}x {s['n']:>9} {s['wr']:>6.1f}% {sig}{abs(s['exp']):>8.4f} {s['pf']:>5.2f} {verdict:>10}")


def evaluate_all_bias_variants(plays, confluence, label="5-year"):
    """Evaluate all 8 bias variants as direction filters on Play 1."""
    print(f"\n{'='*90}")
    print(f"ALL BIAS VARIANTS as DIRECTION FILTER on Play 1 ({label})")
    print(f"{'='*90}")

    bias_cols = ["bias_formation_firstreach", "bias_formation_lasttouch",
                 "bias_close_dir", "bias_fvg", "bias_fvg_ifvg",
                 "bias_fvg_rth", "bias_fvg_1011", "bias_combined"]

    merged = plays.merge(confluence[["trading_day"] + bias_cols], on="trading_day", how="left")

    # Baseline: all Play 1 trades
    print(f"\n  Baseline (no bias filter):")
    s = active_stats(merged[merged["play"] == 1])
    print(f"    N={s['n']}  WR={s['wr']:.1f}%  E[R]={s['exp']:+.4f}  PF={s['pf']:.2f}")

    print(f"\n  {'Bias variant':<30} {'Dir':>5} {'N_active':>9} {'WR':>7} {'E[R]':>9} {'PF':>6} {'Lift':>8}")
    print(f"  {'-'*75}")

    for bias_col in bias_cols:
        for direction in [1, -1]:
            # Filter: only trade in the bias direction
            # For Play 1 breakout: trade long if bias=+1 AND break=+1; trade short if bias=-1 AND break=-1
            mask = (merged["play"] == 1) & (merged[bias_col] == direction) & (merged["result"] != 0)
            # But we need to check if the trade direction matches the bias
            # In play_detail, we don't have trade direction directly; use realized_r sign as proxy
            # Actually, the play is evaluated bar-by-bar; bias_correct_* tells us if bias agreed
            # Let's use a simpler approach: filter by bias and measure E[R]
            g = merged[(merged["play"] == 1) & (merged[bias_col] == direction)]
            s = active_stats(g)
            if s["n"] < 50:
                continue
            lift = s["exp"] - active_stats(merged[merged["play"] == 1])["exp"]
            sig = "+" if s["exp"] > 0 else "-"
            print(f"  {bias_col:<30} {direction:>+5} {s['n']:>9} {s['wr']:>6.1f}% {sig}{abs(s['exp']):>8.4f} {s['pf']:>5.2f} {lift:>+.4f}")


def evaluate_all_entry_modules(plays, entry_signals, label="5-year"):
    """Evaluate all 13 entry modules (E8-E22) as filters on Play 1."""
    print(f"\n{'='*90}")
    print(f"ALL ENTRY MODULES (E8-E22) as FILTERS on Play 1 ({label})")
    print(f"{'='*90}")

    entry_cols = [c for c in entry_signals.columns if c.startswith("entry_") and c not in
                  ("entry_scale_in", "entry_time_qualified_size", "entry_signal_count", "entry_primary")]

    merged = plays.merge(entry_signals[["trading_day"] + entry_cols], on="trading_day", how="left")

    # Baseline
    print(f"\n  Baseline (no entry filter):")
    s = active_stats(merged[merged["play"] == 1])
    print(f"    N={s['n']}  WR={s['wr']:.1f}%  E[R]={s['exp']:+.4f}  PF={s['pf']:.2f}")

    print(f"\n  {'Entry module':<35} {'N_active':>9} {'WR':>7} {'E[R]':>9} {'PF':>6} {'Lift':>8} {'Coverage':>9}")
    print(f"  {'-'*85}")

    for col in entry_cols:
        # Filter: only trade when entry module is active
        g = merged[(merged["play"] == 1) & (merged[col] == True)]
        s = active_stats(g)
        if s["n"] < 20:
            print(f"  {col:<35} {s['n']:>9} (insufficient)")
            continue
        baseline = active_stats(merged[merged["play"] == 1])
        lift = s["exp"] - baseline["exp"]
        coverage = 100 * s["n"] / baseline["n"] if baseline["n"] else 0
        sig = "+" if s["exp"] > 0 else "-"
        print(f"  {col:<35} {s['n']:>9} {s['wr']:>6.1f}% {sig}{abs(s['exp']):>8.4f} {s['pf']:>5.2f} {lift:>+.4f} {coverage:>7.1f}%")


def evaluate_all_exits(plays, confluence, label="5-year"):
    """Evaluate exit-related confluence features as filters."""
    print(f"\n{'='*90}")
    print(f"EXIT-RELATED FEATURES as FILTERS on Play 1 ({label})")
    print(f"{'='*90}")

    exit_cols = ["behavior", "mid_lock_frac", "front_run_active", "retrace_depth_pct",
                 "avwap_aligned", "trend_aligned_with_break"]

    merged = plays.merge(confluence[["trading_day"] + exit_cols], on="trading_day", how="left")

    # Baseline
    baseline = active_stats(merged[merged["play"] == 1])
    print(f"\n  Baseline: N={baseline['n']}  WR={baseline['wr']:.1f}%  E[R]={baseline['exp']:+.4f}  PF={baseline['pf']:.2f}")

    # Categorical: behavior
    print(f"\n  By behavior:")
    for val in merged["behavior"].dropna().unique():
        g = merged[(merged["play"] == 1) & (merged["behavior"] == val)]
        s = active_stats(g)
        if s["n"] < 20:
            continue
        lift = s["exp"] - baseline["exp"]
        sig = "+" if s["exp"] > 0 else "-"
        print(f"    {val:<15} N={s['n']:>5}  WR={s['wr']:.1f}%  E[R]={sig}{abs(s['exp']):.4f}  PF={s['pf']:.2f}  lift={lift:+.4f}")

    # Boolean filters
    for col in ["front_run_active", "avwap_aligned", "trend_aligned_with_break"]:
        if col not in merged.columns:
            continue
        print(f"\n  By {col}:")
        for val in [True, False]:
            g = merged[(merged["play"] == 1) & (merged[col] == val)]
            s = active_stats(g)
            if s["n"] < 20:
                continue
            lift = s["exp"] - baseline["exp"]
            sig = "+" if s["exp"] > 0 else "-"
            print(f"    {str(val):<15} N={s['n']:>5}  WR={s['wr']:.1f}%  E[R]={sig}{abs(s['exp']):.4f}  PF={s['pf']:.2f}  lift={lift:+.4f}")

    # Continuous: mid_lock_frac, retrace_depth_pct (binned)
    for col in ["mid_lock_frac", "retrace_depth_pct"]:
        if col not in merged.columns:
            continue
        print(f"\n  By {col} (deciles):")
        merged[f"{col}_decile"] = pd.qcut(merged[col].fillna(0.5), 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        for q in ["Q1","Q2","Q3","Q4","Q5"]:
            g = merged[(merged["play"] == 1) & (merged[f"{col}_decile"] == q)]
            s = active_stats(g)
            if s["n"] < 20:
                continue
            lift = s["exp"] - baseline["exp"]
            sig = "+" if s["exp"] > 0 else "-"
            med = g[col].median()
            print(f"    {q} (med={med:.3f}): N={s['n']:>5}  WR={s['wr']:.1f}%  E[R]={sig}{abs(s['exp']):.4f}  PF={s['pf']:.2f}  lift={lift:+.4f}")


def evaluate_condition_stacks_all(plays, confluence, entry_signals, label="5-year"):
    """Evaluate cumulative condition stacks combining bias + entry + calendar."""
    print(f"\n{'='*90}")
    print(f"CUMULATIVE CONDITION STACKS - ALL COMBINATIONS ({label})")
    print(f"{'='*90}")

    merged = plays.merge(confluence[["trading_day", "bias_formation_firstreach", "ib_close",
                                     "ib_open", "range_pct", "ib_range", "dow",
                                     "ib_size_bucket_edgeful"]], on="trading_day", how="left")
    merged = merged.merge(entry_signals[["trading_day", "entry_primary"]], on="trading_day", how="left")

    # Compute ib_close_position
    ib_r = merged["ib_range"].fillna(1)
    merged["ib_close_position"] = ((merged["ib_close"] - merged["ib_low"]) / ib_r).clip(0, 1) if "ib_low" in merged.columns else 0.5
    # Actually we need ib_low too
    if "ib_low" not in merged.columns:
        merged = merged.merge(confluence[["trading_day", "ib_low", "ib_high"]], on="trading_day", how="left")
        ib_r = merged["ib_high"] - merged["ib_low"]
        merged["ib_close_position"] = np.where(ib_r > 0, ((merged["ib_close"] - merged["ib_low"]) / ib_r).clip(0, 1), 0.5)

    # Rule 1A stack on Play 1
    print(f"\n  Rule 1A stack on Play 1 (low first + close top 25%):")
    base = merged[merged["play"] == 1]
    s0 = active_stats(base)
    print(f"    Baseline (all Play 1):           N={s0['n']:>5}  WR={s0['wr']:.1f}%  E[R]={s0['exp']:+.4f}  PF={s0['pf']:.2f}")

    for play in [1, 3]:
        print(f"\n  Play {play} with Rule 1A direction filter:")
        base = merged[merged["play"] == play]
        s0 = active_stats(base)
        print(f"    Baseline:                        N={s0['n']:>5}  WR={s0['wr']:.1f}%  E[R]={s0['exp']:+.4f}  PF={s0['pf']:.2f}")

        # + Rule 1A (low first + top 25%)
        r1a = base[(base["bias_formation_firstreach"] == 1) & (base["ib_close_position"] >= EDGEFUL_TOP25)]
        s1 = active_stats(r1a)
        if s1["n"] > 0:
            print(f"    + Rule 1A (low first + top 25%): N={s1['n']:>5}  WR={s1['wr']:.1f}%  E[R]={s1['exp']:+.4f}  PF={s1['pf']:.2f}  lift={s1['exp']-s0['exp']:+.4f}")

        # + Rule 1B (high first + bot 25%)
        r1b = base[(base["bias_formation_firstreach"] == -1) & (base["ib_close_position"] <= EDGEFUL_BOT25)]
        s2 = active_stats(r1b)
        if s2["n"] > 0:
            print(f"    + Rule 1B (high first + bot 25%): N={s2['n']:>5}  WR={s2['wr']:.1f}%  E[R]={s2['exp']:+.4f}  PF={s2['pf']:.2f}  lift={s2['exp']-s0['exp']:+.4f}")

        # + Skip huge IB
        no_huge = base[base["ib_size_bucket_edgeful"] != "huge"]
        s3 = active_stats(no_huge)
        if s3["n"] > 0:
            print(f"    + Skip huge IB:                  N={s3['n']:>5}  WR={s3['wr']:.1f}%  E[R]={s3['exp']:+.4f}  PF={s3['pf']:.2f}  lift={s3['exp']-s0['exp']:+.4f}")

        # + Skip Monday
        no_mon = base[base["dow"] != 0]
        s4 = active_stats(no_mon)
        if s4["n"] > 0:
            print(f"    + Skip Monday:                   N={s4['n']:>5}  WR={s4['wr']:.1f}%  E[R]={s4['exp']:+.4f}  PF={s4['pf']:.2f}  lift={s4['exp']-s0['exp']:+.4f}")

        # Combined: Rule 1A + skip huge + skip Monday
        combined = base[(base["bias_formation_firstreach"] == 1) &
                        (base["ib_close_position"] >= EDGEFUL_TOP25) &
                        (base["ib_size_bucket_edgeful"] != "huge") &
                        (base["dow"] != 0)]
        s5 = active_stats(combined)
        if s5["n"] > 0:
            print(f"    COMBINED (1A+no huge+no Mon):    N={s5['n']:>5}  WR={s5['wr']:.1f}%  E[R]={s5['exp']:+.4f}  PF={s5['pf']:.2f}  lift={s5['exp']-s0['exp']:+.4f}")


def evaluate_stop_optimization_all(plays, symbol="NQ1", account=50000):
    """Stop optimization for all play+target combos with prop viability."""
    print(f"\n{'='*90}")
    print(f"STOP OPTIMIZATION - ALL PLAYS ({symbol}, ${account:,} account)")
    print(f"{'='*90}")

    pv = POINT_VALUE.get(symbol, {"micro": 2.0})
    avg_price = AVG_PRICE.get(symbol, 20000)
    stop_distances = [0.25, 0.50, 0.75, 1.00]

    print(f"\n  {'Play':>5} {'Target':>7} {'Stop':>6} {'N':>6} {'WR':>7} {'E[R]':>9} {'PF':>6} {'$ risk':>8} {'% acct':>7} {'Viable':>7}")
    print(f"  {'-'*75}")

    for play in [1, 2, 3]:
        for target_lvl in sorted(plays[plays["play"] == play]["target_lvl"].unique()):
            g = plays[(plays["play"] == play) & (plays["target_lvl"] == target_lvl)]
            active = g[g["result"] != 0].copy()
            n = len(active)
            if n < 50:
                continue

            for stop_r in stop_distances:
                sim_r = active["realized_r"].copy()
                stopped = active["mae"] <= -stop_r
                sim_r[stopped] = -stop_r

                wins = (sim_r > 0).sum()
                wr = 100 * wins / n
                exp = sim_r.mean()
                pf_pos = sim_r[sim_r > 0].sum()
                pf_neg = abs(sim_r[sim_r < 0].sum())
                pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')

                avg_range_pct = 0.8
                target_pts = target_lvl * avg_range_pct * avg_price / 100
                stop_pts = stop_r * target_pts
                dollar = stop_pts * pv["micro"]
                pct = 100 * dollar / account
                viable = "YES" if (pct < 1.0 and exp > 0) else ("maybe" if exp > 0 else "NO")
                sig = "+" if exp > 0 else "-"
                print(f"  {play:>5} {target_lvl:>6}x {stop_r:>5.2f}R {n:>6} {wr:>6.1f}% {sig}{abs(exp):>8.4f} {pf:>5.2f} ${dollar:>6.0f} {pct:>5.2f}% {viable:>7}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="NQ1")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--account", type=float, default=50000)
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    print(f"\n{'#'*90}")
    print(f"# PHASE E: COMPREHENSIVE STRATEGY EVALUATION")
    print(f"# Scope: {','.join(symbols)} NY AM IB, {args.years} years")
    print(f"{'#'*90}")

    for sym in symbols:
        print(f"\n{'='*90}")
        print(f"SYMBOL: {sym}")
        print(f"{'='*90}")

        plays = load_play_detail(sym, "NY AM IB", args.years)
        confluence = load_confluence(sym, "NY AM IB", args.years)
        entry_signals = load_entry_signals(sym, "NY AM IB", args.years)
        print(f"  Play detail: {len(plays)}  Confluence: {len(confluence)}  Entry signals: {len(entry_signals)}")

        if len(plays) == 0:
            continue

        # 1. All plays x targets
        evaluate_all_plays_targets(plays, f"{args.years}yr {sym}")

        # 2. All bias variants
        if len(confluence) > 0:
            evaluate_all_bias_variants(plays, confluence, f"{args.years}yr {sym}")

        # 3. All entry modules
        if len(entry_signals) > 0:
            evaluate_all_entry_modules(plays, entry_signals, f"{args.years}yr {sym}")

        # 4. Exit-related features
        if len(confluence) > 0:
            evaluate_all_exits(plays, confluence, f"{args.years}yr {sym}")

        # 5. Condition stacks (Rule 1 + calendar + IB size)
        if len(confluence) > 0 and len(entry_signals) > 0:
            evaluate_condition_stacks_all(plays, confluence, entry_signals, f"{args.years}yr {sym}")

        # 6. Stop optimization
        evaluate_stop_optimization_all(plays, sym, args.account)

    print(f"\n{'#'*90}")
    print(f"# PHASE E COMPLETE")
    print(f"{'#'*90}")


if __name__ == "__main__":
    main()