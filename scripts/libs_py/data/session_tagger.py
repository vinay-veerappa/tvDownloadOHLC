"""
Tag each bar with session labels.

Usage:
    from scripts.libs_py.data.session_tagger import tag_sessions
    df = tag_sessions(df, config.sessions)
"""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from scripts.trading_framework.config.config_loader import SessionConfig

logger = logging.getLogger(__name__)


def _parse_time(t: str) -> datetime.time:
    """Parse "HH:MM" string to datetime.time."""
    h, m = map(int, t.split(":"))
    return datetime.time(h, m)


def _time_to_minutes(t: str) -> int:
    """Parse "HH:MM" string → integer minutes-of-day (e.g. "09:30" → 570)."""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def tag_sessions(df: pd.DataFrame, sessions: "SessionConfig") -> pd.DataFrame:
    """
    Add session-context columns to the DataFrame in-place.

    New columns added:
        session            : str  — "pre_market" | "rth" | "post_market"
        session_block      : str  — "pre_market" | "ib" | "ny_am" | "lunch" | "ny_pm" | "post_market"
        is_rth             : bool — True if bar is within RTH (rth_start ≤ time < rth_end)
        trading_date       : datetime.date — date of the RTH session this bar belongs to
        minutes_into_session: int — minutes elapsed since 09:30 ET (negative pre-RTH, capped at 0)
        bars_into_session_1m: int — 1-minute bar count since RTH open (0-indexed)

    All time comparisons are made on US/Eastern time (the index timezone).
    The function modifies df in-place and also returns it.

    Args:
        df:       DataFrame with a tz-aware US/Eastern DatetimeIndex.
        sessions: SessionConfig instance from config_loader.

    Returns:
        The same DataFrame with new columns added.
    """
    if df.empty:
        logger.warning("tag_sessions called on empty DataFrame — returning unchanged")
        return df

    # ------------------------------------------------------------------ #
    # 1. Parse session boundary times → integer minutes-of-day (ET)
    # ------------------------------------------------------------------ #
    m_rth_start = _time_to_minutes(sessions.rth_start)   # 570 (09:30 ET)
    m_rth_end   = _time_to_minutes(sessions.rth_end)      # 960 (16:00 ET)
    m_ib_end    = _time_to_minutes(sessions.ib_end)       # 630 (10:30 ET)
    m_ny_am_end = _time_to_minutes(sessions.ny_am_end)    # 660 (11:00 ET)
    m_lunch_end = _time_to_minutes(sessions.lunch_end)    # 810 (13:30 ET)

    # ------------------------------------------------------------------ #
    # 2. Minute-of-day in US/Eastern local time (ADR-001: index is tz-aware
    #    US/Eastern — .hour and .minute return Eastern local values, pandas
    #    handles DST transparently).  No Python datetime.time objects created.
    # ------------------------------------------------------------------ #
    bar_minutes = df.index.hour * 60 + df.index.minute  # numpy int array (C-level)

    # ------------------------------------------------------------------ #
    # 3. Boolean masks — all numpy integer comparisons (no Python objects)
    # ------------------------------------------------------------------ #
    is_rth   = (bar_minutes >= m_rth_start) & (bar_minutes < m_rth_end)
    is_pre   =  bar_minutes <  m_rth_start
    is_post  =  bar_minutes >= m_rth_end

    is_ib    = is_rth & (bar_minutes <  m_ib_end)
    is_ny_am = is_rth & (bar_minutes >= m_ib_end)    & (bar_minutes < m_ny_am_end)
    is_lunch = is_rth & (bar_minutes >= m_ny_am_end) & (bar_minutes < m_lunch_end)
    is_ny_pm = is_rth & (bar_minutes >= m_lunch_end) & (bar_minutes < m_rth_end)

    # ------------------------------------------------------------------ #
    # 4. Assign categorical columns
    # ------------------------------------------------------------------ #
    session = np.where(is_pre,  "pre_market",
               np.where(is_rth,  "rth",
                                  "post_market"))
    df["session"] = pd.Categorical(session,
                                   categories=["pre_market", "rth", "post_market"],
                                   ordered=True)

    block = np.where(is_ib,    "ib",
             np.where(is_ny_am, "ny_am",
              np.where(is_lunch, "lunch",
               np.where(is_ny_pm, "ny_pm",
                np.where(is_pre,  "pre_market",
                                  "post_market")))))
    df["session_block"] = pd.Categorical(
        block,
        categories=["pre_market", "ib", "ny_am", "lunch", "ny_pm", "post_market"],
        ordered=True,
    )

    df["is_rth"] = is_rth

    # ------------------------------------------------------------------ #
    # 5. trading_date — calendar date of each bar's local timestamp
    # ------------------------------------------------------------------ #
    df["trading_date"] = df.index.date

    # ------------------------------------------------------------------ #
    # 6. minutes_into_session
    # ------------------------------------------------------------------ #
    df["minutes_into_session"] = (bar_minutes - m_rth_start).astype(int)

    # ------------------------------------------------------------------ #
    # 7. bars_into_session_1m
    #
    # Cumulative 1-minute bar count since 09:30, per trading_date.
    # Non-RTH bars get -1 (they are before the session opens or after close).
    # ------------------------------------------------------------------ #
    df["bars_into_session_1m"] = -1
    if is_rth.any():
        # Vectorised: cumcount per trading_date within RTH rows only.
        # Non-RTH rows stay at -1.
        rth_mask = df["is_rth"]
        df.loc[rth_mask, "bars_into_session_1m"] = (
            df.loc[rth_mask]
            .groupby("trading_date")
            .cumcount()
            .astype(int)
        )

    logger.debug(
        "Session tagging complete: %d RTH bars, %d pre-market, %d post-market",
        is_rth.sum(), is_pre.sum(), is_post.sum(),
    )
    return df