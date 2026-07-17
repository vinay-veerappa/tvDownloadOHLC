"""
session_box_status.py — Vectorized Session Box Status computation.

Computes the LT/LF/ST/SF status for each of the 4 profiler session boxes
(Asia, London, NY1, NY2) from 1-minute OHLC data. Also computes the
"broken" (mid reversion) status and previous-day shifted context columns.

This is the single source of truth for session box classification.
Extracted from nqstats/classifiers.py (get_quadrant_status) and
nqstats/engine.py (_calculate_session_broken, prev-day shifts).

Session box windows (from PROFILER_KNOWLEDGE_BASE.md):
  Classification windows (where box H/L is set):
    Asia    18:00-19:29
    London  02:30-03:29
    NY1     07:30-08:29
    NY2     11:30-12:29
  Evaluation windows (where status is determined):
    Asia    19:30-02:29
    London  03:30-07:29
    NY1     08:30-11:00
    NY2     12:30-16:00
  Broken windows (where mid reversion is checked):
    Asia    02:30-16:00
    London  07:30-16:00
    NY1     11:30-16:00
    NY2     18:00-11:30 (next cycle)

Status codes (from PineScript f_calc_status):
  0 = None/Neutral
  1 = Long True (LT) — PENDING, can flip to LF
  2 = Long False (LF) — FINAL
  3 = Short True (ST) — PENDING, can flip to SF
  4 = Short False (SF) — FINAL
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import time as dt_time
from typing import Dict, Optional

# ── Box configuration ──────────────────────────────────────────────────────

# Box names in canonical order
BOX_NAMES = ["asiabox", "londonbox", "ny1box", "ny2box"]

# Human-readable session names
BOX_SESSION_MAP = {
    "asiabox": "Asia",
    "londonbox": "London",
    "ny1box": "NY1",
    "ny2box": "NY2",
}

# Evaluation windows: when status is determined (after classification window closes)
EVAL_CONFIG: Dict[str, Dict[str, str]] = {
    "asiabox":   {"start": "19:30", "end": "02:30"},
    "londonbox": {"start": "03:30", "end": "07:30"},
    "ny1box":    {"start": "08:30", "end": "11:00"},
    "ny2box":    {"start": "12:30", "end": "16:00"},
}

# Broken windows: when mid reversion is checked
BROKEN_CONFIG: list[tuple[str, str, str]] = [
    ("asiabox",   "02:30", "16:00"),   # Broken if touched during London/NY
    ("londonbox", "07:30", "16:00"),   # Broken if touched during NY
    ("ny1box",    "11:30", "16:00"),   # Broken if touched during NY2
    ("ny2box",    "18:00", "11:30"),   # Broken if touched during Next Asia
]

# Short code → full status string mapping
STATUS_SHORT_TO_FULL = {
    "LT": "Long True",
    "LF": "Long False",
    "ST": "Short True",
    "SF": "Short False",
    "None": "None",
    "Long True": "Long True",
    "Long False": "Long False",
    "Short True": "Short True",
    "Short False": "Short False",
}

# Full status → short code
STATUS_FULL_TO_SHORT = {v: k for k, v in STATUS_SHORT_TO_FULL.items() if k not in ("None",)}


# ── Core computation ──────────────────────────────────────────────────────


def compute_box_status(
    df_1m: pd.DataFrame,
    boxes_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Compute LT/LF/ST/SF status for all 4 session boxes.

    Replicates the PineScript f_calc_status logic:
      - If high breaks first and low never breaks → LT (Long True)
      - If high breaks first, then low breaks → LF (Long False)
      - If low breaks first and high never breaks → ST (Short True)
      - If low breaks first, then high breaks → SF (Short False)
      - If neither breaks → None

    Args:
        df_1m: 1-minute OHLC DataFrame with DatetimeIndex (any timezone).
        boxes_df: Optional pre-computed session box ranges.
                  Must have columns: {box}_high, {box}_low for each box.
                  If None, boxes are extracted from df_1m via
                  nqstats.sessions.extract_all_sessions().

    Returns:
        DataFrame with columns {box}_status (values: "LT","LF","ST","SF","None"),
        indexed identically to df_1m.
    """
    # Normalize to US/Eastern
    et_df = df_1m.tz_convert("US/Eastern") if df_1m.index.tz else df_1m

    # Extract boxes if not provided
    if boxes_df is None:
        from scripts.libs_py.nqstats.sessions import extract_all_sessions
        boxes_df = extract_all_sessions(et_df)

    results = pd.DataFrame(index=df_1m.index)

    for box_prefix in BOX_NAMES:
        bh_series = boxes_df[f"{box_prefix}_high"]
        bl_series = boxes_df[f"{box_prefix}_low"]

        cfg = EVAL_CONFIG[box_prefix]
        start_t = pd.Timestamp(cfg["start"]).time()
        end_t = pd.Timestamp(cfg["end"]).time()

        # Time mask for evaluation window
        if start_t < end_t:
            time_mask = (et_df.index.time >= start_t) & (et_df.index.time < end_t)
        else:
            # AsiaBox is overnight (19:30 → 02:30)
            time_mask = (et_df.index.time >= start_t) | (et_df.index.time < end_t)

        # Breakout detection
        broke_high = (et_df["high"] > bh_series) & time_mask
        broke_low = (et_df["low"] < bl_series) & time_mask

        # Trading date groups (Asia wraps midnight)
        dates = et_df.index.date
        if box_prefix == "asiabox":
            pm_mask = et_df.index.time >= start_t
            groups = pd.Series(dates, index=et_df.index)
            groups.loc[pm_mask] = groups.loc[pm_mask] + pd.Timedelta(days=1)
        else:
            groups = pd.Series(dates, index=et_df.index)

        # First occurrence per group
        h_triggers = et_df.index[broke_high].to_series().groupby(groups[broke_high]).min()
        l_triggers = et_df.index[broke_low].to_series().groupby(groups[broke_low]).min()

        # Determine status per group
        unique_groups = np.unique(groups.values)
        status_series = pd.Series("None", index=unique_groups)

        triggered_h = h_triggers.reindex(unique_groups)
        triggered_l = l_triggers.reindex(unique_groups)

        has_h = triggered_h.notna()
        has_l = triggered_l.notna()

        # First High: has high AND (no low OR high before low)
        first_h = has_h & (~has_l | (triggered_h < triggered_l))
        # First Low: has low AND (no high OR low before high)
        first_l = has_l & (~has_h | (triggered_l < triggered_h))

        status_series.loc[first_h & ~has_l] = "LT"
        status_series.loc[first_h & has_l] = "LF"
        status_series.loc[first_l & ~has_h] = "ST"
        status_series.loc[first_l & has_h] = "SF"

        # Map back to full index
        results[f"{box_prefix}_status"] = status_series.reindex(groups.values).values

    return results


def compute_box_broken(
    df_1m: pd.DataFrame,
    box_status_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-session "broken" (mid reversion) status.

    A session box is "broken" if price touches the session midpoint
    during the broken window (after the next session begins).

    Args:
        df_1m: 1-minute OHLC DataFrame (already ET-localized).
        box_status_df: DataFrame from compute_box_status() or NQStatsEngine.stats.
                       Must have {box}_mid columns.

    Returns:
        DataFrame with {box}_broken boolean columns, indexed identically to df_1m.
    """
    et_df = df_1m.tz_convert("US/Eastern") if df_1m.index.tz else df_1m
    results = pd.DataFrame(index=df_1m.index)

    for prefix, start_time, end_time in BROKEN_CONFIG:
        mid_col = f"{prefix}_mid"

        # NY2 broken uses previous day's mid (checked in next cycle)
        if prefix == "ny2box" and f"prev_{mid_col}" in box_status_df.columns:
            mid_col = f"prev_{mid_col}"

        if mid_col not in box_status_df.columns:
            results[f"{prefix}_broken"] = False
            continue

        mid_vals = box_status_df[mid_col]

        # Post-session window mask
        post_mask = et_df.between_time(start_time, end_time)

        # Check for touch: low <= mid <= high
        is_broken_mask = (
            (post_mask["low"] <= mid_vals.reindex(post_mask.index))
            & (post_mask["high"] >= mid_vals.reindex(post_mask.index))
        )

        # Group by date — was it ever broken on that date?
        broken_days = is_broken_mask.groupby(is_broken_mask.index.date).any()

        # Map back to full index
        results[f"{prefix}_broken"] = broken_days.reindex(
            box_status_df.index.date
        ).values

    return results


def compute_prev_day_shifts(
    box_status_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute previous-day shifted context columns.

    Shifts each box's status and broken flag by one trading day,
    so that "prev NY1 status" is available for Asia context filtering.

    Args:
        box_status_df: DataFrame with {box}_status and {box}_broken columns.

    Returns:
        DataFrame with prev_{box}_status and prev_{box}_broken columns.
    """
    results = pd.DataFrame(index=box_status_df.index)

    for box_prefix in BOX_NAMES:
        status_col = f"{box_prefix}_status"
        broken_col = f"{box_prefix}_broken"

        if status_col not in box_status_df.columns:
            continue

        # Shift by trading day
        trading_dates = box_status_df.index.date
        daily_status = (
            box_status_df[status_col]
            .groupby(trading_dates)
            .last()
            .shift(1)
            .fillna("None")
        )
        results[f"prev_{status_col}"] = daily_status.reindex(trading_dates).values

        if broken_col in box_status_df.columns:
            daily_broken = (
                box_status_df[broken_col]
                .groupby(trading_dates)
                .last()
                .shift(1)
                .fillna(False)
            )
            results[f"prev_{broken_col}"] = daily_broken.reindex(trading_dates).values

    return results


# ── Convenience: extract latest status as a dict ──────────────────────────


def get_latest_box_status(
    box_status_df: pd.DataFrame,
    broken_df: Optional[pd.DataFrame] = None,
    prev_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Dict[str, object]]:
    """Extract the latest session box statuses as a dict.

    Returns a dict suitable for use as the `live_sessions` parameter
    in compute_profiler():

        {
            "Asia":   {"status": "Long True", "broken": False},
            "London": {"status": "Short True", "broken": True},
            "NY1":    {"status": "None", "broken": False},
            "NY2":    {"status": "None", "broken": False},
        }

    Also returns prev-day context if prev_df is provided.
    """
    latest = box_status_df.iloc[-1]
    result: Dict[str, Dict[str, object]] = {}

    for box_prefix in BOX_NAMES:
        session_name = BOX_SESSION_MAP[box_prefix]
        status_col = f"{box_prefix}_status"
        broken_col = f"{box_prefix}_broken"

        status = latest.get(status_col, "None")
        if isinstance(status, str):
            status = STATUS_SHORT_TO_FULL.get(status, status)

        broken = False
        if broken_df is not None:
            broken = bool(broken_df.iloc[-1].get(broken_col, False))
        elif broken_col in box_status_df.columns:
            broken = bool(latest.get(broken_col, False))

        result[session_name] = {"status": status, "broken": broken}

    return result


def get_latest_prev_context(
    prev_df: pd.DataFrame,
) -> Dict[str, object]:
    """Extract previous-day context from shifted columns.

    Returns a dict with prev_ny1_status, prev_ny2_status, etc.
    suitable for the profiler context chain.
    """
    if prev_df is None or prev_df.empty:
        return {}

    latest = prev_df.iloc[-1]
    result: Dict[str, object] = {}

    for box_prefix in BOX_NAMES:
        session_name = BOX_SESSION_MAP[box_prefix]
        status_col = f"prev_{box_prefix}_status"
        broken_col = f"prev_{box_prefix}_broken"

        if status_col in prev_df.columns:
            status = latest.get(status_col, "None")
            if isinstance(status, str):
                status = STATUS_SHORT_TO_FULL.get(status, status)
            result[f"prev_{session_name.lower()}_status"] = status

        if broken_col in prev_df.columns:
            result[f"prev_{session_name.lower()}_broken"] = bool(
                latest.get(broken_col, False)
            )

    return result
