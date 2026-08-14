"""
Level Rejection, Stalling & Absorption Engine.
==============================================
Identifies structural price interaction at key levels (Support/Resistance, VWAP, PDH/PDL):
1. Wick Rejections: Large upper/lower wicks rejecting a price zone.
2. Stalling / Absorption: Multiple consecutive touches without closing beyond the level.
3. TA-Lib Candlestick Pinbar & Engulfing Integration.
"""
from __future__ import annotations

import logging
from typing import Union
import numpy as np
import pandas as pd

try:
    import talib
    _HAS_TALIB = True
except ImportError:
    _HAS_TALIB = False

logger = logging.getLogger(__name__)


def detect_level_rejection(
    df: pd.DataFrame,
    level: Union[str, pd.Series, float],
    tolerance_pts: float = 2.5,
    min_wick_pct: float = 35.0,
    min_touches: int = 2,
    touch_window: int = 5,
) -> pd.DataFrame:
    """
    Detects rejections, absorption, and stalling at a specified price level.

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close'.
        level: Level column name, Series of dynamic levels, or scalar float.
        tolerance_pts: Distance tolerance in points to define level proximity.
        min_wick_pct: Minimum wick size as percentage of total bar range.
        min_touches: Minimum touches required within window to flag absorption.
        touch_window: Rolling bar window to count touches.

    Returns:
        DataFrame with attached rejection and absorption columns.
    """
    out = df.copy()
    high = out["high"]
    low = out["low"]
    op = out["open"]
    close = out["close"]

    # Resolve level series
    if isinstance(level, str):
        if level not in out.columns:
            raise ValueError(f"Level column '{level}' not found in DataFrame.")
        lvl_s = out[level]
    elif isinstance(level, pd.Series):
        lvl_s = level
    else:
        lvl_s = pd.Series(float(level), index=out.index)

    bar_range = (high - low).replace(0, np.nan)
    body_top = np.maximum(op, close)
    body_bot = np.minimum(op, close)

    lower_wick = body_bot - low
    upper_wick = high - body_top

    lower_wick_pct = (lower_wick / bar_range) * 100.0
    upper_wick_pct = (upper_wick / bar_range) * 100.0

    # 1. Level Proximity / Touch
    touched_support = (low <= (lvl_s + tolerance_pts)) & (high >= (lvl_s - tolerance_pts))
    touched_resistance = (high >= (lvl_s - tolerance_pts)) & (low <= (lvl_s + tolerance_pts))
    level_touch = touched_support | touched_resistance

    out["level_touch"] = level_touch

    # 2. Wick Rejections
    # Bullish Rejection: Price tested level from above/at level, printed long lower wick, closed above level
    bull_reject = (
        touched_support
        & (lower_wick_pct >= min_wick_pct)
        & (close > lvl_s)
        & (close >= (low + bar_range * 0.45))
    )

    # Bearish Rejection: Price tested level from below/at level, printed long upper wick, closed below level
    bear_reject = (
        touched_resistance
        & (upper_wick_pct >= min_wick_pct)
        & (close < lvl_s)
        & (close <= (high - bar_range * 0.45))
    )

    # 3. TA-Lib Candlestick Integration (if installed)
    if _HAS_TALIB:
        o_arr = op.values.astype(np.float64)
        h_arr = high.values.astype(np.float64)
        l_arr = low.values.astype(np.float64)
        c_arr = close.values.astype(np.float64)

        hammer = talib.CDLHAMMER(o_arr, h_arr, l_arr, c_arr) > 0
        shooting_star = talib.CDLSHOOTINGSTAR(o_arr, h_arr, l_arr, c_arr) < 0
        engulfing = talib.CDLENGULFING(o_arr, h_arr, l_arr, c_arr)

        bull_reject = bull_reject | (touched_support & (hammer | (engulfing > 0)))
        bear_reject = bear_reject | (touched_resistance & (shooting_star | (engulfing < 0)))

    out["bullish_level_rejection"] = bull_reject
    out["bearish_level_rejection"] = bear_reject

    # 4. Stalling / Absorption: Multiple touches in window without closing across level
    touch_count = level_touch.astype(int).rolling(touch_window, min_periods=1).sum()
    out["rejection_touch_count"] = touch_count

    # Stalling at Support (Touched 2+ times, none closed below level - tolerance)
    closed_below = (close < (lvl_s - tolerance_pts)).astype(int).rolling(touch_window, min_periods=1).sum()
    support_absorbed = (touch_count >= min_touches) & (closed_below == 0) & (close > lvl_s)

    # Stalling at Resistance (Touched 2+ times, none closed above level + tolerance)
    closed_above = (close > (lvl_s + tolerance_pts)).astype(int).rolling(touch_window, min_periods=1).sum()
    resistance_absorbed = (touch_count >= min_touches) & (closed_above == 0) & (close < lvl_s)

    out["is_support_absorption"] = support_absorbed
    out["is_resistance_absorption"] = resistance_absorbed
    out["is_level_stalling"] = support_absorbed | resistance_absorbed

    return out
