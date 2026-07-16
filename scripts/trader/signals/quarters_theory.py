"""Quarters Theory signal module.

Two main components:

1. **Hourly Candle Quarter Analysis** — divides the current hour into 4 quarters
   (Q1: :00-:14, Q2: :15-:29, Q3: :30-:44, Q4: :45-:59) and analyzes:
   - Which quarter has the hour's HOD/LOD
   - Doji triggers (Q1 sweep and retreat, taking both sides)
   - Instat extreme confirmation (Q1 sets extreme, Q2 confirms)
   - Structure breakdown (Q1 extreme breached in later quarters → Doji)
   - Historical Q1 High/Low probabilities from precomputed quarter stats

2. **Overnight Direction Combinations** — classifies Asia+London status combos
   as trending or contradicting, with OU break probabilities and NY1 expectations.

Data sources:
  - `data/derived/hourly_quarter_stats_{ticker}.json` — historical Q1 High/Low probabilities
  - Live 1m parquet — current hour's Q1-Q4 structure (via live_sessions parameter)
  - Profiler JSON — Asia/London status for overnight combination classification

Quarter definitions (any timeframe → 4 equal parts):
  Q1 (Initial): 0-25% of timeframe (anticipation quarter)
  Q2 (Confirm): 25-50% (confirmation quarter)
  Q3 (Extend):  50-75% (extension quarter)
  Q4 (Complete): 75-100% (completion quarter)

For hourly candles: Q1=:00-:14, Q2=:15-:29, Q3=:30-:44, Q4=:45-:59
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
_DATA = _REPO / "data"
_DERIVED = _REPO / "data" / "derived"

# ─── Overnight Direction Combinations ─────────────────────────────────
# Based on Boot Camp Week 2 Day 5 material.
# Trending = Asia and London agree (both Long or both Short)
# Contradicting = Asia and London disagree

# Trending combinations (bullish examples from Boot Camp):
_TRENDING_COMBOS = {
    ("Long True", "Short False"): {
        "label": "Trending Bullish",
        "asia_ou_break": 75, "asia_ou_mode": "09:30-09:45",
        "london_ou_break": 80, "london_ou_mode": "07:45-08:30",
        "lod_support": True,
        "ny1_expectation": "Best supports hitting Asia OU during NY1 when trending higher",
    },
    ("Long True", "Long True"): {
        "label": "Trending Bullish",
        "asia_ou_break": 59, "asia_ou_mode": "02:30",
        "london_ou_break": 73, "london_ou_mode": "09:30-09:45",
        "lod_support": True,
        "ny1_expectation": "Lower probability of Asia OU break than other trending types",
    },
    ("Short False", "Long True"): {
        "label": "Trending Bullish",
        "asia_ou_break": 76, "asia_ou_mode": "10:00",
        "london_ou_break": 75, "london_ou_mode": "09:30",
        "lod_support": True,
        "ny1_expectation": "Supports overnight LOD",
    },
    ("Short False", "Short False"): {
        "label": "Trending Bullish (Firecracker)",
        "asia_ou_break": 91, "asia_ou_mode": "02:30-03:30",
        "london_ou_break": 86, "london_ou_mode": "07:30-09:45",
        "lod_support": False,
        "ny1_expectation": "Full firecracker — crashes through P12, makes new LOD even in bullish trend",
    },
}


def _is_trending(asia_status: str, london_status: str) -> bool:
    """Check if Asia and London agree (trending) or disagree (contradicting).

    Trending: both Long* or both Short*
    Contradicting: one Long*, one Short*
    """
    asia_dir = "L" if asia_status.startswith("Long") else ("S" if asia_status.startswith("Short") else "N")
    lon_dir = "L" if london_status.startswith("Long") else ("S" if london_status.startswith("Short") else "N")
    return asia_dir == lon_dir and asia_dir != "N"


def _get_combo_info(asia_status: str, london_status: str) -> dict:
    """Get overnight direction combination info."""
    key = (asia_status, london_status)
    if key in _TRENDING_COMBOS:
        return _TRENDING_COMBOS[key]

    trending = _is_trending(asia_status, london_status)
    if not trending:
        return {
            "label": "Contradicting Market",
            "asia_ou_break": None,
            "london_ou_break": None,
            "lod_support": False,
            "ny1_expectation": "Range-bound RTH. Focus on 9:45 reversal or four-step reversal. LOD/HOD likely after RTH open. Use range/cash-flow systems.",
        }

    # Trending but not in the specific combo table — generic trending
    return {
        "label": f"Trending ({asia_status}/{london_status})",
        "asia_ou_break": None,
        "london_ou_break": None,
        "lod_support": True,
        "ny1_expectation": "Trending market — use trend systems. Position before 9:30.",
    }


# ─── Historical Quarter Stats ─────────────────────────────────────────


def _load_quarter_stats(ticker: str) -> dict:
    """Load precomputed hourly quarter stats."""
    path = _DERIVED / f"hourly_quarter_stats_{ticker}.json"
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.warning("[quarters] Failed to load %s: %s", path.name, e)
    return {}


def _get_hour_q1_stats(quarter_stats: dict, hour: int) -> dict | None:
    """Get Q1 High/Low probability for a specific hour.

    Returns:
        {total, q1_high_pct, q1_low_pct, q1_both_pct, q1_neither_pct, q_breakouts}
    """
    hour_key = str(hour)
    hour_data = quarter_stats.get(hour_key)
    if not hour_data:
        return None

    total = hour_data.get("total_sessions", 0)
    if total == 0:
        return None

    h_high = hour_data.get("h_high_q", {})
    h_low = hour_data.get("h_low_q", {})
    q1_excl = hour_data.get("q1_exclusive", {})
    q_breakouts = hour_data.get("q_breakouts", {})

    q1_high = h_high.get("Q1", 0)
    q1_low = h_low.get("Q1", 0)
    q1_both = q1_excl.get("both", 0)
    q1_high_only = q1_excl.get("high_only", 0)
    q1_low_only = q1_excl.get("low_only", 0)
    q1_neither = q1_excl.get("neither", 0)

    return {
        "total": total,
        "q1_high_pct": round(q1_high / total * 100, 1),
        "q1_low_pct": round(q1_low / total * 100, 1),
        "q1_both_pct": round(q1_both / total * 100, 1),
        "q1_high_only_pct": round(q1_high_only / total * 100, 1),
        "q1_low_only_pct": round(q1_low_only / total * 100, 1),
        "q1_neither_pct": round(q1_neither / total * 100, 1),
        # Q1 boundary violation rates
        "q1_high_violated_q2_pct": round(q_breakouts.get("Q1", {}).get("high_violated_in", {}).get("Q2", 0) / total * 100, 1) if q_breakouts else 0,
        "q1_low_violated_q2_pct": round(q_breakouts.get("Q1", {}).get("low_violated_in", {}).get("Q2", 0) / total * 100, 1) if q_breakouts else 0,
        "q1_high_never_violated_pct": round(q_breakouts.get("Q1", {}).get("high_violated_in", {}).get("Never", 0) / total * 100, 1) if q_breakouts else 0,
        "q1_low_never_violated_pct": round(q_breakouts.get("Q1", {}).get("low_violated_in", {}).get("Never", 0) / total * 100, 1) if q_breakouts else 0,
    }


# ─── Live Hourly Candle Analysis ───────────────────────────────────────


def _analyze_hour_quarters(df: pd.DataFrame, hour_start: pd.Timestamp, hour_end: pd.Timestamp) -> dict:
    """Analyze a single hour's quarter structure from 1m data.

    Args:
        df: 1-minute DataFrame with ET-localized tz-aware index.
        hour_start: Start of the hour (e.g., 10:00:00 ET).
        hour_end: End of the hour (e.g., 11:00:00 ET).

    Returns:
        {open, close, high, low, body_pct, q1, q2, q3, q4, hour_high_q, hour_low_q,
         box5_high, box5_low, trigger1, trigger2, structure_status}
    """
    hour_df = df[(df.index >= hour_start) & (df.index < hour_end)]
    if hour_df.empty or len(hour_df) < 5:
        return {"status": "no_data"}

    hour_open = float(hour_df["open"].iloc[0])
    hour_close = float(hour_df["close"].iloc[-1])
    hour_high = float(hour_df["high"].max())
    hour_low = float(hour_df["low"].min())
    body = abs(hour_close - hour_open)
    rng = hour_high - hour_low
    body_pct = (body / rng * 100) if rng > 0 else 0

    # '05 box (first 5 minutes)
    box5_df = hour_df[(hour_df.index >= hour_start) & (hour_df.index < hour_start + pd.Timedelta(minutes=5))]
    box5_high = float(box5_df["high"].max()) if not box5_df.empty else None
    box5_low = float(box5_df["low"].min()) if not box5_df.empty else None

    # Quarter analysis
    quarters = {}
    for q, (qs_min, qe_min) in enumerate([(0, 15), (15, 30), (30, 45), (45, 60)]):
        q_start = hour_start + pd.Timedelta(minutes=qs_min)
        q_end = hour_start + pd.Timedelta(minutes=qe_min)
        q_df = hour_df[(hour_df.index >= q_start) & (hour_df.index < q_end)]
        if q_df.empty:
            quarters[f"Q{q+1}"] = {"high": None, "low": None, "open": None, "close": None,
                                    "high_time": None, "low_time": None}
        else:
            quarters[f"Q{q+1}"] = {
                "high": float(q_df["high"].max()),
                "low": float(q_df["low"].min()),
                "open": float(q_df["open"].iloc[0]),
                "close": float(q_df["close"].iloc[-1]),
                "high_time": q_df["high"].idxmax().strftime("%H:%M"),
                "low_time": q_df["low"].idxmin().strftime("%H:%M"),
            }

    # Which quarter has the hour's high/low
    hour_high_q = None
    hour_low_q = None
    for q_name in ["Q1", "Q2", "Q3", "Q4"]:
        qd = quarters[q_name]
        if qd["high"] is not None and qd["high"] == hour_high:
            hour_high_q = q_name
        if qd["low"] is not None and qd["low"] == hour_low:
            hour_low_q = q_name

    # Q1 structure
    q1 = quarters["Q1"]
    if hour_high_q == "Q1" and hour_low_q != "Q1":
        structure = "Q1 High (low later)"
    elif hour_low_q == "Q1" and hour_high_q != "Q1":
        structure = "Q1 Low (high later)"
    elif hour_high_q == "Q1" and hour_low_q == "Q1":
        structure = "Q1 Both (contained)"
    elif hour_high_q != "Q1" and hour_low_q != "Q1":
        structure = "Q1 Neither (expansion)"
    else:
        structure = "?"

    # Doji triggers
    trigger1 = False  # Q1 swept one side of '05 box then retreated
    trigger2 = False  # Q1 took BOTH sides of '05 box

    if box5_high is not None and box5_low is not None and q1["high"] is not None and q1["low"] is not None:
        took_both = (q1["high"] > box5_high and q1["low"] < box5_low)
        trigger2 = took_both

        swept_high = q1["high"] > box5_high
        swept_low = q1["low"] < box5_low
        retreated = q1["close"] is not None and box5_low < q1["close"] < box5_high
        trigger1 = (swept_high or swept_low) and retreated

    # Instat extreme: Q1 sets extreme, Q2 confirms
    instat_confirmed = False
    instat_type = None
    if hour_high_q == "Q1" and hour_low_q != "Q1":
        # Q1 has the high — check if Q2 confirms by NOT breaking Q1 high
        instat_type = "high"
        # Instat confirmed if Q2-Q4 never break Q1 high
        for q_name in ["Q2", "Q3", "Q4"]:
            if quarters[q_name]["high"] is not None and quarters[q_name]["high"] > q1["high"]:
                break
        else:
            instat_confirmed = True
    elif hour_low_q == "Q1" and hour_high_q != "Q1":
        instat_type = "low"
        for q_name in ["Q2", "Q3", "Q4"]:
            if quarters[q_name]["low"] is not None and quarters[q_name]["low"] < q1["low"]:
                break
        else:
            instat_confirmed = True

    # Structure breakdown: Q1 extreme confirmed but breached later → Doji
    structure_broken = False
    if hour_high_q == "Q1" and instat_confirmed:
        structure_broken = False  # Confirmed = NOT broken
    elif hour_high_q == "Q1" and not instat_confirmed:
        structure_broken = True  # Q1 high was breached → Doji

    # Classification
    if trigger1 or trigger2 or (structure_broken and body_pct < 30):
        classification = "DOJI"
    elif hour_close > hour_open and body_pct > 30:
        classification = "BULLISH"
    elif hour_close < hour_open and body_pct > 30:
        classification = "BEARISH"
    else:
        classification = "NEUTRAL"

    return {
        "status": "ok",
        "open": round(hour_open, 2),
        "close": round(hour_close, 2),
        "high": round(hour_high, 2),
        "low": round(hour_low, 2),
        "body_pct": round(body_pct, 1),
        "classification": classification,
        "structure": structure,
        "hour_high_q": hour_high_q,
        "hour_low_q": hour_low_q,
        "box5_high": round(box5_high, 2) if box5_high else None,
        "box5_low": round(box5_low, 2) if box5_low else None,
        "trigger1": trigger1,
        "trigger2": trigger2,
        "instat_type": instat_type,
        "instat_confirmed": instat_confirmed,
        "structure_broken": structure_broken,
        "quarters": quarters,
    }


# ─── Main computation ────────────────────────────────────────────────


def compute_quarters(
    ticker: str = "NQ1",
    df_1m: pd.DataFrame | None = None,
    now_et: datetime | None = None,
    asia_status: str = "",
    london_status: str = "",
) -> dict:
    """Compute quarters theory data for the narrative cheat sheet.

    Args:
        ticker: Ticker symbol.
        df_1m: 1-minute DataFrame with ET-localized index. Required for live
            hourly candle analysis.
        now_et: Current ET datetime. Defaults to now.
        asia_status: Today's resolved Asia session status (e.g. "Short False").
        london_status: Today's resolved London session status.

    Returns:
        dict with overnight_combo, current_hour, recent_hours, quarter_stats
    """
    if now_et is None:
        import pytz
        now_et = datetime.now(pytz.timezone("America/New_York"))

    result: dict[str, Any] = {
        "ticker": ticker,
        "now_et": now_et.strftime("%H:%M ET"),
        "overnight_combo": {},
        "current_hour": {},
        "recent_hours": [],
        "quarter_stats": {},
    }

    # ── Overnight direction combination ──
    if asia_status and london_status:
        combo = _get_combo_info(asia_status, london_status)
        result["overnight_combo"] = {
            "asia_status": asia_status,
            "london_status": london_status,
            "label": combo["label"],
            "trending": _is_trending(asia_status, london_status),
            "asia_ou_break": combo.get("asia_ou_break"),
            "asia_ou_mode": combo.get("asia_ou_mode"),
            "london_ou_break": combo.get("london_ou_break"),
            "london_ou_mode": combo.get("london_ou_mode"),
            "lod_support": combo.get("lod_support"),
            "ny1_expectation": combo.get("ny1_expectation"),
        }

    # ── Load historical quarter stats ──
    quarter_stats = _load_quarter_stats(ticker)
    if quarter_stats:
        # Get stats for current hour and key RTH hours
        current_hour_num = now_et.hour
        result["quarter_stats"]["current"] = _get_hour_q1_stats(quarter_stats, current_hour_num)
        for h in [9, 10, 11, 12, 13, 14, 15]:
            result["quarter_stats"][f"{h:02d}"] = _get_hour_q1_stats(quarter_stats, h)

    # ── Live hourly candle analysis ──
    if df_1m is not None and not df_1m.empty:
        import pytz as _pytz
        ET = _pytz.timezone("America/New_York")
        if df_1m.index.tz is None:
            df_1m.index = pd.DatetimeIndex(df_1m.index).tz_localize("UTC").tz_convert(ET)
        elif df_1m.index.tz != ET:
            df_1m.index = df_1m.index.tz_convert(ET)

        # Current hour
        current_hour_start = pd.Timestamp(now_et).tz_convert(ET) if pd.Timestamp(now_et).tzinfo else pd.Timestamp(now_et).tz_localize(ET)
        current_hour_start = current_hour_start.replace(minute=0, second=0, microsecond=0)
        current_hour_end = current_hour_start + pd.Timedelta(hours=1)
        result["current_hour"] = _analyze_hour_quarters(df_1m, current_hour_start, current_hour_end)
        result["current_hour"]["hour_label"] = current_hour_start.strftime("%H:00-%H:00")

        # Recent completed hours (up to 3)
        recent = []
        for i in range(1, 4):
            h_start = current_hour_start - pd.Timedelta(hours=i)
            h_end = h_start + pd.Timedelta(hours=1)
            h_data = _analyze_hour_quarters(df_1m, h_start, h_end)
            if h_data.get("status") == "ok":
                h_data["hour_label"] = h_start.strftime("%H:00")
                recent.append(h_data)
        result["recent_hours"] = recent

    return result


# ─── Formatting ──────────────────────────────────────────────────────


def format_quarters_block(data: dict) -> str:
    """Format the quarters theory data into a compact cheat-sheet block."""
    if not data:
        return "== QUARTERS THEORY ==\nNo data available."

    ticker = data.get("ticker", "?")
    now_str = data.get("now_et", "?")
    base_label = ticker.replace("1", "").upper()

    lines = [f"== QUARTERS THEORY ({base_label}) =="]
    lines.append(f"Time: {now_str}")

    # ── Overnight direction combination ──
    combo = data.get("overnight_combo", {})
    if combo:
        lines.append(f"\nOvernight Combo: Asia={combo.get('asia_status','?')} / London={combo.get('london_status','?')}")
        trending = combo.get("trending")
        label = combo.get("label", "?")
        lines.append(f"  Classification: {label} ({'Trending' if trending else 'Contradicting'})")

        if combo.get("asia_ou_break") is not None:
            lines.append(f"  Asia OU Break: {combo['asia_ou_break']}% (mode {combo.get('asia_ou_mode', '?')})")
        if combo.get("london_ou_break") is not None:
            lines.append(f"  London OU Break: {combo['london_ou_break']}% (mode {combo.get('london_ou_mode', '?')})")

        lod_str = "Holds 18:00 LOD" if combo.get("lod_support") else "NO LOD support"
        lines.append(f"  LOD Support: {lod_str}")
        lines.append(f"  NY1: {combo.get('ny1_expectation', '?')}")

    # ── Current hour analysis ──
    ch = data.get("current_hour", {})
    if ch.get("status") == "ok":
        lines.append(f"\nCurrent Hour ({ch.get('hour_label', '?')}):")
        lines.append(f"  O {ch['open']:,.2f} C {ch['close']:,.2f} H {ch['high']:,.2f} L {ch['low']:,.2f} | body {ch['body_pct']:.1f}%")
        lines.append(f"  Classification: {ch['classification']}")
        lines.append(f"  Structure: {ch['structure']} | High in {ch['hour_high_q']} Low in {ch['hour_low_q']}")

        if ch.get("trigger1"):
            lines.append("  [Trigger 1] Q1 swept one side of '05 box then retreated")
        if ch.get("trigger2"):
            lines.append("  [Trigger 2] Q1 took BOTH sides of '05 box (anomaly)")
        if ch.get("instat_type"):
            instat_str = "confirmed" if ch.get("instat_confirmed") else "BROKEN"
            lines.append(f"  Instat {ch['instat_type']}: {instat_str}")
        if ch.get("structure_broken"):
            lines.append("  [Structure Break] Q1 extreme breached → Doji expected")

        # Quarter details
        for q_name in ["Q1", "Q2", "Q3", "Q4"]:
            qd = ch.get("quarters", {}).get(q_name, {})
            if qd.get("high") is not None:
                marker_h = " ←H" if qd["high"] == ch["high"] else ""
                marker_l = " ←L" if qd["low"] == ch["low"] else ""
                lines.append(f"  {q_name}: O {qd['open']:,.2f} C {qd['close']:,.2f} H {qd['high']:,.2f}({qd['high_time']}){marker_h} L {qd['low']:,.2f}({qd['low_time']}){marker_l}")

    # ── Recent completed hours ──
    recent = data.get("recent_hours", [])
    if recent:
        lines.append("\nRecent Hours:")
        for h in recent:
            if h.get("status") == "ok":
                trig = ""
                if h.get("trigger1"): trig += " T1"
                if h.get("trigger2"): trig += " T2"
                lines.append(f"  {h['hour_label']}: {h['classification']:8s} | body {h['body_pct']:.0f}% | H in {h['hour_high_q']} L in {h['hour_low_q']} | {h['structure']}{trig}")

    # ── Historical Q1 stats ──
    qs = data.get("quarter_stats", {})
    if qs:
        lines.append("\nHistorical Q1 Probabilities (20yr):")
        lines.append(f"  {'Hour':5s} | {'Q1 Hi%':>5s} | {'Q1 Lo%':>5s} | {'Q1 Both':>7s} | {'Q1 Neither':>10s} | {'Hi Never Viol':>12s} | {'Lo Never Viol':>12s}")
        for key in ["09", "10", "11", "12", "13", "14", "15", "current"]:
            stats = qs.get(key)
            if stats:
                lines.append(f"  {key:5s} | {stats['q1_high_pct']:4.0f}% | {stats['q1_low_pct']:4.0f}% | {stats['q1_both_pct']:5.0f}% | {stats['q1_neither_pct']:9.0f}% | {stats['q1_high_never_violated_pct']:11.0f}% | {stats['q1_low_never_violated_pct']:11.0f}%")

    return "\n".join(lines)


# ─── Convenience ─────────────────────────────────────────────────────


def build_quarters_block(
    ticker: str = "NQ1",
    df_1m: pd.DataFrame | None = None,
    now_et: datetime | None = None,
    asia_status: str = "",
    london_status: str = "",
) -> str:
    """Compute quarters theory data and return the formatted cheat-sheet block."""
    data = compute_quarters(ticker, df_1m, now_et, asia_status, london_status)
    return format_quarters_block(data)