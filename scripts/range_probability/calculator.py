"""
Range Probability Engine - Core Mathematical Calculator & Matrix Generator
Computes intraday range expansion probabilities conditioned on opening position relative to prior range.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import zoneinfo

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


def get_bucket_index(open_pos: float) -> int:
    """
    Classify normalized open position into 12 discrete buckets:
    - Bucket 0: < 0.0 (Below prior low)
    - Buckets 1-10: Deciles [0.0, 0.1), [0.1, 0.2), ..., [0.9, 1.0)
    - Bucket 11: >= 1.0 (At or above prior high)
    """
    if pd.isna(open_pos):
        return -1
    if open_pos < 0.0:
        return 0
    elif open_pos >= 1.0:
        return 11
    else:
        # Deciles 1 through 10
        decile = int(np.floor(open_pos * 10)) + 1
        return min(10, max(1, decile))


def get_bucket_char(bucket_idx: int) -> str:
    """Returns the single character representation of a bucket (0..9, a, b)."""
    chars = "0123456789ab"
    if 0 <= bucket_idx < len(chars):
        return chars[bucket_idx]
    return "?"


def get_bucket_name(bucket_idx: int) -> str:
    """Returns human-readable name for bucket."""
    if bucket_idx == 0:
        return "below prev low"
    elif bucket_idx == 11:
        return "at/above prev high"
    elif 1 <= bucket_idx <= 10:
        low_bound = (bucket_idx - 1) / 10.0
        high_bound = bucket_idx / 10.0
        return f"{low_bound:.1f} - {high_bound:.1f}"
    return "unknown"


def build_ranges_from_ohlc(
    df: pd.DataFrame,
    range_minutes: int = 60,
    anchor_hour_et: int = 18,
    time_col: str = "time",
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volume_col: Optional[str] = "volume",
) -> pd.DataFrame:
    """
    Aggregates granular OHLC bars (1m/5m) into continuous fixed-duration ranges
    anchored to anchor_hour_et (default 18:00 ET).
    """
    data = df.copy()

    # Standardize timestamp to datetime in UTC and NY
    if time_col in data.columns:
        if pd.api.types.is_numeric_dtype(data[time_col]):
            # Check if milliseconds or seconds
            sample_val = data[time_col].iloc[0]
            unit = "ms" if sample_val > 1e11 else "s"
            data["dt_utc"] = pd.to_datetime(data[time_col], unit=unit, utc=True)
        else:
            data["dt_utc"] = pd.to_datetime(data[time_col], utc=True)
    elif isinstance(data.index, pd.DatetimeIndex):
        data["dt_utc"] = data.index.tz_localize("UTC") if data.index.tz is None else data.index.tz_convert("UTC")
    else:
        raise ValueError(f"Could not parse timestamp column {time_col}")

    # Convert to NY time
    data["dt_ny"] = data["dt_utc"].dt.tz_convert(NY_TZ)

    # Sort ascending
    data = data.sort_values("dt_utc").reset_index(drop=True)

    # Compute minutes since session anchor (18:00 ET)
    ny_hour = data["dt_ny"].dt.hour
    ny_min = data["dt_ny"].dt.minute
    et_mins = ny_hour * 60 + ny_min
    since_anchor = (et_mins - anchor_hour_et * 60 + 1440) % 1440

    # Calculate range index and range start time in minutes offset
    data["range_idx"] = np.floor(since_anchor / range_minutes).astype(int)
    offset_mins = since_anchor % range_minutes

    # Exact range start timestamp in NY
    # We truncate dt_ny by offset_mins and seconds
    data["range_start_dt"] = data["dt_ny"] - pd.to_timedelta(offset_mins, unit="m")
    data["range_start_dt"] = data["range_start_dt"].dt.floor(f"{range_minutes}min") if range_minutes in [15, 30, 60] else data["range_start_dt"]

    # Assign a unique session-range group key
    # Group key increments whenever range_start_dt changes or date shifts
    data["range_group_key"] = (data["range_start_dt"] != data["range_start_dt"].shift()).cumsum()

    # Aggregate OHLC per range block
    agg_dict = {
        open_col: "first",
        high_col: "max",
        low_col: "min",
        close_col: "last",
        "dt_utc": ["first", "last"],
        "dt_ny": "first",
    }
    if volume_col and volume_col in data.columns:
        agg_dict[volume_col] = "sum"

    grouped = data.groupby("range_group_key").agg(agg_dict)
    
    # Flatten columns
    ranges = pd.DataFrame()
    ranges["start_time_utc"] = grouped["dt_utc"]["first"]
    ranges["end_time_utc"] = grouped["dt_utc"]["last"]
    ranges["start_time_ny"] = grouped["dt_ny"]["first"]
    ranges["open"] = grouped[open_col]["first"].astype(float)
    ranges["high"] = grouped[high_col]["max"].astype(float)
    ranges["low"] = grouped[low_col]["min"].astype(float)
    ranges["close"] = grouped[close_col]["last"].astype(float)
    if volume_col and volume_col in data.columns:
        ranges["volume"] = grouped[volume_col]["sum"].astype(float)

    # Time-of-day slot in HHMM format (NY Time)
    ranges["slot"] = ranges["start_time_ny"].dt.strftime("%H%M")
    ranges["range_minutes"] = range_minutes

    # Calculate prior range levels
    ranges["prior_open"] = ranges["open"].shift(1)
    ranges["prior_high"] = ranges["high"].shift(1)
    ranges["prior_low"] = ranges["low"].shift(1)
    ranges["prior_close"] = ranges["close"].shift(1)
    ranges["prior_start_time_utc"] = ranges["start_time_utc"].shift(1)

    # Check temporal adjacency (consecutive ranges within tolerance)
    time_diff_secs = (ranges["start_time_utc"] - ranges["prior_start_time_utc"]).dt.total_seconds()
    expected_secs = range_minutes * 60
    # Adjacency allows for weekend breaks or session resets (within 1.2x of expected range duration)
    ranges["is_adjacent"] = (time_diff_secs >= expected_secs * 0.9) & (time_diff_secs <= expected_secs * 1.5)

    # Normalized opening position
    prior_span = ranges["prior_high"] - ranges["prior_low"]
    valid_span = ranges["is_adjacent"] & (prior_span > 0)

    ranges["open_pos"] = np.where(
        valid_span,
        (ranges["open"] - ranges["prior_low"]) / prior_span,
        np.nan
    )

    # Classify bucket
    ranges["bucket"] = ranges["open_pos"].apply(get_bucket_index)
    ranges["bucket_char"] = ranges["bucket"].apply(get_bucket_char)
    ranges["bucket_name"] = ranges["bucket"].apply(get_bucket_name)

    # Classify Realized Outcome on Range Close
    # Up: close > prior_high
    # Down: close < prior_low
    # Inside: prior_low <= close <= prior_high
    ranges["outcome"] = "INSIDE"
    ranges.loc[valid_span & (ranges["close"] > ranges["prior_high"]), "outcome"] = "UP"
    ranges.loc[valid_span & (ranges["close"] < ranges["prior_low"]), "outcome"] = "DOWN"

    ranges["is_resolved"] = ranges["outcome"].isin(["UP", "DOWN"])

    return ranges


def compute_probability_matrix(
    ranges_df: pd.DataFrame,
    min_prob_threshold: float = 70.0,
    min_sample_size: int = 20,
    train_ratio: float = 0.70,
) -> Dict[str, Any]:
    """
    Computes empirical transition matrices and statistics for a given set of range bars.
    Returns:
    - full_matrix: Dictionary of all (slot, bucket) combinations
    - qualified_matrix: Dictionary of cells meeting min_prob_threshold and sample size
    - pine_lut_string: 17-character encoded string for Pine Script
    """
    valid = ranges_df[ranges_df["is_adjacent"] & (ranges_df["bucket"] >= 0)].copy()
    if len(valid) == 0:
        return {"records": [], "pine_lut_string": "", "total_ranges": 0}

    # Train / Test temporal split
    split_idx = int(len(valid) * train_ratio)
    train_df = valid.iloc[:split_idx]
    test_df = valid.iloc[split_idx:]

    records = []
    
    slots = sorted(valid["slot"].unique())
    buckets = range(12)

    for slot in slots:
        for b in buckets:
            cell_all = valid[(valid["slot"] == slot) & (valid["bucket"] == b)]
            n_total = len(cell_all)
            if n_total == 0:
                continue

            n_up = (cell_all["outcome"] == "UP").sum()
            n_down = (cell_all["outcome"] == "DOWN").sum()
            n_inside = (cell_all["outcome"] == "INSIDE").sum()
            n_resolved = n_up + n_down

            resolve_rate = (n_resolved / n_total * 100.0) if n_total > 0 else 0.0

            # Full-sample directional conditional probability (for reference only)
            if n_resolved > 0:
                p_up_full = (n_up / n_resolved) * 100.0
                p_down_full = (n_down / n_resolved) * 100.0
            else:
                p_up_full = 50.0
                p_down_full = 50.0

            # Calculate Train vs Test breakdown
            cell_train = train_df[(train_df["slot"] == slot) & (train_df["bucket"] == b)]
            n_tr_total = len(cell_train)
            n_tr_up = (cell_train["outcome"] == "UP").sum()
            n_tr_down = (cell_train["outcome"] == "DOWN").sum()
            n_tr_res = n_tr_up + n_tr_down

            # Direction chosen from TRAIN data only (no look-ahead)
            if n_tr_res > 0:
                p_up_train_cond = (n_tr_up / n_tr_res) * 100.0
                p_down_train_cond = (n_tr_down / n_tr_res) * 100.0
            else:
                p_up_train_cond = 50.0
                p_down_train_cond = 50.0

            if p_up_train_cond >= 50.0:
                direction = "U"
                prob_full = p_up_full
                prob_train = p_up_train_cond
            else:
                direction = "D"
                prob_full = p_down_full
                prob_train = p_down_train_cond

            # When train data is empty for this cell, tr_prob is NaN (no look-ahead fallback)
            if n_tr_res == 0:
                tr_prob = np.nan
            else:
                tr_prob = (n_tr_up / n_tr_res * 100.0) if direction == "U" else (n_tr_down / n_tr_res * 100.0)

            cell_test = test_df[(test_df["slot"] == slot) & (test_df["bucket"] == b)]
            n_te_total = len(cell_test)
            n_te_up = (cell_test["outcome"] == "UP").sum()
            n_te_down = (cell_test["outcome"] == "DOWN").sum()
            n_te_res = n_te_up + n_te_down

            if n_te_res > 0:
                te_prob = (n_te_up / n_te_res * 100.0) if direction == "U" else (n_te_down / n_te_res * 100.0)
            else:
                te_prob = np.nan

            # Statistical significance (Z-score vs 50% random coin flip) using train prob
            p_hat = (prob_train / 100.0) if not pd.isna(prob_train) else 0.5
            z_score = float((p_hat - 0.5) / np.sqrt(0.25 / n_tr_res)) if n_tr_res > 0 else 0.0

            is_qual = bool((prob_train >= min_prob_threshold) and (n_total >= min_sample_size) and not pd.isna(prob_train))

            rec = {
                "slot": str(slot),
                "bucket": int(b),
                "bucket_char": str(get_bucket_char(b)),
                "bucket_name": str(get_bucket_name(b)),
                "direction": str(direction),
                "prob_full": float(round(prob_full, 1)),
                "prob_train": float(round(tr_prob, 1)) if not pd.isna(tr_prob) else np.nan,
                "prob_test": float(round(te_prob, 1)) if not pd.isna(te_prob) else np.nan,
                "sample_size": int(n_total),
                "sample_resolved": int(n_resolved),
                "resolve_rate": float(round(resolve_rate, 1)),
                "n_up": int(n_up),
                "n_down": int(n_down),
                "n_inside": int(n_inside),
                "z_score": float(round(z_score, 2)),
                "is_qualified": is_qual,
            }
            records.append(rec)

    # Encode Pine LUT 17-char records:
    # Key (5 chars) = slot (4 chars) + bucket_char (1 char)
    # Val (12 chars) = dir (1 char) + prob_train (3 chars 000-100) + prob_test (3 chars 000-100) + N (3 chars 000-999) + resolve_rate (2 chars 00-99)
    pine_lut_chunks = []
    for r in records:
        if r["is_qualified"]:
            slot_str = r["slot"]
            b_char = r["bucket_char"]
            d_str = r["direction"]
            p_tr_val = r["prob_train"] if not pd.isna(r["prob_train"]) else r["prob_full"]
            p_te_val = r["prob_test"] if not pd.isna(r["prob_test"]) else r["prob_full"]
            p_tr_str = f"{int(round(p_tr_val)):03d}"
            p_te_str = f"{int(round(p_te_val)):03d}"
            n_str = f"{min(999, int(r['sample_size'])):03d}"
            res_str = f"{min(99, int(round(r['resolve_rate']))):02d}"

            entry = f"{slot_str}{b_char}{d_str}{p_tr_str}{p_te_str}{n_str}{res_str}"
            pine_lut_chunks.append(entry)

    pine_lut_str = "".join(pine_lut_chunks)

    return {
        "range_minutes": int(ranges_df["range_minutes"].iloc[0]),
        "total_ranges": len(ranges_df),
        "valid_ranges": len(valid),
        "train_ranges": len(train_df),
        "test_ranges": len(test_df),
        "records": records,
        "qualified_count": len(pine_lut_chunks),
        "pine_lut_string": pine_lut_str,
    }


def compute_expanding_probabilities(ranges_df: pd.DataFrame) -> pd.DataFrame:
    """
    Walk-forward expanding-window probability for each range row.
    For a given row, the probability for its (slot, bucket) is computed
    using ONLY rows that strictly precede it in time (no look-ahead).

    Returns a DataFrame indexed like ranges_df with columns:
    - exp_prob: directional probability (%) using only prior data
    - exp_dir: 'U' or 'D' based on prior data
    - exp_n: number of prior resolved ranges in this (slot, bucket)
    - exp_res_rate: resolve rate (%) using only prior data
    """
    result = pd.DataFrame(
        index=ranges_df.index,
        columns=["exp_prob", "exp_dir", "exp_n", "exp_res_rate"],
        dtype=float,
    )
    result["exp_dir"] = ""
    result["exp_n"] = 0

    valid = ranges_df[ranges_df["is_adjacent"] & (ranges_df["bucket"] >= 0)].copy()
    if valid.empty:
        return result

    valid = valid.sort_values("start_time_utc").reset_index(drop=True)

    # Track cumulative counts per (slot, bucket) group
    cum_up = {}
    cum_down = {}
    cum_total = {}

    for idx, row in valid.iterrows():
        key = (row["slot"], row["bucket"])
        n_prior = cum_total.get(key, 0)
        n_up_prior = cum_up.get(key, 0)
        n_down_prior = cum_down.get(key, 0)
        n_res_prior = n_up_prior + n_down_prior

        if n_res_prior > 0:
            p_up = n_up_prior / n_res_prior
            if p_up >= 0.5:
                exp_dir = "U"
                exp_prob = p_up * 100.0
            else:
                exp_dir = "D"
                exp_prob = (1.0 - p_up) * 100.0
            exp_res_rate = (n_res_prior / n_prior * 100.0) if n_prior > 0 else 0.0
        else:
            exp_dir = ""
            exp_prob = np.nan
            exp_res_rate = np.nan

        # Map back to original index
        orig_idx = ranges_df[
            (ranges_df["slot"] == row["slot"])
            & (ranges_df["bucket"] == row["bucket"])
        ].index
        # Use the start_time to find the exact row
        matching = ranges_df[ranges_df["start_time_utc"] == row["start_time_utc"]]
        if len(matching) > 0:
            orig_idx = matching.index[0]
            result.loc[orig_idx, "exp_prob"] = exp_prob
            result.loc[orig_idx, "exp_dir"] = exp_dir
            result.loc[orig_idx, "exp_n"] = n_res_prior
            result.loc[orig_idx, "exp_res_rate"] = exp_res_rate

        # Update cumulative counts AFTER computing (no look-ahead)
        outcome = row["outcome"]
        cum_total[key] = n_prior + 1
        if outcome == "UP":
            cum_up[key] = n_up_prior + 1
        elif outcome == "DOWN":
            cum_down[key] = n_down_prior + 1

    return result
