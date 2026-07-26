"""IB Statistics Pilot - Phase B: Condition stacks + bootstrap CIs + ES1 cross-check.

Adds three features on top of the Phase A pilot:
  1. Cumulative condition stacks (Edgeful-style: each row adds a condition, reports N + hit rate)
  2. Bootstrap 95% CI on Rule 1 hit rate (is 89% real or within noise at N=83?)
  3. ES1 cross-check (does the Rule 3 inversion hold on ES1 or is it NQ1-specific?)

Usage:
    python -m scripts.edgeful.ib_pilot_stacks
    python -m scripts.edgeful.ib_pilot_stacks --months 12 --symbols NQ1,ES1
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.edgeful.ib_pilot_stats import (
    DERIVED, EDGEFUL_TOP25, EDGEFUL_BOT25, NOON_BREAK_MINUTES,
    load_pilot, add_missing_fields,
)


# ── 1. Cumulative condition stacks (Edgeful-style) ──────────────────────────

def condition_stack(df: pd.DataFrame, conditions: List[Tuple[str, pd.Series]],
                    outcome_col: str, outcome_val, label: str):
    """Build a cumulative condition stack table.

    Each row adds one condition (ANDed with the previous), reports N + hit rate.
    Mirrors the Edgeful playbook table format.

    Parameters
    ----------
    df : DataFrame
    conditions : list of (name, mask) pairs - masks are boolean Series aligned to df
    outcome_col : str - column to check (e.g. "first_break_dir")
    outcome_val : int - value that counts as a "hit" (e.g. 1 for high-break)
    label : str - rule label for the header
    """
    print(f"\n  {label}")
    print(f"  {'Condition':<55} {'N':>5} {'Hit':>5} {'%':>7} {'dvs prev':>9}")
    prev_pct = None
    combined = pd.Series(True, index=df.index)
    for name, mask in conditions:
        combined = combined & mask
        n = combined.sum()
        if n == 0:
            print(f"  {name:<55} {0:>5} {0:>5} {'':>7} {'':>9}")
            continue
        hits = (df.loc[combined, outcome_col] == outcome_val).sum()
        pct = 100 * hits / n
        delta = f"{pct - prev_pct:+.1f}pp" if prev_pct is not None else ""
        print(f"  {name:<55} {n:>5} {hits:>5} {pct:>6.1f}% {delta:>9}")
        prev_pct = pct


def rule1_stacks(df: pd.DataFrame):
    """Rule 1 cumulative condition stacks (long + short side)."""
    print("\n=== Rule 1: Cumulative Condition Stacks ===")

    # Rule 1A: low formed first -> + close in top 25% -> predict high breaks first
    low_first = df["bias_formation_firstreach"] == 1
    top25 = df["ib_close_position"] >= EDGEFUL_TOP25
    print("\n  Rule 1A (long-side: low first -> high breaks first)")
    condition_stack(
        df,
        [("Low formed first (alone)", low_first),
         ("+ close in top 25% of range", top25)],
        "first_break_dir", 1, "Rule 1A"
    )

    # Rule 1B: high formed first -> + close in bottom 25% -> predict low breaks first
    high_first = df["bias_formation_firstreach"] == -1
    bot25 = df["ib_close_position"] <= EDGEFUL_BOT25
    print("\n  Rule 1B (short-side: high first -> low breaks first)")
    condition_stack(
        df,
        [("High formed first (alone)", high_first),
         ("+ close in bottom 25% of range", bot25)],
        "first_break_dir", -1, "Rule 1B"
    )

    # Rule 2A: green IB -> + large IB -> predict green day (outcome)
    green_ib = df["ib_candle_color"] == "green"
    large_ib = df["ib_size_bucket_edgeful"].isin(["large", "huge"])
    print("\n  Rule 2A (green IB + large -> green day outcome)")
    condition_stack(
        df,
        [("Green IB candle (alone)", green_ib),
         ("+ IB size large/huge (>0.7%)", large_ib)],
        "day_color_outcome", "green", "Rule 2A"
    )

    # Rule 3A: break before 12:00 -> + IB candle green -> predict no double break
    broke = df["first_break_dir"] != 0
    early = df["first_break_minutes"] < NOON_BREAK_MINUTES
    green = df["ib_candle_color"] == "green"
    print("\n  Rule 3A (early break -> no double break / hold)")
    condition_stack(
        df,
        [("Any break (baseline)", broke),
         ("+ break before 12:00", early),
         ("+ IB candle green", green)],
        "double_break", False, "Rule 3A"
    )

    # Rule 3B: break after 12:00 -> + prior day red -> predict double break (fade)
    late = df["first_break_minutes"] >= NOON_BREAK_MINUTES
    prior_red = df["prior_day_result"] == -1
    print("\n  Rule 3B (late break -> double break / fade)")
    condition_stack(
        df,
        [("Any break (baseline)", broke),
         ("+ break after 12:00", late),
         ("+ prior day red", prior_red)],
        "double_break", True, "Rule 3B"
    )


# ── 2. Bootstrap 95% CI on hit rates ─────────────────────────────────────────

def bootstrap_ci(hits: int, n: int, n_boot: int = 2000, ci: float = 0.95,
                 seed: int = 42) -> Tuple[float, float]:
    """Bootstrap CI for a proportion (hits/n).

    Resamples n Bernoulli trials with p=hits/n, n_boot times, takes percentiles.
    """
    if n == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    p = hits / n
    # Vectorized: each row is a bootstrap sample of n Bernoulli(p) trials
    samples = rng.binomial(n, p, size=n_boot) / n * 100
    lo = float(np.percentile(samples, (1 - ci) / 2 * 100))
    hi = float(np.percentile(samples, (1 + ci) / 2 * 100))
    return (lo, hi)


def rule1_significance(df: pd.DataFrame, n_boot: int = 2000):
    """Bootstrap 95% CI on Rule 1A/1B hit rates."""
    print("\n=== Rule 1: Bootstrap 95% CI Significance Test ===")
    print(f"  (n_boot={n_boot} resamples per condition)")

    cases = [
        ("Rule 1A: low first (alone)", df["bias_formation_firstreach"] == 1, 1),
        ("Rule 1A: + close in top 25%", (df["bias_formation_firstreach"] == 1) & (df["ib_close_position"] >= EDGEFUL_TOP25), 1),
        ("Rule 1B: high first (alone)", df["bias_formation_firstreach"] == -1, -1),
        ("Rule 1B: + close in bot 25%", (df["bias_formation_firstreach"] == -1) & (df["ib_close_position"] <= EDGEFUL_BOT25), -1),
    ]

    print(f"\n  {'Condition':<40} {'N':>5} {'Hit':>5} {'%':>7} {'95% CI':>18} {'vs 50%?':>10}")
    print(f"  {'-'*90}")
    for label, mask, target_dir in cases:
        sub = df[mask]
        n = len(sub)
        if n == 0:
            continue
        hits = (sub["first_break_dir"] == target_dir).sum()
        pct = 100 * hits / n
        lo, hi = bootstrap_ci(hits, n, n_boot)
        # Is the CI entirely above 50% (significant directional prediction)?
        sig = "YES (sig)" if lo > 50 else ("maybe" if hi > 50 else "no")
        print(f"  {label:<40} {n:>5} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}] {sig:>10}")

    # Edgeful YM reference for comparison
    print(f"\n  Edgeful YM reference (128 sessions):")
    print(f"    Rule 1A: 72.7% (N=66) -> 97.4% (N=38)")
    print(f"    Rule 1B: 77.4% (N=62) -> 97.2% (N=36)")


def rule3_significance(df: pd.DataFrame, n_boot: int = 2000):
    """Bootstrap 95% CI on Rule 3 hold/fade rates."""
    print("\n=== Rule 3: Bootstrap 95% CI Significance Test ===")
    broke = df[df["first_break_dir"] != 0].copy()
    n_total = len(broke)
    if n_total == 0:
        print("  No breaks.")
        return

    early = broke[broke["first_break_minutes"] < NOON_BREAK_MINUTES]
    late = broke[broke["first_break_minutes"] >= NOON_BREAK_MINUTES]

    print(f"\n  {'Condition':<40} {'N':>5} {'Hold':>5} {'%':>7} {'95% CI':>18} {'vs base?':>10}")
    print(f"  {'-'*90}")

    # Baseline
    hits = (~broke["double_break"].fillna(False)).sum()
    pct = 100 * hits / n_total
    lo, hi = bootstrap_ci(hits, n_total, n_boot)
    print(f"  {'Baseline (any break)':<40} {n_total:>5} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}] {'':>10}")

    # Early
    n = len(early)
    if n > 0:
        hits = (~early["double_break"].fillna(False)).sum()
        pct = 100 * hits / n
        lo, hi = bootstrap_ci(hits, n, n_boot)
        sig = "YES (sig)" if lo > 50 else ("maybe" if hi > 50 else "no")
        print(f"  {'Break before 12:00':<40} {n:>5} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}] {sig:>10}")

    # Late
    n = len(late)
    if n > 0:
        hits = (~late["double_break"].fillna(False)).sum()
        pct = 100 * hits / n
        lo, hi = bootstrap_ci(hits, n, n_boot)
        sig = "YES (sig)" if lo > 50 else ("maybe" if hi > 50 else "no")
        print(f"  {'Break after 12:00':<40} {n:>5} {hits:>5} {pct:>6.1f}% [{lo:>5.1f}, {hi:>5.1f}] {sig:>10}")

    print(f"\n  Edgeful YM reference: 85.8% baseline, 94.6% early, 42.9% late fade (57.1% hold)")
    print(f"  NQ1 finding: late breaks hold MORE than early (inverted from YM)")


# ── 3. ES1 cross-check ───────────────────────────────────────────────────────

def cross_check_symbol(symbol: str, months: int = 12, n_boot: int = 2000):
    """Run Rule 1 + Rule 3 on a symbol and print comparison."""
    print(f"\n{'='*70}")
    print(f"CROSS-CHECK: {symbol} NY AM IB ({months} months)")
    print(f"{'='*70}")
    df = load_pilot(symbol, "NY AM IB", months=months)
    if len(df) == 0:
        print(f"  No data for {symbol}.")
        return None
    df = add_missing_fields(df)
    rule1_significance(df, n_boot)
    rule3_significance(df, n_boot)
    return df


def compare_symbols(nq1_df, es1_df):
    """Side-by-side comparison of NQ1 vs ES1."""
    print(f"\n{'='*70}")
    print(f"NQ1 vs ES1 COMPARISON (Rule 1 + Rule 3)")
    print(f"{'='*70}")

    print(f"\n  {'Metric':<45} {'NQ1':>10} {'ES1':>10} {'Same?':>8}")
    print(f"  {'-'*75}")

    for label, nq_val, es_val in [
        ("Total sessions", len(nq1_df), len(es1_df) if es1_df is not None else 0),
        ("Single break %", 100*(~nq1_df["double_break"].fillna(False) & (nq1_df["first_break_dir"]!=0)).sum()/len(nq1_df),
         100*(~es1_df["double_break"].fillna(False) & (es1_df["first_break_dir"]!=0)).sum()/len(es1_df) if es1_df is not None else 0),
        ("Double break %", 100*nq1_df["double_break"].fillna(False).sum()/len(nq1_df),
         100*es1_df["double_break"].fillna(False).sum()/len(es1_df) if es1_df is not None else 0),
    ]:
        match = "yes" if abs(nq_val - es_val) < 5 else "no"
        print(f"  {label:<45} {nq_val:>9.1f}% {es_val:>9.1f}% {match:>8}")

    # Rule 1A stacked
    for label, mask_fn, target in [
        ("Rule 1A: low first -> high breaks", lambda d: (d["bias_formation_firstreach"]==1) & (d["ib_close_position"]>=EDGEFUL_TOP25), 1),
        ("Rule 1B: high first -> low breaks", lambda d: (d["bias_formation_firstreach"]==-1) & (d["ib_close_position"]<=EDGEFUL_BOT25), -1),
    ]:
        nq_sub = nq1_df[mask_fn(nq1_df)]
        nq_n = len(nq_sub)
        nq_hits = (nq_sub["first_break_dir"] == target).sum()
        nq_pct = 100*nq_hits/nq_n if nq_n else 0
        nq_lo, nq_hi = bootstrap_ci(nq_hits, nq_n, 1000)

        if es1_df is not None:
            es_sub = es1_df[mask_fn(es1_df)]
            es_n = len(es_sub)
            es_hits = (es_sub["first_break_dir"] == target).sum()
            es_pct = 100*es_hits/es_n if es_n else 0
            es_lo, es_hi = bootstrap_ci(es_hits, es_n, 1000)
            overlap = "OVERLAP" if (nq_lo <= es_hi and es_lo <= nq_hi) else "DIFFERENT"
            print(f"  {label:<45} {nq_pct:>9.1f}% {es_pct:>9.1f}% {overlap:>8}  NQ1 N={nq_n} ES1 N={es_n}")
            print(f"  {'  95% CI':<45} [{nq_lo:>4.1f}, {nq_hi:>4.1f}] [{es_lo:>4.1f}, {es_hi:>4.1f}]")
        else:
            print(f"  {label:<45} {nq_pct:>9.1f}% {'N/A':>10}  NQ1 N={nq_n}")

    # Rule 3 inversion check
    print(f"\n  Rule 3 (clock filter) - does the NQ1 inversion hold on ES1?")
    for sym, d in [("NQ1", nq1_df), ("ES1", es1_df)]:
        if d is None or len(d) == 0:
            continue
        broke = d[d["first_break_dir"] != 0]
        early = broke[broke["first_break_minutes"] < NOON_BREAK_MINUTES]
        late = broke[broke["first_break_minutes"] >= NOON_BREAK_MINUTES]
        e_hold = 100*(~early["double_break"].fillna(False)).sum()/len(early) if len(early) else 0
        l_hold = 100*(~late["double_break"].fillna(False)).sum()/len(late) if len(late) else 0
        inverted = "YES (inverted)" if l_hold > e_hold else "no (normal)"
        print(f"  {sym}: early hold={e_hold:.1f}% (N={len(early)})  late hold={l_hold:.1f}% (N={len(late)})  -> {inverted}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--symbols", default="NQ1,ES1")
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    # ── NQ1: condition stacks + significance ──
    print(f"\n{'#'*70}")
    print(f"# PHASE B: Condition Stacks + Bootstrap CIs + ES1 Cross-Check")
    print(f"# Scope: {','.join(symbols)} NY AM IB, {args.months} months, n_boot={args.n_boot}")
    print(f"{'#'*70}")

    nq1_df = None
    es1_df = None

    for sym in symbols:
        df = cross_check_symbol(sym, months=args.months, n_boot=args.n_boot)
        if sym == "NQ1":
            nq1_df = df
        elif sym == "ES1":
            es1_df = df

    # ── NQ1 condition stacks (cumulative) ──
    if nq1_df is not None and len(nq1_df) > 0:
        rule1_stacks(nq1_df)

    # ── Cross-symbol comparison ──
    if nq1_df is not None and es1_df is not None:
        compare_symbols(nq1_df, es1_df)
    elif nq1_df is not None:
        print(f"\n  (ES1 not available - skipping cross-check)")

    print(f"\n{'#'*70}")
    print(f"# PHASE B COMPLETE")
    print(f"{'#'*70}")


if __name__ == "__main__":
    main()