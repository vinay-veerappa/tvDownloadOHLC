"""C6: Weekly Profile signal.

Computes the ICT weekly profile (bullish run, bearish run, inside, outside, balanced)
based on where the High of Week (HOW) and Low of Week (LOW) have formed.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger(__name__)


def compute_weekly_profile(ticker: str = "NQ1", current_price: float = 0) -> dict:
    """Compute weekly profile from daily parquet.

    Returns:
        dict with week_high, week_low, profile_type, current_position, day_context
    """
    from pathlib import Path
    _REPO = Path(__file__).parent.parent.parent.parent

    result = {
        "week_high": None, "week_low": None,
        "week_high_day": None, "week_low_day": None,
        "profile_type": "balanced",
        "current_position": "unknown",
        "day_context": "unknown",
        "alignment": "NEUTRAL",
    }

    try:
        df = pd.read_parquet(_REPO / "data" / f"{ticker}_1d.parquet")
        if df.index.tz is not None:
            df.index = df.index.tz_convert("US/Eastern")
        else:
            df.index = df.index.tz_localize("UTC").tz_convert("US/Eastern")
    except Exception as e:
        log.warning("[weekly] Could not load 1d parquet: %s", e)
        return result

    # Current week Monday anchor
    today = date.today()
    monday = today - timedelta(days=today.weekday())  # Monday = 0

    # Filter to current week's bars
    week_bars = df[df.index.date >= monday]
    if week_bars.empty:
        result["day_context"] = "Monday — week starting, no data yet"
        return result

    week_high = float(week_bars["high"].max())
    week_low = float(week_bars["low"].min())
    result["week_high"] = round(week_high, 2)
    result["week_low"] = round(week_low, 2)

    # Which day did HOW/LOW form?
    high_day = week_bars["high"].idxmax()
    low_day = week_bars["low"].idxmin()
    result["week_high_day"] = high_day.strftime("%A") if high_day else "N/A"
    result["week_low_day"] = low_day.strftime("%A") if low_day else "N/A"

    # Profile classification
    today_idx = today.weekday()  # 0=Mon, 4=Fri
    high_early = high_day and high_day.weekday() <= 1  # Mon/Tue
    low_early = low_day and low_day.weekday() <= 1

    # Prior week range for inside/outside check
    prior_week = df[df.index.date < monday].tail(5)
    if not prior_week.empty:
        prior_high = float(prior_week["high"].max())
        prior_low = float(prior_week["low"].min())
        if week_high > prior_high and week_low < prior_low:
            result["profile_type"] = "outside_week"
        elif week_high <= prior_high and week_low >= prior_low:
            result["profile_type"] = "inside_week"
        elif low_early and not high_early:
            result["profile_type"] = "bullish_run"
        elif high_early and not low_early:
            result["profile_type"] = "bearish_run"
        else:
            result["profile_type"] = "balanced"
    else:
        # No prior week data
        if low_early and not high_early:
            result["profile_type"] = "bullish_run"
        elif high_early and not low_early:
            result["profile_type"] = "bearish_run"
        else:
            result["profile_type"] = "balanced"

    # Current position
    if current_price > 0 and week_high and week_low:
        range_pct = (current_price - week_low) / (week_high - week_low) * 100 if week_high > week_low else 50
        if range_pct > 85:
            result["current_position"] = "near HOW — reversal risk"
        elif range_pct < 15:
            result["current_position"] = "near LOW — bounce risk"
        else:
            result["current_position"] = "mid-range — continuation likely"

    # Day context
    if today_idx <= 1:
        result["day_context"] = "Mon/Tue — LOW/HOW likely forming"
    elif today_idx == 2:
        result["day_context"] = "Wed — mid-week inflection"
    else:
        result["day_context"] = "Thu/Fri — HOW/LOW likely set"

    return result


def format_weekly_block(data: dict) -> str:
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    read = cfg["weekly_profiles"].get(data["profile_type"], {}).get("read", "")

    lines = ["== WEEKLY PROFILE =="]
    lines.append(f"Week: HIGH {data['week_high']} ({data['week_high_day']}) | LOW {data['week_low']} ({data['week_low_day']})")
    lines.append(f"Profile: {data['profile_type']} — {read}")
    lines.append(f"Position: {data['current_position']}")
    lines.append(f"Day context: {data['day_context']}")
    return "\n".join(lines)