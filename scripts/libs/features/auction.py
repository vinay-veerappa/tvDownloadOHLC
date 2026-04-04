"""
Auction market theory features.

Adds:
    fast_move_detected  — bool: bar range > 2× recent average range (velocity spike)
    single_print_level  — bool: bar not revisited in next N bars (placeholder for
                          full TPO-based single print logic)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_auction_features(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Fast-move detection: 1-minute bar range > 2.0× rolling 20-bar average range.
    Causal — only uses prior bars.
    """
    bar_range = df["high"] - df["low"]
    avg_range = bar_range.rolling(20, min_periods=5).mean()
    df["fast_move_detected"] = bar_range > (2.0 * avg_range)

    # Single-print placeholder — full implementation requires forward-bar scan
    # which must be deferred to the backtesting loop (not a causal feature).
    # For now, default False so the column is present for the registry.
    df["single_print_level"] = False

    return df
