"""Strat unified signal engine (Pillar 1 — pure).

THE single place that turns OHLC into tradable Strat signals with FTFC.
Both the Python strategy hunters (Pillar 2: strat_strategy.py hunt()) and —
by mirror implementation — the NT8 bots (StratCore.cs) consume this logic.

Pipeline per call:
  1. Resample input (1m ET, or any base TF <= signal TF) to signal_tf.
  2. Classify signal TF + each FTFC TF + HTF trend TF (taxonomy.classify_bars_df).
  3. Scan signal TF combos (combos.StratComboDetector).
  4. Per setup: measured-move targets (targets.measured_targets),
     FTFC score at that bar (price vs TF opens), HTF bias, session/killzone
     gate (session.entry_allowed), allowed-setups + min_rr gates.
  5. Optional next-bar confirmation (no lookahead fills).

Output: canonical signal DataFrame — superset of TheStratStrategy.OUTPUT_COLUMNS:
  signal_time, direction, entry_price, stop_price, target1_price, target2_price,
  model_name, risk_pts, reward_pts, pattern,
  ftfc_score, ftfc_bias, htf_bias, stop_capped, confirmed, confirm_time
"""

from __future__ import annotations

from datetime import time
from typing import Any

import numpy as np
import pandas as pd

from scripts.libs_py.the_strat.combos import (
    ComboType,
    StratComboDetector,
    StratSetup,
    TradeDirection,
)
from scripts.libs_py.the_strat.config import StratConfig, load_strat_config
from scripts.libs_py.the_strat.session import (
    entry_allowed,
    killzones_from_config,
    parse_hhmm,
)
from scripts.libs_py.the_strat.targets import measured_targets
from scripts.libs_py.the_strat.taxonomy import StratType, classify_bars_df

_TF_ALIASES = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "60m": "60min",
    "4h": "4h",
    "D": "D",
    "W": "W",
    "M": "M",
}

OUTPUT_COLUMNS = [
    "signal_time",
    "direction",
    "entry_price",
    "stop_price",
    "target1_price",
    "target2_price",
    "model_name",
    "risk_pts",
    "reward_pts",
    "pattern",
    "ftfc_score",
    "ftfc_bias",
    "htf_bias",
    "stop_capped",
    "confirmed",
    "confirm_time",
]


def _norm_tf(tf: str) -> str:
    return _TF_ALIASES.get(tf, tf)


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    cols = {c.lower(): c for c in df.columns}
    o, h, l, c = cols["open"], cols["high"], cols["low"], cols["close"]
    out = df[[o, h, l, c]].resample(rule, origin="start_day").agg(
        {o: "first", h: "max", l: "min", c: "last"}
    )
    out.columns = ["open", "high", "low", "close"]
    return out.dropna()


def _session_opens_daily(idx: pd.DatetimeIndex, opens: pd.Series) -> pd.Series:
    """Globex-session daily open: rows before 18:00 belong to the session that
    opened 18:00 the prior day. Vectorized via date-shifted grouping."""
    # session_date = date of the 18:00 anchor this bar belongs to
    anchored = idx - pd.Timedelta(hours=18)
    sess_day = anchored.date
    s = pd.Series(opens.values, index=idx)
    first_per_sess = s.groupby(pd.Index(sess_day)).transform("first")
    return first_per_sess


class StratSignalEngine:
    """Stateless engine — construct with a StratConfig, call generate()."""

    def __init__(self, config: StratConfig | None = None, tick_size: float = 0.25):
        self.config = config or load_strat_config()
        self.tick_size = tick_size
        self.detector = StratComboDetector(tick_size=tick_size)

    # -- public ---------------------------------------------------------
    def generate(
        self,
        df: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Generate canonical signals from an OHLC DataFrame (ET-indexed)."""
        p = dict(params or {})
        cfg = self.config

        signal_tf = _norm_tf(str(p.get("timeframe", cfg.signal_tf)))
        allowed = set(p.get("allowed_setups", cfg.allowed_setups) or [])
        min_rr = float(p.get("min_rr_ratio", cfg.min_rr_ratio))
        min_tgt = float(p.get("min_target_points", cfg.min_target_points))
        max_risk = float(p.get("max_risk_points", cfg.max_risk_points))
        use_ftfc = bool(p.get("use_ftfc_filter", cfg.use_ftfc_filter))
        min_score = int(p.get("min_ftfc_score", cfg.min_ftfc_score))
        use_kz = bool(p.get("use_killzones", cfg.use_killzones))
        confirm = bool(p.get("confirm_next_bar", cfg.confirm_next_bar))
        earliest = parse_hhmm(str(p.get("earliest_entry", cfg.earliest_entry)))
        latest = parse_hhmm(str(p.get("latest_entry", cfg.latest_entry)))
        flat_by = parse_hhmm(str(p.get("flatten_by", cfg.flatten_by)))
        kz = killzones_from_config(cfg.killzones)
        tick = float(p.get("tick_size", self.tick_size))

        if df.empty or "close" not in {c.lower() for c in df.columns}:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        base = df.copy().sort_index()
        sig = _resample_ohlc(base, signal_tf)
        if len(sig) < 5:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)
        sig_cls = classify_bars_df(sig, wick_threshold=cfg.wick_threshold)

        # FTFC TF opens ffilled onto the signal index
        ftfc_tfs: list[str] = list(
            p.get("ftfc_timeframes", cfg.ftfc_timeframes) or []
        )
        tf_opens: dict[str, pd.Series] = {}
        for tf in ftfc_tfs:
            ntf = _norm_tf(tf)
            if ntf in ("D", "W", "M"):
                continue  # session-anchored below
            try:
                r = _resample_ohlc(base, ntf)
            except (ValueError, KeyError):
                continue
            tf_opens[tf] = r["open"].reindex(sig.index, method="ffill")

        # Daily session open (Globex 18:00 ET anchor)
        if any(t == "D" for t in ftfc_tfs):
            try:
                o_col = {c.lower(): c for c in base.columns}["open"]
                tf_opens["D"] = _session_opens_daily(
                    sig.index, base[o_col].reindex(sig.index, method="ffill")
                )
            except KeyError:
                pass

        # HTF trend bias series (60m strat type ffilled: 2U=+1, 2D=-1 else 0)
        htf_bias = pd.Series(0, index=sig.index, dtype=int)
        try:
            htf = classify_bars_df(_resample_ohlc(base, _norm_tf(cfg.htf_trend_tf)))
            st_htf = htf["strat_type"].reindex(sig.index, method="ffill").fillna(0)
            htf_bias = (
                (st_htf == int(StratType.TWO_UP)).astype(int)
                - (st_htf == int(StratType.TWO_DOWN)).astype(int)
            )
        except (ValueError, KeyError):
            pass

        h = sig["high"].values
        l = sig["low"].values
        o = sig["open"].values
        c = sig["close"].values

        setups: list[StratSetup] = self.detector.scan_dataframe(
            sig, min_rr_ratio=0.0  # RR gated AFTER measured targets (combos RR is structural)
        )

        rows: list[dict[str, Any]] = []
        for s in setups:
            if allowed and s.combo_type.value not in allowed:
                continue
            i = s.index
            ts = sig.index[i]
            t: time = ts.time()
            if not entry_allowed(t, earliest, latest, flat_by, kz, use_kz):
                continue

            direction = 1 if s.direction == TradeDirection.LONG else -1

            # Structural levels from the pattern (trigger bar extremes)
            if "2U-1-2U" == s.pattern_string or "2D-1-2U" == s.pattern_string or "3-1-2U" == s.pattern_string:
                inside_high, inside_low = h[i - 1], l[i - 1]
                entry = inside_high + tick
                struct_stop = inside_low - tick
                origin_open = o[i - 2]
            elif "2D-1-2D" == s.pattern_string or "2U-1-2D" == s.pattern_string or "3-1-2D" == s.pattern_string:
                inside_high, inside_low = h[i - 1], l[i - 1]
                entry = inside_low - tick
                struct_stop = inside_high + tick
                origin_open = o[i - 2]
            elif "2D-2U" == s.pattern_string:
                inside_high, inside_low = h[i - 1], l[i - 1]
                entry = inside_high + tick
                struct_stop = inside_low - tick
                origin_open = o[i - 1]
            elif "2U-2D" == s.pattern_string:
                inside_high, inside_low = h[i - 1], l[i - 1]
                entry = inside_low - tick
                struct_stop = inside_high + tick
                origin_open = o[i - 1]
            else:
                continue  # RevStrat patterns: detector does not emit yet

            prior_leg = abs(c[i] - origin_open)
            mt = measured_targets(
                direction, entry, struct_stop,
                inside_high, inside_low, prior_leg,
                min_tgt, max_risk, tick,
            )
            if mt.rr_ratio < min_rr:
                continue

            # FTFC score at this bar: price vs each TF open
            px = float(c[i])
            bull = bear = 0
            for tf, opens in tf_opens.items():
                op = opens.iloc[i]
                if op is None or (isinstance(op, float) and np.isnan(op)) or op <= 0:
                    continue
                if px > op:
                    bull += 1
                elif px < op:
                    bear += 1
            score = bull - bear
            if use_ftfc:
                if direction == 1 and score < min_score:
                    continue
                if direction == -1 and score > -min_score:
                    continue
            bias = 1 if score >= min_score else (-1 if score <= -min_score else 0)

            hb = int(htf_bias.iloc[i])

            # Next-bar confirmation (kill lookahead fills)
            confirmed = True
            confirm_time = ts
            if confirm:
                if i + 1 >= len(sig):
                    continue  # no next bar to confirm — skip, don't fabricate
                if direction == 1:
                    confirmed = bool(h[i + 1] >= entry)
                else:
                    confirmed = bool(l[i + 1] <= entry)
                if not confirmed:
                    continue
                confirm_time = sig.index[i + 1]

            rows.append(
                {
                    "signal_time": ts,
                    "direction": direction,
                    "entry_price": entry,
                    "stop_price": struct_stop,
                    "target1_price": mt.target1,
                    "target2_price": mt.target2,
                    "model_name": s.combo_type.value,
                    "risk_pts": mt.risk_points,
                    "reward_pts": mt.reward_points,
                    "pattern": s.pattern_string,
                    "ftfc_score": score,
                    "ftfc_bias": bias,
                    "htf_bias": hb,
                    "stop_capped": mt.stop_capped,
                    "confirmed": confirmed,
                    "confirm_time": confirm_time,
                }
            )

        if not rows:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)
        return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
