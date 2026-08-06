"""HTF Weekly EMA(5) Excursion Analysis Engine

Calculates percentage distance excursions from completed prior Weekly EMA(5),
52-week historical distributions (Mean, Median, Mode), 2%-3% magnet zones,
and NFP Friday macro anomaly detection. Supports any futures ticker.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).parent.parent.parent
ET = pytz.timezone("America/New_York")


def compute_htf_ema_analysis(ticker: str = "NQ1", target_date: str | None = None) -> dict[str, Any]:
    """Computes HTF Weekly EMA(5) excursion statistics for a ticker at target_date.
    
    Returns:
        Dict containing prior_weekly_ema, current_dist_pct, mean_dup, median_dup, mode_dup,
        mean_ddn, median_ddn, mode_ddn, is_2to3_zone, is_nfp_friday, etc.
    """
    res = {
        "ticker": ticker,
        "target_date": target_date,
        "weekly_ema5": None,
        "dist_pct": 0.0,
        "direction": "flat",
        "is_2to3_zone": False,
        "is_nfp_friday": False,
        "dup_stats": {"mean": 0.0, "median": 0.0, "mode": 0.0},
        "ddn_stats": {"mean": 0.0, "median": 0.0, "mode": 0.0},
        "binned_modes": {"dup_mode_bin": "0.0-0.5%", "ddn_mode_bin": "0.0-0.5%"},
    }

    daily_path = REPO_ROOT / "data" / f"{ticker}_1d.parquet"
    if not daily_path.exists():
        log.warning("[htf_ema] Daily parquet missing for %s", ticker)
        return res

    df_1d = pd.read_parquet(daily_path)
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    if df_1d.empty:
        return res

    # Resolve target date to actual trading session date (18:00 ET bar belongs to next session day)
    def _session_date(dt: pd.Timestamp) -> datetime.date:
        # If timestamp is 17:00 ET or later, it belongs to the next calendar trading day
        if dt.hour >= 17:
            return (dt + pd.Timedelta(days=1)).date()
        return dt.date()

    df_1d["session_date"] = [ _session_date(t) for t in df_1d.index ]

    # Resolve target date
    if target_date:
        t_dt = pd.to_datetime(target_date).date()
        df_1d = df_1d[df_1d["session_date"] <= t_dt]

    if len(df_1d) < 15:
        return res

    # Detect NFP Friday (First Friday of month)
    eval_date = t_dt if target_date else last_bar_session
    is_friday = eval_date.weekday() == 4
    is_first_week = eval_date.day <= 7
    res["is_nfp_friday"] = bool(is_friday and is_first_week)

    # Resample daily data to completed weekly bars (W-FRI)
    df_wk = df_1d.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    }).dropna()

    if len(df_wk) < 5:
        return res

    # Compute Weekly EMA(5)
    df_wk["ema5"] = df_wk["close"].ewm(span=5, adjust=False).mean()

    # Prior completed week's EMA(5)
    # If last daily bar is Friday close, current week is completing; use iloc[-2] as completed prior week
    # Otherwise use iloc[-2] to avoid in-progress week
    prior_wk = df_wk.iloc[-2] if len(df_wk) >= 2 else df_wk.iloc[-1]
    prior_ema5 = float(prior_wk["ema5"])
    res["weekly_ema5"] = round(prior_ema5, 2)

    # Current daily close distance from prior Weekly EMA(5)
    current_close = float(df_1d.iloc[-1]["close"])
    dist_pct = ((current_close - prior_ema5) / prior_ema5) * 100.0
    res["dist_pct"] = round(dist_pct, 2)
    res["direction"] = "up" if dist_pct >= 0 else "down"
    res["is_2to3_zone"] = bool(2.0 <= abs(dist_pct) <= 3.0)

    # Compute 52-week historical excursions
    # Exclude current week, take up to 52 prior completed weeks
    lookback_wks = df_wk.iloc[-53:-1] if len(df_wk) >= 53 else df_wk.iloc[:-1]
    
    dup_list = []
    ddn_list = []

    for i in range(1, len(lookback_wks)):
        prev_ema = float(lookback_wks.iloc[i-1]["ema5"])
        cur_hi = float(lookback_wks.iloc[i]["high"])
        cur_lo = float(lookback_wks.iloc[i]["low"])

        d_up = max(0.0, ((cur_hi - prev_ema) / prev_ema) * 100.0)
        d_dn = max(0.0, ((prev_ema - cur_lo) / prev_ema) * 100.0)

        dup_list.append(d_up)
        ddn_list.append(d_dn)

    # Function to compute Mean, Median, Binned Mode (0.5% bins)
    def calc_excursion_stats(arr: list[float]) -> tuple[dict, str]:
        if not arr:
            return {"mean": 0.0, "median": 0.0, "mode": 0.0}, "0.0-0.5%"
        
        s = pd.Series(arr)
        mean_val = float(s.mean())
        med_val = float(s.median())

        # Bin in 0.5% increments
        bins = np.arange(0.0, max(s.max() + 1.0, 5.0), 0.5)
        binned = pd.cut(s[s > 0.001], bins=bins)  # purge zero bin
        mode_counts = binned.value_counts()
        
        if not mode_counts.empty:
            top_bin = mode_counts.index[0]
            mode_center = float((top_bin.left + top_bin.right) / 2.0)
            mode_str = f"{top_bin.left:.1f}%-{top_bin.right:.1f}%"
        else:
            mode_center = med_val
            mode_str = "0.0-0.5%"

        return {
            "mean": round(mean_val, 2),
            "median": round(med_val, 2),
            "mode": round(mode_center, 2),
        }, mode_str

    dup_stats, dup_mode_bin = calc_excursion_stats(dup_list)
    ddn_stats, ddn_mode_bin = calc_excursion_stats(ddn_list)

    res["dup_stats"] = dup_stats
    res["ddn_stats"] = ddn_stats
    res["binned_modes"] = {
        "dup_mode_bin": dup_mode_bin,
        "ddn_mode_bin": ddn_mode_bin,
    }

    return res


def format_htf_ema_block(data: dict) -> str:
    """Format HTF EMA Analysis into a narrative cheat sheet block."""
    if not data or data.get("weekly_ema5") is None:
        return "== HTF EMA ANALYSIS ==\nNo Weekly EMA(5) data available"

    lines = ["== HTF WEEKLY EMA(5) EXCURSION ANALYSIS =="]
    lines.append(f"Ticker: {data['ticker']} | Target Date: {data['target_date']}")
    lines.append(f"Completed Weekly EMA(5): {data['weekly_ema5']} | Current Distance: {data['dist_pct']:+.2f}%")
    
    zone_str = "YES (2%-3% Reversion Magnet Active)" if data['is_2to3_zone'] else "No (Normal Range)"
    nfp_str = "YES (First Friday 08:30 AM Anchor Active)" if data['is_nfp_friday'] else "No"
    
    lines.append(f"2%-3% Magnet Zone: {zone_str} | NFP Friday: {nfp_str}")
    lines.append("52-WEEK HISTORICAL EXCURSION STATS:")
    
    dup = data['dup_stats']
    ddn = data['ddn_stats']
    bins = data['binned_modes']
    
    lines.append(f"  ➤ Upward (dUp):   Mean={dup['mean']}% | Median={dup['median']}% | Mode={dup['mode']}% (Bin: {bins['dup_mode_bin']})")
    lines.append(f"  ➤ Downward (dDn): Mean={ddn['mean']}% | Median={ddn['median']}% | Mode={ddn['mode']}% (Bin: {bins['ddn_mode_bin']})")
    
    return "\n".join(lines)
