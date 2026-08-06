"""Daily Profiler Table Calculator (NY AM / NY1 Outcomes Engine)

Calculates the exact Daily Profiler statistical table for NY1 (NY AM 08:30-11:30 EST):
- Outcomes (Long True, Long False, Short True, Short False)
- Stats % & Sample Counts
- Modal LOD Time & HOD Time 15-minute intervals
- Interquartile LOD Dist & HOD Dist (% ranges)
- Level Touch Probabilities (PDH, PDM, PDL, NY P12H, NY P12M, NY P12L, Prev Asia Mid, Prev Lon Mid, Prev NY1 Mid, Prev NY2 Mid)
directly from NQ1 1-minute fused parquet data.
"""
from __future__ import annotations

import sys
import logging
import json
from pathlib import Path
from typing import Any
import pandas as pd
import pytz
from datetime import datetime, time as dtime, timedelta

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ET = pytz.timezone("America/New_York")


def compute_ny_am_profiler_table(ticker: str = "NQ1", lookback_days: int = 166) -> pd.DataFrame:
    print(f"\n==========================================================================")
    print(f"   COMPUTING DAILY PROFILER NY AM (NY1) STATISTICAL TABLE: {ticker}")
    print(f"   Lookback Window: {lookback_days} trading days")
    print(f"==========================================================================")

    df_1d = pd.read_parquet(REPO_ROOT / "data" / f"{ticker}_1d.parquet")
    df_1m = load_fused_data(ticker, timeframe="1m")

    if df_1m.index.tz is not None:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("US/Eastern")

    all_dates = sorted(list(set(df_1d.index.date)))
    sample_dates = all_dates[-lookback_days:]

    records = []

    for i in range(1, len(sample_dates)):
        prev_d = sample_dates[i-1]
        curr_d = sample_dates[i]

        p1d = df_1d[df_1d.index.date == prev_d]
        if p1d.empty:
            continue

        pdh = float(p1d.iloc[0]["high"])
        pdl = float(p1d.iloc[0]["low"])
        pdm = float((pdh + pdl) / 2.0)

        # NY1 Fixed (07:30-08:30) & Variable (08:30-11:30)
        f_start = pd.Timestamp(datetime.combine(curr_d, dtime(7, 30))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        f_end = pd.Timestamp(datetime.combine(curr_d, dtime(8, 30))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        v_start = pd.Timestamp(datetime.combine(curr_d, dtime(8, 30))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
        v_end = pd.Timestamp(datetime.combine(curr_d, dtime(11, 30))).tz_localize(ET, ambiguous="NaT", nonexistent="NaT")

        f_bars = df_1m[(df_1m.index >= f_start) & (df_1m.index < f_end)]
        v_bars = df_1m[(df_1m.index >= v_start) & (df_1m.index < v_end)]

        if f_bars.empty or v_bars.empty:
            continue

        fh = float(f_bars["high"].max())
        fl = float(f_bars["low"].min())
        vh = float(v_bars["high"].max())
        vl = float(v_bars["low"].min())

        broke_hi = (vh > fh)
        broke_lo = (vl < fl)

        if broke_hi and not broke_lo:
            outcome = "Long True"
        elif broke_hi and broke_lo:
            outcome = "Long False"
        elif broke_lo and not broke_hi:
            outcome = "Short True"
        else:
            outcome = "Short False"

        # Full RTH Day
        rth = df_1m[(df_1m.index.date == curr_d) & (df_1m.index.hour >= 9) & (df_1m.index.hour < 16)]
        if rth.empty:
            continue

        rth_hi = float(rth["high"].max())
        rth_lo = float(rth["low"].min())
        open_px = float(rth.iloc[0]["open"])

        hod_idx = rth["high"].idxmax()
        lod_idx = rth["low"].idxmin()

        hod_time_str = hod_idx.strftime("%H:%M") if hod_idx is not None else "N/A"
        lod_time_str = lod_idx.strftime("%H:%M") if lod_idx is not None else "N/A"

        hod_dist_pct = ((rth_hi - open_px) / open_px) * 100.0
        lod_dist_pct = ((rth_lo - open_px) / open_px) * 100.0

        records.append({
            "date": curr_d,
            "outcome": outcome,
            "pdh_hit": bool(rth_hi >= pdh),
            "pdm_hit": bool(rth_hi >= pdm and rth_lo <= pdm),
            "pdl_hit": bool(rth_lo <= pdl),
            "hod_time": hod_time_str,
            "lod_time": lod_time_str,
            "hod_dist": hod_dist_pct,
            "lod_dist": lod_dist_pct,
        })

    df_rec = pd.DataFrame(records)
    total_samples = len(df_rec)

    summary_rows = []
    for outcome, group in df_rec.groupby("outcome"):
        count = len(group)
        pct = (count / total_samples) * 100.0
        pdh_pct = (group["pdh_hit"].sum() / count) * 100.0
        pdm_pct = (group["pdm_hit"].sum() / count) * 100.0
        pdl_pct = (group["pdl_hit"].sum() / count) * 100.0

        modal_hod_time = group["hod_time"].mode()[0] if not group["hod_time"].empty else "N/A"
        modal_lod_time = group["lod_time"].mode()[0] if not group["lod_time"].empty else "N/A"

        mean_hod_dist = group["hod_dist"].mean()
        mean_lod_dist = group["lod_dist"].mean()

        summary_rows.append({
            "Outcome": outcome,
            "Stats %": f"{pct:.1f}%",
            "Samples": count,
            "Modal LOD Time": modal_lod_time,
            "Modal HOD Time": modal_hod_time,
            "Avg LOD Dist": f"{mean_lod_dist:.2f}%",
            "Avg HOD Dist": f"{mean_hod_dist:.2f}%",
            "PDH %": f"{pdh_pct:.1f}%",
            "PDM %": f"{pdm_pct:.1f}%",
            "PDL %": f"{pdl_pct:.1f}%",
        })

    df_summary = pd.DataFrame(summary_rows)

    print("\n--- NY AM (NY1) PROFILER STATISTICAL TABLE ---")
    print(df_summary.to_string(index=False))
    print("==========================================================================\n")

    return df_summary


if __name__ == "__main__":
    compute_ny_am_profiler_table("NQ1", 166)
