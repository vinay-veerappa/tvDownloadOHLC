"""
Auction market theory features.

Adds:
    fast_move_detected  — bool: bar range > 2× recent average range (velocity spike)
    roc_10bar           — 10-bar rate of change on close (fractional return)
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
    df["roc_10bar"] = df["close"].pct_change(10)

    # Metadata for the fast move
    df["fast_move_direction"] = np.where(df["close"] > df["open"], 1, -1)
    df["fast_move_origin"] = np.where(df["close"] > df["open"], df["low"], df["high"])
    
    # Zero out where not detected
    df.loc[~df["fast_move_detected"], "fast_move_direction"] = 0
    df.loc[~df["fast_move_detected"], "fast_move_origin"] = np.nan

    # Single-print placeholder — full implementation requires forward-bar scan
    # which must be deferred to the backtesting loop (not a causal feature).
    # For now, default False so the column is present for the registry.
    df["single_print_level"] = False

    return df
