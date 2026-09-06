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
from scripts.strategies.ifvg_cisd.core.config import load_config
from scripts.trading_framework.reporting.decision_log import GateRecorder


def htf_completion_label(htf_index: pd.DatetimeIndex, freq_minutes: int) -> pd.DatetimeIndex:
    """
    Convert bar-OPEN resample labels to bar-COMPLETION stamps.

    NT8 stamps Time[0] at bar close. pandas resample labels at bar open.
    A 5m bar labeled 10:00 completes at 10:05 — only at 10:05 does the
    CISD close that generated the signal become knowable. All signal
    timestamps must be completion-stamped so that (a) the sim cannot enter
    retroactively and (b) they join directly against NT8's diag CSV times.
    """
    return htf_index + pd.Timedelta(minutes=freq_minutes)


# ── Numba-compiled variant signal kernel ──────────────────────────────
@_njit
def _variant_signal_kernel(
    htf_open, htf_high, htf_low, htf_close,
    cisd_event_arr, cisd_state_arr, fvg_event_arr, fvg_top_arr, fvg_bottom_arr,
    ifvg_event_arr, bpr_event_arr,
    bull_cisd_level_arr, bear_cisd_level_arr,
    variant_int, tick_size, min_risk_bps, max_risk_bps,
    stop_type_int, stop_loss_bps, entry_mechanism_int,
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
    v2_triggered = False

    # Unmitigated FVG tracking (fixed arrays, per-leg)
    max_fvg = 50
    bull_fvg_bots = np.full(max_fvg, np.nan, dtype=np.float64)
    bear_fvg_tops = np.full(max_fvg, np.nan, dtype=np.float64)
    bull_fvg_count = 0
    bear_fvg_count = 0

    for i in range(n):
        o = htf_open[i]; h = htf_high[i]; l = htf_low[i]; c = htf_close[i]
        ce = cisd_event_arr[i]; cs = cisd_state_arr[i]
        fe = fvg_event_arr[i]; ie = ifvg_event_arr[i]; be = bpr_event_arr[i]

        # Snapshot prior leg flags BEFORE reset (for V1/V2 check at flip)
        prior_leg_has_bpr = leg_has_bpr
        prior_leg_has_ifvg = leg_has_ifvg
        prior_bull_fvg = bull_fvg_count
        prior_bear_fvg = bear_fvg_count

        if ce == 1:
            crossed = np.nan
            if i > 0 and not np.isnan(bear_cisd_level_arr[i-1]):
                crossed = bear_cisd_level_arr[i-1]
            regime = 1
            leg_origin_low = crossed; leg_origin_high = np.nan
            leg_cisd_level = bull_cisd_level_arr[i] if not np.isnan(bull_cisd_level_arr[i]) else o
            leg_has_bpr = False; leg_has_ifvg = False
            v2_triggered = False
            bull_fvg_count = 0; bear_fvg_count = 0
            for k in range(max_fvg):
                bull_fvg_bots[k] = np.nan
                bear_fvg_tops[k] = np.nan
        elif ce == -1:
            crossed = np.nan
            if i > 0 and not np.isnan(bull_cisd_level_arr[i-1]):
                crossed = bull_cisd_level_arr[i-1]
            regime = -1
            leg_origin_low = np.nan; leg_origin_high = crossed
            leg_cisd_level = bear_cisd_level_arr[i] if not np.isnan(bear_cisd_level_arr[i]) else o
            leg_has_bpr = False; leg_has_ifvg = False
            v2_triggered = False
            bull_fvg_count = 0; bear_fvg_count = 0
            for k in range(max_fvg):
                bull_fvg_bots[k] = np.nan
                bear_fvg_tops[k] = np.nan
        else:
            regime = cs

        if regime != 0:
            # Track unmitigated FVGs in the active leg
            if fe == 1 and bull_fvg_count < max_fvg:
                bull_fvg_bots[bull_fvg_count] = fvg_bottom_arr[i]
                bull_fvg_count += 1
            elif fe == -1 and bear_fvg_count < max_fvg:
                bear_fvg_tops[bear_fvg_count] = fvg_top_arr[i]
                bear_fvg_count += 1
            if ie == 1 and regime == 1: leg_has_ifvg = True
            if ie == -1 and regime == -1: leg_has_ifvg = True
            if be != 0: leg_has_bpr = True

            # Mitigation: remove filled FVGs (bull filled when low <= bot, bear when high >= top)
            k = 0
            while k < bull_fvg_count:
                if l <= bull_fvg_bots[k]:
                    for m in range(k, bull_fvg_count - 1):
                        bull_fvg_bots[m] = bull_fvg_bots[m + 1]
                    bull_fvg_count -= 1
                else:
                    k += 1
            k = 0
            while k < bear_fvg_count:
                if h >= bear_fvg_tops[k]:
                    for m in range(k, bear_fvg_count - 1):
                        bear_fvg_tops[m] = bear_fvg_tops[m + 1]
                    bear_fvg_count -= 1
                else:
                    k += 1

        price_ref = c if not np.isnan(c) else o
        min_risk = price_ref * min_risk_bps / 10000.0
        max_risk = price_ref * max_risk_bps / 10000.0

        if variant_int == 1:
            # V1: CISD trigger + (prior leg had BPR OR prior leg had IFVG)
            # The prior leg's BPR/IFVG are the reversal evidence; no FVG-count AND.
            if ce == 1 and (prior_leg_has_bpr or prior_leg_has_ifvg):
                ok = _emit_long_signal(
                    i, c, o, l, leg_cisd_level, leg_origin_low,
                    tick_size, min_risk, max_risk,
                    stop_type_int, stop_loss_bps, entry_mechanism_int,
                    sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, sig_count,
                )
                if ok: sig_count += 1
            elif ce == -1 and (prior_leg_has_bpr or prior_leg_has_ifvg):
                ok = _emit_short_signal(
                    i, c, o, h, leg_cisd_level, leg_origin_high,
                    tick_size, min_risk, max_risk,
                    stop_type_int, stop_loss_bps, entry_mechanism_int,
                    sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, sig_count,
                )
                if ok: sig_count += 1
        elif variant_int == 2:
            # V2: CISD trigger + 2+ unmitigated FVGs in the OPPOSING delivery run
            if ce == 1 and not v2_triggered and prior_bear_fvg >= 2:
                ok = _emit_long_signal(
                    i, c, o, l, leg_cisd_level, leg_origin_low,
                    tick_size, min_risk, max_risk,
                    stop_type_int, stop_loss_bps, entry_mechanism_int,
                    sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, sig_count,
                )
                if ok:
                    sig_count += 1
                    v2_triggered = True
            elif ce == -1 and not v2_triggered and prior_bull_fvg >= 2:
                ok = _emit_short_signal(
                    i, c, o, h, leg_cisd_level, leg_origin_high,
                    tick_size, min_risk, max_risk,
                    stop_type_int, stop_loss_bps, entry_mechanism_int,
                    sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, sig_count,
                )
                if ok:
                    sig_count += 1
                    v2_triggered = True

    return sig_idx[:sig_count], sig_dir[:sig_count], sig_entry[:sig_count], sig_stop[:sig_count], sig_risk[:sig_count]


@_njit
def _resolve_long_bracket(c, l, leg_cisd_level, leg_origin_low, tick_size,
                          stop_type_int, stop_loss_bps, entry_mechanism_int):
    """
    Resolve entry/stop for a bullish CISD signal with VALID geometry.

    Entry (mechanism):
      0 (market)    : flip-bar close.
      1 (cisd_limit): the armed CISD level — a pullback entry. Only valid if
                      the level is BELOW the flip close (a discount the market
                      may still give). Otherwise degrade to market close.
    Stop (type):
      0 (bps_stat)          : entry - stop_loss_bps of entry. The statistical SL:
                              with the entry right, this is never hit.
      1 (structural)        : the crossed origin level (leg_origin_low) MINUS a
                              2-tick buffer — but ONLY when it sits below entry.
                              If the crossed level is above the entry (invalid
                              long geometry), skip the trade entirely.
      2 (structural_capped) : structural, but capped at stop_loss_bps.
      3 (skip_if_out_of_band): structural stop, and skip if its distance is
                              outside [min_risk, max_risk] — mirrors the
                              Python-only pre-2026-09 behaviour.
    Returns (ok, entry, stop, risk).
    """
    ep = c
    if entry_mechanism_int == 1 and not np.isnan(leg_cisd_level) and leg_cisd_level < c:
        ep = leg_cisd_level

    if stop_type_int == 0:  # bps_stat
        rs = ep - (ep * stop_loss_bps / 10000.0)
        return True, ep, rs, ep - rs

    # structural family: the crossed origin is the invalidation level
    if np.isnan(leg_origin_low):
        # no crossed level recorded — degrade to bps_stat rather than guess
        rs = ep - (ep * stop_loss_bps / 10000.0)
        return True, ep, rs, ep - rs

    struct_stop = leg_origin_low - 2.0 * tick_size
    if struct_stop >= ep:
        # Crossed level at/above entry: invalid long geometry. Types 1 and 3
        # skip; type 2 degrades to the bps cap.
        if stop_type_int == 2:
            rs = ep - (ep * stop_loss_bps / 10000.0)
            return True, ep, rs, ep - rs
        return False, ep, struct_stop, 0.0

    risk = ep - struct_stop
    if stop_type_int == 2:  # structural capped at bps ceiling
        max_risk = ep * stop_loss_bps / 10000.0
        if risk > max_risk:
            rs = ep - max_risk
            return True, ep, rs, ep - rs
    return True, ep, struct_stop, risk


@_njit
def _resolve_short_bracket(c, h, leg_cisd_level, leg_origin_high, tick_size,
                           stop_type_int, stop_loss_bps, entry_mechanism_int):
    """Mirror of _resolve_long_bracket for shorts."""
    ep = c
    if entry_mechanism_int == 1 and not np.isnan(leg_cisd_level) and leg_cisd_level > c:
        ep = leg_cisd_level

    if stop_type_int == 0:  # bps_stat
        rs = ep + (ep * stop_loss_bps / 10000.0)
        return True, ep, rs, rs - ep

    if np.isnan(leg_origin_high):
        rs = ep + (ep * stop_loss_bps / 10000.0)
        return True, ep, rs, rs - ep

    struct_stop = leg_origin_high + 2.0 * tick_size
    if struct_stop <= ep:
        if stop_type_int == 2:
            rs = ep + (ep * stop_loss_bps / 10000.0)
            return True, ep, rs, rs - ep
        return False, ep, struct_stop, 0.0

    risk = struct_stop - ep
    if stop_type_int == 2:
        max_risk = ep * stop_loss_bps / 10000.0
        if risk > max_risk:
            rs = ep + max_risk
            return True, ep, rs, rs - ep
    return True, ep, struct_stop, risk


@_njit
def _emit_long_signal(bar_i, c, o, l, leg_cisd_level, leg_origin_low,
                      tick_size, min_risk, max_risk,
                      stop_type_int, stop_loss_bps, entry_mechanism_int,
                      sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, slot):
    ok, ep, rs, risk = _resolve_long_bracket(
        c, l, leg_cisd_level, leg_origin_low, tick_size,
        stop_type_int, stop_loss_bps, entry_mechanism_int,
    )
    if not ok:
        return False
    if risk < min_risk or risk > max_risk:
        return False
    sig_idx[slot] = bar_i
    sig_dir[slot] = 1
    sig_entry[slot] = ep
    sig_stop[slot] = rs
    sig_risk[slot] = risk
    return True


@_njit
def _emit_short_signal(bar_i, c, o, h, leg_cisd_level, leg_origin_high,
                       tick_size, min_risk, max_risk,
                       stop_type_int, stop_loss_bps, entry_mechanism_int,
                       sig_idx, sig_dir, sig_entry, sig_stop, sig_risk, slot):
    ok, ep, rs, risk = _resolve_short_bracket(
        c, h, leg_cisd_level, leg_origin_high, tick_size,
        stop_type_int, stop_loss_bps, entry_mechanism_int,
    )
    if not ok:
        return False
    if risk < min_risk or risk > max_risk:
        return False
    sig_idx[slot] = bar_i
    sig_dir[slot] = -1
    sig_entry[slot] = ep
    sig_stop[slot] = rs
    sig_risk[slot] = risk
    return True


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
        "entry_mechanism",
    ]

    def __init__(self, ticker: str = "NQ1") -> None:
        self.ticker = ticker
        self.strategy_name = "5m IFVG CISD Distribution"
        # Section 5.5: the criteria this hunter evaluates. None means not
        # instrumented; set by hunt() on every path.
        self.last_decisions: Optional[pd.DataFrame] = None

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        p = params or {}
        df = data.copy()

        if "close" not in df.columns or df.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        # Shared manifest defaults (configs/strategies/ifvg_cisd.yaml) — the same
        # file the C# generator projects into IfvgCisdConfig.cs. Explicit params
        # override; absence falls through to the manifest so the two platforms
        # can never silently disagree on a default.
        cfg = load_config()

        resample_tf = p.get("resample_tf", cfg.htf_resample)
        max_trades_per_day = p.get("max_trades_per_day", cfg.max_trades_per_day)
        r_mult_tp1 = p.get("r_mult_tp1", 1.0)
        r_mult_tp2 = p.get("r_mult_tp2", 2.5)
        atr_risk_mult = p.get("atr_risk_mult", cfg.atr_risk_mult)
        tick_size = float(p.get("tick_size", 0.25))

        variant = str(p.get("variant", cfg.variant)).lower()
        filter_lunch = bool(p.get("filter_lunch", cfg.lunch_filter_enabled))
        use_ker_filter = bool(p.get("use_ker_filter", False))
        ker_min = float(p.get("ker_min", 0.45))
        use_barbwire_filter = bool(p.get("use_barbwire_filter", False))
        max_bar_overlap = float(p.get("max_bar_overlap", 65.0))
        include_vi = bool(p.get("include_vi", cfg.include_vi))
        strict_ifvg_only = bool(p.get("strict_ifvg_only", cfg.strict_ifvg_only))

        # 1. Compute HTF CISD / FVG / iFVG / BPR
        df_htf = resample_ohlcv(df, resample_tf)
        cisd_htf = compute_cisd(df_htf)
        require_directional = bool(p.get("require_directional_candle", False))
        ifvg_htf = compute_ifvg(df_htf, include_vi=include_vi, require_directional_candle=require_directional)
        fvg_htf = compute_fvg(df_htf, include_vi=include_vi, require_directional_candle=require_directional)

        if variant in ("baseline", "strict_ifvg", "loose"):
            return self._hunt_baseline(
                df,
                df_htf,
                cisd_htf,
                ifvg_htf,
                fvg_htf,
                p,
            )

        bpr_htf = compute_bpr(df_htf, align_to_base=False, require_directional_candle=require_directional)
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

        # Merge causally onto 1m execution timeline (no lookahead).
        # The HTF signal computed on the bar labeled 10:00 is only knowable
        # at its COMPLETION (10:05). merge_asof(backward) on the raw open
        # labels would expose the signal to 1m bars from 10:00-10:04 — up to
        # (freq-1) minutes of lookahead. Re-index the HTF frame on
        # completion stamps before merging so a 1m bar only sees signals
        # whose HTF bar has fully closed.
        cfg = load_config()
        try:
            resample_minutes = int("".join(ch for ch in resample_tf if ch.isdigit()))
        except ValueError:
            resample_minutes = 5
        sig_htf_completion = sig_htf[["htf_long", "htf_short"]].copy()
        sig_htf_completion.index = htf_completion_label(sig_htf.index, resample_minutes)

        df = pd.merge_asof(
            df,
            sig_htf_completion,
            left_index=True,
            right_index=True,
            direction="backward",
        )
        df["htf_long"] = df["htf_long"].fillna(False)
        df["htf_short"] = df["htf_short"].fillna(False)

        # Execution ATR and Swings.
        # NOTE: no .bfill() — backfilling the first 13 bars of ATR uses
        # FUTURE bars' true ranges (lookahead). Bars without a full ATR
        # simply carry NaN and are filtered out of the entry mask below.
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14, min_periods=14).mean()
        df["swing_low2"] = df["low"].rolling(2).min()
        df["swing_high2"] = df["high"].rolling(2).max()

        t = df.index.time
        in_rth = (t >= time(cfg.earliest_entry_hhmm // 100, cfg.earliest_entry_hhmm % 100)) & (
            t <= time(cfg.latest_entry_hhmm // 100, cfg.latest_entry_hhmm % 100)
        )
        time_mask = in_rth & df["atr"].notna()

        if cfg.lunch_filter_enabled:
            lunch_start = time(cfg.lunch_start_hhmm // 100, cfg.lunch_start_hhmm % 100)
            lunch_end = time(cfg.lunch_end_hhmm // 100, cfg.lunch_end_hhmm % 100)
            not_lunch = (t < lunch_start) | (t > lunch_end)
            time_mask = time_mask & not_lunch

        sig_mask_long = time_mask & df["htf_long"]
        sig_mask_short = time_mask & df["htf_short"]

        # The BASE trigger before the optional filters narrow it, so the
        # filter gates can actually fail (section 5.5).
        base_long, base_short = sig_mask_long.copy(), sig_mask_short.copy()

        # Applied-filter ledger for the decision log.
        applied_filters: list = []

        if use_ker_filter:
            ker_series = compute_kaufman_efficiency(df, length=10)
            applied_filters.append(
                ("ker_efficiency", ker_series >= ker_min, ker_series, ker_min))
            sig_mask_long = sig_mask_long & (ker_series >= ker_min)
            sig_mask_short = sig_mask_short & (ker_series >= ker_min)

        if use_barbwire_filter:
            overlap_series = compute_bar_overlap(df, length=5)
            applied_filters.append(
                ("not_barbwire", overlap_series <= max_bar_overlap,
                 overlap_series, max_bar_overlap))
            sig_mask_long = sig_mask_long & (overlap_series <= max_bar_overlap)
            sig_mask_short = sig_mask_short & (overlap_series <= max_bar_overlap)

        # Decision log (section 5.5). TRIGGER = the HTF CISD+iFVG state bar;
        # gates: the entry window (RTH, ATR-known, lunch), the optional
        # filters, and the daily trade cap -- the loop's `continue` is the
        # cap's rejection and is the one criterion the loop hid. The log
        # records which qualifying bars the cap REFUSED; the loop stays the
        # authority on which bar trades.
        _day = pd.Series([d.date() for d in df.index], index=df.index)
        _qual = (sig_mask_long | sig_mask_short).astype(int)
        _ordinal = _qual.groupby(_day).cumsum()
        under_cap = _ordinal <= max_trades_per_day
        rec = (
            GateRecorder(df.index, run_id="", strategy="ifvg_cisd")
            .trigger(base_long, "long")
            .trigger(base_short, "short")
            .gate("entry_window_rth_atr", time_mask)
        )
        for gname, gmask, gval, gthr in applied_filters:
            rec = rec.gate(gname, gmask, value=gval, threshold=gthr)
        rec = rec.gate("daily_trade_cap", under_cap,
                       value=_ordinal, threshold=max_trades_per_day)
        self.last_decisions = rec.to_frame(signal_prefix="ic_")

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
            min_risk_bps = float(p.get("min_risk_bps", cfg.min_risk_bps))
            max_risk_bps = float(p.get("max_risk_bps", cfg.max_risk_bps))
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
                    "entry_mechanism": str(p.get("entry_mechanism", "market")).lower(),
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
        cfg = load_config()
        resample_tf = str(p.get("resample_tf", cfg.htf_resample))
        max_trades_per_day = p.get("max_trades_per_day", cfg.max_trades_per_day)
        r_mult_tp1 = p.get("r_mult_tp1", 1.0)
        r_mult_tp2 = p.get("r_mult_tp2", 2.5)
        tick_size = float(p.get("tick_size", 0.25))
        filter_lunch = bool(p.get("filter_lunch", cfg.lunch_filter_enabled))
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
        sig_htf["fvg_top"] = fvg_htf["fvg_top"]
        sig_htf["fvg_bottom"] = fvg_htf["fvg_bottom"]
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
        min_risk_bps = float(p.get("min_risk_bps", cfg.min_risk_bps))
        max_risk_bps = float(p.get("max_risk_bps", cfg.max_risk_bps))

        # Stop-type / entry-mechanism projections into the kernel's int space.
        # Both come from the manifest (single source of truth) unless the caller
        # overrides — the C# bot reads the SAME manifest via IfvgCisdConfig.cs.
        entry_mechanism = str(p.get("entry_mechanism", cfg.entry_mechanism)).lower()
        stop_type_map = {
            "bps_stat": 0,
            "structural": 1,
            "structural_capped_bps": 2,
            "skip_if_out_of_band": 3,
        }
        mechanism_map = {"market": 0, "cisd_limit": 1}
        stop_type_int = stop_type_map[
            str(p.get("stop_loss_type", cfg.stop_loss_type)).lower()
        ]
        stop_loss_bps = float(p.get("stop_loss_bps", cfg.stop_loss_bps))
        mechanism_int = mechanism_map[entry_mechanism]

        sig_idx, sig_dir, sig_entry, sig_stop, sig_risk = _variant_signal_kernel(
            htf_open.astype(np.float64), htf_high.astype(np.float64),
            htf_low.astype(np.float64), htf_close.astype(np.float64),
            sig_htf["cisd_event"].values.astype(np.int8),
            sig_htf["cisd_state"].values.astype(np.int8),
            sig_htf["fvg_event"].values.astype(np.int8),
            sig_htf["fvg_top"].values.astype(np.float64),
            sig_htf["fvg_bottom"].values.astype(np.float64),
            sig_htf["ifvg_event"].values.astype(np.int8),
            sig_htf["bpr_event"].values.astype(np.int8),
            sig_htf["bull_cisd_level"].values.astype(np.float64),
            sig_htf["bear_cisd_level"].values.astype(np.float64),
            variant_int, tick_size, min_risk_bps, max_risk_bps,
            stop_type_int, stop_loss_bps, mechanism_int,
        )

        # ── Post-process: apply time/session filters and daily trade limits ──
        # Signal timestamps are bar-COMPLETION stamps (NT8 Time[0] semantics):
        # a 5m bar labeled 10:00 completes at 10:05, and only then is the CISD
        # close that fired the signal knowable. htf_index[i] is the OPEN label,
        # so we shift by the resample interval before applying session filters
        # and before the sim consumes signal_time.
        try:
            resample_minutes = int("".join(ch for ch in resample_tf if ch.isdigit()))
        except ValueError:
            resample_minutes = 5
        htf_index = htf_completion_label(sig_htf.index, resample_minutes)

        signal_rows: list[dict[str, Any]] = []
        last_signal_date: Optional[Any] = None
        daily_trades = 0
        # Decision-log tallies for the loop's three refusals (section 5.5).
        # The kernel fires at most one signal per HTF bar, so per-signal rows
        # (not per-bar masks) are the honest shape here; a mask over 1m bars
        # would re-describe what the kernel already narrowed.
        _log_rows: list = []

        for j in range(len(sig_idx)):
            i = sig_idx[j]
            # Completion stamp: signal becomes actionable at HTF bar close.
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
                _log_rows.append((ts, direction, "daily_trade_cap", 0,
                                  max_trades_per_day))
                continue

            # Session window (ET) — from the shared manifest
            t = ts.time()
            hhmm = ts.hour * 100 + ts.minute
            if not (cfg.earliest_entry_hhmm <= hhmm <= cfg.latest_entry_hhmm):
                _log_rows.append((ts, direction, "entry_window_rth", 0,
                                  cfg.latest_entry_hhmm))
                continue
            if cfg.lunch_filter_enabled and (
                cfg.lunch_start_hhmm <= hhmm <= cfg.lunch_end_hhmm
            ):
                _log_rows.append((ts, direction, "lunch_window", 0,
                                  cfg.lunch_end_hhmm))
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
                "entry_mechanism": entry_mechanism,
            })
            _log_rows.append((ts, direction, "", 1, None))
            daily_trades += 1

        # Decision log (section 5.5): one row per kernel signal with its
        # blocking gate named. Built directly because the per-row loop is
        # the authority here; the schema is the shared COLUMNS.
        from scripts.trading_framework.reporting.decision_log import COLUMNS
        _n = len(_log_rows)
        _df_log = pd.DataFrame({
            "schema_version": [1] * _n,
            "run_id": [""] * _n,
            "side": ["python"] * _n,
            "strategy": ["ifvg_cisd"] * _n,
            "seq": list(range(1, _n + 1)),
            "bar_time": [r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]) for r in _log_rows],
            "session": [""] * _n,
            "direction": [r[1] for r in _log_rows],
            "decision": ["REJECTED" if r[2] else "ENTRY" for r in _log_rows],
            "signal_name": ["icv_{}".format(k + 1) for k in range(_n)],
            "gate": [r[2] for r in _log_rows],
            "kind": ["gate"] * _n,
            "gate_pass": [r[3] for r in _log_rows],
            "gate_value": ["" for _ in _log_rows],
            "gate_threshold": [str(r[4]) if r[4] is not None else "" for r in _log_rows],
            "detail": ["" for _ in _log_rows],
        })
        self.last_decisions = _df_log.reindex(columns=list(COLUMNS)) if _n else (
            GateRecorder(pd.DatetimeIndex([]), run_id="",
                         strategy="ifvg_cisd").to_frame(signal_prefix="ic_"))

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
