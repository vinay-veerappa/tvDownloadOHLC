"""
ICT Asia Volatility Range Strategy
=====================================
Harmonised under ADR-020 / ADR-017 / ADR-002.

Concept:
    The Asian session (20:00–00:00 ET) typically consolidates into a
    tight range.  ICT methodology expects London or NY to break one
    side of this range (the "Judas Swing"), then trade to the opposing
    extreme and beyond.

    This strategy:
      1. Identifies the Asian session high/low for each day
      2. Detects the first breakout of either extreme during London open
         (02:00–05:00 ET) or NY open (08:30–11:00 ET)
      3. Waits for a closing rejection (close back inside the range = sweep)
      4. Enters in the opposite direction with stop beyond the wick extreme

Ported from: scripts/strategies/ict/core/bias_asia_volatility.py
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

from scripts.libs_py.ict_engine import get_session_data, detect_swings
from scripts.trading_framework.reporting.decision_log import GateRecorder

_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]
_LAST_ENTRY_HOUR, _LAST_ENTRY_MIN = 14, 30


class ICTAsiaVolatilityStrategy:
    """
    ICT Asia Range Breakout / Judas Swing Strategy.

    Identifies the Asian consolidation range and trades the reversal
    when price sweeps one extreme and closes back inside the range
    during London open or NY open killzone.

    Complies with:
        - ADR-017: Zero-loop vectorization
        - ADR-002: Percentage-normalised stops / targets
        - ADR-020: Hard exit at 16:00 ET; no entries after 14:30 ET
    """

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT Asia Volatility / Judas Swing"
        # Section 5.5: the criteria this hunter evaluates. None means not
        # instrumented; set by hunt() on every path.
        self.last_decisions: Optional[pd.DataFrame] = None

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        data : pd.DataFrame  — NY-localised OHLCV from DataLoader
        params : dict
            swing_length      : int   — fractal window for context swings (default 5)
            risk_reward       : float — R:R multiplier (default 2.0)
            stop_ticks        : int   — extra ticks beyond wick extreme (default 4)
            tick_size         : float — instrument tick size (default 0.25)
            min_range_points  : float — minimum Asian range width to consider (default 10.0)
            killzone          : str   — 'london_open' | 'ny_open' | 'both' (default 'both')
        """
        p              = params or {}
        swing_len      = int(p.get("swing_length", 5))
        rr             = float(p.get("risk_reward", 2.0))
        stop_ticks     = int(p.get("stop_ticks", 4))
        tick_size      = float(p.get("tick_size", 0.25))
        min_range      = float(p.get("min_range_points", 10.0))
        killzone       = str(p.get("killzone", "both"))
        stop_buf       = stop_ticks * tick_size

        # ── 1. Pillar-1 indicators ──────────────────────────────────────────
        asian   = get_session_data(data, "asian")
        swings  = detect_swings(data, swing_length=swing_len)

        idx   = data.index
        close = data["close"].values
        high  = data["high"].values
        low   = data["low"].values

        asian_hi = asian["session_high"].values
        asian_lo = asian["session_low"].values
        asian_range = asian_hi - asian_lo

        # ── 2. Active killzone mask ─────────────────────────────────────────
        if hasattr(idx, "hour"):
            hour, minute = idx.hour, idx.minute
            in_london = (
                ((hour > 2) | ((hour == 2) & (minute >= 0)))
                & (hour < 5)
            )
            in_ny = (
                ((hour > 8) | ((hour == 8) & (minute >= 30)))
                & ((hour < _LAST_ENTRY_HOUR) | ((hour == _LAST_ENTRY_HOUR) & (minute <= _LAST_ENTRY_MIN)))
            )
            if killzone == "london_open":
                in_active_kz = np.asarray(in_london)
            elif killzone == "ny_open":
                in_active_kz = np.asarray(in_ny)
            else:  # both
                in_active_kz = np.asarray(in_london) | np.asarray(in_ny)
        else:
            in_active_kz = np.ones(len(data), dtype=bool)

        # ── 3. Sweep detection (Judas Swing) ────────────────────────────────
        # RAW sweep+recovery is the decision-log trigger; the range floor and
        # the killzone are GATES so their rejections are visible (5.5).
        # A bullish Judas sweep: wick below Asian low then closes ABOVE it
        # → expect price to continue UP (stop hunt of sell-side liq.)
        sweep_bull = (low < asian_lo) & (close > asian_lo)
        judas_long = (
            sweep_bull
            & (asian_range >= min_range)           # meaningful range only
            & in_active_kz
        )

        # A bearish Judas sweep: wick above Asian high then closes BELOW it
        # → expect price to continue DOWN (stop hunt of buy-side liq.)
        sweep_bear = (high > asian_hi) & (close < asian_hi)
        judas_short = (
            sweep_bear
            & (asian_range >= min_range)
            & in_active_kz
        )

        # Deduplicate: only first signal per day
        direction = np.where(judas_long, "long", np.where(judas_short, "short", None))
        mask = (direction == "long") | (direction == "short")

        # Decision log (section 5.5): the sweep+recovery is the trigger; the
        # gates are the Asian-range floor, the killzone window, and
        # first-per-day. Recorded even when nothing sweeps.
        is_first = pd.Series(False, index=idx)
        if mask.any():
            _dates = pd.Series(pd.to_datetime(idx).normalize(), index=idx)
            first_mask = pd.Series(direction, index=idx).notna()
            # first qualifying bar per day
            _ord = first_mask.astype(int).groupby(_dates).cumsum()
            first_bar = first_mask & (_ord == 1)
            is_first |= first_bar
        self.last_decisions = (
            GateRecorder(idx, run_id="", strategy="ict_asia_volatility")
            .trigger(pd.Series(sweep_bull, index=idx), "long")
            .trigger(pd.Series(sweep_bear, index=idx), "short")
            .gate("asian_range_floor",
                  pd.Series(asian_range >= min_range, index=idx),
                  value=pd.Series(asian_range, index=idx),
                  threshold=min_range)
            .gate("killzone_window", pd.Series(in_active_kz, index=idx))
            .gate("first_signal_per_day", is_first)
            .to_frame(signal_prefix="iav_")
        )

        if not mask.any():
            return pd.DataFrame(columns=_COLS)

        sig = pd.DataFrame({
            "signal_time": idx[mask],
            "direction":   direction[mask],
            "entry_price": close[mask],
            "asian_hi":    asian_hi[mask],
            "asian_lo":    asian_lo[mask],
            "high":        high[mask],
            "low":         low[mask],
        })

        # Keep only first signal per calendar day
        sig["_date"] = pd.to_datetime(sig["signal_time"]).dt.normalize()
        sig = sig.groupby("_date").head(1).drop(columns="_date")

        # ── 4. Stop at wick extreme; target via R:R ─────────────────────────
        is_long = sig["direction"] == "long"
        sig["stop_price"] = np.where(
            is_long,
            sig["low"] - stop_buf,    # stop below the sweep wick low
            sig["high"] + stop_buf,   # stop above the sweep wick high
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
            "swing_length":     ("int",         3,    9),
            "risk_reward":      ("float",       1.5,  3.5),
            "stop_ticks":       ("int",         2,    10),
            "min_range_points": ("float",       5.0,  30.0),
            "killzone":         ("categorical", ["london_open", "ny_open", "both"]),
        }
