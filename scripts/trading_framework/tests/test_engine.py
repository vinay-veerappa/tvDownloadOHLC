import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.risk.risk_config import Signal, TradeDirection, TradeStatus
from scripts.trading_framework.core.engine import BacktestEngine
from scripts.trading_framework.config.config_loader import AppConfig

@pytest.fixture
def mock_config():
    """Mock configuration for testing engine logic."""
    config = type('obj', (object,), {})
    config.trade_risk_policy = "fixed_target"
    config.trade_risk_policies = {"fixed_target": {"tp_atr": 2.0, "sl_atr": 1.0}}
    # Ensure missing rth_start attribute is provided to avoid engine collection errors
    config.sessions = type('obj', (object,), {"flatten_by": "16:00", "rth_start": "09:30"})
    config.execution = type('obj', (object,), {
        "tick_size": {"MES": 0.25},
        "point_value": {"MES": 5.0},
        "slippage_ticks": 1,
        "commission_per_contract": 0.62,
        "default_contracts": 1
    })
    return config

@pytest.fixture
def mock_data():
    """Mock 1-minute pricing data for backtest simulation."""
    dates = pd.date_range("2026-04-04 09:30", periods=10, freq='min')
    df = pd.DataFrame({
        "open": [100.0] * 10,
        "high": [101.0, 102.0, 100.5, 103.0, 101.0, 100.0, 99.0, 98.0, 97.0, 96.0],
        "low": [99.0, 100.0, 99.5, 101.0, 100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        "close": [100.5] * 10,
        "volume": [1000] * 10
    }, index=dates)
    return df

def test_engine_long_entry_exit(mock_config, mock_data):
    """Test a basic long trade through the backtest engine."""
    engine = BacktestEngine(mock_config)
    
    # Entry at 09:30 @ 100.5. Verify fill calculation includes slippage.
    sig = Signal(
        timestamp=mock_data.index[0], strategy_name="test",
        symbol="MES", direction=TradeDirection.LONG, 
        entry_price=100.5, stop_price=95.0,
        risk_points=5.5, risk_dollars=27.5, context={}
    )
    
    result = engine.run([sig], mock_data)
    assert len(result.trades) == 1
    trade = result.trades[0]
    
    # Fill price calculation: 100.5 + (0.25 * 1 tick slippage) = 100.75
    assert trade.entry_fill_price == 100.75
    assert trade.status == TradeStatus.CLOSED

def test_engine_short_entry_exit(mock_config, mock_data):
    """Test a basic short trade through the backtest engine."""
    engine = BacktestEngine(mock_config)
    
    # Entry at 09:35 @ 100.0. Verify fill calculation includes slippage.
    sig = Signal(
        timestamp=mock_data.index[5], strategy_name="test",
        symbol="MES", direction=TradeDirection.SHORT, 
        entry_price=100.0, stop_price=105.0,
        risk_points=5.0, risk_dollars=25.0, context={}
    )
    
    result = engine.run([sig], mock_data)
    assert len(result.trades) == 1
    trade = result.trades[0]
    
    # Fill price calculation: 100.0 - (0.25 * 1 tick slippage) = 99.75
    assert trade.entry_fill_price == 99.75
    # Verify the signal's direction property to confirm short trade handling
    assert trade.signal.direction == TradeDirection.SHORT

def test_engine_no_bars_after_signal(mock_config, mock_data):
    """Ensure engine handles cases where the signal is on the final available bar."""
    engine = BacktestEngine(mock_config)
    
    sig = Signal(
        timestamp=mock_data.index[-1], strategy_name="test",
        symbol="MES", direction=TradeDirection.LONG, 
        entry_price=100.0, stop_price=95.0,
        risk_points=5.0, risk_dollars=25.0, context={}
    )
    
    result = engine.run([sig], mock_data)
    assert len(result.trades) == 1
    # Trade should be closed immediately if no further bars exist for execution
    assert result.trades[0].status == TradeStatus.CLOSED
