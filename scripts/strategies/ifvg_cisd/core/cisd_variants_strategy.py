"""
========================================================================================
CISD Strategy Variants Engine: Baseline vs BPR/IFVG+FVG vs Double FVG
========================================================================================
Implements and compares three institutional execution models:

1. Baseline (Existing Model):
   - HTF CISD + HTF IFVG (with VI merger)
   - Entry on 1m bar close upon confirmation
   - Stop Loss: ATR risk bracket / swing extreme

2. Variant 1 (BPR or IFVG + FVG @ CISD Entry):
   - Condition: Balanced Price Range (BPR) OR [Inversion FVG (IFVG) + regular FVG] in the move
   - Trigger: CISD Delivery state confirmation
   - Entry Price: CISD Level (the breached delivery anchor open) or close
   - Stop Loss: Structural Low of the CISD (for Longs) / High of the CISD (for Shorts)

3. Variant 2 (Double FVG, No IFVG @ 2nd FVG Entry):
   - Condition: No IFVG present in the delivery leg, but 2 consecutive/active FVGs in same direction
   - Trigger: Creation of the 2nd FVG
   - Entry Price: 2nd FVG creation bar close / boundary
   - Stop Loss: Structural Low of the CISD (for Longs) / High of the CISD (for Shorts)

Supports any timeframe from 1min up to 15min and causal 1m execution alignment.

Author: Institutional Research Suite / Antigravity
========================================================================================
"""
from __future__ import annotations

import sys
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

# Bootstrap root path
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.bpr import compute_bpr
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg
from scripts.libs_py.data.resampler import resample_ohlcv


class CISDVariantsStrategy:
    """Institutional Strategy Engine for CISD, IFVG, BPR, and Multi-FVG Variants."""

    OUTPUT_COLUMNS = [
        "signal_time",
        "direction",
        "entry_price",
        "stop_price",
        "target1_price",
        "target2_price",
        "model_name",
        "risk_pts",
        "cisd_level",
        "cisd_origin_stop",
        "timeframe",
        "variant",
    ]

    VARIANTS = {
        "baseline": "Baseline: IFVG + CISD (ATR Stop)",
        "variant1_bpr_or_ifvg_fvg": "Variant 1: [BPR or (IFVG+FVG)] @ CISD Entry (CISD Low/High Stop)",
        "variant2_double_fvg_no_ifvg": "Variant 2: [No IFVG + 2x FVG] @ 2nd FVG Entry (CISD Low/High Stop)",
    }

    def __init__(self, ticker: str = "NQ") -> None:
        self.ticker = ticker.upper()
        # Default risk bounds based on instrument
        if "ES" in self.ticker or "MES" in self.ticker:
            self.min_risk_pts = 1.50
            self.max_risk_pts = 15.00
            self.tick_buffer = 0.25
        else:  # NQ / MNQ default
            self.min_risk_pts = 6.00
            self.max_risk_pts = 50.00
            self.tick_buffer = 0.50

    def hunt(
        self,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Executes signal generation for the chosen strategy variant and timeframe.
        """
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        # Standardize lowercase column names
        df.columns = [c.lower() for c in df.columns]

        variant = p.get("variant", "variant1_bpr_or_ifvg_fvg")
        resample_tf = p.get("resample_tf", "5min")
        max_trades_per_day = p.get("max_trades_per_day", 2)
        r_mult_tp1 = float(p.get("r_mult_tp1", 1.0))
        r_mult_tp2 = float(p.get("r_mult_tp2", 2.5))
        filter_lunch = bool(p.get("filter_lunch", True))
        rth_only = bool(p.get("rth_only", True))
        entry_style = p.get("entry_style", "cisd_level")  # "cisd_level" or "bar_close"
        include_vi = bool(p.get("include_vi", True))

        # 1. Resample to Target Timeframe (e.g. 1min, 2min, 3min, 5min, 15min)
        if resample_tf in ["1m", "1min", "1T"]:
            df_htf = df.copy()
        else:
            df_htf = resample_ohlcv(df, resample_tf)

        # 2. Compute Primitives on HTF
        cisd_htf = compute_cisd(df_htf)
        bpr_htf = compute_bpr(df_htf)
        ifvg_htf = compute_ifvg(df_htf, include_vi=include_vi)
        fvg_htf = compute_fvg(df_htf, include_vi=include_vi)

        # Extract Series
        htf_o = df_htf["open"].values
        htf_h = df_htf["high"].values
        htf_l = df_htf["low"].values
        htf_c = df_htf["close"].values
        n_htf = len(df_htf)

        cisd_event = cisd_htf["cisd_event"].values
        cisd_state = cisd_htf["cisd_state"].values
        bull_cisd_lvl = cisd_htf["active_bull_cisd_level"].values
        bear_cisd_lvl = cisd_htf["active_bear_cisd_level"].values
        cisd_origin_low = cisd_htf["cisd_origin_low"].values
        cisd_origin_high = cisd_htf["cisd_origin_high"].values

        bpr_event = bpr_htf["bpr_event"].values
        ifvg_event = ifvg_htf["ifvg_event"].values
        ifvg_state = ifvg_htf["ifvg_state"].values
        fvg_event = fvg_htf["fvg_event"].values
        fvg_top = fvg_htf["fvg_top"].values
        fvg_bottom = fvg_htf["fvg_bottom"].values

        # Signal arrays on HTF
        htf_long_sig = np.zeros(n_htf, dtype=bool)
        htf_short_sig = np.zeros(n_htf, dtype=bool)
        htf_entry_price = np.full(n_htf, np.nan, dtype=np.float64)
        htf_stop_price = np.full(n_htf, np.nan, dtype=np.float64)
        htf_cisd_lvl = np.full(n_htf, np.nan, dtype=np.float64)
        htf_cisd_orig = np.full(n_htf, np.nan, dtype=np.float64)

        # -------------------------------------------------------------
        # STATEFUL HTF SIGNAL GENERATION
        # -------------------------------------------------------------
        leg_dir = 0
        leg_has_bpr = False
        leg_has_ifvg = False
        leg_fvg_count = 0
        leg_origin_low = np.nan
        leg_origin_high = np.nan
        leg_cisd_level = np.nan
        v2_triggered_in_leg = False

        for t in range(1, n_htf):
            ev = cisd_event[t]
            st = cisd_state[t]
            bp = bpr_event[t]
            iv_ev = ifvg_event[t]
            iv_st = ifvg_state[t]
            fv = fvg_event[t]

            # ── Check Delivery Regime Flip ──────────────────────────────
            if ev == 1:
                leg_dir = 1
                leg_has_bpr = (bp == 1)
                leg_has_ifvg = (iv_ev == 1 or iv_st == 1)
                leg_fvg_count = 1 if (fv == 1) else 0
                leg_origin_low = cisd_origin_low[t] if not np.isnan(cisd_origin_low[t]) else htf_l[t]
                leg_cisd_level = bull_cisd_lvl[t] if not np.isnan(bull_cisd_lvl[t]) else htf_c[t]
                v2_triggered_in_leg = False

            elif ev == -1:
                leg_dir = -1
                leg_has_bpr = (bp == -1)
                leg_has_ifvg = (iv_ev == -1 or iv_st == -1)
                leg_fvg_count = 1 if (fv == -1) else 0
                leg_origin_high = cisd_origin_high[t] if not np.isnan(cisd_origin_high[t]) else htf_h[t]
                leg_cisd_level = bear_cisd_lvl[t] if not np.isnan(bear_cisd_lvl[t]) else htf_c[t]
                v2_triggered_in_leg = False

            else:
                # Continuation in current regime
                if leg_dir == 1:
                    if bp == 1:
                        leg_has_bpr = True
                    if iv_ev == 1 or iv_st == 1:
                        leg_has_ifvg = True
                    if fv == 1:
                        leg_fvg_count += 1

                elif leg_dir == -1:
                    if bp == -1:
                        leg_has_bpr = True
                    if iv_ev == -1 or iv_st == -1:
                        leg_has_ifvg = True
                    if fv == -1:
                        leg_fvg_count += 1

            # ── VARIANT 0: Baseline (HTF CISD + HTF IFVG) ───────────────
            if variant == "baseline":
                if st == 1 and (iv_ev == 1):
                    htf_long_sig[t] = True
                    htf_entry_price[t] = htf_c[t]
                    htf_cisd_lvl[t] = leg_cisd_level
                    htf_cisd_orig[t] = leg_origin_low

                elif st == -1 and (iv_ev == -1):
                    htf_short_sig[t] = True
                    htf_entry_price[t] = htf_c[t]
                    htf_cisd_lvl[t] = leg_cisd_level
                    htf_cisd_orig[t] = leg_origin_high

            # ── VARIANT 1: [BPR or (IFVG + FVG)] @ CISD Entry ───────────
            elif variant == "variant1_bpr_or_ifvg_fvg":
                if ev == 1:
                    # Check if BPR or (IFVG + FVG) occurred in this setup/run
                    # Also lookback up to 3 bars before CISD
                    recent_bpr = leg_has_bpr or (bp == 1) or any(bpr_event[max(0, t-3):t+1] == 1)
                    recent_ifvg = leg_has_ifvg or (iv_ev == 1) or any(ifvg_event[max(0, t-3):t+1] == 1)
                    recent_fvg = (leg_fvg_count >= 1) or (fv == 1) or any(fvg_event[max(0, t-3):t+1] == 1)

                    if recent_bpr or (recent_ifvg and recent_fvg):
                        htf_long_sig[t] = True
                        e_lvl = leg_cisd_level if not np.isnan(leg_cisd_level) else htf_c[t]
                        htf_entry_price[t] = e_lvl if entry_style == "cisd_level" else htf_c[t]
                        htf_stop_price[t] = (leg_origin_low - self.tick_buffer) if not np.isnan(leg_origin_low) else (htf_l[t] - self.tick_buffer)
                        htf_cisd_lvl[t] = e_lvl
                        htf_cisd_orig[t] = leg_origin_low

                elif ev == -1:
                    recent_bpr = leg_has_bpr or (bp == -1) or any(bpr_event[max(0, t-3):t+1] == -1)
                    recent_ifvg = leg_has_ifvg or (iv_ev == -1) or any(ifvg_event[max(0, t-3):t+1] == -1)
                    recent_fvg = (leg_fvg_count >= 1) or (fv == -1) or any(fvg_event[max(0, t-3):t+1] == -1)

                    if recent_bpr or (recent_ifvg and recent_fvg):
                        htf_short_sig[t] = True
                        e_lvl = leg_cisd_level if not np.isnan(leg_cisd_level) else htf_c[t]
                        htf_entry_price[t] = e_lvl if entry_style == "cisd_level" else htf_c[t]
                        htf_stop_price[t] = (leg_origin_high + self.tick_buffer) if not np.isnan(leg_origin_high) else (htf_h[t] + self.tick_buffer)
                        htf_cisd_lvl[t] = e_lvl
                        htf_cisd_orig[t] = leg_origin_high

            # ── VARIANT 2: [No IFVG + 2x FVG] @ 2nd FVG Entry ───────────
            elif variant == "variant2_double_fvg_no_ifvg":
                if (leg_dir == 1 or ev == 1) and not v2_triggered_in_leg:
                    # Count FVGs in this delivery leg (from CISD origin up to 10 bars back)
                    fvg_in_leg = np.sum(fvg_event[max(0, t-10):t+1] == 1)
                    if fv == 1 and fvg_in_leg >= 2:
                        htf_long_sig[t] = True
                        htf_entry_price[t] = fvg_top[t] if (entry_style == "fvg_boundary" and not np.isnan(fvg_top[t])) else htf_c[t]
                        htf_stop_price[t] = (leg_origin_low - self.tick_buffer) if not np.isnan(leg_origin_low) else (htf_l[t] - self.tick_buffer)
                        htf_cisd_lvl[t] = leg_cisd_level
                        htf_cisd_orig[t] = leg_origin_low
                        v2_triggered_in_leg = True

                elif (leg_dir == -1 or ev == -1) and not v2_triggered_in_leg:
                    fvg_in_leg = np.sum(fvg_event[max(0, t-10):t+1] == -1)
                    if fv == -1 and fvg_in_leg >= 2:
                        htf_short_sig[t] = True
                        htf_entry_price[t] = fvg_bottom[t] if (entry_style == "fvg_boundary" and not np.isnan(fvg_bottom[t])) else htf_c[t]
                        htf_stop_price[t] = (leg_origin_high + self.tick_buffer) if not np.isnan(leg_origin_high) else (htf_h[t] + self.tick_buffer)
                        htf_cisd_lvl[t] = leg_cisd_level
                        htf_cisd_orig[t] = leg_origin_high
                        v2_triggered_in_leg = True

        # 3. Assemble HTF Signals DataFrame
        df_sig_htf = pd.DataFrame(
            {
                "htf_long": htf_long_sig,
                "htf_short": htf_short_sig,
                "htf_entry": htf_entry_price,
                "htf_stop": htf_stop_price,
                "htf_cisd_lvl": htf_cisd_lvl,
                "htf_cisd_orig": htf_cisd_orig,
            },
            index=df_htf.index,
        )

        # 4. Merge Causally onto Base 1m Execution Timeline (if HTF != 1m)
        if resample_tf in ["1m", "1min", "1T"]:
            df_exec = df.join(df_sig_htf)
        else:
            # We want exact bar-close events to align to execution bar
            # When HTF closes at timestamp T, it becomes actionable at T
            df_sig_htf_shifted = df_sig_htf.copy()
            df_exec = pd.merge_asof(
                df,
                df_sig_htf_shifted,
                left_index=True,
                right_index=True,
                direction="backward",
            )
            # Only trigger on the exact 1m bar that coincides with HTF close
            is_htf_close_bar = df.index.isin(df_htf.index)
            df_exec["htf_long"] = df_exec["htf_long"] & is_htf_close_bar
            df_exec["htf_short"] = df_exec["htf_short"] & is_htf_close_bar

        # Compute ATR for baseline stop calculation
        high_low = df_exec["high"] - df_exec["low"]
        high_close = (df_exec["high"] - df_exec["close"].shift(1)).abs()
        low_close = (df_exec["low"] - df_exec["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df_exec["atr"] = tr.rolling(14, min_periods=14).mean().bfill()

        # 5. Apply Session & Time Filters
        times = df_exec.index.time
        if rth_only:
            in_rth = (times >= time(9, 45)) & (times <= time(15, 30))
            time_mask = in_rth
        else:
            time_mask = np.ones(len(df_exec), dtype=bool)

        if filter_lunch:
            not_lunch = (times < time(11, 30)) | (times > time(13, 30))
            time_mask = time_mask & not_lunch

        sig_mask_long = time_mask & df_exec["htf_long"].fillna(False)
        sig_mask_short = time_mask & df_exec["htf_short"].fillna(False)

        # 6. Extract Trades & Apply Daily Throttling
        trades: List[Dict[str, Any]] = []
        last_date = None
        daily_trades = 0
        last_sig_time = None

        active_indices = df_exec[sig_mask_long | sig_mask_short].index

        for idx in active_indices:
            row = df_exec.loc[idx]
            current_date = idx.date()

            if last_sig_time == idx:
                continue

            if current_date != last_date:
                last_date = current_date
                daily_trades = 0

            if daily_trades >= max_trades_per_day:
                continue

            is_long = bool(row["htf_long"])
            exec_c = float(row["close"])
            raw_entry = float(row["htf_entry"]) if not np.isnan(row["htf_entry"]) else exec_c
            raw_stop = float(row["htf_stop"]) if not np.isnan(row["htf_stop"]) else np.nan

            entry_price = raw_entry if not np.isnan(raw_entry) else exec_c

            if variant == "baseline" or np.isnan(raw_stop):
                atr_val = float(row["atr"]) if not np.isnan(row["atr"]) else 10.0
                calc_risk = max(self.min_risk_pts, min(self.max_risk_pts, atr_val * 1.8))
                if is_long:
                    stop_price = entry_price - calc_risk
                else:
                    stop_price = entry_price + calc_risk
                risk_pts = calc_risk
            else:
                if is_long:
                    stop_price = raw_stop
                    risk_pts = max(self.min_risk_pts, min(self.max_risk_pts, entry_price - stop_price))
                    stop_price = entry_price - risk_pts
                else:
                    stop_price = raw_stop
                    risk_pts = max(self.min_risk_pts, min(self.max_risk_pts, stop_price - entry_price))
                    stop_price = entry_price + risk_pts

            if is_long:
                direction = "LONG"
                target1_price = entry_price + (risk_pts * r_mult_tp1)
                target2_price = entry_price + (risk_pts * r_mult_tp2)
            else:
                direction = "SHORT"
                target1_price = entry_price - (risk_pts * r_mult_tp1)
                target2_price = entry_price - (risk_pts * r_mult_tp2)

            trades.append(
                {
                    "signal_time": idx,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target1_price": target1_price,
                    "target2_price": target2_price,
                    "model_name": self.VARIANTS.get(variant, variant),
                    "risk_pts": risk_pts,
                    "cisd_level": float(row["htf_cisd_lvl"]),
                    "cisd_origin_stop": float(row["htf_cisd_orig"]),
                    "timeframe": resample_tf,
                    "variant": variant,
                }
            )

            daily_trades += 1
            last_sig_time = idx

        return pd.DataFrame(trades, columns=self.OUTPUT_COLUMNS)
