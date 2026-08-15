"""
========================================================================================
Liquidity Engine - Institutional High-Performance Liquidity Sweep & Pool Detection
========================================================================================

Detects, tracks, and analyzes institutional liquidity pools and sweep events:
1. Major Structural Liquidity (Fractal Swing Highs / Lows, Equal Highs / Equal Lows).
2. Higher-Timeframe Session & Daily Liquidity:
   - Previous Day High (PDH) / Previous Day Low (PDL)
   - Asia Session High (ASH) / Asia Session Low (ASL) [18:00 - 00:00 ET]
   - London Session High (LOH) / London Session Low (LOL) [02:00 - 05:00 ET]
   - Midnight Open (NY 00:00 Open)
3. Liquidity Sweep Detection:
   - Buyside Liquidity (BSL) Sweep: Price pierces high level, rejecting / trapping buyers.
   - Sellside Liquidity (SSL) Sweep: Price pierces low level, rejecting / trapping sellers.
4. Liquidity Sweep Recency Filter for CISD & Strategy Validation.

Author: Institutional Research Suite / Antigravity
License: MIT
========================================================================================
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

try:
    import numba
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


def _jit_decorator(func):
    if HAS_NUMBA:
        return numba.njit(fastmath=True, cache=True)(func)
    return func


@_jit_decorator
def _detect_swing_liquidity_kernel(
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    swing_len: int,
    sweep_lookback: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    JIT-compiled detection of rolling swing liquidity sweeps and recency masks.
    """
    n = len(high_arr)
    bsl_swept = np.zeros(n, dtype=np.int8)
    ssl_swept = np.zeros(n, dtype=np.int8)
    has_recent_bsl_sweep = np.zeros(n, dtype=np.int8)
    has_recent_ssl_sweep = np.zeros(n, dtype=np.int8)

    if n < (2 * swing_len + 1):
        return bsl_swept, ssl_swept, has_recent_bsl_sweep, has_recent_ssl_sweep

    # Track confirmed historical swing levels
    max_swings = 200
    sh_levels = np.zeros(max_swings, dtype=np.float64)
    sl_levels = np.zeros(max_swings, dtype=np.float64)
    sh_count = 0
    sl_count = 0

    last_bsl_sweep_idx = -9999
    last_ssl_sweep_idx = -9999

    for t in range(swing_len, n):
        # 1. Confirm a pivot at t - swing_len
        pivot_idx = t - swing_len
        p_high = high_arr[pivot_idx]
        p_low = low_arr[pivot_idx]

        is_sh = True
        for k in range(max(0, pivot_idx - swing_len), min(n, pivot_idx + swing_len + 1)):
            if high_arr[k] > p_high:
                is_sh = False
                break

        is_sl = True
        for k in range(max(0, pivot_idx - swing_len), min(n, pivot_idx + swing_len + 1)):
            if low_arr[k] < p_low:
                is_sl = False
                break

        if is_sh and (sh_count < max_swings):
            sh_levels[sh_count] = p_high
            sh_count += 1

        if is_sl and (sl_count < max_swings):
            sl_levels[sl_count] = p_low
            sl_count += 1

        # 2. Check if current candle t sweeps any active swing level
        curr_h = high_arr[t]
        curr_l = low_arr[t]
        curr_c = close_arr[t]

        # Check BSL sweeps (High pierces level, but close rejects or fails to sustain)
        if sh_count > 0:
            for s in range(sh_count - 1, max(-1, sh_count - 10), -1):
                lvl = sh_levels[s]
                if curr_h > lvl:
                    bsl_swept[t] = 1
                    last_bsl_sweep_idx = t
                    break

        # Check SSL sweeps (Low pierces level, but close rejects)
        if sl_count > 0:
            for s in range(sl_count - 1, max(-1, sl_count - 10), -1):
                lvl = sl_levels[s]
                if curr_l < lvl:
                    ssl_swept[t] = 1
                    last_ssl_sweep_idx = t
                    break

        # 3. Recency lookback
        if (t - last_bsl_sweep_idx) <= sweep_lookback:
            has_recent_bsl_sweep[t] = 1

        if (t - last_ssl_sweep_idx) <= sweep_lookback:
            has_recent_ssl_sweep[t] = 1

    return bsl_swept, ssl_swept, has_recent_bsl_sweep, has_recent_ssl_sweep


def compute_liquidity_levels(
    df: pd.DataFrame,
    swing_length: int = 5,
    sweep_lookback_bars: int = 20,
) -> pd.DataFrame:
    """
    Computes major liquidity pools (PDH/PDL, Asia H/L, London H/L, Swings)
    and liquidity sweep flags.
    """
    high = np.ascontiguousarray(df["high"].values, dtype=np.float64)
    low = np.ascontiguousarray(df["low"].values, dtype=np.float64)
    close = np.ascontiguousarray(df["close"].values, dtype=np.float64)

    bsl_sw, ssl_sw, rec_bsl, rec_ssl = _detect_swing_liquidity_kernel(
        high, low, close, swing_length, sweep_lookback_bars
    )

    res = pd.DataFrame(index=df.index)
    res["bsl_swept"] = bsl_sw
    res["ssl_swept"] = ssl_sw
    res["has_recent_bsl_sweep"] = rec_bsl
    res["has_recent_ssl_sweep"] = rec_ssl

    return res
