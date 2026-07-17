"""Benchmark pandas vs polars for profiler data pipeline operations."""
import sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import json
import time
import pandas as pd
import polars as pl
import numpy as np

DATA_DIR = _REPO / "data"

# ── Test 1: Load profiler JSON → filter → pivot ──────────────────────

def bench_json_pipeline():
    """Simulates ProfilerService.apply_filters() pipeline."""
    json_path = DATA_DIR / "NQ1_profiler.json"
    with open(json_path) as f:
        sessions = json.load(f)
    print(f"\n{'='*60}")
    print(f"Test 1: JSON → filter → pivot ({len(sessions)} session records)")
    print(f"{'='*60}")

    # ── Pandas ──
    t0 = time.perf_counter()
    df = pd.DataFrame(sessions)
    # Pivot: date x session → status
    status_pivot = df.pivot_table(
        index="date", columns="session", values="status", aggfunc="last"
    )
    broken_pivot = df.pivot_table(
        index="date", columns="session", values="broken", aggfunc="last"
    )
    # Add prev-day shifts
    for s in ["NY1", "NY2", "Asia"]:
        if s in status_pivot.columns:
            status_pivot[f"Prev {s}"] = status_pivot[s].shift(1)
    # Filter: Asia == "Long True"
    mask = status_pivot["Asia"].fillna("") == "Long True"
    matched = status_pivot.index[mask].tolist()
    t_pd = time.perf_counter() - t0
    print(f"  Pandas:  {t_pd*1000:.1f} ms  (matched {len(matched)} dates)")

    # ── Polars ──
    t0 = time.perf_counter()
    pl_df = pl.DataFrame(sessions)
    # Pivot
    status_pivot_pl = pl_df.pivot(
        index="date", columns="session", values="status",
        aggregate_function="last"
    )
    broken_pivot_pl = pl_df.pivot(
        index="date", columns="session", values="broken",
        aggregate_function="last"
    )
    # Add prev-day shifts
    for s in ["NY1", "NY2", "Asia"]:
        if s in status_pivot_pl.columns:
            status_pivot_pl = status_pivot_pl.with_columns(
                pl.col(s).shift(1).alias(f"Prev {s}")
            )
    # Filter
    matched_pl = status_pivot_pl.filter(
        pl.col("Asia").fill_null("") == "Long True"
    )["date"].to_list()
    t_pl = time.perf_counter() - t0
    print(f"  Polars:  {t_pl*1000:.1f} ms  (matched {len(matched_pl)} dates)")
    print(f"  Speedup: {t_pd/t_pl:.1f}x")

    return t_pd, t_pl


# ── Test 2: 1m OHLC → box status computation ─────────────────────────

def bench_box_status():
    """Simulates session_box_status.compute_box_status() on 1m data."""
    print(f"\n{'='*60}")
    print(f"Test 2: 1m OHLC → box status (vectorized breakout detection)")
    print(f"{'='*60}")

    # Load 7 days of 1m data (~10K rows)
    live_path = DATA_DIR / "live" / "live_storage_-NQ.parquet"
    df_raw = pd.read_parquet(live_path)
    if "timestamp" in df_raw.columns:
        df_raw["datetime"] = pd.to_datetime(df_raw["timestamp"], unit="s", utc=True)
        df_raw = df_raw.set_index("datetime")
    df_raw = df_raw.tail(10080)  # 7 days

    # Normalize to ET
    if df_raw.index.tz is None:
        df_raw.index = df_raw.index.tz_localize("UTC").tz_convert("US/Eastern")
    elif str(df_raw.index.tz) != "US/Eastern":
        df_raw.index = df_raw.index.tz_convert("US/Eastern")

    print(f"  Rows: {len(df_raw)} | Range: {df_raw.index[0]} → {df_raw.index[-1]}")

    # ── Pandas ──
    t0 = time.perf_counter()
    et_df = df_raw.copy()
    dates = et_df.index.date
    times = et_df.index.time

    # Simulate Asia box status computation
    from datetime import time as dt_time
    start_t = dt_time(19, 30)
    end_t = dt_time(2, 30)

    # Time mask
    time_mask = (times >= start_t) | (times < end_t)

    # Box high/low (simplified: use daily resample)
    daily_high = et_df["high"].resample("D").max()
    daily_low = et_df["low"].resample("D").min()
    bh = daily_high.reindex(et_df.index.date, method=None)
    bl = daily_low.reindex(et_df.index.date, method=None)
    # Forward-fill to align
    bh = pd.Series(bh.values, index=et_df.index).ffill()
    bl = pd.Series(bl.values, index=et_df.index).ffill()

    broke_high = (et_df["high"] > bh) & time_mask
    broke_low = (et_df["low"] < bl) & time_mask

    # Group by trading date
    pm_mask = times >= start_t
    groups = pd.Series(dates, index=et_df.index)
    groups.loc[pm_mask] = groups.loc[pm_mask] + pd.Timedelta(days=1)

    h_triggers = et_df.index[broke_high].to_series().groupby(groups[broke_high]).min()
    l_triggers = et_df.index[broke_low].to_series().groupby(groups[broke_low]).min()

    unique_groups = np.unique(groups.values)
    status_series = pd.Series("None", index=unique_groups)
    triggered_h = h_triggers.reindex(unique_groups)
    triggered_l = l_triggers.reindex(unique_groups)
    has_h = triggered_h.notna()
    has_l = triggered_l.notna()
    first_h = has_h & (~has_l | (triggered_h < triggered_l))
    first_l = has_l & (~has_h | (triggered_l < triggered_h))
    status_series.loc[first_h & ~has_l] = "LT"
    status_series.loc[first_h & has_l] = "LF"
    status_series.loc[first_l & ~has_h] = "ST"
    status_series.loc[first_l & has_h] = "SF"
    result_pd = status_series.reindex(groups.values).values
    t_pd = time.perf_counter() - t0
    unique_statuses = pd.Series(result_pd).value_counts().to_dict()
    print(f"  Pandas:  {t_pd*1000:.1f} ms  (statuses: {unique_statuses})")

    # ── Polars ──
    t0 = time.perf_counter()
    pl_df = pl.from_pandas(df_raw.reset_index())
    pl_df = pl_df.rename({"datetime": "dt"})

    # Time components
    pl_df = pl_df.with_columns([
        pl.col("dt").dt.date().alias("date"),
        pl.col("dt").dt.time().alias("time"),
    ])

    # Time mask
    pl_df = pl_df.with_columns(
        ((pl.col("time") >= start_t) | (pl.col("time") < end_t)).alias("time_mask")
    )

    # Daily high/low
    daily_hl = pl_df.group_by("date").agg([
        pl.col("high").max().alias("day_high"),
        pl.col("low").min().alias("day_low"),
    ])
    pl_df = pl_df.join(daily_hl, on="date")

    # Breakout detection
    pl_df = pl_df.with_columns([
        (pl.col("high") > pl.col("day_high")).cast(pl.Boolean).alias("broke_high"),
        (pl.col("low") < pl.col("day_low")).cast(pl.Boolean).alias("broke_low"),
    ])
    pl_df = pl_df.with_columns([
        (pl.col("broke_high") & pl.col("time_mask")).alias("bh_active"),
        (pl.col("broke_low") & pl.col("time_mask")).alias("bl_active"),
    ])

    # Trading groups (Asia wraps midnight)
    pl_df = pl_df.with_columns(
        pl.when(pl.col("time") >= start_t)
        .then(pl.col("date").cast(pl.Date) + pl.duration(days=1))
        .otherwise(pl.col("date").cast(pl.Date))
        .alias("trading_date")
    )

    # First trigger per group
    h_first = (
        pl_df.filter(pl.col("bh_active"))
        .group_by("trading_date")
        .agg(pl.col("dt").min().alias("h_time"))
    )
    l_first = (
        pl_df.filter(pl.col("bl_active"))
        .group_by("trading_date")
        .agg(pl.col("dt").min().alias("l_time"))
    )

    # Status logic
    all_dates = pl_df.select("trading_date").unique()
    status_pl = (
        all_dates
        .join(h_first, on="trading_date", how="left")
        .join(l_first, on="trading_date", how="left")
        .with_columns([
            pl.col("h_time").is_not_null().alias("has_h"),
            pl.col("l_time").is_not_null().alias("has_l"),
        ])
        .with_columns([
            (pl.col("has_h") & (~pl.col("has_l") | (pl.col("h_time") < pl.col("l_time")))).alias("first_h"),
            (pl.col("has_l") & (~pl.col("has_h") | (pl.col("l_time") < pl.col("h_time")))).alias("first_l"),
        ])
        .with_columns(
            pl.when(pl.col("first_h") & ~pl.col("has_l")).then(pl.lit("LT"))
            .when(pl.col("first_h") & pl.col("has_l")).then(pl.lit("LF"))
            .when(pl.col("first_l") & ~pl.col("has_h")).then(pl.lit("ST"))
            .when(pl.col("first_l") & pl.col("has_h")).then(pl.lit("SF"))
            .otherwise(pl.lit("None"))
            .alias("status")
        )
    )
    result_pl = status_pl["status"].to_list()
    t_pl = time.perf_counter() - t0
    from collections import Counter
    unique_pl = dict(Counter(result_pl))
    print(f"  Polars:  {t_pl*1000:.1f} ms  (statuses: {unique_pl})")
    print(f"  Speedup: {t_pd/t_pl:.1f}x")

    return t_pd, t_pl


# ── Test 3: Large-scale aggregation (simulating get_filtered_stats) ──

def bench_aggregation():
    """Simulates ProfilerService.get_filtered_stats() aggregation."""
    json_path = DATA_DIR / "NQ1_profiler.json"
    with open(json_path) as f:
        sessions = json.load(f)

    print(f"\n{'='*60}")
    print(f"Test 3: Aggregation — group by date+session, compute stats")
    print(f"{'='*60}")

    # ── Pandas ──
    t0 = time.perf_counter()
    df = pd.DataFrame(sessions)
    # Distribution by session
    dist = df.groupby("session")["status"].value_counts().unstack(fill_value=0)
    # Range stats
    range_stats = df.groupby("session").agg(
        high_median=("high_pct", "median"),
        low_median=("low_pct", "median"),
        high_mean=("high_pct", "mean"),
        low_mean=("low_pct", "mean"),
    )
    # Broken rate
    broken_rate = df.groupby("session")["broken"].mean()
    t_pd = time.perf_counter() - t0
    print(f"  Pandas:  {t_pd*1000:.1f} ms")

    # ── Polars ──
    t0 = time.perf_counter()
    pl_df = pl.DataFrame(sessions)
    dist_pl = pl_df.group_by("session", "status").len().pivot(
        index="session", columns="status", values="len"
    )
    range_pl = pl_df.group_by("session").agg([
        pl.col("high_pct").median().alias("high_median"),
        pl.col("low_pct").median().alias("low_median"),
        pl.col("high_pct").mean().alias("high_mean"),
        pl.col("low_pct").mean().alias("low_mean"),
    ])
    broken_pl = pl_df.group_by("session").agg(
        pl.col("broken").mean().alias("broken_rate")
    )
    t_pl = time.perf_counter() - t0
    print(f"  Polars:  {t_pl*1000:.1f} ms")
    print(f"  Speedup: {t_pd/t_pl:.1f}x")

    return t_pd, t_pl


# ── Test 4: Parquet read ─────────────────────────────────────────────

def bench_parquet_read():
    """Compare parquet read speed."""
    live_path = DATA_DIR / "live" / "live_storage_-NQ.parquet"

    print(f"\n{'='*60}")
    print(f"Test 4: Parquet read (live_storage_-NQ.parquet)")
    print(f"{'='*60}")

    file_size_mb = live_path.stat().st_size / 1e6

    t0 = time.perf_counter()
    df_pd = pd.read_parquet(live_path)
    t_pd = time.perf_counter() - t0
    print(f"  Pandas:  {t_pd*1000:.1f} ms  ({file_size_mb:.1f} MB → {len(df_pd)} rows)")

    t0 = time.perf_counter()
    df_pl = pl.read_parquet(live_path)
    t_pl = time.perf_counter() - t0
    print(f"  Polars:  {t_pl*1000:.1f} ms  ({file_size_mb:.1f} MB → {len(df_pl)} rows)")
    print(f"  Speedup: {t_pd/t_pl:.1f}x")

    return t_pd, t_pl


# ── Run all ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = {}

    try:
        t_pd, t_pl = bench_json_pipeline()
        results["json_pivot_filter"] = (t_pd, t_pl)
    except Exception as e:
        print(f"  SKIP: {e}")

    try:
        t_pd, t_pl = bench_box_status()
        results["box_status_1m"] = (t_pd, t_pl)
    except Exception as e:
        print(f"  SKIP: {e}")

    try:
        t_pd, t_pl = bench_aggregation()
        results["aggregation"] = (t_pd, t_pl)
    except Exception as e:
        print(f"  SKIP: {e}")

    try:
        t_pd, t_pl = bench_parquet_read()
        results["parquet_read"] = (t_pd, t_pl)
    except Exception as e:
        print(f"  SKIP: {e}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, (t_pd, t_pl) in results.items():
        speedup = t_pd / t_pl
        bar = "█" * min(int(speedup * 5), 30)
        print(f"  {name:20s}: {speedup:4.1f}x faster with Polars  {bar}")
