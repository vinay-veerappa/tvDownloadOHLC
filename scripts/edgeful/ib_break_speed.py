"""
Phase 5.4 — Break Speed Distribution (PRD FR-7).

Compute break-speed (points/min) distribution from ib_facts and its
relationship to play outcomes by joining to ib_play_detail.

Reads:  data/derived/ib_facts_{SYM}.parquet  (ib_break_speed via derived or computed here)
        data/derived/ib_play_detail_{SYM}.parquet
Writes: data/derived/ib_break_speed_stats.parquet
        columns: symbol, session_slot, time_basis, play, target_lvl,
                 speed_bucket, n_trades, win_rate, expectancy, mean_speed
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
SPEED_BINS = [-1e9, 0, 0.5, 1.0, 2.0, 5.0, 1e9]  # pts/min buckets
SPEED_LABELS = ["no_break", "very_slow", "slow", "moderate", "fast", "very_fast"]


def build_break_speed_stats(df_facts: pd.DataFrame, df_play: pd.DataFrame) -> pd.DataFrame:
    # Compute break speed if not present
    if "ib_break_speed" not in df_facts.columns:
        bm = df_facts["first_break_minutes_5min"] if "first_break_minutes_5min" in df_facts.columns else df_facts["first_break_minutes"]
        df_facts = df_facts.assign(ib_break_speed=df_facts["range_pts"] / bm.replace(0, np.nan))
    speed = df_facts[["trading_day", "session_slot", "time_basis", "ib_break_speed"]].copy()
    speed["speed_bucket"] = pd.cut(speed["ib_break_speed"].abs(), bins=SPEED_BINS,
                                   labels=SPEED_LABELS, right=False)
    # Join speed to play detail
    merged = df_play.merge(speed, on=["trading_day", "session_slot", "time_basis"], how="left")
    rows = []
    for key, g in merged.groupby(["symbol", "session_slot", "time_basis", "play", "target_lvl", "speed_bucket"], sort=False, observed=False):
        n = len(g)
        if n < 30:
            continue
        rows.append({
            **dict(zip(["symbol", "session_slot", "time_basis", "play", "target_lvl", "speed_bucket"], key)),
            "n_trades": n,
            "win_rate": round(float((g["result"] == 1).mean()), 4),
            "expectancy": round(float(g["realized_r"].mean()), 4),
            "mean_speed": round(float(g["ib_break_speed"].abs().mean()), 4),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    frames = []
    for sym in symbols:
        facts_path = DERIVED / f"ib_facts_{sym}.parquet"
        play_path = DERIVED / f"ib_play_detail_{sym}.parquet"
        if not facts_path.exists() or not play_path.exists():
            print(f"[WARN] missing data for {sym}, skipping")
            continue
        df_facts = pd.read_parquet(facts_path)
        df_play = pd.read_parquet(play_path)
        out = build_break_speed_stats(df_facts, df_play)
        print(f"[{sym}] {len(out)} speed-bucket rows")
        frames.append(out)
    if frames:
        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(DERIVED / "ib_break_speed_stats.parquet", index=False)
        print(f"[ALL] wrote {len(final)} rows to {DERIVED/'ib_break_speed_stats.parquet'}")


if __name__ == "__main__":
    main()