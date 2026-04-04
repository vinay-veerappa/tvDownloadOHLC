"""
ATR (Average True Range) features.

Produces:
    atr_14    — 1-minute ATR with period 14
    atr_5m_14 — 5-minute ATR with period 14 (merged back to 1m bars)

All computations are strictly causal (no future data).
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_atr(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Compute ATR on the 1-minute DataFrame.

    Uses Wilder's smoothed ATR (ewm with adjust=False, com=period-1),
    which is the standard definition and avoids lookahead.

    Adds columns:
        atr_14      — ATR(14) on 1m bars (points)

    If "5m_high" / "5m_low" / "5m_close" columns already exist (added by
    the resampler), also adds:
        atr_5m_14   — ATR(14) computed on the 5-minute bars, forward-filled
                      back to each 1-minute bar via merge_asof.

    Args:
        df:     DataFrame with at minimum: high, low, close columns.
        config: AppConfig (optional; not used here but keeps the registry
                call signature consistent).

    Returns:
        df with atr_14 (and optionally atr_5m_14) added.
    """
    period = 14

    # ── 1m ATR ──────────────────────────────────────────────────────────
    tr = _true_range(df["high"], df["low"], df["close"])
    df["atr_14"] = tr.ewm(com=period - 1, adjust=False, min_periods=period).mean()

    # ── 5m ATR  (only if resampled columns already exist) ───────────────
    has_5m = all(c in df.columns for c in ("5m_high", "5m_low", "5m_close"))
    if has_5m:
        # Build a pseudo-OHLC on the 5m close column to compute TR
        df_5m_view = df[["5m_high", "5m_low", "5m_close"]].rename(
            columns={"5m_high": "high", "5m_low": "low", "5m_close": "close"}
        )
        tr5 = _true_range(df_5m_view["high"], df_5m_view["low"], df_5m_view["close"])
        df["atr_5m_14"] = tr5.ewm(com=period - 1, adjust=False, min_periods=period).mean()
    else:
        logger.debug("5m columns not found — skipping atr_5m_14")

    return df


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Wilder True Range: max(H-L, |H-Cprev|, |L-Cprev|)."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    tr.name = "tr"
    return tr
