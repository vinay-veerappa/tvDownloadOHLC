"""
Phase 5 strategy-specific derived data: IB Breakout Enhanced Filter Set.

Reads the master IB confluence table and produces a compact filter table
for the existing IB Break / IB Breakout Modular strategies. Each row maps
a first-break event to:
  - break direction and entry side
  - strict / lenient filter pass flags
  - a confluence score
  - recommended target/stop multiples (from empirical expectations)
  - an expectation bucket (edge estimate / walk-forward placeholder)

Output:
    data/derived/ib_breakout_filter_{SYM}.parquet

ADR-017 compliant: fully vectorized NumPy/Pandas; no per-row loops.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DERIVED = ROOT / "data" / "derived"

INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

KEY_COLS = ["symbol", "session_slot", "time_basis", "trading_day"]


def _load_confluence(sym: str) -> pd.DataFrame:
    path = DATA_DERIVED / f"ib_confluence_{sym}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run ib_master_confluence first.")
    df = pd.read_parquet(path)
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _compute_break_context(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    break_dir = df["first_break_dir"].fillna(0)
    out["break_direction"] = break_dir
    out["entry_side"] = np.where(break_dir > 0, "LONG", np.where(break_dir < 0, "SHORT", "NONE"))
    out["ib_high"] = df["ib_high"]
    out["ib_low"] = df["ib_low"]
    out["ib_range"] = df["ib_range"].replace(0, np.nan)
    out["first_break_minutes"] = df["first_break_minutes"]
    out["first_break_time_val"] = df["first_break_time_val"]
    return out


def _compute_filter_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    trend = df["trend_aligned_with_break"].fillna(0)
    avwap = df["avwap_aligned"].fillna(0)
    avwap_match = df["break_dir_matches_avwap0930"].fillna(0)
    fail = df["fail_setup_score"].fillna(0)

    out["trend_aligned"] = trend.astype(int)
    out["avwap_aligned"] = avwap.astype(int)
    out["break_dir_matches_avwap0930"] = avwap_match.astype(int)
    out["fail_setup_flag"] = fail.astype(int)

    # Lenient: at least trend aligned.
    out["lenient_filter_pass"] = (trend == 1).astype(int)

    # Strict: trend + AVWAP + AVWAP-direction match + no fail-setup flag.
    out["strict_filter_pass"] = (
        (trend == 1) & (avwap == 1) & (avwap_match == 1) & (fail == 0)
    ).astype(int)

    return out


def _compute_confluence_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Composite confluence score from available breakout-confluence components.
    Weights are interpretable hand-tuned starting points.
    """
    score = pd.Series(0.0, index=df.index)

    score += df["trend_aligned_with_break"].fillna(0) * 3.0
    score += df["avwap_aligned"].fillna(0) * 2.0
    score += df["break_dir_matches_avwap0930"].fillna(0) * 2.0

    if "avwap_mixed" in df.columns:
        score -= df["avwap_mixed"].fillna(0) * 1.5

    if "news_high_impact_present" in df.columns:
        score -= df["news_high_impact_present"].fillna(0) * 1.0

    score -= df["fail_setup_score"].fillna(0) * 2.0

    if "range_bucket_full" in df.columns:
        # Prefer moderate expansion range; extremely compressed or very wide IB adds uncertainty.
        rb = df["range_bucket_full"].astype(str)
        score += np.where(rb == "normal", 0.5, 0.0)
        score -= np.where(rb.isin(["compressed", "wide"]), 0.5, 0.0)

    return pd.DataFrame({"confluence_score": score})


def _compute_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Suggested target/stop multiples and expectation bucket based on observed
    empirical expectations (ADR-002: normalized price percentage outcomes).
    """
    out = pd.DataFrame(index=df.index)

    # Fallback realized magnitude means if columns exist, else reasonable defaults.
    play1_mean = df["play1_result"].abs().mean() if "play1_result" in df.columns else 0.005
    play3_mean = df["play3_result"].abs().mean() if "play3_result" in df.columns else 0.015

    strict = df["strict_filter_pass"].fillna(0) if "strict_filter_pass" in df.columns else pd.Series(0, index=df.index)

    # Empirical default multiples derived from mean magnitudes.
    ratio = play3_mean / np.where(play1_mean == 0, np.nan, play1_mean)
    ratio = np.clip(ratio, 1.0, 3.0)
    ratio = pd.Series(ratio, index=df.index).fillna(1.5)
    out["recommended_target_multiple"] = np.where(strict == 1, ratio, np.clip(ratio, 1.0, 2.0))

    out["recommended_stop_multiple"] = 1.0

    # Expectation bucket: placeholder until walk-forward empirical calibration is wired in.
    # Uses the composite confluence score to label low / medium / high edge.
    cs = df["confluence_score"].fillna(0) if "confluence_score" in df.columns else pd.Series(0, index=df.index)
    out["expectation_bucket"] = np.where(
        cs >= 6.0, "high",
        np.where(cs >= 3.0, "medium", "low")
    )

    return out


def _select_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    targets = {
        "target_realized_dir_ext": "realized_dir_ext",
        "target_realized_dir_break": "realized_dir_break",
        "target_play1_result": "play1_result",
        "target_play2_result": "play2_result",
        "target_play3_result": "play3_result",
        "target_bias_correct_combined_05x": "bias_correct_combined_05x",
    }
    for new, old in targets.items():
        if old in df.columns:
            out[new] = df[old]
    return out


def process_symbol(sym: str) -> None:
    print(f"[{sym}] building IB breakout enhanced filter set")
    df = _load_confluence(sym)

    meta = df[KEY_COLS].copy()

    parts = [
        meta,
        _compute_break_context(df),
        _compute_filter_flags(df),
        _compute_confluence_score(df),
        _compute_recommendations(df),
        _select_outcomes(df),
    ]

    result = pd.concat(parts, axis=1)
    result = result.loc[:, ~result.columns.duplicated()]

    # Coerce object columns to string for Parquet safety.
    for col in ["entry_side", "expectation_bucket"]:
        if col in result.columns:
            result[col] = result[col].astype(str)

    out_path = DATA_DERIVED / f"ib_breakout_filter_{sym}.parquet"
    result.to_parquet(out_path, index=False)
    print(f"[{sym}] wrote {len(result)} rows x {len(result.columns)} cols -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()

    instruments = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    for sym in instruments:
        try:
            process_symbol(sym)
        except Exception as e:
            print(f"[{sym}] ERROR: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
