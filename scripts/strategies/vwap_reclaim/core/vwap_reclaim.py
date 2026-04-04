import numpy as np
import pandas as pd
from datetime import time
from typing import Any, Dict, Optional


class VWAPReclaimStrategy:
    """ADR-017 vectorized VWAP reclaim hunter."""

    OUTPUT_COLUMNS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "volume" not in df.columns:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 1.2))
        tp_r_mult = float(p.get("tp_r_mult", 1.8))
        rel_vol_min = float(p.get("rel_vol_min", 1.0))
        min_abs_volume = float(p.get("min_abs_volume", 1.0))

        date_key = df.index.normalize()
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].clip(lower=0)

        cum_pv = (typical_price * vol).groupby(date_key).cumsum()
        cum_vol = vol.groupby(date_key).cumsum().replace(0, np.nan)
        df["vwap"] = cum_pv / cum_vol

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean()

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

        risk = first_sigs["atr"] * sl_atr_mult
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
            "sl_atr_mult": ("float", 0.8, 2.2),
            "tp_r_mult": ("float", 1.0, 3.0),
            "rel_vol_min": ("float", 0.8, 2.0),
            "min_abs_volume": ("float", 1.0, 5000.0),
        }
