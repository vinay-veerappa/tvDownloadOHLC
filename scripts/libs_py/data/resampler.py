"""
Resample 1-minute bars to higher timeframes.

Usage:
    from scripts.libs_py.data.resampler import resample_ohlcv, add_resampled_columns
    df_5m = resample_ohlcv(df, "5min")
    df_1m = add_resampled_columns(df_1m, "5min", "5m_")
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_OHLCV_AGG = {
    "open":   "first",
    "high":   "max",
    "low":    "min",
    "close":  "last",
    "volume": "sum",
}


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Resample a 1-minute OHLCV DataFrame to a higher frequency.

    Args:
        df:   DataFrame with open/high/low/close/volume columns and a
              DatetimeIndex (tz-aware US/Eastern).
        freq: pandas offset alias — e.g. "5min", "15min", "30min", "1h".

    Returns:
        Resampled DataFrame with the same column names.
        - Only bars where at least one source bar existed are included
          (no synthetic empty periods from the resampler).
        - Resampling is session-aware: if the DataFrame contains a
          ``trading_date`` column, resampling is grouped per session to
          avoid spanning bars across overnight gaps.

    Note:
        If you need to fuse the resampled bars back onto the 1m timeline,
        use ``add_resampled_columns()`` instead.
    """
    ohlcv_cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    agg = {c: _OHLCV_AGG[c] for c in ohlcv_cols}

    # Determine if session-grouping is needed.
    # For frequencies < 1 hour, a global resample is safe: 5m/15m/30m bars
    # always fall within a single session (markets open at fixed times).
    # Session-grouping is only required for ≥ 1h to avoid overnight spanning.
    _SHORT_FREQS = {"1min", "2min", "3min", "5min", "10min", "15min", "30min",
                    "1T", "2T", "3T", "5T", "10T", "15T", "30T"}
    needs_session_group = "trading_date" in df.columns and freq not in _SHORT_FREQS

    if needs_session_group:
        # Slow path: group per session to avoid cross-session bars (1h+)
        result = (
            df[ohlcv_cols + ["trading_date"]]
            .groupby("trading_date", group_keys=False)
            .apply(lambda s: s[ohlcv_cols].resample(freq).agg(agg).dropna(how="all"))
        )
        if isinstance(result.index, pd.MultiIndex):
            result = result.droplevel(0)
    else:
        # Fast path: single vectorised global resample (C-level, no Python loops)
        result = df[ohlcv_cols].resample(freq).agg(agg).dropna(how="all")

    result = result.sort_index()
    logger.debug("Resampled %d 1m bars → %d %s bars", len(df), len(result), freq)
    return result


def add_resampled_columns(
    df_1m: pd.DataFrame,
    freq: str,
    prefix: str,
) -> pd.DataFrame:
    """
    Resample to ``freq`` and merge the resample values back onto the 1-minute
    DataFrame as additional columns prefixed with ``prefix``.

    Example:
        add_resampled_columns(df, "5min", "5m_")
        → adds: 5m_open, 5m_high, 5m_low, 5m_close, 5m_volume

    Each 1-minute bar receives the values of the higher-timeframe bar it
    belongs to, via a forward-fill merge on the 5m period boundaries.

    The merge is left-join so the 1m bar count is unchanged.
    """
    df_higher = resample_ohlcv(df_1m, freq)
    if df_higher.empty:
        logger.warning("add_resampled_columns: resampled DataFrame is empty, no columns added")
        return df_1m

    # Rename columns with prefix before merging
    df_higher = df_higher.rename(columns={c: f"{prefix}{c}" for c in df_higher.columns})

    # merge_asof requires sorted indexes — both should already be sorted
    # Use merge_asof: for each 1m bar, take the most recent HTF bar (left/forward)
    df_out = pd.merge_asof(
        df_1m,
        df_higher,
        left_index=True,
        right_index=True,
        direction="backward",
    )

    logger.debug(
        "Added %d %s columns via %s merge (prefix='%s')",
        len(df_higher.columns), freq, "backward merge_asof", prefix,
    )
    return df_out