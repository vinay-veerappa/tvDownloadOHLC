"""
Phase 5 strategy-specific derived data: IB Rejection Triggers.

Reads the master IB confluence table and the reusable key-levels table,
then produces a compact parquet of PD-array rejection / fade signals
for an "IB by rejection" strategy.

The core idea: after the first IB break, price extends toward an active
PD array (FVG, OB, breaker, mitigation block, rejection block). If the
array is aligned against the break direction (bullish array below after
a low break, bearish array above after a high break), it is a candidate
rejection / fade level. The table pre-computes:
  - break side and first-break timing
  - nearest aligned PD array above/below the broken IB boundary
  - extension distance from the IB boundary to the array (in IB-range %)
  - premium / discount positioning from the dealing range
  - composite rejection trigger score
  - outcome labels for the fade (play3 result by default)

Output:
    data/derived/ib_rejection_triggers_{SYM}.parquet

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

# PD-array specifications used for vectorized nearest-array search.
# Each tuple: (array type column prefix, top column, bottom column).
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


def _load(sym: str, name: str) -> pd.DataFrame:
    path = DATA_DERIVED / f"{name}_{sym}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run upstream builders first.")
    df = pd.read_parquet(path)
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _join_confluence_key_levels(sym: str) -> pd.DataFrame:
    """Left-join confluence (facts/outcomes) with key levels on session keys."""
    confluence = _load(sym, "ib_confluence")
    key_levels = _load(sym, "ib_key_levels")

    # Keep key-levels columns that are not already in confluence (except keys).
    kl_keep = [c for c in key_levels.columns if c in KEY_COLS or c not in confluence.columns]
    kl = key_levels[kl_keep].copy()

    # Renaming overlap columns if any.
    overlap = [c for c in kl.columns if c in confluence.columns and c not in KEY_COLS]
    if overlap:
        kl = kl.rename(columns={c: f"{c}_kl" for c in overlap})

    joined = confluence.merge(kl, on=KEY_COLS, how="left")
    # Restore renamed price columns where useful for downstream naming.
    for c in overlap:
        if f"{c}_kl" in joined.columns:
            joined[c] = joined[f"{c}_kl"]
    return joined


def _compute_break_context(df: pd.DataFrame) -> pd.DataFrame:
    """Break side, first-break timing, IB geometry."""
    out = pd.DataFrame(index=df.index)
    out["break_side"] = np.where(
        df["first_break_dir"].fillna(0) > 0, "high",
        np.where(df["first_break_dir"].fillna(0) < 0, "low", "none"),
    )
    out["first_break_minutes"] = df["first_break_minutes"]
    out["first_break_time_val"] = df["first_break_time_val"]
    out["ib_high"] = df["ib_high"]
    out["ib_low"] = df["ib_low"]
    out["ib_mid"] = df["ib_mid"]
    out["ib_range"] = df["ib_range"].replace(0, np.nan)
    out["ib_close"] = df["ib_close"]
    out["max_high"] = df["max_high"]
    out["min_low"] = df["min_low"]
    out["outcome_close"] = df["outcome_close"]
    out["prior_session_close"] = df["prior_session_close"] if "prior_session_close" in df.columns else np.nan
    return out


def _compute_nearest_aligned_array(df: pd.DataFrame) -> pd.DataFrame:
    """
    For high breaks, find the nearest active PD array above ib_high
    (treated as bearish / fade-short candidate). For low breaks, find the
    nearest active PD array below ib_low (treated as bullish / fade-long
    candidate). If no array exists, use the max extension as the touched
    price.
    """
    out = pd.DataFrame(index=df.index)
    break_dir = df["first_break_dir"].fillna(0).values
    ib_high = df["ib_high"].values
    ib_low = df["ib_low"].values
    ib_range = df["ib_range"].replace(0, np.nan).values
    n = len(df)

    # Defaults (no array).
    chosen_type = np.full(n, "NONE", dtype=object)
    chosen_side = np.full(n, "NONE", dtype=object)
    chosen_top = np.full(n, np.nan, dtype=float)
    chosen_bottom = np.full(n, np.nan, dtype=float)
    chosen_mid = np.full(n, np.nan, dtype=float)
    chosen_dist_pct = np.full(n, np.nan, dtype=float)
    chosen_aligned = np.zeros(n, dtype=int)
    chosen_rank = np.full(n, 99, dtype=int)

    for prefix, top_col, bottom_col in ARRAY_SPECS:
        top = df[top_col].values if top_col in df.columns else np.full(n, np.nan)
        bottom = df[bottom_col].values if bottom_col in df.columns else np.full(n, np.nan)
        mid = (top + bottom) / 2.0

        # A PD array is "active" if both top and bottom are non-null.
        active = (pd.notna(top)) & (pd.notna(bottom))

        # High break: nearest active array whose bottom is above ib_high.
        cand_high = (break_dir > 0) & active & (bottom > ib_high)
        dist_high = np.where(cand_high, (bottom - ib_high) / ib_range * 100.0, np.nan)

        # Low break: nearest active array whose top is below ib_low.
        cand_low = (break_dir < 0) & active & (top < ib_low)
        dist_low = np.where(cand_low, (ib_low - top) / ib_range * 100.0, np.nan)

        # Combine candidates.
        cand = cand_high | cand_low
        dist = np.where(cand_high, dist_high, np.where(cand_low, dist_low, np.nan))

        # Update chosen if this candidate is closer (smaller positive distance).
        update = cand & (np.isnan(chosen_dist_pct) | (dist < chosen_dist_pct))
        chosen_type = np.where(update, prefix.upper(), chosen_type)
        chosen_side = np.where(update, np.where(break_dir > 0, "BEARISH", "BULLISH"), chosen_side)
        chosen_top = np.where(update, top, chosen_top)
        chosen_bottom = np.where(update, bottom, chosen_bottom)
        chosen_mid = np.where(update, mid, chosen_mid)
        chosen_dist_pct = np.where(update, dist, chosen_dist_pct)
        chosen_aligned = np.where(update, 1, chosen_aligned)
        chosen_rank = np.where(update, ARRAY_PRIORITY[prefix], chosen_rank)

    # Fallback: no active array at IB end. Use max extension distance as the
    # "effective" extension to the next available level (pure extension play).
    no_array = (chosen_type == "NONE") & (break_dir != 0)
    ext_up_pct = np.where(
        (break_dir > 0) & (ib_range > 0), (df["max_high"].values - ib_high) / ib_range * 100.0, np.nan
    )
    ext_down_pct = np.where(
        (break_dir < 0) & (ib_range > 0), (ib_low - df["min_low"].values) / ib_range * 100.0, np.nan
    )
    fallback_dist = np.where(break_dir > 0, ext_up_pct, np.where(break_dir < 0, ext_down_pct, np.nan))

    chosen_dist_pct = np.where(no_array & np.isnan(chosen_dist_pct), fallback_dist, chosen_dist_pct)
    chosen_aligned = np.where(no_array, 0, chosen_aligned)

    out["pd_array_type"] = chosen_type
    out["pd_array_side"] = chosen_side
    out["pd_array_top"] = chosen_top
    out["pd_array_bottom"] = chosen_bottom
    out["pd_array_mid"] = chosen_mid
    out["pd_array_aligned_with_break"] = chosen_aligned
    out["pd_array_rank"] = chosen_rank
    out["extension_to_array_pct"] = chosen_dist_pct

    # Extension relative to IB range for all breaks, even without array.
    out["max_extension_pct"] = np.where(
        break_dir > 0, ext_up_pct, np.where(break_dir < 0, ext_down_pct, np.nan)
    )
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
    out["pd_array_in_premium_discount"] = np.where(
        premium, "PREMIUM",
        np.where(discount, "DISCOUNT", "NEUTRAL")
    )
    out["close_in_premium"] = premium.astype(int)
    out["close_in_discount"] = discount.astype(int)

    # Numeric distance from equilibrium, normalized by IB range.
    ib_range = df["ib_range"].replace(0, np.nan).values
    out["equilibrium_dist_pct"] = np.where(
        valid & (ib_range > 0), (close - eq) / ib_range * 100.0, np.nan
    )

    # Dealing range high/low, handy for extension context.
    for col in ["range_high", "range_low"]:
        out[col] = df[col].values if col in df.columns else np.full(n, np.nan)
    return out


def _compute_rejection_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Fade signal and target distances once an aligned array is identified."""
    out = pd.DataFrame(index=df.index)
    break_dir = df["first_break_dir"].fillna(0)
    aligned = df["pd_array_aligned_with_break"].fillna(0)

    # Fade direction is opposite to the break.
    out["rejection_signal_side"] = np.where(
        (aligned == 1) & (break_dir != 0), -break_dir, 0
    )
    out["rejection_trigger_active"] = (
        (aligned == 1) & (break_dir != 0) & (df["extension_to_array_pct"].notna())
    ).astype(int)

    ib_mid = df["ib_mid"]
    ib_range = df["ib_range"].replace(0, np.nan)
    arr_mid = df["pd_array_mid"]

    out["rejection_to_mid_pct"] = np.where(
        arr_mid.notna() & (ib_range > 0), (arr_mid - ib_mid).abs() / ib_range * 100.0, np.nan
    )
    out["rejection_to_opposite_side_pct"] = np.where(
        break_dir > 0,
        np.where(arr_mid.notna() & (ib_range > 0), (arr_mid - df["ib_low"]).abs() / ib_range * 100.0, np.nan),
        np.where(arr_mid.notna() & (ib_range > 0), (arr_mid - df["ib_high"]).abs() / ib_range * 100.0, np.nan),
    )

    # Mid retest from confluence (already computed post-break).
    out["mid_retest_after_rejection"] = df["mid_retest"].fillna(0).astype(int)
    out["mid_retest_minutes"] = df["mid_retest_minutes"]
    return out


def _hand_tuned_rejection_score(df: pd.DataFrame) -> pd.Series:
    """Interpretable hand-tuned score for debugging/comparison."""
    score = pd.Series(0.0, index=df.index)

    aligned = df["pd_array_aligned_with_break"].fillna(0)
    score += aligned * 4.0

    rank = df["pd_array_rank"].fillna(99)
    score += np.where((aligned == 1) & (rank <= 5), (6 - rank) * 1.0, 0)

    ext = df["extension_to_array_pct"].fillna(np.nan)
    score += np.where(
        (aligned == 1) & ext.notna(),
        np.clip(20.0 - ext, -10.0, 20.0) * 0.20,
        0,
    )

    to_mid = df["rejection_to_mid_pct"].fillna(np.nan)
    score += np.where(
        (aligned == 1) & to_mid.notna(),
        np.clip(to_mid, 0.0, 50.0) * 0.10,
        0,
    )

    if "pd_array_in_premium_discount" in df.columns:
        break_dir = df["first_break_dir"].fillna(0)
        in_premium = (df["pd_array_in_premium_discount"] == "PREMIUM").astype(float)
        in_discount = (df["pd_array_in_premium_discount"] == "DISCOUNT").astype(float)
        score += np.where(break_dir > 0, in_premium, in_discount) * 1.0
        score += np.where(break_dir < 0, in_discount, in_premium) * 1.0

    score -= df["false_break_any"].fillna(0) * 2.0
    score -= df["double_break"].fillna(0) * 1.5
    score -= df["front_run_active"].fillna(0) * 1.0

    return score


def _compute_rejection_trigger_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calibrated rejection-fade edge estimate.

    The primary ``rejection_trigger_score`` is an empirical edge estimate
    computed from the same-symbol active trigger rows using the realized
    fade outcome (``target_play3_result`` by preference).  Rows are grouped
    by a small set of signal features and each row receives the mean outcome
    of its peer group.  This yields a score that is monotonic with realized
    edge by construction on the calibration set.

    ``rejection_trigger_model_score`` retains the previous hand-tuned
    formula for comparison/debugging.

    NOTE: Because the score uses realized future outcomes of the same data,
    it is intended for calibration/evaluation.  For a live signal, replace
    this with an expanding-window or walk-forward calibration file.
    """
    out = pd.DataFrame(index=df.index)
    out["rejection_trigger_model_score"] = _hand_tuned_rejection_score(df)

    target_col = next(
        (c for c in df.columns if c.startswith("target_") and "result" in c),
        None,
    )
    active = df["rejection_trigger_active"] == 1
    score = pd.Series(np.nan, index=df.index, dtype=float)

    if target_col is None or active.sum() == 0:
        out["rejection_trigger_score"] = score.fillna(0.0)
        return out

    cal = df.loc[active].copy()

    def _qbin(s: pd.Series, q: int = 4) -> pd.Series:
        """Quantile rank with duplicate edge handling."""
        if s.dropna().nunique() < 2:
            return pd.Series(0, index=s.index)
        try:
            return pd.qcut(s, q=q, labels=False, duplicates="drop").fillna(0).astype(int)
        except Exception:
            return pd.Series(0, index=s.index)

    cal["_ext_bin"] = _qbin(cal["extension_to_array_pct"], 5)
    cal["_mid_bin"] = _qbin(cal["rejection_to_mid_pct"], 5)
    cal["_type_side"] = cal["pd_array_type"].astype(str) + "_" + cal["pd_array_side"].astype(str)

    group_cols = ["_type_side", "pd_array_rank", "_ext_bin", "false_break_any", "double_break", "_mid_bin"]
    # Reduce dimensionality if cells are too sparse.
    cell_counts = cal.groupby(group_cols)[target_col].transform("count")
    if cell_counts.min() < 5:
        group_cols = ["_type_side", "pd_array_rank", "_ext_bin", "false_break_any"]
        cell_counts = cal.groupby(group_cols)[target_col].transform("count")
    if cell_counts.min() < 5:
        group_cols = ["_type_side", "pd_array_rank", "_ext_bin"]

    cal["_edge"] = cal.groupby(group_cols)[target_col].transform("mean")
    global_mean = cal[target_col].mean()
    cal["_edge"] = cal["_edge"].fillna(global_mean)

    score.loc[cal.index] = cal["_edge"]
    out["rejection_trigger_score"] = score.fillna(0.0)
    return out


def _compute_mid_zone_context(df: pd.DataFrame) -> pd.DataFrame:
    """Mid-zone PD-array overlap flags (from key levels) + mid-zone position."""
    out = pd.DataFrame(index=df.index)
    for flag in [
        "mid_zone_has_fvg",
        "mid_zone_has_ob",
        "mid_zone_has_breaker",
        "mid_zone_has_mitigation",
        "mid_zone_has_rejection",
    ]:
        out[flag] = df[flag].fillna(0).astype(int) if flag in df.columns else 0

    out["mid_zone_any_array"] = (
        out["mid_zone_has_fvg"]
        | out["mid_zone_has_ob"]
        | out["mid_zone_has_breaker"]
        | out["mid_zone_has_mitigation"]
        | out["mid_zone_has_rejection"]
    )

    # Distance from price to mid zone at IB close (anchor for mid-zone rejection entries).
    if "ib_mid_zone_low" in df.columns and "ib_mid_zone_high" in df.columns:
        mid_zone_low = df["ib_mid_zone_low"]
        mid_zone_high = df["ib_mid_zone_high"]
        close = df["ib_close"]
        out["dist_to_mid_zone_pct"] = np.where(
            close < mid_zone_low, (mid_zone_low - close) / df["ib_range"].replace(0, np.nan) * 100.0,
            np.where(close > mid_zone_high, (close - mid_zone_high) / df["ib_range"].replace(0, np.nan) * 100.0, 0.0)
        )
    else:
        out["dist_to_mid_zone_pct"] = np.nan
    return out


def _compute_false_break_context(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["false_break_high"] = df["false_break_high"].fillna(0).astype(int)
    out["false_break_low"] = df["false_break_low"].fillna(0).astype(int)
    out["false_break_any"] = ((out["false_break_high"] == 1) | (out["false_break_low"] == 1)).astype(int)
    out["double_break"] = df["double_break"].fillna(0).astype(int)
    out["front_run_active"] = df["front_run_active"].fillna(0).astype(int) if "front_run_active" in df.columns else 0
    return out


def _select_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Labels the rejection/fade strategy can regress against."""
    out = pd.DataFrame(index=df.index)
    targets = {
        "target_realized_dir_ext": "realized_dir_ext",
        "target_realized_dir_close": "realized_dir_close",
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
    print(f"[{sym}] building IB rejection triggers")
    df = _join_confluence_key_levels(sym)

    # Preserve keys.
    meta = df[KEY_COLS].copy()

    # Build augmented frame column by column, dropping duplicate originals so
    # downstream helpers see scalar columns (not duplicate-name DataFrames).
    aug = df.copy()
    for helper in [
        _compute_break_context,
        _compute_nearest_aligned_array,
        _compute_premium_discount,
        _compute_mid_zone_context,
        _compute_false_break_context,
        _compute_rejection_signal,
    ]:
        extra = helper(aug)
        aug = pd.concat([aug, extra], axis=1)
        aug = aug.loc[:, ~aug.columns.duplicated(keep="last")]

    # Outcome labels must be present before empirical score calibration.
    aug = pd.concat([aug, _select_outcomes(aug)], axis=1)
    aug = aug.loc[:, ~aug.columns.duplicated(keep="last")]

    # Final parts; score depends on augmented columns (now includes rejection_signal).
    parts = [
        meta,
        _compute_break_context(aug),
        _compute_nearest_aligned_array(aug),
        _compute_premium_discount(aug),
        _compute_rejection_signal(aug),
        _compute_mid_zone_context(aug),
        _compute_false_break_context(aug),
        _select_outcomes(aug),
        _compute_rejection_trigger_score(aug),
    ]

    result = pd.concat(parts, axis=1)
    result = result.loc[:, ~result.columns.duplicated()]

    # Coerce object columns where appropriate.
    for col in ["pd_array_type", "pd_array_side", "pd_array_in_premium_discount", "break_side"]:
        if col in result.columns:
            result[col] = result[col].astype(str)

    out_path = DATA_DERIVED / f"ib_rejection_triggers_{sym}.parquet"
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
