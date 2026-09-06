import numpy as np
import pandas as pd
from datetime import time
from typing import Any, Dict, Optional

from scripts.trading_framework.reporting.decision_log import GateRecorder


class SixAMReversalStrategy:
    """ADR-017 vectorized 6AM reversal hunter around prior-day range sweeps."""

    OUTPUT_COLUMNS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker
        # Section 5.5: the criteria this hunter evaluates, for the decision
        # log. None means not instrumented; set by hunt().
        self.last_decisions: Optional[pd.DataFrame] = None

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 0.9))
        tp_r_mult = float(p.get("tp_r_mult", 1.5))
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

        window_mask = (df.index.time >= time(6, 0)) & (df.index.time <= time(7, 0))

        long_mask = (
            window_mask
            & (df["low"] < (df["prior_low"] * (1.0 - break_buffer)))
            & (df["close"] > df["prior_low"])
        )
        short_mask = (
            window_mask
            & (df["high"] > (df["prior_high"] * (1.0 + break_buffer)))
            & (df["close"] < df["prior_high"])
        )

        df["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        df.loc[long_mask, "direction"] = "long"
        df.loc[short_mask, "direction"] = "short"

        combined = df.dropna(subset=["direction"]).copy()
        if combined.empty:
            # Still record: the triggers and gates exist even when nothing
            # survives them all, and "no entries" plus an empty log would be
            # indistinguishable from "not instrumented".
            self.last_decisions = self._record(
                df, long_mask, short_mask, window_mask,
                pd.Series(False, index=df.index))
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        combined["date"] = combined.index.normalize()
        first_sigs = combined.groupby("date").head(1).copy()

        is_first = pd.Series(False, index=df.index)
        is_first.loc[first_sigs.index] = True

        # 4b. Decision log (section 5.5). Trigger = the sweep+reclaim bar;
        # the gates below are everything that can still block it. The window
        # and the reclaim are the strategy's actual criteria -- the sweep
        # itself is the trigger, not a gate.
        self.last_decisions = self._record(df, long_mask, short_mask,
                                            window_mask, is_first)

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

    def _record(self, df, long_mask, short_mask, window_mask, is_first):
        sweep = ((df["low"] < df["prior_low"]) | (df["high"] > df["prior_high"]))
        depth = pd.Series(np.nan, index=df.index)
        long_depth = (df["prior_low"] - df["low"]).clip(lower=0)
        short_depth = (df["high"] - df["prior_high"]).clip(lower=0)
        depth = long_depth + short_depth
        return (
            GateRecorder(df.index, run_id="", strategy="six_am_reversal")
            .trigger(long_mask, "long")
            .trigger(short_mask, "short")
            # A magnitude: how deep the sweep went beyond the prior-day level.
            # On a bar that triggered because of the sweep, the sweep cannot
            # fail -- so it is a measure, not a gate.
            .measure("sweep_depth_pts", depth)
            .gate("first_signal_of_day", is_first)
            .to_frame(signal_prefix="sar_")
        )

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "sl_atr_mult": ("float", 0.4, 1.8),
            "tp_r_mult": ("float", 1.0, 3.0),
            "break_buffer": ("float", 0.0, 0.002),
        }
