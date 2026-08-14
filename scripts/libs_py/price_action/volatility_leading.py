"""
Leading Volatility, Compression & Trend Efficiency Module.
==========================================================
Provides zero-lag leading indicators to replace slow Wilder-smoothed indicators (like ADX):
1. Kaufman Efficiency Ratio (KER): Instantaneous directional path efficiency.
2. John Carter's TTM Volatility Squeeze: Bollinger Bands inside Keltner Channel coiling.
3. Bar Overlap Ratio: Quantifies mutual price containment to detect tight consolidation coils.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_kaufman_efficiency(
    df: pd.DataFrame,
    period: int = 5,
    efficient_threshold: float = 0.65,
    chop_threshold: float = 0.30,
) -> pd.DataFrame:
    """
    Computes Kaufman Efficiency Ratio (KER):
        KER = |Close_t - Close_{t-n}| / Sum(|Close_i - Close_{i-1}|)

    Args:
        df: 1m DataFrame with 'close'.
        period: Rolling bar lookback (default 5 for responsive LTF detection).
        efficient_threshold: Threshold above which movement is institutional trend.
        chop_threshold: Threshold below which movement is random rotational noise.

    Returns:
        DataFrame with attached 'ker_{period}', 'is_efficient_trend', 'is_choppy_noise'.
    """
    out = df.copy()
    close = out["close"]

    direction = (close - close.shift(period)).abs()
    volatility = (close - close.shift(1)).abs().rolling(window=period, min_periods=period).sum()

    ker_col = f"ker_{period}"
    out[ker_col] = (direction / volatility.replace(0, np.nan)).fillna(0.0).clip(0.0, 1.0)
    out["is_efficient_trend"] = out[ker_col] >= efficient_threshold
    out["is_choppy_noise"] = out[ker_col] <= chop_threshold

    return out


def compute_ttm_squeeze(
    df: pd.DataFrame,
    bb_length: int = 20,
    bb_mult: float = 2.0,
    kc_length: int = 20,
    kc_mult: float = 1.5,
) -> pd.DataFrame:
    """
    Computes John Carter's TTM Volatility Squeeze:
    - Squeeze ON: Bollinger Bands contract inside Keltner Channels (energy coiling).
    - Squeeze FIRED: Bollinger Bands expand outside Keltner Channels + Momentum direction.

    Args:
        df: DataFrame with 'high', 'low', 'close'.
        bb_length: Bollinger Band SMA length (default 20).
        bb_mult: Bollinger Band standard deviation multiplier (default 2.0).
        kc_length: Keltner Channel EMA length (default 20).
        kc_mult: Keltner Channel ATR multiplier (default 1.5).

    Returns:
        DataFrame with 'squeeze_on', 'squeeze_fired_bull', 'squeeze_fired_bear', 'squeeze_mom'.
    """
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]

    # 1. Bollinger Bands
    bb_mid = close.rolling(bb_length, min_periods=bb_length).mean()
    bb_std = close.rolling(bb_length, min_periods=bb_length).std()
    bb_upper = bb_mid + (bb_mult * bb_std)
    bb_lower = bb_mid - (bb_mult * bb_std)

    # 2. Keltner Channels
    kc_mid = close.ewm(span=kc_length, adjust=False).mean()
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    kc_atr = tr.rolling(kc_length, min_periods=kc_length).mean()
    kc_upper = kc_mid + (kc_mult * kc_atr)
    kc_lower = kc_mid - (kc_mult * kc_atr)

    # 3. Squeeze State
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    out["squeeze_on"] = squeeze_on

    # 4. Momentum Oscillator (Linear Regression of Delta vs Midpoint)
    highest_h = high.rolling(kc_length, min_periods=kc_length).max()
    lowest_l = low.rolling(kc_length, min_periods=kc_length).min()
    donchian_mid = (highest_h + lowest_l) / 2.0
    val_mid = (donchian_mid + kc_mid) / 2.0
    delta = close - val_mid

    # Fast slope approximation of linear regression over 12 periods
    out["squeeze_mom"] = delta.ewm(span=12, adjust=False).mean()

    # Squeeze Release / Firing Transitions
    was_squeezed = squeeze_on.shift(1).fillna(False)
    now_released = ~squeeze_on & was_squeezed

    out["squeeze_fired_bull"] = now_released & (out["squeeze_mom"] > 0)
    out["squeeze_fired_bear"] = now_released & (out["squeeze_mom"] < 0)

    return out


def compute_bar_overlap(df: pd.DataFrame, window: int = 3, threshold: float = 0.65) -> pd.DataFrame:
    """
    Calculates mutual range overlap across consecutive bars to detect tight consolidation.

    Args:
        df: DataFrame with 'high', 'low'.
        window: Number of consecutive bars to evaluate.
        threshold: Overlap fraction (0.65 = 65% mutual overlap).

    Returns:
        DataFrame with 'bar_overlap_pct' and 'is_barbwire_overlap'.
    """
    out = df.copy()
    high = out["high"]
    low = out["low"]

    overlap_high = high.rolling(window, min_periods=window).min()
    overlap_low = low.rolling(window, min_periods=window).max()
    mutual_range = np.maximum(0.0, overlap_high - overlap_low)

    total_span = high.rolling(window, min_periods=window).max() - low.rolling(window, min_periods=window).min()
    overlap_ratio = (mutual_range / total_span.replace(0, np.nan)).fillna(0.0)

    out["bar_overlap_pct"] = overlap_ratio * 100.0
    out["is_barbwire_overlap"] = overlap_ratio >= threshold

    return out
