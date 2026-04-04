"""
Keltner Channel feature computation.

Requires upstream: atr_14

Adds: kc_upper, kc_lower, kc_mid
"""
from __future__ import annotations

import pandas as pd


def compute_keltner_channels(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Standard Keltner Channels: 20-period EMA ± 2 × ATR(14).
    Requires atr_14 already computed by atr.compute_atr().
    """
    period   = 20
    atr_mult = 2.0

    ema = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
    df["kc_mid"]   = ema
    df["kc_upper"] = ema + atr_mult * df["atr_14"]
    df["kc_lower"] = ema - atr_mult * df["atr_14"]

    return df
