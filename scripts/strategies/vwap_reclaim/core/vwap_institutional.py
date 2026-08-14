"""
Institutional VWAP Strategy Engine (ADR-017 / ADR-020 compliant).
==================================================================
Multi-Timeframe Fusion (5m/15m Trend & Structure + 1m/3m Trigger) with ICT Confluences:
1. Model 'retest': Dynamic Trend Retest (5m ADX >= 18, 5m Price > 50 SMA, 1m VWAP Dip & Bounce)
2. Model 'fade': Band Fade Mean Reversion (5m ADX < 22, 1m +-2SD Band Extreme Reversion)
3. Model 'sweep_reclaim': Liquidity Sweep + CISD + VWAP Reclaim
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import time
from typing import Any, Dict, Optional

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.data.resampler import resample_ohlcv, add_resampled_columns
from scripts.libs_py.ict_engine import detect_swings, detect_cisd
from scripts.libs_py.features.orb_bias import compute_orb_bias
from scripts.libs_py.features.quarterly_cycles import compute_quarterly_cycles


class VWAPInstitutionalStrategy:
    """Institutional Multi-Timeframe VWAP & ICT Confluence Strategy."""

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
        self.strategy_name = "Institutional VWAP Suite"

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "volume" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        # ── Parameter Extraction ──
        model_mode = p.get("model_mode", "all")  # 'retest', 'fade', 'sweep_reclaim', 'all'
        atr_period = int(p.get("atr_period", 14))
        sl_atr_mult = float(p.get("sl_atr_mult", 1.8))
        tp1_r_mult = float(p.get("tp1_r_mult", 1.0))
        tp2_r_mult = float(p.get("tp2_r_mult", 2.0))
        min_retest_adx = float(p.get("min_retest_adx", 18.0))
        max_fade_adx = float(p.get("max_fade_adx", 22.0))
        filter_lunch = bool(p.get("filter_lunch", True))
        use_orb_bias = bool(p.get("use_orb_bias", False))
        use_quarterly_cycles = bool(p.get("use_quarterly_cycles", False))
        max_trades_day = int(p.get("max_trades_day", 2))

        # ── Compute Optional Confluence Feature Modules ──
        if use_orb_bias:
            df = compute_orb_bias(df)
        if use_quarterly_cycles:
            df = compute_quarterly_cycles(df)

        # ── 1. Calculate 1m Base VWAP & Standard Deviation Bands ──
        date_key = df.index.normalize()
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"].clip(lower=0)

        cum_pv = (typical_price * vol).groupby(date_key).cumsum()
        cum_vol = vol.groupby(date_key).cumsum().replace(0, np.nan)
        df["vwap"] = cum_pv / cum_vol

        cum_p2v = ((typical_price ** 2) * vol).groupby(date_key).cumsum()
        variance = np.maximum(0.0, (cum_p2v / cum_vol) - (df["vwap"] ** 2))
        df["vwap_sd"] = np.sqrt(variance)
        df["upper_2sd"] = df["vwap"] + 2.0 * df["vwap_sd"]
        df["lower_2sd"] = df["vwap"] - 2.0 * df["vwap_sd"]

        # 1m ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=atr_period, min_periods=atr_period).mean()

        # ── 2. Multi-Timeframe Fusion (5m Trend & ADX) ──
        # Resample to 5m and compute 5m ADX & 5m SMA50
        df_5m = resample_ohlcv(df, "5min")
        if not df_5m.empty:
            df_5m["sma50"] = df_5m["close"].rolling(50, min_periods=20).mean()
            
            # 5m DMI / ADX
            up_m = df_5m["high"] - df_5m["high"].shift(1)
            dn_m = df_5m["low"].shift(1) - df_5m["low"]
            plus_dm = np.where((up_m > dn_m) & (up_m > 0), up_m, 0.0)
            minus_dm = np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0.0)
            
            tr_5m_hl = df_5m["high"] - df_5m["low"]
            tr_5m_hc = (df_5m["high"] - df_5m["close"].shift(1)).abs()
            tr_5m_lc = (df_5m["low"] - df_5m["close"].shift(1)).abs()
            tr_5m = pd.concat([tr_5m_hl, tr_5m_hc, tr_5m_lc], axis=1).max(axis=1)
            tr_5m_smooth = tr_5m.rolling(14, min_periods=14).mean()
            
            plus_di = 100 * pd.Series(plus_dm, index=df_5m.index).rolling(14, min_periods=14).mean() / tr_5m_smooth
            minus_di = 100 * pd.Series(minus_dm, index=df_5m.index).rolling(14, min_periods=14).mean() / tr_5m_smooth
            dx_5m = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
            df_5m["adx"] = dx_5m.rolling(14, min_periods=14).mean()

            # Merge 5m context back onto 1m timeline without lookahead
            df_5m_slim = df_5m[["sma50", "adx"]].rename(columns={"sma50": "5m_sma50", "adx": "5m_adx"})
            df = pd.merge_asof(df, df_5m_slim, left_index=True, right_index=True, direction="backward")
        else:
            df["5m_sma50"] = df["close"].rolling(50).mean()
            df["5m_adx"] = 20.0

        # Fill potential NaNs defensively
        df["5m_sma50"] = df["5m_sma50"].ffill().bfill()
        df["5m_adx"] = df["5m_adx"].ffill().fillna(20.0)

        # ── 3. ICT Swings & CISD ──
        swings = detect_swings(df, swing_length=5)
        cisd = detect_cisd(df, swings)
        df["cisd"] = cisd["cisd"]

        # ── 4. Candle & Swing Geometry ──
        bar_range = (df["high"] - df["low"]).replace(0, np.nan)
        df["lower_wick_pct"] = (df[["open", "close"]].min(axis=1) - df["low"]) / bar_range * 100.0
        df["upper_wick_pct"] = (df["high"] - df[["open", "close"]].max(axis=1)) / bar_range * 100.0

        # 2-bar swing extrema for structural stops
        df["swing_low2"] = df["low"].rolling(2).min()
        df["swing_high2"] = df["high"].rolling(2).max()

        # ── 5. Session Time Windows ──
        t = df.index.time
        mask_ny_am = (t >= time(9, 45)) & (t <= time(11, 30))
        mask_ny_pm = (t >= time(13, 30)) & (t <= time(15, 30))
        
        if filter_lunch:
            in_session = mask_ny_am | mask_ny_pm
        else:
            in_session = (t >= time(9, 45)) & (t <= time(15, 30))

        if use_quarterly_cycles and "is_quarterly_expansion_window" in df.columns:
            in_session = in_session & df["is_quarterly_expansion_window"]

        # ── 6. Signal Model Generation ──
        # Model 1: Dynamic Retest (Trend Pullback)
        is_bull_trend = (df["5m_adx"] >= min_retest_adx) & (df["close"] > df["5m_sma50"]) & (df["vwap"] > df["5m_sma50"])
        is_bear_trend = (df["5m_adx"] >= min_retest_adx) & (df["close"] < df["5m_sma50"]) & (df["vwap"] < df["5m_sma50"])

        retest_l_raw = is_bull_trend & (df["low"] <= df["vwap"]) & (df["close"] > df["vwap"]) & ((df["close"] - df["low"]) >= bar_range * 0.4)
        retest_s_raw = is_bear_trend & (df["high"] >= df["vwap"]) & (df["close"] < df["vwap"]) & ((df["high"] - df["close"]) >= bar_range * 0.4)

        retest_long = in_session & retest_l_raw.shift(1).fillna(False) & (df["high"] > df["high"].shift(1))
        retest_short = in_session & retest_s_raw.shift(1).fillna(False) & (df["low"] < df["low"].shift(1))

        # Model 2: Band Fade (Mean Reversion at +-2SD)
        fade_long = in_session & (df["5m_adx"] < max_fade_adx) & (df["low"].rolling(3).min() <= df["lower_2sd"]) & (df["close"] > df["lower_2sd"]) & ((df["lower_wick_pct"] >= 20) | (df["close"] > df["open"]))
        fade_short = in_session & (df["5m_adx"] < max_fade_adx) & (df["high"].rolling(3).max() >= df["upper_2sd"]) & (df["close"] < df["upper_2sd"]) & ((df["upper_wick_pct"] >= 20) | (df["close"] < df["open"]))

        # Model 3: ICT Liquidity Sweep Reclaim (CISD Shift at VWAP)
        sweep_long = in_session & (df["cisd"] == 1) & (df["close"] > df["vwap"]) & (df["low"] <= df["vwap"])
        sweep_short = in_session & (df["cisd"] == -1) & (df["close"] < df["vwap"]) & (df["high"] >= df["vwap"])

        # Apply 09:30 1m ORB Directional Bias Gate
        if use_orb_bias and "orb_1m_bias" in df.columns:
            retest_long = retest_long & (df["orb_1m_bias"] == 1)
            retest_short = retest_short & (df["orb_1m_bias"] == -1)
            sweep_long = sweep_long & (df["orb_1m_bias"] == 1)
            sweep_short = sweep_short & (df["orb_1m_bias"] == -1)

        # ── 7. Dispatch Selected Models ──
        sig_records = []

        if model_mode in ["retest", "all"]:
            sig_records.append((retest_long, "long", "retest"))
            sig_records.append((retest_short, "short", "retest"))

        if model_mode in ["fade", "all"]:
            sig_records.append((fade_long, "long", "fade"))
            sig_records.append((fade_short, "short", "fade"))

        if model_mode in ["sweep_reclaim", "all"]:
            sig_records.append((sweep_long, "long", "sweep_reclaim"))
            sig_records.append((sweep_short, "short", "sweep_reclaim"))

        df_signals = []
        for mask, direction, m_name in sig_records:
            sub = df[mask].copy()
            if not sub.empty:
                sub["direction"] = direction
                sub["model_name"] = m_name
                df_signals.append(sub)

        if not df_signals:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        combined = pd.concat(df_signals).sort_index()
        # Drop duplicates on the same bar prioritizing retest > sweep > fade
        combined = combined[~combined.index.duplicated(keep="first")]

        # Group by date and limit to max_trades_day
        combined["date"] = combined.index.normalize()
        sigs = combined.groupby("date").head(max_trades_day).copy()

        sigs["signal_time"] = sigs.index
        sigs["entry_price"] = sigs["close"]

        # ── 8. Structural Stop Loss & Targets Calculation ──
        swing_dist_long = sigs["entry_price"] - sigs["swing_low2"].shift(1).fillna(sigs["low"])
        swing_dist_short = sigs["swing_high2"].shift(1).fillna(sigs["high"]) - sigs["entry_price"]

        risk_long = np.maximum(sigs["atr"] * sl_atr_mult, swing_dist_long)
        risk_short = np.maximum(sigs["atr"] * sl_atr_mult, swing_dist_short)
        risk = np.where(sigs["direction"] == "long", risk_long, risk_short)
        sigs["risk_pts"] = risk

        sigs["stop_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] - risk,
            sigs["entry_price"] + risk,
        )
        
        # TP1 (Cover the Queen / 1R)
        sigs["target1_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] + (risk * tp1_r_mult),
            sigs["entry_price"] - (risk * tp1_r_mult),
        )
        
        # TP2 (Runner Target / 2R)
        sigs["target2_price"] = np.where(
            sigs["direction"] == "long",
            sigs["entry_price"] + (risk * tp2_r_mult),
            sigs["entry_price"] - (risk * tp2_r_mult),
        )

        return sigs[self.OUTPUT_COLUMNS].dropna().reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "sl_atr_mult": ("float", 1.4, 2.4),
            "tp1_r_mult": ("float", 0.8, 1.4),
            "tp2_r_mult": ("float", 1.8, 3.5),
            "min_retest_adx": ("float", 15.0, 25.0),
            "max_fade_adx": ("float", 18.0, 26.0),
            "filter_lunch": [True, False],
        }
