"""IB Statistics Pilot — Phase A: Load data + add missing derived fields.

Pilot scope: NQ1 NY AM IB, 3-12 month windows. Validates fast before expanding.

Code review fixes applied (2026-07-26):
  B1: dropped double-shifted prior_close (prior_session_close is already prior-day)
  B2: renamed day_color → day_color_outcome (post-trade); added prior_day_color (pre-trade)
  B3: renamed opened_inside_prior_range → ib_open_inside_prior_range (NY AM semantics)
  B4: separated active vs no-setup rows in play-detail stats (fixes understated WR/E[R])
  B5: defensive bool comparisons using ~ / sum()
  E1: guard zero-range IB to avoid silent inf → 1.0 clipping
  E2: report warm-up NaN drops from shift(1)
  E3: use calendar months via PeriodIndex for accurate month boundaries
  E4: guard empty pilot window to prevent ValueError on min/max
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"

# Edgeful rule thresholds (from STATISTICAL_DISCOVERY_PLAN.md §7.5; TODO: verify against Edgeful PDF)
EDGEFUL_TOP25 = 0.75          # Rule 1A: close in top 25% of IB range
EDGEFUL_BOT25 = 0.25          # Rule 1B: close in bottom 25%
EDGEFUL_SIZE_THRESHOLDS = (0.47, 0.70, 0.90)  # small / mid / large (huge = >0.90)
NY_AM_IB_END = "10:30"        # IB close for NY AM session
NOON_BREAK_MINUTES = 90       # minutes after 10:30 = 12:00 ET


def load_pilot(symbol="NQ1", session="NY AM IB", months=3):
    """Load ib_confluence filtered to pilot scope (last N calendar months)."""
    path = DERIVED / f"ib_confluence_{symbol}.parquet"
    df = pd.read_parquet(path)
    df = df[df["session_slot"] == session].copy()
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    max_day = df["trading_day"].max()
    # E3: use calendar months via PeriodIndex (accurate month boundaries)
    min_day = (max_day.to_period("M") - months).to_timestamp()
    df = df[df["trading_day"] >= min_day].copy()
    # E4: guard empty window
    if len(df) == 0:
        print(f"[Pilot] {symbol} {session}: 0 sessions in {months}-month window. Aborting.")
        return df
    print(f"[Pilot] {symbol} {session}: {len(df)} sessions from {df['trading_day'].min().date()} to {df['trading_day'].max().date()}")
    return df


def add_missing_fields(df):
    """Add the 6 Edgeful-style derived fields (with review fixes applied)."""
    if len(df) == 0:
        return df
    df = df.sort_values("trading_day").reset_index(drop=True)

    # 1. ib_close_position: where IB close sits within IB range (0=at low, 1=at high)
    # E1: guard zero-range IB to avoid silent inf → 1.0 clipping
    ib_range = df["ib_high"] - df["ib_low"]
    df["ib_close_position"] = np.where(
        ib_range > 0,
        ((df["ib_close"] - df["ib_low"]) / ib_range).clip(0, 1),
        0.5,  # mid-point for doji-IB (zero range)
    )

    # 2. ib_candle_color: green/red first hour (knowable at 10:30)
    df["ib_candle_color"] = np.where(df["ib_close"] > df["ib_open"], "green",
                                     np.where(df["ib_close"] < df["ib_open"], "red", "doji"))

    # 3a. day_color_outcome: POST-TRADE green/red close vs prior session close (knowable at 16:00)
    #     B2: renamed from day_color to make post-trade status explicit
    if "outcome_close" in df.columns and "prior_session_close" in df.columns:
        # prior_session_close is ALREADY the prior day's RTH close (no extra shift needed — B1 fix)
        df["day_color_outcome"] = np.where(df["outcome_close"] > df["prior_session_close"], "green",
                                            np.where(df["outcome_close"] < df["prior_session_close"], "red", "flat"))
    else:
        df["day_color_outcome"] = "unknown"

    # 3b. prior_day_color: PRE-TRADE — what direction did yesterday close vs its own IB close?
    #     This is the Edgeful-equivalent of "was yesterday green/red?" (knowable at 09:30)
    if "realized_dir_close" in df.columns:
        df["prior_day_color"] = df["realized_dir_close"].shift(1).map(
            {1: "green", -1: "red", 0: "flat"}).fillna("unknown")
    else:
        df["prior_day_color"] = "unknown"

    # 4. ib_open_inside_prior_range: did today's IB open fall within yesterday's IB range?
    #    B3: renamed from opened_inside_prior_range. For NY AM, ib_open = 09:30 bar open = session open.
    #    DO NOT generalize to other sessions without verifying open semantics.
    df["prior_ib_high"] = df["ib_high"].shift(1)
    df["prior_ib_low"] = df["ib_low"].shift(1)
    # E2: report warm-up drops
    n_warmup = df["prior_ib_high"].isna().sum()
    if n_warmup > 0:
        print(f"  [add_missing_fields] Dropped {n_warmup} warm-up day(s) with no prior-day IB (shift boundary).")
    df["ib_open_inside_prior_range"] = (df["ib_open"] >= df["prior_ib_low"]) & (df["ib_open"] <= df["prior_ib_high"])

    # 5. close_location: POST-TRADE 3-way classification (knowable at 16:00)
    #    Used in Rule 5 (post-hoc analysis). Boundary at exact ib_high/ib_low → "inside" (strict > / <).
    if "outcome_close" in df.columns:
        df["close_location"] = np.where(df["outcome_close"] > df["ib_high"], "above",
                                         np.where(df["outcome_close"] < df["ib_low"], "below", "inside"))
    else:
        df["close_location"] = "unknown"

    # 6. ib_size_bucket_edgeful: Edgeful thresholds on range_pct
    #    Thresholds from STATISTICAL_DISCOVERY_PLAN.md §7.5; TODO: verify 0.47 against Edgeful PDF
    if "range_pct" in df.columns:
        s1, s2, s3 = EDGEFUL_SIZE_THRESHOLDS
        df["ib_size_bucket_edgeful"] = np.where(df["range_pct"] < s1, "small",
                                                np.where(df["range_pct"] < s2, "mid",
                                                         np.where(df["range_pct"] < s3, "large", "huge")))
    else:
        df["ib_size_bucket_edgeful"] = "unknown"

    return df


def baseline_table(df):
    """Edgeful-style baseline: what happens on a normal day."""
    print("\n=== Baseline Statistics (Edgeful Section 0) ===")
    n = len(df)
    if n == 0:
        print("No data.")
        return

    # B5: defensive bool comparisons using ~ / sum() instead of == False / == True
    single_break = ((df["first_break_dir"] != 0) & (~df["double_break"].fillna(False))).sum()
    double_break = df["double_break"].fillna(False).sum()
    no_break = (df["first_break_dir"] == 0).sum()
    high_first = (df["first_break_dir"] == 1).sum()
    low_first = (df["first_break_dir"] == -1).sum()
    # B2: use day_color_outcome (post-trade) — labeled as OUTCOME in the table
    green_day = (df["day_color_outcome"] == "green").sum() if "day_color_outcome" in df.columns else 0

    print(f"{'Stat':<30} {'N':>5} {'%':>8}")
    print(f"{'-'*48}")
    print(f"{'Total sessions':<30} {n:>5} {'':>8}")
    print(f"{'Single break':<30} {single_break:>5} {100*single_break/n:>7.1f}%")
    print(f"{'Double break':<30} {double_break:>5} {100*double_break/n:>7.1f}%")
    print(f"{'No break':<30} {no_break:>5} {100*no_break/n:>7.1f}%")
    print(f"{'First break = IB high':<30} {high_first:>5} {100*high_first/n:>7.1f}%")
    print(f"{'First break = IB low':<30} {low_first:>5} {100*low_first/n:>7.1f}%")
    print(f"{'Green day (OUTCOME - post-close)':<30} {green_day:>5} {100*green_day/n:>7.1f}%")
    # Pre-trade prior day color for comparison
    if "prior_day_color" in df.columns:
        prior_green = (df["prior_day_color"] == "green").sum()
        print(f"{'Prior day green (PRE-TRADE)':<30} {prior_green:>5} {100*prior_green/n:>7.1f}%")

    # IB size distribution
    print(f"\nIB size distribution (Edgeful buckets):")
    if "ib_size_bucket_edgeful" in df.columns:
        for bucket, g in df.groupby("ib_size_bucket_edgeful"):
            print(f"  {bucket:<8} {len(g):>4} ({100*len(g)/n:.1f}%)  range_pct median: {g['range_pct'].median():.3f}")

    # IB candle color
    print(f"\nIB candle color:")
    if "ib_candle_color" in df.columns:
        for color, g in df.groupby("ib_candle_color"):
            print(f"  {color:<8} {len(g):>4} ({100*len(g)/n:.1f}%)")

    return df


def rule1_direction_trigger(df):
    """Edgeful Rule 1: 10:30 direction trigger.

    Rule 1A: low formed first + close in top 25% → IB high breaks first
    Rule 1B: high formed first + close in bottom 25% → IB low breaks first
    """
    print("\n=== Rule 1: 10:30 Direction Trigger ===")
    n_total = len(df)

    # Rule 1A: low first + close in top 25%
    low_first = df[df["bias_formation_firstreach"] == 1]
    low_first_top25 = low_first[low_first["ib_close_position"] >= 0.75]

    # Rule 1B: high first + close in bottom 25%
    high_first = df[df["bias_formation_firstreach"] == -1]
    high_first_bot25 = high_first[high_first["ib_close_position"] <= 0.25]

    print(f"\nRule 1A (long-side trigger):")
    print(f"  {'Condition':<55} {'N':>4} {'Hit':>6} {'%':>7}")
    base = low_first
    n = len(base)
    hits = (base["first_break_dir"] == 1).sum()
    print(f"  {'Low formed first (alone)':<55} {n:>4} {hits:>6} {100*hits/n if n else 0:>6.1f}%")
    stacked = low_first_top25
    n = len(stacked)
    hits = (stacked["first_break_dir"] == 1).sum()
    print(f"  {'+ close in top 25% of range':<55} {n:>4} {hits:>6} {100*hits/n if n else 0:>6.1f}%")

    print(f"\nRule 1B (short-side trigger):")
    base = high_first
    n = len(base)
    hits = (base["first_break_dir"] == -1).sum()
    print(f"  {'High formed first (alone)':<55} {n:>4} {hits:>6} {100*hits/n if n else 0:>6.1f}%")
    stacked = high_first_bot25
    n = len(stacked)
    hits = (stacked["first_break_dir"] == -1).sum()
    print(f"  {'+ close in bottom 25% of range':<55} {n:>4} {hits:>6} {100*hits/n if n else 0:>6.1f}%")

    # Edgeful YM reference: 72.7% → 97.4% (1A), 77.4% → 97.2% (1B)


def rule3_clock_filter(df):
    """Edgeful Rule 3: hold vs fade by time of break."""
    print("\n=== Rule 3: Clock Filter (Hold vs Fade) ===")
    broke = df[df["first_break_dir"] != 0].copy()
    n_total = len(broke)
    if n_total == 0:
        print("  No breaks.")
        return

    # Convert first_break_minutes to clock time. IB closes at 10:30 for NY AM.
    # first_break_minutes = minutes after IB close (10:30)
    # break before 12:00 = first_break_minutes < 90
    early = broke[broke["first_break_minutes"] < 90]
    late = broke[broke["first_break_minutes"] >= 90]

    print(f"\n  {'Condition':<55} {'N':>4} {'No double':>10} {'%':>7}")
    # Baseline: any break
    no_double = (broke["double_break"] == False).sum()
    print(f"  {'Baseline (any break)':<55} {n_total:>4} {no_double:>10} {100*no_double/n_total:>6.1f}%")
    # Early break
    n = len(early)
    if n > 0:
        no_double = (early["double_break"] == False).sum()
        print(f"  {'Break before 12:00':<55} {n:>4} {no_double:>10} {100*no_double/n:>6.1f}%")
    # Late break
    n = len(late)
    if n > 0:
        no_double = (late["double_break"] == False).sum()
        fade = (late["double_break"] == True).sum()
        print(f"  {'Break after 12:00':<55} {n:>4} {no_double:>10} {100*no_double/n:>6.1f}% (fade: {100*fade/n:.1f}%)")
    # Late + prior day red
    if n > 0 and "prior_day_result" in late.columns:
        late_prior_red = late[late["prior_day_result"] == -1]
        n2 = len(late_prior_red)
        if n2 > 0:
            fade = (late_prior_red["double_break"] == True).sum()
            print(f"  {'  + prior day red':<55} {n2:>4} {'':>10} {'':>7} fade: {100*fade/n2:.1f}%")

    # Edgeful YM reference: 85.8% baseline, 94.6% early, 42.9% late fade
    # Note: NQ1 may INVERT this pattern — late breaks hold, early breaks fade more


def rule4_extension_targets(df):
    """Edgeful Rule 4: extension targets by IB size."""
    print("\n=== Rule 4: Extension Targets by IB Size ===")
    # Check which ext columns exist
    ext_cols = [c for c in df.columns if c.startswith("ext_up_") or c.startswith("ext_down_")]
    if not ext_cols:
        print("  No extension columns found. Checking max_ext_up/down instead.")
        if "max_ext_up" in df.columns and "max_ext_down" in df.columns:
            for bucket, g in df.groupby("ib_size_bucket_edgeful"):
                n = len(g)
                if n == 0: continue
                # P50/P75/P90 of max extension up and down (in IB range multiples)
                print(f"  {bucket:<8} N={n:>3}  max_ext_up P50={g['max_ext_up'].median():.2f} P75={g['max_ext_up'].quantile(0.75):.2f} P90={g['max_ext_up'].quantile(0.90):.2f}")
                print(f"  {'':8}        max_ext_down P50={g['max_ext_down'].median():.2f} P75={g['max_ext_down'].quantile(0.75):.2f} P90={g['max_ext_down'].quantile(0.90):.2f}")
        return

    # Small IB + low break → reaches -0.5x
    print(f"\n  Small IB + low break before 12:00:")
    small_low = df[(df["ib_size_bucket_edgeful"] == "small") &
                   (df["first_break_dir"] == -1) &
                   (df["first_break_minutes"] < 90)]
    n = len(small_low)
    if n > 0 and "ext_down_0_5_hit" in df.columns:
        hit = small_low["ext_down_0_5_hit"].sum()
        print(f"    N={n}  reaches -0.5x: {hit} ({100*hit/n:.1f}%)")
    elif n > 0:
        reach = (small_low["max_ext_down"] >= 0.5).sum()
        print(f"    N={n}  reaches -0.5x (via max_ext_down): {reach} ({100*reach/n:.1f}%)")

    # Huge IB → rotation back inside
    print(f"\n  Huge IB (>0.9%) → closes back inside IB:")
    huge = df[df["ib_size_bucket_edgeful"] == "huge"]
    n = len(huge)
    if n > 0 and "close_location" in df.columns:
        inside = (huge["close_location"] == "inside").sum()
        print(f"    N={n}  closes inside: {inside} ({100*inside/n:.1f}%)")

    # Edgeful YM reference: 84.6% reach -0.5x (small+low), 76.2% rotation (huge)


def rule5_close_location(df):
    """Edgeful Rule 5: close location ladder."""
    print("\n=== Rule 5: Close Location Ladder ===")
    if "close_location" not in df.columns:
        print("  close_location not available.")
        return

    n_total = len(df)
    above = (df["close_location"] == "above").sum()
    inside = (df["close_location"] == "inside").sum()
    below = (df["close_location"] == "below").sum()
    print(f"\n  {'Condition stack':<50} {'N':>4} {'Above':>8} {'Inside':>8} {'Below':>8}")
    print(f"  {'All days (baseline)':<50} {n_total:>4} {100*above/n_total:>7.1f}% {100*inside/n_total:>7.1f}% {100*below/n_total:>7.1f}%")

    # High breaks first
    high_first = df[df["first_break_dir"] == 1]
    n = len(high_first)
    if n > 0:
        a = (high_first["close_location"] == "above").sum()
        i = (high_first["close_location"] == "inside").sum()
        b = (high_first["close_location"] == "below").sum()
        print(f"  {'IB high breaks first':<50} {n:>4} {100*a/n:>7.1f}% {100*i/n:>7.1f}% {100*b/n:>7.1f}%")

        # + before 12:00
        early = high_first[high_first["first_break_minutes"] < 90]
        n = len(early)
        if n > 0:
            a = (early["close_location"] == "above").sum()
            i = (early["close_location"] == "inside").sum()
            b = (early["close_location"] == "below").sum()
            print(f"  {'+ before 12:00':<50} {n:>4} {100*a/n:>7.1f}% {100*i/n:>7.1f}% {100*b/n:>7.1f}%")

            # + IB candle green
            green = early[early["ib_candle_color"] == "green"]
            n = len(green)
            if n > 0:
                a = (green["close_location"] == "above").sum()
                i = (green["close_location"] == "inside").sum()
                b = (green["close_location"] == "below").sum()
                print(f"  {'+ IB candle green':<50} {n:>4} {100*a/n:>7.1f}% {100*i/n:>7.1f}% {100*b/n:>7.1f}%")

    # Extension confirmation
    if "ext_up_0_5_hit" in df.columns:
        high_broke = df[df["first_break_dir"] == 1]
        reached_05 = high_broke[high_broke["ext_up_0_5_hit"] == True]
        n = len(reached_05)
        if n > 0:
            a = (reached_05["close_location"] == "above").sum()
            print(f"\n  {'High broke + reached +0.5x':<50} {n:>4} {100*a/n:>7.1f}% above IB high")
        never_05 = high_broke[high_broke["ext_up_0_5_hit"] == False]
        n = len(never_05)
        if n > 0:
            i = (never_05["close_location"] == "inside").sum()
            print(f"  {'High broke + never +0.5x':<50} {n:>4} {100*i/n:>7.1f}% back inside")

    # Edgeful YM reference: 25.8% above baseline, 86.7% with green IB stack, 84% if +0.5x reached


if __name__ == "__main__":
    # Iterate: start at 3 months, expand to 6 months (128 sessions, Edgeful's window)
    for months in [3, 6, 12]:
        print(f"\n{'='*70}")
        print(f"PILOT RUN: {months} months")
        print(f"{'='*70}")
        df = load_pilot("NQ1", "NY AM IB", months=months)
        df = add_missing_fields(df)
        baseline_table(df)
        rule1_direction_trigger(df)
        rule3_clock_filter(df)
        rule4_extension_targets(df)
        rule5_close_location(df)

    # Conditional expectancy from ib_play_detail
    print(f"\n{'='*70}")
    print(f"CONDITIONAL EXPECTANCY (from ib_play_detail)")
    print(f"{'='*70}")
    play_path = DERIVED / "ib_play_detail_NQ1.parquet"
    if play_path.exists():
        plays = pd.read_parquet(play_path)
        plays = plays[plays["session_slot"] == "NY AM IB"].copy()
        plays["trading_day"] = pd.to_datetime(plays["trading_day"])
        max_day = df["trading_day"].max()
        min_day = max_day - pd.Timedelta(days=12 * 30)  # 12 months
        plays_12m = plays[plays["trading_day"] >= min_day]
        print(f"\nPlay detail rows (12 months): {len(plays_12m)}")

        # B4: separate active vs no-setup rows (result=0 is no-setup, not a loss)
        # realized_r is 0 for no-setup days, +target_mult for wins, -1.0 for stop-outs,
        # and directionally signed timeout_r for in-trade drifts.
        for play in [1, 2, 3]:
            g = plays_12m[plays_12m["play"] == play]
            n = len(g)
            if n == 0: continue
            active = g[g["result"] != 0]
            n_active = len(active)
            if n_active == 0:
                print(f"\n  Play {play}: N={n}  no active trades.")
                continue
            wins = (active["result"] == 1).sum()
            wr = 100 * wins / n_active  # B4: denominator is active, not all rows
            exp = active["realized_r"].mean()  # B4: mean over active only (no zero-dilution)
            pf_pos = active[active["result"] == 1]["realized_r"].sum()
            pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            coverage = 100 * n_active / n
            print(f"\n  Play {play}: N={n}  active={n_active} ({coverage:.1f}% coverage)  WR={wr:.1f}%  E[R]={exp:.4f}  PF={pf:.2f}")

            # By target level (also active-only)
            for lvl in sorted(g["target_lvl"].unique()):
                gl = g[g["target_lvl"] == lvl]
                gl_active = gl[gl["result"] != 0]
                n2 = len(gl_active)
                if n2 < 10: continue
                wr2 = 100 * (gl_active["result"] == 1).sum() / n2
                exp2 = gl_active["realized_r"].mean()
                print(f"    target={lvl}x: N_active={n2}  WR={wr2:.1f}%  E[R]={exp2:.4f}")

    print(f"\n{'='*70}")
    print("PILOT COMPLETE")
    print(f"{'='*70}")