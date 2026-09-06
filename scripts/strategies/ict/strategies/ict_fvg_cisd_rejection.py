"""
ICT FVG Rejection + CISD + MSS Strategy
========================================
Harmonised under ADR-020 / ADR-017 / ADR-002 / ADR-011.

Concept:
    Price enters a higher-timeframe Fair Value Gap (the "draw"), rejects
    from it, and the rejection displacement creates lower-timeframe FVG(s).
    CISD confirms the delivery shift, MSS confirms the structure break.
    Both required before entry.

    All variants are parameters — one class, all test arms.
    See: docs/strategies/fvg_cisd_rejection/FVG_CISD_REJECTION_STRATEGY.md

Architecture:
    Pillar 2 - Pure Signal Hunter. Fully vectorized (ADR-017 zero-loop).
    Loads pre-computed parquet files for FVG/structure (no re-detection).
    Uses merge_asof, ffill, and NumPy primitives for all signal logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, Dict, Optional

import sys

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.libs_py.ict_engine import (
    detect_fvg,
    detect_swings,
    detect_cisd,
    detect_cisd_authoritative,
    detect_structure_breaks,
)
from scripts.trading_framework.reporting.decision_log import GateRecorder

# ── Constants ──────────────────────────────────────────────────────────────
_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]

_DERIVED_ICT_DIR = Path(_root_dir) / "data" / "derived" / "ICT"

# Timeframe to resample rule mapping
_TF_RULES = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "1d": "1D"}


class ICTFVGCISDRejectionStrategy:
    """
    ICT FVG Rejection + CISD + MSS Strategy.

    Fully vectorized per ADR-017. All test variants are parameters.
    """

    def __init__(self, ticker: str = "ES1") -> None:
        self.ticker = ticker
        self.strategy_name = "ICT FVG+CISD Rejection"
        # Section 5.5: the criteria this hunter evaluates. None means not
        # instrumented; set by hunt() on every path.
        self.last_decisions: Optional[pd.DataFrame] = None

    # ── Public interface ──────────────────────────────────────────────

    def hunt(
        self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Generate trade signals — fully vectorized (ADR-017).

        Parameters
        ----------
        data : pd.DataFrame — NY-localised 1-min OHLCV
        params : dict — see get_param_grid() for all options

        Returns
        -------
        pd.DataFrame with _COLS + extended metric columns.
        """
        p = params or {}
        htf_tf = p.get("htf_tf", "15m")
        ltf_tf = p.get("ltf_tf", "5m")
        require_rej_fvg = bool(p.get("require_rejection_fvg", True))
        cisd_impl = p.get("cisd_impl", "sweep_open")
        entry_method = p.get("entry_method", "2nd_fvg")
        sl_method = p.get("sl_method", "swing_extreme")
        tp_rr = int(p.get("tp_rr", 2))
        require_mss = bool(p.get("require_mss", True))
        fvg_freshness = p.get("fvg_freshness", "fresh")
        swing_len = int(p.get("swing_length", 5))
        tick_size = float(p.get("tick_size", 0.25))
        stop_ticks = int(p.get("stop_ticks", 2))
        use_precomputed = bool(p.get("use_precomputed", True))
        stop_buf = stop_ticks * tick_size

        # ── 1. Prepare exec timeframe data ───────────────────────────
        exec_ohlc = data[["open", "high", "low", "close", "volume"]].copy()
        n = len(exec_ohlc)
        if n == 0:
            return pd.DataFrame(columns=_COLS)

        exec_idx = exec_ohlc.index
        exec_close = exec_ohlc["close"].values.astype(np.float64)
        exec_open = exec_ohlc["open"].values.astype(np.float64)
        exec_high = exec_ohlc["high"].values.astype(np.float64)
        exec_low = exec_ohlc["low"].values.astype(np.float64)
        exec_ns = exec_idx.asi8  # nanosecond int64 for vectorized time math

        # ── 2. Load FVG data (pre-computed or on-the-fly) ─────────────
        htf_fvg_df = self._load_fvg(htf_tf, use_precomputed, exec_ohlc)
        if htf_fvg_df is None or htf_fvg_df.empty:
            return pd.DataFrame(columns=_COLS)

        ltf_fvg_df = self._load_fvg(ltf_tf, use_precomputed, exec_ohlc)
        if ltf_fvg_df is None or ltf_fvg_df.empty:
            return pd.DataFrame(columns=_COLS)

        # ── 3. Load CISD + MSS from pre-computed structure parquet ────
        # Use pre-computed structure parquet when available (same as FVG parquet).
        # Falls back to on-the-fly detection only for 1m LTF or delivery_series CISD.
        cisd_col = "cisd_type"
        if use_precomputed and ltf_tf != "1m" and cisd_impl == "sweep_open":
            struct_fp = _DERIVED_ICT_DIR / f"{self.ticker}_structure_{ltf_tf}.parquet"
            if struct_fp.exists():
                struct_full = pd.read_parquet(struct_fp)
                cisd_df = struct_full[["cisd_type"]].copy()
                # Reconstruct break_high/break_low from swing levels + LTF close
                ltf_ohlc = self._resample_ohlc(exec_ohlc, ltf_tf)
                last_sh = struct_full["swing_level"].where(struct_full["swing_type"] == 1).ffill().reindex(ltf_ohlc.index).fillna(np.inf)
                last_sl = struct_full["swing_level"].where(struct_full["swing_type"] == -1).ffill().reindex(ltf_ohlc.index).fillna(-np.inf)
                struct_df = pd.DataFrame({
                    "break_high": ltf_ohlc["close"].values > last_sh.values,
                    "break_low": ltf_ohlc["close"].values < last_sl.values,
                }, index=ltf_ohlc.index)
                swings = struct_full[["swing_type", "swing_level"]].copy()
                swings.rename(columns={"swing_type": "shl", "swing_level": "level"}, inplace=True)
            else:
                ltf_ohlc = self._resample_ohlc(exec_ohlc, ltf_tf)
                swings = detect_swings(ltf_ohlc, swing_length=swing_len)
                cisd_df = detect_cisd(ltf_ohlc, swings)
                struct_df = detect_structure_breaks(ltf_ohlc, swings)
        else:
            # On-the-fly: 1m LTF or delivery_series CISD
            ltf_ohlc = self._resample_ohlc(exec_ohlc, ltf_tf)
            swings = detect_swings(ltf_ohlc, swing_length=swing_len)
            if cisd_impl == "delivery_series":
                cisd_df = detect_cisd_authoritative(ltf_ohlc, swings)
            else:
                cisd_df = detect_cisd(ltf_ohlc, swings)
            struct_df = detect_structure_breaks(ltf_ohlc, swings)

        # ── 4. Map HTF FVGs to exec timeframe via searchsorted ──────────
        htf_active = self._build_active_fvgs(htf_fvg_df, exec_idx, fvg_freshness, exec_ohlc)
        ltf_active = self._build_active_fvgs(ltf_fvg_df, exec_idx, fvg_freshness, exec_ohlc)

        htf_bull_top = htf_active["bull_top"].values
        htf_bull_bot = htf_active["bull_bot"].values
        htf_bear_top = htf_active["bear_top"].values
        htf_bear_bot = htf_active["bear_bot"].values
        htf_bull_create = htf_active["bull_create_ns"].values
        htf_bear_create = htf_active["bear_create_ns"].values

        bull_has = ~np.isnan(htf_bull_top)
        bear_has = ~np.isnan(htf_bear_top)

        # ── 5. FVG touch + rejection (vectorized) ─────────────────────
        htf_bull_touch = bull_has & (exec_low <= htf_bull_top) & (exec_low >= htf_bull_bot)
        htf_bear_touch = bear_has & (exec_high >= htf_bear_bot) & (exec_high <= htf_bear_top)

        htf_bull_reject = htf_bull_touch & (exec_close > exec_open)
        htf_bear_reject = htf_bear_touch & (exec_close < exec_open)

        # FVG fill depth (vectorized)
        bull_gap = htf_bull_top - htf_bull_bot
        bull_gap_s = np.where(bull_gap > 0, bull_gap, 1e-9)
        htf_bull_fill = np.where(htf_bull_touch, (htf_bull_top - exec_low) / bull_gap_s, 0.0)
        bear_gap = htf_bear_top - htf_bear_bot
        bear_gap_s = np.where(bear_gap > 0, bear_gap, 1e-9)
        htf_bear_fill = np.where(htf_bear_touch, (exec_high - htf_bear_bot) / bear_gap_s, 0.0)

        # FVG size % of price (vectorized)
        htf_bull_size_pct = np.where(bull_has, bull_gap / exec_close * 100, 0.0)
        htf_bear_size_pct = np.where(bear_has, bear_gap / exec_close * 100, 0.0)

        # FVG age in bars (vectorized)
        bar_ns = int(np.median(np.diff(exec_ns))) if n > 1 else 60_000_000_000
        htf_bull_age = np.where(bull_has, (exec_ns - htf_bull_create) / bar_ns, 0).astype(int)
        htf_bull_age = np.maximum(htf_bull_age, 0)
        htf_bear_age = np.where(bear_has, (exec_ns - htf_bear_create) / bar_ns, 0).astype(int)
        htf_bear_age = np.maximum(htf_bear_age, 0)

        # ── 6. FVG entry time (first touch of current FVG zone) ──────
        # The entry time is the START of the current FVG touch sequence.
        # When price touches FVG at bar i, entry_time = i.
        # When price stops touching (gap between touches), reset entry_time.
        # This gives us the window [first_touch → current] for rejection FVG count.
        # Use a state machine: track when touch starts (transition from no-touch to touch)
        bull_touch_starts = htf_bull_touch & ~np.roll(htf_bull_touch, 1, axis=0).astype(bool)
        bull_touch_starts[0] = htf_bull_touch[0]  # handle first bar
        # Forward-fill the start time while touch is ongoing
        bull_entry_ns_raw = pd.Series(np.where(bull_touch_starts, exec_ns, np.nan))
        # Within each consecutive touch run, fill forward the start time
        bull_touch_groups = bull_touch_starts.cumsum()
        bull_fvg_entry_ns = bull_entry_ns_raw.groupby(bull_touch_groups).ffill().values
        # For bars where there's no active touch, use the most recent start (for CISD check later)
        bull_fvg_entry_ns_last = pd.Series(np.where(htf_bull_touch, bull_fvg_entry_ns, np.nan)).ffill().values

        bear_touch_starts = htf_bear_touch & ~np.roll(htf_bear_touch, 1, axis=0).astype(bool)
        bear_touch_starts[0] = htf_bear_touch[0]
        bear_entry_ns_raw = pd.Series(np.where(bear_touch_starts, exec_ns, np.nan))
        bear_touch_groups = bear_touch_starts.cumsum()
        bear_fvg_entry_ns = bear_entry_ns_raw.groupby(bear_touch_groups).ffill().values
        bear_fvg_entry_ns_last = pd.Series(np.where(htf_bear_touch, bear_fvg_entry_ns, np.nan)).ffill().values

        # Time-to-CISD: bars from FVG entry to current (vectorized)
        # Use the "last" entry time (most recent touch start) for CISD timing
        time_to_cisd_bull = np.where(
            np.isfinite(bull_fvg_entry_ns_last),
            (exec_ns - bull_fvg_entry_ns_last) / bar_ns, 0
        ).astype(int)
        time_to_cisd_bull = np.maximum(time_to_cisd_bull, 0)
        time_to_cisd_bear = np.where(
            np.isfinite(bear_fvg_entry_ns_last),
            (exec_ns - bear_fvg_entry_ns_last) / bar_ns, 0
        ).astype(int)
        time_to_cisd_bear = np.maximum(time_to_cisd_bear, 0)

        # ── 7. Map CISD/MSS to exec timeframe (vectorized ffill) ──────
        cisd_bull_fired = self._cumulative_fire(cisd_df[cisd_col].values == 1, cisd_df.index, exec_idx)
        cisd_bear_fired = self._cumulative_fire(cisd_df[cisd_col].values == -1, cisd_df.index, exec_idx)
        mss_bull_fired = self._cumulative_fire(struct_df["break_high"].values.astype(bool), struct_df.index, exec_idx)
        mss_bear_fired = self._cumulative_fire(struct_df["break_low"].values.astype(bool), struct_df.index, exec_idx)

        # Pre-FVG sweep (vectorized) — reuse MSS fire results (break_low = mss_bear, break_high = mss_bull)
        pre_bull_sweep = mss_bear_fired & htf_bull_touch
        pre_bear_sweep = mss_bull_fired & htf_bear_touch

        # ── 8. Rejection-leg FVG count (vectorized) ──────────────────
        rej_fvg_bull_count = self._count_fvgs_in_window_vec(
            ltf_fvg_df, ltf_fvg_df["fvg_type"] == 1, bull_fvg_entry_ns, exec_ns
        )
        rej_fvg_bear_count = self._count_fvgs_in_window_vec(
            ltf_fvg_df, ltf_fvg_df["fvg_type"] == -1, bear_fvg_entry_ns, exec_ns
        )

        # ── 9. Confluence count (vectorized) ──────────────────────────
        ltf_bull_has = ~np.isnan(ltf_active["bull_top"].values)
        ltf_bear_has = ~np.isnan(ltf_active["bear_top"].values)
        confluence = bull_has.astype(int) + bear_has.astype(int) + ltf_bull_has.astype(int) + ltf_bear_has.astype(int)

        # ── 10. Entry price (vectorized) ──────────────────────────────
        if entry_method == "cisd_close":
            bull_entry = exec_close.copy()
            bear_entry = exec_close.copy()
        else:
            bull_entry = self._compute_rej_fvg_entry_vec(
                ltf_fvg_df, ltf_fvg_df["fvg_type"] == 1,
                bull_fvg_entry_ns, exec_ns, entry_method, exec_close
            )
            bear_entry = self._compute_rej_fvg_entry_vec(
                ltf_fvg_df, ltf_fvg_df["fvg_type"] == -1,
                bear_fvg_entry_ns, exec_ns, entry_method, exec_close
            )

        # ── 11. Stop loss (vectorized) ────────────────────────────────
        if sl_method == "htf_fvg_boundary":
            bull_stop = np.where(bull_has, htf_bull_bot - stop_buf, np.nan)
            bear_stop = np.where(bear_has, htf_bear_top + stop_buf, np.nan)
        else:  # swing_extreme
            bull_stop = self._compute_swing_stop_vec(
                exec_low, exec_high, bull_fvg_entry_ns, exec_ns, is_long=True, stop_buf=stop_buf
            )
            bear_stop = self._compute_swing_stop_vec(
                exec_low, exec_high, bear_fvg_entry_ns, exec_ns, is_long=False, stop_buf=stop_buf
            )

        # ── 12. Target (vectorized) ───────────────────────────────────
        bull_risk = bull_entry - bull_stop
        bull_target = bull_entry + bull_risk * tp_rr
        bear_risk = bear_stop - bear_entry
        bear_target = bear_entry - bear_risk * tp_rr

        # ── 13. Build entry mask (vectorized) ─────────────────────────
        bull_mask = htf_bull_reject & cisd_bull_fired
        if require_mss:
            bull_mask &= mss_bull_fired
        if require_rej_fvg:
            bull_mask &= (rej_fvg_bull_count > 0)
        bull_mask &= np.isfinite(bull_entry) & np.isfinite(bull_stop) & (bull_risk > 1e-9)

        bear_mask = htf_bear_reject & cisd_bear_fired
        if require_mss:
            bear_mask &= mss_bear_fired
        if require_rej_fvg:
            bear_mask &= (rej_fvg_bear_count > 0)
        bear_mask &= np.isfinite(bear_entry) & np.isfinite(bear_stop) & (bear_risk > 1e-9)

        # ── 14. Decision log (section 5.5), before assembly ───────────
        # TRIGGER = the HTF FVG rejection bar (in-gap + directional close);
        # gates: CISD fired, MSS fired (when required), rejection-leg FVG
        # count (when required), and finite entry/stop geometry. Recorded
        # even when nothing qualifies.
        rec = (
            GateRecorder(exec_idx, run_id="", strategy="ict_fvg_cisd_rejection")
            .trigger(pd.Series(htf_bull_reject, index=exec_idx), "long")
            .trigger(pd.Series(htf_bear_reject, index=exec_idx), "short")
            .gate("cisd_fired",
                  pd.Series(cisd_bull_fired | cisd_bear_fired, index=exec_idx))
        )
        if require_mss:
            rec = rec.gate("mss_fired",
                            pd.Series(mss_bull_fired | mss_bear_fired,
                                      index=exec_idx))
        if require_rej_fvg:
            rec = rec.gate("rejection_fvg_present",
                            pd.Series((rej_fvg_bull_count > 0)
                                      | (rej_fvg_bear_count > 0),
                                      index=exec_idx))
        rec = rec.gate(
            "geometry_finite",
            pd.Series((np.isfinite(bull_entry) & np.isfinite(bull_stop)
                       & (bull_risk > 1e-9))
                      | (np.isfinite(bear_entry) & np.isfinite(bear_stop)
                         & (bear_risk > 1e-9))
                      | (~htf_bull_reject & ~htf_bear_reject),
                      index=exec_idx))
        self.last_decisions = rec.to_frame(signal_prefix="ifc_")

        # ── 15. Assemble output ───────────────────────────────────────
        bull_idx_arr = np.where(bull_mask)[0]
        bear_idx_arr = np.where(bear_mask)[0]

        frames = []

        if len(bull_idx_arr) > 0:
            frames.append(pd.DataFrame({
                "signal_time": exec_idx[bull_idx_arr],
                "direction": "long",
                "entry_price": bull_entry[bull_idx_arr],
                "stop_price": bull_stop[bull_idx_arr],
                "target1_price": bull_target[bull_idx_arr],
                "htf_tf": htf_tf, "ltf_tf": ltf_tf, "cisd_impl": cisd_impl,
                "entry_method": entry_method, "sl_method": sl_method, "tp_rr": tp_rr,
                "fvg_freshness": fvg_freshness,
                "fvg_fill_pct_at_rejection": htf_bull_fill[bull_idx_arr] * 100,
                "fvg_age_bars": htf_bull_age[bull_idx_arr],
                "htf_fvg_size_pct": htf_bull_size_pct[bull_idx_arr],
                "rejection_fvg_count": rej_fvg_bull_count[bull_idx_arr],
                "time_to_cisd_bars": time_to_cisd_bull[bull_idx_arr],
                "confluence_count": confluence[bull_idx_arr],
                "pre_fvg_sweep": pre_bull_sweep[bull_idx_arr],
                "day_of_week": exec_idx[bull_idx_arr].dayofweek,
            }))

        if len(bear_idx_arr) > 0:
            frames.append(pd.DataFrame({
                "signal_time": exec_idx[bear_idx_arr],
                "direction": "short",
                "entry_price": bear_entry[bear_idx_arr],
                "stop_price": bear_stop[bear_idx_arr],
                "target1_price": bear_target[bear_idx_arr],
                "htf_tf": htf_tf, "ltf_tf": ltf_tf, "cisd_impl": cisd_impl,
                "entry_method": entry_method, "sl_method": sl_method, "tp_rr": tp_rr,
                "fvg_freshness": fvg_freshness,
                "fvg_fill_pct_at_rejection": htf_bear_fill[bear_idx_arr] * 100,
                "fvg_age_bars": htf_bear_age[bear_idx_arr],
                "htf_fvg_size_pct": htf_bear_size_pct[bear_idx_arr],
                "rejection_fvg_count": rej_fvg_bear_count[bear_idx_arr],
                "time_to_cisd_bars": time_to_cisd_bear[bear_idx_arr],
                "confluence_count": confluence[bear_idx_arr],
                "pre_fvg_sweep": pre_bear_sweep[bear_idx_arr],
                "day_of_week": exec_idx[bear_idx_arr].dayofweek,
            }))

        if not frames:
            return pd.DataFrame(columns=_COLS)

        out = pd.concat(frames, ignore_index=True)
        out = out.drop_duplicates(subset=["signal_time", "direction"], keep="first")
        return out.reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        return {
            "htf_tf": ("categorical", ["15m", "1h", "1d"]),
            "ltf_tf": ("categorical", ["5m", "1m"]),
            "require_rejection_fvg": ("categorical", [True, False]),
            "cisd_impl": ("categorical", ["sweep_open", "delivery_series"]),
            "entry_method": ("categorical", ["2nd_fvg", "1st_fvg", "fvg_50pct", "cisd_close"]),
            "sl_method": ("categorical", ["swing_extreme", "htf_fvg_boundary"]),
            "tp_rr": ("categorical", [1, 2, 3]),
            "fvg_freshness": ("categorical", ["fresh", "multi"]),
            "swing_length": ("int", 3, 9),
        }

    # ── Vectorized helpers ───────────────────────────────────────────

    @staticmethod
    def _cumulative_fire(
        fire_mask: np.ndarray, ltf_index: pd.DatetimeIndex, exec_index: pd.DatetimeIndex
    ) -> np.ndarray:
        """Map LTF boolean signal to exec as cumulative 'has fired' via ffill.

        The two indexes can arrive in different resolutions (ns vs us under
        pandas 3) or tz representations, and a cross-resolution reindex
        raises. Normalize BOTH to the exec index's unit before reindexing --
        values are instants, so the mapping is unaffected.
        """
        if not fire_mask.any():
            return np.zeros(len(exec_index), dtype=bool)
        ltf = pd.DatetimeIndex(ltf_index)
        if (ltf.tz is None) != (exec_index.tz is None):
            # Make tz match: an aware frame with naive LTF (or vice versa)
            # means one side lost its localization; localize to the other.
            if exec_index.tz is not None and ltf.tz is None:
                ltf = ltf.tz_localize(exec_index.tz)
            elif exec_index.tz is None and ltf.tz is not None:
                ltf = ltf.tz_localize(None)
        ltf = ltf.as_unit(exec_index.unit)
        s = pd.Series(1, index=ltf[fire_mask])
        cum = s.cumsum().reindex(exec_index, method="ffill").fillna(0)
        return cum.values > 0

    @staticmethod
    def _count_fvgs_in_window_vec(
        fvg_df: pd.DataFrame,
        type_mask: np.ndarray,
        fvg_entry_ns: np.ndarray,
        exec_ns: np.ndarray,
    ) -> np.ndarray:
        """Vectorized: count LTF FVGs created between FVG entry time and current bar.

        Uses dual searchsorted on sorted FVG creation times — O(n log k) where
        k = number of FVGs, no intermediate Series allocation.
        """
        n = len(exec_ns)
        result = np.zeros(n, dtype=int)

        fvg_times_ns = fvg_df.index[type_mask].asi8
        if len(fvg_times_ns) == 0:
            return result

        # Count FVGs at or before each exec bar
        current_count = np.searchsorted(fvg_times_ns, exec_ns, side="right")

        # Count FVGs at or before each FVG entry time
        entry_valid = np.isfinite(fvg_entry_ns)
        entry_ns_safe = np.where(entry_valid, fvg_entry_ns, fvg_times_ns[0]).astype(np.int64)
        entry_count = np.searchsorted(fvg_times_ns, entry_ns_safe, side="right")

        result = np.maximum(current_count - entry_count, 0)
        result[~entry_valid] = 0
        return result

    @staticmethod
    def _compute_rej_fvg_entry_vec(
        fvg_df: pd.DataFrame,
        type_mask: np.ndarray,
        fvg_entry_ns: np.ndarray,
        exec_ns: np.ndarray,
        entry_method: str,
        exec_close: np.ndarray,
    ) -> np.ndarray:
        """Vectorized: compute entry price from rejection-leg FVG midpoints.

        Uses searchsorted on FVG creation times for the Nth FVG after entry.
        """
        n = len(exec_ns)
        result = exec_close.astype(float).copy()  # fallback

        fvg_times_ns = fvg_df.index[type_mask].asi8
        fvg_tops = fvg_df["fvg_top"].values[type_mask]
        fvg_bots = fvg_df["fvg_bottom"].values[type_mask]
        fvg_mids = (fvg_tops + fvg_bots) / 2

        if len(fvg_times_ns) == 0:
            return result

        entry_valid = np.isfinite(fvg_entry_ns)
        if not entry_valid.any():
            return result

        if entry_method == "1st_fvg":
            target_offset = 0
        elif entry_method == "2nd_fvg":
            target_offset = 1
        elif entry_method == "fvg_50pct":
            target_offset = -1  # last FVG in window
        else:
            return result

        entry_ns_safe = np.where(entry_valid, fvg_entry_ns, fvg_times_ns[0]).astype(np.int64)

        # searchsorted: first FVG time >= entry_ns
        start_pos = np.searchsorted(fvg_times_ns, entry_ns_safe, side="left")

        if target_offset >= 0:
            # 1st or 2nd FVG after entry
            target_pos = start_pos + target_offset
            valid_idx = target_pos < len(fvg_times_ns)
            # Fall back to 1st if 2nd doesn't exist
            fallback_pos = np.where(valid_idx, target_pos, start_pos)
            fallback_valid = fallback_pos < len(fvg_times_ns)
            clipped = np.clip(fallback_pos, 0, len(fvg_mids) - 1)
            result = np.where(
                entry_valid & fallback_valid,
                fvg_mids[clipped],
                result
            )
        else:
            # fvg_50pct: last FVG created at or before current bar AND >= entry time
            end_pos = np.searchsorted(fvg_times_ns, exec_ns, side="right") - 1
            valid_range = (end_pos >= start_pos) & entry_valid & (end_pos >= 0)
            clipped = np.clip(end_pos, 0, len(fvg_mids) - 1)
            result = np.where(
                valid_range,
                fvg_mids[clipped],
                result
            )

        return result

    @staticmethod
    def _compute_swing_stop_vec(
        exec_low: np.ndarray,
        exec_high: np.ndarray,
        fvg_entry_ns: np.ndarray,
        exec_ns: np.ndarray,
        is_long: bool,
        stop_buf: float,
    ) -> np.ndarray:
        """Vectorized: compute swing extreme stop from FVG entry to current bar.

        Uses cumulative min/max with group-id based on FVG entry time changes.
        """
        n = len(exec_ns)
        result = np.full(n, np.nan)

        entry_valid = np.isfinite(fvg_entry_ns)
        if not entry_valid.any():
            return result

        # Find exec bar position for each FVG entry time
        entry_ns_safe = np.where(entry_valid, fvg_entry_ns, exec_ns[0]).astype(np.int64)
        entry_pos = np.searchsorted(exec_ns, entry_ns_safe, side="right") - 1
        entry_pos = np.clip(entry_pos, 0, n - 1)

        # Vectorized group detection: new group when entry_pos changes AND entry_valid
        # Use np.roll to detect changes (rising edge of entry_pos differences)
        prev_entry_pos = np.roll(entry_pos, 1)
        prev_entry_pos[0] = -1
        group_changes = entry_valid & (entry_pos != prev_entry_pos)
        group_ids = np.cumsum(group_changes)

        if is_long:
            # Stop = min(low) from entry to current bar, resetting at group boundaries
            # Vectorized: groupby(group_ids).cummin() — pure pandas, zero loops
            running_min = pd.Series(exec_low).groupby(group_ids).cummin().values
            result = np.where(np.isfinite(running_min), running_min - stop_buf, np.nan)
        else:
            # Stop = max(high) from entry to current bar, resetting at group boundaries
            running_max = pd.Series(exec_high).groupby(group_ids).cummax().values
            result = np.where(np.isfinite(running_max), running_max + stop_buf, np.nan)

        return result

    # ── Data loading helpers ─────────────────────────────────────────

    def _load_fvg(
        self, tf: str, use_precomputed: bool, exec_ohlc: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """Load FVG data — pre-computed parquet or detect on-the-fly."""
        if use_precomputed and tf != "1d":
            fp = _DERIVED_ICT_DIR / f"{self.ticker}_fvg_{tf}.parquet"
            if fp.exists():
                df = pd.read_parquet(fp)
                df = df[df["fvg_type"] != 0].copy()
                return df

        rule = _TF_RULES.get(tf)
        if rule is None:
            return None
        fvg = detect_fvg(exec_ohlc, resample_rule=rule)
        fvg = fvg[fvg["fvg_type"] != 0].copy()
        return fvg

    @staticmethod
    def _resample_ohlc(ohlc: pd.DataFrame, tf: str) -> pd.DataFrame:
        """Resample 1-min OHLC to target timeframe."""
        rule = _TF_RULES.get(tf, "5min")
        return (
            ohlc[["open", "high", "low", "close", "volume"]]
            .resample(rule, origin="start_day")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )

    @staticmethod
    def _build_active_fvgs(
        fvg_df: pd.DataFrame,
        exec_index: pd.DatetimeIndex,
        freshness: str = "multi",
        exec_ohlc: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """Map FVG events to exec timeframe via np.searchsorted (fully vectorized).

        For 'fresh' mode: an FVG is invalidated once price fully fills it
        (low <= fvg_bottom for bull, high >= fvg_top for bear). Only unmitigated
        FVGs are active.
        For 'multi' mode: FVG stays active until displaced (close beyond midpoint).

        Returns DataFrame with bull_top, bull_bot, bull_create_ns,
        bear_top, bear_bot, bear_create_ns (all aligned to exec_index).
        """
        n = len(exec_index)
        exec_ns = exec_index.asi8

        bull = fvg_df[fvg_df["fvg_type"] == 1].copy()
        bear = fvg_df[fvg_df["fvg_type"] == -1].copy()

        # For 'fresh' mode, we need OHLC to check mitigation
        # For 'multi' mode, all FVGs stay active (current behavior)
        if freshness == "fresh" and exec_ohlc is not None:
            return ICTFVGCISDRejectionStrategy._build_active_fvgs_fresh(
                fvg_df, exec_index, exec_ohlc
            )

        # Default ('multi' or no OHLC): all FVGs stay active
        if not bull.empty:
            bull = bull.sort_index()
            bull_create_ns = bull.index.asi8
            bull_tops = bull["fvg_top"].values.astype(float)
            bull_bots = bull["fvg_bottom"].values.astype(float)
            pos = np.searchsorted(bull_create_ns, exec_ns, side="right") - 1
            valid = pos >= 0
            bull_top = np.where(valid, bull_tops[np.clip(pos, 0, len(bull_tops) - 1)], np.nan)
            bull_bot = np.where(valid, bull_bots[np.clip(pos, 0, len(bull_bots) - 1)], np.nan)
            bull_create = np.where(valid, bull_create_ns[np.clip(pos, 0, len(bull_create_ns) - 1)].astype(float), np.nan)
        else:
            bull_top = np.full(n, np.nan)
            bull_bot = np.full(n, np.nan)
            bull_create = np.full(n, np.nan)

        if not bear.empty:
            bear = bear.sort_index()
            bear_create_ns = bear.index.asi8
            bear_tops = bear["fvg_top"].values.astype(float)
            bear_bots = bear["fvg_bottom"].values.astype(float)
            pos = np.searchsorted(bear_create_ns, exec_ns, side="right") - 1
            valid = pos >= 0
            bear_top = np.where(valid, bear_tops[np.clip(pos, 0, len(bear_tops) - 1)], np.nan)
            bear_bot = np.where(valid, bear_bots[np.clip(pos, 0, len(bear_bots) - 1)], np.nan)
            bear_create = np.where(valid, bear_create_ns[np.clip(pos, 0, len(bear_create_ns) - 1)].astype(float), np.nan)
        else:
            bear_top = np.full(n, np.nan)
            bear_bot = np.full(n, np.nan)
            bear_create = np.full(n, np.nan)

        return pd.DataFrame({
            "bull_top": bull_top,
            "bull_bot": bull_bot,
            "bull_create_ns": bull_create,
            "bear_top": bear_top,
            "bear_bot": bear_bot,
            "bear_create_ns": bear_create,
        }, index=exec_index)

    @staticmethod
    def _build_active_fvgs_fresh(
        fvg_df: pd.DataFrame,
        exec_index: pd.DatetimeIndex,
        exec_ohlc: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build active FVGs with 'fresh' mode: invalidate once price fully fills.

        A bullish FVG is mitigated when low <= fvg_bottom (price fills the gap).
        A bearish FVG is mitigated when high >= fvg_top.

        Vectorized: uses cummin/cummax of lows/highs to find mitigation times
        in O(n) instead of O(n_fvg × n) per FVG loop.
        """
        n = len(exec_index)
        exec_ns = exec_index.asi8
        exec_low = exec_ohlc["low"].values
        exec_high = exec_ohlc["high"].values

        # Cumulative running min/max for fast mitigation lookup
        # For bull FVG created at time T with bottom B:
        #   mitigated at first bar where running_min(low)[T:] <= B
        #   = first bar where cummin_low <= B (starting from T)
        # We precompute cummin and cummax arrays
        cummin_low = np.minimum.accumulate(exec_low)
        cummax_high = np.maximum.accumulate(exec_high)

        result = {}
        for fvg_type, fvg_label, level_col, cum_arr, cmp_op in [
            (1, "bull", "fvg_bottom", cummin_low, "le"),   # bull: low <= bottom
            (-1, "bear", "fvg_top", cummax_high, "ge"),     # bear: high >= top
        ]:
            fvg_subset = fvg_df[fvg_df["fvg_type"] == fvg_type].sort_index().copy()
            top_col = "fvg_top" if fvg_type == 1 else "fvg_top"
            bot_col = "fvg_bottom" if fvg_type == 1 else "fvg_bottom"

            n_fvg = len(fvg_subset)
            top_arr = np.full(n, np.nan)
            bot_arr = np.full(n, np.nan)
            create_arr = np.full(n, np.nan)

            if n_fvg == 0:
                result[f"{fvg_label}_top"] = top_arr
                result[f"{fvg_label}_bot"] = bot_arr
                result[f"{fvg_label}_create_ns"] = create_arr
                continue

            fvg_create_ns = fvg_subset.index.asi8
            fvg_tops = fvg_subset["fvg_top"].values.astype(float)
            fvg_bots = fvg_subset["fvg_bottom"].values.astype(float)
            fvg_levels = fvg_subset[level_col].values.astype(float)  # the mitigation level

            # Compute mitigation bar for each FVG using searchsorted on cummin/cummax
            # For bull: mitigation = first bar after creation where cummin_low <= fvg_bottom
            # For bear: mitigation = first bar after creation where cummax_high >= fvg_top
            #
            # Trick: cummin_low is monotonically non-increasing.
            # For bull FVG with bottom B, we need first bar where cummin_low <= B.
            # Since cummin is non-increasing, once it drops below B it stays below.
            # So we can use searchsorted on a reversed/sorted version.
            # But cummin is non-increasing, not sorted for searchsorted.
            # Instead, use: neg_cummin = -cummin_low (non-decreasing), then searchsorted(-B)
            # For bear: cummax_high is non-decreasing, searchsorted(fvg_top, side='left')

            fvg_create_pos = np.searchsorted(exec_ns, fvg_create_ns, side="right")
            fvg_mitigation_pos = np.full(n_fvg, n, dtype=int)

            if cmp_op == "le":
                # Bull: find first bar after creation where low <= bottom
                # cummin_low is non-increasing. -cummin_low is non-decreasing.
                # first bar where cummin_low <= B  =>  first bar where -cummin_low >= -B
                # => searchsorted(-cummin_low, -B, side='left') on the non-decreasing array
                neg_cummin = -cummin_low
                for fi in range(n_fvg):
                    start = fvg_create_pos[fi]
                    if start >= n:
                        continue
                    # Search for first position >= start where neg_cummin >= -fvg_levels[fi]
                    # Since neg_cummin is non-decreasing, searchsorted works
                    pos = np.searchsorted(neg_cummin[start:], -fvg_levels[fi], side="left")
                    if pos < n - start:
                        fvg_mitigation_pos[fi] = start + pos
            else:
                # Bear: find first bar after creation where high >= top
                # cummax_high is non-decreasing. searchsorted(fvg_top, side='left')
                for fi in range(n_fvg):
                    start = fvg_create_pos[fi]
                    if start >= n:
                        continue
                    pos = np.searchsorted(cummax_high[start:], fvg_levels[fi], side="left")
                    if pos < n - start:
                        fvg_mitigation_pos[fi] = start + pos

            # Now build the active FVG array: for each exec bar, the active FVG is
            # the most recent one created before that bar AND not yet mitigated.
            # Vectorized: iterate FVGs in order, fill [create_pos, mitigation_pos) range
            for fi in range(n_fvg):
                start_pos = fvg_create_pos[fi]
                end_pos = min(fvg_mitigation_pos[fi], n)
                if start_pos < n and start_pos < end_pos:
                    top_arr[start_pos:end_pos] = fvg_tops[fi]
                    bot_arr[start_pos:end_pos] = fvg_bots[fi]
                    create_arr[start_pos:end_pos] = float(fvg_create_ns[fi])

            result[f"{fvg_label}_top"] = top_arr
            result[f"{fvg_label}_bot"] = bot_arr
            result[f"{fvg_label}_create_ns"] = create_arr

        return pd.DataFrame({
            "bull_top": result["bull_top"],
            "bull_bot": result["bull_bot"],
            "bull_create_ns": result["bull_create_ns"],
            "bear_top": result["bear_top"],
            "bear_bot": result["bear_bot"],
            "bear_create_ns": result["bear_create_ns"],
        }, index=exec_index)