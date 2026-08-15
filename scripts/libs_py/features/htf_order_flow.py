"""
========================================================================================
Higher-Timeframe (HTF) Order Flow & Trend Alignment Filter
========================================================================================
A reusable quantitative feature module to compute and align Higher-Timeframe trend
and momentum (1-Hour / 4-Hour / Daily) with intraday 1-minute and 5-minute strategies.

Key Methods:
------------
1. Vectorized HTF EMA Slope & Cross (1H EMA 20 vs EMA 50)
2. Shifted by 1 full bar to guarantee 100% Zero Lookahead & Anti-Repainting.
3. Multi-timeframe trend scoring (+1 Bullish, -1 Bearish, 0 Neutral).
========================================================================================
"""

from __future__ import annotations
import numpy as np
import pandas as pd

class HTFOrderFlowFilter:
    """
    Decoupled HTF Order Flow Trend Alignment Engine.
    """
    @staticmethod
    def compute_1h_trend_series(df_5m: pd.DataFrame, fast_span: int = 20, slow_span: int = 50) -> np.ndarray:
        """
        Computes 1-Hour EMA trend alignment and reindexes onto 5-minute series with shift(1).
        """
        df_1h = df_5m.resample("1h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        }).dropna()

        fast_ema = df_1h["close"].ewm(span=fast_span, adjust=False).mean()
        slow_ema = df_1h["close"].ewm(span=slow_span, adjust=False).mean()

        trend_1h = (fast_ema > slow_ema).astype(int) - (fast_ema < slow_ema).astype(int)

        # Shift by 1 full 1-Hour bar so current 5m bar ONLY sees completed 1H bars!
        trend_5m = trend_1h.shift(1).reindex(df_5m.index, method="ffill").fillna(0).values
        return trend_5m
