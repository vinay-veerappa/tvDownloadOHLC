"""
Al Brooks Price Action & Bar-by-Bar Microstructure Engine.
==========================================================
Implements Al Brooks Price Action principles:
1. Bar Classification: Trend Bars, Dojis, Signal Bars, Barbwire (Tight Trading Range).
2. Two-Legged Pullback Leg Counter: High 1 / High 2 (H1/H2) in bull trends, Low 1 / Low 2 (L1/L2) in bear trends.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def classify_brooks_bars(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifies candlestick microstructure into Al Brooks bar categories.

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close'.

    Returns:
        DataFrame with attached bar classification columns:
        - is_bull_trend_bar, is_bear_trend_bar, is_doji_bar, is_barbwire
    """
    out = df.copy()
    op = out["open"]
    high = out["high"]
    low = out["low"]
    close = out["close"]

    bar_range = (high - low).replace(0, np.nan)
    body = (close - op).abs()
    body_pct = (body / bar_range) * 100.0

    # Trend Bars: Body >= 55% of range, close near extreme
    is_bull = (close > op) & (body_pct >= 55.0) & (close >= (high - bar_range * 0.25))
    is_bear = (close < op) & (body_pct >= 55.0) & (close <= (low + bar_range * 0.25))

    # Doji / Range Bars: Body <= 25% of range
    is_doji = body_pct <= 25.0

    out["is_bull_trend_bar"] = is_bull
    out["is_bear_trend_bar"] = is_bear
    out["is_trend_bar"] = is_bull | is_bear
    out["is_doji_bar"] = is_doji

    # Barbwire: 3+ overlapping bars with alternating colors and Doji-like indecision
    overlap_high = high.rolling(3, min_periods=3).min()
    overlap_low = low.rolling(3, min_periods=3).max()
    span = high.rolling(3, min_periods=3).max() - low.rolling(3, min_periods=3).min()
    overlap_pct = (overlap_high - overlap_low).clip(lower=0) / span.replace(0, np.nan)

    alternating_colors = (close > op) != (close.shift(1) > op.shift(1))
    out["is_barbwire"] = (overlap_pct >= 0.65) & alternating_colors & (is_doji | is_doji.shift(1))

    return out


def detect_h1_h2_l1_l2(df: pd.DataFrame, ema_period: int = 20) -> pd.DataFrame:
    """
    State machine counting two-legged pullbacks (H1/H2 in bull trends, L1/L2 in bear trends).

    Args:
        df: DataFrame with 'open', 'high', 'low', 'close'.
        ema_period: EMA lookback for trend baseline.

    Returns:
        DataFrame with 'h1_signal', 'h2_signal', 'l1_signal', 'l2_signal'.
    """
    out = classify_brooks_bars(df)
    close = out["close"]
    high = out["high"]
    low = out["low"]

    ema = close.ewm(span=ema_period, adjust=False).mean()
    out["trend_ema"] = ema

    is_bull_trend = close > ema
    is_bear_trend = close < ema

    h1_arr = np.zeros(len(out), dtype=bool)
    h2_arr = np.zeros(len(out), dtype=bool)
    l1_arr = np.zeros(len(out), dtype=bool)
    l2_arr = np.zeros(len(out), dtype=bool)

    highs = high.values
    lows = low.values
    is_bull_arr = is_bull_trend.values
    is_bear_arr = is_bear_trend.values
    is_bw_arr = out["is_barbwire"].fillna(False).values

    # State tracking for leg counting
    bull_leg_count = 0
    bear_leg_count = 0

    for i in range(1, len(out)):
        # Reset leg counts on trend flips or inside barbwire
        if not is_bull_arr[i] or is_bw_arr[i]:
            bull_leg_count = 0
        if not is_bear_arr[i] or is_bw_arr[i]:
            bear_leg_count = 0

        # ── Bull Trend: High 1 / High 2 Counting ──
        if is_bull_arr[i] and not is_bw_arr[i]:
            made_lower_low = lows[i] < lows[i - 1]
            broke_prev_high = highs[i] > highs[i - 1]

            if made_lower_low:
                bull_leg_count += 1

            if broke_prev_high:
                if bull_leg_count == 1:
                    h1_arr[i] = True
                elif bull_leg_count >= 2:
                    h2_arr[i] = True
                    bull_leg_count = 0  # Reset after H2 trigger

        # ── Bear Trend: Low 1 / Low 2 Counting ──
        if is_bear_arr[i] and not is_bw_arr[i]:
            made_higher_high = highs[i] > highs[i - 1]
            broke_prev_low = lows[i] < lows[i - 1]

            if made_higher_high:
                bear_leg_count += 1

            if broke_prev_low:
                if bear_leg_count == 1:
                    l1_arr[i] = True
                elif bear_leg_count >= 2:
                    l2_arr[i] = True
                    bear_leg_count = 0

    out["h1_signal"] = h1_arr
    out["h2_signal"] = h2_arr
    out["l1_signal"] = l1_arr
    out["l2_signal"] = l2_arr

    return out
