"""
3-Phase Break and Retest Engine.
=================================
Algorithmic state machine implementing the classical institutional pattern:
Phase 1: Breakout — Clean displacement close beyond a key horizontal level.
Phase 2: Retest   — Subsequent shallow pullback touching the broken level.
Phase 3: Rejection & Confirmation — Wick rejection confirming old resistance is now support.
"""
from __future__ import annotations

import logging
from typing import Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def detect_break_and_retest(
    df: pd.DataFrame,
    level: Union[str, pd.Series, float],
    tolerance_pts: float = 2.5,
    max_retest_bars: int = 8,
    min_wick_pct: float = 30.0,
) -> pd.DataFrame:
    """
    Evaluates 3-phase Break and Retest pattern across any level.

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close'.
        level: Level column name, Series, or scalar float.
        tolerance_pts: Distance tolerance for retest touch in points.
        max_retest_bars: Maximum bar lookahead window allowed for the retest.
        min_wick_pct: Minimum rejection wick percentage on the retest bar.

    Returns:
        DataFrame with attached break and retest signal columns.
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
    body = (close - op).abs()
    body_pct = (body / bar_range) * 100.0

    lower_wick_pct = ((np.minimum(op, close) - low) / bar_range) * 100.0
    upper_wick_pct = ((high - np.maximum(op, close)) / bar_range) * 100.0

    # ── Phase 1: Breakout Detection ──
    # Bullish Breakout: Prior bar was <= level, current bar closes solidly above level
    was_below = close.shift(1) <= lvl_s.shift(1)
    now_above = close > (lvl_s + 0.5)
    bull_breakout = was_below & now_above & (body_pct >= 45.0)

    # Bearish Breakout: Prior bar was >= level, current bar closes solidly below level
    was_above = close.shift(1) >= lvl_s.shift(1)
    now_below = close < (lvl_s - 0.5)
    bear_breakout = was_above & now_below & (body_pct >= 45.0)

    out["level_breakout_bull"] = bull_breakout
    out["level_breakout_bear"] = bear_breakout

    # ── Phase 2 & 3: Retest & Confirmation State Machine ──
    # Track bars elapsed since last breakout
    break_bull_idx = bull_breakout.astype(int)
    break_bear_idx = bear_breakout.astype(int)

    # Rolling window checks for retest
    retest_bull_sigs = np.zeros(len(out), dtype=bool)
    retest_bear_sigs = np.zeros(len(out), dtype=bool)

    highs_arr = high.values
    lows_arr = low.values
    closes_arr = close.values
    lw_arr = lower_wick_pct.values
    uw_arr = upper_wick_pct.values
    lvl_arr = lvl_s.values
    bb_arr = bull_breakout.values
    br_arr = bear_breakout.values

    last_bull_break_bar = -999
    last_bear_break_bar = -999

    for i in range(len(out)):
        if bb_arr[i]:
            last_bull_break_bar = i
        if br_arr[i]:
            last_bear_break_bar = i

        curr_lvl = lvl_arr[i]
        curr_l = lows_arr[i]
        curr_h = highs_arr[i]
        curr_c = closes_arr[i]

        # Check Bullish Retest (Level broken up in past 1..max_retest_bars)
        bars_since_bull_break = i - last_bull_break_bar
        if 1 <= bars_since_bull_break <= max_retest_bars:
            # Low touched level from above within tolerance, close held above level
            touched_level = (curr_l <= (curr_lvl + tolerance_pts)) and (curr_h >= curr_lvl)
            held_support = curr_c >= (curr_lvl - tolerance_pts)
            rejected = lw_arr[i] >= min_wick_pct or (curr_c > curr_l + (curr_h - curr_l) * 0.5)

            if touched_level and held_support and rejected:
                retest_bull_sigs[i] = True
                last_bull_break_bar = -999  # Consume breakout

        # Check Bearish Retest
        bars_since_bear_break = i - last_bear_break_bar
        if 1 <= bars_since_bear_break <= max_retest_bars:
            touched_level = (curr_h >= (curr_lvl - tolerance_pts)) and (curr_l <= curr_lvl)
            held_resistance = curr_c <= (curr_lvl + tolerance_pts)
            rejected = uw_arr[i] >= min_wick_pct or (curr_c < curr_h - (curr_h - curr_l) * 0.5)

            if touched_level and held_resistance and rejected:
                retest_bear_sigs[i] = True
                last_bear_break_bar = -999

    out["retest_bull_confirmed"] = retest_bull_sigs
    out["retest_bear_confirmed"] = retest_bear_sigs

    return out
