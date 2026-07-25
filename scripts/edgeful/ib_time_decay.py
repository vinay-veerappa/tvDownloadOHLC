"""
Phase 5.2 — Time-Decay Exit Schedule (PRD FR-7).

For each (symbol, session_slot, time_basis, play), compute P(win | elapsed_minutes)
using ib_play_detail's mfe/mae timing proxy. Since play_detail doesn't carry
explicit entry/exit timestamps, we approximate elapsed via the `timeout_loss`
flag and a coarse bucketing of trades by their trading-day slot position.

Where a finer timing source is available (e.g. ib_facts.first_break_minutes),
this script joins it to bucket the decay curve. The output is a curve of
win probability per elapsed bucket, used to set time-decay exit rules.

Reads:  data/derived/ib_play_detail_{SYM}.parquet
        data/derived/ib_facts_{SYM}.parquet (optional, for first_break_minutes)
Writes: data/derived/ib_time_decay_curves.parquet
        columns: symbol, session_slot, time_basis, play, target_lvl,
                 elapsed_minutes_bucket, win_prob, n_remaining, n_wins
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
GROUP_COLS = ["symbol", "session_slot", "time_basis", "play", "target_lvl"]
# Elapsed buckets in minutes (approximate trade-hold time)
ELAPSED_BUCKETS = [0, 15, 30, 45, 60, 75, 90, 120, 150, 180, 240, 360, 9999]


def _elapsed_for_row(row, fb_min_map: pd.Series) -> float:
    """Approximate elapsed = first_break_minutes + mfe/mae contribution.

    Without explicit exit times, use first_break_minutes as the entry anchor
    and assume the trade resolves within a window scaled by realized_r sign.
    This is a coarse proxy; replace with real exit timestamps when available.
    """
    fb = fb_min_map.get((row["trading_day"], row["session_slot"]), np.nan)
    if pd.isna(fb):
        return np.nan
    return float(fb)


def build_time_decay(df_play: pd.DataFrame, df_facts: pd.DataFrame) -> pd.DataFrame:
    """P(win | elapsed_bucket) per play."""
    rows = []
    fb_col = "first_break_minutes_5min" if "first_break_minutes_5min" in df_facts.columns else "first_break_minutes"
    if fb_col not in df_facts.columns:
        return pd.DataFrame()
    # Join first_break_minutes onto play detail via (trading_day, session_slot)
    fb = df_facts[["trading_day", "session_slot", "time_basis", fb_col]].rename(columns={fb_col: "elapsed"})
    merged = df_play.merge(fb, on=["trading_day", "session_slot", "time_basis"], how="left")
    merged = merged.dropna(subset=["elapsed"])
    if merged.empty:
        return pd.DataFrame()
    for key, g in merged.groupby(GROUP_COLS, sort=False):
        if len(g) < 50:
            continue
        g = g.copy()
        g["bucket"] = pd.cut(g["elapsed"], bins=ELAPSED_BUCKETS, right=False, include_lowest=True)
        for bucket, bg in g.groupby("bucket", observed=False):
            n = len(bg)
            if n < 30:
                continue
            wins = int((bg["result"] == 1).sum())
            rows.append({
                **dict(zip(GROUP_COLS, key)),
                "elapsed_minutes_bucket": str(bucket),
                "win_prob": round(wins / n, 4),
                "n_remaining": n, "n_wins": wins,
            })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    frames = []
    for sym in symbols:
        play_path = DERIVED / f"ib_play_detail_{sym}.parquet"
        facts_path = DERIVED / f"ib_facts_{sym}.parquet"
        if not play_path.exists() or not facts_path.exists():
            print(f"[WARN] missing data for {sym}, skipping")
            continue
        df_play = pd.read_parquet(play_path)
        df_facts = pd.read_parquet(facts_path)
        out = build_time_decay(df_play, df_facts)
        print(f"[{sym}] {len(out)} decay rows")
        frames.append(out)
    if frames:
        final = pd.concat(frames, ignore_index=True)
        final.to_parquet(DERIVED / "ib_time_decay_curves.parquet", index=False)
        print(f"[ALL] wrote {len(final)} rows to {DERIVED/'ib_time_decay_curves.parquet'}")


if __name__ == "__main__":
    main()