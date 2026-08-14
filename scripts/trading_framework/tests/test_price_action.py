"""
Unit tests for the Price Action Library.
========================================
Tests:
1. Kaufman Efficiency Ratio & TTM Volatility Squeeze.
2. Level Rejection & Absorption Engine.
3. Break and Retest 3-Phase State Machine.
4. Al Brooks Bar Classification & H2/L2 Leg Counter.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import pytest

from scripts.libs_py.price_action import (
    detect_level_rejection,
    detect_break_and_retest,
    classify_brooks_bars,
    detect_h1_h2_l1_l2,
    compute_kaufman_efficiency,
    compute_ttm_squeeze,
    compute_bar_overlap,
)


@pytest.fixture
def synthetic_ohlcv():
    dates = pd.date_range("2026-01-05 09:30:00", periods=50, freq="1min", tz="America/New_York")
    
    # Create an upward trend with a 2-legged pullback
    p = np.linspace(15000, 15100, 50)
    df = pd.DataFrame(
        {
            "open": p - 1.0,
            "high": p + 3.0,
            "low": p - 3.0,
            "close": p + 1.0,
            "volume": 500,
        },
        index=dates,
    )
    return df


def test_kaufman_efficiency():
    # Linear runaway trend: Should have KER ~ 1.0
    dates = pd.date_range("2026-01-05 09:30:00", periods=10, freq="1min")
    df_trend = pd.DataFrame({"close": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118]}, index=dates)
    res_trend = compute_kaufman_efficiency(df_trend, period=5)
    assert res_trend["ker_5"].iloc[-1] == 1.0
    assert res_trend["is_efficient_trend"].iloc[-1] == True

    # Oscillating chop: Should have KER close to 0.0
    df_chop = pd.DataFrame({"close": [100, 102, 100, 102, 100, 102, 100, 102, 100, 102]}, index=dates)
    res_chop = compute_kaufman_efficiency(df_chop, period=5)
    assert res_chop["ker_5"].iloc[-1] <= 0.25
    assert res_chop["is_choppy_noise"].iloc[-1] == True


def test_ttm_squeeze(synthetic_ohlcv):
    res = compute_ttm_squeeze(synthetic_ohlcv)
    assert "squeeze_on" in res.columns
    assert "squeeze_mom" in res.columns
    assert "squeeze_fired_bull" in res.columns
    assert "squeeze_fired_bear" in res.columns


def test_level_rejection():
    dates = pd.date_range("2026-01-05 09:30:00", periods=5, freq="1min")
    # Bar 2 tests support at 15000 with a long lower wick (low=14999, close=15005, high=15006)
    df = pd.DataFrame(
        {
            "open": [15010, 15004, 15010, 15004, 15008],
            "high": [15015, 15006, 15012, 15007, 15015],
            "low":  [15008, 14999, 15007, 14999, 15006],
            "close":[15010, 15005, 15011, 15006, 15014],
        },
        index=dates,
    )
    res = detect_level_rejection(df, level=15000.0, tolerance_pts=2.0)
    assert res["level_touch"].iloc[1] == True
    assert res["bullish_level_rejection"].iloc[1] == True
    assert res["is_support_absorption"].iloc[3] == True


def test_break_and_retest():
    dates = pd.date_range("2026-01-05 09:30:00", periods=5, freq="1min")
    # Bar 0: Below 15000
    # Bar 1: Breakout above 15000 (close=15020)
    # Bar 2: Retest pullback touching 15001 with rejection (low=15000.5, close=15015)
    df = pd.DataFrame(
        {
            "open": [14990, 14995, 15018, 15014, 15025],
            "high": [14998, 15025, 15020, 15028, 15035],
            "low":  [14985, 14994, 15000.5, 15012, 15022],
            "close":[14992, 15020, 15015, 15026, 15032],
        },
        index=dates,
    )
    res = detect_break_and_retest(df, level=15000.0, tolerance_pts=2.0)
    assert res["level_breakout_bull"].iloc[1] == True
    assert res["retest_bull_confirmed"].iloc[2] == True


def test_al_brooks_microstructure(synthetic_ohlcv):
    res_bars = classify_brooks_bars(synthetic_ohlcv)
    assert "is_trend_bar" in res_bars.columns
    assert "is_doji_bar" in res_bars.columns
    assert "is_barbwire" in res_bars.columns

    res_legs = detect_h1_h2_l1_l2(synthetic_ohlcv)
    assert "h1_signal" in res_legs.columns
    assert "h2_signal" in res_legs.columns
    assert "l1_signal" in res_legs.columns
    assert "l2_signal" in res_legs.columns
