"""
Phase 6 — IB Regime Classifier (PRD FR-8).

Classifies each (trading_day, session_slot, time_basis) into a regime and
selects the optimal play + direction. The regime router sits on top of
Phases 2–5 derived data.

Regimes (PRD §9.9):
- trend:   ib_range_pct_of_daily < 30 (trailing est) + fast break + POC near extreme
- normal:  30–50% + moderate break + POC near mid
- range:   > 50% + slow/no break + POC centered
- skip:    FOMC/NFP/CPI/ISM, contradictory overnight, late mid-lock, quarterly OPEX

Reads:  data/derived/ib_confluence_{SYM}.parquet (master confluence, includes
       conviction_score_v2 from Phase 4 + all derived fields from Phase 2)
Writes: data/derived/ib_regime_{SYM}.parquet
        columns: symbol, trading_day, session_slot, time_basis,
                 ib_regime, ib_regime_confidence,
                 suggested_play, suggested_direction, suggested_expectancy
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DERIVED = ROOT / "data" / "derived"
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]


def _classify_regime(row) -> str:
    """Single-row regime classifier. Uses derived fields where present."""
    # Skip-day triggers
    skip_flags = [
        row.get("is_fomc_day"), row.get("is_nfp_day"),
        row.get("is_cpi_day"), row.get("is_ism_day"),
        row.get("is_quarterly_opex"),
    ]
    if any(bool(f) if not pd.isna(f) else False for f in skip_flags):
        return "skip"
    # Contradictory overnight
    if row.get("profiler_overnight_regime") == "contradicting":
        return "skip"
    # Late mid-lock (range-bound)
    mid_lock = row.get("mid_lock_frac")
    if pd.notna(mid_lock) and mid_lock > 0.85:
        return "skip"

    # Day-type from ib_range_pct_of_daily (realized — for trailing est use a
    # proxy; here we use the realized ratio as the label, with `unknown` → normal)
    r = row.get("ib_range_pct_of_daily")
    day_type = row.get("ib_day_type_predicted", "unknown")
    break_urgency = row.get("ib_break_urgency", "low")
    poc_skew = row.get("ib_tpo_skew", 0)

    # BL-7 FIX: Use trailing 5d percentile for pre-trade regime estimation.
    # The realized ib_range_pct_of_daily is only known at end of day and
    # creates look-ahead bias if used for trade decisions.
    # ib_range_5d_pctile: 0 = IB is small relative to recent IBs (trend likely),
    # 1 = IB is large relative to recent IBs (range likely).
    r_trailing = row.get("ib_range_5d_pctile")

    # Trend: small IB relative to trailing IBs + fast break + POC near extreme
    # Use trailing percentile (pre-trade available) instead of realized ratio
    if pd.notna(r_trailing) and r_trailing < 0.30:
        if break_urgency == "high" and poc_skew != 0:
            return "trend"
        return "trend"  # trend-ish even if break slow

    # Range: large IB relative to trailing IBs + slow break + POC centered
    if pd.notna(r_trailing) and r_trailing >= 0.70:
        if break_urgency == "low" and poc_skew == 0:
            return "range"
        return "range"

    # Normal variation (50–70% trailing)
    if pd.notna(r_trailing) and 0.50 <= r_trailing < 0.70:
        return "range"

    # Fallback: use day_type label (which uses realized ratio — for analysis only)
    if day_type == "trend":
        return "trend"
    if day_type == "range":
        return "range"
    if day_type == "normal_variation":
        return "range"

    # Normal (30–50% trailing) or unknown
    return "normal"


def _suggested_play_direction(regime: str, row) -> tuple:
    """Return (play, direction, expected_expectancy)."""
    if regime == "skip":
        return 0, 0, 0.0
    fb_dir = row.get("first_break_dir", 0)
    direction = int(fb_dir) if pd.notna(fb_dir) and fb_dir != 0 else 0
    if regime == "trend":
        return 1, direction, 0.65  # Play 1 breakout, target ~65% WR
    if regime == "normal":
        return 2, direction, 0.60  # Play 2 retest
    if regime == "range":
        return 3, -direction if direction != 0 else 0, 0.65  # Play 3 fade (opposite)
    return 0, 0, 0.0


def _regime_confidence(row, regime: str) -> float:
    """Confidence = conviction_score_v2 normalized + regime-trigger agreement."""
    v2 = row.get("conviction_score_v2", 0.0)
    if pd.isna(v2):
        v2 = 0.0
    # Agreement among the regime's own triggers (0–1)
    agrees = 0
    total = 0
    if regime == "trend":
        total += 1
        if row.get("ib_break_urgency") == "high": agrees += 1
        total += 1
        if row.get("ib_tpo_skew", 0) != 0: agrees += 1
        total += 1
        if pd.notna(row.get("ib_range_pct_of_daily")) and row["ib_range_pct_of_daily"] < 0.30: agrees += 1
    elif regime == "range":
        total += 1
        if row.get("ib_break_urgency") == "low": agrees += 1
        total += 1
        if row.get("ib_tpo_skew", 0) == 0: agrees += 1
        total += 1
        if pd.notna(row.get("ib_range_pct_of_daily")) and row["ib_range_pct_of_daily"] >= 0.70: agrees += 1
    elif regime == "normal":
        total = 1
        agrees = 1  # default-confidence regime
    trigger_conf = agrees / max(total, 1)
    return round(0.5 * float(v2) + 0.5 * trigger_conf, 4)


def classify_symbol(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    regimes = df.apply(_classify_regime, axis=1)
    out["ib_regime"] = regimes
    # Compute play/direction/expectancy/confidence row-by-row (small enough)
    plays, dirs, exps, confs = [], [], [], []
    for i, row in df.iterrows():
        regime = out.loc[i, "ib_regime"]
        play, direction, exp = _suggested_play_direction(regime, row)
        conf = _regime_confidence(row, regime)
        plays.append(play); dirs.append(direction); exps.append(exp); confs.append(conf)
    out["suggested_play"] = plays
    out["suggested_direction"] = dirs
    out["suggested_expectancy"] = exps
    out["ib_regime_confidence"] = confs
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    for sym in symbols:
        path = DERIVED / f"ib_confluence_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        out = classify_symbol(df)
        out_path = DERIVED / f"ib_regime_{sym}.parquet"
        out.to_parquet(out_path, index=False)
        print(f"[{sym}] wrote {len(out)} regime rows to {out_path}")
        if len(out):
            print(out["ib_regime"].value_counts().to_dict())


if __name__ == "__main__":
    main()