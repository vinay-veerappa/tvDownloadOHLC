"""
Initial Balance (IB) computation.

The IB is the high-low range of the first 60 minutes of RTH (09:30–10:30 ET).

Requires upstream columns:
    trading_date  — from session_tagger.tag_sessions()
    is_rth        — from session_tagger.tag_sessions()
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_initial_balance(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    For each trading_date, compute IB metrics and broadcast to all bars on
    that date (NaN before ib_end is formed).

    Adds columns:
        ib_high          — highest high in [09:30, 10:30)
        ib_low           — lowest low in [09:30, 10:30)
        ib_mid           — (ib_high + ib_low) / 2
        ib_width         — ib_high - ib_low (points)
        ib_width_pctile_20d — percentile rank vs prior 20 sessions (CAUSAL)
        ib_width_pctile_50d — percentile rank vs prior 50 sessions (CAUSAL)
        ib_bias          — "bullish" if close at ib_end > ib_mid, else "bearish"
        ib_ext_up_50     — ib_high + 0.5 × ib_width
        ib_ext_up_100    — ib_high + 1.0 × ib_width
        ib_ext_dn_50     — ib_low  - 0.5 × ib_width
        ib_ext_dn_100    — ib_low  - 1.0 × ib_width
        ib_formed        — bool, True for bars after ib_end on the same date
        price_vs_ib      — "above_ib" | "inside_ib" | "below_ib"

    Performance notes (ADR-008):
        All per-session metrics are computed once via a vectorised groupby
        aggregation and then merged back to the 1m timeline with a left join —
        no bar-by-bar Python loops.

    Args:
        df:     1-minute DataFrame with trading_date, is_rth, high, low, close.
        config: AppConfig (used for sessions.ib_end; defaults to "10:30").
    """
    import datetime as dt

    ib_end_str = "10:30"
    if config is not None:
        try:
            ib_end_str = config.sessions.ib_end
        except AttributeError:
            pass
    h, m = map(int, ib_end_str.split(":"))
    t_ib_end = dt.time(h, m)

    # ── 1. Identify IB bars (RTH, time < 10:30) ─────────────────────────
    bar_times = df.index.time
    is_ib_bar = df["is_rth"] & (bar_times < t_ib_end)

    # ── 2. Compute per-session IB stats via groupby ──────────────────────
    ib_bars = df.loc[is_ib_bar, ["trading_date", "high", "low", "close"]]

    ib_agg = ib_bars.groupby("trading_date").agg(
        ib_high=("high", "max"),
        ib_low=("low", "min"),
        ib_close=("close", "last"),  # close at the last IB bar → bias
    )
    ib_agg["ib_mid"]    = (ib_agg["ib_high"] + ib_agg["ib_low"]) / 2.0
    ib_agg["ib_width"]  = ib_agg["ib_high"] - ib_agg["ib_low"]
    ib_agg["ib_bias"]   = np.where(
        ib_agg["ib_close"] >= ib_agg["ib_mid"], "bullish", "bearish"
    )
    ib_agg["ib_ext_up_50"]  = ib_agg["ib_high"] + 0.5 * ib_agg["ib_width"]
    ib_agg["ib_ext_up_100"] = ib_agg["ib_high"] + 1.0 * ib_agg["ib_width"]
    ib_agg["ib_ext_dn_50"]  = ib_agg["ib_low"]  - 0.5 * ib_agg["ib_width"]
    ib_agg["ib_ext_dn_100"] = ib_agg["ib_low"]  - 1.0 * ib_agg["ib_width"]

    # ── 3. Causal percentile ranks (vectorised) ────────────────────────
    # pandas expanding().rank(pct=True) is O(n·log n) via C mergesort.
    # No Python loops — strictly causal by construction (each row ranked
    # against all prior rows only).
    sorted_dates   = ib_agg.index.sort_values()
    widths_sorted  = ib_agg.loc[sorted_dates, "ib_width"]

    # Shift(1) so the current day is NOT in its own percentile window
    pctile_base = widths_sorted.shift(1)

    def _causal_pctile(s: pd.Series, window: int) -> pd.Series:
        """Rolling percentile of s vs the prior `window` values (causal)."""
        # Use rolling with min_periods=1; each value is already shifted
        return (
            s.rolling(window, min_periods=1)
             .rank(pct=True, method="average")
             * 100
        )

    ib_agg["ib_width_pctile_20d"] = _causal_pctile(pctile_base, 20)
    ib_agg["ib_width_pctile_50d"] = _causal_pctile(pctile_base, 50)

    # ── 4. Merge IB stats back onto 1m DataFrame ─────────────────────────
    # Left join on trading_date — each bar inherits its session's IB values
    cols_to_merge = [
        "ib_high", "ib_low", "ib_mid", "ib_width",
        "ib_width_pctile_20d", "ib_width_pctile_50d",
        "ib_bias",
        "ib_ext_up_50", "ib_ext_up_100",
        "ib_ext_dn_50", "ib_ext_dn_100",
    ]
    # Temporarily reset index for merge, then restore
    df = df.join(ib_agg[cols_to_merge], on="trading_date", how="left")

    # ── 5. ib_formed: True only for bars AFTER ib_end on that date ───────
    df["ib_formed"] = df["is_rth"] & (bar_times >= t_ib_end)

    # Null out IB values for bars before IB has formed (NaN pre-IB)
    pre_ib_mask = ~df["ib_formed"]
    for col in cols_to_merge:
        if col in df.columns:
            df.loc[pre_ib_mask, col] = np.nan

    # ── 6. price_vs_ib ───────────────────────────────────────────────────
    conditions = [
        df["close"] > df["ib_high"],
        df["close"] < df["ib_low"],
    ]
    choices = ["above_ib", "below_ib"]
    df["price_vs_ib"] = np.select(conditions, choices, default="inside_ib")
    # Set to NaN where IB not yet formed
    df.loc[pre_ib_mask, "price_vs_ib"] = np.nan

    logger.debug(
        "IB computed for %d sessions, ib_end=%s",
        len(ib_agg), ib_end_str,
    )
    return df
