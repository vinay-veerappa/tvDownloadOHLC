"""
Generic Range Computation Engine

Provides vectorized computation of:
  - Range H/L/Mid/Open/Close for any time window   (compute_range_hl)
  - Post-range extension-level hit flags and timing (compute_extensions)
  - Mean-reversion / breakout metrics               (compute_mr_metrics)
  - Batch macro extension columns (no bar-walk)     (add_extension_columns)
  - PD level interaction fields for macros           (add_macro_pd_fields)

All time assumptions use ET (America/New_York), naive datetimes (ADR-001).
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EXTENSION_LEVELS_DEFAULT = [0.5, 1.0, 1.5, 2.0, 3.0]


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_hhmm(t: str) -> int:
    """'HH:MM' → minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _ext_label(lvl: float) -> str:
    """0.5 → '50', 1.0 → '100', 1.5 → '150' …"""
    return str(int(round(lvl * 100)))


# ── core range computation ────────────────────────────────────────────────────

def compute_range_hl(
    bars: pd.DataFrame,
    start_time: str,
    end_time: str,
    tz: str = "America/New_York",    # informational; bars must already be ET naive
) -> pd.DataFrame:
    """
    For each ``trading_date`` present in *bars*, compute the H/L/Mid/Open/Close
    within the time window ``[start_time, end_time)``.

    Handles windows that cross midnight (e.g. OVERNIGHT 18:00–09:30) by the
    standard modular check: if ``start_m > end_m`` use OR logic.

    Parameters
    ----------
    bars : DataFrame
        Must have:
          - naive ET DatetimeIndex (ADR-001)
          - ``trading_date`` column (string or date, from session_tagger)
          - standard OHLCV columns: open, high, low, close, volume
    start_time : str   e.g. "09:30"
    end_time   : str   e.g. "10:30"

    Returns
    -------
    DataFrame indexed by ``trading_date`` with columns:
        range_high, range_low, range_mid,
        range_open, range_close,
        range_width, range_width_pct,
        bar_count
    """
    if bars.empty:
        return pd.DataFrame()

    start_m = _parse_hhmm(start_time)
    end_m   = _parse_hhmm(end_time)

    bar_min = bars.index.hour * 60 + bars.index.minute

    if start_m < end_m:
        # same-day window (most common: OR, IB, session ranges)
        mask = (bar_min >= start_m) & (bar_min < end_m)
    elif start_m > end_m:
        # crosses midnight (e.g. OVERNIGHT 18:00–09:30, ASIA 20:00–00:00)
        mask = (bar_min >= start_m) | (bar_min < end_m)
    else:
        # start == end → empty window
        logger.warning("compute_range_hl: start_time == end_time, returning empty.")
        return pd.DataFrame()

    window = bars[mask].copy()
    if window.empty:
        return pd.DataFrame()

    grp = window.groupby("trading_date")

    rng = pd.DataFrame({
        "range_high":  grp["high"].max(),
        "range_low":   grp["low"].min(),
        "range_open":  grp["open"].first(),
        "range_close": grp["close"].last(),
        "bar_count":   grp["high"].count(),
    })

    rng["range_mid"]       = (rng["range_high"] + rng["range_low"]) / 2
    rng["range_width"]     = rng["range_high"] - rng["range_low"]
    rng["range_width_pct"] = np.where(
        rng["range_mid"] > 0,
        rng["range_width"] / rng["range_mid"] * 100,
        np.nan,
    )

    return rng


# ── per-day extension hits ────────────────────────────────────────────────────

def compute_extensions(
    post_bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    levels: list[float] = EXTENSION_LEVELS_DEFAULT,
    range_end_ts: Optional[pd.Timestamp] = None,
) -> dict:
    """
    Given a slice of 1m bars *after* the range closed, determine for each
    extension level whether price reached it and how long it took.

    Parameters
    ----------
    post_bars    : 1m bars starting from range close (ET naive DatetimeIndex)
    range_high   : float — top of the range
    range_low    : float — bottom of the range
    levels       : multiples of range width (0.5 = 50% extension)
    range_end_ts : timestamp of range close (for timing calculation);
                   defaults to first bar in post_bars

    Returns
    -------
    dict  keyed by e.g.:
        ext_up_50_hit, ext_up_50_time_min,
        ext_dn_50_hit, ext_dn_50_time_min,
        ext_up_100_hit, …
    """
    out: dict = {}
    if post_bars.empty:
        for lvl in levels:
            lbl = _ext_label(lvl)
            out[f"ext_up_{lbl}_hit"]      = False
            out[f"ext_up_{lbl}_time_min"] = None
            out[f"ext_dn_{lbl}_hit"]      = False
            out[f"ext_dn_{lbl}_time_min"] = None
        return out

    width    = range_high - range_low
    t0       = range_end_ts if range_end_ts is not None else post_bars.index[0]

    highs    = post_bars["high"].values
    lows     = post_bars["low"].values
    ts       = post_bars.index

    for lvl in levels:
        lbl     = _ext_label(lvl)
        ext_up  = range_high + lvl * width
        ext_dn  = range_low  - lvl * width

        # ── upside ──
        up_mask = highs >= ext_up
        if up_mask.any():
            first_idx = np.argmax(up_mask)
            out[f"ext_up_{lbl}_hit"]      = True
            out[f"ext_up_{lbl}_time_min"] = float((ts[first_idx] - t0).total_seconds() / 60)
        else:
            out[f"ext_up_{lbl}_hit"]      = False
            out[f"ext_up_{lbl}_time_min"] = None

        # ── downside ──
        dn_mask = lows <= ext_dn
        if dn_mask.any():
            first_idx = np.argmax(dn_mask)
            out[f"ext_dn_{lbl}_hit"]      = True
            out[f"ext_dn_{lbl}_time_min"] = float((ts[first_idx] - t0).total_seconds() / 60)
        else:
            out[f"ext_dn_{lbl}_hit"]      = False
            out[f"ext_dn_{lbl}_time_min"] = None

    return out


# ── per-day MR metrics ────────────────────────────────────────────────────────

def compute_mr_metrics(
    post_bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    range_mid: float,
) -> dict:
    """
    Walk post-range bars to compute mean-reversion / breakout metrics.

    Returns
    -------
    dict with keys:
        broke_high_first, broke_low_first,
        first_bo_direction,            # "UP" | "DOWN" | "NONE"
        first_bo_held,                 # stayed outside for 2+ consecutive bars
        first_bo_retested_boundary,    # any later bar retested the broken boundary
        first_bo_failed,               # price closed fully back inside range (failed breakout)
        retest_mid_after_high_break,   retest_mid_after_high_break_time_min,
        retest_mid_after_low_break,    retest_mid_after_low_break_time_min,
        retest_opposite_after_high_break,
        retest_opposite_after_low_break,
        close_vs_range,                # "ABOVE" | "INSIDE" | "BELOW"
        final_direction,               # "UP" | "DOWN" | "NONE"
    """
    empty = dict(
        broke_high_first=False, broke_low_first=False,
        first_bo_direction="NONE", first_bo_held=False,
        first_bo_retested_boundary=False, first_bo_failed=False,
        retest_mid_after_high_break=False, retest_mid_after_high_break_time_min=None,
        retest_mid_after_low_break=False,  retest_mid_after_low_break_time_min=None,
        retest_opposite_after_high_break=False,
        retest_opposite_after_low_break=False,
        close_vs_range="INSIDE", final_direction="NONE",
    )
    if post_bars.empty:
        return empty

    highs  = post_bars["high"].values
    lows   = post_bars["low"].values
    closes = post_bars["close"].values
    ts     = post_bars.index

    # ── first boundary break ──────────────────────────────────────────────────
    up_breaks  = np.where(highs  > range_high)[0]
    dn_breaks  = np.where(lows   < range_low)[0]

    first_up  = int(up_breaks[0])  if len(up_breaks) else None
    first_dn  = int(dn_breaks[0])  if len(dn_breaks) else None

    broke_high_first = False
    broke_low_first  = False
    first_bo         = "NONE"

    if first_up is not None and first_dn is not None:
        if first_up <= first_dn:
            broke_high_first = True
            first_bo         = "UP"
        else:
            broke_low_first = True
            first_bo        = "DOWN"
    elif first_up is not None:
        broke_high_first = True
        first_bo         = "UP"
    elif first_dn is not None:
        broke_low_first = True
        first_bo        = "DOWN"

    # ── breakout held / reversed ──────────────────────────────────────────────
    bo_held              = False
    bo_retested_boundary = False
    bo_failed            = False

    if first_bo == "UP" and first_up is not None:
        # held: 2+ consecutive bars with close > range_high
        above_seq = closes[first_up:] > range_high
        if len(above_seq) >= 2 and above_seq[0] and above_seq[1]:
            bo_held = True
        # retested_boundary: any later bar's low dips back below range_high
        later_lows   = lows[first_up + 1:]
        later_closes = closes[first_up + 1:]
        bo_retested_boundary = bool(len(later_lows)   and np.any(later_lows   < range_high))
        # failed: price closed fully back inside range (reversed through range)
        bo_failed            = bool(len(later_closes) and np.any(later_closes < range_low))

    elif first_bo == "DOWN" and first_dn is not None:
        below_seq = closes[first_dn:] < range_low
        if len(below_seq) >= 2 and below_seq[0] and below_seq[1]:
            bo_held = True
        later_highs  = highs[first_dn + 1:]
        later_closes = closes[first_dn + 1:]
        bo_retested_boundary = bool(len(later_highs)  and np.any(later_highs  > range_low))
        bo_failed            = bool(len(later_closes) and np.any(later_closes > range_high))

    # ── mid retest after high break ───────────────────────────────────────────
    mid_retest_after_up       = False
    mid_retest_after_up_time  = None
    opp_retest_after_up       = False

    if first_up is not None:
        post_up     = post_bars.iloc[first_up + 1:]
        t0          = ts[first_up]
        mid_hits    = post_up[post_up["low"] <= range_mid]
        if not mid_hits.empty:
            mid_retest_after_up      = True
            mid_retest_after_up_time = float((mid_hits.index[0] - t0).total_seconds() / 60)
        opp_hits = post_up[post_up["low"] <= range_low]
        if not opp_hits.empty:
            opp_retest_after_up = True

    # ── mid retest after low break ────────────────────────────────────────────
    mid_retest_after_dn       = False
    mid_retest_after_dn_time  = None
    opp_retest_after_dn       = False

    if first_dn is not None:
        post_dn     = post_bars.iloc[first_dn + 1:]
        t0          = ts[first_dn]
        mid_hits    = post_dn[post_dn["high"] >= range_mid]
        if not mid_hits.empty:
            mid_retest_after_dn      = True
            mid_retest_after_dn_time = float((mid_hits.index[0] - t0).total_seconds() / 60)
        opp_hits = post_dn[post_dn["high"] >= range_high]
        if not opp_hits.empty:
            opp_retest_after_dn = True

    # ── final close location ──────────────────────────────────────────────────
    last_close = float(closes[-1])
    if last_close > range_high:
        close_loc = "ABOVE"
        final_dir = "UP"
    elif last_close < range_low:
        close_loc = "BELOW"
        final_dir = "DOWN"
    else:
        close_loc = "INSIDE"
        final_dir = "NONE"

    return dict(
        broke_high_first=broke_high_first,
        broke_low_first=broke_low_first,
        first_bo_direction=first_bo,
        first_bo_held=bo_held,
        first_bo_retested_boundary=bo_retested_boundary,
        first_bo_failed=bo_failed,
        retest_mid_after_high_break=mid_retest_after_up,
        retest_mid_after_high_break_time_min=mid_retest_after_up_time,
        retest_mid_after_low_break=mid_retest_after_dn,
        retest_mid_after_low_break_time_min=mid_retest_after_dn_time,
        retest_opposite_after_high_break=opp_retest_after_up,
        retest_opposite_after_low_break=opp_retest_after_dn,
        close_vs_range=close_loc,
        final_direction=final_dir,
    )


# ── batch helpers for macro pipeline ─────────────────────────────────────────

def add_extension_columns(
    df: pd.DataFrame,
    levels: list[float] = EXTENSION_LEVELS_DEFAULT,
    high_col: str  = "high",
    low_col: str   = "low",
    post_h_col: str = "post_h",
    post_l_col: str = "post_l",
) -> pd.DataFrame:
    """
    Vectorized extension hit columns for the macro pipeline.

    Uses pre-computed ``post_h`` / ``post_l`` columns (already in
    macro_records) to determine HIT booleans without bar-walking.
    Timing columns are **not** computed here (require bar walk — deferred
    to Phase 3 compute_ranges pipeline).

    New columns added:
        macro_width,
        ext_up_50_hit,  ext_dn_50_hit,
        ext_up_100_hit, ext_dn_100_hit,
        …  (one pair per level in *levels*)
    """
    df = df.copy()

    w = df[high_col] - df[low_col]
    df["macro_width"] = w

    for lvl in levels:
        lbl = _ext_label(lvl)
        df[f"ext_up_{lbl}_hit"] = df[post_h_col] >= (df[high_col] + lvl * w)
        df[f"ext_dn_{lbl}_hit"] = df[post_l_col] <= (df[low_col]  - lvl * w)

    return df


def add_macro_pd_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add PD level interaction fields to a macro DataFrame.

    Requires columns: ``high``, ``low``, ``pdh``, ``pdl``
    (pdh/pdl come from the existing macro pipeline).

    New columns:
        macro_high_vs_pdh  : "ABOVE" | "BELOW"
        macro_low_vs_pdl   : "ABOVE" | "BELOW"
        broke_pdh_during_macro : bool
        broke_pdl_during_macro : bool
    """
    df = df.copy()
    df["macro_high_vs_pdh"]      = np.where(df["high"] > df["pdh"], "ABOVE", "BELOW")
    df["macro_low_vs_pdl"]       = np.where(df["low"]  < df["pdl"], "BELOW", "ABOVE")
    df["broke_pdh_during_macro"] = df["high"] > df["pdh"]
    df["broke_pdl_during_macro"] = df["low"]  < df["pdl"]
    return df
