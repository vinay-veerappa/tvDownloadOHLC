import numpy as np
import pandas as pd
from datetime import time
from typing import Any, Dict, Optional


class EMAPullbackStrategy:
    """ADR-017 vectorized EMA pullback hunter."""

    OUTPUT_COLUMNS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

    def __init__(self, ticker: str = "NQ1"):
        self.ticker = ticker

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        ema_len = int(p.get("ema_len", 50))
        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 1.4))
        tp_r_mult = float(p.get("tp_r_mult", 1.8))
        min_slope = float(p.get("min_slope", 0.0))

        df["ema"] = df["close"].ewm(span=ema_len, adjust=False).mean()
        df["ema_slope"] = df["ema"].diff()

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean()

        intraday_mask = (df.index.time >= time(9, 40)) & (df.index.time <= time(12, 30))

        uptrend = (df["close"] > df["ema"]) & (df["ema_slope"] >= min_slope)
        downtrend = (df["close"] < df["ema"]) & (df["ema_slope"] <= -min_slope)

        long_mask = intraday_mask & uptrend & (df["low"] <= df["ema"]) & (df["close"] >= df["ema"])
        short_mask = intraday_mask & downtrend & (df["high"] >= df["ema"]) & (df["close"] <= df["ema"])

        df["direction"] = pd.Series(pd.NA, index=df.index, dtype="object")
        df.loc[long_mask, "direction"] = "long"
        df.loc[short_mask, "direction"] = "short"

        # ---------------------------------------------------------------------
        # Layer 1: Chop Filter (Institutional Context)
        # ---------------------------------------------------------------------
        if p.get("chop_filter", False):
            # Optimization: only compute for points near potential signals
            potential_mask = long_mask | short_mask
            if potential_mask.any():
                from scripts.libs_py.indicators.market_regime import compute_chop_score
                
                # Chop score looks back 14 bars by default
                results = compute_chop_score(df, lookback=14)
                df['chop_score_1'] = results['chop_score']
                df['chop_score_0'] = df['chop_score_1'].shift(1)
                
                # Veto if BOTH signal bar and prior bar are below threshold (2.0)
                # This ensures we aren't entering into deep compression
                veto_mask = (df['chop_score_1'] < 2.0) & (df['chop_score_0'] < 2.0)
                
                df.loc[veto_mask & potential_mask, "direction"] = pd.NA
                
                # Log vetoes if in debug/detailed mode
                vetoes = (veto_mask & potential_mask).sum()
                if vetoes > 0:
                    print(f"[EMA PULLBACK] Vetoed {vetoes} signals due to Chop Filter (< 2.0)")

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
            "ema_len": ("int", 20, 100),
            "sl_atr_mult": ("float", 0.8, 2.5),
            "tp_r_mult": ("float", 1.0, 3.5),
            "min_slope": ("float", 0.0, 2.0),
        }
