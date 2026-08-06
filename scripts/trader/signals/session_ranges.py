"""C6: Session Detection & Live Session Range Computation.

Detects which trading session is currently active (Asia, London, NY AM, etc.)
and computes live session high/low/range from 1-minute parquet data.

Session boundaries (all ET):
    ASIA:      18:00 - 02:00   (Globex overnight)
    LONDON:    02:00 - 08:30   (London session + pre-NY)
    NY_AM:     09:30 - 11:30   (RTH morning)
    NY_LUNCH:  11:30 - 13:30   (Low volume / manipulation zone)
    NY_PM:     13:30 - 16:00   (RTH afternoon)

Weekend: graceful exit (markets closed).
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

# ── Session boundaries (ET) ────────────────────────────────────────
# (start_hour, start_min, end_hour, end_min, label)
_SESSIONS: list[tuple[int, int, int, int, str]] = [
    (18, 0, 23, 59, "ASIA"),       # 18:00 - midnight (first half)
    (0, 0, 1, 59, "ASIA"),          # midnight - 02:00 (second half)
    (2, 0, 8, 29, "LONDON"),        # 02:00 - 08:30
    # Gap: 08:30-09:30 = pre-open, treated as LONDON tail
    (8, 30, 9, 29, "LONDON"),       # pre-NY open, still London context
    (9, 30, 11, 29, "NY_AM"),       # 09:30 - 11:30
    (11, 30, 13, 30, "NY_LUNCH"),   # 11:30 - 13:30
    (13, 31, 15, 59, "NY_PM"),      # 13:31 - 16:00
    # 16:00-18:00 = after close (not handled by intraday — defer to EOD)
]
# Note: session end times are inclusive (<=), so 13:29 means the last
# minute of NY_LUNCH is 13:29. NY_PM starts at 13:30.

# Session display order for reference
SESSION_ORDER = ["ASIA", "LONDON", "NY_AM", "NY_LUNCH", "NY_PM"]


def detect_session(now_et: datetime | None = None) -> str:
    """Detect the current trading session based on ET time.

    Returns one of: ASIA, LONDON, NY_AM, NY_LUNCH, NY_PM, WEEKEND, AFTER_CLOSE.
    """
    if now_et is None:
        import pytz
        now_et = datetime.now(pytz.timezone("America/New_York"))

    # Weekend check
    if now_et.weekday() in (5, 6):
        return "WEEKEND"

    t = now_et.time()
    for sh, sm, eh, em, label in _SESSIONS:
        start = time(sh, sm)
        end = time(eh, em)
        if start <= end:
            if start <= t <= end:
                return label
        else:
            # Wraps midnight (ASIA 18:00-02:00)
            if t >= start or t <= end:
                return label

    # 16:00-18:00 — after close
    if time(16, 0) <= t < time(18, 0):
        return "AFTER_CLOSE"

    return "UNKNOWN"


def compute_session_range(
    df_1m: pd.DataFrame,
    session_start_hour: int,
    session_start_min: int,
    session_end_hour: int,
    session_end_min: int,
    target_date: Any,
    et_tz: Any,
) -> dict:
    """Compute high/low/open/close for a specific session window on a given date.

    Args:
        df_1m: 1-minute DataFrame with ET-localized tz-aware index.
        session_start_hour/min: Session start time in ET.
        session_end_hour/min: Session end time in ET.
        target_date: The trading date (datetime.date).
        et_tz: The ET timezone object.

    Returns:
        dict with open, high, low, close, range, high_time, low_time.
        Empty dict if no data in the window.
    """
    if df_1m is None or df_1m.empty:
        return {}

    start = pd.Timestamp(target_date).tz_localize(et_tz) + pd.Timedelta(hours=session_start_hour, minutes=session_start_min)
    end = pd.Timestamp(target_date).tz_localize(et_tz) + pd.Timedelta(hours=session_end_hour, minutes=session_end_min)

    # Handle sessions that wrap midnight (e.g., Asia 18:00-02:00)
    if end <= start:
        # Session spans midnight — take from start to end of day + start of next day to end
        mask = (df_1m.index >= start) | (df_1m.index <= end)
    else:
        mask = (df_1m.index >= start) & (df_1m.index <= end)

    session_df = df_1m[mask]
    if session_df.empty:
        return {}

    return {
        "open": float(session_df["open"].iloc[0]),
        "high": float(session_df["high"].max()),
        "low": float(session_df["low"].min()),
        "close": float(session_df["close"].iloc[-1]),
        "range": float(session_df["high"].max() - session_df["low"].min()),
        "high_time": session_df["high"].idxmax(),
        "low_time": session_df["low"].idxmin(),
    }


def compute_all_session_ranges(df_1m: pd.DataFrame, target_date: Any, et_tz: Any) -> dict[str, dict]:
    """Compute ranges for ALL sessions on the given date.

    Returns a dict keyed by session name. Each value is a dict with:
        open, high, low, close, range, mid, high_time, low_time

    Session definitions (all ET, DST-aware via zoneinfo):
        ASIA:       20:00 prev day → 00:00 (ICT Asia killzone)
        LONDON:     02:00 → 05:00 (ICT London killzone)
        ONS:        04:00 → 08:15 (Overnight Session — Price Discovery Macro)
        P12:        18:00 prev day → 06:00 (Full overnight range)
        NY_AM:      09:30 → 12:00 (ICT NY AM killzone)
        NY_LUNCH:   12:00 → 13:30 (Low volume / manipulation zone)
        NY_PM:      13:30 → 16:00 (RTH afternoon)
        SUBMISSION: 14:00 → 18:15 (TBP submission range — OHLC + 50%)
        NY_P12:     prev day 06:00 → 17:59 (Previous day RTH range)
        RTH:        09:30 → 16:00 (Full RTH day)
    """
    from zoneinfo import ZoneInfo

    if et_tz is None:
        et_tz = ZoneInfo("America/New_York")

    if df_1m is None or df_1m.empty:
        return {}

    td = pd.Timestamp(target_date).tz_localize(et_tz) if not isinstance(target_date, pd.Timestamp) else target_date

    # ── ICT killzone sessions ──────────────────────────────────────────
    # Asia: 20:00 prev day → 00:00 (ICT standard)
    asia_start = td - pd.Timedelta(days=1)
    asia_start = asia_start.replace(hour=20, minute=0, second=0, microsecond=0)
    asia_end = td.replace(hour=0, minute=0, second=0, microsecond=0)
    asia = _compute_range(df_1m, asia_start, asia_end)

    # London: 02:00 → 05:00 (ICT killzone)
    london = _compute_range(df_1m,
                            td.replace(hour=2, minute=0, second=0, microsecond=0),
                            td.replace(hour=5, minute=0, second=0, microsecond=0))

    # ONS: 04:00 → 08:15 (Overnight Session — Price Discovery Macro)
    ons = _compute_range(df_1m,
                         td.replace(hour=4, minute=0, second=0, microsecond=0),
                         td.replace(hour=8, minute=15, second=0, microsecond=0))

    # P12: 18:00 prev day → 06:00 (full overnight range)
    p12_start = td - pd.Timedelta(days=1)
    p12_start = p12_start.replace(hour=18, minute=0, second=0, microsecond=0)
    p12_end = td.replace(hour=6, minute=0, second=0, microsecond=0)
    p12 = _compute_range(df_1m, p12_start, p12_end)

    # NY P12: previous day 06:00 → 17:59
    ny_p12_start = td - pd.Timedelta(days=1)
    ny_p12_start = ny_p12_start.replace(hour=6, minute=0, second=0, microsecond=0)
    ny_p12_end = td - pd.Timedelta(days=1)
    ny_p12_end = ny_p12_end.replace(hour=17, minute=59, second=0, microsecond=0)
    ny_p12 = _compute_range(df_1m, ny_p12_start, ny_p12_end)

    # Pre-London (00:00 → 02:00)
    pl = _compute_range(df_1m,
                        td.replace(hour=0, minute=0, second=0, microsecond=0),
                        td.replace(hour=2, minute=0, second=0, microsecond=0))

    # Pre-NY (05:00 → 08:30)
    pre_ny = _compute_range(df_1m,
                            td.replace(hour=5, minute=0, second=0, microsecond=0),
                            td.replace(hour=8, minute=30, second=0, microsecond=0))

    # NY AM (09:30 → 12:00) — ICT killzone
    ny_am = _compute_range(df_1m,
                           td.replace(hour=9, minute=30, second=0, microsecond=0),
                           td.replace(hour=12, minute=0, second=0, microsecond=0))

    # NY Lunch (12:00 → 13:30)
    ny_lunch = _compute_range(df_1m,
                              td.replace(hour=12, minute=0, second=0, microsecond=0),
                              td.replace(hour=13, minute=30, second=0, microsecond=0))

    # NY PM (13:30 → 16:00)
    ny_pm = _compute_range(df_1m,
                           td.replace(hour=13, minute=30, second=0, microsecond=0),
                           td.replace(hour=16, minute=0, second=0, microsecond=0))

    # Submission range (14:00 → 18:15) — TBP submission range
    submission = _compute_range(df_1m,
                                td.replace(hour=14, minute=0, second=0, microsecond=0),
                                td.replace(hour=18, minute=15, second=0, microsecond=0))

    # Full RTH (09:30 → 16:00)
    rth = _compute_range(df_1m,
                        td.replace(hour=9, minute=30, second=0, microsecond=0),
                        td.replace(hour=16, minute=0, second=0, microsecond=0))

    return {
        "ASIA": asia,
        "PL": pl,
        "LONDON": london,
        "ONS": ons,
        "P12": p12,
        "NY_P12": ny_p12,
        "PRE_NY": pre_ny,
        "NY_AM": ny_am,
        "NY_LUNCH": ny_lunch,
        "NY_PM": ny_pm,
        "SUBMISSION": submission,
        "RTH": rth,
    }


def _compute_range(df_1m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Compute OHLC + mid for a time window.

    Args:
        df_1m: 1-minute DataFrame with tz-aware index.
        start: Window start (tz-aware).
        end: Window end (tz-aware).

    Returns:
        dict with open, high, low, close, range, mid, high_time, low_time.
        Empty dict if no data in window.
    """
    if df_1m is None or df_1m.empty:
        return {}

    mask = (df_1m.index >= start) & (df_1m.index <= end)
    window = df_1m[mask]
    if window.empty:
        return {}

    high = float(window["high"].max())
    low = float(window["low"].min())

    return {
        "open": float(window["open"].iloc[0]),
        "high": high,
        "low": low,
        "close": float(window["close"].iloc[-1]),
        "range": high - low,
        "mid": (high + low) / 2,
        "high_time": window["high"].idxmax(),
        "low_time": window["low"].idxmin(),
    }


def detect_sweep(session_data: dict, target_high: float | None, target_low: float | None) -> dict:
    """Check if a session swept (broke) a target session's high or low.

    Args:
        session_data: The sweeping session's range dict (must have 'high' and 'low').
        target_high: The target session's high to check for sweep.
        target_low: The target session's low to check for sweep.

    Returns:
        dict with swept_high, swept_low booleans.
    """
    result = {"swept_high": False, "swept_low": False}
    if not session_data:
        return result
    if target_high is not None and session_data.get("high", 0) > target_high:
        result["swept_high"] = True
    if target_low is not None and session_data.get("low", 0) < target_low:
        result["swept_low"] = True
    return result