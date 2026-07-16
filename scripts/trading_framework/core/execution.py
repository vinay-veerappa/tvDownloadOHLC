"""
Execution model: slippage and commission.
"""

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

from scripts.libs_py.risk.risk_config import TradeDirection

def apply_slippage(price: float, direction: TradeDirection,
                   tick_size: float, slippage_ticks: int, is_entry: bool = True) -> float:
    """
    Apply slippage to a fill price.
    For entries: longs get filled higher, shorts get filled lower.
    For exits: longs get filled lower, shorts get filled higher.
    """
    slippage_points = tick_size * slippage_ticks
    
    if direction == TradeDirection.LONG:
        if is_entry:
            return price + slippage_points
        else:
            return price - slippage_points
    else:  # SHORT
        if is_entry:
            return price - slippage_points
        else:
            return price + slippage_points

def compute_commission(contracts: int, per_contract: float) -> float:
    """Round-trip commission."""
    return contracts * per_contract

def compute_pnl(entry_price: float, exit_price: float,
                direction: TradeDirection, contracts: int,
                point_value: float, commission: float) -> float:
    """
    Compute realized P&L in dollars.
    For longs: (exit - entry) * contracts * point_value - commission
    For shorts: (entry - exit) * contracts * point_value - commission
    """
    if direction == TradeDirection.LONG:
        gross = (exit_price - entry_price) * contracts * point_value
    else:
        gross = (entry_price - exit_price) * contracts * point_value
        
    return gross - commission
