"""
EMA (Exponential Moving Average) feature computation.

Adds: ema_9, ema_20, ema_50, ema_200
"""
from __future__ import annotations

import pandas as pd


def compute_ema(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Compute EMAs using pandas ewm with span= (equivalent to standard EMA).
    No lookahead — adjust=False so each bar only uses prior data.
    """
    for period in (9, 20, 50, 200):
        df[f"ema_{period}"] = (
            df["close"]
            .ewm(span=period, adjust=False, min_periods=period)
            .mean()
        )
    return df
