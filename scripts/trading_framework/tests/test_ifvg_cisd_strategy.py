"""
Unit tests for the 5m MTF IFVG CISD Strategy.
=============================================
Tests:
1. Strategy initialization and registry discovery.
2. Signal generation schema and bounds.
3. Param grid validity.
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

from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy
from scripts.trading_framework.strategies.registry import get_strategy


@pytest.fixture
def sample_ohlcv():
    dates = pd.date_range("2026-01-05 09:30:00", periods=100, freq="1min", tz="America/New_York")
    
    # Create alternating up/down waves to form 5m FVGs and CISD swings
    p = 15000.0 + np.sin(np.linspace(0, 10, 100)) * 50.0
    df = pd.DataFrame(
        {
            "open": p - 2.0,
            "high": p + 5.0,
            "low": p - 5.0,
            "close": p + 2.0,
            "volume": 1000,
        },
        index=dates,
    )
    return df


def test_ifvg_cisd_registry_discovery():
    strat = get_strategy("ifvg_cisd", "NQ1")
    assert strat is not None
    assert strat.strategy_name == "5m IFVG CISD Distribution"


def test_ifvg_cisd_signal_generation(sample_ohlcv):
    strat = IFVGCISDStrategy(ticker="NQ1")
    sigs = strat.hunt(sample_ohlcv, params={"resample_tf": "5min", "filter_lunch": False})
    
    # Verify expected column schema
    for col in IFVGCISDStrategy.OUTPUT_COLUMNS:
        assert col in sigs.columns

    if not sigs.empty:
        # Check risk and targets logic
        for _, row in sigs.iterrows():
            assert row["risk_pts"] > 0
            if row["direction"] == "long":
                assert row["target1_price"] > row["entry_price"]
                assert row["stop_price"] < row["entry_price"]
            else:
                assert row["target1_price"] < row["entry_price"]
                assert row["stop_price"] > row["entry_price"]


def test_ifvg_cisd_param_grid():
    strat = IFVGCISDStrategy(ticker="NQ1")
    grid = strat.get_param_grid()
    assert "resample_tf" in grid
    assert "max_trades_per_day" in grid
    assert "r_mult_tp1" in grid
    assert "r_mult_tp2" in grid
