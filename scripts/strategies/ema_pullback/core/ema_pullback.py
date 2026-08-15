"""
ADR-017 Vectorized EMA Pullback Strategy with Independent Filter & Regime Toggles.
==================================================================================
Identifies high-momentum trend expansions and tests pullbacks to EMA 20/50.
Supports modular ablations:
- FVG Confluence (pullback into active unmitigated FVG)
- Kaufman Efficiency Ratio (KER >= 0.40 trend conviction)
- Barbwire Bar Overlap (mutual containment <= 65%)
- TTM Squeeze Momentum Direction
- VWAP Distance & Chop Filters
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.price_action.volatility_leading import (
    compute_kaufman_efficiency,
    compute_ttm_squeeze,
    compute_bar_overlap,
)
from scripts.libs_py.ict_engine import detect_fvg


class EMAPullbackStrategy:
    """ADR-017 vectorized EMA pullback hunter with modular filter ablations."""

    OUTPUT_COLUMNS = [
        "signal_time",
        "direction",
        "entry_price",
        "stop_price",
        "target1_price",
        "model_name",
        "risk_pts",
    ]

    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        self.strategy_name = "EMA Pullback"

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        ema_len = int(p.get("ema_len", 50))
        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 1.4))
        tp_r_mult = float(p.get("tp_r_mult", 1.8))
        min_slope = float(p.get("min_slope", 0.0))

        # Filter Toggles (all default to False for pristine raw baseline unless specified)
        use_fvg_filter = bool(p.get("use_fvg_filter", False))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.40))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))
        use_ttm_squeeze_filter = bool(p.get("use_ttm_squeeze_filter", False))
        use_vwap_filter = bool(p.get("use_vwap_filter", False))
        use_chop_filter = bool(p.get("use_chop_filter", False))

        # 1. Base EMA & Slope
        df["ema"] = df["close"].ewm(span=ema_len, adjust=False).mean()
        df["ema_slope"] = df["ema"].diff()

        # ATR calculation
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean().bfill()

        # Time Window: RTH Morning
        intraday_mask = (df.index.time >= time(9, 40)) & (df.index.time <= time(12, 30))

        uptrend = (df["close"] > df["ema"]) & (df["ema_slope"] >= min_slope)
        downtrend = (df["close"] < df["ema"]) & (df["ema_slope"] <= -min_slope)

        long_mask = intraday_mask & uptrend & (df["low"] <= df["ema"]) & (df["close"] >= df["ema"])
        short_mask = intraday_mask & downtrend & (df["high"] >= df["ema"]) & (df["close"] <= df["ema"])

        # ---------------------------------------------------------------------
        # Isolated Filter 1: FVG Confluence (Pullback touches unmitigated FVG)
        # ---------------------------------------------------------------------
        if use_fvg_filter and (long_mask | short_mask).any():
            fvg_df = detect_fvg(df, require_candle_direction=True)
            # Bullish FVG active within last 10 bars
            recent_bull_fvg = (fvg_df["fvg_type"] == 1).rolling(10, min_periods=1).max().astype(bool)
            recent_bear_fvg = (fvg_df["fvg_type"] == -1).rolling(10, min_periods=1).max().astype(bool)
            long_mask &= recent_bull_fvg
            short_mask &= recent_bear_fvg

        # ---------------------------------------------------------------------
        # Isolated Filter 2: Kaufman Efficiency Ratio (KER >= threshold)
        # ---------------------------------------------------------------------
        if use_ker_filter and (long_mask | short_mask).any():
            ker_df = compute_kaufman_efficiency(df, period=5, efficient_threshold=ker_min)
            ker_valid = ker_df["ker_5"] >= ker_min
            long_mask &= ker_valid
            short_mask &= ker_valid

        # ---------------------------------------------------------------------
        # Isolated Filter 3: Barbwire Anti-Chop (Bar Overlap <= threshold)
        # ---------------------------------------------------------------------
        if use_barbwire_filter and (long_mask | short_mask).any():
            overlap_df = compute_bar_overlap(df, window=3, threshold=max_bar_overlap / 100.0)
            not_barbwire = ~overlap_df["is_barbwire_overlap"]
            long_mask &= not_barbwire
            short_mask &= not_barbwire

        # ---------------------------------------------------------------------
        # Isolated Filter 4: TTM Squeeze Momentum Direction
        # ---------------------------------------------------------------------
        if use_ttm_squeeze_filter and (long_mask | short_mask).any():
            squeeze_df = compute_ttm_squeeze(df)
            long_mask &= (squeeze_df["squeeze_mom"] > 0)
            short_mask &= (squeeze_df["squeeze_mom"] < 0)

        # ---------------------------------------------------------------------
        # Isolated Filter 5: VWAP Distance Filter
        # ---------------------------------------------------------------------
        if use_vwap_filter and (long_mask | short_mask).any() and "volume" in df.columns:
            date_key = df.index.normalize()
            typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
            vol = df["volume"].clip(lower=0)
            cum_pv = (typical_price * vol).groupby(date_key).cumsum()
            cum_vol = vol.groupby(date_key).cumsum().replace(0, np.nan)
            vwap = cum_pv / cum_vol
            # Only long above VWAP, short below VWAP
            long_mask &= (df["close"] > vwap)
            short_mask &= (df["close"] < vwap)

        # ---------------------------------------------------------------------
        # Isolated Filter 6: Institutional Chop Filter
        # ---------------------------------------------------------------------
        if use_chop_filter and (long_mask | short_mask).any():
            from scripts.libs_py.features.chop import compute_chop_score
            chop_res = compute_chop_score(df)
            not_choppy = chop_res["chop_regime"] != "choppy"
            long_mask &= not_choppy
            short_mask &= not_choppy

        df["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        df.loc[long_mask, "direction"] = "long"
        df.loc[short_mask, "direction"] = "short"

        combined = df.dropna(subset=["direction"]).copy()
        if combined.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        combined["date"] = combined.index.normalize()
        first_sigs = combined.groupby("date").head(1).copy()

        first_sigs["signal_time"] = first_sigs.index
        first_sigs["entry_price"] = first_sigs["close"]
        first_sigs["model_name"] = "ema_pullback"

        risk = first_sigs["atr"] * sl_atr_mult
        first_sigs["risk_pts"] = risk
        first_sigs["stop_price"] = np.where(
            first_sigs["direction"] == "long",
            first_sigs["entry_price"] - risk,
            first_sigs["entry_price"] + risk,
        )
        first_sigs["target1_price"] = np.where(
            first_sigs["direction"] == "long",
            first_sigs["entry_price"] + (risk * tp_r_mult),
            first_sigs["entry_price"] - (risk * tp_r_mult),
        )

        return first_sigs[self.OUTPUT_COLUMNS].dropna().reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "ema_len": [20, 50],
            "sl_atr_mult": [1.0, 1.4, 1.8],
            "tp_r_mult": [1.5, 2.0, 2.5],
            "use_fvg_filter": [True, False],
            "use_ker_filter": [True, False],
            "use_barbwire_filter": [True, False],
            "use_ttm_squeeze_filter": [True, False],
            "use_vwap_filter": [True, False],
        }
