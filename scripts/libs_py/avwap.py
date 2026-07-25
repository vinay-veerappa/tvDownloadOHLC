"""
Anchored VWAP utilities.

Provides a vectorized anchored VWAP and standard-deviation bands from a
user-specified anchor time (default 09:30 ET for IB start).

The VWAP is reset every time the anchor time is crossed, so each session gets
its own anchored VWAP starting at the chosen time-of-day.  Overnight sessions
with cross-midnight anchors are handled via the same time-of-day reset rule.
"""

from datetime import time
from typing import Tuple

import numpy as np
import pandas as pd


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _anchor_reset_mask(index: pd.DatetimeIndex, anchor_minute: int, reset_days: pd.Series) -> pd.Series:
    """
    Return boolean Series indicating rows where a new anchor starts.
    Anchor resets when bar minute-of-day crosses the anchor time on a day that
    is different from the prior row's anchor day (handles overnight bars).
    The first row of the input is always treated as a reset (per-day call).
    """
    idx = pd.DatetimeIndex(index)
    minutes = idx.hour * 60 + idx.minute
    anchor_day = reset_days.where(minutes >= anchor_minute)
    # Forward-fill within each anchor stretch.
    anchor_day = anchor_day.ffill()
    reset = anchor_day.diff().ne(0)
    reset.iloc[0] = True
    return reset


def compute_avwap(
    df: pd.DataFrame,
    anchor_time: time = time(9, 30),
    price_col: str = "close",
    volume_col: str = "volume",
    dev_bands: Tuple[float, ...] = (1.0, 2.0),
    slope_window: int = 15,
) -> pd.DataFrame:
    """
    Compute anchored VWAP and bands.

    Parameters
    ----------
    df : DataFrame with DatetimeIndex (naive ET/UTC) and columns price_col,
         volume_col, plus high/low (used for band touches).
    anchor_time : time of day to reset the anchor (e.g., 09:30).
    price_col : column used as typical price proxy (default close).
    volume_col : volume column.
    dev_bands : standard-deviation multipliers to return (default 1,2).
    slope_window : number of bars for VWAP slope.

    Returns
    -------
    DataFrame with original columns plus:
        avwap_price, avwap_deviation_pct, avwap_slope,
        avwap_above_count, avwap_below_count, avwap_touch_count,
        avwap_break_dir, avwap_distance_at_break,
        avwap_std_upper_{k}, avwap_std_lower_{k}
    """
    anchor_min = _time_to_minutes(anchor_time)
    idx = pd.DatetimeIndex(df.index)
    minutes = idx.hour * 60 + idx.minute

    # Use date component as reset key; for cross-midnight sessions the anchor
    # starts on the calendar day when the anchor time is first reached.
    days = pd.Series(pd.DatetimeIndex(idx).date, index=idx)
    reset = _anchor_reset_mask(idx, anchor_min, days)
    group = reset.cumsum()

    tp = (df["high"] + df["low"] + df[price_col]) / 3.0
    pv = tp * df[volume_col]

    # Cumulative sums within each anchor group.
    cum_pv = pv.groupby(group).cumsum()
    cum_v = df[volume_col].groupby(group).cumsum()
    avwap = cum_pv / cum_v.replace(0, np.nan)

    # Deviation of price from AVWAP (used for bands and slope).
    dev = df[price_col] - avwap
    deviation_pct = dev / avwap.replace(0, np.nan) * 100.0

    # Rolling std of deviation within anchor group (minimum 10 bars).
    roll_std = dev.groupby(group).transform(
        lambda s: s.rolling(max(slope_window, 10), min_periods=5).std()
    )

    out = pd.DataFrame(index=idx)
    out["avwap_price"] = avwap
    out["avwap_deviation_pct"] = deviation_pct
    out["avwap_slope"] = avwap.groupby(group).transform(
        lambda s: s.diff(slope_window).fillna(0.0)
    )

    for k in dev_bands:
        out[f"avwap_std_upper_{int(k)}"] = avwap + k * roll_std
        out[f"avwap_std_lower_{int(k)}"] = avwap - k * roll_std

    # Per-bar counts within the current anchor stretch.
    above = (df[price_col] > avwap).astype(int)
    below = (df[price_col] < avwap).astype(int)
    touch = ((df["low"] <= avwap) & (df["high"] >= avwap)).astype(int)
    out["avwap_above_count"] = above.groupby(group).cumsum()
    out["avwap_below_count"] = below.groupby(group).cumsum()
    out["avwap_touch_count"] = touch.groupby(group).cumsum()

    # Break direction: at each bar, if price closes above AVWAP => +1, below => -1, equal => 0.
    out["avwap_break_dir"] = np.where(
        df[price_col] > avwap, 1,
        np.where(df[price_col] < avwap, -1, 0)
    )
    out["avwap_distance_at_break"] = deviation_pct

    return out
