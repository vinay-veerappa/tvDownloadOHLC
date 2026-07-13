"""Multi-Timeframe Range Detection Module.

Computes active ranges at multiple timeframes simultaneously — from micro
(5 min) to macro (weekly) — and presents them as a stack. Each range reports
H/L, width, position, touches, classification, and breakout status.

Also provides compression detection (ATR shrinking) and adaptive auto-range
(finding the tightest window where price has spent the most time).

Timeframes (from micro to macro):
    MICRO_5     — last 5 1m bars    (scalp / micro chop)
    MICRO_15    — last 15 1m bars   (short-term entry)
    MICRO_30    — last 30 1m bars   (chop detection)
    SHORT_60    — last 60 1m bars   (hourly range)
    SHORT_120   — last 120 1m bars  (session chunk)
    SESSION     — current session H/L (from session_ranges)
    RTH         — full RTH day H/L
    DAILY_1     — today's daily H/L
    DAILY_3     — rolling 3-day H/L
    DAILY_5     — rolling 5-day H/L
    WEEKLY      — current week H/L
    WEEKLY_2    — rolling 2-week H/L

Usage:
    from scripts.trader.signals.range_detection import (
        compute_range_stack,
        detect_compression,
        find_tightest_range,
        format_range_block,
    )

    # For intraday (day trading): micro + short + session + daily
    stack = compute_range_stack(df_1m, df_1d, df_1w, price, session_ranges,
                                tf_levels=["MICRO_5","MICRO_15","MICRO_30",
                                           "SHORT_60","SHORT_120","SESSION",
                                           "RTH","DAILY_1"])
    # For EOD: daily + multi-day
    stack = compute_range_stack(df_1m, df_1d, df_1w, price, session_ranges,
                                tf_levels=["RTH","DAILY_1","DAILY_3","DAILY_5"])
    # For weekly: weekly + multi-week
    stack = compute_range_stack(df_1m, df_1d, df_1w, price, session_ranges,
                                tf_levels=["DAILY_5","WEEKLY","WEEKLY_2"])
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent

# ── Timeframe definitions ───────────────────────────────────────────
# (label, lookback_bars for 1m, or days for daily, or weeks for weekly)
_INTRADAY_TFS = {
    "MICRO_5": 5,
    "MICRO_15": 15,
    "MICRO_30": 30,
    "SHORT_60": 60,
    "SHORT_120": 120,
}

_DAILY_TFS = {
    "DAILY_1": 1,
    "DAILY_3": 3,
    "DAILY_5": 5,
}

_WEEKLY_TFS = {
    "WEEKLY": 1,
    "WEEKLY_2": 2,
}

# Classification thresholds (% of price)
_TIGHT_THRESHOLD = 0.15   # < 0.15% = TIGHT
_WIDE_THRESHOLD = 0.30    # > 0.30% = WIDE

# Touch tolerance (in points/ticks — price within this distance of boundary counts as a touch)
_TOUCH_TOLERANCE = 2.0

# Compression thresholds
_COMPRESSION_THRESHOLD = 0.50   # 15m ATR / 60m ATR < 0.50 = compression
_EXTREME_COMPRESSION = 0.30     # < 0.30 = extreme coil


def _classify_width(width_pct: float) -> str:
    """Classify range width as TIGHT, NORMAL, or WIDE."""
    if width_pct < _TIGHT_THRESHOLD:
        return "TIGHT"
    elif width_pct > _WIDE_THRESHOLD:
        return "WIDE"
    return "NORMAL"


def compute_range_from_1m(
    df_1m: pd.DataFrame,
    lookback_bars: int,
    current_price: float,
) -> dict:
    """Compute range from the last N 1-minute bars.

    Returns dict with high, low, mid, width, width_pct, position_pct,
    is_inside, touches_high, touches_low, classification, breakout.
    """
    if df_1m is None or df_1m.empty or lookback_bars < 2:
        return {}

    recent = df_1m.tail(lookback_bars)
    if recent.empty:
        return {}

    high = float(recent["high"].max())
    low = float(recent["low"].min())
    mid = (high + low) / 2
    width = high - low
    width_pct = (width / current_price * 100) if current_price > 0 else 0
    position_pct = ((current_price - low) / width * 100) if width > 0 else 50
    is_inside = low <= current_price <= high

    # Touch counting: bars where high got within tolerance of range high,
    # or low got within tolerance of range low.
    touches_high = int((recent["high"] >= high - _TOUCH_TOLERANCE).sum())
    touches_low = int((recent["low"] <= low + _TOUCH_TOLERANCE).sum())

    # Breakout detection: did the latest bar close outside the range?
    latest_close = float(recent["close"].iloc[-1])
    breakout = "NONE"
    if latest_close > high:
        breakout = "BREAKOUT_UP"
    elif latest_close < low:
        breakout = "BREAKOUT_DOWN"

    # Time in range (minutes)
    time_in_range = len(recent)

    return {
        "high": high,
        "low": low,
        "mid": mid,
        "width": width,
        "width_pct": round(width_pct, 3),
        "position_pct": round(position_pct, 1),
        "is_inside": is_inside,
        "touches_high": touches_high,
        "touches_low": touches_low,
        "classification": _classify_width(width_pct),
        "breakout": breakout,
        "time_in_range_min": time_in_range,
    }


def compute_range_from_daily(
    df_1d: pd.DataFrame,
    days: int,
    current_price: float,
) -> dict:
    """Compute rolling range from the last N daily bars.

    Excludes the current incomplete bar (today) from the range calculation
    but uses it for breakout detection.
    """
    if df_1d is None or df_1d.empty or days < 1:
        return {}

    # Use the last N completed bars for the range
    # (today's bar is still forming, so we use prior N bars for H/L)
    if len(df_1d) > days:
        range_bars = df_1d.iloc[-(days + 1):-1]  # last N completed bars
    else:
        range_bars = df_1d.iloc[-days:]

    if range_bars.empty:
        return {}

    high = float(range_bars["high"].max())
    low = float(range_bars["low"].min())
    mid = (high + low) / 2
    width = high - low
    width_pct = (width / current_price * 100) if current_price > 0 else 0
    position_pct = ((current_price - low) / width * 100) if width > 0 else 50
    is_inside = low <= current_price <= high

    # Breakout: is today's price above/below the range?
    breakout = "NONE"
    if current_price > high:
        breakout = "BREAKOUT_UP"
    elif current_price < low:
        breakout = "BREAKOUT_DOWN"

    return {
        "high": high,
        "low": low,
        "mid": mid,
        "width": width,
        "width_pct": round(width_pct, 3),
        "position_pct": round(position_pct, 1),
        "is_inside": is_inside,
        "touches_high": int((range_bars["high"] >= high - _TOUCH_TOLERANCE * 5).sum()),
        "touches_low": int((range_bars["low"] <= low + _TOUCH_TOLERANCE * 5).sum()),
        "classification": _classify_width(width_pct),
        "breakout": breakout,
        "time_in_range_min": None,  # N/A for daily
    }


def compute_range_from_weekly(
    df_1w: pd.DataFrame,
    weeks: int,
    current_price: float,
) -> dict:
    """Compute rolling range from the last N weekly bars."""
    if df_1w is None or df_1w.empty or weeks < 1:
        return {}

    if len(df_1w) > weeks:
        range_bars = df_1w.iloc[-(weeks + 1):-1]
    else:
        range_bars = df_1w.iloc[-weeks:]

    if range_bars.empty:
        return {}

    high = float(range_bars["high"].max())
    low = float(range_bars["low"].min())
    mid = (high + low) / 2
    width = high - low
    width_pct = (width / current_price * 100) if current_price > 0 else 0
    position_pct = ((current_price - low) / width * 100) if width > 0 else 50
    is_inside = low <= current_price <= high

    breakout = "NONE"
    if current_price > high:
        breakout = "BREAKOUT_UP"
    elif current_price < low:
        breakout = "BREAKOUT_DOWN"

    return {
        "high": high,
        "low": low,
        "mid": mid,
        "width": width,
        "width_pct": round(width_pct, 3),
        "position_pct": round(position_pct, 1),
        "is_inside": is_inside,
        "touches_high": int((range_bars["high"] >= high - _TOUCH_TOLERANCE * 10).sum()),
        "touches_low": int((range_bars["low"] <= low + _TOUCH_TOLERANCE * 10).sum()),
        "classification": _classify_width(width_pct),
        "breakout": breakout,
        "time_in_range_min": None,
    }


def _format_range_from_session(session_data: dict, current_price: float) -> dict:
    """Convert a session_ranges dict into the same range format."""
    if not session_data or not session_data.get("high"):
        return {}
    high = session_data["high"]
    low = session_data["low"]
    mid = (high + low) / 2
    width = high - low
    width_pct = (width / current_price * 100) if current_price > 0 else 0
    position_pct = ((current_price - low) / width * 100) if width > 0 else 50
    is_inside = low <= current_price <= high

    breakout = "NONE"
    if current_price > high:
        breakout = "BREAKOUT_UP"
    elif current_price < low:
        breakout = "BREAKOUT_DOWN"

    return {
        "high": high,
        "low": low,
        "mid": mid,
        "width": width,
        "width_pct": round(width_pct, 3),
        "position_pct": round(position_pct, 1),
        "is_inside": is_inside,
        "touches_high": 0,  # Not tracked for session ranges
        "touches_low": 0,
        "classification": _classify_width(width_pct),
        "breakout": breakout,
        "time_in_range_min": None,
    }


def compute_range_stack(
    df_1m: pd.DataFrame | None,
    df_1d: pd.DataFrame | None,
    df_1w: pd.DataFrame | None,
    current_price: float,
    session_ranges: dict | None = None,
    tf_levels: list[str] | None = None,
) -> dict[str, dict]:
    """Compute ranges at multiple timeframes simultaneously.

    Args:
        df_1m: 1-minute DataFrame (ET-localized, tz-aware).
        df_1d: Daily DataFrame (optional, for daily/multi-day ranges).
        df_1w: Weekly DataFrame (optional, for weekly ranges).
        current_price: Current price.
        session_ranges: Output from compute_all_session_ranges() (for SESSION/RTH).
        tf_levels: List of timeframe labels to compute. If None, computes all intraday TFs.

    Returns:
        Dict keyed by timeframe label, each value is a range dict.
    """
    if tf_levels is None:
        tf_levels = list(_INTRADAY_TFS.keys())

    result: dict[str, dict] = {}

    for tf in tf_levels:
        try:
            if tf in _INTRADAY_TFS:
                r = compute_range_from_1m(df_1m, _INTRADAY_TFS[tf], current_price)
                if r:
                    result[tf] = r

            elif tf == "SESSION":
                if session_ranges:
                    # Use the most relevant completed session
                    for sess_key in ["ASIA", "LONDON", "NY_AM", "NY_LUNCH", "NY_PM"]:
                        sd = session_ranges.get(sess_key)
                        if sd and sd.get("high") and sd.get("range", 0) > 0:
                            r = _format_range_from_session(sd, current_price)
                            if r:
                                result[f"SESSION ({sess_key})"] = r
                                break

            elif tf == "RTH":
                if session_ranges:
                    sd = session_ranges.get("RTH")
                    if sd and sd.get("high"):
                        r = _format_range_from_session(sd, current_price)
                        if r:
                            result[tf] = r

            elif tf in _DAILY_TFS:
                r = compute_range_from_daily(df_1d, _DAILY_TFS[tf], current_price)
                if r:
                    result[tf] = r

            elif tf in _WEEKLY_TFS:
                r = compute_range_from_weekly(df_1w, _WEEKLY_TFS[tf], current_price)
                if r:
                    result[tf] = r

        except Exception as e:
            log.warning("[range_stack] %s failed: %s", tf, e)

    return result


def detect_compression(df_1m: pd.DataFrame) -> dict:
    """Detect compression by comparing ATR at different timeframes.

    Computes:
        - 15-bar ATR (micro)
        - 60-bar ATR (hourly)
        - session-to-date ATR (if enough data)
        - Compression ratio (15m ATR / 60m ATR)
        - Flag: COMPRESSING / NORMAL / EXPANDING

    Returns dict with atr_15, atr_60, ratio, status, alert.
    """
    if df_1m is None or df_1m.empty or len(df_1m) < 60:
        return {"status": "INSUFFICIENT_DATA"}

    try:
        recent = df_1m.tail(120)
        # True Range: max(high-low, |high-prev_close|, |low-prev_close|)
        tr = pd.DataFrame({
            "hl": recent["high"] - recent["low"],
            "hc": (recent["high"] - recent["close"].shift(1)).abs(),
            "lc": (recent["low"] - recent["close"].shift(1)).abs(),
        }).max(axis=1)

        atr_15 = float(tr.tail(15).mean())
        atr_60 = float(tr.tail(60).mean())

        ratio = atr_15 / atr_60 if atr_60 > 0 else 1.0

        if ratio < _EXTREME_COMPRESSION:
            status = "EXTREME_COMPRESSION"
            alert = "⚠ Extreme coil — expect violent expansion"
        elif ratio < _COMPRESSION_THRESHOLD:
            status = "COMPRESSING"
            alert = "⚠ Compression building — expect expansion soon"
        elif ratio > 1.5:
            status = "EXPANDING"
            alert = "Volatility expanding — momentum building"
        else:
            status = "NORMAL"
            alert = ""

        return {
            "atr_15": round(atr_15, 2),
            "atr_60": round(atr_60, 2),
            "ratio": round(ratio, 3),
            "status": status,
            "alert": alert,
        }
    except Exception as e:
        log.warning("[compression] Failed: %s", e)
        return {"status": "ERROR", "alert": str(e)}


def find_tightest_range(
    df_1m: pd.DataFrame,
    min_bars: int = 15,
    max_bars: int = 240,
) -> dict:
    """Find the tightest range window in the last max_bars.

    Scans all window sizes from min_bars to max_bars and finds the one
    with the smallest range (high - low) where price is currently inside.

    This finds "the range that matters right now" — the level pair
    traders are actually watching, regardless of fixed timeframe boundaries.

    Returns dict with high, low, width, width_pct, bars, start_time, end_time.
    """
    if df_1m is None or df_1m.empty or len(df_1m) < min_bars:
        return {}

    try:
        recent = df_1m.tail(max_bars)
        current_price = float(recent["close"].iloc[-1])

        best = None
        best_width = float("inf")

        for n in range(min_bars, min(len(recent), max_bars) + 1):
            window = recent.tail(n)
            high = float(window["high"].max())
            low = float(window["low"].min())
            width = high - low

            # Only consider windows where current price is inside
            if low <= current_price <= high and width < best_width and width > 0:
                best_width = width
                best = {
                    "high": high,
                    "low": low,
                    "mid": (high + low) / 2,
                    "width": width,
                    "width_pct": round(width / current_price * 100, 3),
                    "bars": n,
                    "classification": _classify_width(width / current_price * 100) if current_price > 0 else "UNKNOWN",
                    "start_time": window.index[0],
                    "end_time": window.index[-1],
                }

        return best or {}
    except Exception as e:
        log.warning("[tightest_range] Failed: %s", e)
        return {}


def format_range_block(range_stack: dict, compression: dict | None = None) -> str:
    """Format the range stack + compression into a cheat-sheet block.

    Args:
        range_stack: Output from compute_range_stack().
        compression: Output from detect_compression() (optional).

    Returns:
        Formatted string for the cheat sheet.
    """
    if not range_stack:
        return "== RANGE STACK ==\nNo range data available."

    lines = ["== RANGE STACK =="]

    # Table header
    lines.append("| Timeframe | High | Low | Width | % | Pos | Touches | Status |")
    lines.append("|---|---|---|---|---|---|---|---|")

    # Display labels
    display_labels = {
        "MICRO_5": "Micro 5m",
        "MICRO_15": "Micro 15m",
        "MICRO_30": "Micro 30m",
        "SHORT_60": "Short 60m",
        "SHORT_120": "Short 2h",
        "RTH": "RTH Day",
        "DAILY_1": "Daily 1d",
        "DAILY_3": "3-Day",
        "DAILY_5": "5-Day",
        "WEEKLY": "Weekly",
        "WEEKLY_2": "2-Week",
    }

    for tf, r in range_stack.items():
        label = display_labels.get(tf, tf)
        high = r.get("high", 0)
        low = r.get("low", 0)
        width = r.get("width", 0)
        width_pct = r.get("width_pct", 0)
        pos = r.get("position_pct", 50)
        th = r.get("touches_high", 0)
        tl = r.get("touches_low", 0)
        breakout = r.get("breakout", "NONE")
        inside = r.get("is_inside", False)

        if breakout == "BREAKOUT_UP":
            status = "↑ BROKE OUT"
        elif breakout == "BREAKOUT_DOWN":
            status = "↓ BROKE OUT"
        elif inside:
            status = f"IN RANGE ({r.get('classification', '?')})"
        else:
            status = "OUTSIDE"

        pos_str = f"{pos:.0f}%" if pos != 50 else "50%"
        lines.append(
            f"| {label} | {high:,.2f} | {low:,.2f} | {width:,.2f} | {width_pct:.2f}% | {pos_str} | H:{th} L:{tl} | {status} |"
        )

    # Compression section
    if compression and compression.get("status") not in ("INSUFFICIENT_DATA", "ERROR"):
        lines.append("")
        lines.append("== COMPRESSION CHECK ==")
        if compression.get("atr_15") is not None:
            lines.append(f"15m ATR: {compression['atr_15']:.2f} pts | 60m ATR: {compression['atr_60']:.2f} pts")
            lines.append(f"Ratio: {compression['ratio']:.2f} — {compression['status']}")
        if compression.get("alert"):
            lines.append(compression["alert"])

    return "\n".join(lines)


def format_adaptive_range_block(adaptive: dict) -> str:
    """Format the tightest adaptive range into a cheat-sheet block."""
    if not adaptive:
        return ""
    high = adaptive.get("high", 0)
    low = adaptive.get("low", 0)
    mid = adaptive.get("mid", 0)
    width = adaptive.get("width", 0)
    width_pct = adaptive.get("width_pct", 0)
    bars = adaptive.get("bars", 0)
    classification = adaptive.get("classification", "?")
    start = adaptive.get("start_time")
    end = adaptive.get("end_time")
    start_str = start.strftime("%H:%M") if hasattr(start, "strftime") else "?"
    end_str = end.strftime("%H:%M") if hasattr(end, "strftime") else "?"

    lines = ["== ADAPTIVE RANGE (tightest window) =="]
    lines.append(f"High {high:,.2f} | Low {low:,.2f} | Mid {mid:,.2f}")
    lines.append(f"Width {width:,.2f} pts ({width_pct:.2f}%) — {classification}")
    lines.append(f"Window: {bars} bars ({start_str} → {end_str})")
    return "\n".join(lines)