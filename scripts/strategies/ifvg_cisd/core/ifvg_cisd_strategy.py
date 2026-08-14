"""
5-Minute MTF Inversion FVG (IFVG) & CISD Distribution/Accumulation Strategy.
=============================================================================
Combines 5-minute institutional displacement and orderflow failure with 1-minute precision execution:
1. 5m Change in State of Delivery (CISD) confirms delivery bias flip.
2. 5m Inversion Fair Value Gap (IFVG) confirms orderflow absorption / trapped participants.
3. Surgical execution with Cover the Queen scale-outs (1.0R TP1 / 2.5R TP2).
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

from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.ict_engine import detect_swings, detect_fvg, detect_inversion_fvg, detect_cisd


class IFVGCISDStrategy:
    """5-Minute MTF Inversion FVG (IFVG) & CISD Strategy."""

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
        filter_lunch = p.get("filter_lunch", True)

        # 1. Resample to 5m HTF
        df_htf = resample_ohlcv(df, resample_tf)
        swings_htf = detect_swings(df_htf, swing_length=5)
        cisd_htf = detect_cisd(df_htf, swings_htf)
        fvg_htf = detect_fvg(df_htf, require_candle_direction=True)
        ifvg_htf = detect_inversion_fvg(df_htf, fvg_htf)

        sig_htf = pd.DataFrame(index=df_htf.index)
        sig_htf["cisd_htf"] = cisd_htf["cisd"]
        sig_htf["ifvg_htf"] = ifvg_htf["ifvg"]
        sig_htf["fvg_htf"] = fvg_htf["fvg_type"]

        recent_cisd_bull = (sig_htf["cisd_htf"] == 1).rolling(3, min_periods=1).max().astype(bool)
        recent_cisd_bear = (sig_htf["cisd_htf"] == -1).rolling(3, min_periods=1).max().astype(bool)

        sig_htf["htf_long"] = recent_cisd_bull & ((sig_htf["ifvg_htf"] == 1) | (sig_htf["fvg_htf"] == 1))
        sig_htf["htf_short"] = recent_cisd_bear & ((sig_htf["ifvg_htf"] == -1) | (sig_htf["fvg_htf"] == -1))

        # 2. Merge causally onto 1m execution timeline
        df = pd.merge_asof(df, sig_htf[["htf_long", "htf_short"]], left_index=True, right_index=True, direction="backward")
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

        sig_df = df.copy()
        sig_df["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        sig_df.loc[sig_mask_long, "direction"] = "long"
        sig_df.loc[sig_mask_short, "direction"] = "short"

        comb = sig_df.dropna(subset=["direction"]).copy()
        if comb.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        comb["date"] = comb.index.normalize()
        sigs = comb.groupby("date").head(max_trades_per_day).copy()
        sigs["signal_time"] = sigs.index
        sigs["entry_price"] = sigs["close"]
        sigs["model_name"] = f"ifvg_cisd_{resample_tf}"

        swing_dist_long = sigs["entry_price"] - sigs["swing_low2"].shift(1).fillna(sigs["low"])
        swing_dist_short = sigs["swing_high2"].shift(1).fillna(sigs["high"]) - sigs["entry_price"]
        risk_long = np.maximum(sigs["atr"] * atr_risk_mult, swing_dist_long)
        risk_short = np.maximum(sigs["atr"] * atr_risk_mult, swing_dist_short)
        risk = np.where(sigs["direction"] == "long", risk_long, risk_short)
        sigs["risk_pts"] = risk

        sigs["stop_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] - risk,
            sigs["entry_price"] + risk,
        )
        sigs["target1_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] + (risk * r_mult_tp1),
            sigs["entry_price"] - (risk * r_mult_tp1),
        )
        sigs["target2_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] + (risk * r_mult_tp2),
            sigs["entry_price"] - (risk * r_mult_tp2),
        )

        return sigs[self.OUTPUT_COLUMNS].dropna().reset_index(drop=True)

    def get_param_grid(self) -> Dict[str, Any]:
        return {
            "resample_tf": ["3min", "5min"],
            "max_trades_per_day": [1, 2],
            "r_mult_tp1": [1.0, 1.2],
            "r_mult_tp2": [2.0, 2.5, 3.0],
            "atr_risk_mult": [1.5, 1.8, 2.0],
            "filter_lunch": [True, False],
        }
