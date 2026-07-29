"""
IB Custom-Anchor VWAP + Trend Confirmation Builder — Phase 2.6

Reads `ib_facts_{SYM}.parquet` and fused 1m OHLCV data and computes anchored
VWAP fields plus simple trend confirmations for one or more anchor times.

Performance note: heavy work is done once per anchor over the full 1m history,
then sliced per session/time-basis, not per-day.

Default anchors: 09:30 (IB start), 18:00, 00:00, 08:00, 09:00, 10:00, 13:30.
Output:
    data/derived/ib_avwap_{SYM}.parquet
"""

import argparse
import logging
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

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
from scripts.libs_py.avwap import compute_avwap
from scripts.libs_py.nqstats.sessions import get_logical_trading_date
from scripts.libs_py.nqstats.ib import SESSION_CONFIGS_V5

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

DERIVED_DIR = Path("data/derived")
INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]

DEFAULT_ANCHORS: Dict[str, time] = {
    "avwap_0930": time(9, 30),
    "avwap_1800": time(18, 0),
    "avwap_0000": time(0, 0),
    "avwap_0800": time(8, 0),
    "avwap_0900": time(9, 0),
    "avwap_1000": time(10, 0),
    "avwap_1330": time(13, 30),
}


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _load_facts(symbol: str) -> pd.DataFrame:
    path = DERIVED_DIR / f"ib_facts_{symbol}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    df = pd.read_parquet(path)
    df["trading_day"] = df["trading_day"].astype(str)
    return df


def _load_1m(symbol: str) -> pd.DataFrame:
    loader = get_loader()
    df = loader.load_1m(symbol, start_date=None, end_date=None)
    if df.empty:
        raise ValueError(f"No 1m data returned for {symbol}")
    if "volume" not in df.columns:
        raise KeyError(f"1m data for {symbol} missing volume column")
    df["logical_date"] = get_logical_trading_date(df.index)
    df["logical_date_str"] = df["logical_date"].astype(str)
    df["bar_minute"] = df.index.hour * 60 + df.index.minute
    df["bar_time"] = df.index.time
    return df


def _build_session_time_lookup(
    df_facts: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return a lookup keyed by (session_slot, time_basis) with columns:
    start_minute, end_minute, and a mapping of trading_day -> (start, end,
    offset_hours).  For ET_fixed the start/end are constants; for event_anchored
    they vary by day.
    """
    rows = []
    for (slot, basis), grp in df_facts.groupby(["session_slot", "time_basis"], sort=False):
        cfg = SESSION_CONFIGS_V5[slot]
        base_start = _minutes(cfg["ib_start"])
        base_end = _minutes(cfg["ib_end"])
        if basis == "event_anchored":
            day_offsets = dict(
                zip(
                    grp["trading_day"].astype(str).values,
                    grp["et_window_offset_hours"].astype(int).values,
                )
            )
        else:
            day_offsets = None
        rows.append({
            "session_slot": slot,
            "time_basis": basis,
            "base_start": base_start,
            "base_end": base_end,
            "day_offsets": day_offsets,
        })
    return pd.DataFrame(rows)


def _session_mask_vectorized(
    df_1m: pd.DataFrame,
    lookup_row: pd.Series,
) -> pd.Series:
    """Boolean mask for 1m bars inside the session window for one session/time_basis."""
    start = lookup_row["base_start"]
    end = lookup_row["base_end"]
    day_offsets = lookup_row["day_offsets"]

    minutes = df_1m["bar_minute"].values
    dates = df_1m["logical_date_str"].values

    if day_offsets is None:
        if start < end:
            return pd.Series((minutes >= start) & (minutes < end), index=df_1m.index)
        # Overnight / wrap-around
        return pd.Series((minutes >= start) | (minutes < end), index=df_1m.index)

    # Vectorized event-anchored start/end per day.
    offset_vec = np.array([day_offsets.get(d, 0) for d in dates], dtype=int)
    start_vec = (start + offset_vec * 60) % 1440
    end_vec = (end + offset_vec * 60) % 1440
    mask = start_vec < end_vec
    inside = np.empty(len(minutes), dtype=bool)
    inside[mask] = (minutes[mask] >= start_vec[mask]) & (minutes[mask] < end_vec[mask])
    inside[~mask] = (minutes[~mask] >= start_vec[~mask]) | (minutes[~mask] < end_vec[~mask])
    return pd.Series(inside, index=df_1m.index)


def _compute_anchor_avwap_overall(
    df_1m: pd.DataFrame,
    anchor_times: Dict[str, time],
) -> pd.DataFrame:
    """
    Compute each anchor's AVWAP once over the entire 1m history.
    Returns a DataFrame aligned to df_1m with only the columns we need for
    downstream aggregation.
    """
    out = pd.DataFrame(index=df_1m.index)
    # Pre-compute typical price once.
    tp = (df_1m["high"] + df_1m["low"] + df_1m["close"]) / 3.0
    pv = tp * df_1m["volume"]
    out["tpv"] = pv
    out["vol"] = df_1m["volume"].astype(np.float64)
    out["close"] = df_1m["close"]
    out["high"] = df_1m["high"]
    out["low"] = df_1m["low"]
    out["bar_minute"] = df_1m["bar_minute"].values
    out["logical_date_str"] = df_1m["logical_date_str"].values

    for label, anchor_t in anchor_times.items():
        anchor_min = _minutes(anchor_t)
        idx = pd.DatetimeIndex(df_1m.index)
        # Anchor resets when minute-of-day crosses anchor time.
        minutes = idx.hour * 60 + idx.minute
        # Use logical date for reset-day boundary.
        anchor_day = pd.Series(df_1m["logical_date_str"].astype(str).values, index=df_1m.index)
        anchor_day = anchor_day.where(minutes >= anchor_min)
        anchor_day = anchor_day.ffill()
        reset = anchor_day.ne(anchor_day.shift()).fillna(False)
        reset.iloc[0] = True
        group = reset.cumsum()

        cum_pv = out["tpv"].groupby(group).cumsum()
        cum_v = out["vol"].groupby(group).cumsum()
        avwap = cum_pv / cum_v.replace(0, np.nan)
        dev = out["close"] - avwap
        deviation_pct = dev / avwap.replace(0, np.nan) * 100.0

        # Rolling std of deviation within anchor group.
        roll_std = dev.groupby(group).transform(lambda s: s.rolling(20, min_periods=5).std())

        out[f"{label}_price"] = avwap
        out[f"{label}_deviation_pct"] = deviation_pct
        out[f"{label}_slope"] = avwap.groupby(group).transform(lambda s: s.diff(15).fillna(0.0))
        out[f"{label}_std_upper_1"] = avwap + 1.0 * roll_std
        out[f"{label}_std_lower_1"] = avwap - 1.0 * roll_std
        out[f"{label}_std_upper_2"] = avwap + 2.0 * roll_std
        out[f"{label}_std_lower_2"] = avwap - 2.0 * roll_std

        above = (out["close"] > avwap).astype(int)
        below = (out["close"] < avwap).astype(int)
        touch = ((out["low"] <= avwap) & (out["high"] >= avwap)).astype(int)
        out[f"{label}_above_count"] = above.groupby(group).cumsum()
        out[f"{label}_below_count"] = below.groupby(group).cumsum()
        out[f"{label}_touch_count"] = touch.groupby(group).cumsum()
        out[f"{label}_break_dir"] = np.where(
            out["close"] > avwap, 1, np.where(out["close"] < avwap, -1, 0)
        )

    return out


def _aggregate_session_features(
    avwap_all: pd.DataFrame,
    df_1m: pd.DataFrame,
    session_mask: pd.Series,
    session_slot: str,
    time_basis: str,
    anchor_times: Dict[str, time],
) -> pd.DataFrame:
    """
    For one session/time-basis, take the last bar of each trading day inside the
    session window and extract AVWAP features plus trend confirmations.
    """
    sub = avwap_all.loc[session_mask].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["trading_day"] = df_1m.loc[session_mask, "logical_date_str"].values
    sub["bar_time"] = df_1m.loc[session_mask].index.time

    # Last row per day for AVWAP summaries.
    last = sub.groupby("trading_day").tail(1).copy()
    feat_cols = []
    for label in anchor_times:
        feat_cols.extend([
            f"{label}_price", f"{label}_deviation_pct", f"{label}_slope",
            f"{label}_above_count", f"{label}_below_count", f"{label}_touch_count",
            f"{label}_std_upper_1", f"{label}_std_lower_1",
            f"{label}_std_upper_2", f"{label}_std_lower_2",
        ])
    avwap_out = last[["trading_day"] + feat_cols].copy()

    # Trend confirmations — EMA on DAILY closes (NT8 parity).
    # NT8 IBStrategyBase computes EMA(20/50) on daily closes (one value per
    # trading day = rangeClose), NOT on intraday 1-min bars. The 1-min EMA
    # always trends WITH the break (not misaligned), so it must be computed
    # across days to match NT8's TrendMisalignedWithBreak filter.
    # Step 1: extract the daily close (last bar of session window per day).
    daily_close = sub.groupby("trading_day")["close"].last().sort_index()
    # Step 2: compute EMA across the daily close series (chronological).
    ema20_daily = daily_close.ewm(span=20, adjust=False, min_periods=2).mean()
    ema50_daily = daily_close.ewm(span=50, adjust=False, min_periods=2).mean()
    # Step 3: map EMA values back to each trading day.
    ema20_by_day = ema20_daily.to_dict()
    ema50_by_day = ema50_daily.to_dict()
    # Step 4: build per-day trend features from the daily EMA series.
    trend_records = []
    for day in daily_close.index:
        e20 = ema20_by_day.get(day, np.nan)
        e50 = ema50_by_day.get(day, np.nan)
        # ema_20_slope = change over last 10 days (or available history)
        day_pos = daily_close.index.get_loc(day)
        slope_start = max(0, day_pos - 10)
        e20_slope = float(ema20_daily.iloc[day_pos] - ema20_daily.iloc[slope_start]) if day_pos >= 1 else 0.0
        # Higher highs / lower lows: 2-bar pattern on daily close
        if day_pos >= 2:
            hh = (daily_close.iloc[day_pos] > daily_close.iloc[day_pos - 1] > daily_close.iloc[day_pos - 2])
            ll = (daily_close.iloc[day_pos] < daily_close.iloc[day_pos - 1] < daily_close.iloc[day_pos - 2])
        else:
            hh = False
            ll = False
        trend_records.append({
            "trading_day": day,
            "ema_20_gt_50": bool(e20 > e50) if not (pd.isna(e20) or pd.isna(e50)) else np.nan,
            "ema_20_slope": e20_slope,
            "higher_highs_ib": bool(hh),
            "lower_lows_ib": bool(ll),
        })
    trend = pd.DataFrame(trend_records)
    avwap_out["session_slot"] = session_slot
    avwap_out["time_basis"] = time_basis
    trend["session_slot"] = session_slot
    trend["time_basis"] = time_basis
    return avwap_out.merge(trend, on=["session_slot", "time_basis", "trading_day"], how="outer")


def _add_break_vs_avwap(
    df_facts: pd.DataFrame,
    avwap_all: pd.DataFrame,
    df_1m: pd.DataFrame,
    lookup: pd.DataFrame,
) -> pd.Series:
    """
    For the 09:30 anchor, record break direction at first_break_minutes inside
    each session window.

    Vectorized: build a composite key (session_slot, time_basis, trading_day,
    minutes_from_start) for every bar and lookup each fact's first_break_minutes.
    """
    if "first_break_minutes" not in df_facts.columns:
        return pd.Series(np.nan, index=df_facts.index, name="break_vs_avwap_0930")

    col = "avwap_0930_break_dir"
    result = pd.Series(np.nan, index=df_facts.index, name="break_vs_avwap_0930")

    all_bars = []
    for _, lookup_row in lookup.iterrows():
        mask = _session_mask_vectorized(df_1m, lookup_row)
        if not mask.any():
            continue
        sub = avwap_all.loc[mask].copy()
        sub["trading_day"] = df_1m.loc[mask, "logical_date_str"].values
        sub["minutes_from_start"] = sub.groupby("trading_day").cumcount()
        sub["session_slot"] = lookup_row["session_slot"]
        sub["time_basis"] = lookup_row["time_basis"]
        all_bars.append(sub)

    if not all_bars:
        return result
    bars = pd.concat(all_bars)

    facts = df_facts[["session_slot", "time_basis", "trading_day", "first_break_minutes"]].copy()
    facts = facts.dropna(subset=["first_break_minutes"]).copy()
    facts["first_break_minutes"] = facts["first_break_minutes"].astype(int)

    # For each fact, find the bar at or before first_break_minutes in that window.
    merged = bars.merge(
        facts,
        on=["session_slot", "time_basis", "trading_day"],
        how="inner",
    )
    merged = merged[merged["minutes_from_start"] <= merged["first_break_minutes"]]
    if merged.empty:
        return result

    # Take the closest bar <= first_break_minutes per fact.
    merged["delta"] = merged["first_break_minutes"] - merged["minutes_from_start"]
    best = merged.loc[merged.groupby(["session_slot", "time_basis", "trading_day"])["delta"].idxmin()]

    # Map back to df_facts index by matching all keys.
    best = best.set_index(["session_slot", "time_basis", "trading_day"])
    facts_idx = df_facts.set_index(["session_slot", "time_basis", "trading_day"]).index
    locs = facts_idx.get_indexer(best.index)
    valid = locs >= 0
    result.iloc[locs[valid]] = best[col].values[valid]
    return result


def process_symbol(symbol: str, anchor_times: Dict[str, time] = DEFAULT_ANCHORS) -> pd.DataFrame:
    """Build AVWAP + trend derived fields for one symbol."""
    logger.info("[%s] Loading facts", symbol)
    df_facts = _load_facts(symbol)

    logger.info("[%s] Loading 1m bars", symbol)
    df_1m = _load_1m(symbol)

    logger.info("[%s] Computing AVWAP once per anchor (%d anchors)", symbol, len(anchor_times))
    t0 = pd.Timestamp.now()
    avwap_all = _compute_anchor_avwap_overall(df_1m, anchor_times)
    logger.info("[%s] AVWAP compute took %.1fs", symbol, (pd.Timestamp.now() - t0).total_seconds())

    lookup = _build_session_time_lookup(df_facts)

    out = df_facts[["symbol", "trading_day", "session_slot", "time_basis"]].copy()

    all_feats = []
    for _, lookup_row in lookup.iterrows():
        slot = lookup_row["session_slot"]
        basis = lookup_row["time_basis"]
        t0 = pd.Timestamp.now()
        mask = _session_mask_vectorized(df_1m, lookup_row)
        feats = _aggregate_session_features(avwap_all, df_1m, mask, slot, basis, anchor_times)
        if feats.empty:
            feats = pd.DataFrame({
                "trading_day": df_facts[
                    (df_facts["session_slot"] == slot) & (df_facts["time_basis"] == basis)
                ]["trading_day"].unique()
            })
            for label in anchor_times:
                for suffix in [
                    "_price", "_deviation_pct", "_slope",
                    "_above_count", "_below_count", "_touch_count",
                    "_std_upper_1", "_std_lower_1", "_std_upper_2", "_std_lower_2",
                ]:
                    feats[f"{label}{suffix}"] = np.nan
            feats["ema_20_gt_50"] = np.nan
            feats["ema_20_slope"] = np.nan
            feats["higher_highs_ib"] = np.nan
            feats["lower_lows_ib"] = np.nan
            feats["session_slot"] = slot
            feats["time_basis"] = basis
        logger.info("[%s] Aggregated %s / %s in %.1fs (%d rows)", symbol, slot, basis,
                    (pd.Timestamp.now() - t0).total_seconds(), len(feats))
        all_feats.append(feats)

    feats_all = pd.concat(all_feats, ignore_index=True)
    out = out.merge(
        feats_all,
        on=["session_slot", "time_basis", "trading_day"],
        how="left",
    )

    t0 = pd.Timestamp.now()
    out["break_vs_avwap_0930"] = _add_break_vs_avwap(df_facts, avwap_all, df_1m, lookup)
    logger.info("[%s] Break-vs-AVWAP took %.1fs", symbol, (pd.Timestamp.now() - t0).total_seconds())

    # Multi-anchor confluence score: how many anchors agree on direction at IB close.
    direction_cols = [c for c in out.columns if c.endswith("_deviation_pct")]
    directions = np.sign(out[direction_cols])
    # Net agreement: absolute sum of signed deviations = n_up - n_down.
    out["avwap_confluence_score"] = directions.apply(
        lambda r: abs(r.dropna().sum()) if r.dropna().any() else np.nan, axis=1
    )
    # Disagreement count: anchors whose sign differs from the majority sign.
    def _max_disagree(r: pd.Series) -> float:
        r = r.dropna()
        if len(r) == 0:
            return np.nan
        n_pos = (r == 1).sum()
        n_neg = (r == -1).sum()
        return float(min(n_pos, n_neg))

    out["avwap_disagreement_count"] = directions.apply(_max_disagree, axis=1)

    # Reorder columns alphabetically for stable output.
    return out[[c for c in sorted(out.columns)]]


def main():
    parser = argparse.ArgumentParser(description="Build IB custom-anchor VWAP + trend fields")
    parser.add_argument(
        "--instruments", type=str, default=",".join(INSTRUMENTS),
        help="Comma-separated symbols (default: all)",
    )
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        out_path = DERIVED_DIR / f"ib_avwap_{sym}.parquet"
        try:
            df = process_symbol(sym)
            df.to_parquet(out_path, index=False)
            logger.info("[%s] Wrote %s rows to %s", sym, len(df), out_path)
        except Exception as e:
            logger.error("[%s] Failed: %s", sym, e)
            raise


if __name__ == "__main__":
    main()
