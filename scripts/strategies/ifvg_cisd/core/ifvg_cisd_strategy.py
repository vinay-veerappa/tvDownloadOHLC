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

try:
    import numba
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

def _njit(func):
    if _HAS_NUMBA:
        return numba.njit(fastmath=True, cache=True)(func)
    return func

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


# ── Numba-compiled variant signal kernel ──────────────────────────────
@_njit
def _variant_signal_kernel(
    htf_open, htf_high, htf_low, htf_close,
    cisd_event_arr, cisd_state_arr, fvg_event_arr,
    ifvg_event_arr, bpr_event_arr,
    bull_cisd_level_arr, bear_cisd_level_arr,
    variant_int, tick_size, min_risk_bps, max_risk_bps,
):
    n = len(htf_open)
    sig_idx = np.full(n, -1, dtype=np.int64)
    sig_dir = np.zeros(n, dtype=np.int8)
    sig_entry = np.full(n, np.nan, dtype=np.float64)
    sig_stop = np.full(n, np.nan, dtype=np.float64)
    sig_risk = np.full(n, np.nan, dtype=np.float64)
    sig_count = 0

    regime = 0
    leg_origin_low = np.nan
    leg_origin_high = np.nan
    leg_cisd_level = np.nan
    leg_has_bpr = False
    leg_has_ifvg = False
    bull_fvg_count = 0
    bear_fvg_count = 0
    prior_bear_fvg = 0
    prior_bull_fvg = 0
    v2_triggered = False

    for i in range(n):
        o = htf_open[i]; h = htf_high[i]; l = htf_low[i]; c = htf_close[i]
        ce = cisd_event_arr[i]; cs = cisd_state_arr[i]
        fe = fvg_event_arr[i]; ie = ifvg_event_arr[i]; be = bpr_event_arr[i]

        # Snapshot prior leg flags BEFORE reset (for V1 check at flip)
        prior_leg_has_bpr = leg_has_bpr
        prior_leg_has_ifvg = leg_has_ifvg
        prior_bull_fvg_snap = bull_fvg_count
        prior_bear_fvg_snap = bear_fvg_count

        if ce == 1:
            crossed = np.nan
            if i > 0 and not np.isnan(bear_cisd_level_arr[i-1]):
                crossed = bear_cisd_level_arr[i-1]
            regime = 1
            leg_origin_low = crossed; leg_origin_high = np.nan
            leg_cisd_level = bull_cisd_level_arr[i] if not np.isnan(bull_cisd_level_arr[i]) else o
            leg_has_bpr = False; leg_has_ifvg = False
            prior_bear_fvg = prior_bear_fvg_snap; bull_fvg_count = 0; v2_triggered = False
        elif ce == -1:
            crossed = np.nan
            if i > 0 and not np.isnan(bull_cisd_level_arr[i-1]):
                crossed = bull_cisd_level_arr[i-1]
            regime = -1
            leg_origin_low = np.nan; leg_origin_high = crossed
            leg_cisd_level = bear_cisd_level_arr[i] if not np.isnan(bear_cisd_level_arr[i]) else o
            leg_has_bpr = False; leg_has_ifvg = False
            prior_bull_fvg = prior_bull_fvg_snap; bear_fvg_count = 0; v2_triggered = False
        else:
            regime = cs

        if regime != 0:
            if fe == 1: bull_fvg_count += 1
            elif fe == -1: bear_fvg_count += 1
            if ie == 1 and regime == 1: leg_has_ifvg = True
            if ie == -1 and regime == -1: leg_has_ifvg = True
            if be != 0: leg_has_bpr = True

        price_ref = c if not np.isnan(c) else o
        min_risk = price_ref * min_risk_bps / 10000.0
        max_risk = price_ref * max_risk_bps / 10000.0

        if variant_int == 1:
            # V1: CISD trigger + (prior leg had BPR OR (prior leg had IFVG + >=1 opposing FVG))
            # For a bull CISD, prior leg was bear -> check bear FVGs
            # For a bear CISD, prior leg was bull -> check bull FVGs
            if ce == 1 and (prior_leg_has_bpr or (prior_leg_has_ifvg and prior_bear_fvg_snap >= 1)):
                ep = leg_cisd_level if not np.isnan(leg_cisd_level) else c
                rs = leg_origin_low - 2*tick_size if not np.isnan(leg_origin_low) else l - 2*tick_size
                if rs >= ep: rs = l - 2*tick_size
                risk = abs(ep - rs)
                if risk >= min_risk and risk <= max_risk:
                    sig_idx[sig_count]=i; sig_dir[sig_count]=1; sig_entry[sig_count]=ep
                    sig_stop[sig_count]=rs; sig_risk[sig_count]=risk; sig_count += 1
            elif ce == -1 and (prior_leg_has_bpr or (prior_leg_has_ifvg and prior_bull_fvg_snap >= 1)):
                ep = leg_cisd_level if not np.isnan(leg_cisd_level) else c
                rs = leg_origin_high + 2*tick_size if not np.isnan(leg_origin_high) else h + 2*tick_size
                if rs <= ep: rs = h + 2*tick_size
                risk = abs(rs - ep)
                if risk >= min_risk and risk <= max_risk:
                    sig_idx[sig_count]=i; sig_dir[sig_count]=-1; sig_entry[sig_count]=ep
                    sig_stop[sig_count]=rs; sig_risk[sig_count]=risk; sig_count += 1
        elif variant_int == 2:
            if ce == 1 and not v2_triggered and prior_bear_fvg >= 2:
                ep = leg_cisd_level if not np.isnan(leg_cisd_level) else c
                rs = leg_origin_low - 2*tick_size if not np.isnan(leg_origin_low) else l - 2*tick_size
                if rs >= ep: rs = l - 2*tick_size
                risk = abs(ep - rs)
                if risk >= min_risk and risk <= max_risk:
                    sig_idx[sig_count]=i; sig_dir[sig_count]=1; sig_entry[sig_count]=ep
                    sig_stop[sig_count]=rs; sig_risk[sig_count]=risk; sig_count += 1
                    v2_triggered = True
            elif ce == -1 and not v2_triggered and prior_bull_fvg >= 2:
                ep = leg_cisd_level if not np.isnan(leg_cisd_level) else c
                rs = leg_origin_high + 2*tick_size if not np.isnan(leg_origin_high) else h + 2*tick_size
                if rs <= ep: rs = h + 2*tick_size
                risk = abs(rs - ep)
                if risk >= min_risk and risk <= max_risk:
                    sig_idx[sig_count]=i; sig_dir[sig_count]=-1; sig_entry[sig_count]=ep
                    sig_stop[sig_count]=rs; sig_risk[sig_count]=risk; sig_count += 1
                    v2_triggered = True

    return sig_idx[:sig_count], sig_dir[:sig_count], sig_entry[:sig_count], sig_stop[:sig_count], sig_risk[:sig_count]


@dataclass
class _LegState:
    regime: int = 0
    origin_low: float = np.nan       # CISD level that was crossed (structural stop)
    origin_high: float = np.nan      # CISD level that was crossed (structural stop)
    cisd_level: float = np.nan       # new armed CISD level for this regime
    crossed_level: float = np.nan    # the old regime's level that was breached to trigger this leg
    has_bpr: bool = False
    has_ifvg: bool = False
    bull_fvg_count: int = 0
    bear_fvg_count: int = 0
    v2_triggered: bool = False
    cisd_bar_index: int = -1         # bar index where the CISD trigger fired


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
            # Baseline uses ATR-based risk (no CISD level available in this path)
            raw_risk = float(row["atr"]) * atr_risk_mult
            min_risk_bps = float(p.get("min_risk_bps", 2.0))
            max_risk_bps = float(p.get("max_risk_bps", 15.0))
            entry_ref = float(row["close"])
            min_risk = entry_ref * min_risk_bps / 10000.0
            max_risk = entry_ref * max_risk_bps / 10000.0
            risk = max(min_risk, min(max_risk, raw_risk))

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
        # Track the armed CISD levels so we can capture the crossed level on flip
        sig_htf["bull_cisd_level"] = cisd_htf["active_bull_cisd_level"]
        sig_htf["bear_cisd_level"] = cisd_htf["active_bear_cisd_level"]

        htf_open = df_htf["open"].values
        htf_high = df_htf["high"].values
        htf_low = df_htf["low"].values
        htf_close = df_htf["close"].values
        n_htf = len(sig_htf)

        # ── Call Numba-compiled variant signal kernel ──
        variant_int = 1 if variant == "variant1" else 2
        min_risk_bps = float(p.get("min_risk_bps", 2.0))
        max_risk_bps = float(p.get("max_risk_bps", 15.0))

        sig_idx, sig_dir, sig_entry, sig_stop, sig_risk = _variant_signal_kernel(
            htf_open.astype(np.float64), htf_high.astype(np.float64),
            htf_low.astype(np.float64), htf_close.astype(np.float64),
            sig_htf["cisd_event"].values.astype(np.int8),
            sig_htf["cisd_state"].values.astype(np.int8),
            sig_htf["fvg_event"].values.astype(np.int8),
            sig_htf["ifvg_event"].values.astype(np.int8),
            sig_htf["bpr_event"].values.astype(np.int8),
            sig_htf["bull_cisd_level"].values.astype(np.float64),
            sig_htf["bear_cisd_level"].values.astype(np.float64),
            variant_int, tick_size, min_risk_bps, max_risk_bps,
        )

        # ── Post-process: apply time/session filters and daily trade limits ──
        signal_rows: list[dict[str, Any]] = []
        last_signal_date: Optional[Any] = None
        daily_trades = 0
        htf_index = sig_htf.index

        for j in range(len(sig_idx)):
            i = sig_idx[j]
            ts = htf_index[i]
            direction = "LONG" if sig_dir[j] == 1 else "SHORT"
            entry_price = float(sig_entry[j])
            stop_price = float(sig_stop[j])
            risk = float(sig_risk[j])

            # Daily trade limit
            current_date = ts.date()
            if current_date != last_signal_date:
                last_signal_date = current_date
                daily_trades = 0
            if daily_trades >= max_trades_per_day:
                continue

            # RTH filter
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
            "min_risk_bps": [2.0, 5.0, 10.0],
            "max_risk_bps": [10.0, 15.0, 20.0],
            "filter_lunch": [True, False],
            "use_ker_filter": [True, False],
            "ker_min": [0.35, 0.45, 0.55],
            "use_barbwire_filter": [True, False],
            "max_bar_overlap": [55.0, 65.0, 75.0],
            "include_vi": [True, False],
            "strict_ifvg_only": [True, False],
        }
