"""
ADR-017 Vectorized Failed Auction Strategy with Independent Filter & Regime Toggles.
====================================================================================
Identifies momentum sweeps outside prior-day extremes and trades mean reversion.
Supports modular ablations:
- CISD Delivery Series Reversal Trigger (eliminates blind limit knife-catching)
- Rejection-Leg FVG Creation (requires displacement gap off extreme)
- Impulse Exhaustion Filter (KER <= 0.40 at peak exhaustion)
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
    detect_swings,
    detect_cisd,
)
from scripts.trading_framework.reporting.decision_log import GateRecorder


class FailedAuctionStrategy:
    """ADR-017 vectorized failed auction hunter with modular filter ablations."""

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
        self.strategy_name = "Failed Auction"
        # Section 5.5: the criteria this hunter evaluates. None means not
        # instrumented; set by hunt().
        self.last_decisions: Optional[pd.DataFrame] = None

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 0.8))
        tp_r_mult = float(p.get("tp_r_mult", 2.0))
        break_buffer = float(p.get("break_buffer", 0.0))

        # Filter Toggles (all default to False for pristine raw baseline unless specified)
        use_cisd_trigger = bool(p.get("use_cisd_trigger", False))
        use_rejection_fvg_filter = bool(p.get("use_rejection_fvg_filter", False))
        use_exhaustion_ker_filter = bool(p.get("use_exhaustion_ker_filter", False))
        ker_exhaustion_max = float(p.get("ker_exhaustion_max", 0.40))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))

        # 1. Base Prior Day Levels
        date_key = df.index.normalize()
        daily = df.groupby(date_key).agg(day_high=("high", "max"), day_low=("low", "min"))
        prior_day = daily.shift(1)

        df["prior_high"] = date_key.map(prior_day["day_high"])
        df["prior_low"] = date_key.map(prior_day["day_low"])

        # ATR calculation
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean().bfill()

        intraday_mask = (df.index.time >= time(9, 35)) & (df.index.time <= time(14, 30))

        sweep_low = df["low"] < (df["prior_low"] * (1.0 - break_buffer))
        reclaim_low = df["close"] > df["prior_low"]
        sweep_high = df["high"] > (df["prior_high"] * (1.0 + break_buffer))
        reclaim_high = df["close"] < df["prior_high"]

        long_mask = intraday_mask & sweep_low & reclaim_low
        short_mask = intraday_mask & sweep_high & reclaim_high

        # The BASE setup before the ablation filters narrow it; the decision
        # log triggers on this so filter gates can actually fail (section 5.5).
        base_long, base_short = long_mask.copy(), short_mask.copy()

        # Applied-filter ledger for the decision log: every OPTIONAL filter
        # appends its mask as it runs, so the roster is exactly what this
        # invocation evaluated.
        applied_filters: list = []

        # ---------------------------------------------------------------------
        # Isolated Filter 1: CISD Delivery Series Reversal Trigger
        # ---------------------------------------------------------------------
        if use_cisd_trigger and (long_mask | short_mask).any():
            swings = detect_swings(df, swing_length=3)
            cisd_df = detect_cisd(df, swings)
            recent_bull_cisd = (cisd_df["cisd"] == 1).rolling(5, min_periods=1).max().astype(bool)
            recent_bear_cisd = (cisd_df["cisd"] == -1).rolling(5, min_periods=1).max().astype(bool)
            applied_filters.append(
                ("cisd_delivery_reversal", recent_bull_cisd | recent_bear_cisd,
                 None, None))
            long_mask &= recent_bull_cisd
            short_mask &= recent_bear_cisd

        # ---------------------------------------------------------------------
        # Isolated Filter 2: Rejection-Leg FVG Creation
        # ---------------------------------------------------------------------
        if use_rejection_fvg_filter and (long_mask | short_mask).any():
            fvg_df = detect_fvg(df, require_candle_direction=True)
            recent_bull_fvg = (fvg_df["fvg_type"] == 1).rolling(3, min_periods=1).max().astype(bool)
            recent_bear_fvg = (fvg_df["fvg_type"] == -1).rolling(3, min_periods=1).max().astype(bool)
            applied_filters.append(
                ("rejection_fvg_present", recent_bull_fvg | recent_bear_fvg,
                 None, None))
            long_mask &= recent_bull_fvg
            short_mask &= recent_bear_fvg

        # ---------------------------------------------------------------------
        # Isolated Filter 3: Impulse Exhaustion (KER <= threshold at reversal)
        # ---------------------------------------------------------------------
        if use_exhaustion_ker_filter and (long_mask | short_mask).any():
            ker_df = compute_kaufman_efficiency(df, period=5)
            # Exhaustion means prior runaway momentum has decelerated
            is_exhausted = ker_df["ker_5"] <= ker_exhaustion_max
            applied_filters.append(
                ("impulse_exhaustion", is_exhausted,
                 ker_df["ker_5"], ker_exhaustion_max))
            long_mask &= is_exhausted
            short_mask &= is_exhausted

        # ---------------------------------------------------------------------
        # Isolated Filter 4: Barbwire Anti-Chop (Bar Overlap <= threshold)
        # ---------------------------------------------------------------------
        if use_barbwire_filter and (long_mask | short_mask).any():
            overlap_df = compute_bar_overlap(df, window=3, threshold=max_bar_overlap / 100.0)
            not_barbwire = ~overlap_df["is_barbwire_overlap"]
            applied_filters.append(("not_barbwire", not_barbwire, None, None))
            long_mask &= not_barbwire
            short_mask &= not_barbwire

        df["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        df.loc[long_mask, "direction"] = "long"
        df.loc[short_mask, "direction"] = "short"

        combined = df.dropna(subset=["direction"]).copy()
        first_sigs = (combined.groupby(combined.index.normalize()).head(1).copy()
                      if not combined.empty else combined)
        is_first = pd.Series(False, index=df.index)
        if len(first_sigs):
            is_first.loc[first_sigs.index] = True

        # Decision log (section 5.5). TRIGGER = the sweep+reclaim bar; the
        # gates are the window, the applied optional filters, and
        # first_of_day. The sweep depth is a MEASURE (it cannot fail on a
        # bar that triggered by sweeping).
        rec = (
            GateRecorder(df.index, run_id="", strategy="failed_auction")
            .trigger(base_long, "long")
            .trigger(base_short, "short")
            .gate("intraday_window", intraday_mask)
        )
        for gname, gmask, gval, gthr in applied_filters:
            rec = rec.gate(gname, gmask, value=gval, threshold=gthr)
        rec = rec.gate("first_signal_of_day", is_first)
        sweep_depth = ((df["prior_low"] - df["low"]).clip(lower=0)
                       + (df["high"] - df["prior_high"]).clip(lower=0))
        rec = rec.measure("sweep_depth_pts", sweep_depth)
        self.last_decisions = rec.to_frame(signal_prefix="fa_")

        if combined.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        combined["date"] = combined.index.normalize()
        first_sigs = combined.groupby("date").head(1).copy()

        first_sigs["signal_time"] = first_sigs.index
        first_sigs["entry_price"] = first_sigs["close"]
        first_sigs["model_name"] = "failed_auction"

        stop_long = np.minimum(first_sigs["low"], first_sigs["prior_low"]) - (first_sigs["atr"] * sl_atr_mult)
        stop_short = np.maximum(first_sigs["high"], first_sigs["prior_high"]) + (first_sigs["atr"] * sl_atr_mult)
        first_sigs["stop_price"] = np.where(first_sigs["direction"] == "long", stop_long, stop_short)

        risk = (first_sigs["entry_price"] - first_sigs["stop_price"]).abs()
        first_sigs["risk_pts"] = risk
        first_sigs["target1_price"] = np.where(
            first_sigs["direction"] == "long",
            first_sigs["entry_price"] + (risk * tp_r_mult),
            first_sigs["entry_price"] - (risk * tp_r_mult),
        )

        return first_sigs[self.OUTPUT_COLUMNS].dropna().reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "sl_atr_mult": [0.4, 0.8, 1.2],
            "tp_r_mult": [1.2, 2.0, 3.0],
            "use_cisd_trigger": [True, False],
            "use_rejection_fvg_filter": [True, False],
            "use_exhaustion_ker_filter": [True, False],
            "use_barbwire_filter": [True, False],
        }
