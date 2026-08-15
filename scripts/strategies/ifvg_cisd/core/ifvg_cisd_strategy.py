"""
Multi-Timeframe Inversion FVG (IFVG) + CISD Strategy Engine.
============================================================
Combines Higher-Timeframe (5m/15m) institutional displacement, Volume Imbalance (VI)
boundary mergers, and Delivery State shifts (CISD) with 1-minute execution:
1. HTF CISD confirms state of delivery flip (Neo pullback & expansion arming).
2. HTF Inversion Fair Value Gap (IFVG + VI) confirms orderflow absorption / trapped liquidity.
3. 1m execution timeline with ATR risk brackets and Cover The Queen trade management.
"""
from __future__ import annotations

import sys
from datetime import time
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

# Dynamic path bootstrap
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.price_action.volatility_leading import (
    compute_kaufman_efficiency,
    compute_bar_overlap,
)


class IFVGCISDStrategy:
    """Multi-Timeframe Inversion FVG (IFVG) & CISD Strategy."""

    OUTPUT_COLUMNS = [
        "signal_time",
        "direction",
        "entry_price",
        "stop_price",
        "target1_price",
        "target2_price",
        "model_name",
        "risk_pts",
    ]

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "5m IFVG CISD Distribution"

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        resample_tf = p.get("resample_tf", "5min")
        max_trades_per_day = p.get("max_trades_per_day", 1)
        r_mult_tp1 = p.get("r_mult_tp1", 1.0)
        r_mult_tp2 = p.get("r_mult_tp2", 2.5)
        atr_risk_mult = p.get("atr_risk_mult", 1.8)

        # Strategy Configuration
        filter_lunch = bool(p.get("filter_lunch", True))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.45))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))
        include_vi = bool(p.get("include_vi", True))
        strict_ifvg_only = bool(p.get("strict_ifvg_only", True))

        # 1. Compute HTF CISD & Inversion FVG (with Volume Imbalance extensions)
        df_htf = resample_ohlcv(df, resample_tf)
        cisd_htf = compute_cisd(df_htf)
        ifvg_htf = compute_ifvg(df_htf, include_vi=include_vi)
        fvg_htf = compute_fvg(df_htf, include_vi=include_vi)

        sig_htf = pd.DataFrame(index=df_htf.index)
        sig_htf["cisd_htf"] = cisd_htf["cisd_state"]
        sig_htf["ifvg_htf"] = ifvg_htf["ifvg_event"]
        sig_htf["ifvg_state"] = ifvg_htf["ifvg_state"]
        sig_htf["fvg_htf"] = fvg_htf["fvg_event"]

        if strict_ifvg_only:
            sig_htf["htf_long"] = (sig_htf["cisd_htf"] == 1) & (sig_htf["ifvg_htf"] == 1)
            sig_htf["htf_short"] = (sig_htf["cisd_htf"] == -1) & (sig_htf["ifvg_htf"] == -1)
        else:
            recent_cisd_bull = (sig_htf["cisd_htf"] == 1).rolling(3, min_periods=1).max().astype(bool)
            recent_cisd_bear = (sig_htf["cisd_htf"] == -1).rolling(3, min_periods=1).max().astype(bool)
            sig_htf["htf_long"] = recent_cisd_bull & ((sig_htf["ifvg_htf"] == 1) | (sig_htf["fvg_htf"] == 1))
            sig_htf["htf_short"] = recent_cisd_bear & ((sig_htf["ifvg_htf"] == -1) | (sig_htf["fvg_htf"] == -1))

        # 2. Merge causally onto 1m execution timeline (no lookahead)
        df = pd.merge_asof(
            df,
            sig_htf[["htf_long", "htf_short"]],
            left_index=True,
            right_index=True,
            direction="backward",
        )
        df["htf_long"] = df["htf_long"].fillna(False)
        df["htf_short"] = df["htf_short"].fillna(False)

        # 3. Execution ATR and Swings
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14, min_periods=14).mean().bfill()
        df["swing_low2"] = df["low"].rolling(2).min()
        df["swing_high2"] = df["high"].rolling(2).max()

        t = df.index.time
        in_rth = (t >= time(9, 45)) & (t <= time(15, 30))
        time_mask = in_rth

        if filter_lunch:
            not_lunch = (t < time(11, 30)) | (t > time(13, 30))
            time_mask = time_mask & not_lunch

        sig_mask_long = time_mask & df["htf_long"]
        sig_mask_short = time_mask & df["htf_short"]

        # Isolated Filter 1: Kaufman Efficiency Ratio on Execution Timeline
        if use_ker_filter:
            ker_series = compute_kaufman_efficiency(df, length=10)
            sig_mask_long = sig_mask_long & (ker_series >= ker_min)
            sig_mask_short = sig_mask_short & (ker_series >= ker_min)

        # Isolated Filter 2: Barbwire Anti-Chop on Execution Timeline
        if use_barbwire_filter:
            overlap_series = compute_bar_overlap(df, length=5)
            sig_mask_long = sig_mask_long & (overlap_series <= max_bar_overlap)
            sig_mask_short = sig_mask_short & (overlap_series <= max_bar_overlap)

        # 4. Signal Extraction & Daily Trade Throttling
        trades: list[dict[str, Any]] = []
        last_date = None
        daily_trades = 0

        for idx, row in df[sig_mask_long | sig_mask_short].iterrows():
            current_date = idx.date()
            if current_date != last_date:
                last_date = current_date
                daily_trades = 0

            if daily_trades >= max_trades_per_day:
                continue

            entry_price = float(row["close"])
            raw_risk = float(row["atr"]) * atr_risk_mult
            risk = max(10.0, min(50.0, raw_risk))

            if row["htf_long"]:
                direction = "LONG"
                stop_price = entry_price - risk
                target1_price = entry_price + (risk * r_mult_tp1)
                target2_price = entry_price + (risk * r_mult_tp2)
            else:
                direction = "SHORT"
                stop_price = entry_price + risk
                target1_price = entry_price - (risk * r_mult_tp1)
                target2_price = entry_price - (risk * r_mult_tp2)

            trades.append(
                {
                    "signal_time": idx,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target1_price": target1_price,
                    "target2_price": target2_price,
                    "model_name": self.strategy_name,
                    "risk_pts": risk,
                }
            )
            daily_trades += 1

        return pd.DataFrame(trades, columns=self.OUTPUT_COLUMNS)
