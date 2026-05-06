"""
PLUGGABLE trade management policies.

Each policy is a class implementing the TradePolicy interface.
The backtest engine calls policy.manage() on each bar while a trade is open.
The policy decides: do nothing, take partial, move stop, exit fully.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from scripts.libs_py.risk.risk_config import TradeRecord, TradeDirection


class PolicyAction(Enum):
    HOLD = "hold"                      # Do nothing
    TAKE_PARTIAL = "take_partial"      # Exit partial_pct at current price
    MOVE_STOP = "move_stop"            # Move stop to new_stop_price
    EXIT_FULL = "exit_full"            # Exit entire remaining position
    TAKE_PARTIAL_AND_MOVE_STOP = "take_partial_and_move_stop"


@dataclass
class PolicyDecision:
    action: PolicyAction
    partial_pct: Optional[float] = None       # For TAKE_PARTIAL
    new_stop_price: Optional[float] = None    # For MOVE_STOP
    exit_reason: Optional[str] = None         # For EXIT_FULL


class TradePolicy(ABC):
    """Abstract base class for trade management policies."""

    @abstractmethod
    def manage(self, trade: "TradeRecord", current_bar: dict,
               bars_since_entry: int) -> PolicyDecision:
        """
        Called on every bar while the trade is open.

        Args:
            trade: current TradeRecord
            current_bar: dict with keys: open, high, low, close, volume, datetime,
                         atr_14 (and any other features on the bar)
            bars_since_entry: int

        Returns: PolicyDecision indicating what to do.
        """
        ...

    @abstractmethod
    def reset(self):
        """Reset internal state for a new trade."""
        ...


class CoverTheQueen(TradePolicy):
    """
    Phase 1: When trade reaches partial_target_rr * risk, take partial_exit_pct off.
             Move stop to breakeven.
    Phase 2: Trail remainder using trail_method.
    """
    
    def __init__(self, params: dict):
        self.partial_exit_pct = params.get("partial_exit_pct", 0.5)
        self.partial_target_rr = params.get("partial_target_rr", 1.0)
        self.remainder_trail_method = params.get("remainder_trail_method", "atr")
        self.trail_atr_multiplier = params.get("trail_atr_multiplier", 2.0)
        self.move_stop_to_breakeven = params.get("move_stop_to_breakeven", True)
        self._partial_taken = False
        self._trailing_stop = None

    def manage(self, trade: "TradeRecord", current_bar: dict, bars_since_entry: int) -> PolicyDecision:
        close_price = current_bar["close"]
        low_price = current_bar["low"]
        high_price = current_bar["high"]
        
        entry = trade.signal.entry_price
        risk = trade.signal.risk_points
        if risk == 0:
            risk = 0.0001 # avoid div/0
            
        is_long = trade.signal.direction == TradeDirection.LONG
        
        # Check original stop first
        orig_stop = trade.signal.stop_price
        if is_long and low_price <= orig_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop")
        elif not is_long and high_price >= orig_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop")

        # 1. Compute current R-multiple
        r_multiple = (close_price - entry) / risk if is_long else (entry - close_price) / risk
        
        # 2. Check partials
        if not self._partial_taken and r_multiple >= self.partial_target_rr:
            self._partial_taken = True
            if self.move_stop_to_breakeven:
                self._trailing_stop = entry
                return PolicyDecision(
                    action=PolicyAction.TAKE_PARTIAL_AND_MOVE_STOP,
                    partial_pct=self.partial_exit_pct,
                    new_stop_price=entry
                )
            return PolicyDecision(
                action=PolicyAction.TAKE_PARTIAL, 
                partial_pct=self.partial_exit_pct
            )

        # 3. Post-partial trailing logic
        if self._partial_taken:
            new_trail = self._trailing_stop or orig_stop
            
            if self.remainder_trail_method == "atr":
                atr = current_bar.get("atr_14", 0)
                if is_long:
                    potential_trail = close_price - (self.trail_atr_multiplier * atr)
                    new_trail = max(new_trail, potential_trail) if new_trail else potential_trail
                else:
                    potential_trail = close_price + (self.trail_atr_multiplier * atr)
                    new_trail = min(new_trail, potential_trail) if new_trail else potential_trail
            
            if new_trail != self._trailing_stop:
                self._trailing_stop = new_trail
                return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=new_trail)
                
            # Check trailing stop hit
            if self._trailing_stop:
                if is_long and low_price <= self._trailing_stop:
                    return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="trail")
                elif not is_long and high_price >= self._trailing_stop:
                    return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="trail")
        
        return PolicyDecision(action=PolicyAction.HOLD)
        
    def reset(self):
        self._partial_taken = False
        self._trailing_stop = None


class FixedTarget(TradePolicy):
    def __init__(self, params: dict):
        self.target_rr = params.get("target_rr", 2.0)
        
    def manage(self, trade: "TradeRecord", current_bar: dict, bars_since_entry: int) -> PolicyDecision:
        close_price = current_bar["close"]
        low_price = current_bar["low"]
        high_price = current_bar["high"]
        entry = trade.signal.entry_price
        risk = max(trade.signal.risk_points, 0.0001)
        is_long = trade.signal.direction == TradeDirection.LONG
        
        orig_stop = trade.signal.stop_price
        if is_long and low_price <= orig_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop")
        elif not is_long and high_price >= orig_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop")
            
        r_multiple = (high_price - entry) / risk if is_long else (entry - low_price) / risk
        if r_multiple >= self.target_rr:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="target")
            
        return PolicyDecision(action=PolicyAction.HOLD)
        
    def reset(self):
        pass


class BreakevenTrail(TradePolicy):
    def __init__(self, params: dict):
        self.breakeven_trigger_rr = params.get("breakeven_trigger_rr", 1.0)
        self.trail_atr_multiplier = params.get("trail_atr_multiplier", 1.5)
        self._be_hit = False
        self._trail = None

    def manage(self, trade: "TradeRecord", current_bar: dict, bars_since_entry: int) -> PolicyDecision:
        close_price = current_bar["close"]
        low_price = current_bar["low"]
        high_price = current_bar["high"]
        entry = trade.signal.entry_price
        risk = max(trade.signal.risk_points, 0.0001)
        is_long = trade.signal.direction == TradeDirection.LONG
        
        orig_stop = trade.signal.stop_price
        current_stop = self._trail or orig_stop
        
        if is_long and low_price <= current_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop" if not self._be_hit else "trail")
        elif not is_long and high_price >= current_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop" if not self._be_hit else "trail")

        r_multiple = (close_price - entry) / risk if is_long else (entry - close_price) / risk
        
        if not self._be_hit and r_multiple >= self.breakeven_trigger_rr:
            self._be_hit = True
            self._trail = entry
            return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=self._trail)

        if self._be_hit:
            atr = current_bar.get("atr_14", 0)
            if is_long:
                potential = close_price - (self.trail_atr_multiplier * atr)
                if potential > self._trail:
                    self._trail = potential
                    return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=self._trail)
            else:
                potential = close_price + (self.trail_atr_multiplier * atr)
                if potential < self._trail:
                    self._trail = potential
                    return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=self._trail)
                    
        return PolicyDecision(action=PolicyAction.HOLD)
        
    def reset(self):
        self._be_hit = False
        self._trail = None


class TimeStop(TradePolicy):
    def __init__(self, params: dict, base_policy: TradePolicy):
        self.max_bars = params.get("max_bars", 30)
        self.applies_to = params.get("applies_to", "remainder")
        self.base_policy = base_policy

    def manage(self, trade: "TradeRecord", current_bar: dict, bars_since_entry: int) -> PolicyDecision:
        if bars_since_entry >= self.max_bars:
            if self.applies_to == "full" or (self.applies_to == "remainder" and trade.partial_exit_time is not None):
                return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="time_stop")

        return self.base_policy.manage(trade, current_bar, bars_since_entry)

    def reset(self):
        self.base_policy.reset()


class ScaledExit(TradePolicy):
    def __init__(self, params: dict):
        self.exits = params.get("exits", [])
        self._exits_taken = [False] * len(self.exits)
        self._trailing_stop = None
        
    def manage(self, trade: "TradeRecord", current_bar: dict, bars_since_entry: int) -> PolicyDecision:
        close_price = current_bar["close"]
        low_price = current_bar["low"]
        high_price = current_bar["high"]
        entry = trade.signal.entry_price
        risk = max(trade.signal.risk_points, 0.0001)
        is_long = trade.signal.direction == TradeDirection.LONG
        
        orig_stop = trade.signal.stop_price
        current_stop = self._trailing_stop or orig_stop
        
        if is_long and low_price <= current_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop" if not self._trailing_stop else "trail")
        elif not is_long and high_price >= current_stop:
            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="stop" if not self._trailing_stop else "trail")

        r_multiple = (high_price - entry) / risk if is_long else (entry - low_price) / risk
        
        for i, exit_cfg in enumerate(self.exits):
            if not self._exits_taken[i]:
                if exit_cfg.get("trail"):
                    # Applies trailing logic
                    atr = current_bar.get("atr_14", 0)
                    mult = exit_cfg.get("trail_atr_multiplier", 2.0)
                    if is_long:
                        potential = close_price - (mult * atr)
                        if self._trailing_stop is None or potential > self._trailing_stop:
                            self._trailing_stop = potential
                            return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=potential)
                    else:
                        potential = close_price + (mult * atr)
                        if self._trailing_stop is None or potential < self._trailing_stop:
                            self._trailing_stop = potential
                            return PolicyDecision(action=PolicyAction.MOVE_STOP, new_stop_price=potential)
                else:
                    if r_multiple >= exit_cfg.get("target_rr", 1.0):
                        self._exits_taken[i] = True
                        if i == len(self.exits) - 1:
                            return PolicyDecision(action=PolicyAction.EXIT_FULL, exit_reason="target")
                        return PolicyDecision(action=PolicyAction.TAKE_PARTIAL, partial_pct=exit_cfg.get("pct", 0.33))
                
        return PolicyDecision(action=PolicyAction.HOLD)
        
    def reset(self):
        self._exits_taken = [False] * len(self.exits)
        self._trailing_stop = None

def get_policy(name: str, params: dict, base_policy: TradePolicy = None) -> TradePolicy:
    if name == "cover_the_queen":
        return CoverTheQueen(params)
    elif name == "fixed_target":
        return FixedTarget(params)
    elif name == "scaled_exit":
        return ScaledExit(params)
    elif name == "breakeven_trail":
        return BreakevenTrail(params)
    elif name == "time_stop":
        return TimeStop(params, base_policy)
    else:
        raise ValueError(f"Unknown risk policy: {name}")
