"""
Market internals features derived from TICK, UVOL, DVOL, TRIN data.

All computations are strictly causal (rolling with no lookahead).
Columns are optional — if an internals symbol was not loaded (file missing),
its derived features simply won't be computed.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_internals_features(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Compute market-internals-derived features.

    Input columns (all optional — function degrades gracefully if absent):
        TICK, TICKQ, UVOL, DVOL, TRIN, TRINQ, ADV

    Added columns:
        vold               — UVOL - DVOL (if both present)
        tick_abs           — abs(TICK)
        tick_persistence   — rolling mean of tick_abs (window from config)
        tick_zero_cross    — rolling count of TICK sign changes
        vold_slope         — per-session linear regression slope of VOLD
        trin_avg           — rolling mean of TRIN
        trin_in_chop_band  — bool: trin_avg between chop_band[0] and chop_band[1]

    Performance (ADR-008):
        All rolling ops are pandas native (C-level). The per-session vold_slope
        is computed via a vectorised groupby+apply using numpy lstsq.
    """
    # ── Config defaults ───────────────────────────────────────────────────
    tick_window      = 30  # minutes
    trin_window      = 30
    chop_band        = (0.9, 1.1)

    if config is not None:
        try:
            tick_window = config.chop.tick_persistence["window_minutes"]
        except (AttributeError, KeyError, TypeError):
            pass
        try:
            trin_window = config.chop.trin_regime["window_minutes"]
        except (AttributeError, KeyError, TypeError):
            pass
        try:
            chop_band = tuple(config.chop.trin_regime["chop_band"])
        except (AttributeError, KeyError, TypeError):
            pass

    # ── VOLD ─────────────────────────────────────────────────────────────
    if "UVOL" in df.columns and "DVOL" in df.columns and "VOLD" not in df.columns:
        df["VOLD"] = df["UVOL"] - df["DVOL"]

    # ── TICK-derived ──────────────────────────────────────────────────────
    if "TICK" in df.columns:
        df["tick_abs"] = df["TICK"].abs()
        df["tick_persistence"] = (
            df["tick_abs"]
            .rolling(window=tick_window, min_periods=1)
            .mean()
        )
        # Sign change = current sign != previous sign, ignoring zeros
        tick_sign = np.sign(df["TICK"])
        prev_sign = tick_sign.shift(1)
        sign_change = ((tick_sign != prev_sign) & (tick_sign != 0) & (prev_sign != 0)).astype(int)
        df["tick_zero_cross"] = sign_change.rolling(tick_window, min_periods=1).sum()
    else:
        logger.debug("TICK column absent — skipping tick_persistence, tick_zero_cross")

    # ── VOLD slope ────────────────────────────────────────────────────────
    if "VOLD" in df.columns and "trading_date" in df.columns:
        df["vold_slope"] = _per_session_slope(df, "VOLD", "trading_date")
    else:
        logger.debug("VOLD or trading_date absent — skipping vold_slope")

    # ── TRIN ─────────────────────────────────────────────────────────────
    if "TRIN" in df.columns:
        df["trin_avg"] = (
            df["TRIN"]
            .rolling(window=trin_window, min_periods=1)
            .mean()
        )
        df["trin_in_chop_band"] = (
            (df["trin_avg"] >= chop_band[0]) & (df["trin_avg"] <= chop_band[1])
        )
    else:
        logger.debug("TRIN column absent — skipping trin features")

    return df


def _per_session_slope(
    df: pd.DataFrame,
    col: str,
    date_col: str,
) -> pd.Series:
    """
    Vectorised expanding OLS slope of ``col`` within each session.

    Uses the closed-form OLS formula with groupby cumsum — O(n) total,
    no Python loops per bar.

    For n observations with x = [0, 1, ..., n-1] and y = col values:
        slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)

    The key insight: Σx = n*(n-1)/2 and Σx² = n*(n-1)*(2n-1)/6
    are closed-form, so only Σxy needs a running cumsum.
    """
    grp = df.groupby(date_col, sort=False)

    # Bar index within each session (0-based)
    x = grp.cumcount().astype(float)                # i = 0,1,2,...
    n = x + 1.0                                      # n bars seen so far

    y = df[col].fillna(0.0)

    # Running sums (all vectorised)
    xy      = x * y
    sum_x   = grp["trading_date"].transform(lambda s: (pd.Series(range(len(s))) * 1.0).cumsum())
    # Simpler: sum_x = n*(n-1)/2  (closed form)
    sum_x   = n * (n - 1.0) / 2.0
    sum_x2  = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0
    sum_y   = grp[col].transform(lambda s: s.fillna(0.0).cumsum())
    sum_xy  = grp["trading_date"].transform(
        lambda s: (x.loc[s.index] * y.loc[s.index]).cumsum()
    )

    denom = n * sum_x2 - sum_x ** 2
    slope = np.where(denom > 0, (n * sum_xy - sum_x * sum_y) / denom, np.nan)

    return pd.Series(slope, index=df.index, name=f"{col}_slope")
