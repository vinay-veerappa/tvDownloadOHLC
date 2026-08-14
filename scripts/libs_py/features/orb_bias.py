"""
09:30 1-Minute Opening Range Breakout (ORB) Real-Time Bias Feature Module.
==========================================================================
Captures the 09:30–09:31 ET opening range and tracks causal real-time confirmed
breakouts (+0.08% / 0.10% beyond range) to establish the day's instantaneous
directional bias.

Adds columns:
    orb_1m_high           — High of the 09:30 bar
    orb_1m_low            — Low of the 09:30 bar
    orb_1m_width          — Range in points (high - low)
    orb_1m_confirmed_up   — bool, True once price confirms upside breakout
    orb_1m_confirmed_dn   — bool, True once price confirms downside breakout
    orb_1m_bias           — int: +1 (Bullish), -1 (Bearish), 0 (Neutral/Inside)
    orb_1m_formed         — bool, True for bars from 09:31 onwards
"""
from __future__ import annotations

import datetime as dt
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_orb_bias(
    df: pd.DataFrame,
    config=None,
    confirmation_pct: float = 0.0008,
) -> pd.DataFrame:
    """
    Computes 09:30 1m ORB metrics and real-time confirmed breakout states.

    Args:
        df: 1-minute DataFrame with DatetimeIndex (or trading_date column),
            high, low, close.
        config: Optional AppConfig.
        confirmation_pct: Fraction above/below range to confirm breakout
                          (default 0.0008 = +0.08%).

    Returns:
        DataFrame with attached ORB feature columns.
    """
    out = df.copy()

    # Determine date key for session grouping
    if "trading_date" in out.columns:
        date_key = out["trading_date"]
    elif hasattr(out.index, "normalize"):
        date_key = out.index.normalize()
    else:
        date_key = pd.to_datetime(out.index).normalize()

    # 1. Identify 09:30 opening bar
    t = out.index.time if hasattr(out.index, "time") else pd.to_datetime(out.index).dt.time
    is_0930_bar = t == dt.time(9, 30)

    # 2. Extract high and low of the 09:30 bar
    orb_high_series = out["high"].where(is_0930_bar).groupby(date_key).transform("max")
    orb_low_series = out["low"].where(is_0930_bar).groupby(date_key).transform("min")

    # Forward fill across the trading session
    out["orb_1m_high"] = orb_high_series.groupby(date_key).ffill()
    out["orb_1m_low"] = orb_low_series.groupby(date_key).ffill()
    out["orb_1m_width"] = out["orb_1m_high"] - out["orb_1m_low"]

    # 3. Track post-09:31 breakout confirmation
    is_post_0931 = t >= dt.time(9, 31)
    out["orb_1m_formed"] = is_post_0931 & out["orb_1m_high"].notna()

    # Confirmed breakout conditions
    up_threshold = out["orb_1m_high"] * (1.0 + confirmation_pct)
    dn_threshold = out["orb_1m_low"] * (1.0 - confirmation_pct)

    raw_up_break = is_post_0931 & (out["close"] > up_threshold)
    raw_dn_break = is_post_0931 & (out["close"] < dn_threshold)

    # Cumulative state per session (once broken, remains active for remainder of day)
    out["orb_1m_confirmed_up"] = raw_up_break.groupby(date_key).cumsum() > 0
    out["orb_1m_confirmed_dn"] = raw_dn_break.groupby(date_key).cumsum() > 0

    # Composite directional bias: +1 for Long, -1 for Short, 0 for Neutral
    bias = np.where(
        out["orb_1m_confirmed_up"] & ~out["orb_1m_confirmed_dn"],
        1,
        np.where(
            out["orb_1m_confirmed_dn"] & ~out["orb_1m_confirmed_up"],
            -1,
            0,
        ),
    )
    out["orb_1m_bias"] = np.where(out["orb_1m_formed"], bias, 0)

    logger.debug("Computed 09:30 1m ORB bias features across %d bars", len(out))
    return out
