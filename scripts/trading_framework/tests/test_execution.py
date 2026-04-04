import pytest
from scripts.libs.risk.risk_config import TradeDirection
from scripts.trading_framework.core.execution import apply_slippage, compute_commission, compute_pnl

def test_slippage_long_entry():
    """Long entry: filled HIGHER."""
    # 100.0 + (0.25 * 2 ticks) = 100.5
    price = 100.0
    fill = apply_slippage(price, TradeDirection.LONG, tick_size=0.25, slippage_ticks=2, is_entry=True)
    assert fill == 100.5

def test_slippage_long_exit():
    """Long exit: filled LOWER."""
    # 100.0 - (0.25 * 2 ticks) = 99.5
    price = 100.0
    fill = apply_slippage(price, TradeDirection.LONG, tick_size=0.25, slippage_ticks=2, is_entry=False)
    assert fill == 99.5

def test_slippage_short_entry():
    """Short entry: filled LOWER."""
    # 100.0 - (0.25 * 2 ticks) = 99.5
    price = 100.0
    fill = apply_slippage(price, TradeDirection.SHORT, tick_size=0.25, slippage_ticks=2, is_entry=True)
    assert fill == 99.5

def test_slippage_short_exit():
    """Short exit: filled HIGHER."""
    # 100.0 + (0.25 * 2 ticks) = 100.5
    price = 100.0
    fill = apply_slippage(price, TradeDirection.SHORT, tick_size=0.25, slippage_ticks=2, is_entry=False)
    assert fill == 100.5

def test_commission_scaling():
    """Test scaling by number of contracts."""
    assert compute_commission(1, 0.62) == 0.62
    assert compute_commission(5, 0.62) == 3.10

def test_pnl_math_long():
    """Test Long P&L: (exit - entry) * point_value - commission."""
    # (105 - 100) * 5.0 * 2 contracts - 1.24 = 50.0 - 1.24 = 48.76
    entry = 100.0
    exit = 105.0
    pnl = compute_pnl(entry, exit, TradeDirection.LONG, contracts=2, point_value=5.0, commission=1.24)
    assert pnl == 48.76

def test_pnl_math_short():
    """Test Short P&L: (entry - exit) * point_value - commission."""
    # (105 - 100) * 5.0 * 2 contracts - 1.24 = 50.0 - 1.24 = 48.76
    entry = 105.0
    exit = 100.0
    pnl = compute_pnl(entry, exit, TradeDirection.SHORT, contracts=2, point_value=5.0, commission=1.24)
    assert pnl == 48.76
