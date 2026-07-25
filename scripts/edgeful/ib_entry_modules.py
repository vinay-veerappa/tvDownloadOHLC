"""
Phase 6 — IB Entry Module Signals (PRD FR-8, §10.15).

Generates per-day entry signals for each entry technique in §10.15 that is
derivable from the master confluence table (scale-in, time-qualified, 80%-rule,
failed-breakout, opening-drive, pre-IB telegraph, sweep+reclaim, body-close,
wick-dominant fade, ACD hold, VCP setup, single-print reclaim).

Two-timeframe (E7) and delta/CVD entries (E19/E20) require data not in the
confluence table and are stubbed as NaN — see PRD §3.1 Tier-3 gating.

Reads:  data/derived/ib_confluence_{SYM}.parquet
Writes: data/derived/ib_entry_signals_{SYM}.parquet
        columns: symbol, trading_day, session_slot, time_basis,
                 entry_scale_in, entry_time_qualified_size,
                 entry_80_rule_long, entry_80_rule_short,
                 entry_failed_breakout_rev, entry_opening_drive,
                 entry_pre_telegraph, entry_sweep_reclaim_long,
                 entry_sweep_reclaim_short, entry_body_close_break,
                 entry_wick_dominant_fade, entry_acd_hold,
                 entry_vcp_setup, entry_single_print_reclaim,
                 entry_signal_count, entry_primary
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


def _time_qualified_size(break_min) -> float:
    """E6: full/half/skip sizing by first-break bucket."""
    if pd.isna(break_min):
        return np.nan
    if break_min <= 15:    return 1.0   # 10:30-10:45 full
    if break_min <= 75:    return 0.5   # 10:45-11:30 half
    if break_min <= 210:   return 0.0   # 11:30-13:00 skip
    if break_min <= 270:   return 0.5   # 13:00-14:30 half
    return 0.0                      # late skip


def build_entry_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    fb_dir = df.get("first_break_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)

    # E5 Scale-in ladder (always "active" — the ladder config is in Phase 5.3)
    out["entry_scale_in"] = 1
    # E6 Time-qualified size
    bm = df.get("first_break_minutes_5min", df.get("first_break_minutes", pd.Series(np.nan, index=df.index)))
    out["entry_time_qualified_size"] = bm.apply(_time_qualified_size)
    # E11 80% rule: >80% time above mid → long after high break; <20% → short
    pct = df.get("ib_pct_time_above_mid", pd.Series(np.nan, index=df.index))
    out["entry_80_rule_long"] = (pct > 0.80) & (fb_dir == 1)
    out["entry_80_rule_short"] = (pct < 0.20) & (fb_dir == -1)
    # E8 Failed-breakout reversal: high/low swept but close back inside
    out["entry_failed_breakout_rev"] = df.get("ib_high_swept", False) | df.get("ib_low_swept", False)
    # E9 Opening drive: OR5 broke within 15 min
    or5 = df.get("ib_or5_broken_in_15", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    out["entry_opening_drive"] = or5
    # E10 Pre-IB telegraph direction != 0
    tel = df.get("ib_pre_telegraph_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    out["entry_pre_telegraph"] = tel != 0
    # E15 Sweep + reclaim (long on low sweep, short on high sweep)
    sweep_dir = df.get("ib_sweep_reclaim_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    out["entry_sweep_reclaim_long"] = sweep_dir == 1
    out["entry_sweep_reclaim_short"] = sweep_dir == -1
    # E17 Body-close break (extreme accepted)
    out["entry_body_close_break"] = df.get("ib_high_body_close", False) | df.get("ib_low_body_close", False)
    # E18 Wick-dominant fade
    out["entry_wick_dominant_fade"] = (df.get("ib_high_wick_pct", pd.Series(0, index=df.index)) > 20) | \
                                      (df.get("ib_low_wick_pct", pd.Series(0, index=df.index)) > 20)
    # E12 ACD hold
    out["entry_acd_hold"] = df.get("ib_or_acd_a_held", False)
    # E13 VCP setup
    out["entry_vcp_setup"] = df.get("ib_vcp_setup", False)
    # E14 Single-print reclaim (upper single print present)
    out["entry_single_print_reclaim"] = df.get("ib_has_upper_single_print", False) | \
                                         df.get("ib_has_lower_single_print", False)
    # E22 CISD confirmation (Change in State of Delivery) — per CISD document
    # Bullish CSD = price traded up through the last down-close candle's open
    # Bearish CSD = price traded down through the last up-close candle's open
    # These serve as entry CONFIRMATION for breakout/reversal strategies.
    cisd_dir = df.get("ib_cisd_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    out["entry_cisd_bull_confirm"] = cisd_dir == 1
    out["entry_cisd_bear_confirm"] = cisd_dir == -1
    # CISD + break confluence: CSD direction agrees with first_break_dir
    fb_dir2 = df.get("first_break_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    out["entry_cisd_break_confluence"] = (cisd_dir != 0) & (cisd_dir == fb_dir2)
    # CISD inversion (failed CSD → opposite-direction signal)
    out["entry_cisd_inversion"] = df.get("ib_cisd_inversion", False)

    # Entry count + primary (the highest-confidence active entry)
    entry_cols = [c for c in out.columns if c.startswith("entry_") and c not in ("entry_scale_in", "entry_time_qualified_size", "entry_signal_count", "entry_primary")]
    out["entry_signal_count"] = out[entry_cols].sum(axis=1)
    # Primary = first active entry in priority order
    priority = ["entry_cisd_break_confluence", "entry_80_rule_long", "entry_80_rule_short", "entry_sweep_reclaim_long",
                "entry_sweep_reclaim_short", "entry_vcp_setup", "entry_failed_breakout_rev",
                "entry_acd_hold", "entry_opening_drive", "entry_pre_telegraph",
                "entry_single_print_reclaim", "entry_body_close_break", "entry_wick_dominant_fade",
                "entry_cisd_bull_confirm", "entry_cisd_bear_confirm"]
    out["entry_primary"] = ""
    for c in priority:
        if c in out.columns:
            mask = out[c].astype(bool) & (out["entry_primary"] == "")
            out.loc[mask, "entry_primary"] = c
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
        out = build_entry_signals(df)
        out_path = DERIVED / f"ib_entry_signals_{sym}.parquet"
        out.to_parquet(out_path, index=False)
        print(f"[{sym}] wrote {len(out)} entry rows to {out_path}")
        if len(out):
            print(f"  signal counts: mean={out.entry_signal_count.mean():.2f}, max={out.entry_signal_count.max()}")


if __name__ == "__main__":
    main()