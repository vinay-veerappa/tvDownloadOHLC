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
    """Compute ranges for all sessions on the given date.

    Returns a dict keyed by session name: ASIA, PL, LONDON, PRE_NY, NY_AM, NY_LUNCH, NY_PM, RTH.
    Each value is the output of compute_session_range().
    """
    # Session definitions for range computation
    # Note: Asia wraps midnight (starts prior evening)
    sessions = {
        # Asia: 18:00 previous day to 00:00 (we use target_date - 1 day for the start)
        # For simplicity, we compute Asia as 18:00 of target_date to 00:00 of target_date+1
        # But since target_date is the RTH trading day, Asia before it started at 18:00 the day before.
        # We handle this by looking at the prior evening + early morning.
        # Actually, for intraday use, we want TODAY's Asia which starts at 18:00 today.
        # But if it's NY session, Asia already happened (last night). We need the Asia that precedes today's RTH.
        # So Asia = 18:00 of (target_date - 1) to 00:00 of target_date.
    }

    # Asia (prior evening 18:00 to midnight)
    asia = compute_session_range(
        df_1m, 18, 0, 0, 0, target_date, et_tz
    )
    # Adjust: Asia start should be prior day's 18:00
    # compute_session_range uses target_date for start, so we need special handling
    if df_1m is not None and not df_1m.empty:
        asia_start = pd.Timestamp(target_date).tz_localize(et_tz) - pd.Timedelta(days=1)
        asia_start = asia_start.replace(hour=18, minute=0, second=0, microsecond=0)
        asia_end = pd.Timestamp(target_date).tz_localize(et_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        # If target_date is today, the Asia that preceded today's RTH started yesterday at 18:00
        asia_mask = (df_1m.index >= asia_start) & (df_1m.index <= asia_end)
        asia_df = df_1m[asia_mask]
        if not asia_df.empty:
            asia = {
                "open": float(asia_df["open"].iloc[0]),
                "high": float(asia_df["high"].max()),
                "low": float(asia_df["low"].min()),
                "close": float(asia_df["close"].iloc[-1]),
                "range": float(asia_df["high"].max() - asia_df["low"].min()),
                "high_time": asia_df["high"].idxmax(),
                "low_time": asia_df["low"].idxmin(),
            }
        else:
            asia = {}

    # Pre-London (00:00 - 02:00)
    pl = compute_session_range(df_1m, 0, 0, 2, 0, target_date, et_tz)

    # London (02:00 - 05:00)
    london = compute_session_range(df_1m, 2, 0, 5, 0, target_date, et_tz)

    # Pre-NY (05:00 - 08:30)
    pre_ny = compute_session_range(df_1m, 5, 0, 8, 30, target_date, et_tz)

    # NY AM (09:30 - 11:30)
    ny_am = compute_session_range(df_1m, 9, 30, 11, 30, target_date, et_tz)

    # NY Lunch (12:00 - 13:00) — Herman lunch range trigger
    ny_lunch = compute_session_range(df_1m, 12, 0, 13, 0, target_date, et_tz)

    # NY PM (13:30 - 16:00)
    ny_pm = compute_session_range(df_1m, 13, 30, 16, 0, target_date, et_tz)

    # Full RTH (09:30 - 16:00)
    rth = compute_session_range(df_1m, 9, 30, 16, 0, target_date, et_tz)

    return {
        "ASIA": asia,
        "PL": pl,
        "LONDON": london,
        "PRE_NY": pre_ny,
        "NY_AM": ny_am,
        "NY_LUNCH": ny_lunch,
        "NY_PM": ny_pm,
        "RTH": rth,
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