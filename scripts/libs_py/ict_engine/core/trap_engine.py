"""
========================================================================================
Trapped Liquidity & Failed State Re-Expansion Engine (Alpha 1)
========================================================================================
A reusable quantitative engine for detecting and executing trapped liquidity breakouts.

Concept:
--------
When an institutional structure (such as a CISD delivery origin SL-4, an Opening Range
Breakout boundary, or a major Key Level) is invalidated by high-volume displacement,
the opposing side is trapped. This failure triggers an explosive continuation leg.

The Engine arms an opposing breakout order with:
1. Entry: Breach point beyond the invalidated structural anchor.
2. Stop Loss: The failed structure's opposite boundary.
3. Target: Basis Points expansion target (30-50 bps).
========================================================================================
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

@dataclass
class TrapOrder:
    direction: int          # +1 for Long Breakout, -1 for Short Breakout
    entry_level: float
    stop_loss: float
    armed_bar: int
    target_bps: float
    max_wait_bars: int = 3

class TrappedLiquidityEngine:
    """
    Decoupled Trapped Liquidity Breakout Engine.
    """
    def __init__(self, max_wait_bars: int = 3, target_bps: float = 40.0, max_risk_bps: float = 15.0):
        self.max_wait_bars = max_wait_bars
        self.target_bps = target_bps
        self.max_risk_bps = max_risk_bps
        self.pending_trap: Optional[TrapOrder] = None

    def on_structure_invalidation(
        self,
        bar_idx: int,
        failed_direction: int,
        invalidation_price: float,
        failed_anchor_price: float,
        buffer_ticks: float = 1.0,
    ) -> Optional[TrapOrder]:
        """
        Called when a trade or structural setup hits its stop loss / invalidation.
        Arms an immediate opposing breakout trap order.
        """
        # If a Long setup failed (breached down), arm a Short Breakout
        if failed_direction == 1:
            trap_entry = invalidation_price - buffer_ticks
            trap_sl = failed_anchor_price
            risk_bps = ((trap_sl - trap_entry) / trap_entry) * 10000.0

            if 0 < risk_bps <= self.max_risk_bps:
                self.pending_trap = TrapOrder(
                    direction=-1,
                    entry_level=trap_entry,
                    stop_loss=trap_sl,
                    armed_bar=bar_idx,
                    target_bps=self.target_bps,
                    max_wait_bars=self.max_wait_bars,
                )
                return self.pending_trap

        # If a Short setup failed (breached up), arm a Long Breakout
        elif failed_direction == -1:
            trap_entry = invalidation_price + buffer_ticks
            trap_sl = failed_anchor_price
            risk_bps = ((trap_entry - trap_sl) / trap_entry) * 10000.0

            if 0 < risk_bps <= self.max_risk_bps:
                self.pending_trap = TrapOrder(
                    direction=1,
                    entry_level=trap_entry,
                    stop_loss=trap_sl,
                    armed_bar=bar_idx,
                    target_bps=self.target_bps,
                    max_wait_bars=self.max_wait_bars,
                )
                return self.pending_trap

        return None

    def check_fill(self, bar_idx: int, high: float, low: float) -> Optional[Tuple[int, float, float, float]]:
        """
        Evaluates whether a pending trap breakout is filled on the current bar.
        Returns (direction, entry_price, stop_loss, target_bps) or None.
        """
        if self.pending_trap is None:
            return None

        if (bar_idx - self.pending_trap.armed_bar) > self.pending_trap.max_wait_bars:
            self.pending_trap = None
            return None

        # Check Long Breakout Fill
        if self.pending_trap.direction == 1 and high >= self.pending_trap.entry_level:
            filled_trap = self.pending_trap
            self.pending_trap = None
            return (1, filled_trap.entry_level, filled_trap.stop_loss, filled_trap.target_bps)

        # Check Short Breakout Fill
        elif self.pending_trap.direction == -1 and low <= self.pending_trap.entry_level:
            filled_trap = self.pending_trap
            self.pending_trap = None
            return (-1, filled_trap.entry_level, filled_trap.stop_loss, filled_trap.target_bps)

        return None
