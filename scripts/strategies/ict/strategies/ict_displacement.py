"""
ICT Displacement (Market Structure Shift) Strategy
====================================================
Harmonised under ADR-020 / ADR-021 / ADR-017 / ADR-002.

Concept:
    A Market Structure Shift (MSS) occurs when price closes through
    the most recent confirmed Swing High (bullish MSS) or Swing Low
    (bearish MSS).  Entry is taken at the close of the breaking bar;
    the stop is placed beyond the swing that was violated; the target
    is set at a configurable R:R multiple.

Ported from: scripts/strategies/ict/core/bias_displacement.py
Architecture: Pillar 2 - Pure Signal Hunter (zero I/O, zero loops)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

from scripts.libs_py.ict_engine import detect_swings, detect_structure_breaks

# Canonical output columns required by VectorizedBacktester
_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

# Hard exit: 15:59 ET (ADR-020 — prop-firm RTH liquidation)
_LAST_ENTRY_HOUR = 14
_LAST_ENTRY_MINUTE = 30


class ICTDisplacementStrategy:
    """
    ICT Market Structure Shift (Displacement) Strategy.

    Detects vectorised MSS events and returns a canonical Signal List
    DataFrame suitable for VectorizedBacktester.run().

    Complies with:
        - ADR-017: Zero-loop vectorization
        - ADR-002: Percentage-normalised stop/target arithmetic
        - ADR-020: 16:00 ET hard-exit (no new entries after 14:30 ET)
    """

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT Displacement (MSS)"

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        data : pd.DataFrame
            OHLCV DataFrame with tz-aware America/New_York index (from DataLoader).
        params : dict, optional
            swing_length : int   — rolling window for swing detection (default 5)
            risk_reward  : float — R:R multiplier for target (default 2.0)
            stop_ticks   : int   — ticks beyond swing for stop (default 4)
            tick_size    : float — instrument tick size (default 0.25)
            session_only : bool  — restrict to NY open 09:30–14:30 (default True)

        Returns
        -------
        pd.DataFrame with columns: signal_time, direction, entry_price,
                                   stop_price, target1_price
        """
        p = params or {}
        swing_length  = int(p.get("swing_length", 5))
        risk_reward   = float(p.get("risk_reward", 2.0))
        stop_ticks    = int(p.get("stop_ticks", 4))
        tick_size     = float(p.get("tick_size", 0.25))
        session_only  = bool(p.get("session_only", True))
        stop_buf      = stop_ticks * tick_size

        # ── 1. Pillar-1 vectorised indicators ──────────────────────────────
        swings = detect_swings(data, swing_length=swing_length)
        breaks = detect_structure_breaks(data, swings)

        close = data["close"].values
        idx   = data.index

        # ── 2. MSS signals: first close that clears the tracked level ───────
        # break_high == True  → bullish MSS (close > last swing high)
        # break_low  == True  → bearish MSS (close < last swing low)
        bull_mss = breaks["break_high"].values & ~np.roll(breaks["break_high"].values, 1)
        bear_mss = breaks["break_low"].values  & ~np.roll(breaks["break_low"].values,  1)
        bull_mss[0] = bear_mss[0] = False   # roll artifact

        # ── 3. Time filter (ADR-020) ────────────────────────────────────────
        if session_only and hasattr(idx, "hour"):
            hour   = idx.hour
            minute = idx.minute
            in_session = (
                ((hour > 9) | ((hour == 9) & (minute >= 30)))
                & ((hour < _LAST_ENTRY_HOUR) | ((hour == _LAST_ENTRY_HOUR) & (minute <= _LAST_ENTRY_MINUTE)))
            )
            bull_mss = bull_mss & np.asarray(in_session)
            bear_mss = bear_mss & np.asarray(in_session)

        # ── 4. Assemble signal rows (vectorised where) ──────────────────────
        direction = np.where(bull_mss, "long", np.where(bear_mss, "short", None))
        mask = (direction == "long") | (direction == "short")

        if not mask.any():
            return pd.DataFrame(columns=_COLS)

        sig = pd.DataFrame({
            "signal_time": idx[mask],
            "direction":   direction[mask],
            "entry_price": close[mask],
            "level_h":     breaks["level_h"].values[mask],
            "level_l":     breaks["level_l"].values[mask],
        })

        # ── 5. Stop & target (ADR-002: percentage arithmetic) ───────────────
        is_long = sig["direction"] == "long"
        sig["stop_price"] = np.where(
            is_long,
            sig["level_l"] - stop_buf,   # stop below the violated swing low
            sig["level_h"] + stop_buf,   # stop above the violated swing high
        )
        risk = (sig["entry_price"] - sig["stop_price"]).abs()
        sig["target1_price"] = np.where(
            is_long,
            sig["entry_price"] + risk * risk_reward,
            sig["entry_price"] - risk * risk_reward,
        )

        return sig[_COLS].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """Optuna-compatible parameter search space."""
        return {
            "swing_length": ("int",         3,    9),
            "risk_reward":  ("float",       1.5,  3.0),
            "stop_ticks":   ("int",         2,    10),
            "session_only": ("categorical", [True, False]),
        }
