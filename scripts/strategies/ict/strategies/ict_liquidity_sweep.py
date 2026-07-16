"""
ICT Liquidity Sweep Strategy
==============================
Harmonised under ADR-020 / ADR-017 / ADR-002.

Concept:
    Price sweeps through a swing high/low (taking out buy/sell-side
    liquidity), then immediately reverses — a "stop hunt."  Entry is
    taken at the close of the CISD bar (Change in State of Delivery)
    that confirms the reversal.  Stop is placed beyond the sweep
    extreme; target is the opposite swing at an R:R multiple.

Ported from: scripts/strategies/ict/core/bias_liquidity_sweep.py
Architecture: Pillar 2 - Pure Signal Hunter (zero I/O, zero loops)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional


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

from scripts.libs_py.ict_engine import detect_swings, detect_cisd

_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]
_LAST_ENTRY_HOUR, _LAST_ENTRY_MIN = 14, 30


class ICTLiquiditySweepStrategy:
    """
    ICT Liquidity Sweep (Stop Hunt + CISD) Strategy.

    Complies with:
        - ADR-017: Zero-loop vectorization
        - ADR-002: Percentage-normalised stops/targets
        - ADR-020: No new entries after 14:30 ET; hard exit at 16:00 ET
    """

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT Liquidity Sweep"

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        data : pd.DataFrame  — NY-localised OHLCV from DataLoader
        params : dict
            swing_length : int   — fractal window (default 5)
            risk_reward  : float — R:R multiplier (default 2.0)
            stop_ticks   : int   — ticks beyond sweep extreme (default 6)
            tick_size    : float — instrument tick (default 0.25)
            session_only : bool  — restrict to 09:30–14:30 ET (default True)
        """
        p           = params or {}
        swing_len   = int(p.get("swing_length", 5))
        rr          = float(p.get("risk_reward", 2.0))
        stop_ticks  = int(p.get("stop_ticks", 6))
        tick_size   = float(p.get("tick_size", 0.25))
        session_only = bool(p.get("session_only", True))
        stop_buf    = stop_ticks * tick_size

        # ── 1. Pillar-1 vectorised indicators ──────────────────────────────
        swings = detect_swings(data, swing_length=swing_len)
        cisd   = detect_cisd(data, swings)

        idx   = data.index
        close = data["close"].values
        high  = data["high"].values
        low   = data["low"].values

        # ── 2. Sweep events ─────────────────────────────────────────────────
        # detect_cisd tracks sweep_high (wick above last SH, close back below)
        # and sweep_low (wick below last SL, close back above)
        # bullish_shift → price swept the sell-side (lows) then CISD long
        # bearish_shift → price swept the buy-side  (highs) then CISD short
        bull_entry = (cisd["cisd"].values == 1)
        bear_entry = (cisd["cisd"].values == -1)

        # ── 3. Time filter (ADR-020) ────────────────────────────────────────
        if session_only and hasattr(idx, "hour"):
            hour, minute = idx.hour, idx.minute
            in_session = (
                ((hour > 9) | ((hour == 9) & (minute >= 30)))
                & ((hour < _LAST_ENTRY_HOUR) | ((hour == _LAST_ENTRY_HOUR) & (minute <= _LAST_ENTRY_MIN)))
            )
            bull_entry = bull_entry & np.asarray(in_session)
            bear_entry = bear_entry & np.asarray(in_session)

        direction = np.where(bull_entry, "long", np.where(bear_entry, "short", None))
        mask = (direction == "long") | (direction == "short")

        if not mask.any():
            return pd.DataFrame(columns=_COLS)

        # ── 4. Track the sweep extreme for stop placement ───────────────────
        # For a bullish CISD (swept lows): stop = recent low - buf
        # For a bearish CISD (swept highs): stop = recent high + buf
        last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
        last_sl = swings["level"].where(swings["shl"] == -1).ffill().values

        sig = pd.DataFrame({
            "signal_time": idx[mask],
            "direction":   direction[mask],
            "entry_price": close[mask],
            "last_sh":     last_sh[mask],
            "last_sl":     last_sl[mask],
        })

        # ── 5. Stop & target ─────────────────────────────────────────────────
        is_long = sig["direction"] == "long"
        sig["stop_price"] = np.where(
            is_long,
            sig["last_sl"] - stop_buf,
            sig["last_sh"] + stop_buf,
        )
        risk = (sig["entry_price"] - sig["stop_price"]).abs()
        sig["target1_price"] = np.where(
            is_long,
            sig["entry_price"] + risk * rr,
            sig["entry_price"] - risk * rr,
        )

        return sig[_COLS].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "swing_length": ("int",         3,    9),
            "risk_reward":  ("float",       1.5,  3.0),
            "stop_ticks":   ("int",         4,    12),
            "session_only": ("categorical", [True, False]),
        }
