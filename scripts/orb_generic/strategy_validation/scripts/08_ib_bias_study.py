#!/usr/bin/env python3
"""
08_ib_bias_study.py — Initial Balance Bias Validation
======================================================
Validates the "which extreme formed first" directional edge:
- If OR high forms first → opposite side (low) breaks → short bias
- If OR low forms first → opposite side (high) breaks → long bias

Tests across multiple OR durations (5, 15, 30, 45, 60 min) and
segments by OR width percentage.

Also validates the Closing Half Rule:
- High formed first → price tends to close in lower half
- Low formed first → price tends to close in upper half

Usage:
    python 08_ib_bias_study.py --symbol NQ1
    python 08_ib_bias_study.py --symbol NQ1 ES1 --or-durations 30 45 60
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


def normalize_trade_date(series_or_index):
    s = pd.Series(series_or_index)
    try:
        return pd.to_datetime(s).dt.strftime("%Y-%m-%d")
    except Exception:
        return s.astype(str).str[:10]


def build_rth_daily_dict(rth: pd.DataFrame) -> dict:
    rth = rth.copy()
    rth["_td_norm"] = normalize_trade_date(rth["trade_date"]).values
    if not isinstance(rth.index, pd.DatetimeIndex):
        try:
            rth.index = pd.to_datetime(rth.index, utc=True).tz_convert("US/Eastern")
        except Exception:
            pass
    return {td: grp for td, grp in rth.groupby("_td_norm")}


@timer
def analyze_ib_bias(rth: pd.DataFrame, or_durations: list) -> pd.DataFrame:
    """For each day and each OR duration, determine:
    1. Which extreme formed first (high or low)
    2. Which side broke first after OR close
    3. Where price closed relative to OR (upper/lower half)
    4. Full day direction
    """
    daily_dict = build_rth_daily_dict(rth)
    results = []

    for td_str, day_bars in daily_dict.items():
        if len(day_bars) < 60:
            continue

        bar_minutes = day_bars.index.hour * 60 + day_bars.index.minute

        for dur in or_durations:
            or_start_min = 9 * 60 + 30
            or_end_min = or_start_min + dur

            # Get OR bars
            or_mask = (bar_minutes >= or_start_min) & (bar_minutes < or_end_min)
            or_bars = day_bars[or_mask]
            if len(or_bars) < 3:
                continue

            or_high = or_bars["high"].max()
            or_low = or_bars["low"].min()
            or_width = or_high - or_low
            or_mid = (or_high + or_low) / 2.0
            or_width_pct = (or_width / or_mid) * 100 if or_mid > 0 else 0

            if or_width <= 0:
                continue

            # --- Which extreme formed first? ---
            # Track when running high/low was last updated
            running_high = or_bars["high"].iloc[0]
            running_low = or_bars["low"].iloc[0]
            high_set_idx = 0
            low_set_idx = 0

            for i in range(1, len(or_bars)):
                if or_bars["high"].iloc[i] > running_high:
                    running_high = or_bars["high"].iloc[i]
                    high_set_idx = i
                if or_bars["low"].iloc[i] < running_low:
                    running_low = or_bars["low"].iloc[i]
                    low_set_idx = i

            if high_set_idx < low_set_idx:
                first_formed = "high"
            elif low_set_idx < high_set_idx:
                first_formed = "low"
            else:
                first_formed = "simultaneous"

            # --- What happened in the first half vs second half of OR? ---
            half = len(or_bars) // 2
            first_half = or_bars.iloc[:half]
            second_half = or_bars.iloc[half:]

            first_half_high = first_half["high"].max()
            first_half_low = first_half["low"].min()
            second_half_high = second_half["high"].max()
            second_half_low = second_half["low"].min()

            # Did the high come from first or second half?
            high_in_first_half = first_half_high >= second_half_high
            low_in_first_half = first_half_low <= second_half_low

            # --- Post-OR analysis ---
            post_or_mask = bar_minutes >= or_end_min
            post_or = day_bars[post_or_mask]
            if len(post_or) < 10:
                continue

            post_highs = post_or["high"].values
            post_lows = post_or["low"].values
            post_close_last = post_or["close"].iloc[-1]

            # Which side broke first after OR?
            high_break_idx = np.where(post_highs > or_high)[0]
            low_break_idx = np.where(post_lows < or_low)[0]

            high_broke = len(high_break_idx) > 0
            low_broke = len(low_break_idx) > 0

            if high_broke and low_broke:
                if high_break_idx[0] < low_break_idx[0]:
                    first_break = "high"
                elif low_break_idx[0] < high_break_idx[0]:
                    first_break = "low"
                else:
                    first_break = "simultaneous"
                both_broke = True
            elif high_broke:
                first_break = "high"
                both_broke = False
            elif low_broke:
                first_break = "low"
                both_broke = False
            else:
                first_break = "neither"
                both_broke = False

            # Closing half
            day_close = post_close_last
            closed_upper_half = day_close > or_mid
            closed_lower_half = day_close < or_mid

            # Day high/low post-OR
            day_high = post_or["high"].max()
            day_low = post_or["low"].min()
            up_excursion = day_high - or_high if day_high > or_high else 0
            down_excursion = or_low - day_low if day_low < or_low else 0

            # IB bias prediction accuracy
            # "High formed first" → predict low break (short)
            # "Low formed first" → predict high break (long)
            if first_formed == "high":
                predicted_break = "low"
                predicted_direction = "short"
            elif first_formed == "low":
                predicted_break = "high"
                predicted_direction = "long"
            else:
                predicted_break = "unknown"
                predicted_direction = "unknown"

            prediction_correct = (first_break == predicted_break) if predicted_break != "unknown" else None

            # Closing half rule accuracy
            # "High formed first" → predict close in lower half
            # "Low formed first" → predict close in upper half
            if first_formed == "high":
                closing_half_correct = closed_lower_half
            elif first_formed == "low":
                closing_half_correct = closed_upper_half
            else:
                closing_half_correct = None

            results.append({
                "trade_date": td_str,
                "or_duration": dur,
                "or_high": or_high,
                "or_low": or_low,
                "or_width": or_width,
                "or_width_pct": or_width_pct,
                "or_mid": or_mid,
                "first_formed": first_formed,
                "high_set_bar": high_set_idx,
                "low_set_bar": low_set_idx,
                "high_in_first_half": high_in_first_half,
                "low_in_first_half": low_in_first_half,
                "first_break": first_break,
                "both_broke": both_broke,
                "high_broke": high_broke,
                "low_broke": low_broke,
                "day_close": day_close,
                "closed_upper_half": closed_upper_half,
                "closed_lower_half": closed_lower_half,
                "up_excursion": up_excursion,
                "down_excursion": down_excursion,
                "up_excursion_pct": up_excursion / or_mid * 100 if or_mid > 0 else 0,
                "down_excursion_pct": down_excursion / or_mid * 100 if or_mid > 0 else 0,
                "predicted_direction": predicted_direction,
                "prediction_correct": prediction_correct,
                "closing_half_correct": closing_half_correct,
            })

    return pd.DataFrame(results)


@timer
def compute_summaries(df: pd.DataFrame) -> dict:
    """Compute summary statistics from the IB bias data."""
    summaries = {}

    for dur in sorted(df["or_duration"].unique()):
        dur_df = df[df["or_duration"] == dur].copy()
        n = len(dur_df)

        # Filter to valid predictions (exclude simultaneous)
        valid = dur_df[dur_df["first_formed"].isin(["high", "low"])]
        nv = len(valid)

        # --- Overall IB bias accuracy ---
        pred_correct = valid["prediction_correct"].sum()
        pred_accuracy = pred_correct / nv * 100 if nv > 0 else 0

        # --- By first_formed direction ---
        high_first = valid[valid["first_formed"] == "high"]
        low_first = valid[valid["first_formed"] == "low"]

        # When high formed first, how often does low break?
        hf_low_breaks = high_first["first_break"].eq("low").sum()
        hf_accuracy = hf_low_breaks / len(high_first) * 100 if len(high_first) > 0 else 0

        # When low formed first, how often does high break?
        lf_high_breaks = low_first["first_break"].eq("high").sum()
        lf_accuracy = lf_high_breaks / len(low_first) * 100 if len(low_first) > 0 else 0

        # --- Closing half rule ---
        closing_valid = valid[valid["closing_half_correct"].notna()]
        closing_accuracy = closing_valid["closing_half_correct"].mean() * 100 if len(closing_valid) > 0 else 0

        # --- By OR width bucket ---
        valid["width_bucket"] = pd.cut(valid["or_width_pct"],
                                        bins=[0, 0.1, 0.2, 0.4, 0.6, 0.9, 100],
                                        labels=["0-0.1%", "0.1-0.2%", "0.2-0.4%", "0.4-0.6%", "0.6-0.9%", "0.9%+"])

        width_stats = []
        for bucket, grp in valid.groupby("width_bucket", observed=True):
            ng = len(grp)
            if ng < 20:
                continue

            hf = grp[grp["first_formed"] == "high"]
            lf = grp[grp["first_formed"] == "low"]

            hf_acc = hf["first_break"].eq("low").mean() * 100 if len(hf) > 0 else 0
            lf_acc = lf["first_break"].eq("high").mean() * 100 if len(lf) > 0 else 0

            width_stats.append({
                "width_bucket": str(bucket),
                "count": ng,
                "high_first_count": len(hf),
                "low_first_count": len(lf),
                "high_first_low_break_pct": hf_acc,
                "low_first_high_break_pct": lf_acc,
                "overall_prediction_pct": grp["prediction_correct"].mean() * 100,
                "closing_half_pct": grp["closing_half_correct"].mean() * 100 if grp["closing_half_correct"].notna().any() else 0,
            })

        # --- Distribution of first_formed ---
        pct_high_first = (valid["first_formed"] == "high").mean() * 100
        pct_low_first = (valid["first_formed"] == "low").mean() * 100

        # --- When prediction is correct, how much excursion? ---
        correct = valid[valid["prediction_correct"] == True]
        wrong = valid[valid["prediction_correct"] == False]

        if len(correct) > 0:
            # For high-first (short bias) correct predictions, measure down excursion
            hf_correct = correct[correct["first_formed"] == "high"]
            lf_correct = correct[correct["first_formed"] == "low"]
            avg_correct_excursion_pct = pd.concat([
                hf_correct["down_excursion_pct"],
                lf_correct["up_excursion_pct"]
            ]).mean() if len(hf_correct) + len(lf_correct) > 0 else 0
        else:
            avg_correct_excursion_pct = 0

        summaries[dur] = {
            "or_duration_min": dur,
            "total_days": n,
            "valid_days": nv,
            "pct_high_first": pct_high_first,
            "pct_low_first": pct_low_first,
            "overall_prediction_accuracy": pred_accuracy,
            "high_first_low_break_pct": hf_accuracy,
            "low_first_high_break_pct": lf_accuracy,
            "closing_half_accuracy": closing_accuracy,
            "avg_correct_excursion_pct": avg_correct_excursion_pct,
            "high_first_count": len(high_first),
            "low_first_count": len(low_first),
            "width_breakdown": width_stats,
        }

    return summaries


def main():
    parser = argparse.ArgumentParser(description="IB Bias Validation Study")
    parser.add_argument("--symbols", nargs="*", default=["NQ1", "ES1"])
    parser.add_argument("--or-durations", nargs="*", type=int, default=[5, 15, 30, 45, 60])
    args = parser.parse_args()

    config = get_config()
    cfg_data = config["data"]
    cfg_data.ensure_dirs()

    for symbol in args.symbols:
        log(f"\n{'='*60}")
        log(f"IB BIAS STUDY — {symbol}")
        log(f"{'='*60}")

        rth = load_derived(f"{symbol}_rth_1min", cfg_data)
        if "trade_date" not in rth.columns:
            rth["trade_date"] = rth.index.date

        log(f"Running IB bias analysis for OR durations: {args.or_durations}")
        df = analyze_ib_bias(rth, args.or_durations)
        save_results(df, f"{symbol}_ib_bias_detail", cfg_data)
        log(f"  Total records: {len(df)}")

        log(f"\nComputing summaries...")
        summaries = compute_summaries(df)

        # Print results
        for dur, s in summaries.items():
            log(f"\n{'─'*50}")
            log(f"OR Duration: {dur} minutes")
            log(f"{'─'*50}")
            log(f"  Total days: {s['valid_days']} (excl simultaneous)")
            log(f"  High formed first: {s['pct_high_first']:.1f}% ({s['high_first_count']} days)")
            log(f"  Low formed first:  {s['pct_low_first']:.1f}% ({s['low_first_count']} days)")
            log(f"")
            log(f"  *** IB BIAS PREDICTION ACCURACY ***")
            log(f"  Overall (opposite side breaks): {s['overall_prediction_accuracy']:.1f}%")
            log(f"  High first → low breaks:        {s['high_first_low_break_pct']:.1f}%")
            log(f"  Low first → high breaks:         {s['low_first_high_break_pct']:.1f}%")
            log(f"")
            log(f"  *** CLOSING HALF RULE ***")
            log(f"  Accuracy: {s['closing_half_accuracy']:.1f}%")
            log(f"")
            log(f"  Avg excursion on correct predictions: {s['avg_correct_excursion_pct']:.3f}%")

            if s["width_breakdown"]:
                log(f"\n  By OR Width:")
                log(f"  {'Width':<12} {'Count':>6} {'HF→LB%':>8} {'LF→HB%':>8} {'Pred%':>7} {'Close%':>7}")
                for w in s["width_breakdown"]:
                    log(f"  {w['width_bucket']:<12} {w['count']:>6} {w['high_first_low_break_pct']:>7.1f}% {w['low_first_high_break_pct']:>7.1f}% {w['overall_prediction_pct']:>6.1f}% {w['closing_half_pct']:>6.1f}%")

        # Save summary
        # Convert numpy int keys to plain int for JSON serialization
        clean_summaries = {int(k): v for k, v in summaries.items()}
        save_results_json(clean_summaries, f"{symbol}_ib_bias_summary", cfg_data)
        
        # Also save a clean comparison table
        comparison_rows = []
        for dur, s in summaries.items():
            comparison_rows.append({
                "or_duration": dur,
                "valid_days": s["valid_days"],
                "pct_high_first": s["pct_high_first"],
                "pct_low_first": s["pct_low_first"],
                "overall_accuracy": s["overall_prediction_accuracy"],
                "high_first_low_break": s["high_first_low_break_pct"],
                "low_first_high_break": s["low_first_high_break_pct"],
                "closing_half_accuracy": s["closing_half_accuracy"],
            })
        comp_df = pd.DataFrame(comparison_rows)
        save_results(comp_df, f"{symbol}_ib_bias_comparison", cfg_data)
        log(f"\nComparison table:")
        print(comp_df.to_string(index=False))

    log(f"\n{'='*60}")
    log("IB BIAS STUDY COMPLETE")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
