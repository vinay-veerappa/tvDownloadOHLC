"""
Phase 5 derived data: reusable key levels + PD-array context per IB session.

Reads fused 1m data once, runs vectorized ICT detectors, computes a configurable
set of anchor opens/mids, and joins everything to the ib_facts session grid.

Output:
    data/derived/ib_key_levels_{SYM}.parquet

Key columns:
    - anchor opens/mids: midnight_open, globex_1800_open, ny_0930_open,
      prev_day_mid, prev_week_mid, prev_month_mid, h4_open_* etc.
    - PD arrays at IB high/low and inside the IB mid 40-60% zone.
    - nearest PD-array distance from break extension and from pullback into mid zone.

ADR-017 compliant: vectorized NumPy/Pandas, no per-row Python loops.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from scripts.libs_py.ict_engine.core.pa import (
    detect_breaker,
    detect_fvg,
    detect_liquidity,
    detect_mitigation_block,
    detect_orderblock,
    detect_rejection_block,
)
from scripts.libs_py.ict_engine.core.pd_matrix import rank_pd_arrays
from scripts.libs_py.ict_engine.core.retracements import detect_dealing_range
from scripts.libs_py.ict_engine.core.structure import detect_swings
from scripts.libs_py.nqstats.ib import SESSION_CONFIGS_V5
from scripts.libs_py.nqstats.sessions import get_logical_trading_date
from scripts.utils.fused_data_loader import load_fused_data

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "scripts" / "edgeful" / "ib_key_levels_config.yaml"
DATA_DERIVED = ROOT / "data" / "derived"

INSTRUMENTS = ["NQ1", "ES1", "YM1", "RTY1", "CL1", "GC1"]


def _load_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _to_dt_time(tstr: str) -> time:
    return datetime.strptime(tstr, "%H:%M").time()


def _et_localize(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure index is ET-localized DatetimeIndex."""
    if df.index.tz is None:
        # Data is stored UTC; localize and convert.
        df = df.copy()
        df.index = pd.to_datetime(df.index).tz_localize("UTC").tz_convert("America/New_York")
        df.index = df.index.tz_localize(None)
    return df


def _compute_fixed_opens(df: pd.DataFrame, anchors: List[Dict]) -> pd.DataFrame:
    """For each fixed_open anchor, materialize the open price at the first bar >= time."""
    out = pd.DataFrame(index=df.index)
    times = pd.Series(df.index.time, index=df.index)
    dates = pd.Series(df.index.date, index=df.index)

    for a in anchors:
        if a.get("type") != "fixed_open":
            continue
        target = _to_dt_time(a["time"])
        # first bar of each day at or after target time
        mask = times >= target
        first_bar = df[mask].groupby(dates[mask])["open"].first()
        day_map = pd.Series(
            {d: v for d, v in zip(first_bar.index, first_bar.values)},
            index=df.index,
        )
        out[a["name"]] = day_map.ffill().values
    return out


def _compute_period_stats(df: pd.DataFrame, anchors: List[Dict]) -> pd.DataFrame:
    """period_mid and period_close over calendar periods."""
    out = pd.DataFrame(index=df.index)
    idx = pd.to_datetime(df.index)

    # Normalize deprecated aliases for newer pandas.
    alias_map = {"1D": "D", "1W": "W-SUN", "1M": "ME", "ME": "ME"}

    for a in anchors:
        freq = a.get("period", "D")
        freq = alias_map.get(freq, freq)
        if a.get("type") == "period_mid":
            period_high = df["high"].resample(freq, closed="left", label="left").max()
            period_low = df["low"].resample(freq, closed="left", label="left").min()
            mid = ((period_high + period_low) / 2).reindex(idx, method="ffill")
            out[a["name"]] = mid.shift(1).values
        elif a.get("type") == "period_close":
            close = df["close"].resample(freq, closed="left", label="left").last()
            close_re = close.reindex(idx, method="ffill")
            out[a["name"]] = close_re.shift(1).values
    return out


def _compute_h4_opens(df: pd.DataFrame) -> pd.DataFrame:
    """Generate 4-hour anchored opens (00,04,08,12,16,20 ET)."""
    out = pd.DataFrame(index=df.index)
    hour = pd.Series(df.index.hour, index=df.index)
    date = pd.Series(df.index.date, index=df.index)

    for h in [0, 4, 8, 12, 16, 20]:
        # first bar at or after h for each day
        mask = hour >= h
        day_first = df[mask].groupby(date[mask])["open"].first()
        series = pd.Series(
            {d: v for d, v in zip(day_first.index, day_first.values)},
            index=df.index,
        ).ffill()
        # Only valid from hour h until next h bracket.
        active = (hour >= h) & (hour < (h + 4))
        out[f"h4_open_{h:02d}"] = np.where(active, series.values, np.nan)
    return out.ffill(axis=0)


def _compute_rolling_opens(df: pd.DataFrame, anchors: List[Dict]) -> pd.DataFrame:
    """Rolling open anchors like weekly_open / monthly_open — fully vectorized."""
    out = pd.DataFrame(index=df.index)
    n = len(df)
    opens = df["open"].values
    times = pd.Series(df.index.time, index=df.index).values

    for a in anchors:
        if a.get("type") != "rolling_open":
            continue
        target = _to_dt_time(a["time"])
        # Boolean mask: bar time is at or after anchor time.
        mask = pd.Series([t >= target for t in times], index=df.index)
        rule = a.get("rule")

        if rule == "first_bar_of_week":
            iso = df.index.isocalendar()
            group_key = (iso.year.astype(np.int64) * 100 + iso.week.astype(np.int64))
        elif rule == "first_bar_of_month":
            group_key = (
                df.index.year.astype(np.int64).values * 100
                + df.index.month.astype(np.int64).values
            )
        else:
            # fallback to daily rolling open; reuse fixed_open logic below.
            first_bar = df.loc[mask].groupby(df.index[mask].date)["open"].first()
            day_map = pd.Series(np.nan, index=df.index)
            for d, price in first_bar.items():
                day_map[df.index.date == d] = price
            out[a["name"]] = day_map.ffill().values
            continue

        # Vectorized first valid open per group at/after target time.
        # cumsum of mask within each group -> 1 at the first qualifying bar.
        group_key_s = pd.Series(group_key, index=df.index)
        first_qualifying = ((mask.groupby(group_key_s).cumsum() == 1) & mask).values
        vals = np.where(first_qualifying, opens, np.nan)
        vals = pd.Series(vals, index=df.index).groupby(group_key_s).ffill().values
        out[a["name"]] = vals
    return out


def _detect_ict_features(df: pd.DataFrame, cfg: Dict) -> pd.DataFrame:
    """Run all vectorized ICT detectors on 1m data and return a combined per-bar frame."""
    swing_length = cfg.get("ict", {}).get("swing_length", 5)
    liq_thresh = cfg.get("ict", {}).get("liquidity_threshold", 0.0001)

    swings = detect_swings(df, swing_length=swing_length)
    fvg = detect_fvg(df)
    ob = detect_orderblock(df, swings)
    breaker = detect_breaker(df, swings)
    mb = detect_mitigation_block(df, swings)
    rb = detect_rejection_block(df, swings)
    liq = detect_liquidity(df, swings, threshold=liq_thresh)
    dr = detect_dealing_range(df, swings)

    combined = pd.DataFrame(index=df.index)
    combined["swing_type"] = swings.get("shl", 0).fillna(0).astype(int)
    combined["swing_level"] = swings.get("level", np.nan)

    combined["fvg_type"] = fvg.get("fvg_type", 0).fillna(0).astype(int)
    combined["fvg_top"] = fvg.get("fvg_top", np.nan)
    combined["fvg_bottom"] = fvg.get("fvg_bottom", np.nan)

    combined["ob"] = ob.get("ob", 0).fillna(0).astype(int)
    combined["ob_top"] = ob.get("top", np.nan)
    combined["ob_bottom"] = ob.get("bottom", np.nan)

    combined["breaker"] = breaker.get("breaker", 0).fillna(0).astype(int)
    combined["breaker_top"] = breaker.get("top", np.nan)
    combined["breaker_bottom"] = breaker.get("bottom", np.nan)

    combined["mitigation"] = mb.get("mitigation_block", 0).fillna(0).astype(int)
    combined["mitigation_top"] = mb.get("top", np.nan)
    combined["mitigation_bottom"] = mb.get("bottom", np.nan)

    combined["rejection"] = rb.get("rejection_block", 0).fillna(0).astype(int)
    combined["rejection_top"] = rb.get("top", np.nan)
    combined["rejection_bottom"] = rb.get("bottom", np.nan)

    for col in ["swept_high", "swept_low"]:
        if col in liq.columns:
            combined[col] = liq[col].fillna(0).astype(int)

    for col in ["equilibrium", "is_discount", "is_premium", "range_high", "range_low"]:
        if col in dr.columns:
            combined[col] = dr[col]
    return combined


def _find_nearest_array(price: pd.Series, ict: pd.DataFrame, col_type: str, col_top: str, col_bottom: str) -> pd.DataFrame:
    """Vectorized nearest active PD array of a given type relative to price."""
    active = ict[ict[col_type] != 0].copy()
    if active.empty:
        return pd.DataFrame({
            "nearest_type": pd.Series(np.nan, index=price.index),
            "nearest_dir": pd.Series(np.nan, index=price.index),
            "nearest_dist_pct": pd.Series(np.nan, index=price.index),
        })

    # Forward-fill top/bottom values within each contiguous active block.
    active["top_ffill"] = active[col_top].ffill()
    active["bottom_ffill"] = active[col_bottom].ffill()
    active["mid"] = (active["top_ffill"] + active["bottom_ffill"]) / 2.0

    # Reindex to full index, forward fill.
    mid = active["mid"].reindex(price.index, method="ffill")
    top = active["top_ffill"].reindex(price.index, method="ffill")
    bottom = active["bottom_ffill"].reindex(price.index, method="ffill")
    typ = active[col_type].reindex(price.index, method="ffill")

    # Distance as % of price (approximately).
    dist = (mid - price) / price.abs()

    return pd.DataFrame({
        "nearest_type": typ,
        "nearest_dir": np.sign(dist),
        "nearest_dist_pct": dist * 100.0,
        "nearest_top": top,
        "nearest_bottom": bottom,
    })


def _compute_ib_end_ts(row: pd.Series) -> pd.Timestamp:
    """Return the IB end timestamp for an ib_facts row."""
    slot = row["session_slot"]
    basis = row["time_basis"]
    cfg_s = SESSION_CONFIGS_V5[slot]
    trading_day = pd.to_datetime(row["trading_day"]).date()
    ib_end_time = cfg_s["ib_end"]
    end_min = ib_end_time.hour * 60 + ib_end_time.minute

    if basis == "event_anchored" and slot in ("Tokyo IB", "London IB"):
        offset = int(row.get("et_window_offset_hours", 0))
        end_min = (end_min + offset * 60) % 1440

    return pd.Timestamp.combine(trading_day, time(end_min // 60, end_min % 60))


def _session_key_levels(session_df: pd.DataFrame, ict_bars: pd.DataFrame, ib_facts: pd.DataFrame, cfg: Dict) -> pd.DataFrame:
    """
    For each ib_facts session row, sample the anchor prices and PD-array context
    at the IB close time.  We intentionally sample at IB end (not mid_end) so that
    all anchors available up to that point are present and the PD-array context
    reflects the state just after IB formation.
    """
    keys = ib_facts[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    keys["sample_ts"] = ib_facts.apply(_compute_ib_end_ts, axis=1)

    # Build a lookup of timestamp -> anchor prices.
    anchor_cols = [c for c in session_df.columns if c not in ["open", "high", "low", "close", "volume"]]
    anchor_lookup = session_df[anchor_cols].copy()

    # Normalize all timestamp dtypes to nanoseconds for merge_asof.
    keys["sample_ts"] = pd.to_datetime(keys["sample_ts"]).astype("datetime64[ns]")

    # Sample nearest available anchor prices at sample_ts using merge_asof.
    anchor_lookup = anchor_lookup.reset_index()
    anchor_lookup["datetime"] = pd.to_datetime(anchor_lookup["datetime"]).astype("datetime64[ns]")
    keys_ts = keys[["sample_ts"]].dropna().reset_index()
    keys_ts["sample_ts"] = keys_ts["sample_ts"].astype("datetime64[ns]")
    sampled = pd.merge_asof(
        keys_ts.sort_values("sample_ts"),
        anchor_lookup.sort_values("datetime"),
        left_on="sample_ts",
        right_on="datetime",
        direction="backward",
    ).sort_values("index").set_index("index")

    # PD-array context sampled at sample_ts.
    ict_bars_reset = ict_bars.reset_index()
    ict_bars_reset["datetime"] = pd.to_datetime(ict_bars_reset["datetime"]).astype("datetime64[ns]")
    ict_sampled = pd.merge_asof(
        keys_ts.sort_values("sample_ts"),
        ict_bars_reset.sort_values("datetime"),
        left_on="sample_ts",
        right_on="datetime",
        direction="backward",
    ).sort_values("index").set_index("index")

    result = keys[["symbol", "trading_day", "session_slot", "time_basis"]].copy()
    for c in anchor_cols:
        result[c] = sampled[c].values

    # IB high/low/mid/range from ib_facts.
    for c in ["ib_high", "ib_low", "ib_mid", "ib_range", "first_break_dir", "max_ext_up", "max_ext_down", "mid_retest"]:
        if c in ib_facts.columns:
            result[c] = ib_facts[c].values

    # PD arrays at IB high and low.
    # We look for the nearest active array above/below the IB high and low at sample time.
    # Simplification: use the ict_sampled nearest top/bottom values.
    result["pd_array_fvg_top"] = ict_sampled["fvg_top"].values
    result["pd_array_fvg_bottom"] = ict_sampled["fvg_bottom"].values
    result["pd_array_ob_top"] = ict_sampled["ob_top"].values
    result["pd_array_ob_bottom"] = ict_sampled["ob_bottom"].values
    result["pd_array_breaker_top"] = ict_sampled["breaker_top"].values
    result["pd_array_breaker_bottom"] = ict_sampled["breaker_bottom"].values
    result["pd_array_mitigation_top"] = ict_sampled["mitigation_top"].values
    result["pd_array_mitigation_bottom"] = ict_sampled["mitigation_bottom"].values
    result["pd_array_rejection_top"] = ict_sampled["rejection_top"].values
    result["pd_array_rejection_bottom"] = ict_sampled["rejection_bottom"].values

    # Dealing range / premium / discount lines at IB end.
    for col in ["equilibrium", "is_discount", "is_premium", "range_high", "range_low"]:
        if col in ict_sampled.columns:
            result[col] = ict_sampled[col].values

    # IB mid zone.
    zone_cfg = cfg.get("ib_mid_zone", {})
    zone_low = result["ib_mid"] + zone_cfg.get("lower_frac", -0.10) * result["ib_range"]
    zone_high = result["ib_mid"] + zone_cfg.get("upper_frac", 0.10) * result["ib_range"]
    result["ib_mid_zone_low"] = zone_low
    result["ib_mid_zone_high"] = zone_high

    # Flag which array type overlaps the mid zone at sample time.
    def _overlaps(top, bottom, zlow, zhigh):
        return (top >= zlow) & (bottom <= zhigh)

    result["mid_zone_has_fvg"] = _overlaps(result["pd_array_fvg_top"], result["pd_array_fvg_bottom"], zone_low, zone_high).astype(int)
    result["mid_zone_has_ob"] = _overlaps(result["pd_array_ob_top"], result["pd_array_ob_bottom"], zone_low, zone_high).astype(int)
    result["mid_zone_has_breaker"] = _overlaps(result["pd_array_breaker_top"], result["pd_array_breaker_bottom"], zone_low, zone_high).astype(int)
    result["mid_zone_has_mitigation"] = _overlaps(result["pd_array_mitigation_top"], result["pd_array_mitigation_bottom"], zone_low, zone_high).astype(int)
    result["mid_zone_has_rejection"] = _overlaps(result["pd_array_rejection_top"], result["pd_array_rejection_bottom"], zone_low, zone_high).astype(int)

    return result


def process_symbol(sym: str, cfg: Dict) -> None:
    print(f"[{sym}] loading fused 1m data")
    # require_historical=True because ib_facts spans deep history (2006-2024) while
    # live storage only covers the most recent ~year.
    df_1m = load_fused_data(sym, timeframe="1m", require_historical=True)
    df_1m = _et_localize(df_1m)

    print(f"[{sym}] running anchor level computation")
    anchors = cfg.get("anchors", [])
    anchor_frames = [
        _compute_fixed_opens(df_1m, anchors),
        _compute_rolling_opens(df_1m, anchors),
        _compute_period_stats(df_1m, anchors),
    ]
    if any(a.get("type") == "h4_series" for a in anchors):
        anchor_frames.append(_compute_h4_opens(df_1m))

    session_df = pd.concat([df_1m[["open", "high", "low", "close", "volume"]]] + anchor_frames, axis=1)

    print(f"[{sym}] running ICT detectors")
    ict_bars = _detect_ict_features(df_1m, cfg)

    print(f"[{sym}] loading ib_facts for session grid")
    facts_path = DATA_DERIVED / f"ib_facts_{sym}.parquet"
    if not facts_path.exists():
        raise FileNotFoundError(f"{facts_path} not found; run ib_pipeline first.")
    ib_facts = pd.read_parquet(facts_path)

    print(f"[{sym}] joining key levels to session grid")
    result = _session_key_levels(session_df, ict_bars, ib_facts, cfg)

    out_path = DATA_DERIVED / f"ib_key_levels_{sym}.parquet"
    result.to_parquet(out_path, index=False)
    print(f"[{sym}] wrote {len(result)} rows x {len(result.columns)} cols -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default=",".join(INSTRUMENTS))
    args = parser.parse_args()

    global cfg
    cfg = _load_config()

    instruments = [s.strip().upper() for s in args.instruments.split(",") if s.strip()]
    for sym in instruments:
        try:
            process_symbol(sym, cfg)
        except Exception as e:
            print(f"[{sym}] ERROR: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
