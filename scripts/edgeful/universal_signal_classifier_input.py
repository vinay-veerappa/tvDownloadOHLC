"""
Phase 5 #6: Universal Signal Classifier Input.

Builds a single, normalized feature matrix per instrument that can train the
Layer-8 `SignalClassifier` to filter false-positive signals across all IB
breakout, pullback, and rejection strategies.

Rows are sourced from:
    - data/derived/ib_breakout_filter_{SYM}.parquet
    - data/derived/ib_pullback_triggers_{SYM}.parquet
    - data/derived/ib_rejection_triggers_{SYM}.parquet

Each row is joined with a curated set of predictor columns from the master
`ib_confluence_{SYM}.parquet` table.  Targets are attached at signal time:
    - target_play3_result   : signed normalized outcome
    - target_positive       : (target_play3_result > 0)
    - target_sign           : sign of target_play3_result

Output:
    data/derived/universal_signal_classifier_input_{SYM}.parquet

ADR-017 compliant: vectorized NumPy/Pandas only; no per-row Python loops.
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

# ---------------------------------------------------------------------------
# Curated predictor columns from ib_confluence.
# We deliberately exclude any outcome, target, bias-correct, or post-signal
# columns to avoid leakage.  All selected columns are numeric or low-cardinality
# strings LightGBM can encode.
#
# REG-1 (2026-09-05): the `*_bucket_full` columns were REMOVED from this list.
# They are whole-sample quantile labels -- a 2010 row's bucket was computed
# using data through 2026 -- so training on them leaks the future
# distribution into every split. The causal `*_trailing` variants remain;
# they encode the same information as expanding quantiles that were knowable
# on the day. `_attach_confluence_features` keeps only columns listed here,
# so the leakage is gone at the join, not merely de-weighted.
# ---------------------------------------------------------------------------
CONFLUENCE_FEATURES = [
    # IB structure
    "ib_open", "ib_high", "ib_low", "ib_close", "ib_mid", "ib_range",
    "range_pct", "range_atr", "range_pts",
    "range_bucket_trailing", "range_pctile_20", "range_pctile_60",
    "ib_range_pct_of_daily", "ib_range_5d_pctile", "ib_range_5d_contracting",
    "ib_range_5d_expanding", "ib_vs_overnight_ratio",
    "ib_inside_outside", "ib_tpo_skew", "ib_poc_price", "ib_vah", "ib_val",
    # Break context
    "first_break_dir", "first_break_minutes", "first_break_bucket",
    "ib_break_speed", "break_speed_bars", "first_break_time_val",
    "realized_dir_break", "realized_dir_ext", "realized_dir_close",
    "max_high", "min_low", "max_ext_up", "max_ext_down",
    # Trend / AVWAP / EMA
    "trend_aligned_with_break", "trend_misaligned_with_break",
    "avwap_aligned", "avwap_mixed", "break_dir_matches_avwap0930",
    "avwap_0930_deviation_pct", "avwap_0930_slope",
    "avwap_0930_touch_count", "avwap_0930_above_count", "avwap_0930_below_count",
    "ema_20_gt_50", "ema_20_slope",
    # Mid / retest
    "mid_lock_frac", "mid_lock_time", "mid_retest", "mid_retest_minutes",
    "mid_touch_count_formation", "mid_touch_count_outcome",
    "retrace_depth_pct",
    # False-break / failed auction
    "false_break_high", "false_break_low", "double_break", "double_break_order",
    "front_run_active", "front_run_activation_mins", "front_run_time",
    "fail_setup_score",
    # News / OPEX
    "news_high_impact_present", "news_0945_today", "news_1000_today",
    "news_1030_today", "ib_news_break", "ib_news_distorted",
    "news_impact_level", "minutes_since_news", "minutes_since_news_5min",
    "is_opex_week", "is_opex_friday", "is_quarterly_opex", "opex_ib_range_pctile",
    "days_to_opex", "opex_phase",
    # Session / calendar
    "dow", "dst_regime", "us_dst", "uk_dst", "early_mid_event", "gap_dir",
    "gap_pct", "gap_pts", "gap_filled", "gap_fill_minutes",
    # Volume / volatility context. vix_bucket_full REMOVED (REG-1:
    # whole-sample quantile label -- training-time leakage); the trailing
    # variant carries the causal version of the same signal.
    "vix_bucket_trailing", "vix_close",
]

# Columns that are strings but low-cardinality / useful for LightGBM categorical encoding.
CONFLUENCE_CAT_FEATURES = [
    "range_bucket_trailing", "first_break_bucket",
    "dst_regime", "news_impact_level", "opex_phase",
    "vix_bucket_trailing",
]

# Source-specific columns to normalize.
SOURCE_TABLES = {
    "ib_breakout_filter": {
        "path": DATA_DERIVED / "ib_breakout_filter_{sym}.parquet",
        "side_col": "entry_side",
        "score_col": "confluence_score",
        "filter_col": "strict_filter_pass",
        "bucket_col": "expectation_bucket",
    },
    "ib_pullback_triggers": {
        "path": DATA_DERIVED / "ib_pullback_triggers_{sym}.parquet",
        "side_col": "first_break_dir",
        "score_col": "pullback_trigger_score",
        "filter_col": "pullback_into_ib",
        "bucket_col": "nearest_fib_level",
    },
    "ib_rejection_triggers": {
        "path": DATA_DERIVED / "ib_rejection_triggers_{sym}.parquet",
        "side_col": "rejection_signal_side",
        "score_col": "rejection_trigger_score",
        "filter_col": "rejection_trigger_active",
        "bucket_col": "pd_array_type",
    },
}


def _load_confluence(sym: str) -> pd.DataFrame:
    path = DATA_DERIVED / f"ib_confluence_{sym}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run ib_master_confluence first.")
    df = pd.read_parquet(path)
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _source_rows(df: pd.DataFrame, source: str, mapping: dict) -> pd.DataFrame:
    """Normalize one signal source into the common row schema."""
    out = pd.DataFrame(index=df.index)
    out[KEY_COLS] = df[KEY_COLS].values

    # Signal side normalization -> LONG/SHORT/NONE
    side = df[mapping["side_col"]]
    if mapping["side_col"] == "first_break_dir":
        out["signal_side"] = np.where(
            side > 0, "LONG", np.where(side < 0, "SHORT", "NONE")
        )
    else:
        out["signal_side"] = (
            side.fillna("NONE")
            .astype(str)
            .str.upper()
            .replace({"0": "NONE", "1": "LONG", "-1": "SHORT"})
        )

    out["signal_source"] = np.full(len(df), source, dtype=object)
    out["signal_score"] = df[mapping["score_col"]].fillna(0).astype(float)
    out["filter_pass"] = (
        df[mapping["filter_col"]].fillna(0).astype(int) if mapping["filter_col"] in df.columns else 0
    )

    bucket = df[mapping["bucket_col"]] if mapping["bucket_col"] in df.columns else None
    if bucket is not None:
        out["signal_bucket"] = bucket.astype(str).where(bucket.notna(), "UNKNOWN")
    else:
        out["signal_bucket"] = "UNKNOWN"

    # Entry price proxy.  Use ib_close if available, otherwise ib_mid or midpoint.
    ib_close = df["ib_close"] if "ib_close" in df.columns else (
        (df["ib_high"] + df["ib_low"]) / 2.0 if "ib_high" in df.columns and "ib_low" in df.columns else pd.Series(np.nan, index=df.index)
    )
    out["entry_price"] = np.where(
        out["signal_side"] == "LONG",
        df["ib_high"].fillna(ib_close),
        np.where(out["signal_side"] == "SHORT", df["ib_low"].fillna(ib_close), ib_close),
    )

    # Target / stop distance placeholders as multiples of IB range.
    ib_range = df["ib_range"].replace(0, np.nan)
    if "recommended_target_multiple" in df.columns:
        out["target_multiple"] = df["recommended_target_multiple"].fillna(1.0)
    else:
        out["target_multiple"] = 1.0
    if "recommended_stop_multiple" in df.columns:
        out["stop_multiple"] = df["recommended_stop_multiple"].fillna(1.0)
    else:
        out["stop_multiple"] = 1.0

    denom = ib_close.replace(0, np.nan)
    out["target_distance_pct"] = (out["target_multiple"] * ib_range / denom).fillna(0) * 100.0
    out["stop_distance_pct"] = (out["stop_multiple"] * ib_range / denom).fillna(0) * 100.0

    # Targets.
    out["target_play3_result"] = df["target_play3_result"].fillna(0).astype(float) if "target_play3_result" in df.columns else 0.0
    out["target_positive"] = (out["target_play3_result"] > 0).astype(int)
    out["target_sign"] = np.sign(out["target_play3_result"]).astype(int)
    if "target_bias_correct_combined_05x" in df.columns:
        out["target_bias_correct_combined_05x"] = df["target_bias_correct_combined_05x"].fillna(0).astype(float)

    # Add a few source-specific engineered bits useful to the classifier.
    if source == "ib_breakout_filter":
        out["signal_type"] = "breakout"
    elif source == "ib_pullback_triggers":
        out["signal_type"] = "pullback"
        if "pullback_into_ib_pct" in df.columns:
            out["pullback_into_ib_pct"] = df["pullback_into_ib_pct"].fillna(0).astype(float)
        if "avwap_reclaim_aligned" in df.columns:
            out["avwap_reclaim_aligned"] = df["avwap_reclaim_aligned"].fillna(0).astype(int)
    else:  # ib_rejection_triggers
        out["signal_type"] = "rejection"
        if "rejection_to_mid_pct" in df.columns:
            out["rejection_to_mid_pct"] = df["rejection_to_mid_pct"].fillna(np.nan)
        if "extension_to_array_pct" in df.columns:
            out["extension_to_array_pct"] = df["extension_to_array_pct"].fillna(np.nan)

    return out


def _attach_confluence_features(signal_rows: pd.DataFrame, confluence: pd.DataFrame) -> pd.DataFrame:
    """Left-join signal rows to confluence predictors on session keys."""
    avail = [c for c in CONFLUENCE_FEATURES if c in confluence.columns]
    cat_avail = [c for c in CONFLUENCE_CAT_FEATURES if c in confluence.columns]

    features = confluence[KEY_COLS + avail].copy()

    # Coerce categorical columns to string for safe parquet + LightGBM encoding.
    for c in cat_avail:
        features[c] = features[c].astype(str)

    joined = signal_rows.merge(features, on=KEY_COLS, how="left")

    # If a feature column is also in signal_rows, keep the confluence version.
    # But never drop the source-row identity/target columns.
    protected = {
        "signal_source", "signal_side", "signal_type", "signal_bucket",
        "signal_score", "filter_pass", "entry_price", "target_multiple",
        "stop_multiple", "target_distance_pct", "stop_distance_pct",
        "target_play3_result", "target_play2_result", "target_play1_result",
        "target_positive", "target_sign", "pullback_into_ib_pct",
        "avwap_reclaim_aligned", "rejection_to_mid_pct", "extension_to_array_pct",
        "score_decile",
    }
    overlap = [c for c in joined.columns if c in signal_rows.columns and c not in KEY_COLS and c not in avail and c not in protected]
    joined = joined.drop(columns=overlap)
    return joined


def process_symbol(sym: str) -> None:
    print(f"[{sym}] building universal signal classifier input")

    confluence = _load_confluence(sym)

    source_frames: list[pd.DataFrame] = []
    for source, mapping in SOURCE_TABLES.items():
        path = str(mapping["path"]).format(sym=sym)
        if not Path(path).exists():
            print(f"[{sym}] WARNING: {path} missing, skipping source {source}")
            continue
        df = pd.read_parquet(path)
        df["trading_day"] = df["trading_day"].astype(str)
        rows = _source_rows(df, source, mapping)
        source_frames.append(rows)

    if not source_frames:
        raise RuntimeError(f"[{sym}] no signal source tables found")

    signal_rows = pd.concat(source_frames, axis=0, ignore_index=True)
    signal_rows = signal_rows.loc[:, ~signal_rows.columns.duplicated()]

    result = _attach_confluence_features(signal_rows, confluence)

    # Add a simple empirical edge estimate per source+score decile as a baseline.
    result["score_decile"] = (
        result.groupby("signal_source")["signal_score"]
        .transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False, duplicates="drop"))
        .fillna(-1)
        .astype(int)
    )

    # Coerce object columns to string for Parquet safety.
    for col in result.columns:
        if result[col].dtype == object:
            result[col] = result[col].astype(str)

    out_path = DATA_DERIVED / f"universal_signal_classifier_input_{sym}.parquet"
    result.to_parquet(out_path, index=False)
    print(
        f"[{sym}] wrote {len(result)} rows x {len(result.columns)} cols -> {out_path}"
    )
    print(
        f"[{sym}] positive rate={result['target_positive'].mean():.2%} "
        f"sources={result['signal_source'].value_counts().to_dict()}"
    )


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
