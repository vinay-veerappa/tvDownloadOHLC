"""
Phase 5 strategy-specific derived data: IB Pullback triggers.

Reads the master IB confluence table and produces a compact parquet of
pullback-to-IB-extreme entry signals with pre-computed filters, targets,
and outcome labels for the existing IB Pullback hunter.

Output:
    data/derived/ib_pullback_triggers_{SYM}.parquet

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

# Common Fibonacci retracement levels used for IB pullback entries.
FIB_LEVELS = np.array([0.236, 0.382, 0.500, 0.618, 0.786])

KEY_COLS = ["symbol", "session_slot", "time_basis", "trading_day"]

# PD-array specifications used for vectorized nearest-array search.
ARRAY_SPECS = [
    ("ob", "pd_array_ob_top", "pd_array_ob_bottom"),
    ("breaker", "pd_array_breaker_top", "pd_array_breaker_bottom"),
    ("fvg", "pd_array_fvg_top", "pd_array_fvg_bottom"),
    ("mitigation", "pd_array_mitigation_top", "pd_array_mitigation_bottom"),
    ("rejection", "pd_array_rejection_top", "pd_array_rejection_bottom"),
]

# Priority order for arrays when multiple overlap. Lower index = higher priority.
ARRAY_PRIORITY = {
    "ob": 1,
    "breaker": 2,
    "fvg": 3,
    "mitigation": 4,
    "rejection": 5,
}


def _load_confluence(sym: str) -> pd.DataFrame:
    path = DATA_DERIVED / f"ib_confluence_{sym}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run ib_master_confluence first.")
    return pd.read_parquet(path)


def _load_key_levels(sym: str) -> pd.DataFrame:
    path = DATA_DERIVED / f"ib_key_levels_{sym}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run ib_key_levels first.")
    df = pd.read_parquet(path)
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _join_confluence_key_levels(sym: str) -> pd.DataFrame:
    """Left-join confluence (facts/outcomes) with key levels on session keys."""
    confluence = _load_confluence(sym)
    key_levels = _load_key_levels(sym)

    kl_keep = [c for c in key_levels.columns if c in KEY_COLS or c not in confluence.columns]
    kl = key_levels[kl_keep].copy()

    overlap = [c for c in kl.columns if c in confluence.columns and c not in KEY_COLS]
    if overlap:
        kl = kl.rename(columns={c: f"{c}_kl" for c in overlap})

    joined = confluence.merge(kl, on=KEY_COLS, how="left")
    for c in overlap:
        if f"{c}_kl" in joined.columns:
            joined[c] = joined[f"{c}_kl"]
    return joined


def _compute_fib_distance_features(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized Fib retracement distance from current IB high/low to IB range."""
    out = pd.DataFrame(index=df.index)
    ib_range = df["ib_range"].replace(0, np.nan)

    # Break direction: +1 means high was taken out first (bull break), -1 bear break.
    # Pullback direction is opposite for mean-reversion, same for continuation.
    break_dir = df["first_break_dir"].fillna(0)

    # Distance from IB high / low in % of IB range.
    out["dist_ib_high_pct"] = (df["max_high"] - df["ib_high"]) / ib_range
    out["dist_ib_low_pct"] = (df["ib_low"] - df["min_low"]) / ib_range

    # Pullback depth into IB range from the broken side.
    # If bull break (dir=+1), pullback from high down toward IB low.
    high_pull = (df["ib_high"] - df["min_low"]) / ib_range
    low_pull = (df["max_high"] - df["ib_low"]) / ib_range

    out["pullback_into_ib_pct"] = np.where(
        break_dir > 0, high_pull, np.where(break_dir < 0, low_pull, np.nan)
    )

    # Crosses back into the IB range (retracement >= small threshold).
    out["pullback_into_ib"] = (out["pullback_into_ib_pct"] > 0.10).astype(int)

    # Nearest Fib level reached by the pullback.
    # For bull break we use high_pull (retrace down); for bear break low_pull (retrace up).
    reached = np.where(break_dir > 0, high_pull.values, low_pull.values)
    reached = np.where(np.isnan(reached), np.inf, reached)  # no break -> inf
    fib_dists = np.abs(reached[:, None] - FIB_LEVELS[None, :])  # (n, 5)
    nearest_idx = np.argmin(fib_dists, axis=1)
    out["nearest_fib_level"] = FIB_LEVELS[nearest_idx]
    out["nearest_fib_distance"] = np.min(fib_dists, axis=1)

    # Explicit 0.618/0.786 deep-retrace flags.
    out["deep_retrace_618"] = (reached >= 0.618).astype(int)
    out["deep_retrace_786"] = (reached >= 0.786).astype(int)
    return out


def _compute_nearest_pd_array(df: pd.DataFrame) -> pd.DataFrame:
    """
    For pullback continuation, identify the nearest active PD array on the
    *same side* as the break (supportive array).  A high break looks for an
    array above ib_high; a low break looks for an array below ib_low.
    """
    out = pd.DataFrame(index=df.index)
    break_dir = df["first_break_dir"].fillna(0).values
    ib_high = df["ib_high"].values
    ib_low = df["ib_low"].values
    ib_range = df["ib_range"].replace(0, np.nan).values
    n = len(df)

    chosen_type = np.full(n, "NONE", dtype=object)
    chosen_top = np.full(n, np.nan, dtype=float)
    chosen_bottom = np.full(n, np.nan, dtype=float)
    chosen_mid = np.full(n, np.nan, dtype=float)
    chosen_dist_pct = np.full(n, np.nan, dtype=float)
    chosen_rank = np.full(n, 99, dtype=int)

    for prefix, top_col, bottom_col in ARRAY_SPECS:
        top = df[top_col].values if top_col in df.columns else np.full(n, np.nan)
        bottom = df[bottom_col].values if bottom_col in df.columns else np.full(n, np.nan)
        mid = (top + bottom) / 2.0

        active = (pd.notna(top)) & (pd.notna(bottom))
        # Same-side array: above ib_high for bull break, below ib_low for bear break.
        cand_high = (break_dir > 0) & active & (bottom > ib_high)
        cand_low = (break_dir < 0) & active & (top < ib_low)
        cand = cand_high | cand_low
        dist = np.where(
            cand_high, (bottom - ib_high) / ib_range * 100.0,
            np.where(cand_low, (ib_low - top) / ib_range * 100.0, np.nan)
        )

        update = cand & (np.isnan(chosen_dist_pct) | (dist < chosen_dist_pct))
        chosen_type = np.where(update, prefix.upper(), chosen_type)
        chosen_top = np.where(update, top, chosen_top)
        chosen_bottom = np.where(update, bottom, chosen_bottom)
        chosen_mid = np.where(update, mid, chosen_mid)
        chosen_dist_pct = np.where(update, dist, chosen_dist_pct)
        chosen_rank = np.where(update, ARRAY_PRIORITY[prefix], chosen_rank)

    out["nearest_pd_array_type"] = chosen_type
    out["nearest_pd_array_top"] = chosen_top
    out["nearest_pd_array_bottom"] = chosen_bottom
    out["nearest_pd_array_mid"] = chosen_mid
    out["nearest_pd_array_dist_pct"] = chosen_dist_pct
    out["nearest_pd_array_rank"] = chosen_rank
    return out


def _compute_premium_discount(df: pd.DataFrame) -> pd.DataFrame:
    """Classify the IB close relative to the dealing range at IB end."""
    out = pd.DataFrame(index=df.index)
    n = len(df)
    close = df["ib_close"].values
    eq = df["equilibrium"].values if "equilibrium" in df.columns else np.full(n, np.nan)

    valid = np.isfinite(eq) & np.isfinite(close)
    premium = valid & (close > eq)
    discount = valid & (close < eq)
    out["close_in_premium"] = premium.astype(int)
    out["close_in_discount"] = discount.astype(int)
    out["ib_close_premium_discount"] = np.where(
        premium, "PREMIUM",
        np.where(discount, "DISCOUNT", "NEUTRAL")
    )

    ib_range = df["ib_range"].replace(0, np.nan).values
    out["equilibrium_dist_pct"] = np.where(
        valid & (ib_range > 0), (close - eq) / ib_range * 100.0, np.nan
    )

    for col in ["range_high", "range_low", "equilibrium"]:
        out[col] = df[col].values if col in df.columns else np.full(n, np.nan)
    return out


def _compute_avwap_reentry(df: pd.DataFrame) -> pd.DataFrame:
    """Compare current price vs 09:30 AVWAP for pullback re-entry signals."""
    out = pd.DataFrame(index=df.index)
    break_dir = df["first_break_dir"].fillna(0)

    # Deviation from 09:30 anchor AVWAP.
    avwap_dev = df["avwap_0930_deviation_pct"].fillna(0) / 100.0

    # Re-entry to AVWAP: price crossing back through the AVWAP in the direction of the IB break.
    # For bull break, a pullback returns to / below AVWAP then reclaims it -> continuation.
    # We proxy with signed deviation flipping sign relative to break direction.
    out["avwap_deviation_pct"] = avwap_dev
    out["avwap_reclaim_bull"] = (
        (break_dir > 0) & (avwap_dev <= 0.001)
    ).astype(int)
    out["avwap_reclaim_bear"] = (
        (break_dir < 0) & (avwap_dev >= -0.001)
    ).astype(int)
    out["avwap_reclaim_aligned"] = out["avwap_reclaim_bull"] | out["avwap_reclaim_bear"]

    # AVWAP touches during IB (from ib_avwap_trend).
    out["avwap_0930_touch_count"] = df["avwap_0930_touch_count"].fillna(0).astype(int)
    return out


def _compute_mid_features(df: pd.DataFrame) -> pd.DataFrame:
    """Midpoint retest features for pullback continuation / failure."""
    out = pd.DataFrame(index=df.index)
    out["mid_lock_frac"] = df["mid_lock_frac"].fillna(0)
    out["mid_retest"] = df["mid_retest"].fillna(0).astype(int)
    out["mid_retest_minutes"] = df["mid_retest_minutes"].fillna(np.nan)

    # Speed of first break in minutes; late breaks have less time to pull back.
    out["first_break_minutes"] = df["first_break_minutes"]
    out["break_speed_bars"] = df["ib_break_speed"].fillna(np.nan)
    return out


def _compute_false_break_signals(df: pd.DataFrame) -> pd.DataFrame:
    """False-break / failed-auction components for pullback filtering."""
    out = pd.DataFrame(index=df.index)
    out["false_break_high"] = df["false_break_high"].fillna(0).astype(int)
    out["false_break_low"] = df["false_break_low"].fillna(0).astype(int)
    out["false_break_any"] = ((out["false_break_high"] == 1) | (out["false_break_low"] == 1)).astype(int)
    out["double_break"] = df["double_break"].fillna(0).astype(int)

    # Front-run / early sweep signals.
    out["front_run_active"] = df["front_run_active"].fillna(0).astype(int)
    return out


def _select_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Labels that the IB Pullback strategy can regress against."""
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


def _build_trigger_score(df: pd.DataFrame) -> pd.DataFrame:
    """Composite pullback-entry score (higher = more favorable)."""
    score = pd.Series(0, index=df.index, dtype=float)

    if "trend_aligned_with_break" in df.columns:
        score += df["trend_aligned_with_break"].fillna(0) * 2.0
    if "avwap_reclaim_aligned" in df.columns:
        score += df["avwap_reclaim_aligned"].fillna(0) * 1.5
    if "mid_retest" in df.columns:
        score += df["mid_retest"].fillna(0) * 1.0
    if "deep_retrace_618" in df.columns:
        score += df["deep_retrace_618"].fillna(0) * 1.0
    if "false_break_any" in df.columns:
        score -= df["false_break_any"].fillna(0) * 2.0
    if "fail_setup_score" in df.columns:
        score -= df["fail_setup_score"].fillna(0) * 1.0
    if "pullback_into_ib" in df.columns:
        score += df["pullback_into_ib"].fillna(0) * 0.5

    # Slight premium/discount adjustment: prefer continuation entries aligned with close position.
    if "close_in_premium" in df.columns and "close_in_discount" in df.columns:
        break_dir = df["first_break_dir"].fillna(0)
        # Bull break + close in premium is a warning; bear break + close in discount is a warning.
        score -= np.where(
            (break_dir > 0) & (df["close_in_premium"].fillna(0) == 1), 0.5, 0.0
        )
        score -= np.where(
            (break_dir < 0) & (df["close_in_discount"].fillna(0) == 1), 0.5, 0.0
        )

    # Reward presence of a same-side PD array as a continuation target / support.
    if "nearest_pd_array_rank" in df.columns:
        score += np.where(df["nearest_pd_array_rank"].fillna(99) <= 5, 0.5, 0.0)

    return pd.DataFrame({"pullback_trigger_score": score})


def process_symbol(sym: str) -> None:
    print(f"[{sym}] building IB pullback triggers")
    df = _join_confluence_key_levels(sym)

    # Preserve key session identifiers.
    meta = df[KEY_COLS].copy()

    # Core price/context columns needed by downstream strategy code.
    core = df[[
        "ib_open", "ib_high", "ib_low", "ib_close", "ib_range",
        "first_break_dir", "first_break_minutes", "first_break_time_val",
        "max_high", "min_low", "outcome_close", "prior_session_close",
    ]].copy() if all(c in df.columns for c in [
        "ib_open", "ib_high", "ib_low", "ib_close", "ib_range",
        "first_break_dir", "first_break_minutes", "first_break_time_val",
        "max_high", "min_low", "outcome_close", "prior_session_close",
    ]) else pd.DataFrame(index=df.index)

    fib_features = _compute_fib_distance_features(df)

    parts = [
        meta,
        core,
        fib_features,
        _compute_nearest_pd_array(df),
        _compute_premium_discount(df),
        _compute_avwap_reentry(df),
        _compute_mid_features(df),
        _compute_false_break_signals(df),
        _select_outcomes(df),
        _build_trigger_score(pd.concat([df, fib_features], axis=1)),
    ]

    result = pd.concat(parts, axis=1)

    # Deduplicate any column collisions from the confluence table carrying through.
    result = result.loc[:, ~result.columns.duplicated()]

    # Coerce object columns for Parquet safety.
    for col in ["nearest_pd_array_type", "ib_close_premium_discount"]:
        if col in result.columns:
            result[col] = result[col].astype(str)

    out_path = DATA_DERIVED / f"ib_pullback_triggers_{sym}.parquet"
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
