"""
ICT NY Session Killzone Strategy
==================================
Harmonised under ADR-020 / ADR-017 / ADR-002.

Concept:
    The New York AM killzone (08:30–11:00 ET) is the highest-probability
    ICT manipulation window.  Price typically sweeps Asian or London
    session liquidity in the first 30–60 minutes, then trades towards
    the true algorithmic target for the day.

    This strategy:
      1. Identifies the Asian session high/low (20:00–00:00 ET previous day)
      2. Detects a sweep of those levels in the NY killzone
      3. Waits for a CISD bar confirming the reversal
      4. Enters long/short with stop beyond the sweep extreme

Ported from: scripts/strategies/ict/core/bias_ny_session.py
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

from scripts.libs_py.ict_engine import (
    detect_swings,
    detect_cisd,
    get_session_data,
)

_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

# NY Killzone window (ET) — ADR-004 / sessions.py KILLZONES
_KZ_START_HOUR, _KZ_START_MIN = 8, 30
_KZ_END_HOUR,   _KZ_END_MIN   = 11, 0
_LAST_ENTRY_HOUR, _LAST_ENTRY_MIN = 14, 30


class ICTNYSessionStrategy:
    """
    ICT New York Killzone (NYAM) Liquidity + CISD Strategy.

    Identifies sweep of Asian session liquidity during the NY open
    killzone (08:30–11:00 ET) then enters on CISD confirmation.

    Complies with:
        - ADR-017: Zero-loop vectorization
        - ADR-002: Percentage-normalised stops / targets
        - ADR-020: Hard exit at 16:00 ET; no entries after 14:30 ET
    """

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT NY Session Killzone"

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        data : pd.DataFrame  — NY-localised OHLCV from DataLoader
        params : dict
            swing_length : int   — fractal window (default 5)
            risk_reward  : float — R:R multiplier (default 2.5)
            stop_ticks   : int   — extra ticks beyond sweep extreme (default 6)
            tick_size    : float — instrument tick size (default 0.25)
        """
        p           = params or {}
        swing_len   = int(p.get("swing_length", 5))
        rr          = float(p.get("risk_reward", 2.5))
        stop_ticks  = int(p.get("stop_ticks", 6))
        tick_size   = float(p.get("tick_size", 0.25))
        stop_buf    = stop_ticks * tick_size

        # ── 1. Pillar-1 indicators ──────────────────────────────────────────
        swings = detect_swings(data, swing_length=swing_len)
        cisd   = detect_cisd(data, swings)

        # Asian session high/low: provides the liquidity levels to be swept
        asian = get_session_data(data, "asian")

        idx   = data.index
        close = data["close"].values
        high  = data["high"].values
        low   = data["low"].values

        # ── 2. NY Killzone time mask ────────────────────────────────────────
        if hasattr(idx, "hour"):
            hour, minute = idx.hour, idx.minute
            in_kz = (
                ((hour > _KZ_START_HOUR) | ((hour == _KZ_START_HOUR) & (minute >= _KZ_START_MIN)))
                & ((hour < _KZ_END_HOUR) | ((hour == _KZ_END_HOUR) & (minute <= _KZ_END_MIN)))
            )
        else:
            in_kz = np.ones(len(data), dtype=bool)

        # ── 3. Asian range as liquidity targets ─────────────────────────────
        asian_hi = asian["session_high"].values
        asian_lo = asian["session_low"].values

        # A "sweep" of the Asian high = wick above it then closes below
        # A "sweep" of the Asian low  = wick below it then closes above
        swept_high = (high > asian_hi) & (close < asian_hi)
        swept_low  = (low < asian_lo) & (close > asian_lo)

        # ── 4. CISD in the killzone confirms the trade direction ─────────────
        bull_entry = (cisd["cisd"].values == 1) & swept_low  & np.asarray(in_kz)
        bear_entry = (cisd["cisd"].values == -1) & swept_high & np.asarray(in_kz)

        direction = np.where(bull_entry, "long", np.where(bear_entry, "short", None))
        mask = (direction == "long") | (direction == "short")

        if not mask.any():
            return pd.DataFrame(columns=_COLS)

        # ── 5. Build signal rows ─────────────────────────────────────────────
        last_sh = swings["level"].where(swings["shl"] == 1).ffill().values
        last_sl = swings["level"].where(swings["shl"] == -1).ffill().values

        sig = pd.DataFrame({
            "signal_time": idx[mask],
            "direction":   direction[mask],
            "entry_price": close[mask],
            "last_sh":     last_sh[mask],
            "last_sl":     last_sl[mask],
            "asian_hi":    asian_hi[mask],
            "asian_lo":    asian_lo[mask],
        })

        is_long = sig["direction"] == "long"
        sig["stop_price"] = np.where(
            is_long,
            sig["asian_lo"] - stop_buf,   # stop below swept Asian low
            sig["asian_hi"] + stop_buf,   # stop above swept Asian high
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
            "swing_length": ("int",   3,   9),
            "risk_reward":  ("float", 1.5, 4.0),
            "stop_ticks":   ("int",   4,   12),
        }
