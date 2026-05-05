"""
Acceptance / Rejection classifier.

Adds:
    level_state — categorical: "accepting" | "rejecting" | "neutral"

Logic: A level is "accepting" when price stays above (for long) or below (for
short) VWAP for N consecutive bars.  "Rejecting" is the inverse.
Requires upstream: vwap, above_vwap
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_acceptance_rejection(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Simple acceptance/rejection based on VWAP persistence.
    - "accepting": 3+ consecutive bars where close > vwap
    - "rejecting": 3+ consecutive bars where close < vwap
    - "neutral":   otherwise
    """
    if "above_vwap" not in df.columns:
        df["level_state"] = "neutral"
        return df

    persistence = 3

    above = df["above_vwap"].astype(int)
    below = (~df["above_vwap"]).astype(int)

    consecutive_above = above.rolling(persistence, min_periods=persistence).sum()
    consecutive_below = below.rolling(persistence, min_periods=persistence).sum()

    conditions = [
        consecutive_above == persistence,
        consecutive_below == persistence,
    ]
    choices = ["accepting", "rejecting"]
    df["level_state"] = np.select(conditions, choices, default="neutral")
    df["level_state"] = pd.Categorical(
        df["level_state"],
        categories=["rejecting", "neutral", "accepting"],
        ordered=True,
    )

    return df
