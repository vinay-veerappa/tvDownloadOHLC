"""
IB Derived Fields Builder — Phase 2

Reads `ib_facts_{SYM}.parquet` plus fused 1m OHLCV data and computes the
market-profile, multi-day-context, break-characteristic, and failure-mode
columns defined in the IB data-gathering plan.

Output:
    data/derived/ib_derived_{SYM}.parquet

One row per (trading_day, session_slot, time_basis), aligned 1:1 with
`ib_facts_{SYM}.parquet`.  All calculations are vectorized where possible;
per-symbol loops are used only to keep 1m memory footprint bounded.
"""

import argparse
import logging
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Make repo root importable
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.edgeful.lib.data_loader import get_loader
from scripts.libs_py.nqstats.sessions import get_logical_trading_date, get_dst_flags
from scripts.libs_py.nqstats.ib import SESSION_CONFIGS_V5

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

DERIVED_DIR = Path("data/derived")
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

# 1m close rounding precision per instrument (used for TPO binning)
TPO_PRECISION = {
    "NQ1": 2,
    "ES1": 2,
    "YM1": 0,
    "RTY1": 1,
    "CL1": 2,
    "GC1": 1,
}


def _session_cfg(session_slot: str, time_basis: str = "ET_fixed") -> Dict:
    """Return window config for a session slot, handling event_anchored shifts."""
    base = SESSION_CONFIGS_V5[session_slot]
    cfg = {
        "start": base["ib_start"],
        "end": base["ib_end"],
    }
    return cfg


def _event_anchored_window(row: pd.Series, cfg: Dict) -> Tuple[time, time]:
    """
    Return actual (start, end) time for a single event-anchored facts row.

    Uses the same DST logic as calculate_ib_statistics_v5:
    et_window_offset_hours -1 -> session shifted one hour earlier,
    +1 -> shifted one hour later.
    """
    offset = row.get("et_window_offset_hours", 0)
    base_start = datetime.combine(datetime.today(), cfg["start"])
    base_end = datetime.combine(datetime.today(), cfg["end"])
    start = (base_start + timedelta(hours=int(offset))).time()
    end = (base_end + timedelta(hours=int(offset))).time()
    return start, end


def _add_logical_date_and_time(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Add logical_date (roll at 18:00 ET) and bar time-of-day columns."""
    df = df_1m.copy()
    df["logical_date"] = get_logical_trading_date(df.index)
    df["bar_time"] = df.index.time
    df["minutes_from_midnight"] = df.index.hour * 60 + df.index.minute
    # Pre-fetch DST maps on unique calendar days for event-anchored sessions
    unique_dates = pd.to_datetime(df["logical_date"]).unique()
    us_dst_daily, uk_dst_daily = get_dst_flags(pd.DatetimeIndex(unique_dates))
    day_dst_map = pd.DataFrame({
        "logical_date": pd.Series(unique_dates).dt.date.astype(str),
        "us_dst": us_dst_daily.values,
        "uk_dst": uk_dst_daily.values,
    })
    df["logical_date_str"] = df["logical_date"].astype(str)
    df = df.merge(day_dst_map, left_on="logical_date_str", right_on="logical_date", how="left", suffixes=("", "_dst"))
    df = df.drop(columns=["logical_date_dst"])
    return df


def _load_facts(symbol: str) -> pd.DataFrame:
    path = DERIVED_DIR / f"ib_facts_{symbol}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    df = pd.read_parquet(path)
    # ensure string trading_day for merging
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _load_1m(symbol: str) -> pd.DataFrame:
    loader = get_loader()
    df = loader.load_1m(symbol, start_date=None, end_date=None)
    if df.empty:
        raise ValueError(f"No 1m data returned for {symbol}")
    # Keep volume for VWAP work later; for Phase 2 TPO/touch counts we need OHLC only
    return df




def _daily_window_map(df_facts: pd.DataFrame, cfg: Dict, time_basis: str) -> pd.DataFrame:
    """
    Build a unique (trading_day -> start, end) lookup for this session/time_basis.
    ET_fixed uses the same window every day; event_anchored uses per-row offsets.
    """
    if time_basis == "event_anchored":
        cols = ["trading_day", "et_window_offset_hours"]
        rows = df_facts[cols].drop_duplicates().reset_index(drop=True)
        base_start = datetime.combine(datetime.today(), cfg["start"])
        base_end = datetime.combine(datetime.today(), cfg["end"])
        rows["start"] = rows["et_window_offset_hours"].apply(
            lambda o: (base_start + timedelta(hours=int(o))).time()
        )
        rows["end"] = rows["et_window_offset_hours"].apply(
            lambda o: (base_end + timedelta(hours=int(o))).time()
        )
        rows = rows.drop(columns=["et_window_offset_hours"])
    else:
        days = df_facts["trading_day"].unique()
        rows = pd.DataFrame({
            "trading_day": days,
            "start": cfg["start"],
            "end": cfg["end"],
        })
    return rows


def compute_tpo_and_touches(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                            symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """
    Compute TPO-based and touch-count fields for one session/time_basis.

    Returns a DataFrame indexed exactly like df_facts with columns:
        ib_poc_price, ib_vah, ib_val, ib_tpo_skew,
        ib_high_touch_count, ib_low_touch_count
    """
    cfg = _session_cfg(session_slot, time_basis)
    precision = TPO_PRECISION.get(symbol, 2)

    window_map = _daily_window_map(df_facts, cfg, time_basis)
    joined = df_1m.merge(window_map, left_on="logical_date_str", right_on="trading_day", how="inner")
    if joined.empty:
        return _empty_tpo(df_facts.index)

    times = joined["bar_time"]
    start = joined["start"]
    end = joined["end"]
    if cfg["start"] < cfg["end"]:
        mask = (times >= start) & (times < end)
    else:
        mask = (times >= start) | (times < end)
    window_bars = joined.loc[mask].copy()
    if window_bars.empty:
        return _empty_tpo(df_facts.index)

    window_bars["rounded_close"] = np.round(window_bars["close"], precision)

    log_every = 500
    counter = {"n": 0}
    def _tpo_stats_with_progress(g: pd.DataFrame) -> pd.Series:
        counter["n"] += 1
        if counter["n"] % log_every == 0:
            logger.info("[%s %s/%s TPO] processed %s/%s days", symbol, session_slot, time_basis, counter["n"], len(window_map))
        return _tpo_stats_one_from_group(g)

    stats = window_bars.groupby("logical_date_str").apply(_tpo_stats_with_progress, include_groups=False)
    stats.index = stats.index.astype(str).rename("trading_day")

    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    )
    out = out.drop(columns=["trading_day"])
    out.index = df_facts.index
    return out


def _empty_tpo(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({
        "ib_poc_price": np.nan, "ib_vah": np.nan, "ib_val": np.nan,
        "ib_tpo_skew": 0, "ib_high_touch_count": 0, "ib_low_touch_count": 0,
    }, index=index)


def _tpo_stats_one_from_group(g: pd.DataFrame) -> pd.Series:
    """Vectorized TPO stats on a single day's IB window bars."""
    closes = g["rounded_close"]
    if len(closes) == 0:
        return pd.Series({
            "ib_poc_price": np.nan, "ib_vah": np.nan, "ib_val": np.nan,
            "ib_tpo_skew": 0, "ib_high_touch_count": 0, "ib_low_touch_count": 0,
        })
    vc = closes.value_counts().sort_index()
    poc_price = float(vc.idxmax())
    vah = float(np.percentile(closes, 70))
    val = float(np.percentile(closes, 30))
    mean_c = closes.mean()
    med_c = closes.median()
    eps = 1e-9
    skew = 0 if abs(mean_c - med_c) < eps else (1 if mean_c > med_c else -1)
    ib_high = g["high"].max()
    ib_low = g["low"].min()
    high_touches = int((g["high"] >= ib_high - eps).sum())
    low_touches = int((g["low"] <= ib_low + eps).sum())
    return pd.Series({
        "ib_poc_price": poc_price, "ib_vah": vah, "ib_val": val,
        "ib_tpo_skew": skew, "ib_high_touch_count": high_touches, "ib_low_touch_count": low_touches,
    })


def compute_open_drive_dir(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                           symbol: str, session_slot: str, time_basis: str) -> pd.Series:
    """
    Determine whether the first 5 minutes of the session are entirely above/below
    the prior logical day's close.

    Returns a Series indexed like df_facts with values +1 / -1 / 0.
    """
    cfg = _session_cfg(session_slot, time_basis)

    window_map = _daily_window_map(df_facts, cfg, time_basis)
    joined = df_1m.merge(window_map, left_on="logical_date_str", right_on="trading_day", how="inner")
    if joined.empty:
        return pd.Series(np.nan, index=df_facts.index, name="ib_open_drive_dir")

    times = joined["bar_time"]
    start = joined["start"]
    end = joined["end"]
    if cfg["start"] < cfg["end"]:
        mask = (times >= start) & (times < end)
    else:
        mask = (times >= start) | (times < end)
    window_bars = joined.loc[mask].copy()
    if window_bars.empty:
        return pd.Series(np.nan, index=df_facts.index, name="ib_open_drive_dir")

    # First 5 bars of the session window per day, preserving day label
    first5 = window_bars.sort_index().reset_index()
    index_name = first5.columns[0]
    first5["rn"] = first5.groupby("logical_date_str").cumcount()
    first5 = first5[first5["rn"] < 5].set_index(index_name)

    daily_close = df_1m.groupby("logical_date_str")["close"].last()
    prior_close_map = daily_close.shift(1)

    # Aggregate first 5 bars per day
    agg = first5.groupby("logical_date_str").agg({"low": "min", "high": "max"})
    agg["prior_close"] = prior_close_map.reindex(agg.index)
    conds = [
        agg["low"] > agg["prior_close"],
        agg["high"] < agg["prior_close"],
    ]
    choices = [1.0, -1.0]
    drive = pd.Series(
        np.select([c.values for c in conds], choices, default=0.0),
        index=agg.index,
        name="ib_open_drive_dir",
    )
    drive.index = drive.index.astype(str).rename("trading_day")

    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        drive, left_on="trading_day", right_index=True, how="left"
    )["ib_open_drive_dir"]
    out.index = df_facts.index
    return out


def compute_multi_day_context(df_facts: pd.DataFrame) -> pd.DataFrame:
    """Pure-facts derived context fields."""
    df = df_facts.copy()
    df = df.sort_values(["symbol", "session_slot", "time_basis", "trading_day"])

    # 5-day rolling percentiles of ib_range
    df["ib_range_5d_pctile"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_range"].transform(
        lambda s: s.rolling(20, min_periods=5).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    )
    # Simpler rolling percentile via expanding window not ideal; use rolling rank
    df["ib_range_5d_pctile"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_range"].transform(
        lambda s: s.rolling(20, min_periods=5).apply(lambda x: (x[-1] - x.min()) / (x.max() - x.min()) if x.max() != x.min() else np.nan, raw=True)
    )
    df["ib_range_5d_contracting"] = df["ib_range_5d_pctile"] <= 0.20
    df["ib_range_5d_expanding"] = df["ib_range_5d_pctile"] >= 0.80

    # Multi-day composite
    df["ib_3day_composite_high"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_high"].transform(lambda s: s.rolling(3, min_periods=1).max())
    df["ib_3day_composite_low"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_low"].transform(lambda s: s.rolling(3, min_periods=1).min())

    # Inside/outside vs prior day IB
    df["prior_ib_high"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_high"].shift(1)
    df["prior_ib_low"] = df.groupby(["symbol", "session_slot", "time_basis"])["ib_low"].shift(1)
    conditions = [
        (df["ib_high"] <= df["prior_ib_high"]) & (df["ib_low"] >= df["prior_ib_low"]),
        (df["ib_high"] > df["prior_ib_high"]) & (df["ib_low"] < df["prior_ib_low"]),
    ]
    choices = ["inside", "outside"]
    df["ib_inside_outside"] = np.select(conditions, choices, default="overlapping")

    # Range as pct of daily range (use facts range_pct if present, else compute proxy)
    if "range_pct" in df.columns:
        df["ib_range_pct_of_daily"] = df["range_pct"]
    else:
        df["ib_range_pct_of_daily"] = np.nan

    # Overnight ratio proxy: if Globex IB facts exist, use same-day Globex range / IB range
    # This is a placeholder; a better version computes from 1m in a later phase.
    df["ib_vs_overnight_ratio"] = np.nan

    return df[[
        "ib_range_pct_of_daily", "ib_range_5d_pctile",
        "ib_range_5d_contracting", "ib_range_5d_expanding",
        "ib_inside_outside", "ib_3day_composite_high", "ib_3day_composite_low",
        "ib_vs_overnight_ratio",
    ]]


def compute_break_speed_and_failure(df_facts: pd.DataFrame) -> pd.DataFrame:
    """Break speed and per-play failure modes (no 1m data required)."""
    df = df_facts.copy()
    # Use 5-min bucketed minutes if present
    break_min = df["first_break_minutes_5min"] if "first_break_minutes_5min" in df.columns else df["first_break_minutes"]
    df["ib_break_speed"] = df["range_pts"] / break_min.replace(0, np.nan)

    for n in (1, 2, 3):
        res_col = f"play{n}_result"
        to_col = f"play{n}_timeout_loss"
        if res_col not in df.columns:
            continue
        conds = [
            (df[res_col] != -1),
            df["false_break_high"] | df["false_break_low"],
            (df["retrace_depth_pct"] > 50),
            df.get(to_col, False),
        ]
        choices = ["none", "fakeout", "fade", "chop"]
        df[f"ib_failure_mode_play{n}"] = np.select(conds, choices, default="wrong_dir")

    return df[["ib_break_speed", "ib_failure_mode_play1", "ib_failure_mode_play2", "ib_failure_mode_play3"]]


def process_symbol(symbol: str) -> pd.DataFrame:
    """Build derived fields for one symbol."""
    logger.info("[%s] Loading facts", symbol)
    df_facts = _load_facts(symbol)
    logger.info("[%s] Facts loaded: %s rows", symbol, len(df_facts))

    logger.info("[%s] Loading 1m bars", symbol)
    df_1m = _load_1m(symbol)
    logger.info("[%s] 1m bars loaded: %s rows", symbol, len(df_1m))
    logger.info("[%s] Enriching timestamps", symbol)
    df_1m = _add_logical_date_and_time(df_1m)
    logger.info("[%s] Timestamps enriched", symbol)

    # Pure-facts fields
    out = df_facts[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    out = pd.concat([out, compute_multi_day_context(df_facts)], axis=1)
    out = pd.concat([out, compute_break_speed_and_failure(df_facts)], axis=1)

    # 1m-dependent fields per session/time_basis
    tpo_frames = []
    drive_frames = []
    for (session_slot, time_basis), frame in df_facts.groupby(["session_slot", "time_basis"], sort=False):
        t0 = pd.Timestamp.now()
        logger.info("[%s] Computing 1m-derived fields for %s / %s", symbol, session_slot, time_basis)
        tpo = compute_tpo_and_touches(df_1m, frame, symbol, session_slot, time_basis)
        drive = compute_open_drive_dir(df_1m, frame, symbol, session_slot, time_basis)
        tpo_frames.append(tpo)
        drive_frames.append(drive)
        logger.info("[%s] Completed %s / %s in %.1fs", symbol, session_slot, time_basis, (pd.Timestamp.now() - t0).total_seconds())

    tpo_all = pd.concat(tpo_frames)
    out = out.sort_index()
    tpo_all = tpo_all.sort_index()
    out["ib_poc_price"] = tpo_all["ib_poc_price"]
    out["ib_vah"] = tpo_all["ib_vah"]
    out["ib_val"] = tpo_all["ib_val"]
    out["ib_tpo_skew"] = tpo_all["ib_tpo_skew"]
    out["ib_high_touch_count"] = tpo_all["ib_high_touch_count"]
    out["ib_low_touch_count"] = tpo_all["ib_low_touch_count"]
    out["ib_open_drive_dir"] = pd.concat(drive_frames).sort_index()

    # Preserve 5-min bucketed timing columns from facts when present
    for col in ["first_break_minutes_5min", "mid_retest_minutes_5min", "gap_fill_minutes_5min"]:
        if col in df_facts.columns:
            out[col] = df_facts[col]

    # Sort columns for stable schema
    return out[[c for c in sorted(out.columns)]]


def main():
    parser = argparse.ArgumentParser(description="Build IB derived fields per symbol")
    parser.add_argument("--instruments", type=str, default=",".join(INSTRUMENTS),
                        help="Comma-separated symbols (default: all)")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        out_path = DERIVED_DIR / f"ib_derived_{sym}.parquet"
        try:
            df = process_symbol(sym)
            df.to_parquet(out_path, index=False)
            logger.info("[%s] Wrote %s rows to %s", sym, len(df), out_path)
        except Exception as e:
            logger.error("[%s] Failed: %s", sym, e)
            raise


if __name__ == "__main__":
    main()
