"""
ADR-017 Vectorized VWAP Reclaim Strategy with Independent Filter & Regime Toggles.
==================================================================================
Identifies deviations from Session VWAP and trades reclaims back through VWAP.
Supports modular ablations:
- IFVG / Displacement Through VWAP (trapped participant absorption)
- CISD Delivery Series Flip (delivery run reversal)
- VWAP Cross Limit (veto rotational chop when daily crosses > threshold)
- Kaufman Efficiency Ratio (KER >= 0.35)
- Barbwire Bar Overlap (mutual containment <= 65%)
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
    compute_bar_overlap,
)
from scripts.libs_py.ict_engine import (
    detect_fvg,
    detect_inversion_fvg,
    detect_swings,
    detect_cisd,
)


class VWAPReclaimStrategy:
    """ADR-017 vectorized VWAP reclaim hunter with modular filter ablations."""

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
        self.strategy_name = "VWAP Reclaim"

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "volume" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 1.2))
        tp_r_mult = float(p.get("tp_r_mult", 1.8))
        rel_vol_min = float(p.get("rel_vol_min", 1.0))
        min_abs_volume = float(p.get("min_abs_volume", 1.0))

        # Filter Toggles (all default to False for pristine raw baseline unless specified)
        use_ifvg_filter = bool(p.get("use_ifvg_filter", False))
        use_cisd_filter = bool(p.get("use_cisd_filter", False))
        use_vwap_cross_limit = bool(p.get("use_vwap_cross_limit", False))
        max_vwap_crosses = int(p.get("max_vwap_crosses", 4))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.35))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))

        # 1. Base VWAP calculation
        date_key = df.index.normalize()
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].clip(lower=0)

        cum_pv = (typical_price * vol).groupby(date_key).cumsum()
        cum_vol = vol.groupby(date_key).cumsum().replace(0, np.nan)
        df["vwap"] = cum_pv / cum_vol

        # ATR calculation
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean().bfill()

        df["rel_vol"] = vol / vol.rolling(20, min_periods=20).mean()
        intraday_mask = (df.index.time >= time(9, 35)) & (df.index.time <= time(13, 0))

        prev_close = df["close"].shift(1)
        prev_vwap = df["vwap"].shift(1)

        long_mask = (
            intraday_mask
            & (prev_close < prev_vwap)
            & (df["close"] > df["vwap"])
            & (df["low"] <= df["vwap"])
            & (df["rel_vol"] >= rel_vol_min)
            & (vol >= min_abs_volume)
        )
        short_mask = (
            intraday_mask
            & (prev_close > prev_vwap)
            & (df["close"] < df["vwap"])
            & (df["high"] >= df["vwap"])
            & (df["rel_vol"] >= rel_vol_min)
            & (vol >= min_abs_volume)
        )

        # ---------------------------------------------------------------------
        # Isolated Filter 1: IFVG / Displacement Through VWAP
        # ---------------------------------------------------------------------
        if use_ifvg_filter and (long_mask | short_mask).any():
            fvg_df = detect_fvg(df, require_candle_direction=True)
            ifvg_df = detect_inversion_fvg(df, fvg_df)
            # Reclaim candle or recent 3 bars formed a valid IFVG in direction
            recent_bull_ifvg = (ifvg_df["ifvg"] == 1).rolling(3, min_periods=1).max().astype(bool)
            recent_bear_ifvg = (ifvg_df["ifvg"] == -1).rolling(3, min_periods=1).max().astype(bool)
            recent_bull_fvg = (fvg_df["fvg_type"] == 1).rolling(3, min_periods=1).max().astype(bool)
            recent_bear_fvg = (fvg_df["fvg_type"] == -1).rolling(3, min_periods=1).max().astype(bool)
            long_mask &= (recent_bull_ifvg | recent_bull_fvg)
            short_mask &= (recent_bear_ifvg | recent_bear_fvg)

        # ---------------------------------------------------------------------
        # Isolated Filter 2: CISD Delivery Flip
        # ---------------------------------------------------------------------
        if use_cisd_filter and (long_mask | short_mask).any():
            swings = detect_swings(df, swing_length=3)
            cisd_df = detect_cisd(df, swings)
            recent_bull_cisd = (cisd_df["cisd"] == 1).rolling(5, min_periods=1).max().astype(bool)
            recent_bear_cisd = (cisd_df["cisd"] == -1).rolling(5, min_periods=1).max().astype(bool)
            long_mask &= recent_bull_cisd
            short_mask &= recent_bear_cisd

        # ---------------------------------------------------------------------
        # Isolated Filter 3: VWAP Rotational Cross Limit
        # ---------------------------------------------------------------------
        if use_vwap_cross_limit and (long_mask | short_mask).any():
            crosses = ((prev_close < prev_vwap) & (df["close"] > df["vwap"])) | (
                (prev_close > prev_vwap) & (df["close"] < df["vwap"])
            )
            daily_cross_count = crosses.groupby(date_key).cumsum()
            under_cross_limit = daily_cross_count <= max_vwap_crosses
            long_mask &= under_cross_limit
            short_mask &= under_cross_limit

        # ---------------------------------------------------------------------
        # Isolated Filter 4: Kaufman Efficiency Ratio (KER >= threshold)
        # ---------------------------------------------------------------------
        if use_ker_filter and (long_mask | short_mask).any():
            ker_df = compute_kaufman_efficiency(df, period=5, efficient_threshold=ker_min)
            ker_valid = ker_df["ker_5"] >= ker_min
            long_mask &= ker_valid
            short_mask &= ker_valid

        # ---------------------------------------------------------------------
        # Isolated Filter 5: Barbwire Anti-Chop (Bar Overlap <= threshold)
        # ---------------------------------------------------------------------
        if use_barbwire_filter and (long_mask | short_mask).any():
            overlap_df = compute_bar_overlap(df, window=3, threshold=max_bar_overlap / 100.0)
            not_barbwire = ~overlap_df["is_barbwire_overlap"]
            long_mask &= not_barbwire
            short_mask &= not_barbwire

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
        first_sigs["model_name"] = "vwap_reclaim"

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
            "sl_atr_mult": [0.8, 1.2, 1.6],
            "tp_r_mult": [1.2, 1.8, 2.5],
            "use_ifvg_filter": [True, False],
            "use_cisd_filter": [True, False],
            "use_vwap_cross_limit": [True, False],
            "use_ker_filter": [True, False],
            "use_barbwire_filter": [True, False],
        }
