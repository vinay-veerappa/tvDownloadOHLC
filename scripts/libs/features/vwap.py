"""
Session VWAP and derived features.

All functions take a DataFrame and config, add columns, return the DataFrame.
VWAP resets at each RTH session open (09:30 ET) using the ``trading_date`` column.

Requires upstream columns:
    trading_date  — from session_tagger.tag_sessions()
    atr_14        — from atr.compute_atr()
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_vwap(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Compute session VWAP and derived features grouped by ``trading_date``.

    Formula:
        typical_price = (high + low + close) / 3
        vwap = cumsum(typical_price * volume) / cumsum(volume)

    Adds columns:
        vwap               — session VWAP (points)
        vwap_distance      — close - vwap (points; positive = above VWAP)
        vwap_distance_atr  — vwap_distance / atr_14 (ATR-normalised; ADR-002)
        vwap_slope         — linear regression slope over last 12 bars of VWAP
        vwap_cross_count   — rolling count of close crossing VWAP in last N bars
        above_vwap         — bool (close > vwap)
        vwap_std_1         — vwap + 1 × session rolling std band
        vwap_std_neg1      — vwap - 1 × session rolling std band

    Performance notes (ADR-008):
        - groupby + cumsum is fully vectorised (no Python loops).
        - Rolling ops use min_periods=1 for partial windows at session open.
        - vwap_cross_count uses a sign-change trick to avoid a per-bar loop.
    """
    required = {"trading_date", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"compute_vwap: missing required columns {missing}")

    # ── Typical price ────────────────────────────────────────────────────
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    tpv = tp * df["volume"]

    # ── Per-session cumulative sums (RTH-only accumulation) ──────────────
    # Keep VWAP anchored to 09:30 session open for each trading_date.
    is_rth = df["is_rth"] if "is_rth" in df.columns else pd.Series(True, index=df.index)
    tpv_rth = tpv.where(is_rth, 0.0)
    vol_rth = df["volume"].where(is_rth, 0.0)

    grp = df["trading_date"]
    cum_tpv = tpv_rth.groupby(grp).cumsum()
    cum_vol = vol_rth.groupby(grp).cumsum()

    # Guard against zero volume bars and keep non-RTH VWAP as NaN.
    df["vwap"] = np.where(cum_vol > 0, cum_tpv / cum_vol, np.nan)
    df.loc[~is_rth, "vwap"] = np.nan

    # ── VWAP distance ────────────────────────────────────────────────────
    df["vwap_distance"] = df["close"] - df["vwap"]

    if "atr_14" in df.columns:
        df["vwap_distance_atr"] = df["vwap_distance"] / df["atr_14"].replace(0, np.nan)
    else:
        logger.debug("atr_14 not found — skipping vwap_distance_atr")

    # ── Above / below flag ───────────────────────────────────────────────
    df["above_vwap"] = df["close"] > df["vwap"]

    # ── VWAP slope: vectorised rolling OLS over last `win` bars ──────────
    # Closed-form OLS: slope = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)
    # where x = [0,1,...,win-1] is constant — so Σx, Σx² can be precomputed.
    win = 12
    vwap_s = df["vwap"].ffill()

    # Rolling sums of y and x*y over a fixed window
    sum_y  = vwap_s.rolling(win, min_periods=2).sum()
    # x = [0,1,...,win-1] for a full window; bar index within window = rolling cumcount
    # Pre-compute the fixed terms (only depend on n and win)
    n_arr  = vwap_s.rolling(win, min_periods=2).count()           # actual n in window
    # Σx = n*(n-1)/2,  Σx² = n*(n-1)*(2n-1)/6  (for x=[0..n-1])
    sum_x  = n_arr * (n_arr - 1) / 2.0
    sum_x2 = n_arr * (n_arr - 1) * (2 * n_arr - 1) / 6.0
    # Σxy: weight each y_i by its position i within the rolling window
    # trick: Σ(i·y_i) = Σy_i * (n-1) - Σ_{j=0}^{n-1} y_{n-1-j} * j / — easier via:
    # Σxy = cumsum approach: compute rolling weighted sum using a convolution-style expansion
    # Simpler: use rolling apply only on window positions (but keep it numpy-vectorised)
    # Use the identity: Σ(i·y_i) = Σ(y_k * (k - win_start)) for k in window
    # which equals: rolling sum of (k * y_k) minus win_start * rolling sum of y_k
    # where k is the absolute position in the series
    k      = np.arange(len(vwap_s), dtype=float)
    ky     = k * vwap_s.fillna(0.0)
    sum_ky = ky.rolling(win, min_periods=2).sum()
    sum_k  = k.copy().view()  # scalar window positions
    # cumsum of k within window = rolling sum of k
    roll_sum_k = pd.Series(k, index=df.index).rolling(win, min_periods=2).sum()

    numer = n_arr * sum_ky - roll_sum_k * sum_y
    denom_slope = n_arr * sum_x2 - sum_x ** 2
    df["vwap_slope"] = np.where(denom_slope > 0, numer / denom_slope, np.nan)

    # ── VWAP cross count ─────────────────────────────────────────────────
    cross_window_bars = 60  # default: 60 × 1m = 1 hour (≈ 12 × 5m bars)
    if config is not None:
        try:
            cross_window_bars = config.chop.vwap_cross.get(
                "window_bars_5m", 12
            ) * 5
        except AttributeError:
            pass  # config.chop not present — use default

    # Sign of (close - vwap): +1 above, -1 below, 0 exactly on
    side = np.sign(df["close"] - df["vwap"])
    # A cross happens when sign changes between consecutive bars
    crossed = (side != side.shift(1)).astype(int)
    df["vwap_cross_count"] = crossed.rolling(cross_window_bars, min_periods=1).sum()

    # ── VWAP std bands — vectorised expanding std ─────────────────────────
    # Expanding std via the sum-of-squares formula (no groupby+apply):
    #   std² = (Σy² - (Σy)²/n) / (n-1)
    # All operations are groupby-transform (C-level), no Python callbacks.
    tp_s   = pd.Series(tp.values, index=df.index, name="tp")
    n_bars = tp_s.groupby(grp).cumcount() + 1.0  # expanding bar count
    sum_tp  = tp_s.groupby(grp).transform("cumsum")
    sum_tp2 = (tp_s ** 2).groupby(grp).transform("cumsum")
    # Bessel-corrected expanding variance
    var = (sum_tp2 - sum_tp ** 2 / n_bars) / (n_bars - 1).clip(lower=1)
    rolling_std = np.sqrt(var.clip(lower=0))

    df["vwap_std_1"]    = df["vwap"] + rolling_std
    df["vwap_std_neg1"] = df["vwap"] - rolling_std

    logger.debug("VWAP computed for %d bars across %d sessions",
                 len(df), df["trading_date"].nunique())
    return df


def _linreg_slope(arr: np.ndarray) -> float:
    """Compute OLS slope for a 1D array (used inside rolling.apply)."""
    n = len(arr)
    if n < 2:
        return np.nan
    x = np.arange(n, dtype=float)
    x -= x.mean()
    y = arr - arr.mean()
    denom = (x * x).sum()
    if denom == 0:
        return 0.0
    return float((x * y).sum() / denom)
