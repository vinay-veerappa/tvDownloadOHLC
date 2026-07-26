"""IB Statistics Pilot — Phase A: Load data + add missing derived fields.

3-month horizon, NQ1, NY AM IB. Validates fast before expanding.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"


def load_pilot(symbol="NQ1", session="NY AM IB", months=3):
    """Load ib_confluence filtered to pilot scope."""
    path = DERIVED / f"ib_confluence_{symbol}.parquet"
    df = pd.read_parquet(path)
    df = df[df["session_slot"] == session].copy()
    # Last N months of trading days
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    max_day = df["trading_day"].max()
    min_day = max_day - pd.Timedelta(days=months * 30)
    df = df[df["trading_day"] >= min_day].copy()
    print(f"[Pilot] {symbol} {session}: {len(df)} sessions from {df['trading_day'].min().date()} to {df['trading_day'].max().date()}")
    return df


def add_missing_fields(df):
    """Add the 6 Edgeful-style derived fields."""
    # 1. ib_close_position: where IB close sits within IB range (0=at low, 1=at high)
    df["ib_close_position"] = (df["ib_close"] - df["ib_low"]) / (df["ib_high"] - df["ib_low"])
    df["ib_close_position"] = df["ib_close_position"].clip(0, 1)

    # 2. ib_candle_color: green/red first hour
    df["ib_candle_color"] = np.where(df["ib_close"] > df["ib_open"], "green",
                                     np.where(df["ib_close"] < df["ib_open"], "red", "doji"))

    # 3. day_color: green/red close vs prior session close
    df = df.sort_values("trading_day")
    df["prior_close"] = df["prior_session_close"].shift(1) if "prior_session_close" in df.columns else np.nan
    if "outcome_close" in df.columns:
        # day_color = sign(outcome_close - prior_session_close) where prior_session_close is the previous day's close
        # prior_session_close already stores the prior day's RTH close for NY AM
        df["day_color"] = np.where(df["outcome_close"] > df["prior_session_close"], "green",
                                    np.where(df["outcome_close"] < df["prior_session_close"], "red", "flat"))
    else:
        df["day_color"] = "unknown"

    # 4. opened_inside_prior_range: did today's open fall within yesterday's IB range?
    # We need prior day's ib_high/ib_low
    df["prior_ib_high"] = df["ib_high"].shift(1)
    df["prior_ib_low"] = df["ib_low"].shift(1)
    df["opened_inside_prior_range"] = (df["ib_open"] >= df["prior_ib_low"]) & (df["ib_open"] <= df["prior_ib_high"])

    # 5. close_location_3way: above IB high / inside / below IB low
    if "outcome_close" in df.columns:
        df["close_location"] = np.where(df["outcome_close"] > df["ib_high"], "above",
                                         np.where(df["outcome_close"] < df["ib_low"], "below", "inside"))
    else:
        df["close_location"] = "unknown"

    # 6. ib_size_bucket_edgeful: Edgeful thresholds on range_pct
    if "range_pct" in df.columns:
        df["ib_size_bucket_edgeful"] = np.where(df["range_pct"] < 0.47, "small",
                                                np.where(df["range_pct"] < 0.70, "mid",
                                                         np.where(df["range_pct"] < 0.90, "large", "huge")))
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

    single_break = ((df["first_break_dir"] != 0) & (df["double_break"] == False)).sum()
    double_break = (df["double_break"] == True).sum()
    no_break = (df["first_break_dir"] == 0).sum()
    high_first = (df["first_break_dir"] == 1).sum()
    low_first = (df["first_break_dir"] == -1).sum()
    green_day = (df["day_color"] == "green").sum() if "day_color" in df.columns else 0

    print(f"{'Stat':<30} {'N':>5} {'%':>8}")
    print(f"{'-'*48}")
    print(f"{'Total sessions':<30} {n:>5} {'':>8}")
    print(f"{'Single break':<30} {single_break:>5} {100*single_break/n:>7.1f}%")
    print(f"{'Double break':<30} {double_break:>5} {100*double_break/n:>7.1f}%")
    print(f"{'No break':<30} {no_break:>5} {100*no_break/n:>7.1f}%")
    print(f"{'First break = IB high':<30} {high_first:>5} {100*high_first/n:>7.1f}%")
    print(f"{'First break = IB low':<30} {low_first:>5} {100*low_first/n:>7.1f}%")
    print(f"{'Green day':<30} {green_day:>5} {100*green_day/n:>7.1f}%")

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

        for play in [1, 2, 3]:
            g = plays_12m[plays_12m["play"] == play]
            n = len(g)
            if n == 0: continue
            wins = (g["result"] == 1).sum()
            wr = 100 * wins / n
            exp = g["realized_r"].mean()
            pf_pos = g[g["result"] == 1]["realized_r"].sum()
            pf_neg = abs(g[g["result"] == -1]["realized_r"].sum())
            pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
            print(f"\n  Play {play}: N={n}  WR={wr:.1f}%  E[R]={exp:.4f}  PF={pf:.2f}")

            # By target level
            for lvl in sorted(g["target_lvl"].unique()):
                gl = g[g["target_lvl"] == lvl]
                n2 = len(gl)
                if n2 < 10: continue
                wr2 = 100 * (gl["result"] == 1).sum() / n2
                exp2 = gl["realized_r"].mean()
                print(f"    target={lvl}x: N={n2}  WR={wr2:.1f}%  E[R]={exp2:.4f}")

    print(f"\n{'='*70}")
    print("PILOT COMPLETE")
    print(f"{'='*70}")