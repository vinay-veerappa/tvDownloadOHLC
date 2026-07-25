"""
Phase 6 — IB Pre-Break Signals (PRD FR-8, strategy #17/#63/#64).

Generates pre-break signals from the contraction/expansion cycle and the
Minervini VCP setup. These anticipate the break rather than waiting for it.

Reads:  data/derived/ib_confluence_{SYM}.parquet
Writes: data/derived/ib_pre_break_signals_{SYM}.parquet
        columns: symbol, trading_day, session_slot, time_basis,
                 pre_break_5day_contraction, pre_break_vcp_setup,
                 pre_break_vcp_volume_dry_up, pre_break_active,
                 pre_break_direction, pre_break_confidence
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


def build_pre_break(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    # 5-day contraction (strategy #17): ib_range_5d_contracting flag
    contract = df.get("ib_range_5d_contracting", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    out["pre_break_5day_contraction"] = contract
    # VCP 3-day contracting (strategy #63)
    vcp_contract = df.get("ib_vcp_3day_contracting", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    # VCP volume dry-up (strategy #64): volume ratio < 0.6
    vol_ratio = df.get("ib_vcp_volume_ratio", pd.Series(np.nan, index=df.index))
    vol_dry_up = (vol_ratio < 0.6).fillna(False)
    out["pre_break_vcp_setup"] = df.get("ib_vcp_setup", False)
    out["pre_break_vcp_volume_dry_up"] = vol_dry_up
    # Active = any contraction signal (5d or VCP)
    out["pre_break_active"] = contract | vcp_contract | out["pre_break_vcp_setup"]
    # Direction from pre-IB telegraph (§9.8) or open drive
    tel = df.get("ib_pre_telegraph_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    drive = df.get("ib_open_drive_dir", pd.Series(0, index=df.index)).fillna(0).astype(int)
    # Combine: telegraph wins, else drive
    out["pre_break_direction"] = np.where(tel != 0, tel, drive)
    # Confidence: number of contraction signals agreeing (0–3)
    out["pre_break_confidence"] = (
        contract.astype(int) + vcp_contract.astype(int) + vol_dry_up.astype(int)
    )
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
        out = build_pre_break(df)
        out_path = DERIVED / f"ib_pre_break_signals_{sym}.parquet"
        out.to_parquet(out_path, index=False)
        active = int(out["pre_break_active"].sum())
        print(f"[{sym}] wrote {len(out)} rows; pre-break active: {active} days")


if __name__ == "__main__":
    main()