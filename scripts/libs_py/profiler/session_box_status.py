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
# Evaluation windows: when status is determined (after classification window closes)
# End times are EXCLUSIVE (half-open [start, end)) — per PineScript time() semantics.
# Full session windows from PROFILER_KNOWLEDGE_BASE.md:
#   Asia    19:30-02:29  → end 02:30
#   London  03:30-07:29  → end 07:30
#   NY1     08:30-11:29  → end 11:30
#   NY2     12:30-15:59  → end 16:00
EVAL_CONFIG: Dict[str, Dict[str, str]] = {
    "asiabox":   {"start": "19:30", "end": "02:30"},
    "londonbox": {"start": "03:30", "end": "07:30"},
    "ny1box":    {"start": "08:30", "end": "11:30"},
    "ny2box":    {"start": "12:30", "end": "16:00"},
}

# Broken windows: when mid reversion is checked.
# Per PROFILER_KNOWLEDGE_BASE.md §3, broken windows for Asia/London/NY1
# extend to 17:00 ET (end of trading day). NY2 is the exception: it can
# only be broken when the NEXT Asia session starts (18:00), because the
# broken check begins strictly after the next session begins — and NY2
# is the last session of the day.
#   Asia:    02:30 → 17:00 (starts when London begins)
#   London:  07:30 → 17:00 (starts when NY1 begins)
#   NY1:     11:30 → 17:00 (starts when NY2 begins)
#   NY2:     18:00 → 11:30 (next day — starts when next Asia begins,
#                           checked through next NY1 start)
BROKEN_CONFIG: list[tuple[str, str, str]] = [
    ("asiabox",   "02:30", "17:00"),   # Broken if touched during London/NY
    ("londonbox", "07:30", "17:00"),   # Broken if touched during NY
    ("ny1box",    "11:30", "17:00"),   # Broken if touched during NY2 + EOD
    ("ny2box",    "18:00", "11:30"),   # Broken if touched during Next Asia/London
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

        # ADR-026 (REG-2 option A): the status is knowable only as of the bar
        # that determines it. Until 2026-09-05 the day's FINAL status was
        # stamped onto every bar of the group from 18:00 the prior evening --
        # the same-class lookahead the box_reversion causality probe caught in
        # the range stamper. Three knowability bands, per group:
        #   * before the classification window opens (classification bars are
        #     those in the box's CLASS window, not eval): "None"
        #   * during the window, before the break that settles the status has
        #     occurred: "Pending" (the PineScript convention -- LT/SF are
        #     PENDING states that can flip)
        #   * from the settling break (or window close, if nothing broke)
        #     onward: the final status
        # The settling bar is max(first h-trigger, first l-trigger) when both
        # exist (the second break makes it final), the single trigger when one
        # exists, else the window's close.
        settle_times = pd.Series(pd.NaT, index=unique_groups, dtype=object)
        for g in unique_groups:
            th = triggered_h.get(g)
            tl = triggered_l.get(g)
            cands = [t for t in (th, tl) if pd.notna(t)]
            if cands:
                settle_times.loc[g] = max(cands)
        # object dtype -> datetime dtype matching the frame (aware or naive)
        _st = pd.to_datetime(pd.Series(settle_times.values, index=unique_groups),
                             errors="coerce")
        if et_df.index.tz is not None and _st.dt.tz is None:
            _st = _st.dt.tz_localize(et_df.index.tz)
        settle_times = _st
        # Classification windows (the PROFILER_BOX_CONFIG windows from
        # nqstats.sessions, mirrored here because the config is not exported):
        # the box forms here and its status is final when the window closes.
        cls_windows = {
            "asiabox":   (pd.Timestamp("18:00").time(), pd.Timestamp("19:31").time()),
            "londonbox": (pd.Timestamp("02:30").time(), pd.Timestamp("03:31").time()),
            "ny1box":    (pd.Timestamp("07:30").time(), pd.Timestamp("08:31").time()),
            "ny2box":    (pd.Timestamp("11:30").time(), pd.Timestamp("12:31").time()),
        }
        cs, ce = cls_windows[box_prefix]
        times = et_df.index.time
        if cs < ce:
            class_mask = (times >= cs) & (times < ce)
        else:
            class_mask = (times >= cs) | (times < ce)
        cls_idx = et_df.index[class_mask]
        cls_grp = groups[class_mask]
        cls_last_per_group = (cls_idx.to_series()
                              .groupby(cls_grp.values).max()
                              .reindex(unique_groups))
        cls_first_per_group = (cls_idx.to_series()
                               .groupby(cls_grp.values).min()
                               .reindex(unique_groups))
        # groups whose window closed with no break settle at the close
        no_break = settle_times.isna()
        settle_times.loc[no_break] = cls_last_per_group[no_break]

        # Per-bar: the FINAL status is visible only at/after the group's
        # settle time; inside the window before the settle bar it is
        # "Pending"; before the window opens it is "None". The comparisons
        # are on the INDEX (bar timestamps), not on the frame's columns.
        # pd.Series(numpy-values) strips tz, so rebuild each from a
        # DatetimeIndex with the frame's tz and unit.
        idx_series = pd.Series(et_df.index, index=et_df.index)

        def _as_frame_indexed(per_group: pd.Series) -> pd.Series:
            # Map per-GROUP times onto bars. No .values round trip: numpy
            # datetime64 strips tz (UTC-naive), and tz_localize() then
            # reinterprets the wall clock, shifting the boundary by the
            # offset (09:53 ET settle -> 13:53 ET under pandas 3).
            mapped = per_group.reindex(pd.Index(groups.values))
            di = pd.to_datetime(mapped, errors="coerce")
            di = pd.DatetimeIndex(di)
            if di.tz is None and et_df.index.tz is not None:
                di = di.tz_localize(et_df.index.tz)
            elif di.tz is not None and et_df.index.tz is None:
                di = di.tz_localize(None)
            di = di.as_unit(et_df.index.unit)
            return pd.Series(di, index=et_df.index)

        bar_settle = _as_frame_indexed(settle_times)
        bar_first_cls = _as_frame_indexed(cls_first_per_group)
        final_vals = status_series.reindex(groups.values).values
        settled = (bar_settle.notna()
                   & (idx_series >= bar_settle)).values
        pre_window = (bar_first_cls.isna()
                     | (idx_series < bar_first_cls)).values
        status_vals = np.where(settled, final_vals,
                               np.where(pre_window, "None", "Pending"))

        results[f"{box_prefix}_status"] = status_vals

    return results


def compute_box_broken(
    df_1m: pd.DataFrame,
    box_status_df: pd.DataFrame,
    boxes_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Compute per-session "broken" (mid reversion) status.

    A session box is "broken" if price touches the session midpoint
    during the broken window (after the next session begins).

    Args:
        df_1m: 1-minute OHLC DataFrame (already ET-localized).
        box_status_df: DataFrame from compute_box_status() or NQStatsEngine.stats.
        boxes_df: DataFrame with {box}_mid columns (from extract_all_sessions).
                  If None, falls back to looking for mid columns in box_status_df
                  (for backward compat with NQStatsEngine which merges them).

    Returns:
        DataFrame with {box}_broken boolean columns, indexed identically to df_1m.
    """
    et_df = df_1m.tz_convert("US/Eastern") if df_1m.index.tz else df_1m
    results = pd.DataFrame(index=df_1m.index)

    # The mid columns live in the boxes DataFrame (from extract_all_sessions),
    # not in the status DataFrame. NQStatsEngine merges them into .stats, but
    # SessionBoxEngine keeps them separate. Accept either source.
    mid_source = boxes_df if boxes_df is not None else box_status_df

    for prefix, start_time, end_time in BROKEN_CONFIG:
        mid_col = f"{prefix}_mid"

        # NY2 broken window wraps overnight (18:00 → 11:30 next day), so it
        # checks the PREVIOUS day's NY2 mid during the current day's
        # Asia/London sessions.
        if prefix == "ny2box" and f"prev_{mid_col}" in mid_source.columns:
            mid_col = f"prev_{mid_col}"

        if mid_col not in mid_source.columns:
            results[f"{prefix}_broken"] = False
            continue

        mid_vals = mid_source[mid_col]

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
