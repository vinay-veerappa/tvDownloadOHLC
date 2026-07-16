"""
Unit tests for institutional grading logic.
"""
import pytest
import pandas as pd
import numpy as np

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

from scripts.trading_framework.reporting.tearsheet import (
    compute_institutional_metrics,
    _grade_ev, _grade_pf, _grade_sqn, _grade_drr
)

# Mock trade objects for testing
class MockTrade:
    def __init__(self, realized_pnl):
        self.realized_pnl = realized_pnl

def test_grading_logic_tier_a():
    """
    Test that high-performing metrics result in Grade A.
    """
    assert _grade_ev(150.0) == 'A'
    assert _grade_pf(2.5) == 'A'
    assert _grade_sqn(3.5) == 'A'
    assert _grade_drr(2.0) == 'A'

def test_grading_logic_tier_f():
    """
    Test that poor-performing metrics result in Grade F.
    """
    assert _grade_ev(-1.0) == 'F'
    assert _grade_pf(0.5) == 'F'
    assert _grade_sqn(0.5) == 'F'
    assert _grade_drr(12.0) == 'F'

def test_institutional_metrics_computation():
    """
    Test the full computation function with mock data.
    - 4 wins of $400, 2 losses of -$200.
    - Risk per trade = $200.
    """
    trades = [
        MockTrade(400), MockTrade(400), MockTrade(400), MockTrade(400),
        MockTrade(-200), MockTrade(-200)
    ]
    equity_curve = pd.Series([50000, 50400, 50800, 51200, 51600, 51400, 51200])
    
    metrics = compute_institutional_metrics(trades, equity_curve, account_size=50000.0, risk_per_trade=200.0)
    
    # EV = (4/6 * 400) - (2/6 * 200) = 266.67 - 66.67 = 200.0
    assert metrics['ev'] == pytest.approx(200.0)
    assert metrics['ev_grade'] == 'A'
    
    # PF = 1600 / 400 = 4.0
    assert metrics['pf'] == 4.0
    assert metrics['pf_grade'] == 'A'
    
    # Check that we have all keys
    assert "sqn" in metrics
    assert "ror" in metrics
    assert "drr" in metrics

def test_empty_trades_handling():
    """
    Ensure the system doesn't crash if no trades are found.
    """
    metrics = compute_institutional_metrics([], pd.Series([50000]), 50000.0, 200.0)
    assert metrics == {}

if __name__ == "__main__":
    # If run directly, run the tests
    import sys
    pytest.main(sys.argv)
