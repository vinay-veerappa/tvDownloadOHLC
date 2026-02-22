#!/usr/bin/env python3
# strategy_validation/scripts/01_opening_range_study.py
"""
Study 1: Opening Range Breakout/Failure Statistics
===================================================
Analyzes OR behavior across all configured durations using derived data.
Never touches raw parquet files — reads from cached CSV/JSON.

Usage:
    python 01_opening_range_study.py                          # all symbols, all OR durations
    python 01_opening_range_study.py --symbols ES NQ          # specific symbols
    python 01_opening_range_study.py --or-durations 15 30     # specific OR durations only

Outputs (in results_dir):
    {symbol}_or_breakout_rates.csv       — basic breakout statistics per OR duration
    {symbol}_or_excursion_stats.csv      — post-breakout excursion distributions
    {symbol}_or_excursion_detail.csv     — raw per-day excursion data (for histograms)
    {symbol}_or_width_analysis.csv       — OR width as predictor of day type
    {symbol}_or_context_analysis.csv     — OR behavior near key levels
    {symbol}_or_day_of_week.csv          — breakout stats by day of week
    {symbol}_or_judas_stats.csv          — Judas swing (false breakout) analysis
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_config
from scripts.utils import load_derived, save_results, save_results_json, log, timer


# ---------------------------------------------------------------------------
# Core analysis functions — all vectorized
# ---------------------------------------------------------------------------

@timer
def analyze_breakout_rates(rth: pd.DataFrame, or_data: pd.DataFrame,
                           durations: list) -> pd.DataFrame:
    """Analysis 1.1: Basic OR breakout rates.

    For each OR duration, compute:
    - % days high broken, low broken, both, neither
    - Which side broke first
    - Judas swing rate
    - Time to first break
    """
    results = []

    for dur in durations:
        or_h = or_data[f"or_{dur}_high"]
        or_l = or_data[f"or_{dur}_low"]

        # Get post-OR bars for each trade date
        # OR end time in minutes from midnight
        or_end_min = 9 * 60 + 30 + dur
        rth_minutes = rth.index.hour * 60 + rth.index.minute
        post_or_mask = rth_minutes >= or_end_min

        post_or = rth[post_or_mask].copy()

        # For each trade date, find if/when OR levels were broken
        trade_dates = or_h.index  # common dates

        high_broken = np.full(len(trade_dates), False)
        low_broken = np.full(len(trade_dates), False)
        high_break_time = np.full(len(trade_dates), np.nan)  # minutes after OR close
        low_break_time = np.full(len(trade_dates), np.nan)

        for i, td in enumerate(trade_dates):
            td_str = str(td)
            day_bars = post_or[post_or["trade_date"].astype(str) == td_str]
            if len(day_bars) == 0:
                continue

            h = or_h.iloc[i]
            l = or_l.iloc[i]

            if pd.isna(h) or pd.isna(l):
                continue

            highs = day_bars["high"].values
            lows = day_bars["low"].values
            bar_minutes = day_bars.index.hour * 60 + day_bars.index.minute

            # Find first bar where high > OR high
            h_break_idx = np.where(highs > h)[0]
            if len(h_break_idx) > 0:
                high_broken[i] = True
                high_break_time[i] = bar_minutes[h_break_idx[0]] - or_end_min

            # Find first bar where low < OR low
            l_break_idx = np.where(lows < l)[0]
            if len(l_break_idx) > 0:
                low_broken[i] = True
                low_break_time[i] = bar_minutes[l_break_idx[0]] - or_end_min

        n = len(trade_dates)
        both_broken = high_broken & low_broken
        neither_broken = ~high_broken & ~low_broken

        # Which side first
        high_first = high_broken & (
            ~low_broken | (high_break_time < low_break_time)
        )
        low_first = low_broken & (
            ~high_broken | (low_break_time < high_break_time)
        )
        simultaneous = high_broken & low_broken & (high_break_time == low_break_time)

        # Judas swing: first break FAILS and opposite side gets taken
        # Definition: first side breaks, then the OTHER side also breaks
        judas_from_high = high_first & low_broken  # broke high first, then low was taken
        judas_from_low = low_first & high_broken   # broke low first, then high was taken
        judas_total = judas_from_high | judas_from_low

        # Valid break times (non-NaN)
        valid_h_times = high_break_time[high_broken]
        valid_l_times = low_break_time[low_broken]
        all_first_times = np.concatenate([
            high_break_time[high_first & ~np.isnan(high_break_time)],
            low_break_time[low_first & ~np.isnan(low_break_time)]
        ])

        results.append({
            "or_duration": dur,
            "total_days": n,
            "pct_high_broken": high_broken.sum() / n * 100,
            "pct_low_broken": low_broken.sum() / n * 100,
            "pct_both_broken": both_broken.sum() / n * 100,
            "pct_neither_broken": neither_broken.sum() / n * 100,
            "pct_high_first": high_first.sum() / n * 100,
            "pct_low_first": low_first.sum() / n * 100,
            "pct_simultaneous": simultaneous.sum() / n * 100,
            "pct_judas_total": judas_total.sum() / n * 100,
            "pct_judas_from_high": judas_from_high.sum() / n * 100,
            "pct_judas_from_low": judas_from_low.sum() / n * 100,
            "avg_time_first_break_min": np.nanmean(all_first_times) if len(all_first_times) > 0 else np.nan,
            "median_time_first_break_min": np.nanmedian(all_first_times) if len(all_first_times) > 0 else np.nan,
            "avg_time_high_break_min": np.nanmean(valid_h_times) if len(valid_h_times) > 0 else np.nan,
            "avg_time_low_break_min": np.nanmean(valid_l_times) if len(valid_l_times) > 0 else np.nan,
        })

    return pd.DataFrame(results).set_index("or_duration")


@timer
def analyze_excursions(rth: pd.DataFrame, or_data: pd.DataFrame,
                       durations: list) -> tuple:
    """Analysis 1.2: Post-breakout excursion analysis.

    For each day where OR was broken, measure:
    - Max favorable excursion beyond the break level
    - Max adverse excursion after the break
    - Whether the day closed beyond the break level
    """
    summary_rows = []
    detail_frames = []

    for dur in durations:
        or_h = or_data[f"or_{dur}_high"]
        or_l = or_data[f"or_{dur}_low"]
        or_end_min = 9 * 60 + 30 + dur

        trade_dates = or_h.index
        rth_minutes = rth.index.hour * 60 + rth.index.minute
        post_or = rth[rth_minutes >= or_end_min].copy()

        # Storage for per-day detail
        day_details = []

        for i, td in enumerate(trade_dates):
            td_str = str(td)
            day_bars = post_or[post_or["trade_date"].astype(str) == td_str]
            if len(day_bars) == 0:
                continue

            h = or_h.iloc[i]
            l = or_l.iloc[i]
            if pd.isna(h) or pd.isna(l):
                continue

            day_high = day_bars["high"].max()
            day_low = day_bars["low"].min()
            day_close = day_bars["close"].iloc[-1]

            detail = {
                "trade_date": td,
                "or_duration": dur,
                "or_high": h,
                "or_low": l,
                "or_width": h - l,
            }

            # Upside breakout excursion
            if day_high > h:
                detail["up_break"] = True
                detail["up_max_excursion"] = day_high - h
                detail["up_max_adverse"] = h - day_low  # how far below OR high it went
                detail["up_close_above"] = day_close > h
                detail["up_close_distance"] = day_close - h
            else:
                detail["up_break"] = False
                detail["up_max_excursion"] = 0
                detail["up_max_adverse"] = 0
                detail["up_close_above"] = False
                detail["up_close_distance"] = day_close - h

            # Downside breakout excursion
            if day_low < l:
                detail["down_break"] = True
                detail["down_max_excursion"] = l - day_low
                detail["down_max_adverse"] = day_high - l  # how far above OR low it went
                detail["down_close_below"] = day_close < l
                detail["down_close_distance"] = l - day_close
            else:
                detail["down_break"] = False
                detail["down_max_excursion"] = 0
                detail["down_max_adverse"] = 0
                detail["down_close_below"] = False
                detail["down_close_distance"] = l - day_close

            day_details.append(detail)

        df_detail = pd.DataFrame(day_details)
        detail_frames.append(df_detail)

        # Compute summary statistics
        up_breaks = df_detail[df_detail["up_break"]]
        dn_breaks = df_detail[df_detail["down_break"]]

        summary_rows.append({
            "or_duration": dur,
            # Upside
            "up_break_count": len(up_breaks),
            "up_avg_excursion": up_breaks["up_max_excursion"].mean() if len(up_breaks) > 0 else 0,
            "up_median_excursion": up_breaks["up_max_excursion"].median() if len(up_breaks) > 0 else 0,
            "up_p25_excursion": up_breaks["up_max_excursion"].quantile(0.25) if len(up_breaks) > 0 else 0,
            "up_p75_excursion": up_breaks["up_max_excursion"].quantile(0.75) if len(up_breaks) > 0 else 0,
            "up_avg_adverse": up_breaks["up_max_adverse"].mean() if len(up_breaks) > 0 else 0,
            "up_pct_close_above": up_breaks["up_close_above"].mean() * 100 if len(up_breaks) > 0 else 0,
            # Downside
            "dn_break_count": len(dn_breaks),
            "dn_avg_excursion": dn_breaks["down_max_excursion"].mean() if len(dn_breaks) > 0 else 0,
            "dn_median_excursion": dn_breaks["down_max_excursion"].median() if len(dn_breaks) > 0 else 0,
            "dn_p25_excursion": dn_breaks["down_max_excursion"].quantile(0.25) if len(dn_breaks) > 0 else 0,
            "dn_p75_excursion": dn_breaks["down_max_excursion"].quantile(0.75) if len(dn_breaks) > 0 else 0,
            "dn_avg_adverse": dn_breaks["down_max_adverse"].mean() if len(dn_breaks) > 0 else 0,
            "dn_pct_close_below": dn_breaks["down_close_below"].mean() * 100 if len(dn_breaks) > 0 else 0,
        })

    summary = pd.DataFrame(summary_rows).set_index("or_duration")
    all_detail = pd.concat(detail_frames, ignore_index=True)

    return summary, all_detail


@timer
def analyze_or_width(detail: pd.DataFrame, durations: list) -> pd.DataFrame:
    """Analysis 1.3: OR width as predictor of day behavior.

    Bucket OR width into quintiles and compute breakout stats per bucket.
    """
    results = []

    for dur in durations:
        dur_data = detail[detail["or_duration"] == dur].copy()
        if len(dur_data) < 50:
            continue

        # Create quintile buckets
        dur_data["width_quintile"] = pd.qcut(dur_data["or_width"], 5,
                                              labels=["Q1_narrow", "Q2", "Q3", "Q4", "Q5_wide"],
                                              duplicates="drop")

        for q, grp in dur_data.groupby("width_quintile", observed=True):
            n = len(grp)
            both = (grp["up_break"] & grp["down_break"]).sum()
            up_only = (grp["up_break"] & ~grp["down_break"]).sum()
            dn_only = (grp["down_break"] & ~grp["up_break"]).sum()

            results.append({
                "or_duration": dur,
                "width_quintile": q,
                "count": n,
                "avg_or_width": grp["or_width"].mean(),
                "pct_up_break": grp["up_break"].mean() * 100,
                "pct_down_break": grp["down_break"].mean() * 100,
                "pct_both_broken": both / n * 100,
                "pct_trend_day_up": up_only / n * 100,
                "pct_trend_day_down": dn_only / n * 100,
                "avg_up_excursion": grp.loc[grp["up_break"], "up_max_excursion"].mean() if grp["up_break"].any() else 0,
                "avg_dn_excursion": grp.loc[grp["down_break"], "down_max_excursion"].mean() if grp["down_break"].any() else 0,
            })

    return pd.DataFrame(results)


@timer
def analyze_or_context(or_data: pd.DataFrame, daily_levels: pd.DataFrame,
                       detail: pd.DataFrame, durations: list) -> pd.DataFrame:
    """Analysis 1.4: OR behavior relative to key levels (PDH, PDL, ONH, ONL)."""
    results = []

    # Align dates
    common = or_data.index.intersection(daily_levels.index)

    for dur in durations:
        or_h = or_data.loc[common, f"or_{dur}_high"]
        or_l = or_data.loc[common, f"or_{dur}_low"]
        pdh = daily_levels.loc[common, "pdh"]
        pdl = daily_levels.loc[common, "pdl"]
        onh = daily_levels.loc[common, "onh"]
        onl = daily_levels.loc[common, "onl"]

        # Classify OR position relative to PDH/PDL
        above_pdh = or_l > pdh
        below_pdl = or_h < pdl
        straddle_pdh = (or_l <= pdh) & (or_h >= pdh) & ~below_pdl
        straddle_pdl = (or_l <= pdl) & (or_h >= pdl) & ~above_pdh
        inside = ~above_pdh & ~below_pdl & ~straddle_pdh & ~straddle_pdl

        contexts = {
            "above_pdh": above_pdh,
            "below_pdl": below_pdl,
            "straddle_pdh": straddle_pdh,
            "straddle_pdl": straddle_pdl,
            "inside_range": inside,
        }

        # Also classify relative to overnight range
        above_onh = or_l > onh
        below_onl = or_h < onl
        inside_on = ~above_onh & ~below_onl

        contexts["above_onh"] = above_onh
        contexts["below_onl"] = below_onl
        contexts["inside_overnight"] = inside_on

        dur_detail = detail[detail["or_duration"] == dur].set_index("trade_date")

        for ctx_name, ctx_mask in contexts.items():
            ctx_dates = common[ctx_mask.values]
            ctx_detail = dur_detail.loc[dur_detail.index.isin(ctx_dates)]
            n = len(ctx_detail)

            if n < 10:
                continue

            results.append({
                "or_duration": dur,
                "context": ctx_name,
                "count": n,
                "pct_of_days": n / len(common) * 100,
                "pct_up_break": ctx_detail["up_break"].mean() * 100 if n > 0 else 0,
                "pct_down_break": ctx_detail["down_break"].mean() * 100 if n > 0 else 0,
                "pct_both": (ctx_detail["up_break"] & ctx_detail["down_break"]).mean() * 100 if n > 0 else 0,
                "avg_up_excursion": ctx_detail.loc[ctx_detail["up_break"], "up_max_excursion"].mean() if ctx_detail["up_break"].any() else 0,
                "avg_dn_excursion": ctx_detail.loc[ctx_detail["down_break"], "down_max_excursion"].mean() if ctx_detail["down_break"].any() else 0,
            })

    return pd.DataFrame(results)


@timer
def analyze_day_of_week(or_data: pd.DataFrame, detail: pd.DataFrame,
                        durations: list) -> pd.DataFrame:
    """Analysis 1.5: OR breakout stats by day of week."""
    results = []

    day_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}

    # Add day of week to detail
    detail = detail.copy()
    detail["dow"] = pd.to_datetime(detail["trade_date"]).dt.dayofweek

    for dur in durations:
        dur_detail = detail[detail["or_duration"] == dur]

        for dow, day_name in day_names.items():
            grp = dur_detail[dur_detail["dow"] == dow]
            n = len(grp)
            if n < 20:
                continue

            both = (grp["up_break"] & grp["down_break"]).sum()

            results.append({
                "or_duration": dur,
                "day_of_week": day_name,
                "count": n,
                "pct_up_break": grp["up_break"].mean() * 100,
                "pct_down_break": grp["down_break"].mean() * 100,
                "pct_both_broken": both / n * 100,
                "avg_or_width": grp["or_width"].mean(),
                "avg_up_excursion": grp.loc[grp["up_break"], "up_max_excursion"].mean() if grp["up_break"].any() else 0,
                "avg_dn_excursion": grp.loc[grp["down_break"], "down_max_excursion"].mean() if grp["down_break"].any() else 0,
                "pct_close_above_or_h": grp["up_close_above"].mean() * 100,
                "pct_close_below_or_l": grp["down_close_below"].mean() * 100,
            })

    return pd.DataFrame(results)


@timer
def analyze_judas_detail(rth: pd.DataFrame, or_data: pd.DataFrame,
                         durations: list) -> pd.DataFrame:
    """Detailed Judas swing analysis.

    When the first breakout fails and the opposite side is taken:
    - How far did the false break go before reversing?
    - How long did the false break last?
    - What's the average P&L of fading the first break?
    """
    results = []

    for dur in durations:
        or_h = or_data[f"or_{dur}_high"]
        or_l = or_data[f"or_{dur}_low"]
        or_end_min = 9 * 60 + 30 + dur

        rth_minutes = rth.index.hour * 60 + rth.index.minute
        post_or = rth[rth_minutes >= or_end_min].copy()
        trade_dates = or_h.index

        for i, td in enumerate(trade_dates):
            td_str = str(td)
            day_bars = post_or[post_or["trade_date"].astype(str) == td_str]
            if len(day_bars) == 0:
                continue

            h = or_h.iloc[i]
            l = or_l.iloc[i]
            if pd.isna(h) or pd.isna(l):
                continue

            highs = day_bars["high"].values
            lows = day_bars["low"].values
            closes = day_bars["close"].values
            bar_minutes = day_bars.index.hour * 60 + day_bars.index.minute

            # Find break times
            h_break_idx = np.where(highs > h)[0]
            l_break_idx = np.where(lows < l)[0]

            h_broke = len(h_break_idx) > 0
            l_broke = len(l_break_idx) > 0

            if not (h_broke and l_broke):
                continue  # Need both sides broken for Judas

            h_time = h_break_idx[0]
            l_time = l_break_idx[0]

            if h_time == l_time:
                continue  # Simultaneous, not a Judas

            if h_time < l_time:
                # Broke high first, then low — Judas was the high break
                false_break_dir = "up"
                false_break_excursion = highs[:l_time].max() - h  # how far above OR high
                reversal_excursion = l - lows[l_time:].min()      # how far below OR low
                # Fade trade: short at OR high after break, target OR low
                fade_entry = h
                fade_target = l
                fade_stop = highs[:l_time].max()  # worst case before reversal
                day_close_dist = l - closes[-1]
            else:
                # Broke low first, then high — Judas was the low break
                false_break_dir = "down"
                false_break_excursion = l - lows[:h_time].min()
                reversal_excursion = highs[h_time:].max() - h
                fade_entry = l
                fade_target = h
                fade_stop = lows[:h_time].min()
                day_close_dist = closes[-1] - h

            or_width = h - l

            results.append({
                "trade_date": td,
                "or_duration": dur,
                "false_break_dir": false_break_dir,
                "false_break_excursion_pts": false_break_excursion,
                "false_break_excursion_or_pct": false_break_excursion / or_width * 100 if or_width > 0 else 0,
                "reversal_excursion_pts": reversal_excursion,
                "time_to_reversal_min": abs(h_time - l_time),
                "or_width": or_width,
                "fade_risk_pts": abs(fade_stop - fade_entry),
                "fade_reward_pts": abs(fade_target - fade_entry),
                "fade_rr": abs(fade_target - fade_entry) / abs(fade_stop - fade_entry) if abs(fade_stop - fade_entry) > 0 else 0,
            })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Study 1: Opening Range Statistics")
    parser.add_argument("--symbols", nargs="*", help="Symbols to analyze")
    parser.add_argument("--or-durations", nargs="*", type=int, help="OR durations in minutes")
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    cfg_or = config["opening_range"]

    durations = args.or_durations if args.or_durations else cfg_or.or_durations_minutes

    # Find available derived data files
    derived_path = Path(cfg_data.derived_dir)
    if args.symbols:
        symbols = args.symbols
    else:
        # Auto-detect from derived files
        files = list(derived_path.glob("*_rth_1min.*"))
        symbols = list(set(f.stem.split("_")[0] for f in files))

    if not symbols:
        log("ERROR: No derived data found. Run 00_data_prep.py first.")
        sys.exit(1)

    log(f"Analyzing symbols: {symbols}")
    log(f"OR durations: {durations}")

    for symbol in symbols:
        log(f"\n{'='*60}")
        log(f"STUDY 1: Opening Range Analysis — {symbol}")
        log(f"{'='*60}")

        # Load derived data
        log("Loading derived data...")
        rth = load_derived(f"{symbol}_rth_1min", cfg_data)
        or_data = load_derived(f"{symbol}_opening_ranges", cfg_data)
        daily_levels = load_derived(f"{symbol}_daily_levels", cfg_data)

        # Ensure trade_date column exists in rth
        if "trade_date" not in rth.columns:
            log("  WARNING: trade_date not in RTH data, attempting to reconstruct")
            rth["trade_date"] = rth.index.date

        # Filter durations to those available in data
        available_durs = [d for d in durations if f"or_{d}_high" in or_data.columns]
        if not available_durs:
            log(f"  ERROR: No OR data for durations {durations}. Available columns: {list(or_data.columns)}")
            continue
        log(f"  Available OR durations: {available_durs}")

        # --- Run analyses ---

        # 1.1: Breakout rates
        log("\n--- 1.1: Breakout Rates ---")
        breakout_rates = analyze_breakout_rates(rth, or_data, available_durs)
        save_results(breakout_rates, f"{symbol}_or_breakout_rates", cfg_data)
        print(breakout_rates.to_string())

        # 1.2: Excursion analysis
        log("\n--- 1.2: Excursion Analysis ---")
        excursion_summary, excursion_detail = analyze_excursions(rth, or_data, available_durs)
        save_results(excursion_summary, f"{symbol}_or_excursion_stats", cfg_data)
        save_results(excursion_detail, f"{symbol}_or_excursion_detail", cfg_data)
        print(excursion_summary.to_string())

        # 1.3: OR width analysis
        log("\n--- 1.3: OR Width Analysis ---")
        width_analysis = analyze_or_width(excursion_detail, available_durs)
        save_results(width_analysis, f"{symbol}_or_width_analysis", cfg_data)
        print(width_analysis.to_string())

        # 1.4: Context analysis
        log("\n--- 1.4: Context Analysis (Key Levels) ---")
        context = analyze_or_context(or_data, daily_levels, excursion_detail, available_durs)
        save_results(context, f"{symbol}_or_context_analysis", cfg_data)
        print(context.to_string())

        # 1.5: Day of week
        log("\n--- 1.5: Day of Week ---")
        dow = analyze_day_of_week(or_data, excursion_detail, available_durs)
        save_results(dow, f"{symbol}_or_day_of_week", cfg_data)
        print(dow.to_string())

        # Judas swing detail
        log("\n--- Judas Swing Detail ---")
        judas = analyze_judas_detail(rth, or_data, available_durs)
        save_results(judas, f"{symbol}_or_judas_stats", cfg_data)
        if len(judas) > 0:
            # Summary by duration
            judas_summary = judas.groupby("or_duration").agg(
                total_judas=("trade_date", "count"),
                avg_false_excursion=("false_break_excursion_pts", "mean"),
                avg_reversal_excursion=("reversal_excursion_pts", "mean"),
                avg_fade_rr=("fade_rr", "mean"),
                median_fade_rr=("fade_rr", "median"),
                pct_up_false=("false_break_dir", lambda x: (x == "up").mean() * 100),
            )
            print(judas_summary.to_string())

        log(f"\n{symbol} Study 1 complete.")

    log(f"\n{'='*60}")
    log("STUDY 1 COMPLETE")
    log(f"Results saved to: {cfg_data.results_dir}/")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
