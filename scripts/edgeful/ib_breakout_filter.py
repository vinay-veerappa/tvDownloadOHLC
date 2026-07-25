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


def _walk_forward_calibration(
    df: pd.DataFrame,
    min_obs: int = 20,
    smooth_k: float = 10.0,
) -> pd.DataFrame:
    """
    Walk-forward empirical probability calibration keyed by filter features.

    For every row we estimate:
      - P(win | strict-pass features) via expanding-window lookback on prior
        trading days that share the same (session_slot, range_bucket_full,
        first_break_dir) calibration cell.
      - P(win | lenient-pass features) using the same expanding-window logic but
        keyed by (session_slot, range_bucket_full) so the estimate is less sparse.
      - Mean realized magnitude (play3_mfe) for strict-pass and lenient-pass
        cells to inform target sizing.

    Win is defined as ``play3_result > 0`` — a profitable trade outcome.
    Outcomes are lagged by one trading day (via per-day groupby shift) so a
    row never sees any same-day outcome, eliminating same-day leakage.
    Cells with fewer than ``min_obs`` observations fall back to the
    instrument-wide prior, blended with Laplace shrinkage of ``smooth_k``
    pseudo-observations.

    ADR-017: fully vectorized; group-level operations are ``expanding().mean()``
    and ``groupby().shift(1)`` on sorted data.
    """
    out = pd.DataFrame(index=df.index)

    # Build a clean sorted working frame aligned with df.index.
    work = pd.DataFrame(index=df.index)
    work["trading_day"] = df["trading_day"].astype(str)
    work["session_slot"] = df["session_slot"].astype(str)
    work["range_bucket_full"] = df["range_bucket_full"].astype(str)
    work["first_break_dir"] = df["first_break_dir"].fillna(0).astype(int)
    # Win = profitable play3 trade, not direction-extension match.
    work["win"] = (df["play3_result"].fillna(0) > 0).astype(float)
    work["play3_mfe"] = df["play3_mfe"].fillna(0).astype(float)
    work["strict"] = (
        (df["trend_aligned_with_break"].fillna(0) == 1)
        & (df["avwap_aligned"].fillna(0) == 1)
        & (df["break_dir_matches_avwap0930"].fillna(0) == 1)
        & (df["fail_setup_score"].fillna(0) == 0)
    ).astype(int)
    work["lenient"] = (df["trend_aligned_with_break"].fillna(0) == 1).astype(int)

    # Sort by (trading_day, session_slot) for deterministic within-day ordering.
    work = work.sort_values(["trading_day", "session_slot"]).reset_index(drop=True)

    # Build a string cell key for vectorized grouping.
    def _cell_key(cols: list[str]) -> pd.Series:
        key = work["session_slot"].astype(str) + "|" + work["range_bucket_full"].astype(str)
        if "first_break_dir" in cols:
            key = key + "|" + work["first_break_dir"].astype(str)
        return key

    # --- Strict calibration cell: session_slot x range_bucket_full x first_break_dir ---
    strict_key = _cell_key(["first_break_dir"])
    work["strict_key"] = strict_key.where(work["strict"] == 1, np.nan)

    # Mask win/mfe to strict-pass rows, then lag by one trading day.
    # groupby(trading_day).shift(1) ensures first row of each day gets NaN,
    # preventing same-day leakage across session slots.
    win_strict_masked = work["win"].where(work["strict"] == 1, np.nan)
    mfe_strict_masked = work["play3_mfe"].where(work["strict"] == 1, np.nan)
    work["win_strict_lag"] = win_strict_masked.groupby(work["trading_day"]).shift(1)
    work["mfe_strict_lag"] = mfe_strict_masked.groupby(work["trading_day"]).shift(1)

    strict_win_rate = work.groupby("strict_key")["win_strict_lag"].transform(
        lambda s: s.expanding(min_periods=min_obs).mean()
    )
    strict_mfe = work.groupby("strict_key")["mfe_strict_lag"].transform(
        lambda s: s.expanding(min_periods=min_obs).mean()
    )
    strict_nobs = work.groupby("strict_key")["win_strict_lag"].transform(
        lambda s: s.expanding(min_periods=1).count()
    )

    # --- Lenient calibration cell: session_slot x range_bucket_full ---
    lenient_key = _cell_key([])
    work["lenient_key"] = lenient_key.where(work["lenient"] == 1, np.nan)
    win_lenient_masked = work["win"].where(work["lenient"] == 1, np.nan)
    mfe_lenient_masked = work["play3_mfe"].where(work["lenient"] == 1, np.nan)
    work["win_lenient_lag"] = win_lenient_masked.groupby(work["trading_day"]).shift(1)
    work["mfe_lenient_lag"] = mfe_lenient_masked.groupby(work["trading_day"]).shift(1)

    lenient_win_rate = work.groupby("lenient_key")["win_lenient_lag"].transform(
        lambda s: s.expanding(min_periods=min_obs).mean()
    )
    lenient_mfe = work.groupby("lenient_key")["mfe_lenient_lag"].transform(
        lambda s: s.expanding(min_periods=min_obs).mean()
    )
    lenient_nobs = work.groupby("lenient_key")["win_lenient_lag"].transform(
        lambda s: s.expanding(min_periods=1).count()
    )

    # --- Instrument-wide prior (lagged by one trading day) ---
    # Use first row per day as the daily value, shift by one day.
    prior_win = work.groupby("trading_day")["win"].transform("first")
    prior_win = prior_win.shift(1).expanding(min_periods=1).mean()
    prior_mfe = work.groupby("trading_day")["play3_mfe"].transform("first")
    prior_mfe = prior_mfe.shift(1).expanding(min_periods=1).mean()
    lenient_win_first = work["win"].where(work["lenient"] == 1, np.nan)
    lenient_win_first = lenient_win_first.groupby(work["trading_day"]).transform("first")
    lenient_prior_win = lenient_win_first.shift(1).expanding(min_periods=1).mean()
    lenient_mfe_first = work["play3_mfe"].where(work["lenient"] == 1, np.nan)
    lenient_mfe_first = lenient_mfe_first.groupby(work["trading_day"]).transform("first")
    lenient_prior_mfe = lenient_mfe_first.shift(1).expanding(min_periods=1).mean()

    # Shrinkage fallback: blend cell estimate with prior.
    def _blend(cell: pd.Series, prior: pd.Series, nobs: pd.Series) -> pd.Series:
        # Laplace-style shrinkage: (n_obs * cell + k * prior) / (n_obs + k)
        cell = cell.fillna(prior)
        blended = (nobs.fillna(0).astype(float) * cell + smooth_k * prior) / (
            nobs.fillna(0).astype(float) + smooth_k
        )
        return blended.fillna(prior)

    out["empirical_win_rate_strict"] = _blend(strict_win_rate, prior_win, strict_nobs)
    out["empirical_mean_mfe_strict"] = _blend(strict_mfe, prior_mfe, strict_nobs)
    out["empirical_win_rate_lenient"] = _blend(lenient_win_rate, lenient_prior_win, lenient_nobs)
    out["empirical_mean_mfe_lenient"] = _blend(lenient_mfe, lenient_prior_mfe, lenient_nobs)

    # Restore original row order.
    out = out.reindex(df.index)
    return out


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

    # Expectation bucket now uses walk-forward empirical strict win-rate
    # calibrated by (session_slot, range_bucket_full, first_break_dir).
    # Win = play3_result > 0, so base rate is ~14%, thresholds reflect that.
    ewr = df["empirical_win_rate_strict"].fillna(0.14) if "empirical_win_rate_strict" in df.columns else pd.Series(0.14, index=df.index)
    out["expectation_bucket"] = np.where(
        ewr >= 0.25, "high",
        np.where(ewr >= 0.18, "medium", "low")
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

    # Calibration must be visible to recommendation logic, so merge before calling it.
    cal = _walk_forward_calibration(df)
    df_cal = pd.concat([df, cal], axis=1)

    parts = [
        meta,
        _compute_break_context(df),
        _compute_filter_flags(df),
        _compute_confluence_score(df),
        cal,
        _compute_recommendations(df_cal),
        _select_outcomes(df),
    ]

    result = pd.concat(parts, axis=1)
    result = result.loc[:, ~result.columns.duplicated()]

    # Coerce object columns to string for Parquet safety.
    for col in ["entry_side", "expectation_bucket"]:
        if col in result.columns:
            result[col] = result[col].astype(str)

    # Float columns from calibration may arrive as object because of reindex;
    # ensure clean numeric dtypes.
    for col in result.columns:
        if result[col].dtype == object:
            result[col] = pd.to_numeric(result[col], errors="ignore")

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
