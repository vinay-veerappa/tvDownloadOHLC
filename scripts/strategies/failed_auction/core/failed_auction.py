import numpy as np
import pandas as pd
from datetime import time
from typing import Any, Dict, Optional


class FailedAuctionStrategy:
    """ADR-017 vectorized failed auction hunter using prior-day extremes."""

    OUTPUT_COLUMNS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 0.8))
        tp_r_mult = float(p.get("tp_r_mult", 2.0))
        break_buffer = float(p.get("break_buffer", 0.0))

        date_key = df.index.normalize()
        daily = df.groupby(date_key).agg(day_high=("high", "max"), day_low=("low", "min"))
        prior_day = daily.shift(1)

        df["prior_high"] = date_key.map(prior_day["day_high"])
        df["prior_low"] = date_key.map(prior_day["day_low"])

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean()

        intraday_mask = (df.index.time >= time(9, 35)) & (df.index.time <= time(14, 30))

        sweep_low = df["low"] < (df["prior_low"] * (1.0 - break_buffer))
        reclaim_low = df["close"] > df["prior_low"]
        sweep_high = df["high"] > (df["prior_high"] * (1.0 + break_buffer))
        reclaim_high = df["close"] < df["prior_high"]

        long_mask = intraday_mask & sweep_low & reclaim_low
        short_mask = intraday_mask & sweep_high & reclaim_high

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

        stop_long = np.minimum(first_sigs["low"], first_sigs["prior_low"]) - (first_sigs["atr"] * sl_atr_mult)
        stop_short = np.maximum(first_sigs["high"], first_sigs["prior_high"]) + (first_sigs["atr"] * sl_atr_mult)
        first_sigs["stop_price"] = np.where(first_sigs["direction"] == "long", stop_long, stop_short)

        risk = (first_sigs["entry_price"] - first_sigs["stop_price"]).abs()
        first_sigs["target1_price"] = np.where(
            first_sigs["direction"] == "long",
            first_sigs["entry_price"] + (risk * tp_r_mult),
            first_sigs["entry_price"] - (risk * tp_r_mult),
        )

        return first_sigs[self.OUTPUT_COLUMNS].dropna().reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "sl_atr_mult": ("float", 0.4, 1.8),
            "tp_r_mult": ("float", 1.0, 4.0),
            "break_buffer": ("float", 0.0, 0.002),
        }
