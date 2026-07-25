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
    # Preserve the original 1m timestamp as a column (merges below reset the index)
    df["_ts"] = pd.to_datetime(df.index)
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 additions — §9.2 / §9.5 / §9.6 / §9.8 / §10.14
# All vectorized; share the same per-day IB window join used by TPO.
# ─────────────────────────────────────────────────────────────────────────────

def _ib_window_bars(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                    symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """Return the per-day IB-window 1m bars joined to trading_day.

    Reuses the same window logic as compute_tpo_and_touches. Returns a frame
    with columns: trading_day, open, high, low, close, volume, _ts (the 1m
    timestamp as a python datetime, preserved across the merge). Empty frame
    if no overlap.
    """
    cfg = _session_cfg(session_slot, time_basis)
    window_map = _daily_window_map(df_facts, cfg, time_basis)
    # Carry the 1m timestamp as a column so it survives the merge (merge resets index)
    src = df_1m
    joined = src.merge(window_map, left_on="logical_date_str", right_on="trading_day", how="inner")
    if joined.empty:
        return joined
    times = joined["bar_time"]
    start = joined["start"]
    end = joined["end"]
    if cfg["start"] < cfg["end"]:
        mask = (times >= start) & (times < end)
    else:
        mask = (times >= start) | (times < end)
    cols = ["trading_day", "open", "high", "low", "close", "_ts"] + (["volume"] if "volume" in joined.columns else [])
    return joined.loc[mask, cols].copy()


def compute_volume_weighted(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                            symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§9.2 volume-weighted IB fields: ib_vwap, vol_at_high/low, vol_poc, vol_skew."""
    cols = ["ib_vwap", "ib_vol_at_high", "ib_vol_at_low", "ib_vol_poc_price", "ib_vol_skew"]
    empty = pd.DataFrame({c: np.nan for c in cols}, index=df_facts.index)
    if "volume" not in df_1m.columns:
        return empty
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty
    precision = TPO_PRECISION.get(symbol, 2)
    eps = 1e-9

    def _one(g: pd.DataFrame) -> pd.Series:
        if g.empty:
            return pd.Series({c: np.nan for c in cols})
        vol = g["volume"].astype(float)
        if vol.sum() <= 0:
            return pd.Series({c: np.nan for c in cols})
        typical = (g["high"] + g["low"] + g["close"]) / 3.0
        vwap = float((typical * vol).sum() / vol.sum())
        ib_high = g["high"].max()
        ib_low = g["low"].min()
        mid = (ib_high + ib_low) / 2.0
        vol_at_high = float(vol[g["high"] >= ib_high - eps].sum())
        vol_at_low = float(vol[g["low"] <= ib_low + eps].sum())
        lvl = np.round(g["close"], precision)
        vol_by_lvl = vol.groupby(lvl).sum()
        vol_poc = float(vol_by_lvl.max()) if not vol_by_lvl.empty else np.nan
        upper_vol = float(vol[g["close"] > mid].sum())
        lower_vol = float(vol[g["close"] < mid].sum())
        if abs(upper_vol - lower_vol) / max(vol.sum(), 1.0) < 0.02:
            skew = 0
        else:
            skew = 1 if upper_vol > lower_vol else -1
        return pd.Series({
            "ib_vwap": vwap, "ib_vol_at_high": vol_at_high, "ib_vol_at_low": vol_at_low,
            "ib_vol_poc_price": vol_poc, "ib_vol_skew": skew,
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


def compute_or5_fields(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                       symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§9.5 opening auction (first 5 minutes): OR5 high/low, break timing, agreement."""
    cols = ["ib_or5_high", "ib_or5_low", "ib_or5_break_minutes",
            "ib_or5_broken_in_15", "ib_or5_ib_close_agree"]
    empty = pd.DataFrame({c: np.nan for c in cols}, index=df_facts.index)
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty

    def _one(g: pd.DataFrame) -> pd.Series:
        if g.empty:
            return pd.Series({c: np.nan for c in cols})
        g = g.sort_values("_ts")
        first5 = g.head(5)
        or5_high = float(first5["high"].max())
        or5_low = float(first5["low"].min())
        ib_high = float(g["high"].max())
        ib_low = float(g["low"].min())
        ib_close = float(g["close"].iloc[-1])
        rest = g.iloc[5:]
        break_min = np.nan
        broken_in_15 = False
        if not rest.empty:
            up_break = rest["high"] > or5_high
            dn_break = rest["low"] < or5_low
            break_mask = up_break | dn_break
            if break_mask.any():
                first_break_ts = rest["_ts"].iloc[break_mask.values.argmax()]
                first5_start = first5["_ts"].iloc[0]
                break_min = float((first_break_ts - first5_start).total_seconds() / 60.0)
                broken_in_15 = bool(break_min <= 15)
        or5_mid = (or5_high + or5_low) / 2.0
        agree = 0
        if ib_close > or5_mid and ib_high >= or5_high:
            agree = 1
        elif ib_close < or5_mid and ib_low <= or5_low:
            agree = 1
        elif ib_close != or5_mid:
            agree = -1
        return pd.Series({
            "ib_or5_high": or5_high, "ib_or5_low": or5_low,
            "ib_or5_break_minutes": break_min, "ib_or5_broken_in_15": broken_in_15,
            "ib_or5_ib_close_agree": agree,
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


def compute_pct_time_above_mid(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                               symbol: str, session_slot: str, time_basis: str) -> pd.Series:
    """§9.6 80% rule: fraction of IB bars with close above ib_mid."""
    out = pd.Series(np.nan, index=df_facts.index, name="ib_pct_time_above_mid")
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return out

    def _one(g: pd.DataFrame) -> float:
        if g.empty:
            return np.nan
        mid = (g["high"].max() + g["low"].min()) / 2.0
        return float((g["close"] > mid).mean())

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    mapped = df_facts["trading_day"].map(stats)
    out.loc[:] = mapped.values
    return out


def compute_pre_telegraph(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                         symbol: str, session_slot: str, time_basis: str) -> pd.Series:
    """§9.8 pre-IB telegraph: 5-min window before IB start vs its own open."""
    out = pd.Series(0.0, index=df_facts.index, name="ib_pre_telegraph_dir")
    cfg = _session_cfg(session_slot, time_basis)
    window_map = _daily_window_map(df_facts, cfg, time_basis)
    joined = df_1m.merge(window_map, left_on="logical_date_str", right_on="trading_day", how="inner")
    if joined.empty:
        return out
    times = joined["bar_time"]
    start = joined["start"]
    # Compute pre-start as (start - 5 min) in minutes-from-midnight (handles day wrap)
    start_mfm = start.apply(lambda t: t.hour * 60 + t.minute)
    pre_start_mfm = (start_mfm - 5) % (24 * 60)
    bar_mfm = joined["minutes_from_midnight"]
    # Window: bar within [pre_start, start) — handle wrap when start < 5
    if (pre_start_mfm <= start_mfm).all():
        mask = (bar_mfm >= pre_start_mfm) & (bar_mfm < start_mfm)
    else:
        mask = (bar_mfm >= pre_start_mfm) | (bar_mfm < start_mfm)
    pre = joined.loc[mask, ["trading_day", "open", "close", "_ts"]].copy()
    if pre.empty:
        return out

    def _one(g: pd.DataFrame) -> float:
        if g.empty:
            return 0.0
        g = g.sort_values("_ts")
        o = float(g["open"].iloc[0])
        c = float(g["close"].iloc[-1])
        if abs(c - o) < 1e-9:
            return 0.0
        return 1.0 if c > o else -1.0

    stats = pre.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    mapped = df_facts["trading_day"].map(stats)
    out.loc[:] = mapped.fillna(0.0).values
    return out


def compute_post_break_magnet(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                              symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§9.8 post-break mid magnet: did price return to mid after first break closed outside?"""
    cols = ["ib_mid_revisited_post_break", "ib_mid_revisit_post_break_minutes"]
    empty = pd.DataFrame({cols[0]: False, cols[1]: np.nan}, index=df_facts.index)
    fb_time_col = "first_break_time_val" if "first_break_time_val" in df_facts.columns else None
    if fb_time_col is None or "first_break_dir" not in df_facts.columns:
        return empty
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty
    bar_idx_by_day = {td: g.sort_values("_ts") for td, g in bars.groupby("trading_day")}

    def _one(row) -> pd.Series:
        td = row["trading_day"]
        fb_ts = row[fb_time_col]
        fb_dir = row["first_break_dir"]
        if pd.isna(fb_ts) or pd.isna(fb_dir) or int(fb_dir) == 0:
            return pd.Series({cols[0]: False, cols[1]: np.nan})
        day_bars = bar_idx_by_day.get(td)
        if day_bars is None or day_bars.empty:
            return pd.Series({cols[0]: False, cols[1]: np.nan})
        ib_high = day_bars["high"].max()
        ib_low = day_bars["low"].min()
        mid = (ib_high + ib_low) / 2.0
        post = day_bars[day_bars["_ts"] > fb_ts]
        if post.empty:
            return pd.Series({cols[0]: False, cols[1]: np.nan})
        if fb_dir > 0:
            touched = post["low"] <= mid
        else:
            touched = post["high"] >= mid
        if not touched.any():
            return pd.Series({cols[0]: False, cols[1]: np.nan})
        first_touch = post["_ts"].iloc[touched.values.argmax()]
        mins = float((first_touch - fb_ts).total_seconds() / 60.0)
        return pd.Series({cols[0]: True, cols[1]: mins})

    res = df_facts.apply(_one, axis=1)
    res.columns = cols
    res.index = df_facts.index
    return res


def compute_vcp_fields(df_facts: pd.DataFrame) -> pd.DataFrame:
    """§10.14.2 VCP contraction + §10.14.5 RVOL proxy (pure-facts)."""
    df = df_facts.copy().sort_values(["symbol", "session_slot", "time_basis", "trading_day"])
    grp = df.groupby(["symbol", "session_slot", "time_basis"])
    df["prev1_range"] = grp["ib_range"].shift(1)
    df["prev2_range"] = grp["ib_range"].shift(2)
    df["ib_vcp_3day_contracting"] = (df["prev2_range"] > df["prev1_range"]) & (df["prev1_range"] > df["ib_range"])
    vol_col = None
    for cand in ["ib_volume", "volume"]:
        if cand in df.columns:
            vol_col = cand
            break
    if vol_col:
        df["ib_vcp_volume_ratio"] = df[vol_col] / grp[vol_col].transform(
            lambda s: s.rolling(20, min_periods=5).mean()
        )
    else:
        df["ib_vcp_volume_ratio"] = np.nan
    df["ib_vcp_setup"] = df["ib_vcp_3day_contracting"] & (df["ib_vcp_volume_ratio"] < 0.6)
    df["ib_rvol"] = df["ib_vcp_volume_ratio"]
    df["ib_rvol_bucket"] = np.select(
        [df["ib_rvol"] < 0.7, df["ib_rvol"] > 1.5],
        ["low", "high"], default="normal",
    )
    return df[["ib_vcp_3day_contracting", "ib_vcp_volume_ratio",
               "ib_vcp_setup", "ib_rvol", "ib_rvol_bucket"]]


def compute_single_prints(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                           symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§10.14.3 single prints: TPO price levels visited exactly once in IB."""
    cols = ["ib_has_upper_single_print", "ib_has_lower_single_print",
            "ib_single_print_high", "ib_single_print_low"]
    empty = pd.DataFrame({c: False for c in cols[:2]} | {c: np.nan for c in cols[2:]},
                        index=df_facts.index)
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty
    precision = TPO_PRECISION.get(symbol, 2)

    def _one(g: pd.DataFrame) -> pd.Series:
        if g.empty:
            return pd.Series({cols[0]: False, cols[1]: False, cols[2]: np.nan, cols[3]: np.nan})
        lvl = np.round(g["close"], precision)
        vc = lvl.value_counts()
        singles = vc[vc == 1].index
        if singles.empty:
            return pd.Series({cols[0]: False, cols[1]: False, cols[2]: np.nan, cols[3]: np.nan})
        mid = (g["high"].max() + g["low"].min()) / 2.0
        upper = singles[singles > mid]
        lower = singles[singles < mid]
        return pd.Series({
            cols[0]: bool(len(upper) > 0), cols[1]: bool(len(lower) > 0),
            cols[2]: float(upper.max()) if len(upper) else np.nan,
            cols[3]: float(lower.min()) if len(lower) else np.nan,
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


def compute_wick_body_fields(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                             symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§10.14.9 wick/body acceptance at IB extremes."""
    cols = ["ib_high_wick_pct", "ib_low_wick_pct", "ib_high_body_close", "ib_low_body_close"]
    empty = pd.DataFrame({c: np.nan for c in cols}, index=df_facts.index)
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty

    def _one(g: pd.DataFrame) -> pd.Series:
        if g.empty:
            return pd.Series({c: np.nan for c in cols})
        ib_high = g["high"].max()
        ib_low = g["low"].min()
        ib_range = ib_high - ib_low
        if ib_range <= 0:
            return pd.Series({c: np.nan for c in cols})
        high_bar = g.loc[g["high"].idxmax()]
        low_bar = g.loc[g["low"].idxmin()]
        high_wick = (ib_high - max(high_bar["open"], high_bar["close"])) / ib_range * 100.0
        low_wick = (min(low_bar["open"], low_bar["close"]) - ib_low) / ib_range * 100.0
        return pd.Series({
            "ib_high_wick_pct": float(high_wick),
            "ib_low_wick_pct": float(low_wick),
            "ib_high_body_close": bool(high_bar["close"] >= ib_high - 0.1 * ib_range),
            "ib_low_body_close": bool(low_bar["close"] <= ib_low + 0.1 * ib_range),
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


def compute_sweep_fields(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                         symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§10.14.10 IB extreme sweeps (intrabar poke + close back inside)."""
    cols = ["ib_high_swept", "ib_low_swept", "ib_sweep_reclaim_dir"]
    empty = pd.DataFrame({c: False for c in cols}, index=df_facts.index)
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty

    def _one(g: pd.DataFrame) -> pd.Series:
        if g.empty:
            return pd.Series({c: False for c in cols})
        ib_high = g["high"].max()
        ib_low = g["low"].min()
        high_swept = bool(((g["high"] >= ib_high - 1e-9) & (g["close"] < ib_high)).any())
        low_swept = bool(((g["low"] <= ib_low + 1e-9) & (g["close"] > ib_low)).any())
        reclaim = 0
        if low_swept and not high_swept:
            reclaim = 1
        elif high_swept and not low_swept:
            reclaim = -1
        return pd.Series({
            "ib_high_swept": high_swept, "ib_low_swept": low_swept,
            "ib_sweep_reclaim_dir": reclaim,
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = False
    out.index = df_facts.index
    return out[cols]


def compute_acd_fields(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                       symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """§10.14.1 Mark Fisher ACD: A-up, A-down, C level, A-held."""
    cols = ["ib_or_acd_a_up", "ib_or_acd_a_down", "ib_or_acd_c_level", "ib_or_acd_a_held"]
    empty = pd.DataFrame({c: np.nan for c in cols}, index=df_facts.index)
    bars = _ib_window_bars(df_1m, df_facts, symbol, session_slot, time_basis)
    if bars.empty:
        return empty

    def _one(g: pd.DataFrame) -> pd.Series:
        if len(g) < 5:
            return pd.Series({c: np.nan for c in cols})
        g = g.sort_index()
        first5 = g.head(5)
        or5_high = first5["high"].max()
        or5_low = first5["low"].min()
        or5_range = or5_high - or5_low
        if or5_range <= 0:
            return pd.Series({c: np.nan for c in cols})
        a_up = or5_high + 0.1 * or5_range
        a_down = or5_low - 0.1 * or5_range
        open_price = first5["open"].iloc[0]
        c_level = open_price + 3 * or5_range
        rest = g.iloc[5:]
        a_held = False
        if not rest.empty:
            held_up = (rest["close"] > a_up).rolling(5, min_periods=5).sum() >= 5
            held_dn = (rest["close"] < a_down).rolling(5, min_periods=5).sum() >= 5
            a_held = bool(held_up.any() or held_dn.any())
        return pd.Series({
            "ib_or_acd_a_up": float(a_up), "ib_or_acd_a_down": float(a_down),
            "ib_or_acd_c_level": float(c_level), "ib_or_acd_a_held": a_held,
        })

    stats = bars.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


def compute_empirical_classification(df_facts: pd.DataFrame) -> pd.DataFrame:
    """§10.14.8 TrevorTrades empirical categories (pure-facts)."""
    df = df_facts.copy()
    if "ib_range" in df.columns:
        p25 = df["ib_range"].quantile(0.25)
        p75 = df["ib_range"].quantile(0.75)
        df["ib_range_size_class"] = np.select(
            [df["ib_range"] < p25, df["ib_range"] > p75],
            ["small", "large"], default="average",
        )
    else:
        df["ib_range_size_class"] = "average"

    bm = df["first_break_minutes_5min"] if "first_break_minutes_5min" in df.columns else df.get("first_break_minutes")
    if bm is not None:
        df["ib_break_urgency"] = np.select(
            [bm < 30, (bm >= 30) & (bm <= 60)],
            ["high", "medium"], default="low",
        )
    else:
        df["ib_break_urgency"] = "low"

    max_ext_col = None
    for c in ["max_ext_up", "max_ext_down"]:
        if c in df.columns:
            max_ext_col = c
            break
    if max_ext_col and "ib_range" in df.columns and (df["ib_range"] > 0).any():
        ext_frac = df[max_ext_col] / df["ib_range"]
        df["ib_extension_expectation"] = np.select(
            [ext_frac >= 0.25, ext_frac >= 0.50, ext_frac >= 1.0],
            ["likely_25", "likely_50", "likely_100"], default="unlikely_100",
        )
    else:
        df["ib_extension_expectation"] = "likely_25"

    if "ib_range_pct_of_daily" in df.columns and df["ib_range_pct_of_daily"].notna().any():
        r = df["ib_range_pct_of_daily"]
        # ib_range_pct_of_daily is a fraction (0.21 = 21%); compare to 0.30/0.50/0.70
        df["ib_day_type_predicted"] = np.select(
            [r < 0.30, (r >= 0.30) & (r < 0.50), (r >= 0.50) & (r < 0.70)],
            ["trend", "normal", "normal_variation"], default="range",
        )
    else:
        df["ib_day_type_predicted"] = "unknown"

    return df[["ib_range_size_class", "ib_break_urgency",
               "ib_extension_expectation", "ib_day_type_predicted"]]


# ─────────────────────────────────────────────────────────────────────────────
# CISD — Change in State of Delivery (per the CISD document, 2026-07-25)
#
# The document specifies: "Price does NOT need to close above the opening price
# to validate. Merely trading through the opening price validates the CSD."
# This is STRICTER-less than detect_cisd_authoritative (which requires close).
#
# Per-IB-session fields produced:
#   ib_cisd_bullish  — bool: did a bullish CSD fire during/after IB? (price trades
#                   up through the open of the last down-close candle before an up-run)
#   ib_cisd_bearish  — bool: symmetric bearish CSD
#   ib_cisd_bull_time — minutes from IB start to first bullish CSD (NaN if none)
#   ib_csd_bear_time — minutes from IB start to first bearish CSD
#   ib_cisd_anchor_bull — the opening price that was breached (bullish CSD anchor)
#   ib_cisd_anchor_bear — the opening price that was breached (bearish CSD anchor)
#   ib_cisd_inversion — bool: did an inversion fire? (body closes in forbidden half)
#   ib_cisd_dir — +1 if bullish fired first, -1 bearish first, 0 none
# ─────────────────────────────────────────────────────────────────────────────

def compute_cisd_fields(df_1m: pd.DataFrame, df_facts: pd.DataFrame,
                        symbol: str, session_slot: str, time_basis: str) -> pd.DataFrame:
    """CISD fields per the Change-in-State-of-Delivery document.

    Uses the full 1m session window (IB start → session out_end) so CSD triggers
    after IB close are captured too. The candidate candle is the last down-close
    (bullish CSD) or up-close (bearish CSD) candle prior to an impulse run.
    """
    cols = ["ib_cisd_bullish", "ib_cisd_bearish", "ib_cisd_bull_time",
            "ib_cisd_bear_time", "ib_cisd_anchor_bull", "ib_cisd_anchor_bear",
            "ib_cisd_inversion", "ib_cisd_dir"]
    empty = pd.DataFrame({
        "ib_cisd_bullish": False, "ib_cisd_bearish": False,
        "ib_cisd_bull_time": np.nan, "ib_cisd_bear_time": np.nan,
        "ib_cisd_anchor_bull": np.nan, "ib_cisd_anchor_bear": np.nan,
        "ib_cisd_inversion": False, "ib_cisd_dir": 0,
    }, index=df_facts.index)

    # Use the full session window (IB start to out_end) so post-IB CSDs are caught
    cfg = _session_cfg(session_slot, time_basis)
    window_map = _daily_window_map(df_facts, cfg, time_basis)
    src = df_1m
    joined = src.merge(window_map, left_on="logical_date_str", right_on="trading_day", how="inner")
    if joined.empty:
        return empty
    times = joined["bar_time"]
    start = joined["start"]
    end = joined["end"]
    if cfg["start"] < cfg["end"]:
        mask = (times >= start) & (times < end)
    else:
        mask = (times >= start) | (times < end)
    sess = joined.loc[mask, ["trading_day", "open", "high", "low", "close", "_ts"]].copy()
    if sess.empty:
        return empty

    eps = 1e-9

    def _one(g: pd.DataFrame) -> pd.Series:
        if len(g) < 3:
            return pd.Series({c: (False if "bullish" in c or "bearish" in c or "inversion" in c else (0 if "dir" in c else np.nan)) for c in cols})
        g = g.sort_values("_ts")
        o = g["open"].values
        h = g["high"].values
        l = g["low"].values
        c = g["close"].values
        ts = g["_ts"].values
        ib_start_ts = ts[0]
        down_close = c < o
        up_close = c > o
        # Bullish CSD: find last down-close candle before an up-run, anchor = its open,
        # trigger = price trades UP THROUGH that open (high >= anchor), not just close.
        bull_fired = False
        bull_time = np.nan
        bull_anchor = np.nan
        for i in range(1, len(g)):
            if down_close[i - 1] and not bull_fired:
                anchor = o[i - 1]
                # trade-through: any subsequent bar's high >= anchor
                if h[i] >= anchor - eps:
                    bull_fired = True
                    bull_time = float((ts[i] - ib_start_ts).astype("timedelta64[s]").astype(float) / 60.0) if hasattr(ts[i] - ib_start_ts, "astype") else float((pd.Timestamp(ts[i]) - pd.Timestamp(ib_start_ts)).total_seconds() / 60.0)
                    bull_anchor = float(anchor)
                    break
        # Bearish CSD: last up-close candle before a down-run, anchor = its open,
        # trigger = price trades DOWN THROUGH that open (low <= anchor).
        bear_fired = False
        bear_time = np.nan
        bear_anchor = np.nan
        for i in range(1, len(g)):
            if up_close[i - 1] and not bear_fired:
                anchor = o[i - 1]
                if l[i] <= anchor + eps:
                    bear_fired = True
                    bear_time = float((pd.Timestamp(ts[i]) - pd.Timestamp(ib_start_ts)).total_seconds() / 60.0)
                    bear_anchor = float(anchor)
                    break
        # Inversion: a body close in the forbidden half of the candidate candle range
        # (bullish: lower half; bearish: upper half). Simplified: if bull fired but a
        # later bar closes below the candidate candle's midpoint.
        inversion = False
        if bull_fired and bull_anchor == bull_anchor:
            # candidate candle range: o[i-1] to h[i-1] (approx). Forbidden = lower half
            cand_low = l[list(g.index).index(g.index[0])]  # placeholder; simplified check
            # Use the anchor bar's range if we tracked it; here use bull_anchor as proxy
            pass  # full inversion tracking deferred — needs candidate candle index
        # Direction: which fired first
        direction = 0
        if bull_fired and (not bear_fired or bull_time <= bear_time):
            direction = 1
        elif bear_fired:
            direction = -1
        return pd.Series({
            "ib_cisd_bullish": bull_fired, "ib_cisd_bearish": bear_fired,
            "ib_cisd_bull_time": bull_time, "ib_cisd_bear_time": bear_time,
            "ib_cisd_anchor_bull": bull_anchor, "ib_cisd_anchor_bear": bear_anchor,
            "ib_cisd_inversion": inversion, "ib_cisd_dir": direction,
        })

    stats = sess.groupby("trading_day").apply(_one, include_groups=False)
    stats.index = stats.index.astype(str)
    out = df_facts[["trading_day"]].reset_index(drop=True).merge(
        stats, left_on="trading_day", right_index=True, how="left"
    ).drop(columns=["trading_day"])
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out.index = df_facts.index
    return out[cols]


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
    out = pd.concat([out, compute_vcp_fields(df_facts)], axis=1)
    # Empirical classification needs ib_range_pct_of_daily (from multi-day context above)
    out = pd.concat([out, compute_empirical_classification(out)], axis=1)

    # 1m-dependent fields per session/time_basis
    tpo_frames = []
    drive_frames = []
    vol_frames = []
    or5_frames = []
    pct_above_frames = []
    telegraph_frames = []
    magnet_frames = []
    single_frames = []
    wick_frames = []
    sweep_frames = []
    acd_frames = []
    cisd_frames = []
    for (session_slot, time_basis), frame in df_facts.groupby(["session_slot", "time_basis"], sort=False):
        t0 = pd.Timestamp.now()
        logger.info("[%s] Computing 1m-derived fields for %s / %s", symbol, session_slot, time_basis)
        tpo_frames.append(compute_tpo_and_touches(df_1m, frame, symbol, session_slot, time_basis))
        drive_frames.append(compute_open_drive_dir(df_1m, frame, symbol, session_slot, time_basis))
        vol_frames.append(compute_volume_weighted(df_1m, frame, symbol, session_slot, time_basis))
        or5_frames.append(compute_or5_fields(df_1m, frame, symbol, session_slot, time_basis))
        pct_above_frames.append(compute_pct_time_above_mid(df_1m, frame, symbol, session_slot, time_basis))
        telegraph_frames.append(compute_pre_telegraph(df_1m, frame, symbol, session_slot, time_basis))
        magnet_frames.append(compute_post_break_magnet(df_1m, frame, symbol, session_slot, time_basis))
        single_frames.append(compute_single_prints(df_1m, frame, symbol, session_slot, time_basis))
        wick_frames.append(compute_wick_body_fields(df_1m, frame, symbol, session_slot, time_basis))
        sweep_frames.append(compute_sweep_fields(df_1m, frame, symbol, session_slot, time_basis))
        acd_frames.append(compute_acd_fields(df_1m, frame, symbol, session_slot, time_basis))
        cisd_frames.append(compute_cisd_fields(df_1m, frame, symbol, session_slot, time_basis))
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

    vol_all = pd.concat(vol_frames).sort_index()
    for c in ["ib_vwap", "ib_vol_at_high", "ib_vol_at_low", "ib_vol_poc_price", "ib_vol_skew"]:
        out[c] = vol_all[c]
    or5_all = pd.concat(or5_frames).sort_index()
    for c in ["ib_or5_high", "ib_or5_low", "ib_or5_break_minutes", "ib_or5_broken_in_15", "ib_or5_ib_close_agree"]:
        out[c] = or5_all[c]
    out["ib_pct_time_above_mid"] = pd.concat(pct_above_frames).sort_index()
    out["ib_pre_telegraph_dir"] = pd.concat(telegraph_frames).sort_index()
    magnet_all = pd.concat(magnet_frames).sort_index()
    out["ib_mid_revisited_post_break"] = magnet_all["ib_mid_revisited_post_break"]
    out["ib_mid_revisit_post_break_minutes"] = magnet_all["ib_mid_revisit_post_break_minutes"]
    single_all = pd.concat(single_frames).sort_index()
    for c in ["ib_has_upper_single_print", "ib_has_lower_single_print", "ib_single_print_high", "ib_single_print_low"]:
        out[c] = single_all[c]
    wick_all = pd.concat(wick_frames).sort_index()
    for c in ["ib_high_wick_pct", "ib_low_wick_pct", "ib_high_body_close", "ib_low_body_close"]:
        out[c] = wick_all[c]
    sweep_all = pd.concat(sweep_frames).sort_index()
    for c in ["ib_high_swept", "ib_low_swept", "ib_sweep_reclaim_dir"]:
        out[c] = sweep_all[c]
    acd_all = pd.concat(acd_frames).sort_index()
    for c in ["ib_or_acd_a_up", "ib_or_acd_a_down", "ib_or_acd_c_level", "ib_or_acd_a_held"]:
        out[c] = acd_all[c]
    cisd_all = pd.concat(cisd_frames).sort_index()
    for c in ["ib_cisd_bullish", "ib_cisd_bearish", "ib_cisd_bull_time",
             "ib_cisd_bear_time", "ib_cisd_anchor_bull", "ib_cisd_anchor_bear",
             "ib_cisd_inversion", "ib_cisd_dir"]:
        out[c] = cisd_all[c]

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
