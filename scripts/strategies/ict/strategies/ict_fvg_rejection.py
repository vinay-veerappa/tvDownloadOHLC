"""
ICT FVG Rejection Strategy
============================
Harmonised under ADR-020 / ADR-017 / ADR-002.

Concept:
    Price returns to a Fair Value Gap (FVG) — a 3-candle imbalance
    left by a displacement move.  When price enters the FVG zone and
    closes back in the direction of the original move (rejection),
    a trade is taken.  Stop is placed beyond the FVG boundary;
    target is the next liquidity draw at an R:R multiple.

Ported from: scripts/strategies/ict/core/bias_fvg_rejection.py
Architecture: Pillar 2 - Pure Signal Hunter (zero I/O, zero loops)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

from scripts.libs_py.ict_engine import detect_fvg, detect_swings

_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]
_LAST_ENTRY_HOUR, _LAST_ENTRY_MIN = 14, 30


class ICTFVGRejectionStrategy:
    """
    ICT Fair Value Gap (FVG) Rejection Strategy.

    Detects vectorised FVGs and enters on the first bar where price
    re-enters the gap zone and closes in the originating direction.

    Complies with:
        - ADR-017: Zero-loop vectorization  (detect_fvg is fully vectorised)
        - ADR-002: Percentage-normalised stops / targets
        - ADR-020: No new entries after 14:30 ET
    """

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT FVG Rejection"

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
            stop_ticks        : int   — extra ticks beyond FVG boundary (default 2)
            tick_size         : float — instrument tick size (default 0.25)
            join_consecutive  : bool  — merge adjacent FVGs (default False)
            session_only      : bool  — restrict to 09:30–14:30 ET (default True)
        """
        p                = params or {}
        swing_len        = int(p.get("swing_length", 5))
        rr               = float(p.get("risk_reward", 2.0))
        stop_ticks       = int(p.get("stop_ticks", 2))
        tick_size        = float(p.get("tick_size", 0.25))
        join_consecutive = bool(p.get("join_consecutive", False))
        session_only     = bool(p.get("session_only", True))
        stop_buf         = stop_ticks * tick_size

        # ── 1. Pillar-1 vectorised indicators ──────────────────────────────
        fvg    = detect_fvg(data, join_consecutive=join_consecutive)
        swings = detect_swings(data, swing_length=swing_len)

        idx   = data.index
        close = data["close"].values
        open_ = data["open"].values
        high  = data["high"].values
        low   = data["low"].values

        # ── 2. Forward-fill FVG zone boundaries (the gap persists until filled) ─
        # fvg["fvg"]  :  1 = bullish, -1 = bearish, NaN = none
        # fvg["top"]  :  upper bound of the gap
        # fvg["bottom"]: lower bound of the gap
        fvg_type = fvg["fvg"].values
        fvg_top  = fvg["top"].values
        fvg_bot  = fvg["bottom"].values

        # Carry the most recent *unmitigated* FVG forward using ffill
        bull_top = pd.Series(np.where(fvg_type == 1, fvg_top, np.nan)).ffill().values
        bull_bot = pd.Series(np.where(fvg_type == 1, fvg_bot, np.nan)).ffill().values
        bear_top = pd.Series(np.where(fvg_type == -1, fvg_top, np.nan)).ffill().values
        bear_bot = pd.Series(np.where(fvg_type == -1, fvg_bot, np.nan)).ffill().values

        # ── 3. Rejection detection ──────────────────────────────────────────
        # Bullish FVG rejection:
        #   price enters the gap (low <= bull_top and low >= bull_bot)
        #   AND closes bullishly (close > open_)  — rejection long
        bull_touch  = (low <= bull_top) & (low >= bull_bot)
        bull_reject = bull_touch & (close > open_)   # bullish close inside gap

        # Bearish FVG rejection:
        #   price enters the gap (high >= bear_bot and high <= bear_top)
        #   AND closes bearishly (close < open_)  — rejection short
        bear_touch  = (high >= bear_bot) & (high <= bear_top)
        bear_reject = bear_touch & (close < open_)

        # ── 4. Time filter (ADR-020) ────────────────────────────────────────
        if session_only and hasattr(idx, "hour"):
            hour, minute = idx.hour, idx.minute
            in_session = (
                ((hour > 9) | ((hour == 9) & (minute >= 30)))
                & ((hour < _LAST_ENTRY_HOUR) | ((hour == _LAST_ENTRY_HOUR) & (minute <= _LAST_ENTRY_MIN)))
            )
            bull_reject = bull_reject & np.asarray(in_session)
            bear_reject = bear_reject & np.asarray(in_session)

        direction = np.where(bull_reject, "long", np.where(bear_reject, "short", None))
        mask = (direction == "long") | (direction == "short")

        if not mask.any():
            return pd.DataFrame(columns=_COLS)

        # ── 5. Assemble & price signals ─────────────────────────────────────
        sig = pd.DataFrame({
            "signal_time": idx[mask],
            "direction":   direction[mask],
            "entry_price": close[mask],
            # Stop is placed just beyond the opposite FVG boundary
            "fvg_bot_bull": bull_bot[mask],
            "fvg_top_bear": bear_top[mask],
            # Use swing context for target sizing
            "last_sh": swings["level"].where(swings["shl"] == 1).ffill().values[mask],
            "last_sl": swings["level"].where(swings["shl"] == -1).ffill().values[mask],
        })

        is_long = sig["direction"] == "long"
        sig["stop_price"] = np.where(
            is_long,
            sig["fvg_bot_bull"] - stop_buf,   # stop just below FVG bottom
            sig["fvg_top_bear"] + stop_buf,   # stop just above FVG top
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
            "risk_reward":      ("float",       1.5,  3.0),
            "stop_ticks":       ("int",         1,    6),
            "join_consecutive": ("categorical", [True, False]),
            "session_only":     ("categorical", [True, False]),
        }
