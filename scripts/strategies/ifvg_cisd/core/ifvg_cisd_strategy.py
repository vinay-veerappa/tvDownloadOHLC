"""
Multi-Timeframe Inversion FVG (IFVG) + CISD Strategy Engine.
============================================================
Combines Higher-Timeframe (5m/15m) institutional displacement, Volume Imbalance (VI)
boundary mergers, and Delivery State shifts (CISD) with 1-minute execution.

Three variants mirror the NinjaTrader C# ICTFVGCISDBot:
1. baseline   : HTF CISD regime + iFVG, ATR risk bracket (original behavior).
2. variant1   : CISD trigger + (BPR OR (iFVG AND >=1 FVG in leg)), stop at CISD origin.
3. variant2   : CISD regime/trigger + 2nd FVG in leg, no IFVG required, stop at CISD origin.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
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
from scripts.libs_py.bpr import compute_bpr
from scripts.libs_py.data.resampler import resample_ohlcv
from scripts.libs_py.price_action.volatility_leading import (
    compute_kaufman_efficiency,
    compute_bar_overlap,
)


@dataclass
class _LegState:
    regime: int = 0
    origin_low: float = np.nan
    origin_high: float = np.nan
    cisd_level: float = np.nan
    has_bpr: bool = False
    has_ifvg: bool = False
    bull_fvg_count: int = 0
    bear_fvg_count: int = 0
    v2_triggered: bool = False


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
        tick_size = float(p.get("tick_size", 0.25))

        variant = str(p.get("variant", "baseline")).lower()
        filter_lunch = bool(p.get("filter_lunch", True))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.45))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))
        include_vi = bool(p.get("include_vi", True))
        strict_ifvg_only = bool(p.get("strict_ifvg_only", True))

        # 1. Compute HTF CISD / FVG / iFVG / BPR
        df_htf = resample_ohlcv(df, resample_tf)
        cisd_htf = compute_cisd(df_htf)
        ifvg_htf = compute_ifvg(df_htf, include_vi=include_vi)
        fvg_htf = compute_fvg(df_htf, include_vi=include_vi)

        if variant in ("baseline", "strict_ifvg", "loose"):
            return self._hunt_baseline(
                df,
                df_htf,
                cisd_htf,
                ifvg_htf,
                fvg_htf,
                p,
            )

        bpr_htf = compute_bpr(df_htf, align_to_base=False)
        return self._hunt_csharp_variants(
            df,
            df_htf,
            cisd_htf,
            ifvg_htf,
            fvg_htf,
            bpr_htf,
            variant,
            p,
        )

    # ===================================================================================
    # ORIGINAL BASELINE BEHAVIOR (preserved for existing backtests / optimizers)
    # ===================================================================================
    def _hunt_baseline(
        self,
        df: pd.DataFrame,
        df_htf: pd.DataFrame,
        cisd_htf: pd.DataFrame,
        ifvg_htf: pd.DataFrame,
        fvg_htf: pd.DataFrame,
        p: Dict[str, Any],
    ) -> pd.DataFrame:
        resample_tf = p.get("resample_tf", "5min")
        max_trades_per_day = p.get("max_trades_per_day", 1)
        r_mult_tp1 = p.get("r_mult_tp1", 1.0)
        r_mult_tp2 = p.get("r_mult_tp2", 2.5)
        atr_risk_mult = p.get("atr_risk_mult", 1.8)
        filter_lunch = bool(p.get("filter_lunch", True))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.45))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))
        strict_ifvg_only = bool(p.get("strict_ifvg_only", True))

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

        # Merge causally onto 1m execution timeline (no lookahead)
        df = pd.merge_asof(
            df,
            sig_htf[["htf_long", "htf_short"]],
            left_index=True,
            right_index=True,
            direction="backward",
        )
        df["htf_long"] = df["htf_long"].fillna(False)
        df["htf_short"] = df["htf_short"].fillna(False)

        # Execution ATR and Swings
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

        if use_ker_filter:
            ker_series = compute_kaufman_efficiency(df, length=10)
            sig_mask_long = sig_mask_long & (ker_series >= ker_min)
            sig_mask_short = sig_mask_short & (ker_series >= ker_min)

        if use_barbwire_filter:
            overlap_series = compute_bar_overlap(df, length=5)
            sig_mask_long = sig_mask_long & (overlap_series <= max_bar_overlap)
            sig_mask_short = sig_mask_short & (overlap_series <= max_bar_overlap)

        # Signal Extraction & Daily Trade Throttling
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

    # ===================================================================================
    # C# VARIANTS (variant1 / variant2)
    # ===================================================================================
    def _hunt_csharp_variants(
        self,
        df: pd.DataFrame,
        df_htf: pd.DataFrame,
        cisd_htf: pd.DataFrame,
        ifvg_htf: pd.DataFrame,
        fvg_htf: pd.DataFrame,
        bpr_htf: pd.DataFrame,
        variant: str,
        p: Dict[str, Any],
    ) -> pd.DataFrame:
        max_trades_per_day = p.get("max_trades_per_day", 1)
        r_mult_tp1 = p.get("r_mult_tp1", 1.0)
        r_mult_tp2 = p.get("r_mult_tp2", 2.5)
        tick_size = float(p.get("tick_size", 0.25))
        filter_lunch = bool(p.get("filter_lunch", True))
        write_diag_csv = bool(p.get("write_diag_csv", False))
        diag_csv_path: Optional[Path] = None
        diag_rows: list[dict[str, Any]] = []
        if write_diag_csv:
            diag_csv_path = Path(
                p.get("diag_csv_path") or f"/tmp/ifvg_cisd_py_diag_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            diag_csv_path.parent.mkdir(parents=True, exist_ok=True)

        sig_htf = pd.DataFrame(index=df_htf.index)
        sig_htf["cisd_event"] = cisd_htf["cisd_event"]
        sig_htf["cisd_state"] = cisd_htf["cisd_state"]
        sig_htf["ifvg_event"] = ifvg_htf["ifvg_event"]
        sig_htf["ifvg_state"] = ifvg_htf["ifvg_state"]
        sig_htf["fvg_event"] = fvg_htf["fvg_event"]
        sig_htf["bpr_event"] = bpr_htf["bpr_event"]

        htf_open = df_htf["open"].values
        htf_high = df_htf["high"].values
        htf_low = df_htf["low"].values
        htf_close = df_htf["close"].values
        n_htf = len(sig_htf)

        signal_rows: list[dict[str, Any]] = []
        leg = _LegState()
        last_signal_date: Optional[Any] = None
        daily_trades = 0
        htf_index = sig_htf.index

        for i in range(n_htf):
            ts = htf_index[i]
            o, h, l, c = htf_open[i], htf_high[i], htf_low[i], htf_close[i]
            cisd_event = int(sig_htf.iloc[i]["cisd_event"])
            cisd_state = int(sig_htf.iloc[i]["cisd_state"])
            fvg_event = int(sig_htf.iloc[i]["fvg_event"])
            ifvg_event = int(sig_htf.iloc[i]["ifvg_event"])
            bpr_event = int(sig_htf.iloc[i]["bpr_event"])

            # Causal 3-bar pivots (for diagnostic parity with C#/Pine)
            is_low_pivot = False
            is_high_pivot = False
            if i >= 2:
                l1, l2 = htf_low[i - 1], htf_low[i - 2]
                h1, h2 = htf_high[i - 1], htf_high[i - 2]
                is_low_pivot = (l1 < l2) and (l1 < l)
                is_high_pivot = (h1 > h2) and (h1 > h)

            if cisd_event == 1:
                leg = _LegState(
                    regime=1,
                    origin_low=htf_low[i - 1] if i > 0 else l,
                    origin_high=np.nan,
                    cisd_level=o,
                    has_bpr=False,
                    has_ifvg=False,
                    bull_fvg_count=0,
                    bear_fvg_count=0,
                    v2_triggered=False,
                )
            elif cisd_event == -1:
                leg = _LegState(
                    regime=-1,
                    origin_low=np.nan,
                    origin_high=htf_high[i - 1] if i > 0 else h,
                    cisd_level=o,
                    has_bpr=False,
                    has_ifvg=False,
                    bull_fvg_count=0,
                    bear_fvg_count=0,
                    v2_triggered=False,
                )
            else:
                leg.regime = cisd_state

            if leg.regime != 0:
                if fvg_event == 1:
                    leg.bull_fvg_count += 1
                elif fvg_event == -1:
                    leg.bear_fvg_count += 1
                if ifvg_event == 1 and leg.regime == 1:
                    leg.has_ifvg = True
                if ifvg_event == -1 and leg.regime == -1:
                    leg.has_ifvg = True
                if bpr_event != 0:
                    leg.has_bpr = True

            direction: Optional[str] = None
            entry_price = np.nan
            stop_price = np.nan
            risk = np.nan

            if variant == "variant1":
                if cisd_event == 1 and (leg.has_bpr or (leg.has_ifvg and leg.bull_fvg_count >= 1)):
                    direction = "LONG"
                    entry_price = leg.cisd_level if not np.isnan(leg.cisd_level) else c
                    stop_price = leg.origin_low - 2 * tick_size if not np.isnan(leg.origin_low) else l - 2 * tick_size
                    risk = max(10.0, min(50.0, entry_price - stop_price))
                    stop_price = entry_price - risk
                elif cisd_event == -1 and (leg.has_bpr or (leg.has_ifvg and leg.bear_fvg_count >= 1)):
                    direction = "SHORT"
                    entry_price = leg.cisd_level if not np.isnan(leg.cisd_level) else c
                    stop_price = leg.origin_high + 2 * tick_size if not np.isnan(leg.origin_high) else h + 2 * tick_size
                    risk = max(10.0, min(50.0, stop_price - entry_price))
                    stop_price = entry_price + risk

            elif variant == "variant2":
                if (leg.regime == 1 or cisd_event == 1) and not leg.v2_triggered and fvg_event == 1 and leg.bull_fvg_count >= 2:
                    direction = "LONG"
                    entry_price = c
                    stop_price = leg.origin_low - 2 * tick_size if not np.isnan(leg.origin_low) else l - 2 * tick_size
                    risk = max(10.0, min(50.0, entry_price - stop_price))
                    stop_price = entry_price - risk
                    leg.v2_triggered = True
                elif (leg.regime == -1 or cisd_event == -1) and not leg.v2_triggered and fvg_event == -1 and leg.bear_fvg_count >= 2:
                    direction = "SHORT"
                    entry_price = c
                    stop_price = leg.origin_high + 2 * tick_size if not np.isnan(leg.origin_high) else h + 2 * tick_size
                    risk = max(10.0, min(50.0, stop_price - entry_price))
                    stop_price = entry_price + risk
                    leg.v2_triggered = True

            if write_diag_csv:
                # Infer bar open time from the HTF index delta so close vs open aligns with C#/TV
                bar_delta = pd.Timedelta(minutes=1)
                if i > 0:
                    bar_delta = ts - htf_index[i - 1]
                bar_open = ts - bar_delta
                # CandlePersonality: 1=bull, -1=bear, 0=doji
                cp = 1 if c > o else -1 if c < o else 0
                diag_rows.append({
                    "BarCloseTime": ts,
                    "BarOpenTime": bar_open,
                    "Open": o,
                    "High": h,
                    "Low": l,
                    "Close": c,
                    "CandlePersonality": cp,
                    "Vibes": cisd_state,  # cisd_state is the running regime (+1/-1/0)
                    "BagholderEntry": leg.cisd_level if not np.isnan(leg.cisd_level) else np.nan,
                    "PainThreshold": np.nan,  # not tracked in this strategy layer
                    "BullCisdTrigger": int(cisd_event == 1),
                    "BearCisdTrigger": int(cisd_event == -1),
                    "BullFvgCount": leg.bull_fvg_count,
                    "BearFvgCount": leg.bear_fvg_count,
                    "IsBullFvg": int(fvg_event == 1),
                    "IsBearFvg": int(fvg_event == -1),
                    "IsBullIfvg": int(ifvg_event == 1),
                    "IsBearIfvg": int(ifvg_event == -1),
                    "IsBullBpr": int(bpr_event == 1),
                    "IsBearBpr": int(bpr_event == -1),
                    "SignalLong": int(direction == "LONG"),
                    "SignalShort": int(direction == "SHORT"),
                    "CanEnter": int(direction is not None),
                    "InRth": int(time(9, 45) <= ts.time() <= time(15, 30)),
                    "HasBPR": int(leg.has_bpr),
                    "HasIFVG": int(leg.has_ifvg),
                })

            if direction is None:
                continue

            current_date = ts.date()
            if current_date != last_signal_date:
                last_signal_date = current_date
                daily_trades = 0
            if daily_trades >= max_trades_per_day:
                continue

            t = ts.time()
            if not (time(9, 45) <= t <= time(15, 30)):
                continue
            if filter_lunch and (time(11, 30) <= t <= time(13, 30)):
                continue

            target1_price = entry_price + (risk * r_mult_tp1) if direction == "LONG" else entry_price - (risk * r_mult_tp1)
            target2_price = entry_price + (risk * r_mult_tp2) if direction == "LONG" else entry_price - (risk * r_mult_tp2)

            signal_rows.append({
                "signal_time": ts,
                "direction": direction,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "target1_price": target1_price,
                "target2_price": target2_price,
                "model_name": self.strategy_name,
                "risk_pts": risk,
            })
            daily_trades += 1

        if write_diag_csv and diag_csv_path and diag_rows:
            pd.DataFrame(diag_rows).to_csv(diag_csv_path, index=False)
            print(f"[DIAG] Python CSV written to: {diag_csv_path}")

        return pd.DataFrame(signal_rows, columns=self.OUTPUT_COLUMNS)

    def get_param_grid(self) -> Dict[str, list]:
        """Return the searchable parameter grid for this strategy."""
        return {
            "resample_tf": ["3min", "5min", "15min"],
            "variant": ["baseline", "variant1", "variant2"],
            "max_trades_per_day": [1, 2, 3],
            "r_mult_tp1": [1.0, 1.5, 2.0],
            "r_mult_tp2": [2.0, 2.5, 3.0],
            "atr_risk_mult": [1.0, 1.8, 2.5],
            "filter_lunch": [True, False],
            "use_ker_filter": [True, False],
            "ker_min": [0.35, 0.45, 0.55],
            "use_barbwire_filter": [True, False],
            "max_bar_overlap": [55.0, 65.0, 75.0],
            "include_vi": [True, False],
            "strict_ifvg_only": [True, False],
        }
