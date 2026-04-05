"""
Bollinger Bands feature computation.

Requires upstream: atr_14 (for bandwidth normalisation)

Adds: bb_upper, bb_lower, bb_mid, bb_pct_b, bb_bandwidth
"""
from __future__ import annotations

import pandas as pd


def compute_bollinger_bands(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Standard 20-period, 2-std Bollinger Bands on 1-minute close.
    All causal (rolling with no lookahead).
    """
    period = 20
    n_std  = 2.0

    rolling = df["close"].rolling(window=period, min_periods=period)
    df["bb_mid"]   = rolling.mean()
    std            = rolling.std(ddof=1)
    # Keep strict ordering bb_upper > bb_mid > bb_lower even on flat windows.
    std = std.clip(lower=1e-12)
    df["bb_upper"] = df["bb_mid"] + n_std * std
    df["bb_lower"] = df["bb_mid"] - n_std * std

    band_width = df["bb_upper"] - df["bb_lower"]
    df["bb_pct_b"] = (df["close"] - df["bb_lower"]) / band_width.replace(0, float("nan"))
    df["bb_bandwidth"] = band_width / df["bb_mid"].replace(0, float("nan"))

    return df
