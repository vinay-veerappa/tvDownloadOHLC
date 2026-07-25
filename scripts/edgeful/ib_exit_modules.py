"""
Phase 6 — IB Exit Module Signals (PRD FR-8, §10.16/§10.17).

Generates per-day exit-rule signals derived from the master confluence table.
MAE-calibrated stops (S2) come from ib_optimal_stops; trailing-by-IB-fractions
(S15), session-boundary (T15), VWAP-cross (T5), liquidity-target (T6),
partial-ladder (T4), time-decay (T14) are flagged here.

Reads:  data/derived/ib_confluence_{SYM}.parquet
        data/derived/ib_optimal_stops.parquet
        data/derived/ib_time_decay_curves.parquet
        data/derived/ib_optimal_ladders.parquet
Writes: data/derived/ib_exit_signals_{SYM}.parquet
        columns: symbol, trading_day, session_slot, time_basis,
                 stop_mae_calibrated, stop_trailing_ib_fractions,
                 exit_session_boundary, exit_vwap_cross, exit_liquidity_target,
                 exit_partial_ladder, exit_time_decay, exit_mid_magnet_fast,
                 exit_signal_count, exit_primary
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


def build_exit_signals(df: pd.DataFrame, stops: pd.DataFrame,
                       decay: pd.DataFrame, ladders: pd.DataFrame) -> pd.DataFrame:
    out = df[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    # S2 MAE-calibrated stop: is there an optimal stop row for this group?
    stop_keys = ["symbol", "session_slot", "time_basis", "play", "target_lvl"]
    # Mark stop available (any row for this symbol/session/time_basis)
    if not stops.empty:
        avail = stops.groupby(["symbol", "session_slot", "time_basis"]).size().reset_index(name="_n")
        out = out.merge(avail, on=["symbol", "session_slot", "time_basis"], how="left")
        out["stop_mae_calibrated"] = out["_n"].fillna(0) > 0
        out = out.drop(columns=["_n"])
    else:
        out["stop_mae_calibrated"] = False
    # S15 Trailing by IB fractions: always recommended (rule-based)
    out["stop_trailing_ib_fractions"] = True
    # T15 Session-boundary exit: NY AM/PM IB sessions exit by 15:50 (ADR-020)
    out["exit_session_boundary"] = df["session_slot"].isin(["NY AM IB", "NY PM IB"])
    # T5 VWAP-cross exit: requires ib_vwap to exist (Phase 2 §9.2)
    out["exit_vwap_cross"] = df.get("ib_vwap", pd.Series(np.nan, index=df.index)).notna()
    # T6 Liquidity target: requires PDH/PDL columns (daily_context join)
    has_liq = any(c in df.columns for c in ["pdh", "pdl", "p12_high", "p12_low"])
    out["exit_liquidity_target"] = has_liq
    # T4 Partial ladder: always recommended (Phase 5.3 produces per-group ladders)
    out["exit_partial_ladder"] = True
    # T14 Time-decay exit: available if decay curves exist for this group
    if not decay.empty:
        decay_groups = decay.groupby(["symbol", "session_slot", "time_basis"]).size().reset_index(name="_n")
        out = out.merge(decay_groups, on=["symbol", "session_slot", "time_basis"], how="left")
        out["exit_time_decay"] = out["_n"].fillna(0) > 0
        out = out.drop(columns=["_n"])
    else:
        out["exit_time_decay"] = False
    # T35 Mid-magnet fast exit: ib_mid_revisit_post_break_minutes < 15
    mag_min = df.get("ib_mid_revisit_post_break_minutes", pd.Series(np.nan, index=df.index))
    mag_flag = df.get("ib_mid_revisited_post_break", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    out["exit_mid_magnet_fast"] = mag_flag & (mag_min < 15)

    exit_cols = ["stop_mae_calibrated", "stop_trailing_ib_fractions",
                 "exit_session_boundary", "exit_vwap_cross", "exit_liquidity_target",
                 "exit_partial_ladder", "exit_time_decay", "exit_mid_magnet_fast"]
    out["exit_signal_count"] = out[exit_cols].sum(axis=1)
    out["exit_primary"] = "partial_ladder"  # default
    # Override to mid-magnet if fast magnet regime
    out.loc[out["exit_mid_magnet_fast"], "exit_primary"] = "mid_magnet_fast"
    out.loc[out["exit_vwap_cross"] & (out["exit_primary"] == "partial_ladder"), "exit_primary"] = "vwap_cross"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    # Load pooled Phase 5 outputs once
    stops = pd.read_parquet(DERIVED / "ib_optimal_stops.parquet") if (DERIVED / "ib_optimal_stops.parquet").exists() else pd.DataFrame()
    decay = pd.read_parquet(DERIVED / "ib_time_decay_curves.parquet") if (DERIVED / "ib_time_decay_curves.parquet").exists() else pd.DataFrame()
    ladders = pd.read_parquet(DERIVED / "ib_optimal_ladders.parquet") if (DERIVED / "ib_optimal_ladders.parquet").exists() else pd.DataFrame()
    for sym in symbols:
        path = DERIVED / f"ib_confluence_{sym}.parquet"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping {sym}")
            continue
        df = pd.read_parquet(path)
        out = build_exit_signals(df, stops, decay, ladders)
        out_path = DERIVED / f"ib_exit_signals_{sym}.parquet"
        out.to_parquet(out_path, index=False)
        print(f"[{sym}] wrote {len(out)} exit rows to {out_path}")


if __name__ == "__main__":
    main()