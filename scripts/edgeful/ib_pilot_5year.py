"""IB Statistics Pilot - Phase C: 5-year edge survival analysis.

Expands the pilot to 5 years and evaluates per-day, per-day-of-week, per-month,
and per-year to see if the edge holds across time and calendar dimensions.

Usage:
    python -m scripts.edgeful.ib_pilot_5year --symbols NQ1,ES1
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edgeful.ib_pilot_stats import (
    DERIVED, EDGEFUL_TOP25, EDGEFUL_BOT25, NOON_BREAK_MINUTES,
    load_pilot, add_missing_fields, baseline_table,
)
from scripts.edgeful.ib_pilot_stacks import bootstrap_ci

DOW_NAMES = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def load_5year(symbol: str, session: str = "NY AM IB", years: int = 5):
    """Load ib_confluence for last N years (calendar)."""
    path = DERIVED / f"ib_confluence_{symbol}.parquet"
    df = pd.read_parquet(path)
    df = df[df["session_slot"] == session].copy()
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    max_day = df["trading_day"].max()
    min_day = (max_day.to_period("M") - years * 12).to_timestamp()
    df = df[df["trading_day"] >= min_day].copy()
    if len(df) == 0:
        print(f"[5yr] {symbol} {session}: 0 sessions. Aborting.")
        return df
    print(f"[5yr] {symbol} {session}: {len(df)} sessions from {df['trading_day'].min().date()} to {df['trading_day'].max().date()}")
    return df


def load_play_detail_5year(symbol: str, session: str = "NY AM IB", years: int = 5):
    """Load ib_play_detail for last N years (calendar)."""
    path = DERIVED / f"ib_play_detail_{symbol}.parquet"
    if not path.exists():
        return pd.DataFrame()
    p = pd.read_parquet(path)
    p = p[p["session_slot"] == session].copy()
    p["trading_day"] = pd.to_datetime(p["trading_day"])
    max_day = p["trading_day"].max()
    min_day = (max_day.to_period("M") - years * 12).to_timestamp()
    p = p[p["trading_day"] >= min_day].copy()
    return p


def edge_by_year(plays: pd.DataFrame, label: str = "5-year"):
    """Per-year E[R] / WR / PF for each play (active trades only)."""
    print(f"\n=== Edge by Year ({label}) ===")
    plays = plays.copy()
    plays["year"] = plays["trading_day"].dt.year

    for play in [1, 2, 3]:
        print(f"\n  Play {play}:")
        print(f"  {'Year':<8} {'N':>6} {'Active':>7} {'Cov%':>6} {'WR':>7} {'E[R]':>9} {'PF':>6} {'95% CI (E[R])':>20}")
        g = plays[plays["play"] == play]
        for year in sorted(g["year"].unique()):
            gy = g[g["year"] == year]
            n = len(gy)
            active = gy[gy["result"] != 0]
            n_a = len(active)
            if n_a == 0:
                print(f"  {year:<8} {n:>6} {0:>7} {'':>6} {'':>7} {'':>9} {'':>6}")
                continue
            wins = (active["result"] == 1).sum()
            wr = 100 * wins / n_a
            exp = active["realized_r"].mean()
            pf_pos = active[active["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            # Bootstrap CI on E[R]: resample active realized_r
            rng = np.random.default_rng(42)
            boots = rng.choice(active["realized_r"].values, size=(2000, n_a), replace=True).mean(axis=1)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            sig = "+" if exp > 0 else "-"
            print(f"  {year:<8} {n:>6} {n_a:>7} {100*n_a/n:>5.0f}% {wr:>6.1f}% {sig}{abs(exp):>8.4f} {pf:>5.2f} [{lo:>+.4f}, {hi:>+.4f}]")
        # All-time row
        active_all = g[g["result"] != 0]
        n_all = len(active_all)
        if n_all > 0:
            exp_all = active_all["realized_r"].mean()
            pf_pos = active_all[active_all["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active_all[active_all["result"] == -1]["realized_r"].sum())
            pf_all = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            wr_all = 100 * (active_all["result"] == 1).sum() / n_all
            print(f"  {'ALL':<8} {len(g):>6} {n_all:>7} {100*n_all/len(g):>5.0f}% {wr_all:>6.1f}% {exp_all:>+8.4f} {pf_all:>5.2f}")


def edge_by_dow(plays: pd.DataFrame, label: str = "5-year"):
    """Per-day-of-week E[R] / WR / PF for each play."""
    print(f"\n=== Edge by Day of Week ({label}) ===")
    plays = plays.copy()
    plays["dow"] = plays["trading_day"].dt.dayofweek

    for play in [1, 2, 3]:
        print(f"\n  Play {play}:")
        print(f"  {'DOW':<6} {'N':>6} {'Active':>7} {'WR':>7} {'E[R]':>9} {'PF':>6}")
        g = plays[plays["play"] == play]
        for dow in sorted(g["dow"].unique()):
            gd = g[g["dow"] == dow]
            active = gd[gd["result"] != 0]
            n_a = len(active)
            if n_a < 20:
                print(f"  {DOW_NAMES.get(dow, str(dow)):<6} {len(gd):>6} {n_a:>7} {'(insufficient)':>7}")
                continue
            wins = (active["result"] == 1).sum()
            wr = 100 * wins / n_a
            exp = active["realized_r"].mean()
            pf_pos = active[active["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            sig = "+" if exp > 0 else "-"
            print(f"  {DOW_NAMES.get(dow, str(dow)):<6} {len(gd):>6} {n_a:>7} {wr:>6.1f}% {sig}{abs(exp):>8.4f} {pf:>5.2f}")


def edge_by_month(plays: pd.DataFrame, label: str = "5-year"):
    """Per-month E[R] / WR / PF for each play (aggregated across years)."""
    print(f"\n=== Edge by Month ({label}, aggregated across years) ===")
    plays = plays.copy()
    plays["month"] = plays["trading_day"].dt.month

    for play in [1, 2, 3]:
        print(f"\n  Play {play}:")
        print(f"  {'Month':<6} {'N':>6} {'Active':>7} {'WR':>7} {'E[R]':>9} {'PF':>6}")
        g = plays[plays["play"] == play]
        for month in sorted(g["month"].unique()):
            gm = g[g["month"] == month]
            active = gm[gm["result"] != 0]
            n_a = len(active)
            if n_a < 20:
                print(f"  {MONTH_NAMES.get(month, str(month)):<6} {len(gm):>6} {n_a:>7} {'(insufficient)':>7}")
                continue
            wins = (active["result"] == 1).sum()
            wr = 100 * wins / n_a
            exp = active["realized_r"].mean()
            pf_pos = active[active["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            sig = "+" if exp > 0 else "-"
            print(f"  {MONTH_NAMES.get(month, str(month)):<6} {len(gm):>6} {n_a:>7} {wr:>6.1f}% {sig}{abs(exp):>8.4f} {pf:>5.2f}")


def edge_by_target(plays: pd.DataFrame, label: str = "5-year"):
    """Per (play, target_lvl) E[R] over 5 years - the granular truth."""
    print(f"\n=== Edge by (Play, Target Level) - 5 year granular ===")
    print(f"  {'Play':>6} {'Target':>7} {'N_active':>9} {'WR':>7} {'E[R]':>9} {'PF':>6} {'95% CI (E[R])':>20}")
    for play in [1, 2, 3]:
        for lvl in sorted(plays[plays["play"] == play]["target_lvl"].unique()):
            g = plays[(plays["play"] == play) & (plays["target_lvl"] == lvl)]
            active = g[g["result"] != 0]
            n_a = len(active)
            if n_a < 50:
                print(f"  {play:>6} {lvl:>6}x {n_a:>9} {'(insufficient N)':>20}")
                continue
            wins = (active["result"] == 1).sum()
            wr = 100 * wins / n_a
            exp = active["realized_r"].mean()
            pf_pos = active[active["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            rng = np.random.default_rng(42)
            boots = rng.choice(active["realized_r"].values, size=(2000, n_a), replace=True).mean(axis=1)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            sig = "+" if exp > 0 else "-"
            print(f"  {play:>6} {lvl:>6}x {n_a:>9} {wr:>6.1f}% {sig}{abs(exp):>8.4f} {pf:>5.2f} [{lo:>+.4f}, {hi:>+.4f}]")


def rule1_5year(df: pd.DataFrame, n_boot: int = 2000):
    """Rule 1 direction trigger over 5 years with bootstrap CI."""
    print(f"\n=== Rule 1: 5-Year Direction Trigger ===")
    cases = [
        ("Rule 1A: low first (alone)", df["bias_formation_firstreach"] == 1, 1),
        ("Rule 1A: + close in top 25%", (df["bias_formation_firstreach"] == 1) & (df["ib_close_position"] >= EDGEFUL_TOP25), 1),
        ("Rule 1B: high first (alone)", df["bias_formation_firstreach"] == -1, -1),
        ("Rule 1B: + close in bot 25%", (df["bias_formation_firstreach"] == -1) & (df["ib_close_position"] <= EDGEFUL_BOT25), -1),
    ]
    print(f"  {'Condition':<40} {'N':>6} {'Hit':>5} {'%':>7} {'95% CI':>18} {'vs 50%?':>10}")
    print(f"  {'-'*90}")
    for label, mask, target_dir in cases:
        sub = df[mask]
        n = len(sub)
        if n == 0:
            continue
        hits = (sub["first_break_dir"] == target_dir).sum()
        pct = 100 * hits / n
        lo, hi = bootstrap_ci(hits, n, n_boot)
        sig = "YES (sig)" if lo > 50 else ("maybe" if hi > 50 else "no")
        print(f"  {label:<40} {n:>6} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}] {sig:>10}")


def rule3_5year(df: pd.DataFrame, n_boot: int = 2000):
    """Rule 3 clock filter over 5 years with bootstrap CI."""
    print(f"\n=== Rule 3: 5-Year Clock Filter ===")
    broke = df[df["first_break_dir"] != 0].copy()
    n_total = len(broke)
    if n_total == 0:
        print("  No breaks.")
        return
    early = broke[broke["first_break_minutes"] < NOON_BREAK_MINUTES]
    late = broke[broke["first_break_minutes"] >= NOON_BREAK_MINUTES]
    print(f"  {'Condition':<40} {'N':>6} {'Hold':>5} {'%':>7} {'95% CI':>18}")
    print(f"  {'-'*80}")
    for label, sub in [("Baseline (any break)", broke), ("Break before 12:00", early), ("Break after 12:00", late)]:
        n = len(sub)
        if n == 0:
            continue
        hits = (~sub["double_break"].fillna(False)).sum()
        pct = 100 * hits / n
        lo, hi = bootstrap_ci(hits, n, n_boot)
        print(f"  {label:<40} {n:>6} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="NQ1,ES1")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    print(f"\n{'#'*70}")
    print(f"# PHASE C: 5-Year Edge Survival Analysis")
    print(f"# Scope: {','.join(symbols)} NY AM IB, {args.years} years, n_boot={args.n_boot}")
    print(f"{'#'*70}")

    for sym in symbols:
        print(f"\n{'='*70}")
        print(f"SYMBOL: {sym}")
        print(f"{'='*70}")

        # Load 5-year confluence + play detail
        df = load_5year(sym, "NY AM IB", years=args.years)
        if len(df) == 0:
            continue
        df = add_missing_fields(df)
        plays = load_play_detail_5year(sym, "NY AM IB", years=args.years)
        print(f"  Play detail rows ({args.years}yr): {len(plays)}")

        # Baseline
        baseline_table(df)

        # Rule 1 + Rule 3 over 5 years
        rule1_5year(df, args.n_boot)
        rule3_5year(df, args.n_boot)

        # Edge survival: per-year, per-DOW, per-month
        if len(plays) > 0:
            edge_by_year(plays, f"{args.years}-year {sym}")
            edge_by_dow(plays, f"{args.years}-year {sym}")
            edge_by_month(plays, f"{args.years}-year {sym}")
            edge_by_target(plays, f"{args.years}-year {sym}")

    print(f"\n{'#'*70}")
    print(f"# PHASE C COMPLETE")
    print(f"{'#'*70}")


if __name__ == "__main__":
    main()