"""
briefing_core.py
================
Shared library for the Weekly Briefing + Daily EOD Update system.

Provides:
  - resolve_track():           Programmatic Track A/B/C mandate from GEX regime
  - compute_invalidation():    Account invalidation threshold from EM + walls
  - get_dataloader():          DataLoader instance with overridden date range
  - load_macro_levels():       Per-ticker block from data/options/macro_levels.json
  - load_scored_levels():      Filtered scored levels from macro_levels scored_analysis
  - load_weekly_ems():         Mon-Fri EM envelope from macro expected_moves
  - load_weekly_price_context(): Prior week OHLCV + momentum via DataLoader
  - load_daily_price_context():  Today's OHLCV via DataLoader
  - assess_track_alignment():   On-track check for daily updates

All bar calculations use vectorized Pandas (ADR-017 compliant).
All timestamps are ET for display, UTC for storage (ADR-001).
All performance metrics are percentages (ADR-002).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


# Side-effect import: ensures the repo root is on sys.path so
# `from scripts.trader import ...` works without a per-file hack.
# See scripts/trader/_path_setup.py for the full rationale.
from scripts.trader import _path_setup  # noqa: F401

from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.trader.signals.expected_move import get_em_context, format_em_block
from scripts.trader.signals.volatility import get_vix_vvix_checkpoint
from scripts.trader.signals.ict_context import compute_ict_from_htf
from scripts.trader.signals.candle_science import get_candle_science_read, format_candle_science_block
from scripts.trader.signals.confluence import assess_confluence
from scripts.trader.signals.day_type import classify_day_type
from scripts.trader.signals.weekly_profile import compute_weekly_profile
from scripts.trader.signals.liquidity_map import build_liquidity_map
from scripts.trader.signals.gex_regime import get_gex_regime_change, save_today_snapshot
from scripts.trader.data_freshness import check_all

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

def run_async_safely(coro):
    """Run an async coroutine safely, regardless of whether there is an active event loop."""
    import asyncio
    import threading
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
        
    result = []
    exception = []
    
    def target():
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            result.append(new_loop.run_until_complete(coro))
        except Exception as e:
            exception.append(e)
        finally:
            new_loop.close()
            
    t = threading.Thread(target=target)
    t.start()
    t.join()
    
    if exception:
        raise exception[0]
    return result[0]

def get_latest_rth_date(df_t) -> date:
    """Find the latest date in the dataframe that has RTH data (09:30 to 16:00)."""
    from datetime import timedelta, datetime
    if df_t is not None and not df_t.empty:
        rth_bars = df_t.between_time("09:30", "16:00")
        if not rth_bars.empty:
            return rth_bars.index[-1].date()
        last_dt = df_t.index[-1].date()
        while last_dt.weekday() in (5, 6): # Saturday, Sunday
            last_dt -= timedelta(days=1)
        return last_dt
    now_dt = datetime.now(ET).date()
    while now_dt.weekday() in (5, 6):
        now_dt -= timedelta(days=1)
    return now_dt

# ── Paths ──────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
OPTIONS_DATA_DIR = REPO_ROOT / "data" / "options"
LIVE_DIR = REPO_ROOT / "data" / "live"
MACRO_LEVELS_JSON = OPTIONS_DATA_DIR / "macro_levels.json"
UNIFIED_LEVELS_JSON = OPTIONS_DATA_DIR / "unified_levels.json"
UNIFIED_LEVELS_OPEN_TXT = OPTIONS_DATA_DIR / "current" / "unified_levels_open.txt"
UNIFIED_LEVELS_CLOSE_TXT = OPTIONS_DATA_DIR / "current" / "unified_levels_close.txt"
DB_PATH = REPO_ROOT / "web" / "prisma" / "dev.db"
BIAS_GRADES_PATH = OPTIONS_DATA_DIR / "daily" / "bias_grades.jsonl"


# ── Narrative ticker mapping ───────────────────────────────────────
# The options pipeline stores RTD-native futures under short keys (NQ, ES).
# The narrative layer uses user-facing continuous-contract symbols (NQ1, ES1).
# This helper keeps the mapping in one place.
NARRATIVE_TICKER_MAP: dict[str, str | None] = {
    "NQ1": "NQ",
    "ES1": "ES",
}


def resolve_narrative_ticker(ticker: str) -> str:
    """Map a user-facing narrative ticker to the options-pipeline key.

    Examples:
      - "NQ1" -> "NQ"
      - "ES1" -> "ES"
      - "SPY" -> "SPY" (1:1 passthrough)
    """
    resolved = NARRATIVE_TICKER_MAP.get(ticker)
    return resolved if resolved is not None else ticker

# ── Bias Grade Feedback Loop (Phase F) ─────────────────────────────

def write_bias_grade(
    morning_bias: str,
    actual_outcome: str,
    correct: bool,
    pattern: str = "",
    confluence_level: str = "",
) -> None:
    """Append a bias grade record to the JSONL log."""
    BIAS_GRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "date": datetime.now(ET).strftime("%Y-%m-%d"),
        "morning_bias": morning_bias,
        "actual_outcome": actual_outcome,
        "correct": correct,
        "pattern": pattern,
        "confluence_level": confluence_level,
    }
    with open(BIAS_GRADES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    log.info("[bias_grade] Recorded: %s -> %s (correct=%s)", morning_bias, actual_outcome, correct)


def get_recent_bias_accuracy(n: int = 5) -> dict:
    """Read last N bias grades and compute accuracy.

    Returns:
        dict with {recent_grades: list, correct: int, total: int, accuracy_pct: float, summary: str}
    """
    if not BIAS_GRADES_PATH.exists():
        return {"recent_grades": [], "correct": 0, "total": 0, "accuracy_pct": 0.0, "summary": "No prior bias grades available."}

    grades = []
    with open(BIAS_GRADES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    grades.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    recent = grades[-n:] if len(grades) >= n else grades
    correct = sum(1 for g in recent if g.get("correct"))
    total = len(recent)
    pct = round(correct / total * 100, 1) if total > 0 else 0.0

    summary = f"Recent bias accuracy: {correct}/{total} correct ({pct}%)" if total > 0 else "No prior bias grades available."
    return {
        "recent_grades": recent,
        "correct": correct,
        "total": total,
        "accuracy_pct": pct,
        "summary": summary,
    }


def _format_bias_grade_block(grades: dict) -> str:
    """Format recent bias accuracy into cheat-sheet block."""
    if not grades or grades["total"] == 0:
        return ""
    lines = ["== BIAS GRADE FEEDBACK =="]
    lines.append(grades["summary"])
    for g in grades["recent_grades"]:
        mark = "✓" if g.get("correct") else "✗"
        lines.append(f"  {g['date']}: {g['morning_bias']} -> {g['actual_outcome']} {mark}")
    return "\n".join(lines)


# ── Track Mandate Resolution ───────────────────────────────────────
# Hardcoded mapping: (gex_regime, regime_label) → mandated execution track.
# The LLM NEVER chooses the trading style — Python evaluates the GEX regime
# and injects the exact mandate into the JSON payload.

TRACK_MANDATES: dict[tuple[str, str], str] = {
    ("POSITIVE", "PINNED"): (
        "TRACK B: PREMIUM/DISCOUNT FADE "
        "(Breakouts are strictly prohibited. Focus exclusively on fading "
        "EM boundaries toward the Gamma Magnet.)"
    ),
    ("POSITIVE", "BATTLE_ZONE"): (
        "TRACK B: PREMIUM/DISCOUNT FADE "
        "(Range edges are hard. Fade walls toward Magnet. "
        "No breakout trades until GEX flips negative.)"
    ),
    ("NEGATIVE", "COILED"): (
        "TRACK A: BREAKOUT/MOMENTUM "
        "(Compression regime. Prepare for directional expansion. "
        "Trade the breakout of the coil range with momentum confirmation.)"
    ),
    ("NEGATIVE", "TRENDING"): (
        "TRACK A: BREAKOUT/MOMENTUM "
        "(Trend-follow environment. Join established direction on retest. "
        "Trail stops. Do not fade.)"
    ),
    ("POSITIVE", "NEUTRAL"): (
        "TRACK C: OBSERVATION ONLY "
        "(No statistical edge from options positioning. "
        "Stand aside or wait for regime clarification.)"
    ),
    ("NEGATIVE", "NEUTRAL"): (
        "TRACK C: OBSERVATION ONLY "
        "(No statistical edge from options positioning. "
        "Stand aside or wait for regime clarification.)"
    ),
}


def resolve_track(gex_regime: str, regime_label: str) -> str:
    """Programmatically resolve the mandated execution track.

    The LLM never chooses — this function evaluates the GEX regime
    and returns the exact mandate string to inject into the JSON.
    """
    key = (gex_regime.upper(), regime_label.upper())
    return TRACK_MANDATES.get(
        key,
        "TRACK C: OBSERVATION ONLY (Regime unclear — stand aside.)",
    )


# ── Account Invalidation Threshold ───────────────────────────────

def compute_invalidation(
    call_wall: float,
    put_wall: float,
    friday_em_upper: float,
    friday_em_lower: float,
    spot: float,
    ticker: str,
) -> dict[str, Any]:
    """Calculate the account invalidation threshold for prop-firm protection.

    The invalidation is the outermost structural boundary. If price achieves
    a 30-minute close beyond this, the options distribution model is fractured
    and the trader must cease execution on that instrument.

    - Bullish invalidation = min(put_wall, friday_em_lower)  [below both = model broken]
    - Bearish invalidation = max(call_wall, friday_em_upper) [above both = model broken]
    """
    valid_bullish = [v for v in (put_wall, friday_em_lower) if v is not None and pd.notna(v) and float(v) > 0]
    valid_bearish = [v for v in (call_wall, friday_em_upper) if v is not None and pd.notna(v) and float(v) > 0]

    bullish_inv = min(valid_bullish) if valid_bullish else (spot * 0.95 if spot > 0 else 0.0)
    bearish_inv = max(valid_bearish) if valid_bearish else (spot * 1.05 if spot > 0 else 0.0)

    dist_bullish = round(abs(spot - bullish_inv) / spot * 100, 2) if spot > 0 else 0.0
    dist_bearish = round(abs(bearish_inv - spot) / spot * 100, 2) if spot > 0 else 0.0

    mandate = (
        f"Distribution model fractured. Cease all strategy execution on {ticker} "
        f"if price achieves a 30-minute close acceptance beyond "
        f"{bullish_inv:.2f} (bullish break) or {bearish_inv:.2f} (bearish break)."
    )

    return {
        "bullish_invalidation": round(bullish_inv, 2),
        "bearish_invalidation": round(bearish_inv, 2),
        "distance_to_bullish_inv_pct": dist_bullish,
        "distance_to_bearish_inv_pct": dist_bearish,
        "mandate": mandate,
    }


# ── DataLoader Setup (DRY — reuses existing framework) ─────────────

def get_dataloader(lookback_days: int = 45) -> DataLoader:
    """Initialize DataLoader with a safe date range for narrative context.

    Reuses the existing config from sessions.yaml and the existing
    DataLoader from scripts/libs_py/data/loader.py — no new I/O code.

    The configured date_end is kept because it covers historical parquet
    data that may only run through the end of 2025.  date_start is
    computed from lookback_days, but we clamp it to the configured start
    so stale data still loads (otherwise a future today date can request
    bars starting after the parquet ends and produce an empty slice).
    """
    config = load_config("scripts/trading_framework/config/sessions.yaml")
    now = datetime.now(ET)
    requested_start = (now - timedelta(days=lookback_days)).date()
    config_start = pd.Timestamp(config.date_start).date() if config.date_start else date(2000, 1, 1)
    effective_start = min(requested_start, config_start)
    config.date_start = effective_start.strftime("%Y-%m-%d")
    return DataLoader(config)


# ── Pipeline Output Loaders ───────────────────────────────────────

# load_macro_levels is now defined below with session support (live/open/close)


def format_notional(gex_val: float) -> str:
    if gex_val is None: return ""
    b_val = gex_val / 1e9
    m_val = gex_val / 1e6
    if abs(b_val) >= 1.0:
        return f"{b_val:+.1f}B"
    else:
        return f"{m_val:+.1f}M"

def get_color(token_label: str) -> str:
    lbl = token_label.upper()
    if "CW" in lbl or "CALL WALL" in lbl:
        return "Blue extra-thick"
    elif "PW" in lbl or "PUT WALL" in lbl:
        return "Red extra-thick"
    elif "EM HI" in lbl or "EM UPPER" in lbl:
        return "White dashed"
    elif "EM LO" in lbl or "EM LOWER" in lbl:
        return "White dashed"
    elif "FLIP" in lbl:
        return "Green solid"
    elif "MAX" in lbl:
        return "Red extra-thick"
    elif "CLIFF" in lbl:
        return "Orange solid"
    elif "ZERO GEX" in lbl:
        return "Green solid"
    return "Gray thin"

def map_label(token_label: str, strike: float, ticker: str, notional: str) -> str:
    lbl = token_label.upper()
    prefix = ""
    desc = lbl
    
    if "CW" in lbl:
        prefix = "🚨 " if "0D" not in lbl else ""
        desc = "Major Call Wall" if "W" in token_label else "Call Wall"
    elif "PW" in lbl:
        prefix = "🚨🚨 "
        desc = "MASSIVE Put Wall" if "W" in token_label else "Put Wall"
    elif "MAX" in lbl:
        desc = "Max Pain"
    elif "EM HI" in lbl:
        desc = "Expected Move Upper"
    elif "EM LO" in lbl:
        desc = "Expected Move Lower"
    elif "FLIP" in lbl:
        desc = "GEX Flip"
    elif "ZERO GEX DA" in lbl:
        desc = "Zero GEX (Day Ahead)"
    elif "ZERO GEX" in lbl:
        desc = "Zero GEX"
    elif "CLIFF UP" in lbl:
        desc = "Vol Cliff Upper"
    elif "CLIFF DN" in lbl:
        desc = "Vol Cliff Lower"
        
    res = f"{prefix}{desc} ({ticker} {strike})"
    if notional:
        res += f" {notional}"
    return res

def build_levels_markdown_table(ticker: str, session: str = "open") -> str:
    """Build a precise markdown table of option levels mapped to Futures prices.

    Args:
        ticker: pipeline ticker key (e.g. "NQ", "ES", "SPX").
        session: which snapshot to read.
            - "open"      → `current/unified_levels_open.txt`  (09:30 RTH open).
                            Use this for the morning / premarket narratives.
            - "close"     → `current/unified_levels_close.txt` (16:15 RTH close).
                            Use this for the EOD narrative so the review
                            grades the day against the *current* walls/EMs,
                            not the 6h 55min-stale morning snapshot.
            - "intraday"  → `unified_levels.txt` (the live mirror, always
                            overwritten by the most recent pipeline run).
                            Use this for intraday / 12:00 narratives.
            - any other value also maps to "intraday" / live.

    .. note::
        The default `session="open"` preserves the historical behaviour
        of this function. **New callers should pass an explicit session
        value** — hardcoding "open" is exactly the bug fixed in audit
        issue §1.3 (EOD narrative was grading against the morning's
        09:30 walls at 16:25).

        For more structured access (with per-token metadata, parsed
        tokens, etc.) use `load_unified_levels(session=...)` instead.

    .. note::
        If the requested session's snapshot file is missing, the function
        falls back to the live mirror (`unified_levels.txt`) and logs a
        warning. This is intentional — it keeps the narrative flowing
        even if a particular scheduled pipeline run is delayed.
    """
    # Resolve the source file by session.
    if session in ("close", "eod"):
        # EOD and close both want the 16:15 RTH-close snapshot
        # (the daily-narrative EOD mode is just an alias for the
        # RTH-close grading snapshot).
        primary = UNIFIED_LEVELS_CLOSE_TXT
    elif session == "open":
        primary = UNIFIED_LEVELS_OPEN_TXT
    else:
        # "intraday" and any other value → live mirror (most recent run).
        primary = OPTIONS_DATA_DIR / "unified_levels.txt"

    # Resolve with a safe fallback to the live mirror.
    if primary.exists():
        unified_txt_path = primary
    else:
        fallback = OPTIONS_DATA_DIR / "unified_levels.txt"
        if fallback != primary and fallback.exists():
            log.warning(
                "build_levels_markdown_table: session=%s file missing (%s); "
                "falling back to live mirror (%s).",
                session, primary, fallback,
            )
            unified_txt_path = fallback
        else:
            log.warning(
                "build_levels_markdown_table: no snapshot file found for "
                "session=%s (primary=%s, fallback=%s).",
                session, primary, fallback,
            )
            return "No data"

    unified_txt = unified_txt_path.read_text(encoding="utf-8")
    line = next((l for l in unified_txt.splitlines() if l.startswith(f"{ticker}:")), None)
    if not line: return "No data"
    
    line = line.split(":", 1)[1]
    
    meta = {}
    tokens = []
    for part in line.split(", "):
        if ":" in part:
            val, label = part.split(":", 1)
            if val == "0" and label.startswith("META_"):
                key = label[5:]
                if "_" in key and not any(k in key for k in ["NOTE", "EXPIRY", "REGIME", "BIAS", "WALL_SCOPE", "VEL", "TRIG"]):
                    parts = key.rsplit("_", 1)
                    if len(parts) == 2:
                        try:
                            meta[parts[0]] = float(parts[1])
                        except ValueError:
                            meta[parts[0]] = parts[1]
                else:
                    meta[key] = True
            elif val != "0" or not label.startswith("META_"):
                try:
                    strike = float(val)
                    if "|" in label:
                        filter_code, sign, desc = label.split("|", 2)
                        tokens.append({"strike": strike, "filter": filter_code, "sign": sign, "label": desc})
                except ValueError:
                    pass
    
    gex_data = {}
    gex_file = OPTIONS_DATA_DIR / "gex_profiles.json"
    if gex_file.exists():
        try:
            gex_data = json.loads(gex_file.read_text(encoding="utf-8"))
        except Exception:
            pass
            
    profiles = gex_data.get("profiles", {}).get(ticker, [])
    gex_map = {p["strike"]: p for p in profiles}
    
    ratio = meta.get("FUTURES_RATIO", 1.0)
    basis = meta.get("FUTURES_BASIS", 0.0)
    
    futures_symbol = "NQ/MNQ" if ticker == "QQQ" else "ES/MES"
    
    rows = []
    for t in tokens:
        if "EM85" in t["label"] or "LOC" in t["label"] or "DEX" in t["label"] or "HW" in t["label"] or "MAGNET" in t["label"] or "PIN" in t["label"]:
            continue # Skip noise
            
        strike = t["strike"]
        futures_px = strike * ratio + basis
        
        notional_str = ""
        prof = gex_map.get(strike)
        if prof:
            if "CW" in t["label"]:
                notional_str = format_notional(prof["call_gex"])
            elif "PW" in t["label"] or "MAX" in t["label"]:
                notional_str = format_notional(-prof["put_gex"])
        
        color = get_color(t["label"])
        label = map_label(t["label"], strike, ticker, notional_str)
        rows.append((futures_px, color, label))
        
    rows.sort(key=lambda x: x[0], reverse=True)
    
    # Remove exact duplicates (favoring emojis like 🚨)
    seen_strikes = {}
    dedup = []
    for px, color, label in rows:
        key = round(px)
        if key not in seen_strikes:
            seen_strikes[key] = (px, color, label)
            dedup.append((px, color, label))
        else:
            # If we already have it, but the new label has the emoji, swap it
            if "🚨" in label and "🚨" not in seen_strikes[key][2]:
                seen_strikes[key] = (px, color, label)
                dedup = [d if round(d[0]) != key else (px, color, label) for d in dedup]
    
    md = f"**{futures_symbol} Options Levels:**\n\n"
    md += f"| {futures_symbol} Level | Type |\n"
    md += f"|---|---|\n"
    for px, color, label in dedup:
        md += f"| {px:,.2f} | {label} |\n"
        
    return md

# ── EOD Evaluation Logic ────────────────────────────────────────────────
# The options pipeline currently fetches the INDEX chain (SPX for SPY,
# NDX for QQQ) and stores walls/EMs in INDEX scale.
#
# SPX is standalone — walls are already in SPX scale (correct).
# SPY/QQQ/IWM/DIA: the pipeline stores index-scale walls. The correct
# fix is to update the pipeline to fetch the ETF's own options chain
# directly. The briefing uses whatever the pipeline produces as-is.
# No ratio-based translation is applied — that produces approximate
# values, not real ETF chain data.


def load_scored_levels(
    unified_entry: dict,
    max_levels: int = 6,
    min_significance: str = "SECONDARY",
) -> list[dict]:
    """Extract filtered scored levels from unified_entry.tokens.

    The unified_levels.json has a `tokens` array with parsed levels,
    each having: strike, filter, significance, label, raw.
    Filters by significance (PRIMARY > SECONDARY > CONTEXT) and returns
    the top N levels sorted by significance rank.
    """
    significance_ranks = {"P": 0, "S": 1, "C": 2}  # unified uses P/S/C
    min_rank = significance_ranks.get(min_significance[0] if min_significance else "C", 2)

    tokens = unified_entry.get("tokens", [])

    filtered = [
        {
            "strike": t.get("strike", 0),
            "label": t.get("label", ""),
            "significance": t.get("significance", ""),
            "filter": t.get("filter", ""),
            "raw": t.get("raw", ""),
        }
        for t in tokens
        if significance_ranks.get(t.get("significance", ""), 3) <= min_rank
    ]

    # Sort by significance rank
    filtered.sort(key=lambda x: (significance_ranks.get(x["significance"], 3),))
    return filtered[:max_levels]


def parse_meta_fields(unified_entry: dict) -> dict:
    """Parse META_ fields from the unified_entry.line string.

    The unified_levels.json line format includes META_ fields like:
    0:META_REGIME_TRENDING, 0:META_GEX_TOTAL_-191251078.14, etc.

    Returns a dict of parsed META values.
    """
    line = unified_entry.get("line", "")
    meta = {}

    # Known META key prefixes (sorted by length descending to match longest first)
    # This prevents GEX from matching before GEX_TOTAL, HFLOW before HFLOW_UP10, etc.
    known_keys = [
        "REGIME", "BIAS", "VANNA", "CHARM", "SPEED",
        "HFLOW_UP10", "HFLOW_DN10", "HFLOW_UP25", "HFLOW_DN25",
        "HFLOW_UP50", "HFLOW_DN50",
        "GEX_DA", "GEX_TOTAL",
        "STABILITY", "CONCENTRATION", "INTEGRITY",
        "WALL_SCOPE", "WALL_DTE_MIN", "WALL_DTE_MAX",
        "OI_CALLWALL", "OI_PUTWALL", "OI_PIN",
        "OI_VEL_CW_STATUS", "OI_VEL_PW_STATUS", "OI_VEL_PIN_STATUS",
        "OI_VEL_CW_RATE", "OI_VEL_PW_RATE", "OI_VEL_PIN_RATE",
        "IV", "IVCHG", "SKEW",
        "FUTURES_RATIO", "FUTURES_BASIS",
        "VOL_EXPANSION_UP", "VOL_EXPANSION_DN",
        "S_TRIG", "L_TRIG", "S_TGT", "L_TGT", "S_INV", "L_INV",
        "NOTE",
    ]
    # Sort by length descending for longest-match-first
    known_keys.sort(key=len, reverse=True)

    for part in line.split(", "):
        if part.startswith("0:META_"):
            meta_part = part[7:]  # strip "0:META_"
            # Try to match against known keys
            matched = False
            for key in known_keys:
                prefix = key + "_"
                if meta_part.startswith(prefix):
                    val_str = meta_part[len(prefix):]
                    try:
                        meta[key] = float(val_str)
                    except ValueError:
                        meta[key] = val_str
                    matched = True
                    break
            if not matched:
                # Fallback: the field name is not in the allow-list,
                # but the unified_levels loader is forward-compatible —
                # new META fields can appear before the Python list is
                # updated. We still want to capture them, but only if
                # the key is well-formed: uppercase letters / digits
                # only, must START with a letter, no special chars.
                # This is a strict-format spec (audit §2.10) — the old
                # `rfind("_")` split silently mis-parsed values that
                # contain underscores (e.g. `NOTE: "12-31 expiry"`
                # became key=`NOTE: "12-31`, value=`expiry"`).
                m = re.match(r"^([A-Z][A-Z0-9]*)_(.+)$", meta_part)
                if m:
                    key, val_str = m.group(1), m.group(2)
                    try:
                        meta[key] = float(val_str)
                    except ValueError:
                        meta[key] = val_str
                # else: silently skip — a malformed field is better
                # than a mis-aligned one. The LLM downstream does not
                # depend on every META field being present; it checks
                # `meta.get("FOO")` and tolerates missing keys.

    return meta


def translate_level_to_futures(ticker: str, level: float, meta: dict) -> float:
    """Translate proxy strike levels into futures scale when mapping is available.

    For SPY/QQQ-derived levels, apply FUTURES_RATIO/FUTURES_BASIS from META fields:
      futures_px = strike * ratio + basis
    If mapping is missing or not applicable, return the original level.
    """
    if level in (None, 0):
        return 0.0

    if ticker not in {"SPY", "QQQ"}:
        return round(float(level), 2)

    ratio = meta.get("FUTURES_RATIO", 0)
    basis = meta.get("FUTURES_BASIS", 0)
    if ratio and ratio > 0:
        return round(float(level) * float(ratio) + float(basis), 2)

    return round(float(level), 2)


def load_unified_levels_txt(txt_path: Path) -> dict[str, dict]:
    """Parse a unified_levels_*.txt file into a dict keyed by ticker.

    The TXT format is one line per ticker:
    TICKER:strike:filter|sig|label, strike:filter|sig|label, ..., 0:META_KEY_VALUE, ...

    Returns a dict with the same structure as unified_levels.json entries:
    {"ticker": str, "line": str, "tokens": [...], ...}
    """
    if not txt_path.exists():
        log.warning("File not found: %s", txt_path)
        return {}

    result = {}
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Split ticker from the rest
            colon_idx = line.find(":")
            if colon_idx < 0:
                continue
            ticker = line[:colon_idx]
            rest = line[colon_idx + 1:]

            # Parse tokens (comma-separated, format: strike:filter|sig|label)
            tokens = []
            meta_parts = []
            for part in rest.split(", "):
                if part.startswith("0:META_"):
                    meta_parts.append(part)
                    continue

                # Parse token: strike:filter|sig|label
                parts = part.split(":", 1)
                if len(parts) == 2:
                    try:
                        strike = float(parts[0])
                    except ValueError:
                        continue
                    filter_sig_label = parts[1].split("|")
                    filter_type = filter_sig_label[0] if len(filter_sig_label) > 0 else ""
                    significance = filter_sig_label[1] if len(filter_sig_label) > 1 else ""
                    label = filter_sig_label[2] if len(filter_sig_label) > 2 else ""
                    tokens.append({
                        "strike": strike,
                        "filter": filter_type,
                        "significance": significance,
                        "label": label,
                        "raw": part,
                    })

            # Reconstruct the full line with META_ fields for parse_meta_fields
            full_line = ticker + ":" + rest

            result[ticker] = {
                "ticker": ticker,
                "line": full_line,
                "tokens": tokens,
            }

    return result


def load_weekly_macro_sentiment(target_date: date | None = None) -> dict | None:
    """Load the weekly macro sentiment config for the given date's ISO week.

    Reads ``scripts/config/weekly_macro_sentiment.yaml`` and returns the week's
    config dict, or ``None`` if the file is missing or the week key doesn't match.

    The week key format is ISO: ``YYYY-Www`` (e.g. ``2026-W30``).
    """
    import yaml
    from datetime import date as _date

    if target_date is None:
        target_date = _date.today()

    config_path = REPO_ROOT / "scripts" / "config" / "weekly_macro_sentiment.yaml"
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        log.warning("[macro_sentiment] Failed to load %s: %s", config_path, e)
        return None

    if not data or not isinstance(data, dict):
        return None

    # ISO week key: YYYY-Www
    iso_year, iso_week, _ = target_date.isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"

    week_config = data.get(week_key)
    if not week_config:
        return None

    return week_config


def format_macro_sentiment_block(sentiment: dict) -> str:
    """Format the weekly macro sentiment config into a cheat-sheet block."""
    if not sentiment:
        return ""

    lines: list[str] = ["== WEEKLY MACRO SENTIMENT =="]

    theme = sentiment.get("macro_theme", "")
    if theme:
        lines.append(f"Theme: {theme}")

    event_sentiment = sentiment.get("event_sentiment", {})
    if event_sentiment:
        lines.append("Event Sentiment:")
        for event_name, details in event_sentiment.items():
            if not isinstance(details, dict):
                continue
            time_str = details.get("time", "")
            consensus = details.get("consensus", "")
            cooler = details.get("cooler_than", "")
            hotter = details.get("hotter_than", "")
            note = details.get("note", "")

            parts = [f"  {event_name}"]
            if time_str:
                parts.append(f"({time_str})")
            if consensus:
                parts.append(f"Consensus: {consensus}")
            lines.append(" ".join(parts))
            if cooler:
                lines.append(f"    Cooler: {cooler}")
            if hotter:
                lines.append(f"    Hotter: {hotter}")
            if note:
                lines.append(f"    Note: {note}")

    jh = sentiment.get("jackson_hole", {})
    if isinstance(jh, dict) and jh.get("note"):
        lines.append(f"Jackson Hole: {jh['note']}")

    auctions = sentiment.get("treasury_auctions", [])
    if auctions:
        lines.append("Treasury Auctions:")
        for a in auctions:
            if not isinstance(a, dict):
                continue
            day = a.get("day", "?")
            time_str = a.get("time", "")
            note = a.get("note", "")
            lines.append(f"  {day} {time_str}: {note}")

    themes = sentiment.get("intermarket_themes", [])
    if themes:
        lines.append("Intermarket Themes:")
        for t in themes:
            lines.append(f"  - {t}")

    return "\n".join(lines) if len(lines) > 1 else ""


def load_macro_levels(session: str = "live") -> dict[str, dict]:
    """Load unified levels data and return a dict keyed by ticker.

    Session options:
    - "live": reads unified_levels.json (latest pipeline output)
    - "open": reads unified_levels_open.txt (RTH open snapshot)
    - "close": reads unified_levels_close.txt (RTH close snapshot)

    Returns:
        {"SPX": {ticker, line, tokens, ...}, "QQQ": {...}, ...}
    """
    if session == "open":
        return load_unified_levels_txt(UNIFIED_LEVELS_OPEN_TXT)
    elif session == "close":
        return load_unified_levels_txt(UNIFIED_LEVELS_CLOSE_TXT)
    else:
        # Default: live JSON
        if not UNIFIED_LEVELS_JSON.exists():
            raise FileNotFoundError(f"unified_levels.json not found at {UNIFIED_LEVELS_JSON}")
        with open(UNIFIED_LEVELS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for entry in data.get("tickers", []):
            ticker = entry.get("ticker", "")
            if ticker:
                result[ticker] = entry
        return result


def compute_weekly_ems(unified_entry: dict, spot: float) -> dict:
    """Compute per-day EM envelope from the weekly EM tokens.

    The unified_levels.json has EM HI and EM LO tokens for the front-week
    expiry (e.g., 'EM HI 2d', 'EM LO 2d'). These represent the weekly close
    EM envelope, which stays relevant through the week.

    We compute a per-day progression using sqrt(time) scaling:
    EM_day = EM_weekly * sqrt(DTE_day / DTE_weekly)

    **0DTE fallback**: When the only EM tokens available are 0DTE (label "0d"),
    the RTD chain for NQ/ES doesn't have the weekly expiry. In this case we
    compute the forward Friday EM via the TOS formula (calculate_tos_expected_move)
    using the ATM IV from META_ fields and the next Friday's DTE.

    Returns:
        {"monday": {"upper": x, "lower": y, "em": z}, ...}
    """
    tokens = unified_entry.get("tokens", [])

    # Find EM HI and EM LO tokens (exclude EM85)
    em_hi_token = next((t for t in tokens if "EM HI" in t.get("label", "")), None)
    em_lo_token = next((t for t in tokens if "EM LO" in t.get("label", "") and "EM85" not in t.get("label", "")), None)

    if not em_hi_token or not em_lo_token or spot <= 0:
        return {}

    em_hi = em_hi_token.get("strike", 0)
    em_lo = em_lo_token.get("strike", 0)

    # The weekly EM value is half the envelope width
    weekly_em = (em_hi - em_lo) / 2
    if weekly_em <= 0:
        return {}

    # Extract DTE from the label (e.g., "EM HI 2d" → DTE=2)
    import re
    dte_match = re.search(r"(\d+)d", em_hi_token.get("label", ""))
    weekly_dte = int(dte_match.group(1)) if dte_match else 2
    if weekly_dte <= 0:
        weekly_dte = 1

    # ── 0DTE fallback: compute forward Friday EM via TOS formula ──
    # When the only EM token is 0DTE (DTE=0), the RTD chain doesn't have the
    # weekly expiry. We compute the forward Friday (next Friday, DTE 3-7)
    # EM using the TOS formula with the ATM IV from META_ fields.
    if weekly_dte <= 1:
        tos_weekly_em = _compute_tos_weekly_em_from_meta(unified_entry, spot)
        if tos_weekly_em and tos_weekly_em > 0:
            weekly_em = tos_weekly_em
            # Use DTE=5 as the Friday target for the √(time) progression
            weekly_dte = 5
            log.debug(
                "[weekly_em] 0DTE fallback: using TOS formula EM=%.2f (DTE=5) for %s",
                tos_weekly_em, unified_entry.get("ticker", "?"),
            )
        else:
            # TOS formula failed — fall back to the 0DTE value but note it's
            # an approximation (0DTE scaled by √5 to Friday)
            weekly_dte = 5
            log.warning(
                "[weekly_em] 0DTE fallback failed for %s — using 0DTE EM scaled to Friday (approximation)",
                unified_entry.get("ticker", "?"),
            )

    # Compute per-day EM using sqrt(time) scaling
    # Monday = DTE 1, Tuesday = DTE 2, ..., Friday = DTE 5
    # (assuming the weekly EM is for DTE 2 = front week)
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    result = {}

    for i, day in enumerate(day_names):
        day_dte = i + 1  # 1 through 5
        # Scale EM by sqrt(day_dte / weekly_dte)
        day_em = weekly_em * (day_dte / weekly_dte) ** 0.5
        day_upper = spot + day_em
        day_lower = spot - day_em
        result[day] = {
            "upper": round(day_upper, 2),
            "lower": round(day_lower, 2),
            "em": round(day_em, 2),
        }

    return result


def _compute_tos_weekly_em_from_meta(unified_entry: dict, spot: float) -> float | None:
    """Compute the forward Friday EM using the TOS formula.

    Uses the ATM IV from the META_ fields (parsed from the unified_levels line)
    and the next Friday's DTE to compute the expected move for the weekly expiry.

    This is the consumer-side counterpart of the producer-side
    ``_compute_tos_em_fallback()`` in run_options_levels.py — it handles the
    case where the RTD chain only has 0DTE + monthly expiries and the weekly
    expiry is missing.

    Returns the EM value (±points) or None if inputs are invalid.
    """
    import math
    from datetime import date, timedelta
    from zoneinfo import ZoneInfo

    # Get ATM IV from META_ fields
    meta = parse_meta_fields(unified_entry)
    atm_iv = meta.get("IV", 0) or 0
    if atm_iv <= 0:
        # Try blending 25d IVs if available
        # (not in META_ but may be in the unified entry)
        return None

    # Determine if this is a futures ticker (uses futures TOS intercept)
    ticker = unified_entry.get("ticker", "")
    is_futures = ticker in ("NQ", "ES", "YM", "RTY", "/NQ", "/ES", "/YM", "/RTY")

    # Compute next Friday DTE
    tz = ZoneInfo("America/New_York")
    from datetime import datetime
    today = datetime.now(tz).date()
    days_ahead = 4 - today.weekday()  # 4 = Friday
    if days_ahead <= 0:
        days_ahead += 7
    next_friday = today + timedelta(days=days_ahead)
    dte = (next_friday - today).days
    if dte < 3:
        return None

    # TOS formula: EM = Price * IV * sqrt((0.6368 * DTE + intercept) / 365)
    slope = 0.6368
    intercept = 0.6900 if is_futures else 0.2400
    t_eff = slope * dte + intercept
    t_eff_yr = t_eff / 365.0
    if t_eff_yr <= 0:
        return None

    em_value = spot * atm_iv * math.sqrt(t_eff_yr)
    return em_value if em_value > 0 else None


def load_weekly_ems(unified_entry: dict, spot: float) -> dict:
    """Backward-compatible alias for weekly EM envelope computation."""
    return compute_weekly_ems(unified_entry, spot)


# ── Weekly Macro Context (multi-week GEX regime) ──────────────────


def _query_daily_gex_snapshots(ticker: str, lookback_days: int = 28) -> list[dict]:
    """Query daily GEX snapshots from Prisma DB for multi-week regime analysis.

    Returns one row per trading day with the EOD (last snapshot) GEX values:
    [{date, regime, regime_label, total_gex, spot, gamma_magnet}, ...]
    """
    import sqlite3
    from datetime import datetime, timezone

    # Map narrative tickers to GexSnapshot ticker keys
    ticker_map = {
        "NQ": "/NQ", "NQ1": "/NQ", "/NQ": "/NQ",
        "ES": "/ES", "ES1": "/ES", "/ES": "/ES",
        "QQQ": "QQQ", "SPY": "SPY", "SPX": "SPX",
        "NDX": "NDX", "IWM": "IWM", "DIA": "DIA",
    }
    db_ticker = ticker_map.get(ticker, ticker)

    if not DB_PATH.exists():
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Get the last snapshot per trading day for the lookback period
        cursor.execute(
            """
            SELECT 
                date(tradingDate / 1000, 'unixepoch') as dt,
                gexRegime,
                regimeLabel,
                totalGex,
                spotPrice,
                gammaMagnet,
                callVolumeCentroid,
                putVolumeCentroid
            FROM GexSnapshot
            WHERE ticker = ?
              AND tradingDate >= strftime('%s', 'now', ?) * 1000
            GROUP BY dt
            ORDER BY dt DESC
            """,
            (db_ticker, f"-{lookback_days} days"),
        )
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            result.append({
                "date": r[0],
                "regime": r[1] or "NEUTRAL",
                "regime_label": r[2] or "NEUTRAL",
                "total_gex": r[3] or 0,
                "spot": r[4] or 0,
                "gamma_magnet": r[5] or 0,
                "call_centroid": r[6] or 0,
                "put_centroid": r[7] or 0,
            })
        return result
    except Exception as exc:
        log.warning("[weekly_macro] GexSnapshot query failed for %s: %s", ticker, exc)
        return []


def _query_macro_snapshots(ticker: str, lookback_days: int = 28) -> list[dict]:
    """Query daily wall data for wall migration analysis.

    Tries MacroSnapshot first (has explicit call/put walls). If no recent data,
    falls back to GexSnapshot (has gammaMagnet and pinStrike as wall proxies).

    Returns: [{date, call_wall, put_wall, zero_gamma, gamma_magnet, pin_strike, spot}, ...]
    """
    import sqlite3
    import time

    ticker_map = {
        "NQ": "NDX", "NQ1": "NDX", "/NQ": "NDX",
        "ES": "SPX", "ES1": "SPX", "/ES": "SPX",
        "QQQ": "QQQ", "SPY": "SPY", "SPX": "SPX",
        "NDX": "NDX", "IWM": "IWM", "DIA": "DIA",
    }
    db_ticker = ticker_map.get(ticker, ticker)

    # GexSnapshot ticker (futures-native)
    gex_ticker_map = {
        "NQ": "/NQ", "NQ1": "/NQ", "/NQ": "/NQ",
        "ES": "/ES", "ES1": "/ES", "/ES": "/ES",
        "QQQ": "QQQ", "SPY": "SPY", "SPX": "SPX",
        "NDX": "NDX", "IWM": "IWM", "DIA": "DIA",
    }
    gex_ticker = gex_ticker_map.get(ticker, ticker)

    if not DB_PATH.exists():
        return []

    threshold_ms = (int(time.time()) - (lookback_days + 7) * 86400) * 1000

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 1. Try MacroSnapshot (explicit walls)
        cursor.execute(
            """
            SELECT
                date(tradingDate / 1000, 'unixepoch') as dt,
                macroCallWall,
                macroPutWall,
                zeroGamma,
                spotPrice
            FROM MacroSnapshot
            WHERE ticker = ?
              AND tradingDate >= ?
            ORDER BY tradingDate DESC
            """,
            (db_ticker, threshold_ms),
        )
        rows = cursor.fetchall()

        if rows and len(rows) >= 2:
            conn.close()
            return [
                {
                    "date": r[0],
                    "call_wall": r[1] or 0,
                    "put_wall": r[2] or 0,
                    "zero_gamma": r[3] or 0,
                    "gamma_magnet": 0,
                    "pin_strike": 0,
                    "spot": r[4] or 0,
                }
                for r in rows
            ]

        # 2. Fallback: GexSnapshot (gammaMagnet + pinStrike as wall proxies)
        cursor.execute(
            """
            SELECT
                date(tradingDate / 1000, 'unixepoch') as dt,
                gammaMagnet,
                pinStrike,
                spotPrice
            FROM GexSnapshot
            WHERE ticker = ?
              AND tradingDate >= ?
            GROUP BY dt
            ORDER BY dt DESC
            """,
            (gex_ticker, threshold_ms),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "date": r[0],
                "call_wall": 0,  # GexSnapshot doesn't have explicit walls
                "put_wall": 0,
                "zero_gamma": 0,
                "gamma_magnet": r[1] or 0,
                "pin_strike": r[2] or 0,
                "spot": r[3] or 0,
            }
            for r in rows
        ]
    except Exception as exc:
        log.warning("[weekly_macro] MacroSnapshot/GexSnapshot wall query failed for %s: %s", ticker, exc)
        return []


def build_weekly_macro_context(ticker: str) -> dict:
    """Build a multi-week macro GEX context for the weekly narrative.

    Pulls 4 weeks of GexSnapshot and MacroSnapshot data from Prisma to answer:
    - Is this a 1-day flip or a multi-week regime? (regime persistence)
    - Are the walls drifting? (wall migration)
    - Is total GEX trending? (rising/falling)
    - How stable is the regime? (regime stability score)

    Returns:
        {regime_persistence_pct, current_regime, regime_days, gex_trend,
         wall_migration, regime_stability, summary_str}
    """
    gex_snaps = _query_daily_gex_snapshots(ticker, lookback_days=28)
    macro_snaps = _query_macro_snapshots(ticker, lookback_days=28)

    if not gex_snaps:
        return {"summary_str": "No historical GEX data available for macro context."}

    # ── Regime persistence: what % of days in the lookback were NEGATIVE vs POSITIVE ──
    total_days = len(gex_snaps)
    neg_days = sum(1 for s in gex_snaps if s["regime"] == "NEGATIVE")
    pos_days = sum(1 for s in gex_snaps if s["regime"] == "POSITIVE")
    neg_pct = (neg_days / total_days * 100) if total_days else 0
    pos_pct = (pos_days / total_days * 100) if total_days else 0

    # Current regime (most recent day)
    current = gex_snaps[0]
    current_regime = current["regime"]
    current_label = current["regime_label"]

    # Count consecutive days in current regime
    regime_days = 0
    for s in gex_snaps:
        if s["regime"] == current_regime:
            regime_days += 1
        else:
            break

    # ── GEX trend: compare recent avg to prior avg ──
    recent_5 = gex_snaps[:5] if len(gex_snaps) >= 5 else gex_snaps
    prior_5 = gex_snaps[5:10] if len(gex_snaps) >= 10 else gex_snaps[5:]
    recent_avg_gex = sum(s["total_gex"] for s in recent_5) / len(recent_5) if recent_5 else 0
    prior_avg_gex = sum(s["total_gex"] for s in prior_5) / len(prior_5) if prior_5 else 0

    if prior_avg_gex != 0:
        gex_change_pct = ((recent_avg_gex - prior_avg_gex) / abs(prior_avg_gex)) * 100
    else:
        gex_change_pct = 0

    if recent_avg_gex < prior_avg_gex:
        gex_trend = "FALLING (more negative — vol expanding)"
    elif recent_avg_gex > prior_avg_gex:
        gex_trend = "RISING (less negative — vol compressing)"
    else:
        gex_trend = "STABLE"

    # ── Wall migration: compare latest walls/magnet to earliest in lookback ──
    wall_migration = {}
    if macro_snaps and len(macro_snaps) >= 2:
        latest = macro_snaps[0]
        earliest = macro_snaps[-1]
        has_explicit_walls = latest.get("call_wall", 0) and earliest.get("call_wall", 0)

        if has_explicit_walls:
            cw_delta = latest["call_wall"] - earliest["call_wall"]
            pw_delta = latest["put_wall"] - earliest["put_wall"]
            zg_delta = latest.get("zero_gamma", 0) - earliest.get("zero_gamma", 0)
            wall_migration = {
                "call_wall_delta": round(cw_delta, 2),
                "put_wall_delta": round(pw_delta, 2),
                "zero_gamma_delta": round(zg_delta, 2),
                "call_wall_latest": latest["call_wall"],
                "put_wall_latest": latest["put_wall"],
                "call_wall_earliest": earliest["call_wall"],
                "put_wall_earliest": earliest["put_wall"],
                "source": "MacroSnapshot",
            }
        else:
            # Fallback: use gamma magnet + pin strike as wall proxies
            magnet_delta = (latest.get("gamma_magnet", 0) - earliest.get("gamma_magnet", 0)) if latest.get("gamma_magnet") and earliest.get("gamma_magnet") else 0
            pin_delta = (latest.get("pin_strike", 0) - earliest.get("pin_strike", 0)) if latest.get("pin_strike") and earliest.get("pin_strike") else 0
            wall_migration = {
                "gamma_magnet_delta": round(magnet_delta, 2),
                "pin_strike_delta": round(pin_delta, 2),
                "gamma_magnet_latest": latest.get("gamma_magnet", 0),
                "pin_strike_latest": latest.get("pin_strike", 0),
                "gamma_magnet_earliest": earliest.get("gamma_magnet", 0),
                "pin_strike_earliest": earliest.get("pin_strike", 0),
                "source": "GexSnapshot (magnet/pin proxy)",
            }

    # ── Regime stability: how many regime flips in the lookback? ──
    flips = 0
    for i in range(1, len(gex_snaps)):
        if gex_snaps[i]["regime"] != gex_snaps[i - 1]["regime"]:
            flips += 1
    # Stability: 0 flips = 100% stable, many flips = low stability
    if total_days > 1:
        stability_pct = max(0, 100 - (flips / (total_days - 1) * 100))
    else:
        stability_pct = 100

    # ── Build summary string ──
    regime_desc = "NEGATIVE GAMMA" if current_regime == "NEGATIVE" else "POSITIVE GAMMA" if current_regime == "POSITIVE" else "NEUTRAL"
    persistence_desc = f"{neg_pct:.0f}% negative / {pos_pct:.0f}% positive over {total_days} trading days"
    stability_desc = f"{stability_pct:.0f}% stable ({flips} regime flips in {total_days} days)"

    summary_parts = [
        f"GEX REGIME: {regime_desc} ({current_label}) — {regime_days} consecutive days",
        f"REGIME PERSISTENCE: {persistence_desc}",
        f"GEX TREND: {gex_trend} (recent avg GEX: {recent_avg_gex:,.0f} vs prior: {prior_avg_gex:,.0f}, {gex_change_pct:+.1f}%)",
        f"REGIME STABILITY: {stability_desc}",
    ]
    if wall_migration:
        if wall_migration.get("source") == "MacroSnapshot":
            cw_dir = "up" if wall_migration["call_wall_delta"] > 0 else "down" if wall_migration["call_wall_delta"] < 0 else "flat"
            pw_dir = "up" if wall_migration["put_wall_delta"] > 0 else "down" if wall_migration["put_wall_delta"] < 0 else "flat"
            summary_parts.append(
                f"WALL MIGRATION: Call Wall {wall_migration['call_wall_delta']:+.2f} ({cw_dir}), "
                f"Put Wall {wall_migration['put_wall_delta']:+.2f} ({pw_dir}) over {len(macro_snaps)} days"
            )
        else:
            # GexSnapshot fallback: magnet/pin
            mag_dir = "up" if wall_migration["gamma_magnet_delta"] > 0 else "down" if wall_migration["gamma_magnet_delta"] < 0 else "flat"
            pin_dir = "up" if wall_migration["pin_strike_delta"] > 0 else "down" if wall_migration["pin_strike_delta"] < 0 else "flat"
            summary_parts.append(
                f"GAMMA MIGRATION: Magnet {wall_migration['gamma_magnet_delta']:+.2f} ({mag_dir}), "
                f"Pin {wall_migration['pin_strike_delta']:+.2f} ({pin_dir}) over {len(macro_snaps)} days"
            )

    return {
        "current_regime": current_regime,
        "current_label": current_label,
        "regime_days": regime_days,
        "regime_persistence_neg_pct": round(neg_pct, 1),
        "regime_persistence_pos_pct": round(pos_pct, 1),
        "total_days_sampled": total_days,
        "gex_trend": gex_trend,
        "recent_avg_gex": round(recent_avg_gex, 2),
        "prior_avg_gex": round(prior_avg_gex, 2),
        "gex_change_pct": round(gex_change_pct, 1),
        "regime_stability_pct": round(stability_pct, 1),
        "regime_flips": flips,
        "wall_migration": wall_migration,
        "summary_str": " | ".join(summary_parts),
    }


def format_weekly_macro_context_block(macro_ctx: dict) -> str:
    """Format the weekly macro context into a cheat-sheet block."""
    if not macro_ctx or "summary_str" not in macro_ctx:
        return "== WEEKLY MACRO CONTEXT ==\nNo historical GEX data available."

    lines = ["== WEEKLY MACRO CONTEXT (multi-week GEX regime) =="]
    for part in macro_ctx["summary_str"].split(" | "):
        lines.append(f"• {part}")
    return "\n".join(lines)


def get_friday_em(weekly_ems: dict) -> tuple[float, float]:
    """Extract Friday EM upper/lower from the weekly EMs dict.

    Falls back to the last available day if Friday is missing.
    """
    day_order = ["friday", "thursday", "wednesday", "tuesday", "monday"]
    for day in day_order:
        if day in weekly_ems:
            em = weekly_ems[day]
            return em["upper"], em["lower"]
    return 0.0, 0.0


# ── Price Context (vectorized, via DataLoader) ────────────────────

def _resolve_parquet_symbol(ticker: str) -> str:
    """Map narrative tickers to parquet file prefixes.

    Cash/ETF tickers map 1:1.  Continuous-contract futures (NQ1, ES1) map
    to their short parquet prefix.  Options-pipeline keys (NQ, ES) also
    map to the same parquet prefixes.
    """
    direct_map = {
        "SPX": "SPX",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
        "DIA": "DIA",
        "AAPL": "AAPL",
        "MSFT": "MSFT",
        "NVDA": "NVDA",
        "TSLA": "TSLA",
        "META": "META",
        "GOOGL": "GOOGL",
        "AMZN": "AMZN",
        "AVGO": "AVGO",
        "NQ": "NQ1",
        "ES": "ES1",
        "NQ1": "NQ1",
        "ES1": "ES1",
    }
    return direct_map.get(ticker, ticker)


def load_weekly_price_context(loader: DataLoader, ticker: str) -> dict:
    """Load HTF price context from live storage parquet.

    The live storage parquet (``data/live/live_storage_-{ticker}.parquet``)
    contains ~1 year of 1m bars ending at the current bar — sufficient for
    weekly resampling. The historical parquet (``data/{ticker}_1m.parquet``)
    covers 2006-2024 but is not needed for the weekly briefing.

    Uses vectorized Pandas resampling (ADR-017: no loops).

    Returns prior week OHLCV + momentum metrics.
    """
    parquet_sym = _resolve_parquet_symbol(ticker)

    # Map parquet symbol to live storage filename
    # ES1 -> -ES, NQ1 -> -NQ, SPY -> SPY, etc.
    _live_map = {"ES1": "-ES", "NQ1": "-NQ", "RTY1": "-RTY", "YM1": "-YM"}
    live_ticker = _live_map.get(parquet_sym, parquet_sym)
    live_path = LIVE_DIR / f"live_storage_{live_ticker}.parquet"

    try:
        df_1m = pd.read_parquet(live_path)
        if df_1m.empty:
            raise ValueError("empty parquet")
        # Convert epoch ms to datetime index
        df_1m["datetime"] = pd.to_datetime(df_1m["time"], unit="ms")
        df_1m = df_1m.set_index("datetime")
    except Exception as e:
        log.warning("Could not load live storage for %s (%s): %s — trying fused", ticker, live_path.name, e)
        # Fallback to fused data loader (live + historical)
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            df_1m = load_fused_data(parquet_sym, timeframe="1m", require_historical=False)
        except Exception as e2:
            log.warning("Fused fallback also failed for %s: %s", parquet_sym, e2)
            return {}

    if df_1m.empty:
        return {}

    # Vectorized resampling (ADR-017: no loops in calculation paths)
    # W-FRI = weeks ending Friday (standard for futures)
    weekly = df_1m.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    daily = df_1m.resample("B").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    if weekly.empty or daily.empty:
        return {}

    # Prior week (last completed week)
    prior_week = weekly.iloc[-1]
    prior_week_change_pct = round((prior_week.close / prior_week.open - 1) * 100, 2)
    prior_week_range_pct = round((prior_week.high - prior_week.low) / prior_week.open * 100, 2)

    # Momentum (vectorized pct_change)
    last_5d = round(daily["close"].pct_change(5).iloc[-1] * 100, 2) if len(daily) >= 6 else 0.0
    last_10d = round(daily["close"].pct_change(10).iloc[-1] * 100, 2) if len(daily) >= 11 else 0.0

    # Trend classification via MA stack (vectorized rolling)
    ma_5 = daily["close"].rolling(5).mean().iloc[-1] if len(daily) >= 5 else prior_week.close
    ma_10 = daily["close"].rolling(10).mean().iloc[-1] if len(daily) >= 10 else prior_week.close
    ma_20 = daily["close"].rolling(20).mean().iloc[-1] if len(daily) >= 20 else prior_week.close

    if ma_5 > ma_10 > ma_20:
        trend = "uptrend"
    elif ma_5 < ma_10 < ma_20:
        trend = "downtrend"
    else:
        trend = "choppy"

    return {
        "prior_week": {
            "open": round(float(prior_week.open), 2),
            "high": round(float(prior_week.high), 2),
            "low": round(float(prior_week.low), 2),
            "close": round(float(prior_week.close), 2),
            "change_pct": prior_week_change_pct,
            "range_pct": prior_week_range_pct,
            "body": "bullish" if prior_week.close > prior_week.open else "bearish",
        },
        "recent_momentum": {
            "last_5d_change_pct": last_5d,
            "last_10d_change_pct": last_10d,
            "trend": trend,
        },
    }


def _rth_filter_1m_to_daily(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Filter 1m bars to RTH (09:30-16:00 ET) and resample to daily.

    The audit (§2.7) flagged that resampling the full 1m feed to a
    daily bar takes the LAST 1m bar of the file — which may be a
    20:00 Globex print, not the 16:00 settlement. Filtering to RTH
    first means the resampled bar's `close` is always the
    settlement print.

    Assumes the index is a US/Eastern DatetimeIndex (the loader
    produces this via the time-column-to-datetime-index pipeline).
    If the index is anything else, the filter is a no-op and the
    caller falls back to the daily parquet.
    """
    import pandas as pd
    if not isinstance(df_1m.index, pd.DatetimeIndex):
        return pd.DataFrame()
    # `between_time` is inclusive on both ends by default. 16:00
    # is the settlement print (the 16:00-16:01 bar's OPEN is the
    # settlement; including it is correct).
    rth = df_1m.between_time("09:30", "16:00")
    if rth.empty:
        return rth
    return rth.resample("B").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()


def _is_daily_fresh(daily_df: pd.DataFrame, max_age_days: int = 1) -> bool:
    """Return True if the last bar in `daily_df` is no more than
    `max_age_days` calendar days behind today (in US/Eastern).

    A daily parquet whose last bar is yesterday is fresh; a parquet
    whose last bar is 5 days old is stale. Used by
    `load_daily_price_context` to decide whether to trust the
    daily bar or fall back to RTH-filtered 1m.
    """
    if daily_df is None or daily_df.empty or "time" not in daily_df.columns:
        return False
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)
        last_ts = daily_df["time"].iloc[-1]
        if last_ts > 1e12:  # ms -> s
            last_ts = last_ts / 1000.0
        last_dt_et = datetime.fromtimestamp(float(last_ts), tz=et)
        # Allow a 1-day buffer for the "today" case (RTH may not
        # have closed yet when the EOD narrative runs in the late
        # afternoon, OR the daily rollup job hasn't run yet today).
        return (now_et.date() - last_dt_et.date()).days <= max_age_days
    except Exception:
        return False


def load_daily_price_context(loader: DataLoader, ticker: str) -> dict:
    """Load today's OHLCV via DataLoader for the daily EOD update.

    Returns today's open/high/low/close/change_pct/range_pct/body.

    Audit §2.7 fix: previously, this function resampled the FULL
    1m parquet to a daily bar via `df_1m.resample("B").agg(...)`.
    The `last` aggregator on `close` takes the last 1m bar of
    whatever's in the file — which may be a 20:00 Globex print,
    not the 16:00 settlement. The EOD narrative then reported an
    incorrect close level (and high/low, since Globex can extend
    the daily range well past RTH).

    The fix uses the daily-timeframe parquet directly via
    `loader.load_parquet(ticker, "1D")`. The daily file is the
    settlement bar by construction — it aggregates one bar per
    business day with `close = 16:00 ET settlement print` — and
    is updated by the data-freshness pipeline's daily rollup.

    Two safety nets:
      1. Freshness check: if the daily parquet's last bar is more
         than 1 calendar day behind today, we fall back to the
         RTH-filtered 1m resample (which always returns the 16:00
         settlement regardless of when the daily rollup last ran).
      2. Empty / missing daily file: same fallback.
    """
    parquet_sym = _resolve_parquet_symbol(ticker)

    # ── Primary: read the daily-timeframe parquet ─────────────
    daily_df = None
    try:
        daily_df = loader.load_parquet(parquet_sym, "1D")
    except Exception as e:
        log.debug("[daily_price_context] loader.load_parquet(1D) failed for %s: %s",
                  ticker, e)
        daily_df = None

    use_daily = (
        daily_df is not None
        and not daily_df.empty
        and _is_daily_fresh(daily_df, max_age_days=1)
    )

    if use_daily:
        # The daily file is up to date — use it directly.
        today = daily_df.iloc[-1]
        prev_close = (
            daily_df["close"].iloc[-2]
            if len(daily_df) >= 2
            else float(today["open"])
        )
    else:
        # Fallback: RTH-filtered 1m resample.
        try:
            df_1m = loader.load_price(parquet_sym)
        except Exception as e:
            log.warning(
                "Could not load price data for %s (%s): %s",
                ticker, parquet_sym, e,
            )
            return {}

        if df_1m.empty:
            return {}

        daily = _rth_filter_1m_to_daily(df_1m)
        if daily.empty:
            log.warning(
                "RTH-filtered daily resample is empty for %s "
                "— index may not be a US/Eastern DatetimeIndex",
                ticker,
            )
            return {}

        today = daily.iloc[-1]
        prev_close = (
            daily["close"].iloc[-2]
            if len(daily) >= 2
            else float(today["open"])
        )

    change_pct = round((float(today["close"]) / float(prev_close) - 1) * 100, 2)
    open_v = float(today["open"])
    range_pct = (
        round((float(today["high"]) - float(today["low"])) / open_v * 100, 2)
        if open_v > 0
        else 0.0
    )

    return {
        "open": round(float(today["open"]), 2),
        "high": round(float(today["high"]), 2),
        "low": round(float(today["low"]), 2),
        "close": round(float(today["close"]), 2),
        "change_pct": change_pct,
        "range_pct": range_pct,
        "body": "bullish" if float(today["close"]) > open_v else "bearish",
    }


# ── Track Alignment Assessment (for daily updates) ───────────────

def assess_track_alignment(
    track: str,
    today: dict,
    interactions: dict,
) -> tuple[bool, str]:
    """Programmatically assess if today's price action aligns with the mandated track.

    Returns (on_track: bool, assessment: str).
    The LLM never makes this judgment — Python evaluates it.
    """
    broke_wall_up = interactions.get("call_wall_broken", False)
    broke_wall_dn = interactions.get("put_wall_broken", False)
    tested_wall_up = interactions.get("call_wall_tested", False)
    tested_wall_dn = interactions.get("put_wall_tested", False)

    if "TRACK A" in track:
        # Breakout track: testing/breaking walls is ON track
        if broke_wall_up or broke_wall_dn:
            return True, "Wall broken — momentum expansion consistent with TRACK A."
        elif tested_wall_up or tested_wall_dn:
            return True, "Wall tested — pre-breakout compression consistent with TRACK A setup."
        else:
            return True, "Range-bound — no breakout trigger yet, but TRACK A still pending."

    elif "TRACK B" in track:
        # Fade track: breaking walls is OFF track (regime failure)
        if broke_wall_up or broke_wall_dn:
            return False, "Wall broken — TRACK B fade regime failing. Distribution model under stress."
        elif tested_wall_up or tested_wall_dn:
            return True, "Wall tested and held — consistent with TRACK B fade logic."
        else:
            return True, "Range-bound within walls — TRACK B fade environment intact."

    elif "TRACK C" in track:
        return True, "Observation mode — no track alignment requirement."

    return True, "Track alignment unclear."


def compute_level_interactions(
    today: dict,
    call_wall: float,
    put_wall: float,
    em_upper: float,
    em_lower: float,
    zero_gamma: float,
    gamma_magnet: float,
) -> dict:
    """Compute which levels were tested/broken today (vectorized comparisons).

    'tested' = intraday high/low touched the level
    'broken' = close-based acceptance beyond the level
    """
    high = today.get("high", 0)
    low = today.get("low", 0)
    close = today.get("close", 0)

    # All "tested" / "broken" flags require the level to be strictly
    # positive (a zero level means "no level found" — a 0 GEX wall, for
    # example, is not a real wall and must not register as tested or
    # broken). We standardise on the form `level > 0 and high >= level`
    # rather than the chained `high >= level > 0` because:
    #   1. The chained form is easy to mis-translate (see audit §2.9:
    #      the original `put_wall_tested` had `put_wall > 0` twice).
    #   2. The explicit form reads top-to-bottom: gate on validity
    #      first, then on the touch condition.
    return {
        "call_wall_tested": call_wall > 0 and high >= call_wall,
        "call_wall_broken": call_wall > 0 and close > call_wall,
        "put_wall_tested": put_wall > 0 and low <= put_wall,
        "put_wall_broken": put_wall > 0 and close < put_wall,
        "em_upper_tested": em_upper > 0 and high >= em_upper,
        "em_upper_broken": em_upper > 0 and close > em_upper,
        "em_lower_tested": em_lower > 0 and low <= em_lower,
        "em_lower_broken": em_lower > 0 and close < em_lower,
        "zero_gamma_crossed": (
            zero_gamma > 0 and low < zero_gamma < high
        ),
        "magnet_tested": (
            gamma_magnet > 0 and low < gamma_magnet < high
        ),
    }


# ── Economic Events ───────────────────────────────────────────────

# MEDIUM-impact events are only kept if their name matches one of these
# keywords — these are the events that historically move equity futures.
# All HIGH-impact events are kept unconditionally. LOW is always filtered out.
MEDIUM_ALLOWLIST_KEYWORDS = [
    "FOMC", "FED CHAIR", "POWELL", "INTEREST RATE",
    "CPI", "PCE", "PPI", "INFLATION",
    "NON-FARM PAYROLL", "NFP", "ADP EMPLOYMENT",
    "GDP", "ISM", "PMI",
    "RETAIL SALES", "DURABLE GOODS",
    "INITIAL JOBLESS CLAIMS", "UNEMPLOYMENT RATE",
    "MICHIGAN CONSUMER SENTIMENT", "CB CONSUMER CONFIDENCE",
]

# ── US-relevance filter ──
# The EconomicEvent DB table now has a `country` field (e.g. "USD", "EUR").
# Some callers (econ_calendar.py) filter by country="USD" directly.
# This function (fetch_week_events) uses keyword-based filtering as a
# secondary layer — it catches events where country is null (legacy rows)
# and provides finer-grained control via NON_US_KEYWORDS / US_KEYWORDS.
# Events matching any NON_US_KEYWORD are excluded
# (they are international events with indirect impact on US futures).
# Events matching US_KEYWORDS are always kept regardless of impact level.
# The goal is to keep the narrative focused on events that directly move
# ES/NQ futures.
NON_US_KEYWORDS = [
    # UK
    "CLAIMANT COUNT", "BOE", "BANK OF ENGLAND", "UK GDP", "UK CPI",
    "UK MANUFACTURING", "UK SERVICES", "UK CONSTRUCTION", "GFK CONSUMER",
    "BRC", "RICS", "UK RETAIL", "UK TRADE BALANCE", "UK INDUSTRIAL",
    "UK AVERAGE EARNINGS", "UK CLAIMANT", "PUBLIC SECTOR NET BORROWING",
    # Eurozone
    "FRENCH", "FRANCE", "GERMAN", "GERMANY", "SPANISH", "SPAIN",
    "ITALIAN", "ITALY", "DUTCH", "BELGIAN", "GREEK", "PORTUGUESE",
    "IRISH", "AUSTRIAN", "FINNISH", "EUROZONE", "EURO AREA",
    "EUROZONE FLASH", "EUROZONE COMPOSITE", "EUROZONE MANUFACTURING",
    "EUROZONE SERVICES", "EUROZONE CPI", "EUROZONE GDP",
    "EUROZONE INDUSTRIAL", "EUROZONE TRADE", "EUROZONE EMPLOYMENT",
    "EUROZONE UNEMPLOYMENT", "EUROZONE HICP", "EUROZONE PPI",
    "ECB", "EUROPEAN CENTRAL BANK", "MAIN REFINANCING RATE",
    "MONETARY POLICY STATEMENT", "ECB PRESS CONFERENCE",
    "LAGARDE", "EUROPEAN COMMISSION",
    # Japan
    "JAPANESE", "JAPAN", "BOJ", "BANK OF JAPAN", "TANKAN",
    "JAPAN GDP", "JAPAN CPI", "JAPAN INDUSTRIAL", "JAPAN TRADE",
    "JAPAN MANUFACTURING", "JAPAN SERVICES", "JAPAN RETAIL",
    # China
    "CHINESE", "CHINA", "CHINA GDP", "CHINA CPI", "CHINA PPI",
    "CHINA INDUSTRIAL", "CHINA RETAIL", "CHINA TRADE BALANCE",
    "CHINA MANUFACTURING", "CHINA SERVICES", "CAIXIN",
    # Australia
    "AUSTRALIAN", "AUSTRALIA", "RBA", "RESERVE BANK OF AUSTRALIA",
    "AUSTRALIA GDP", "AUSTRALIA CPI", "AUSTRALIA EMPLOYMENT",
    "AUSTRALIA RETAIL", "AUSTRALIA TRADE", "AUSTRALIA MANUFACTURING",
    # Canada
    "CANADIAN", "CANADA", "BOC", "BANK OF CANADA",
    "CANADA GDP", "CANADA CPI", "CANADA EMPLOYMENT",
    "CANADA RETAIL", "CANADA TRADE", "CANADA MANUFACTURING",
    # Switzerland
    "SWISS", "SWITZERLAND", "SNB", "SWISS NATIONAL BANK",
    # Other international
    "NZD", "NEW ZEALAND", "RBNZ",
    "SOUTH KOREA", "KOREAN", "KOSPI",
    "INDIA", "INDIAN", "RUSSIAN", "RUSSIA",
    "BRAZILIAN", "BRAZIL", "MEXICAN", "MEXICO",
    "SOUTH AFRICAN", "SOUTH AFRICA",
    "OPEC", "OPEC+",
    # International organizations (non-US)
    "IMF", "WORLD BANK", "OECD",
    # Foreign CPI/GDP that aren't US
    "CPI Q/Q",  # This is typically UK/EU quarterly CPI
    "CPI Y/Y",  # This is typically foreign (US uses "CPI M/M" or "CPI Y/Y" but context matters)
]

# US event keywords — events matching these are always kept (US-relevant)
US_KEYWORDS = [
    "CPI M/M", "CORE CPI", "MEDIAN CPI", "TRIMMED CPI", "COMMON CPI",
    "CPI Q/Q",  # US quarterly CPI (released at 18:45 ET, not 02:00 like foreign)
    "PCE", "CORE PCE", "PPI", "CORE PPI",
    "NFP", "NON-FARM", "ADP", "INITIAL JOBLESS", "CONTINUING CLAIMS",
    "UNEMPLOYMENT RATE", "JOBLESS CLAIMS",
    "GDP", "GDP PRICE INDEX", "GROSS DOMESTIC PRODUCT",
    "ISM MANUFACTURING", "ISM SERVICES", "ISM PRICES PAID",
    "S&P GLOBAL",  # Only US PMIs (S&P Global brand); foreign flash PMIs filtered by NON_US_KEYWORDS
    "RETAIL SALES", "CORE RETAIL", "DURABLE GOODS", "CORE DURABLE",
    "FOMC", "FEDERAL OPEN MARKET", "FED CHAIR", "POWELL",
    "INTEREST RATE DECISION", "FEDERAL FUNDS",
    "CONSUMER CONFIDENCE", "CONSUMER SENTIMENT", "MICHIGAN",
    "NEW HOME SALES", "EXISTING HOME SALES", "HOUSING STARTS",
    "BUILDING PERMITS", "CASE-SHILLER",
    "CRUDE OIL INVENTORIES", "EIA", "API CRUDE",
    "TRADE BALANCE", "TIC", "TREASURY INTERNATIONAL",
    "INDUSTRIAL PRODUCTION", "CAPACITY UTILIZATION",
    "FACTORY ORDERS", "INVENTORIES", "WHOLESALE",
    "CURRENT ACCOUNT", "BUDGET BALANCE", "TIC FLOWS",
    "TREASURY AUCTION", "BOND AUCTION",
    "JOINT ECONOMIC", "BEIGE BOOK",
    "PHILLY FED", "NY EMPIRE", "RICHMOND FED", "KC FED",
    "DALLAS FED", "CHICAGO PMI",
    "PRESIDENT TRUMP", "TRUMP SPEAKS", "PRESIDENT SPEAKS",
    "FOSTEC", "FED SURVEY",
    "MBA MORTGAGE", "JOB CUTS", "CHAIN STORE SALES",
]


def _is_non_us_event(name: str) -> bool:
    """Check if an event name matches a non-US keyword (international event)."""
    name_upper = (name or "").upper()
    return any(kw in name_upper for kw in NON_US_KEYWORDS)


def _is_us_event(name: str) -> bool:
    """Check if an event name matches a US keyword."""
    name_upper = (name or "").upper()
    return any(kw in name_upper for kw in US_KEYWORDS)

# Always include these events as macro drivers even if the upstream
# impact classification is not HIGH/MEDIUM.
CRITICAL_EVENT_KEYWORDS = [
    "FOMC MEETING MINUTES",
    "FEDERAL OPEN MARKET COMMITTEE MINUTES",
    "FOMC MINUTES",
]

def _is_market_moving_medium(name: str) -> bool:
    """Check if a MEDIUM-impact event name matches the allowlist."""
    name_upper = (name or "").upper()
    return any(kw in name_upper for kw in MEDIUM_ALLOWLIST_KEYWORDS)


def _is_critical_event(name: str) -> bool:
    """Critical macro events that should never be filtered out."""
    name_upper = (name or "").upper()
    return any(kw in name_upper for kw in CRITICAL_EVENT_KEYWORDS)


async def fetch_week_events(start_date: date, end_date: date) -> list[dict]:
    """Fetch economic events for a date range from the Prisma SQLite DB.

    Filtering rules:
    - HIGH impact: always kept.
    - MEDIUM impact: kept only if the event name matches a keyword in
      MEDIUM_ALLOWLIST_KEYWORDS (e.g. FOMC speeches, ADP, CPI, ISM, etc.).
    - LOW impact: always filtered out.

    Each event includes a 'passed' flag indicating whether the event time
    has already occurred relative to the current time, so the LLM can
    distinguish upcoming from already-released events.
    """
    db = await get_db()
    from datetime import datetime as dt_cls, timezone as tz_cls

    # ET timezone is defined at the top of briefing_core.py
    start_dt = dt_cls.combine(start_date, dt_cls.min.time(), tzinfo=ET)
    end_dt = dt_cls.combine(end_date, dt_cls.max.time(), tzinfo=ET)

    # Current time in ET for the 'passed' flag
    now_et = dt_cls.now(ET)

    try:
        events = await db.economicevent.find_many(
            where={
                "datetime": {
                    "gte": start_dt,
                    "lte": end_dt
                }
            },
            order={"datetime": "asc"}
        )

        res = []
        for e in events:
            impact = (e.impact or "").upper()
            is_critical = _is_critical_event(e.name)

            # ── US-relevance filter ──
            # Exclude international events that don't directly move US futures.
            # Exception: keep if it matches a US keyword (e.g. "CPI M/M" is US
            # even if "CPI Y/Y" alone might be foreign).
            if _is_non_us_event(e.name) and not _is_us_event(e.name):
                continue

            # Filter out LOW unless event is explicitly marked critical.
            if impact == "LOW" and not is_critical:
                continue

            # For MEDIUM, only keep if name matches the allowlist
            if impact == "MEDIUM" and not (_is_market_moving_medium(e.name) or is_critical):
                continue

            # e.datetime is a python datetime object
            # If DB datetime is naive, treat it as UTC source time first and
            # convert to ET. Interpreting naive values as ET can shift weekday.
            if e.datetime.tzinfo:
                evt_dt = e.datetime.astimezone(ET)
            else:
                evt_dt = e.datetime.replace(tzinfo=tz_cls.utc).astimezone(ET)

            # Flag whether this event has already passed
            passed = evt_dt < now_et

            res.append({
                "date": evt_dt.strftime("%Y-%m-%d"),
                "day_of_week": evt_dt.strftime("%A"),
                "time_et": evt_dt.strftime("%H:%M ET"),
                "name": e.name,
                "impact": e.impact.upper() if e.impact else "UNKNOWN",
                "passed": passed
            })
        return res
    except Exception as e:
        log.warning(f"Failed to fetch economic events from DB: {e}")
        return []


# ── Utility ───────────────────────────────────────────────────────

def get_week_label(reference_date: date | None = None) -> str:
    """Get a human-readable label for the week containing reference_date."""
    if reference_date is None:
        reference_date = datetime.now(ET).date()

    # Monday-Friday for the current week anchor.
    monday = reference_date - timedelta(days=reference_date.weekday())
    friday = monday + timedelta(days=4)

    if monday.month == friday.month:
        return f"Week of {monday.strftime('%b %d')} – {friday.strftime('%d, %Y')}"
    else:
        return f"Week of {monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"


def get_prior_friday(reference_date: date | None = None) -> date:
    """Get the most recent Friday from the reference date."""
    if reference_date is None:
        reference_date = datetime.now(ET).date()
    days_back = (reference_date.weekday() - 4) % 7
    if days_back == 0 and reference_date.weekday() == 4:
        return reference_date  # Today is Friday
    return reference_date - timedelta(days=days_back if days_back > 0 else 7)


# ── Prisma DB Helpers ─────────────────────────────────────────────
# DB-first architecture: structured per-ticker data is stored in Prisma
# tables (WeeklyBriefingTicker, DailyEodTickerSnapshot). The "TOON" JSON
# is assembled in-memory from DB queries only when the LLM needs it —
# it is never persisted as a file or a JSON blob field.

def _ensure_database_url() -> None:
    """Set DATABASE_URL if not already set, pointing to the SQLite DB."""
    if os.getenv("DATABASE_URL"):
        return
    os.environ["DATABASE_URL"] = f"file:{DB_PATH.as_posix()}"


async def get_db():
    """Return a connected Prisma client.

    Usage:
        db = await get_db()
        try:
            await db.weeklybriefing.create(...)
        finally:
            await db.disconnect()
    """
    from prisma import Prisma
    _ensure_database_url()
    db = Prisma()
    # Set a generous timeout for SQLite — the Next.js dev server holds
    # a concurrent connection to the same DB, which can cause lock
    # contention. The timeout gives SQLite time to acquire the write lock.
    await db.connect()
    # Enable WAL mode for better concurrency (readers don't block writers)
    try:
        await db.query_raw("PRAGMA journal_mode=WAL;")
        await db.query_raw("PRAGMA busy_timeout=10000;")
    except Exception:
        pass  # WAL mode may already be enabled or not supported
    return db


async def save_weekly_briefing_to_db(
    week_start: date,
    week_end: date,
    ticker_blocks: list[dict],
) -> str:
    """Save the weekly briefing to the Prisma DB.

    Creates a WeeklyBriefing parent row + one WeeklyBriefingTicker child
    per ticker. Uses upsert so re-running for the same week updates in place.

    Returns the briefing ID.
    """
    db = await get_db()
    try:
        from datetime import datetime as dt_cls

        week_start_dt = dt_cls.combine(week_start, dt_cls.min.time())
        week_end_dt = dt_cls.combine(week_end, dt_cls.min.time())

        # Upsert parent
        briefing = await db.weeklybriefing.upsert(
            where={"weekStartDate": week_start_dt},
            data={
                "create": {
                    "weekStartDate": week_start_dt,
                    "weekEndDate": week_end_dt,
                    "tickersCovered": len(ticker_blocks),
                },
                "update": {
                    "weekEndDate": week_end_dt,
                    "tickersCovered": len(ticker_blocks),
                    "generatedAt": dt_cls.now(),
                },
            },
        )

        # Delete old ticker snapshots for this briefing (replace)
        await db.weeklybriefingticker.delete_many(
            where={"briefingId": briefing.id}
        )

        # Create new ticker snapshots
        for block in ticker_blocks:
            pw = block.get("prior_week", {})
            rm = block.get("recent_momentum", {})
            gr = block.get("gex_regime", {})
            kl = block.get("key_levels", {})
            vol = block.get("volatility", {})
            hf = block.get("hedge_flows", {})
            ems = block.get("expected_moves", {})
            inv = block.get("account_invalidation", {})
            sc = block.get("scenarios", {})

            friday_em = ems.get("friday", {})

            await db.weeklybriefingticker.create(
                data={
                    "briefingId": briefing.id,
                    "ticker": block["ticker"],
                    "asset": block.get("asset", block["ticker"]),
                    "spotPrice": block.get("spot_price", 0),
                    # Prior week
                    "priorWeekOpen": pw.get("open"),
                    "priorWeekHigh": pw.get("high"),
                    "priorWeekLow": pw.get("low"),
                    "priorWeekClose": pw.get("close"),
                    "priorWeekChangePct": pw.get("change_pct"),
                    "priorWeekRangePct": pw.get("range_pct"),
                    # Momentum
                    "last5dChangePct": rm.get("last_5d_change_pct"),
                    "last10dChangePct": rm.get("last_10d_change_pct"),
                    "trend": rm.get("trend"),
                    # GEX regime
                    "regimeLabel": gr.get("label", "NEUTRAL"),
                    "gexSign": gr.get("gex_sign", "NEUTRAL"),
                    "totalGex": gr.get("total_gex", 0),
                    "concentrationScore": gr.get("concentration_score"),
                    # Mandated track
                    "mandatedTrack": block.get("mandated_execution_track", ""),
                    # Key levels
                    "callWall": kl.get("call_wall", 0),
                    "putWall": kl.get("put_wall", 0),
                    "zeroGamma": kl.get("zero_gamma"),
                    "gammaMagnet": kl.get("gamma_magnet"),
                    "pinStrike": kl.get("pin_strike"),
                    "pinOdds": kl.get("pin_odds"),
                    "wallSeparation": kl.get("wall_separation"),
                    # Volatility
                    "atmIv": vol.get("atm_iv"),
                    "put25dIv": vol.get("put_25d_iv"),
                    "call25dIv": vol.get("call_25d_iv"),
                    "skewPremium": vol.get("skew_premium"),
                    "skewDirection": vol.get("skew_direction"),
                    # Hedge flows
                    "hedgeFlowBias": hf.get("bias"),
                    # Friday EM (terminal boundary)
                    "fridayEmUpper": friday_em.get("upper"),
                    "fridayEmLower": friday_em.get("lower"),
                    "fridayEmValue": friday_em.get("em"),
                    # Account invalidation
                    "bullishInvalidation": inv.get("bullish_invalidation", 0),
                    "bearishInvalidation": inv.get("bearish_invalidation", 0),
                    "distToBullishInvPct": inv.get("distance_to_bullish_inv_pct", 0),
                    "distToBearishInvPct": inv.get("distance_to_bearish_inv_pct", 0),
                    "invalidationMandate": inv.get("mandate", ""),
                    # Scenarios
                    "scenarioBullish": sc.get("bullish"),
                    "scenarioBearish": sc.get("bearish"),
                    "scenarioNeutral": sc.get("neutral"),
                }
            )

        log.info("✓ Saved weekly briefing to DB: %s (%d tickers)", briefing.id, len(ticker_blocks))
        return briefing.id

    finally:
        await db.disconnect()


def fetch_vol_context(ticker: str, target_date: date) -> dict:
    """
    Fetches Volatility Risk Premium and high-timeframe trend friction features
    from the feature store (SQLite + Parquet) for a given ticker and date.
    """
    import sqlite3
    import numpy as np
    
    # Defaults
    context = {
        "vix": None,
        "vvix": None,
        "historical_vol_20d": None,
        "volatility_risk_premium": None,
        "vrp_interpretation": "PREMIUM_UNDERPRICED",
        "dist_21_ema_pct": None,
        "dist_200_sma_pct": None
    }
    
    # 1. Fetch Volatility & VRP from SQLite DB
    try:
        target_dt = datetime.combine(target_date, datetime.min.time())
        target_ms = int(target_dt.timestamp() * 1000)
        
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT historical_vol_20d, volatility_risk_premium 
                FROM MacroSnapshot 
                WHERE ticker = ? AND tradingDate <= ? 
                ORDER BY tradingDate DESC 
                LIMIT 1
                """,
                (ticker, target_ms)
            )
            row = cursor.fetchone()
            if row:
                hv_val, vrp_val = row
                
                # Apply clean float check to prevent NaN serialization issues
                if hv_val is not None and pd.notna(hv_val):
                    context["historical_vol_20d"] = float(hv_val)
                if vrp_val is not None and pd.notna(vrp_val):
                    context["volatility_risk_premium"] = float(vrp_val)
                    context["vrp_interpretation"] = "PREMIUM_OVERPRICED" if vrp_val > 0.03 else "PREMIUM_UNDERPRICED"
    except Exception as e:
        log.error(f"Error fetching volatility context from DB for {ticker}: {e}", exc_info=True)

    # 2. Fetch Trend Friction features from centralized Parquet matrix
    try:
        friction_path = REPO_ROOT / "data" / "derived" / "market_friction_matrix.parquet"
        if friction_path.exists():
            friction_df = pd.read_parquet(str(friction_path))
            if not friction_df.empty:
                ticker_filter = [ticker]
                if ticker == "SPX":
                    ticker_filter.append("SPY")
                elif ticker == "SPY":
                    ticker_filter.append("SPX")
                    
                df_ticker = friction_df[friction_df['ticker'].isin(ticker_filter)].copy()
                if not df_ticker.empty:
                    df_ticker['date_key'] = df_ticker['date_key'].astype(str)
                    target_date_str = target_date.strftime('%Y-%m-%d')
                    
                    df_sorted = df_ticker[df_ticker['date_key'] <= target_date_str].sort_values(by='date_key', ascending=False)
                    if not df_sorted.empty:
                        latest_row = df_sorted.iloc[0]
                        
                        def clean_float(val):
                            return float(val) if pd.notna(val) else None
                            
                        context["vix"] = clean_float(latest_row.get("vix_close"))
                        context["vvix"] = clean_float(latest_row.get("vvix_close"))
                        context["dist_21_ema_pct"] = clean_float(latest_row.get("dist_21_ema_pct"))
                        context["dist_200_sma_pct"] = clean_float(latest_row.get("dist_200_sma_pct"))
    except Exception as e:
        log.error(f"Error reading market friction matrix for {ticker}: {e}", exc_info=True)
        
    return context


def _reconstruct_confluence(snap) -> dict:
    """Reconstruct GEX × EM confluence verdict from DB snapshot fields."""
    try:
        from scripts.trader.signals.gex_em_confluence import compute_gex_em_verdict
        gex_sign = snap.gexSign or "NEUTRAL"
        regime_label = snap.regimeLabel or "NEUTRAL"
        em_upper = snap.fridayEmUpper
        em_lower = snap.fridayEmLower
        spot = snap.spotPrice or 0
        if em_upper and em_lower and spot > 0:
            return compute_gex_em_verdict(
                gex_regime=("NEGATIVE" if gex_sign == "NEGATIVE" else "POSITIVE" if gex_sign == "POSITIVE" else "NEUTRAL"),
                regime_label=regime_label,
                em_upper=em_upper,
                em_lower=em_lower,
                spot=spot,
                call_wall=snap.callWall,
                put_wall=snap.putWall,
                gamma_magnet=snap.gammaMagnet,
            )
    except Exception:
        pass
    return {}


def _reconstruct_weekly_ems(
    friday_upper: float | None,
    friday_lower: float | None,
    friday_em: float | None,
    spot: float | None,
) -> dict:
    """Reconstruct the per-day weekly EM envelope from the Friday EM values
    stored in the DB.

    The DB only persists the Friday (terminal) EM values. We reconstruct the
    Mon-Fri progression using √(time) scaling, the same model used by
    ``compute_weekly_ems()`` but in reverse — Friday is the full envelope,
    and each prior day scales by √(day/5).

    Returns a dict ``{monday: {upper, lower, em}, ..., friday: {upper, lower, em}}``.
    """
    if not friday_upper or not friday_lower or friday_upper <= 0 or friday_lower <= 0:
        return {}

    import math
    weekly_em = friday_em or ((friday_upper - friday_lower) / 2)
    if weekly_em <= 0:
        return {}

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    result = {}
    for i, day in enumerate(day_names):
        day_dte = i + 1  # 1 through 5
        day_em = weekly_em * math.sqrt(day_dte / 5)
        # Use the spot from the DB; fall back to the midpoint of the Friday envelope
        ref_spot = spot if spot and spot > 0 else (friday_upper + friday_lower) / 2
        result[day] = {
            "upper": round(ref_spot + day_em, 2),
            "lower": round(ref_spot - day_em, 2),
            "em": round(day_em, 2),
        }
    return result


async def load_weekly_briefing_from_db(week_start: date | None = None) -> dict | None:
    """Load the latest (or specified) weekly briefing from DB and assemble
    the in-memory TOON JSON for the LLM.

    This is the DB-first equivalent of reading briefing.json — but instead
    of parsing a file, we query structured DB fields and build the JSON
    in memory.
    """
    from datetime import datetime as dt_cls

    db = await get_db()
    try:
        if week_start:
            from datetime import timedelta
            start_min = dt_cls.combine(week_start - timedelta(days=1), dt_cls.min.time())
            start_max = dt_cls.combine(week_start + timedelta(days=1), dt_cls.max.time())
            briefing = await db.weeklybriefing.find_first(
                where={
                    "weekStartDate": {
                        "gte": start_min,
                        "lte": start_max,
                    }
                },
                order={"weekStartDate": "desc"},
                include={"tickerSnapshots": True},
            )
        else:
            # Get the most recent briefing
            briefing = await db.weeklybriefing.find_first(
                order={"weekStartDate": "desc"},
                include={"tickerSnapshots": True},
            )

        if not briefing:
            return None

        # Enrich DB snapshots with current translation context so narratives can
        # display both futures-scale and original proxy-scale levels.
        unified_lookup = load_macro_levels(session="live")

        def _proxy_context(ticker: str, snap) -> dict:
            if ticker not in {"SPY", "QQQ"}:
                return {}

            unified_entry = unified_lookup.get(ticker)
            if not unified_entry:
                return {}

            meta = parse_meta_fields(unified_entry)
            ratio = meta.get("FUTURES_RATIO", 0)
            basis = meta.get("FUTURES_BASIS", 0)
            if not ratio or ratio <= 0:
                return {}

            def _inverse(level: float | None) -> float | None:
                if level is None:
                    return None
                return round((float(level) - float(basis)) / float(ratio), 2)

            return {
                "proxy_symbol": ticker,
                "futures_symbol": "MES" if ticker == "SPY" else "MNQ",
                "spot_proxy": _inverse(snap.spotPrice),
                "call_wall_proxy": _inverse(snap.callWall),
                "put_wall_proxy": _inverse(snap.putWall),
                "zero_gamma_proxy": _inverse(snap.zeroGamma),
                "gamma_magnet_proxy": _inverse(snap.gammaMagnet),
                "bullish_invalidation_proxy": _inverse(snap.bullishInvalidation),
                "bearish_invalidation_proxy": _inverse(snap.bearishInvalidation),
            }

        # Assemble TOON in memory
        tickers = []
        for snap in briefing.tickerSnapshots:
            tickers.append({
                "ticker": snap.ticker,
                "asset": snap.asset,
                "spot_price": snap.spotPrice,
                "prior_week": {
                    "open": snap.priorWeekOpen,
                    "high": snap.priorWeekHigh,
                    "low": snap.priorWeekLow,
                    "close": snap.priorWeekClose,
                    "change_pct": snap.priorWeekChangePct,
                    "range_pct": snap.priorWeekRangePct,
                },
                "recent_momentum": {
                    "last_5d_change_pct": snap.last5dChangePct,
                    "last_10d_change_pct": snap.last10dChangePct,
                    "trend": snap.trend,
                },
                "gex_regime": {
                    "label": snap.regimeLabel,
                    "gex_sign": snap.gexSign,
                    "total_gex": snap.totalGex,
                    "concentration_score": snap.concentrationScore,
                },
                "mandated_execution_track": snap.mandatedTrack,
                "key_levels": {
                    "call_wall": snap.callWall,
                    "put_wall": snap.putWall,
                    "zero_gamma": snap.zeroGamma,
                    "gamma_magnet": snap.gammaMagnet,
                    "pin_strike": snap.pinStrike,
                    "pin_odds": snap.pinOdds,
                    "wall_separation": snap.wallSeparation,
                },
                "volatility": {
                    "atm_iv": snap.atmIv,
                    "put_25d_iv": snap.put25dIv,
                    "call_25d_iv": snap.call25dIv,
                    "skew_premium": snap.skewPremium,
                    "skew_direction": snap.skewDirection,
                },
                "hedge_flows": {
                    "bias": snap.hedgeFlowBias,
                },
                "account_invalidation": {
                    "bullish_invalidation": snap.bullishInvalidation,
                    "bearish_invalidation": snap.bearishInvalidation,
                    "distance_to_bullish_inv_pct": snap.distToBullishInvPct,
                    "distance_to_bearish_inv_pct": snap.distToBearishInvPct,
                    "mandate": snap.invalidationMandate,
                },
                "scenarios": {
                    "bullish": snap.scenarioBullish,
                    "bearish": snap.scenarioBearish,
                    "neutral": snap.scenarioNeutral,
                },
                "proxy_context": _proxy_context(snap.ticker, snap),
                "institutional_volatility_context": fetch_vol_context(snap.ticker, briefing.weekStartDate.date()),
                "expected_moves": _reconstruct_weekly_ems(
                    snap.fridayEmUpper, snap.fridayEmLower, snap.fridayEmValue,
                    snap.spotPrice,
                ),
                "macro_context": build_weekly_macro_context(snap.ticker),
                "confluence_verdict": _reconstruct_confluence(snap),
            })

        from scripts.trader.weekly_briefing import fetch_week_earnings
        events = await fetch_week_events(briefing.weekStartDate.date(), briefing.weekEndDate.date())
        earnings = fetch_week_earnings(briefing.weekStartDate.date(), briefing.weekEndDate.date())

        return {
            "meta": {
                "id": briefing.id,
                "week_start_date": briefing.weekStartDate.isoformat(),
                "week_end_date": briefing.weekEndDate.isoformat(),
                "generated_at": briefing.generatedAt.isoformat(),
                "tickers_covered": briefing.tickersCovered,
            },
            "economic_events": events,
            "earnings_events": earnings,
            "tickers": tickers,
        }
    finally:
        await db.disconnect()


async def save_narrative_to_db(briefing_id: str, summary_md: str, is_daily: bool = False, eod_id: str | None = None) -> None:
    """Store the LLM-generated narrative in the DB."""
    db = await get_db()
    try:
        # Set busy timeout so SQLite waits for the write lock instead of
        # immediately timing out when the Next.js dev server is connected.
        await db.query_raw("PRAGMA busy_timeout=15000;")
        if is_daily and eod_id:
            await db.dailyeodupdate.update(
                where={"id": eod_id},
                data={"summaryMd": summary_md},
            )
        else:
            await db.weeklybriefing.update(
                where={"id": briefing_id},
                data={"summaryMd": summary_md},
            )
        log.info("✓ Saved narrative to DB (%s)", "daily" if is_daily else "weekly")
    finally:
        await db.disconnect()


# ── Prior Week Performance ──────────────────────────────────────

async def get_prior_week_performance(reference_week_start: date | None = None) -> str:
    """Query DB for the previous week's closed trades and compute aggregate stats.

    Returns a formatted string for the weekly prompt showing:
    - Total P&L per instrument
    - Win rate, trade count
    - Max drawdown
    - Level accuracy (from EOD narratives if available)
    """
    from prisma import Prisma
    from datetime import datetime, timedelta, timezone

    db = Prisma()
    await db.connect()

    acc = await db.account.find_first(where={'name': 'Auto Prop Firm 50K'})
    if not acc:
        await db.disconnect()
        return "No prior week data (account not found)."

    # Get trades from the prior completed week (Mon-Fri), anchored to the
    # weekly briefing's week_start when provided.
    if reference_week_start is not None:
        this_monday_date = reference_week_start
    else:
        today = datetime.now(timezone.utc).date()
        this_monday_date = today - timedelta(days=today.weekday())

    last_monday_date = this_monday_date - timedelta(days=7)
    last_friday_date = last_monday_date + timedelta(days=4)
    last_monday = datetime.combine(last_monday_date, datetime.min.time(), tzinfo=timezone.utc)
    last_friday = datetime.combine(last_friday_date, datetime.max.time(), tzinfo=timezone.utc)

    trades = await db.trade.find_many(
        where={
            'accountId': acc.id,
            'entryDate': {
                'gte': last_monday,
                'lte': last_friday,
            },
        },
        order={'entryDate': 'asc'}
    )

    if not trades:
        await db.disconnect()
        return "No trades found for the prior week."

    # Compute stats
    instruments = {}
    all_pnl = []
    for t in trades:
        ticker = t.ticker or 'UNKNOWN'
        pnl = t.pnl or 0.0
        if ticker not in instruments:
            instruments[ticker] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'max_loss': 0.0}
        instruments[ticker]['trades'] += 1
        instruments[ticker]['pnl'] += pnl
        if pnl > 0:
            instruments[ticker]['wins'] += 1
        elif pnl < 0:
            instruments[ticker]['losses'] += 1
            instruments[ticker]['max_loss'] = min(instruments[ticker]['max_loss'], pnl)
        all_pnl.append(pnl)

    total_pnl = sum(v['pnl'] for v in instruments.values())
    total_trades = sum(v['trades'] for v in instruments.values())
    total_wins = sum(v['wins'] for v in instruments.values())
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    # Compute max drawdown (peak-to-trough on cumulative P&L)
    cumulative = 0
    peak = 0
    max_dd = 0
    for pnl in all_pnl:
        cumulative += pnl
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)

    lines = [
        f"Prior Week Performance ({last_monday_date.strftime('%Y-%m-%d')} to {last_friday_date.strftime('%Y-%m-%d')}):",
        f"  Total P&L: ${total_pnl:,.2f}",
        f"  Total trades: {total_trades} | Win rate: {win_rate:.1f}%",
        f"  Max drawdown: ${max_dd:,.2f}",
    ]

    for ticker, stats in sorted(instruments.items()):
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        lines.append(f"  {ticker}: {stats['trades']} trades | P&L ${stats['pnl']:,.2f} | WR {wr:.0f}%")

    await db.disconnect()
    return "\n".join(lines)


# ── Daily EOD DB Functions ───────────────────────────────────────

async def save_daily_eod_to_db(
    eod_date: date,
    weekly_briefing_id: str | None,
    ticker_snapshots: list[dict],
) -> str:
    """Save the daily EOD update to the Prisma DB.

    Creates a DailyEodUpdate parent + DailyEodTickerSnapshot children.
    Uses upsert so re-running for the same date updates in place.

    Returns the EOD update ID.
    """
    db = await get_db()
    try:
        from datetime import datetime as dt_cls

        eod_dt = dt_cls.combine(eod_date, dt_cls.min.time())

        # Upsert parent
        eod = await db.dailyeodupdate.upsert(
            where={"date": eod_dt},
            data={
                "create": {
                    "date": eod_dt,
                    "weeklyBriefingId": weekly_briefing_id,
                    "tickersCovered": len(ticker_snapshots),
                },
                "update": {
                    "weeklyBriefingId": weekly_briefing_id,
                    "tickersCovered": len(ticker_snapshots),
                    "generatedAt": dt_cls.now(),
                },
            },
        )

        # Delete old ticker snapshots for this EOD (replace)
        await db.dailyeodtickersnapshot.delete_many(
            where={"eodUpdateId": eod.id}
        )

        # Create new ticker snapshots
        for snap in ticker_snapshots:
            await db.dailyeodtickersnapshot.create(
                data={
                    "eodUpdateId": eod.id,
                    "ticker": snap["ticker"],
                    # Today's price action
                    "openPrice": snap.get("open_price", 0),
                    "highPrice": snap.get("high_price", 0),
                    "lowPrice": snap.get("low_price", 0),
                    "closePrice": snap.get("close_price", 0),
                    "changePct": snap.get("change_pct", 0),
                    "rangePct": snap.get("range_pct", 0),
                    "body": snap.get("body", ""),
                    # Weekly anchor reference
                    "mandatedTrack": snap.get("mandated_track", ""),
                    "callWall": snap.get("call_wall", 0),
                    "putWall": snap.get("put_wall", 0),
                    "todayEmUpper": snap.get("today_em_upper"),
                    "todayEmLower": snap.get("today_em_lower"),
                    # Level interactions
                    "callWallTested": snap.get("call_wall_tested", False),
                    "callWallBroken": snap.get("call_wall_broken", False),
                    "putWallTested": snap.get("put_wall_tested", False),
                    "putWallBroken": snap.get("put_wall_broken", False),
                    "emUpperTested": snap.get("em_upper_tested", False),
                    "emUpperBroken": snap.get("em_upper_broken", False),
                    "emLowerTested": snap.get("em_lower_tested", False),
                    "emLowerBroken": snap.get("em_lower_broken", False),
                    # Invalidation proximity
                    "bullishInvalidation": snap.get("bullish_invalidation", 0),
                    "bearishInvalidation": snap.get("bearish_invalidation", 0),
                    "distToBullishInvPct": snap.get("dist_to_bullish_inv_pct", 0),
                    "distToBearishInvPct": snap.get("dist_to_bearish_inv_pct", 0),
                    # Track alignment
                    "onTrack": snap.get("on_track", True),
                    "trackAssessment": snap.get("track_assessment", ""),
                    # Regime check
                    "weeklyRegime": snap.get("weekly_regime", ""),
                    "currentRegime": snap.get("current_regime", ""),
                    "regimeChanged": snap.get("regime_changed", False),
                    # Weekly progress
                    "positionInEmEnvelope": snap.get("position_in_em_envelope"),
                    "daysElapsedInWeek": snap.get("days_elapsed_in_week", 0),
                    "daysRemainingInWeek": snap.get("days_remaining_in_week", 0),
                }
            )

        log.info("✓ Saved daily EOD to DB: %s (%d tickers)", eod.id, len(ticker_snapshots))
        return eod.id

    finally:
        await db.disconnect()


async def load_daily_eod_from_db(eod_date: date | None = None, session_type: str = "eod") -> dict | None:
    """Load the latest (or specified) daily EOD update from DB and assemble
    the in-memory TOON JSON for the LLM.
    """
    from datetime import datetime as dt_cls, timedelta
    
    db = await get_db()
    try:
        if eod_date:
            eod_dt = dt_cls.combine(eod_date, dt_cls.min.time())
            eod = await db.dailyeodupdate.find_unique(
                where={"date": eod_dt},
                include={"tickerSnapshots": True},
            )
        else:
            eod = await db.dailyeodupdate.find_first(
                order={"date": "desc"},
                include={"tickerSnapshots": True},
            )
            
        if not eod:
            return None
            
        target_date = eod.date.date()
        if session_type == "eod":
            # For EOD, get next day's events
            events_date = target_date + timedelta(days=1)
        else:
            # For Open, get today's events
            events_date = target_date
            
        events = await fetch_week_events(events_date, events_date)

        tickers = []
        for snap in eod.tickerSnapshots:
            tickers.append({
                "ticker": snap.ticker,
                "today": {
                    "open": snap.openPrice,
                    "high": snap.highPrice,
                    "low": snap.lowPrice,
                    "close": snap.closePrice,
                    "change_pct": snap.changePct,
                    "range_pct": snap.rangePct,
                    "body": snap.body,
                },
                "weekly_anchor": {
                    "mandated_track": snap.mandatedTrack,
                    "call_wall": snap.callWall,
                    "put_wall": snap.putWall,
                    "today_em_upper": snap.todayEmUpper,
                    "today_em_lower": snap.todayEmLower,
                },
                "level_interactions": {
                    "call_wall_tested": snap.callWallTested,
                    "call_wall_broken": snap.callWallBroken,
                    "put_wall_tested": snap.putWallTested,
                    "put_wall_broken": snap.putWallBroken,
                    "em_upper_tested": snap.emUpperTested,
                    "em_upper_broken": snap.emUpperBroken,
                    "em_lower_tested": snap.emLowerTested,
                    "em_lower_broken": snap.emLowerBroken,
                },
                "invalidation_proximity": {
                    "bullish_invalidation": snap.bullishInvalidation,
                    "bearish_invalidation": snap.bearishInvalidation,
                    "dist_to_bullish_inv_pct": snap.distToBullishInvPct,
                    "dist_to_bearish_inv_pct": snap.distToBearishInvPct,
                },
                "regime_check": {
                    "weekly_regime": snap.weeklyRegime,
                    "current_regime": snap.currentRegime,
                    "regime_changed": snap.regimeChanged,
                },
                "weekly_progress": {
                    "position_in_em_envelope": snap.positionInEmEnvelope,
                    "days_elapsed_in_week": snap.daysElapsedInWeek,
                    "days_remaining_in_week": snap.daysRemainingInWeek,
                },
                "on_track": snap.onTrack,
                "track_assessment": snap.trackAssessment,
                "institutional_volatility_context": fetch_vol_context(snap.ticker, eod.date.date())
            })

        return {
            "meta": {
                "id": eod.id,
                "date": eod.date.isoformat(),
                "weekly_briefing_id": eod.weeklyBriefingId,
                "generated_at": eod.generatedAt.isoformat(),
                "tickers_covered": eod.tickersCovered,
            },
            "economic_events": events,
            "tickers": tickers,
        }
    finally:
        await db.disconnect()


# ── Compact Pre-Processed Summary for LLM ──────────────────────────

def build_compact_briefing(briefing_data: dict, tickers: list[str] | None = None) -> str:
    """Build a compact pre-processed summary that gives the LLM only what it
    needs for trade plan generation. This replaces the raw TOON JSON to save
    ~1000+ tokens by:
    - Filtering to configured tickers
    - Extracting only regime, spot, key levels, and bias
    - Pre-computing level interactions into plain English
    - Stripping weekly progress, track assessment, and vol context
      (these are EOD review fields, not trade-plan inputs)
    """
    import json as _json

    if tickers is None:
        tickers = ["NQ1", "ES1"]

    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    events = briefing_data.get("economic_events", [])

    def _compact_ticker(t: dict) -> dict:
        """Extract only trade-plan-relevant fields from a ticker snapshot."""
        if not t:
            return {}
        today = t.get("today", {})
        anchor = t.get("weekly_anchor", {})
        regime = t.get("regime_check", {})
        inv = t.get("invalidation_proximity", {})
        interactions = t.get("level_interactions", {})

        # Pre-compute level interactions into concise English
        flags = []
        if interactions.get("call_wall_tested"): flags.append("CW tested")
        if interactions.get("call_wall_broken"): flags.append("CW broken")
        if interactions.get("put_wall_tested"): flags.append("PW tested")
        if interactions.get("put_wall_broken"): flags.append("PW broken")
        if interactions.get("em_upper_tested"): flags.append("EM+ tested")
        if interactions.get("em_upper_broken"): flags.append("EM+ broken")
        if interactions.get("em_lower_tested"): flags.append("EM- tested")
        if interactions.get("em_lower_broken"): flags.append("EM- broken")

        return {
            "ticker": t.get("ticker"),
            "spot": today.get("open"),
            "change_pct": today.get("change_pct"),
            "range_pct": today.get("range_pct"),
            "regime": regime.get("current_regime"),
            "regime_changed": regime.get("regime_changed"),
            "bias": anchor.get("mandated_track", ""),
            "call_wall": anchor.get("call_wall"),
            "put_wall": anchor.get("put_wall"),
            "em_upper": anchor.get("today_em_upper"),
            "em_lower": anchor.get("today_em_lower"),
            "bullish_inv": inv.get("bullish_invalidation"),
            "bearish_inv": inv.get("bearish_invalidation"),
            "level_flags": ", ".join(flags) if flags else "none",
        }

    compact: dict[str, Any] = {
        "date": briefing_data.get("meta", {}).get("date", ""),
        "events": events,
    }
    for ticker in tickers:
        compact[ticker] = _compact_ticker(all_data.get(ticker))

    return _json.dumps(compact, indent=2, ensure_ascii=False)


def build_compact_eod(briefing_data: dict, tickers: list[str] | None = None) -> str:
    """Build a compact EOD briefing for the LLM.

    The EOD narrative needs to grade the morning's trades against today's
    price action. It needs: regime, today's OHLC, level interactions, and
    the key levels. It does NOT need: weekly_progress, track_assessment,
    institutional_volatility_context, or SPX (redundant with SPY).

    Saves ~600 tokens vs raw TOON by dropping SPX and stripping review-only fields.
    """
    import json as _json

    if tickers is None:
        tickers = ["NQ1", "ES1"]

    all_data = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
    events = briefing_data.get("economic_events", [])

    def _compact_eod_ticker(t: dict) -> dict:
        if not t:
            return {}
        today = t.get("today", {})
        anchor = t.get("weekly_anchor", {})
        regime = t.get("regime_check", {})
        interactions = t.get("level_interactions", {})

        flags = []
        if interactions.get("call_wall_tested"): flags.append("CW tested")
        if interactions.get("call_wall_broken"): flags.append("CW broken")
        if interactions.get("put_wall_tested"): flags.append("PW tested")
        if interactions.get("put_wall_broken"): flags.append("PW broken")
        if interactions.get("em_upper_tested"): flags.append("EM+ tested")
        if interactions.get("em_upper_broken"): flags.append("EM+ broken")
        if interactions.get("em_lower_tested"): flags.append("EM- tested")
        if interactions.get("em_lower_broken"): flags.append("EM- broken")

        return {
            "ticker": t.get("ticker"),
            "open": today.get("open"),
            "high": today.get("high"),
            "low": today.get("low"),
            "close": today.get("close"),
            "change_pct": today.get("change_pct"),
            "range_pct": today.get("range_pct"),
            "regime": regime.get("current_regime"),
            "call_wall": anchor.get("call_wall"),
            "put_wall": anchor.get("put_wall"),
            "em_upper": anchor.get("today_em_upper"),
            "em_lower": anchor.get("today_em_lower"),
            "level_flags": ", ".join(flags) if flags else "none",
        }

    compact: dict[str, Any] = {
        "date": briefing_data.get("meta", {}).get("date", ""),
        "events": events,
    }
    for ticker in tickers:
        compact[ticker] = _compact_eod_ticker(all_data.get(ticker))

    return _json.dumps(compact, indent=2, ensure_ascii=False)


# ── Trader Narrative Layer (v1: Open mode) ────────────────────────
# Pre-digests overnight price action, intermarket reads, GEX structure,
# ALN/classification, calendar, and prior EOD plan into a compact
# "cheat sheet" (~800-1200 tokens) for the LLM to write a narrative.
# See docs/architecture/TRADER_NARRATIVE_PLAN.md for the full design.

# Globex session window for overnight context (ET).
# 18:00 prior day → 08:30 current day (RTH open).
_GLOBEX_START_HOUR = 18
_GLOBEX_END_HOUR = 8
_GLOBEX_END_MIN = 30


def _extract_gex_levels(unified_entry: dict, ticker: str) -> dict:
    """Extract call_wall, put_wall, zero_gamma, gamma_magnet, flip, regime
    from a unified_levels entry (JSON or TXT-parsed).

    Returns a dict with futures-translated levels when a FUTURES_RATIO is
    present (SPY/QQQ proxy → MES/MNQ scale).
    """
    if not unified_entry:
        return {}

    meta = parse_meta_fields(unified_entry)
    ratio = meta.get("FUTURES_RATIO", 0)
    basis = meta.get("FUTURES_BASIS", 0)

    levels: dict[str, float] = {}
    for t in unified_entry.get("tokens", []):
        label = (t.get("label") or "").upper()
        strike = t.get("strike", 0)
        if not strike:
            continue
        if "CW" in label and "call_wall" not in levels:
            levels["call_wall"] = strike
        elif "PW" in label and "put_wall" not in levels:
            levels["put_wall"] = strike
        elif "ZERO GEX DA" in label and "zero_gamma_da" not in levels:
            levels["zero_gamma_da"] = strike
        elif "ZERO GEX" in label and "zero_gamma" not in levels:
            levels["zero_gamma"] = strike
        elif "FLIP" in label and "flip" not in levels:
            levels["flip"] = strike
        elif "MAGNET" in label and "gamma_magnet" not in levels:
            levels["gamma_magnet"] = strike

    # Translate proxy → futures scale where applicable
    if ratio and ratio > 0 and ticker in {"SPY", "QQQ"}:
        for k, v in list(levels.items()):
            levels[k] = round(v * ratio + basis, 2)

    levels["regime"] = meta.get("REGIME", "")
    levels["bias"] = meta.get("BIAS", "")
    levels["gex_total"] = meta.get("GEX_TOTAL", 0)
    return levels


def build_overnight_context(
    loader: DataLoader | None = None,
    ticker: str = "NQ1",
    target_date: date | None = None,
) -> dict:
    """Pull 1m bars, filter to the Globex session (18:00 → 08:30 ET),
    compute OHLC + trajectory.

    Uses the fused data loader (live + historical) so current overnight
    bars are available. The `loader` arg is kept for API compatibility
    but is not used — the fused loader reads directly from disk.

    Returns a dict with:
      - open, high, low, close (session OHLC)
      - session_high_time, session_low_time (ET HH:MM)
      - change_pct (close vs session open)
      - trajectory (plain-English description)
      - prior_close (last RTH close before globex)

    ADR-017: fully vectorized Pandas, no loops in calculation paths.
    """
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
    except Exception as e:
        log.warning("[overnight] Could not load fused data for %s: %s", ticker, e)
        return {}

    if df_1m is None or df_1m.empty:
        return {}

    if df_1m.index.tz is None:
        # Fused loader returns naive UTC index. Localize to UTC, then convert to ET.
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert(ET)
    else:
        df_1m.index = df_1m.index.tz_convert(ET)

    if target_date is None:
        now_et = datetime.now(ET)
        target_date = now_et.date()
        if now_et.hour >= 18:
            target_date = target_date + timedelta(days=1)
            while target_date.weekday() in (5, 6):
                target_date += timedelta(days=1)
        elif now_et.weekday() in (5, 6):
            while target_date.weekday() in (5, 6):
                target_date -= timedelta(days=1)

    # Globex starts prior evening. Build the globex window: prior day 18:00 → target day 08:30.
    globex_start = datetime.combine(target_date - timedelta(days=1), datetime.min.time(), tzinfo=ET).replace(hour=_GLOBEX_START_HOUR)
    globex_end = datetime.combine(target_date, datetime.min.time(), tzinfo=ET).replace(hour=_GLOBEX_END_HOUR, minute=_GLOBEX_END_MIN)

    mask = (df_1m.index >= globex_start) & (df_1m.index < globex_end)
    globex = df_1m.loc[mask]
    if globex.empty:
        # Fallback: try the most recent 14h of data
        globex = df_1m.iloc[-840:] if len(df_1m) >= 840 else df_1m
        if globex.empty:
            return {}

    session_open = float(globex["open"].iloc[0])
    session_high = float(globex["high"].max())
    session_low = float(globex["low"].min())
    session_close = float(globex["close"].iloc[-1])
    change_pct = round((session_close / session_open - 1) * 100, 2) if session_open > 0 else 0.0

    # High/low times (vectorized idxmin/idxmax)
    high_time = globex["high"].idxmax()
    low_time = globex["low"].idxmin()
    high_time_str = high_time.strftime("%H:%M ET") if high_time else "N/A"
    low_time_str = low_time.strftime("%H:%M ET") if low_time else "N/A"

    # Trajectory: compare first half vs second half close, and high/low ordering
    mid_idx = len(globex) // 2
    first_half_close = float(globex["close"].iloc[mid_idx]) if mid_idx > 0 else session_open
    second_half_close = session_close
    high_first = high_time is not None and high_time.hour < (_GLOBEX_END_HOUR + 12) % 24

    trajectory_parts: list[str] = []
    if session_close < session_open:
        trajectory_parts.append("Sold off from the open")
    elif session_close > session_open:
        trajectory_parts.append("Rallied from the open")
    else:
        trajectory_parts.append("Flat from the open")

    if second_half_close < first_half_close:
        trajectory_parts.append("weakened into the pre-dawn")
    elif second_half_close > first_half_close:
        trajectory_parts.append("firmed into the pre-dawn")

    # Where did the extreme print?
    if low_time is not None and low_time.hour < 6:
        trajectory_parts.append(f"bottomed at {low_time_str}")
    if high_time is not None and high_time.hour >= 18 or (high_time is not None and high_time.hour == 0):
        trajectory_parts.append(f"peaked early at {high_time_str}")

    # Prior RTH close (last bar before 18:00 prior day)
    prior_close_mask = df_1m.index < globex_start
    prior_close_df = df_1m.loc[prior_close_mask]
    prior_close = float(prior_close_df["close"].iloc[-1]) if not prior_close_df.empty else session_open

    # Prior day RTH high/low (09:30–16:00 ET of the previous trading day)
    # Used for RTH Breaks open-scenario classification (nqstats.com/rth_breaks.html)
    prior_rth_high, prior_rth_low = None, None
    for days_back in range(1, 6):
        rth_start = globex_start - timedelta(days=days_back)
        rth_start = rth_start.replace(hour=9, minute=30)
        rth_end = rth_start.replace(hour=16, minute=0)
        prior_rth_mask = (df_1m.index >= rth_start) & (df_1m.index < rth_end)
        prior_rth_df = df_1m.loc[prior_rth_mask]
        
        if not prior_rth_df.empty:
            prior_rth_high = float(prior_rth_df["high"].max())
            prior_rth_low = float(prior_rth_df["low"].min())
            break

    return {
        "ticker": ticker,
        "open": round(session_open, 2),
        "high": round(session_high, 2),
        "low": round(session_low, 2),
        "close": round(session_close, 2),
        "change_pct": change_pct,
        "session_high_time": high_time_str,
        "session_low_time": low_time_str,
        "trajectory": ", ".join(trajectory_parts),
        "prior_close": round(prior_close, 2),
        "prior_rth_high": round(prior_rth_high, 2) if prior_rth_high is not None else None,
        "prior_rth_low": round(prior_rth_low, 2) if prior_rth_low is not None else None,
    }


def _is_schwab_hub_reachable() -> bool:
    """Quick TCP-probe of the local Schwab hub proxy on port 8080.

    Returns True if something is listening on 127.0.0.1:8080 (the
    hub proxy that bridges this repo to the Schwab API). Used by
    `get_intermarket_quotes` to skip the Schwab auth + quote path
    when the hub is down — without this probe, every premarket /
    open run logs a `ConnectionRefusedError` traceback when the
    hub is offline (audit §2.5).
    """
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 8080), timeout=0.25):
            return True
    except OSError:
        return False


def get_intermarket_quotes() -> dict:
    """Fetch live quotes for Brent Crude, 10Y Yield, DXY, VIX, and VVIX.
    Prefers Schwab API, falls back to yfinance.

    Failure handling (audit §2.5):
      - The Schwab auth + quote path is skipped entirely if the
        local hub proxy on port 8080 is unreachable. This avoids
        `ConnectionRefusedError` tracebacks cluttering the console
        when the hub is down.
      - If the hub is reachable but the auth or a single quote
        call fails, we log a single debug line and continue with
        the yfinance fallback. We deliberately do NOT include a
        traceback (no `exc_info=True`) — the LLM downstream is
        tolerant of missing prices, so the noise-to-signal ratio
        of a full traceback is wrong.
    """
    quotes = {
        "brent": {"price": None, "change": None},
        "tnx": {"price": None, "change": None},
        "dxy": {"price": None, "change": None},
        "vix": {"price": None, "change": None},
        "vvix": {"price": None, "change": None},
    }

    # Probe the hub once; bail to the yfinance fallback if it's
    # offline. Avoids `ConnectionRefusedError` tracebacks when the
    # operator simply hasn't started the hub today.
    if not _is_schwab_hub_reachable():
        log.debug("[intermarket] Schwab hub (127.0.0.1:8080) not reachable — using yfinance fallback")
    else:
        # Schwab fetch
        client = None
        try:
            from schwab.auth import easy_client
            import json
            secrets_path = REPO_ROOT / "secrets.json"
            token_path = REPO_ROOT / "token.json"
            if secrets_path.exists() and token_path.exists():
                with open(secrets_path, "r") as f:
                    secrets = json.load(f)
                client = easy_client(
                    api_key=secrets["app_key"],
                    app_secret=secrets["app_secret"],
                    callback_url='https://127.0.0.1:8182',
                    token_path=str(token_path),
                    enforce_enums=False
                )
        except Exception as e:
            log.debug("[intermarket] Schwab auth failed: %s", e)
            client = None

        # We only know Schwab tickers for VIX/VVIX that work well with get_quote currently
        schwab_map = {"vix": "$VIX", "vvix": "$VVIX"}
        if client:
            for key, sym in schwab_map.items():
                try:
                    resp = client.get_quote(sym)
                    if resp.status_code == 200:
                        data = resp.json()
                        if sym in data:
                            q = data[sym].get("quote", {})
                            if "lastPrice" in q:
                                quotes[key]["price"] = q["lastPrice"]
                                quotes[key]["change"] = q.get("netChange", 0.0)
                except Exception as e:
                    log.debug("[intermarket] Schwab quote %s failed: %s", sym, e)

    # Fallback to yfinance for missing
    yf_map = {
        "brent": "BZ=F",
        "tnx": "^TNX",
        "dxy": "DX-Y.NYB",
        "vix": "^VIX",
        "vvix": "^VVIX"
    }
    try:
        import yfinance as yf
        for key, sym in yf_map.items():
            if quotes[key]["price"] is None:
                try:
                    ticker = yf.Ticker(sym)
                    fi = ticker.fast_info
                    quotes[key]["price"] = round(fi.last_price, 2)
                    quotes[key]["change"] = round(fi.last_price - (fi.previous_close or fi.last_price), 2)
                except Exception as e:
                    log.debug("[intermarket] yfinance %s failed: %s", sym, e)
    except Exception as e:
        log.debug("[intermarket] yfinance module unavailable: %s", e)

    return quotes


def build_intermarket_read(
    nq_ctx: dict,
    es_ctx: dict,
    vix_ctx: dict | None = None,
    quotes: dict | None = None,
) -> str:
    """Compare NQ/ES/VIX overnight moves. Detect divergence.

    Returns a plain-English intermarket read string (pre-computed so the
    LLM doesn't have to do the comparison).
    """
    if not nq_ctx or not es_ctx:
        return "Insufficient data for intermarket read."

    nq_chg = nq_ctx.get("change_pct", 0)
    es_chg = es_ctx.get("change_pct", 0)
    vix_chg = 0.0
    vix_note = ""
    if vix_ctx:
        vix_close = vix_ctx.get("close", 0)
        vix_prev = vix_ctx.get("prior_close", vix_close)
        if vix_prev > 0:
            vix_chg = round((vix_close / vix_prev - 1) * 100, 2)

    parts: list[str] = []

    has_valid_quotes = quotes and any(data.get("price") is not None for data in quotes.values())
    if has_valid_quotes:
        parts.append("| Asset | Last Price | Change |")
        parts.append("|---|---|---|")
        for asset, data in quotes.items():
            price = f"{data['price']:.2f}" if data['price'] is not None else "N/A"
            change = f"{data['change']:+.2f}" if data['change'] is not None else "N/A"
            parts.append(f"| {asset.upper()} | {price} | {change} |")
        parts.append("")
        parts.append("**Divergence Analysis:**")

    # Direction comparison
    nq_down = nq_chg < -0.1
    nq_up = nq_chg > 0.1
    es_down = es_chg < -0.1
    es_up = es_chg > 0.1

    if nq_down and not es_down:
        parts.append(
            f"NQ is leading the downside ({nq_chg}%) but ES is not following ({es_chg}%)."
        )
        if vix_ctx and abs(vix_chg) < 1.0:
            parts.append("VIX is flat — this looks like NQ-specific weakness (tech rotation), not a broad risk-off.")
            parts.append("The flush in NQ overnight may be an overshoot since ES and VIX aren't confirming.")
        else:
            parts.append("This is NQ-specific weakness, not a broad risk-off move.")
    elif nq_up and not es_up:
        parts.append(
            f"NQ is leading the upside ({nq_chg}%) but ES is lagging ({es_chg}%)."
        )
        parts.append("Tech is leading; broad market participation is missing.")
    elif es_down and not nq_down:
        parts.append(
            f"ES is leading the downside ({es_chg}%) but NQ is holding ({nq_chg}%)."
        )
        parts.append("This is a broad-market / rates-driven move, not tech-specific.")
    elif es_up and not nq_up:
        parts.append(
            f"ES is leading the upside ({es_chg}%) but NQ is lagging ({nq_chg}%)."
        )
        parts.append("Breadth-led rally; tech is not participating yet.")
    elif nq_down and es_down:
        parts.append(
            f"Both NQ ({nq_chg}%) and ES ({es_chg}%) are down overnight — broad risk-off."
        )
        if vix_ctx and vix_chg > 2.0:
            parts.append(f"VIX is up {vix_chg}% — fear is rising. This is a real risk-off, not an overshoot.")
    elif nq_up and es_up:
        parts.append(
            f"Both NQ ({nq_chg}%) and ES ({es_chg}%) are up overnight — broad bid."
        )
        if vix_ctx and vix_chg < -2.0:
            parts.append(f"VIX is down {vix_chg}% — fear is fading. Risk-on.")
    else:
        parts.append(
            f"NQ ({nq_chg}%) and ES ({es_chg}%) are both flat overnight — no directional signal."
        )

    if vix_ctx:
        vix_note = f" VIX: {vix_ctx.get('close', 'N/A')} (prev {vix_ctx.get('prior_close', 'N/A')}, {vix_chg}%)."
    return " ".join(parts) + vix_note


def get_vix_checkpoint(loader: DataLoader | None = None) -> dict:
    """Check if VIX 1m parquet exists. If yes, use intraday VIX. If no,
    fall back to daily close from the friction matrix.

    Returns a dict with:
      - close: latest VIX close
      - prior_close: previous VIX close (for overnight change)
      - source: "1m_parquet" | "friction_matrix" | "unavailable"
    """
    # Try 1m parquet first (via DataLoader)
    if loader is not None:
        try:
            df_vix = loader.load_price("VIX")
            if df_vix is not None and not df_vix.empty:
                close = float(df_vix["close"].iloc[-1])
                prior_close = float(df_vix["close"].iloc[-2]) if len(df_vix) >= 2 else close
                return {
                    "close": round(close, 2),
                    "prior_close": round(prior_close, 2),
                    "source": "1m_parquet",
                }
        except Exception as e:
            log.debug("[vix_checkpoint] 1m parquet unavailable: %s", e)

    # Fallback: daily close from friction matrix
    try:
        friction_path = REPO_ROOT / "data" / "derived" / "market_friction_matrix.parquet"
        if friction_path.exists():
            friction_df = pd.read_parquet(str(friction_path))
            vix_rows = friction_df[friction_df.get("ticker", pd.Series(["SPY"])).eq("SPY")] if "ticker" in friction_df.columns else friction_df
            if not vix_rows.empty and "vix_close" in vix_rows.columns:
                vix_series = vix_rows["vix_close"].dropna()
                if len(vix_series) >= 2:
                    return {
                        "close": round(float(vix_series.iloc[-1]), 2),
                        "prior_close": round(float(vix_series.iloc[-2]), 2),
                        "source": "friction_matrix",
                    }
                elif len(vix_series) == 1:
                    return {
                        "close": round(float(vix_series.iloc[-1]), 2),
                        "prior_close": round(float(vix_series.iloc[-1]), 2),
                        "source": "friction_matrix",
                    }
    except Exception as e:
        log.warning("[vix_checkpoint] friction matrix fallback failed: %s", e)

    return {"close": None, "prior_close": None, "source": "unavailable"}


def _format_scheduled_risk_block(econ_releases: list[dict]) -> str:
    """Format scheduled economic releases highlighting conflicts."""
    if not econ_releases:
        return "== SCHEDULED RISK ==\nNo economic releases scheduled today."
    
    lines = ["== SCHEDULED RISK =="]
    impact_rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
    deduped: dict[tuple[str, str], dict] = {}

    for release in econ_releases:
        key = (str(release.get("time_et", "")), str(release.get("name", "")))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = release
            continue

        # Prefer the version that has a conflict flag, then higher impact.
        existing_score = (
            1 if existing.get("macro_window_conflict", False) else 0,
            impact_rank.get(str(existing.get("impact", "")).upper(), -1),
        )
        new_score = (
            1 if release.get("macro_window_conflict", False) else 0,
            impact_rank.get(str(release.get("impact", "")).upper(), -1),
        )
        if new_score > existing_score:
            deduped[key] = release

    # Sort conflicts first, then high impact, then time.
    sorted_releases = sorted(
        deduped.values(),
        key=lambda x: (
            0 if x.get("macro_window_conflict", False) else 1,
            -impact_rank.get(str(x.get("impact", "")).upper(), -1),
            str(x.get("time_et", "")),
            str(x.get("name", "")),
        ),
    )
    for r in sorted_releases:
        name = r["name"]
        impact = r["impact"]
        time_et = r["time_et"]
        conflict = r.get("macro_window_conflict", False)
        window_name = r.get("conflict_window", "")
        
        if conflict:
            lines.append(f"⚠ {time_et} [{impact}] {name} — CONFLICT with {window_name} window! (Action: Size Down / Avoid Entry)")
        else:
            lines.append(f"  {time_et} [{impact}] {name}")
    return "\n".join(lines)

def _format_earnings_block(earnings: list[dict]) -> str:
    """Format earnings catalysts ordered by weight."""
    if not earnings:
        return "== EARNINGS CATALYSTS ==\nNo relevant earnings releases."
    
    lines = ["== EARNINGS CATALYSTS =="]
    for e in earnings:
        ticker = e["ticker"]
        company = e["company"]
        cap_val = e["market_cap"]
        timing = e["session_timing"]
        critical = e.get("index_critical", False)
        weight = e.get("index_weight", 0.0)
        
        cap_str = f"${cap_val/1e9:.1f}B" if cap_val else "N/A"
        lbl = f" (Weight: {weight:.2%})" if critical else ""
        
        if timing in ("AMC_YESTERDAY", "BMO_TODAY"):
            last = e.get("last_price")
            source = e.get("quote_source", "unknown")
            move_pct = e.get("premkt_move_pct", 0.0) * 100
            beyond = e.get("beyond_em", False)
            
            prov_str = " [Low Confidence]" if source == "yfinance_fallback" else ""
            move_str = f"Move: {move_pct:+.2f}%{prov_str}" if last is not None else "Price: N/A"
            em_str = " ⚠ BEYOND EM!" if beyond else ""
            
            lines.append(f"  {ticker} ({company}, Cap: {cap_str}){lbl} | Timing: {timing} | {move_str}{em_str}")
        else:
            lines.append(f"  {ticker} ({company}, Cap: {cap_str}){lbl} | Timing: {timing} (Afternoon Volatility Risk — Size Down)")
    return "\n".join(lines)

def _format_news_block(headlines: list[dict]) -> str:
    """Format news headlines block."""
    if not headlines:
        return "== OVERNIGHT NEWS HEADLINES ==\nNo high-impact headlines found."
    
    lines = ["== OVERNIGHT NEWS HEADLINES =="]
    for h in headlines:
        score = h.get("score", 0.0)
        lines.append(f"  - {h['title']} (Score: {score:.1f})")
    return "\n".join(lines)

def _format_caution_score_block(caution: dict) -> str:
    """Format caution score block."""
    lines = ["== CAUTION SCORE =="]
    lines.append(f"Caution Score: {caution['score']}/100 | Risk Posture: {caution['posture']}")
    if caution["reasons"]:
        lines.append("Reasons:")
        for r in caution["reasons"]:
            lines.append(f"  - {r}")
    return "\n".join(lines)


def _format_gex_block(ticker_label: str, levels: dict, spot: float) -> str:
    """Format GEX structure into the cheat-sheet block."""
    if not levels:
        return f"== GEX STRUCTURE ({ticker_label}) ==\nNo GEX data available."

    def _dist_from_spot(level: float | None) -> str:
        if not level or not spot or spot == 0:
            return "N/A"
        pts = level - spot
        pct = (level / spot - 1) * 100
        sign = "+" if pts > 0 else ""
        return f"{sign}{pts:,.2f} pts / {sign}{pct:.2f}%"

    lines = [f"== GEX STRUCTURE ({ticker_label}) =="]
    cw = levels.get("call_wall")
    pw = levels.get("put_wall")
    flip = levels.get("flip") or levels.get("zero_gamma")
    magnet = levels.get("gamma_magnet")
    regime = levels.get("regime", "N/A")
    bias = levels.get("bias", "N/A")

    if cw:
        desc = "overhead resistance" if (spot and cw > spot) else "breached (below spot support)"
        lines.append(f"Upside Ceiling (Call Wall): {cw:,.2f} ({_dist_from_spot(cw)} from spot) — {desc}")
    if pw:
        desc = "below/at current price (support)" if (spot and pw <= spot) else "breached (overhead resistance)"
        lines.append(f"Downside Floor (Put Wall): {pw:,.2f} ({_dist_from_spot(pw)} from spot) — {desc}")
    if flip:
        pos = "above" if (spot and spot > flip) else "below"
        lines.append(f"Volatility Pivot (Gamma Flip): {flip:,.2f} — we're {pos} it ({'positive' if (spot and spot > flip) else 'negative'} gamma, {'pinning' if (spot and spot > flip) else 'amplification'} regime)")
    if magnet:
        lines.append(f"Price Magnet (Gamma Magnet): {magnet:,.2f} — pulling price toward it")
    lines.append(f"Regime: {regime} | Bias: {bias}")
    return "\n".join(lines)


def _format_aln_block(ticker_label: str, aln_data: dict, spot: float) -> str:
    """Format ALN/session pattern data into the cheat-sheet block."""
    if not aln_data:
        return f"== ALN / SESSION PATTERNS ({ticker_label}) ==\nNo ALN data available."

    aln = aln_data.get("aln", "N/A")
    bias = aln_data.get("bias", "N/A")
    conviction = aln_data.get("conviction", "N/A")
    reasoning = aln_data.get("reasoning", "")
    broken = aln_data.get("broken", "N/A")
    levels = aln_data.get("levels", {}) or {}
    primary_target = aln_data.get("primary_target", "NONE")
    primary_target_pct = aln_data.get("primary_target_pct", 0.0)
    break_high_pct = aln_data.get("break_high_pct", 0.0)
    break_low_pct = aln_data.get("break_low_pct", 0.0)
    edge_spent = aln_data.get("edge_spent", False)
    edge_spent_note = aln_data.get("edge_spent_note", "")

    # Expand the 4-letter ALN code into its full name + definition for the LLM
    from scripts.libs_py.nqstats.classifiers import aln_full_string
    import math
    aln_display = aln_full_string(aln) if aln != "N/A" else aln
    lh_raw = levels.get("lh")
    ll_raw = levels.get("ll")
    mid_raw = levels.get("mid")
    lh = float(lh_raw) if lh_raw is not None and pd.notna(lh_raw) and not math.isnan(float(lh_raw)) else None
    ll = float(ll_raw) if ll_raw is not None and pd.notna(ll_raw) and not math.isnan(float(ll_raw)) else None
    mid = float(mid_raw) if mid_raw is not None and pd.notna(mid_raw) and not math.isnan(float(mid_raw)) else None
    ib_bias = aln_data.get("ib_bias", "N/A")
    ib_conviction = aln_data.get("ib_conviction", 0)
    p12 = aln_data.get("p12")

    lines = [f"== ALN / SESSION PATTERNS ({ticker_label}) =="]
    lines.append(f"Pattern: {aln} → {aln_display}")
    lines.append(f"Broken: {broken}")
    if lh is not None and ll is not None:
        lines.append(f"London High: {lh:,.2f} | London Low: {ll:,.2f} | Mid: {mid:,.2f}" if mid is not None else f"London High: {lh:,.2f} | London Low: {ll:,.2f}")
    if p12 and pd.notna(p12) and not math.isnan(float(p12)):
        lines.append(f"Prior Close (P12): {float(p12):,.2f}")
    # Pre-computed break probabilities (LLM should trust these, not re-derive)
    if break_high_pct or break_low_pct:
        lines.append(f"NY Break Probabilities: London High {break_high_pct:.1f}% | London Low {break_low_pct:.1f}%")
    if primary_target != "NONE" and primary_target_pct:
        _target_label = "London High" if primary_target == "LONDON_HIGH" else "London Low"
        lines.append(f"Primary Target: {_target_label} ({primary_target_pct:.1f}% probability)")
    if ib_bias and ib_bias != "N/A":
        lines.append(f"IB Bias: {ib_bias} ({float(ib_conviction)*100:.0f}% conviction)")
    lines.append(f"Bias: {bias} ({conviction})")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
    if edge_spent and edge_spent_note:
        lines.append(f"EDGE SPENT: {edge_spent_note}")

    return "\n".join(lines)


def _format_classification_block(ticker_label: str, class_data: dict) -> str:
    """Format daily classification data into the cheat-sheet block."""
    if not class_data:
        return f"== CLASSIFICATION ({ticker_label}) ==\nNo classification data available."

    prior_type = class_data.get("prior_type", "N/A")
    overnight_key = class_data.get("overnight_key", "N/A")
    seq_probs = class_data.get("sequential_probs", {}) or {}
    over_probs = class_data.get("overnight_probs", {}) or {}
    most_likely = class_data.get("most_likely", "N/A")

    # Expand day-type abbreviations for the LLM (source: docs/DailyClassification/DAILY_CLASSIFICATION.md)
    _DAY_TYPE_NAMES = {
        "R1": "Range 1 — Time Spent (price stays in/retests Opening Range; neutral, rotational)",
        "R2": "Range 2 — Reversal (failed expansion: breaks OR, fails, returns after 11:00)",
        "DWP": "Directional With Pullbacks (trend breaks OR, never returns, but has structural retracements)",
        "DNP": "Directional No Pullback (power trend, breaks OR, no structural retracements)",
    }
    def _expand_dt(abbr: str) -> str:
        return f"{abbr} ({_DAY_TYPE_NAMES.get(abbr, '?')})" if abbr and abbr != "N/A" else abbr

    lines = [f"== CLASSIFICATION ({ticker_label}) =="]
    lines.append(f"Yesterday: {_expand_dt(prior_type)}")
    lines.append(f"Overnight Key: {overnight_key}")
    if seq_probs:
        lines.append("Sequential: " + " | ".join(f"{_expand_dt(k)}: {v}%" for k, v in seq_probs.items()))
    if over_probs:
        lines.append("Overnight: " + " | ".join(f"{_expand_dt(k)}: {v}%" for k, v in over_probs.items()))
    lines.append(f"Most Likely Today: {_expand_dt(most_likely)}")
    return "\n".join(lines)


def _format_key_levels_hierarchy(
    ticker_label: str,
    levels: dict,
    aln_data: dict,
    spot: float,
) -> str:
    """Merge all level sources and sort into overhead/support ladder."""
    import math
    overhead: list[tuple[float, str]] = []
    support: list[tuple[float, str]] = []

    def _add(level: float | None, label: str, spot: float):
        if level is None or pd.isna(level) or spot is None or pd.isna(spot):
            return
        try:
            flvl = float(level)
            fspot = float(spot)
        except (ValueError, TypeError):
            return
        if math.isnan(flvl) or math.isnan(fspot) or flvl <= 0 or fspot <= 0:
            return
        if flvl > fspot:
            overhead.append((flvl, label))
        else:
            support.append((flvl, label))

    if levels:
        _add(levels.get("call_wall"), f"{ticker_label} Call Wall", spot)
        _add(levels.get("flip"), f"{ticker_label} Gamma Flip", spot)
        _add(levels.get("put_wall"), f"{ticker_label} Put Wall", spot)
        _add(levels.get("gamma_magnet"), f"{ticker_label} Magnet", spot)
    if aln_data:
        lvls = aln_data.get("levels", {}) or {}
        _add(lvls.get("lh"), "London High", spot)
        _add(lvls.get("ll"), "London Low", spot)

    overhead.sort(key=lambda x: x[0])
    support.sort(key=lambda x: x[0], reverse=True)

    lines = [f"== GEX & ICT STRUCTURAL LEVELS ({ticker_label}) =="]
    if overhead:
        lines.append("Overhead: " + " → ".join(f"{px:,.2f} ({lbl})" for px, lbl in overhead))
    if support:
        lines.append("Support: " + " → ".join(f"{px:,.2f} ({lbl})" for px, lbl in support))
    if not overhead and not support:
        lines.append("No key levels available.")
    return "\n".join(lines)


# ── Signal block formatters (Phase D) ──────────────────────────────

def _format_volatility_block(vv: dict) -> str:
    """Format VIX/VVIX regime + divergence into cheat-sheet block."""
    if not vv or vv.get("vix_regime") == "unknown":
        return "== VOLATILITY REGIME ==\nVIX/VVIX data unavailable"
    lines = ["== VOLATILITY REGIME =="]
    lines.append(f"VIX: {vv['vix_close']} [{vv['vix_regime'].upper()}] | VVIX: {vv['vvix_close']} [{vv['vvix_regime'].upper()}]")
    lines.append(f"VVIX overnight: {vv['vvix_chg']:+.1f}% → {vv['vvix_roc_regime'].replace('_',' ')}")
    lines.append(f"Divergence: {vv['divergence_read'].replace('_',' ')}")
    lines.append(f"Sizing: {vv['sizing_multiplier']:.0%}")
    return "\n".join(lines)


def _format_ict_block(ticker_label: str, ict: dict, spot: float) -> str:
    """Format ICT dealing range into cheat-sheet block."""
    if not ict or not ict.get("pdh"):
        return f"== ICT DEALING RANGE ({ticker_label}) ==\nICT data unavailable"
    lines = [f"== ICT DEALING RANGE ({ticker_label}) =="]
    lines.append(f"PDH: {ict['pdh']:,.2f} | PDL: {ict['pdl']:,.2f} | Midnight: {ict.get('midnight_open') or 'N/A'}")
    lines.append(f"Price in {ict.get('premium_discount','unknown')} ({ict.get('dealing_range_pct','?')}% of range)")
    if ict.get("bsl_target"):
        lines.append(f"BSL: {ict['bsl_target']:,.2f} | SSL: {ict['ssl_target']:,.2f}")
    return "\n".join(lines)


def _format_candle_science_block(ticker_label: str, cs: dict) -> str:
    """Format Candle Science C1→C2→C3 into cheat-sheet block."""
    if not cs or cs.get("n_matches", 0) == 0:
        return f"== CANDLE SCIENCE ({ticker_label}) ==\nNo pattern match available"
    lines = [f"== CANDLE SCIENCE ({ticker_label}) =="]
    lines.append(
        f"C1: {cs['c1_dir']} | C2: {cs['c2_dir']} | preset={cs.get('preset', '?')} "
        f"(n={cs['n_matches']}, edge={cs['edge']}%)"
    )
    lines.append(f"P(C3 Bull): {cs['p_bull']}% | P(C3 Bear): {cs['p_bear']}%")
    if cs.get("p_break_high") is not None or cs.get("p_break_low") is not None:
        lines.append(
            f"P(C3H>C2H): {cs.get('p_break_high', '?')}% | "
            f"P(C3L<C2L): {cs.get('p_break_low', '?')}% | "
            f"P(C3C>C2C): {cs.get('p_close_gt_c2c', '?')}%"
        )
    mfe = cs.get("mfe", {})
    mae = cs.get("mae", {})
    if mfe or mae:
        mfe_str = " ".join(f"{k}={v:+.2f}%" for k, v in mfe.items()) if mfe else "—"
        mae_str = " ".join(f"{k}={v:+.2f}%" for k, v in mae.items()) if mae else "—"
        rr = cs.get("rr_envelope")
        rr_str = f" | R:R={rr}x" if rr else ""
        lines.append(f"MFE: {mfe_str}")
        lines.append(f"MAE: {mae_str}{rr_str}")
    return "\n".join(lines)


def _format_confluence_block(ticker_label: str, conf: dict) -> str:
    """Format confluence assessment into cheat-sheet block."""
    if not conf:
        return f"== CONFLUENCE ({ticker_label}) ==\nNo confluence data"
    lines = [f"== CONFLUENCE ({ticker_label}) =="]
    lines.append(f"Signal 1 (Overnight): {conf.get('overnight_signal','?')}")
    lines.append(f"Signal 2 (RTH Open): {conf.get('rth_open_signal','?')}")
    lines.append(f"Signal 3 (Daily Chart): {conf.get('daily_chart_signal','?')}")
    lines.append(f"Confluence: {conf.get('confluence','?')} | Sizing: {conf.get('sizing',1.0):.0%}")
    lines.append(f"Note: {conf.get('conviction_note','')}")
    return "\n".join(lines)


def _format_rth_break_block(ticker_label: str, rth_data: dict) -> str:
    """Format RTH break scenario into cheat-sheet block (pre-computed for LLM)."""
    if not rth_data:
        return f"== RTH BREAK SCENARIO ({ticker_label}) ==\nNo RTH data"
    lines = [f"== RTH BREAK SCENARIO ({ticker_label}) =="]
    lines.append(f"Scenario: {rth_data.get('label', 'N/A')}")
    bias = rth_data.get("bias", "NEUTRAL")
    hold_pct = rth_data.get("hold_pct", 0.0)
    if hold_pct:
        lines.append(f"Bias: {bias} ({hold_pct:.1f}% chance close holds)")
    else:
        lines.append(f"Bias: {bias}")
    if rth_data.get("no_reach_opposite_pct"):
        lines.append(f"Opposite reach risk: {100 - rth_data['no_reach_opposite_pct']:.1f}% chance of reaching opposite pRTH")
    lines.append(f"Read: {rth_data.get('read', 'N/A')}")
    return "\n".join(lines)


def _format_day_type_block(dt: dict) -> str:
    """Format day type + killzones into cheat-sheet block."""
    if not dt:
        return "== DAY TYPE ==\nNo day type data"
    lines = ["== DAY TYPE =="]
    lines.append(f"Type: {dt.get('day_type','clean').upper()} | Sizing: {dt.get('sizing_multiplier',1.0):.0%}")
    if dt.get("events_today"):
        lines.append("Events: " + ", ".join(f"{e.get('time_et','?')} {e.get('name','?')}" for e in dt["events_today"]))
    if dt.get("guidance"):
        lines.append(f"Guidance: {dt['guidance']}")
    return "\n".join(lines)


def _format_weekly_profile_block(ticker_label: str, wp: dict) -> str:
    """Format weekly profile into cheat-sheet block."""
    if not wp or not wp.get("week_high"):
        return f"== WEEKLY PROFILE ({ticker_label}) ==\nNo weekly data"
    lines = [f"== WEEKLY PROFILE ({ticker_label}) =="]
    lines.append(f"HOW: {wp['week_high']:,.2f} ({wp.get('week_high_day','?')}) | LOW: {wp['week_low']:,.2f} ({wp.get('week_low_day','?')})")
    lines.append(f"Profile: {wp.get('profile_type','balanced').replace('_',' ')} | Position: {wp.get('current_position','?')}")
    lines.append(f"Day context: {wp.get('day_context','?')} | Alignment: {wp.get('alignment','?')}")
    return "\n".join(lines)


def _format_liquidity_map_block(lm: dict) -> str:
    """Format ICT liquidity raid map into cheat-sheet block."""
    if not lm or lm.get("raid_target") == "unknown":
        return "== ICT LIQUIDITY MAP ==\nNo liquidity data"
    lines = ["== ICT LIQUIDITY MAP =="]
    lines.append(f"Bias: {lm.get('bias','?')} → Raid target: {lm.get('raid_target','?')}")
    if lm.get("raid_target_level"):
        lines.append(f"Target level: {lm['raid_target_level']:,.2f}")
    lines.append(f"Level equality: {lm.get('level_equality','?')} | Weekly: {lm.get('weekly_position','?')}")
    lines.append(f"Timing: {lm.get('entry_timing','?')}")
    return "\n".join(lines)


def _format_gex_regime_block(gr: dict) -> str:
    """Format GEX regime change into cheat-sheet block."""
    if not gr:
        return ""
    lines = ["== GEX REGIME CHANGE =="]
    lines.append(f"Regime: {gr.get('regime_change','stable')}")
    if gr.get("flip_crossed"):
        lines.append("Flip crossed — gamma regime changed")
    if gr.get("wall_moved"):
        lines.append(f"Wall moved: {gr['wall_moved']}")
    return "\n".join(lines)


def build_premarket_context(
    loader: DataLoader | None = None,
    nq_ticker: str = "NQ1",
    es_ticker: str = "ES1",
    target_date: date | None = None,
) -> str:
    """Build the premarket cheat sheet — runs before 09:30 ET open.

    Focuses on: overnight Globex action, GEX structure (live JSON),
    prior EOD classification, today's calendar. No RTH data.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=5)

    if target_date is None:
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            df_t = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
            target_date = get_latest_rth_date(df_t)
        except Exception:
            target_date = datetime.now(ET).date()

    sections: list[str] = []

    # ── Overnight context (NQ + ES) ──
    nq_ctx = build_overnight_context(loader, nq_ticker, target_date)
    es_ctx = build_overnight_context(loader, es_ticker, target_date)

    overnight_lines = ["== OVERNIGHT (Globex 18:00 → 08:30 ET) =="]
    for label, ctx in [("NQ", nq_ctx), ("ES", es_ctx)]:
        if not ctx:
            overnight_lines.append(f"{label}: No data available")
            continue
        overnight_lines.append(
            f"{label}: Open {ctx['open']:,.2f} → Current {ctx['close']:,.2f} ({ctx['change_pct']}%)"
        )
        overnight_lines.append(
            f"    Session Low: {ctx['low']:,.2f} at {ctx['session_low_time']} | Session High: {ctx['high']:,.2f} at {ctx['session_high_time']}"
        )
        overnight_lines.append(f"    Trajectory: {ctx['trajectory']}")
    sections.append("\n".join(overnight_lines))

    # ── GEX structure (NQ + ES) from live JSON ──
    unified = load_macro_levels(session="live")
    nq_unified = unified.get("NQ") or unified.get("QQQ") or {}
    es_unified = unified.get("ES") or unified.get("SPY") or {}

    nq_spot = nq_ctx.get("close", 0) or 0
    es_spot = es_ctx.get("close", 0) or 0

    nq_gex = _extract_gex_levels(nq_unified, "NQ" if "NQ" in unified else "QQQ")
    es_gex = _extract_gex_levels(es_unified, "ES" if "ES" in unified else "SPY")

    # GEX positioning verdict (session-aware — premarket uses prior close reference)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block as _fmt_gex
        sections.append(_fmt_gex(nq_spot, es_spot, nq_ticker, session="PREMARKET", target_date=target_date))
    except Exception as e:
        log.warning("[premarket] GEX positioning failed: %s", e)

    # ── Prior EOD classification ──
    try:
        import scripts.analysis.analyze_daily_classification_bias as class_module
        import sys as _sys
        _orig_argv = _sys.argv
        yesterday = target_date - timedelta(days=1)
        _sys.argv = ["analyze_daily_classification_bias.py", "--ticker", nq_ticker, "--date", yesterday.isoformat()]
        _, class_data = class_module.main()
        _sys.argv = _orig_argv
    except Exception as e:
        log.warning("[premarket] Classification analysis failed: %s", e)
        class_data = {}
    sections.append(_format_classification_block("NQ", class_data))

    # ── Econ Releases & Earnings ──
    async def run_async_signals():
        _ensure_database_url()
        from prisma import Prisma
        db = Prisma()
        await db.connect()
        try:
            from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
            broker = BrokerService()
            
            # Fetch econ events
            from scripts.trader.signals.econ_calendar import get_econ_releases
            econ_releases = await get_econ_releases(target_date, db)
            
            # Fetch earnings
            from scripts.trader.signals.earnings import fetch_earnings_events
            db_path = str(REPO_ROOT / "web" / "prisma" / "dev.db")
            earnings_list = await fetch_earnings_events(target_date, db_path, broker)
        finally:
            await db.disconnect()
        return econ_releases, earnings_list

    try:
        econ_releases, earnings_data = run_async_safely(run_async_signals())
    except Exception as e:
        log.warning("[premarket] Failed to fetch econ/earnings signals: %s", e)
        econ_releases, earnings_data = [], []

    # Fetch news
    from scripts.trader.utils.news_scraper import get_macro_headlines
    try:
        headlines = get_macro_headlines()
    except Exception as e:
        log.warning("[premarket] Failed to fetch headlines: %s", e)
        headlines = []

    # Calculate caution score
    from scripts.trader.signals.caution_score import calculate_caution_score
    try:
        caution_vix = get_vix_vvix_checkpoint()
        caution = calculate_caution_score(caution_vix, nq_ctx, es_ctx, econ_releases, earnings_data)
    except Exception as e:
        log.warning("[premarket] Failed to calculate caution score: %s", e)
        caution = {"score": 0, "posture": "UNKNOWN", "reasons": []}

    # Format blocks
    sections.append(_format_scheduled_risk_block(econ_releases))
    sections.append(_format_earnings_block(earnings_data))
    sections.append(_format_news_block(headlines))
    sections.append(_format_caution_score_block(caution))

    # ── Calendar & structural context (KB-distilled) ──
    # Queries the KB for event-specific ICT methodology (FOMC/CPI/NFP behavior,
    # OPEX patterns, Kish macro windows, post-news candle management) based on
    # today's calendar state. Falls back to plain day_type block if KB is down.
    _calendar_kb_ids: set[str] = set()
    try:
        _cal_block, _calendar_kb_ids = build_calendar_context_block(target_date, econ_releases)
        if _cal_block:
            sections.append(_cal_block)
            log.info("[premarket] Calendar context block appended (%d chars, %d KB units)",
                     len(_cal_block), len(_calendar_kb_ids))
    except Exception as e:
        log.warning("[premarket] Calendar context block failed: %s", e)
        # Fallback: plain day_type block
        try:
            dt = classify_day_type(econ_releases, target_date)
            sections.append(_format_day_type_block(dt))
        except Exception:
            pass

    # ── Weekly event timeline + ICT time map (premarket = full) ──
    try:
        _modifiers = get_weekly_modifiers(target_date, econ_releases)
        _timeline = build_weekly_event_timeline(target_date, econ_releases, _modifiers, mode="premarket")
        if _timeline:
            sections.append(_timeline)
        _dt = classify_day_type(econ_releases, target_date)
        _time_map = build_ict_time_map(_dt.get("day_type", "clean"), target_date, mode="premarket")
        if _time_map:
            sections.append(_time_map)
        _news_mgmt = build_post_news_management_block(_dt.get("day_type", "clean"))
        if _news_mgmt:
            sections.append(_news_mgmt)
    except Exception as e:
        log.warning("[premarket] Weekly timeline / time map failed: %s", e)

    # ── Weekly macro sentiment (curated config) ──
    # Loads scripts/config/weekly_macro_sentiment.yaml for the current ISO week.
    # Provides macro_theme + event_sentiment that the KB cannot (current-week
    # narrative). Skipped gracefully if file is missing or week not configured.
    try:
        _sentiment = load_weekly_macro_sentiment(target_date)
        if _sentiment:
            _sentiment_block = format_macro_sentiment_block(_sentiment)
            if _sentiment_block:
                sections.append(_sentiment_block)
                log.info("[premarket] Macro sentiment block appended")
    except Exception as e:
        log.warning("[premarket] Macro sentiment load failed: %s", e)

    # ICT feature blocks (KZ pivots from overnight, IPDA, gaps as magnets)
    try:
        from scripts.trader.signals.intraday_blocks import (
            _format_kz_pivots_block,
            _format_ipda_block,
            _format_silver_bullet_block,
            _format_macro_block,
            _format_gaps_block,
        )
        import pytz as _pytz
        now_et = datetime.now(_pytz.timezone("America/New_York"))
        sections.append(_format_kz_pivots_block(nq_ticker, nq_spot, "PREMARKET"))
        sections.append(_format_ipda_block(nq_ticker, nq_spot))
        sections.append(_format_silver_bullet_block(now_et))
        sections.append(_format_macro_block(now_et))
        sections.append(_format_gaps_block(nq_ticker, nq_spot))
    except Exception as e:
        log.warning("[premarket] ICT feature blocks failed: %s", e)

    # FTFC bias + SMA stance
    try:
        from scripts.trader.signals.intraday_blocks import _format_ftfc_block
        import pytz as _pytz2
        _now = datetime.now(_pytz2.timezone("America/New_York"))
        sections.append(_format_ftfc_block(nq_ticker, nq_spot, _now))
    except Exception as e:
        log.warning("[premarket] FTFC failed: %s", e)

    # Herman Pre-NY sweep — DOMINANT signal
    try:
        from scripts.libs_py.nqstats.classifiers import compute_herman_pre_ny_sweep
        from scripts.trader.signals.session_ranges import compute_all_session_ranges
        from scripts.utils.fused_data_loader import load_fused_data
        _df = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
        if _df is not None and not _df.empty:
            if _df.index.tz is None:
                _df.index = pd.DatetimeIndex(_df.index).tz_localize("UTC").tz_convert(ET)
            elif _df.index.tz != ET:
                _df.index = _df.index.tz_convert(ET)
            _sr = compute_all_session_ranges(_df, target_date, ET)
            _pre_ny = _sr.get("PRE_NY", {})
            _london = _sr.get("LONDON", {})
            if _pre_ny and _london:
                _sweep = compute_herman_pre_ny_sweep(_pre_ny, _london.get("high"), _london.get("low"))
                _lines = ["== HERMAN PRE-NY SWEEP (05:00-08:30) — DOMINANT =="]
                _lines.append(f"Result: {_sweep['label']}")
                _lines.append(f"Bias: {_sweep['bias']} ({_sweep['probability']:.1f}%)")
                if _sweep["dominant"]:
                    _lines.append("DOMINANT — overrides ALN. Do not fade.")
                else:
                    _lines.append("Not dominant — wait for 09:30 OR break.")
                _lines.append(f"Read: {_sweep['read']}")
                sections.append("\n".join(_lines))
    except Exception as e:
        log.warning("[premarket] Herman Pre-NY sweep failed: %s", e)

    # Delivery triad 1-liner
    try:
        from scripts.trader.signals.intraday_blocks import _format_delivery_triad_1liner
        _triad = _format_delivery_triad_1liner(nq_ticker, nq_spot, target_date)
        if _triad:
            sections.append(f"== DELIVERY TRIAD ==\n{_triad}")
    except Exception as e:
        log.warning("[premarket] Delivery triad failed: %s", e)

    # ── Knowledge Base context (ICT concept grounding) ──
    # Fetches grounded ICT source units from the KB API (port 8900) by
    # detecting concept triggers in the assembled cheat sheet. Degrades
    # gracefully (no block) if the KB API is unreachable.
    # Excludes units already retrieved by the calendar context block to avoid
    # duplication.
    try:
        from scripts.knowledge_bridge.kb_context import fetch_kb_context as _fetch_kb
        _kb_ctx = _fetch_kb("\n\n".join(sections), exclude_ids=_calendar_kb_ids or None)
        if _kb_ctx:
            sections.append(_kb_ctx)
            log.info("[premarket] KB context appended (%d chars, excluded %d calendar units)",
                     len(_kb_ctx), len(_calendar_kb_ids))
        else:
            log.debug("[premarket] KB context empty (API unreachable or no matches)")
    except Exception as e:
        log.warning("[premarket] KB context fetch failed: %s", e)

    return "\n\n".join(sections)


def get_weekly_modifiers(target_date: date, events: list[dict]) -> dict:
    """Compute week-level context like OpEx, Triple Witching, FOMC, Jackson Hole."""
    days_to_friday = 4 - target_date.weekday()
    friday = target_date + timedelta(days=days_to_friday)
    
    is_third_friday = 15 <= friday.day <= 21
    is_opex = is_third_friday
    is_triple_witching = is_third_friday and friday.month in [3, 6, 9, 12]
    
    # Scan all events for the week (not just today) for week-level flags
    # Only match US-specific event names — international releases like
    # "National Core CPI y/y" should NOT trigger CPI week classification
    week_event_names = " ".join((e.get("name") or "").upper() for e in events)

    # FOMC week should only be set for actual policy-decision week events,
    # not generic Fed speaker events (which can occur in any week).
    fomc_decision_markers = [
        "FOMC STATEMENT",
        "FOMC PRESS CONFERENCE",
        "FEDERAL FUNDS RATE",
        "FED FUNDS RATE",
        "INTEREST RATE DECISION",
        "MONETARY POLICY STATEMENT",
    ]
    is_fomc = any(marker in week_event_names for marker in fomc_decision_markers)
    # US CPI events: "CPI m/m", "CPI y/y", "Core CPI m/m", "Core CPI y/y"
    # but NOT "National Core CPI" (international) or "CPI q/q" (international quarterly)
    is_cpi_week = any(
        name in week_event_names
        for name in ["CPI M/M", "CPI Y/Y", "CORE CPI M/M", "CORE CPI Y/Y",
                     "CONSUMER PRICE INDEX", "CONSUMER PRICE M/M", "CONSUMER PRICE Y/Y"]
    )
    is_nfp_week = (
        "NFP" in week_event_names
        or "NON-FARM" in week_event_names
        or "NONFARM" in week_event_names
        or "NONFARM PAYROLLS" in week_event_names
    )
    is_jackson_hole = "JACKSON HOLE" in week_event_names
    has_treasury_auction = "TREASURY AUCTION" in week_event_names or "BOND AUCTION" in week_event_names
    
    return {
        "is_opex_week": is_opex,
        "is_triple_witching_week": is_triple_witching,
        "is_fomc_week": is_fomc,
        "is_cpi_week": is_cpi_week,
        "is_nfp_week": is_nfp_week,
        "is_jackson_hole_week": is_jackson_hole,
        "has_treasury_auction": has_treasury_auction,
    }


def build_calendar_context_block(
    target_date: date,
    econ_events: list[dict],
    weekly_modifiers: dict | None = None,
    archetype_info: dict | None = None,
) -> str:
    """Build a KB-distilled calendar & structural context block.

    Queries the KB for event-specific ICT methodology (FOMC/CPI/NFP/Jackson Hole
    behavior, OPEX week patterns, post-news candle management, Kish macro windows)
    and distills into a structured block for the LLM.

    Unlike the generic ``fetch_kb_context`` scan, this function constructs
    targeted queries based on today's calendar state — so the LLM gets
    event-specific ICT teachings rather than generic setup definitions.
    """
    from scripts.trader.signals.day_type import classify_day_type
    from scripts.knowledge_bridge.kb_context import fetch_kb_context_for_queries

    day_type_data = classify_day_type(econ_events, target_date)
    day_type = day_type_data.get("day_type", "clean")
    dow = target_date.strftime("%A")

    if weekly_modifiers is None:
        # Need the week's events for weekly modifiers — use today's events
        # as a proxy (caller should ideally pass the full week's events)
        weekly_modifiers = get_weekly_modifiers(target_date, econ_events)

    archetype = ""
    if archetype_info:
        archetype = archetype_info.get("archetype", "")

    # ── Build targeted KB queries based on calendar state ──
    queries: list[tuple[str, str]] = []

    # Event-specific behavior
    if day_type == "fomc":
        queries.append(("FOMC Day Behavior",
            "FOMC day accumulation manipulation distribution 2pm Powell statement trading"))
        queries.append(("FOMC Pre-PA",
            "FOMC pre-market weird morning session deliveries reference points"))
    elif day_type == "jackson_hole":
        queries.append(("Jackson Hole Behavior",
            "Jackson Hole Powell speech Friday central bank symposium high impact catalyst liquidity sweep"))
        queries.append(("Jackson Hole Pre-PA",
            "FOMC Powell speech pre-market anticipation strong ranges institutional order flow"))
    elif day_type == "cpi":
        queries.append(("CPI Day Behavior",
            "CPI 08:30 spike resolution Judas swing recovery entry post-news"))
        queries.append(("CPI Liquidity Raid",
            "CPI news liquidity raid Asian lows London lows buy side sell side sweep"))
    elif day_type == "nfp":
        queries.append(("NFP Day Behavior",
            "NFP 08:30 first direction fakeout Judas swing Silver Bullet 10am"))
        queries.append(("NFP Liquidity Raid",
            "NFP news buy side liquidity sweep expansion order block catalyst"))
    elif day_type == "special":
        # Check for Jackson Hole or treasury auction specifically
        event_names = " ".join((e.get("name") or "").upper() for e in econ_events)
        if "TREASURY" in event_names or "BOND AUCTION" in event_names:
            queries.append(("Treasury Auction",
                "treasury auction bond auction noon afternoon volatility speed lower"))
        else:
            queries.append(("Special Event",
                "high impact special event news release spike resolution trading"))

    # Weekly modifiers
    if weekly_modifiers.get("is_opex_week"):
        queries.append(("OPEX Week Pattern",
            "opex week Monday Tuesday run up Wednesday sell-off damage options expiration"))
    if weekly_modifiers.get("is_triple_witching_week"):
        queries.append(("Triple Witching",
            "triple witching quarterly expiration dealer hedging volatility position rollover"))
    if weekly_modifiers.get("is_jackson_hole_week"):
        queries.append(("Jackson Hole Week",
            "Jackson Hole Powell speech Friday central bank symposium high impact anticipation"))
    if weekly_modifiers.get("has_treasury_auction"):
        queries.append(("Treasury Auction Week",
            "treasury auction bond auction noon afternoon volatility trading"))

    # Kish macro windows (always include — they're the intraday timing framework)
    queries.append(("Kish Macro Windows",
        "Kish six intraday macros Price Discover Liquidity Hunt Offset Rebalance Launch Settlement"))

    # Post-news candle management (if any high-impact event today)
    if day_type in ("cpi", "nfp", "fomc", "jackson_hole", "special"):
        queries.append(("Post-News Candle Management",
            "post-news candle management wait M5 close first M1 candle unreliable recovery entry"))
        queries.append(("News Manipulation Windows",
            "manipulation window Judas swing 8:35 9:20 recovery 9:50 10:10 macro MSS post-news"))

    # Weekly profile pattern (Kish's Monday-Friday framework)
    if archetype or weekly_modifiers.get("is_opex_week") or weekly_modifiers.get("is_fomc_week"):
        queries.append(("Weekly Profile Pattern",
            "Kish weekly profile Monday Tuesday create range Wednesday CSD Thursday Friday run"))

    if not queries:
        return "", set()  # Clean day — no calendar-specific KB context needed

    # Fetch from KB
    kb_block, kb_unit_ids = fetch_kb_context_for_queries(queries, max_context_chars=5000, k_per_query=3)

    if not kb_block:
        # KB unavailable — still return the calendar summary without KB
        kb_block = ""

    # ── Build the structured block ──
    lines: list[str] = ["== CALENDAR & STRUCTURAL CONTEXT =="]

    # Calendar summary
    lines.append(f"Day Type: {day_type.upper()} | {dow}")
    if day_type_data.get("sizing_multiplier", 1.0) < 1.0:
        lines.append(f"Sizing: {day_type_data['sizing_multiplier']:.0%} of normal")
    if day_type_data.get("guidance"):
        lines.append(f"Guidance: {day_type_data['guidance']}")

    # Events today
    if day_type_data.get("events_today"):
        lines.append(f"Events: {', '.join(day_type_data['events_today'])}")
        if day_type_data.get("event_time"):
            lines.append(f"Event time: {day_type_data['event_time']} | "
                         f"Pre-buffer: {day_type_data.get('pre_event_buffer', 0)}min | "
                         f"Post-wait: {day_type_data.get('post_event_wait', 0)}min")

    # Week modifiers
    mod_strings: list[str] = []
    if weekly_modifiers.get("is_triple_witching_week"):
        mod_strings.append("TRIPLE WITCHING WEEK")
    elif weekly_modifiers.get("is_opex_week"):
        mod_strings.append("OPEX WEEK")
    if weekly_modifiers.get("is_fomc_week"):
        mod_strings.append("FOMC WEEK")
    if weekly_modifiers.get("is_cpi_week"):
        mod_strings.append("CPI WEEK")
    if weekly_modifiers.get("is_nfp_week"):
        mod_strings.append("NFP WEEK")
    if weekly_modifiers.get("is_jackson_hole_week"):
        mod_strings.append("JACKSON HOLE WEEK")
    if weekly_modifiers.get("has_treasury_auction"):
        mod_strings.append("TREASURY AUCTION WEEK")
    if mod_strings:
        lines.append(f"Week Modifiers: {' | '.join(mod_strings)}")

    # Archetype
    if archetype:
        lines.append(f"Archetype: {archetype}")
        if archetype_info and archetype_info.get("read"):
            lines.append(f"  Read: {archetype_info['read']}")
        if archetype_info and archetype_info.get("execution"):
            lines.append(f"  Execution: {archetype_info['execution']}")

    # Killzones and no-trade zones
    if day_type_data.get("killzones"):
        lines.append(f"Killzones: {' | '.join(day_type_data['killzones'])}")
    if day_type_data.get("no_trade_zones"):
        lines.append(f"No-trade zones: {' | '.join(day_type_data['no_trade_zones'])}")
    if day_type_data.get("no_trade_rules"):
        lines.append(f"No-trade rules: {' | '.join(day_type_data['no_trade_rules'])}")

    # Append KB block if retrieved
    if kb_block:
        lines.append("")
        lines.append(kb_block)

    return "\n".join(lines), kb_unit_ids


# ── ICT Weekly Event Timeline + Intraday Time Map ───────────────────
# These functions encode ICT methodology (Kish/ICT framework) as structured
# data — day-by-day expectations during event weeks and a complete intraday
# time map. KB fragments back up specific rules; the complete framework is
# assembled from ICT/Kish methodology knowledge.
#
# Regime tags: [CHOP] = consolidation/range, [EXPANSION] = directional move,
#              [SWEEP] = liquidity sweep then reversal, [NO-TRADE] = sit out.

# ICT weekly patterns by event type. Each entry is (day_name, expectation, regime).
_WEEKLY_PATTERNS: dict[str, list[tuple[str, str, str]]] = {
    "fomc": [
        ("Monday",    "Range building, consolidation. Defense-prone direction not established.", "[CHOP]"),
        ("Tuesday",   "Pre-positioning, range continues. Some direction hints. Reduced size.", "[CHOP]"),
        ("Wednesday", "FOMC 14:00. AM quiet (50-60% range). NO TRADE 14:00-14:30. Real move 15:00-16:00.", "[CHOP→EXPANSION]"),
        ("Thursday",  "Post-FOMC distribution — cleanest directional setups of the week. Wed real move continues.", "[EXPANSION]"),
        ("Friday",    "Standard AM. OPEX pinning if opex week. Close by 15:00. Weekend risk.", "[CHOP]"),
    ],
    "cpi": [
        ("Monday",    "Range building, positioning before CPI. Low conviction.", "[CHOP]"),
        ("Tuesday",   "CPI 08:30. Blackout 08:15-08:45. Manipulation 08:35-09:20. Recovery 09:50-10:10. 1.5-2x range. Post-spike FVG is entry.", "[SWEEP→EXPANSION]"),
        ("Wednesday", "Continuation or reversal of CPI direction. Often a trend day.", "[EXPANSION]"),
        ("Thursday",  "Standard setups. Direction resolved by CPI.", "[EXPANSION]"),
        ("Friday",    "Standard AM, close by 15:00. Weekend risk.", "[CHOP]"),
    ],
    "nfp": [
        ("Monday",    "Standard trading. Direction establishing.", "[CHOP]"),
        ("Tuesday",   "Standard setups. All killzones active.", "[EXPANSION]"),
        ("Wednesday", "Cleanest trend day. Silver Bullet strong.", "[EXPANSION]"),
        ("Thursday",  "Good setups. Afternoon: reduce size (NFP tomorrow).", "[CHOP→CAUTION]"),
        ("Friday",    "NFP 08:30. Judas Swing — first direction often fakeout. Wait 09:15. Silver Bullet 10-11 powerful. 9AM green → 70.6% green close.", "[SWEEP→EXPANSION]"),
    ],
    "jackson_hole": [
        ("Monday",    "Anticipation building. Strong pre-market ranges. Institutional positioning. Reduced size.", "[CHOP]"),
        ("Tuesday",   "Pre-positioning continues. Standard killzones but reduced conviction.", "[CHOP]"),
        ("Wednesday", "Anticipation peaks. Range-bound. Some directional hints.", "[CHOP]"),
        ("Thursday", "Last full day before speech. Position sizing down.", "[CHOP→CAUTION]"),
        ("Friday",    "Powell speech 10:00 ET. FOMC-class event. No entries 15min before. Wait for spike resolution. Afternoon distribution.", "[SWEEP→EXPANSION]"),
    ],
    "opex": [
        ("Monday",    "Run-up begins. Direction establishing.", "[EXPANSION]"),
        ("Tuesday",   "Takes Monday high, continues up. KB: 'Tuesday OPEX week — you already know what you want to see.' (conf 0.95)", "[EXPANSION]"),
        ("Wednesday", "Does the damage — sell-off. KB: 'Mon-Tue run up, Wed does the damage' (conf 0.90). Best day for shorts.", "[EXPANSION↓]"),
        ("Thursday",  "Sell-off may continue or stabilize.", "[CHOP→EXPANSION]"),
        ("Friday",    "Expiration day. Pinning toward magnet (max pain/peak GEX). Reversals from ceilings/floors reliable. Size down.", "[CHOP/PIN]"),
    ],
    "triple_witching": [
        ("Monday",    "Heavy positioning. Volume building.", "[EXPANSION]"),
        ("Tuesday",   "Continued run-up. Increased volatility from options/futures rolls.", "[EXPANSION]"),
        ("Wednesday", "Sell-off / damage. Position rollover accelerates.", "[EXPANSION↓]"),
        ("Thursday",  "Erratic breakouts due to heavy rollover. Spreads may widen.", "[CHOP/VOLATILE]"),
        ("Friday",    "Triple expiration. Massive volume. Pinning extreme. Size down significantly.", "[CHOP/PIN]"),
    ],
    "clean": [
        ("Monday",    "Defense-prone, direction not established. Wait for London to set direction.", "[CHOP]"),
        ("Tuesday",   "Neutral, good for setups. All killzones active.", "[EXPANSION]"),
        ("Wednesday", "Cleanest trend day of the week. Silver Bullet strong.", "[EXPANSION]"),
        ("Thursday",  "Good setups. Watch for NFP tomorrow (if NFP week).", "[EXPANSION]"),
        ("Friday",    "Institutions reduce risk. After 12:00 volume drops. Close by 15:00.", "[CHOP]"),
    ],
}

# ICT intraday time map. Each entry is (time_range, window_name, regime, action).
# Regime: [SWEEP], [EXPANSION], [CHOP], [NO-TRADE], [SETUP], [DELIVERY]
_INTRADAY_TIME_MAP: list[tuple[str, str, str, str]] = [
    ("02:00-05:00", "London Open killzone (best 02:00-04:00)",  "[SWEEP]",     "Liquidity runs. Sweep direction. Asia range often taken."),
    ("04:00-05:00", "London AM",                                "[SETUP]",     "London sets direction. Range H/L become targets for NY."),
    ("05:00-08:30", "Pre-NY (Herman sweep zone)",               "[SWEEP]",     "Pre-NY sweep of London H/L. Herman dominant signal if sweep occurs."),
    ("08:15-09:45", "Liquidity Hunt Macro (Kish)",              "[SETUP]",     "Price discovery → liquidity sweep → CSD entry. KB conf 0.90."),
    ("08:30",       "NY Open / RTH open",                       "[NO-TRADE]",  "First M1 candle unreliable (except news days). Don't read it. KB conf 0.90."),
    ("09:12",       "9:12 Macro (Kish)",                        "[SETUP]",     "CSD entry signal. 'CSD after 8:15, CSD after 9:12, beautiful.' KB conf 0.90."),
    ("09:30",       "Equities open",                             "[SWEEP]",     "Wait for first candle close (15-min moat). Judas Swing often here — manipulative sweep then reversal."),
    ("08:35-09:20", "Manipulation Window (news days)",           "[NO-TRADE]",  "Judas Swing — manipulative sweeps. Wait for valid setup after 09:20. KB §14."),
    ("09:45-10:00", "Offset Macro (Kish)",                      "[SETUP]",     "'9:45 is the time you only watch.' Silver Bullet begins. KB conf 0.50-0.80."),
    ("09:50-10:10", "MACRO WINDOW — MSS prime time",             "[SETUP]",     "Prime time for MSS/CISD on LTF. Displacement + FVG. KB §14."),
    ("10:00-11:00", "SILVER BULLET window",                      "[EXPANSION]", "Highest probability entries. FVGs in direction of confirmed bias."),
    ("10:45-11:00", "Offset macro rebalance",                    "[CHOP]",      "'Offset's going to be your next time macro.' KB conf 0.40. Rebalance before lunch."),
    ("11:00",       "Rebalance Macro (Kish)",                   "[DELIVERY]",  "Morning delivery assessment. '11 o'clock should create a delivery that's tradable.' KB conf 0.70."),
    ("11:30-13:30", "NY LUNCH — dead zone",                      "[CHOP]",      "No new entries. Mean-reverting chop. Volume drops. KB config."),
    ("12:45",       "12:45 Macro (Kish)",                       "[SWEEP]",     "Time-based liquidity run. After the run, look for CSD entry. KB conf 0.90."),
    ("13:00",       "Treasury auctions (when scheduled)",        "[VOLATILE]",  "Afternoon volatility. 'Bond auction at noon causing volatility and speed lower.' KB conf 0.85."),
    ("14:00-14:30", "FOMC statement (when scheduled)",          "[NO-TRADE]",  "NO TRADE — reverses 60%+. Most dangerous phase. PO3: accumulation→manipulation→distribution."),
    ("15:00-16:00", "POWER HOUR — distribution",                "[EXPANSION]", "Strong directional moves. FOMC real move. Settlement pressure."),
    ("15:59-16:00", "Last bar — prop-firm exit",                 "[EXIT]",      "ADR-020: max exit at 16:00 ET close of 15:59 bar."),
    ("16:00+",      "Post-close / Globex opens 18:00",           "[CHOP]",      "After-hours thin. Weekend risk on Fridays — close all."),
]

# Post-news candle management rules (KB-backed)
_POST_NEWS_RULES: list[tuple[str, str, float]] = [
    ("Don't read the first M1 candle of the session — statistically unreliable (except news days).", "2023-11-10 tip", 0.90),
    ("First two M1 candles of a new M5 typically retrace (OLR) — third shows direction.", "Nov 10 2023 tip", 0.90),
    ("Require M5 candle close above 50% of order block before taking a trade.", "Jul 21 2023 tip", 0.90),
    ("Wait for green M5 candle close above key level before making a decision.", "Sep 26 2023 tip", 0.95),
    ("Don't trade the first candle at 8:15 or equities open — wait for reaction at a key level.", "Jan 15 2024 tip", 0.90),
    ("15 minutes before equities open is a crack — don't commit before 09:30.", "Jan 15 2024 tip", 0.70),
    ("News blackout: no new entries 15 min before HIGH event.", "config", 1.0),
    ("Recovery: 80% of setups occur 20-60 min post-release — wait for MSS/CISD on LTF.", "ICT_CONCEPTS_KB §14", 1.0),
    ("After large expansion, if next candles don't retrace → retracement is delayed. Sponsored candles = continuation.", "Analysis vs Marking Charts", 0.60),
    ("After news, any candle body below the lows should incite speed to push lower — Judas swing.", "Aug 1 2023", 0.90),
]


def build_weekly_event_timeline(
    target_date: date,
    events: list[dict] | None = None,
    weekly_modifiers: dict | None = None,
    archetype_info: dict | None = None,
    *,
    mode: str = "premarket",
) -> str:
    """Build a day-by-day event timeline for the week.

    Args:
        target_date: date to anchor the week (Monday of that week is used).
        events: full week's econ events (for next-week mode, pass next week's events).
        weekly_modifiers: output of get_weekly_modifiers().
        archetype_info: output of determine_weekly_archetype().
        mode: "premarket" (this week, highlight today), "intraday" (weekly position
              line only), "close" (tomorrow's preview), "weekly" (next week full).

    Returns:
        Formatted timeline block string.
    """
    events = events or []
    weekly_modifiers = weekly_modifiers or {}

    # Determine the week type
    if weekly_modifiers.get("is_triple_witching_week"):
        week_type = "triple_witching"
    elif weekly_modifiers.get("is_jackson_hole_week"):
        week_type = "jackson_hole"
    elif weekly_modifiers.get("is_fomc_week"):
        week_type = "fomc"
    elif weekly_modifiers.get("is_cpi_week"):
        week_type = "cpi"
    elif weekly_modifiers.get("is_nfp_week"):
        week_type = "nfp"
    elif weekly_modifiers.get("is_opex_week"):
        week_type = "opex"
    else:
        week_type = "clean"

    pattern = _WEEKLY_PATTERNS.get(week_type, _WEEKLY_PATTERNS["clean"])

    # Find Monday of the target week
    monday = target_date - timedelta(days=target_date.weekday())

    if mode == "intraday":
        # Just the weekly position line
        dow = target_date.strftime("%A")
        today_idx = target_date.weekday()
        day_name, expectation, regime = pattern[today_idx]
        mod_str = _format_modifiers_short(weekly_modifiers)
        lines = [f"Weekly Position: {dow} of {mod_str}."]
        lines.append(f"  ICT Read: {expectation} {regime}")
        return "\n".join(lines)

    if mode == "close":
        # Tomorrow's preview — uses THIS week's pattern since tomorrow is in the same week
        # (unless today is Friday → tomorrow is next week)
        tomorrow = target_date + timedelta(days=1)
        if tomorrow.weekday() >= 5:  # Saturday/Sunday → skip to next Monday
            tomorrow = tomorrow + timedelta(days=(7 - tomorrow.weekday()))
        tomorrow_idx = min(tomorrow.weekday(), 4)
        if tomorrow_idx < len(pattern):
            day_name, expectation, regime = pattern[tomorrow_idx]
        else:
            expectation, regime = "No specific pattern data.", ""
        lines = ["== TOMORROW'S PREVIEW =="]
        lines.append(f"Tomorrow: {tomorrow.strftime('%A')}")
        lines.append(f"  ICT Read: {expectation} {regime}")
        # Weekly position context
        dow = target_date.strftime("%A")
        today_idx = target_date.weekday()
        if today_idx < len(pattern):
            _, today_exp, _ = pattern[today_idx]
            lines.append(f"Today was: {dow} — {today_exp}")
        mod_str = _format_modifiers_short(weekly_modifiers)
        if mod_str != "Clean Week":
            lines.append(f"Week context: {mod_str}")
        return "\n".join(lines)

    # Full timeline (premarket or weekly mode)
    mod_str = _format_modifiers_short(weekly_modifiers)
    lines = [f"== WEEKLY EVENT TIMELINE ({mod_str}) =="]

    active_modifiers: list[str] = []
    if weekly_modifiers.get("is_triple_witching_week"):
        active_modifiers.append("TRIPLE WITCHING")
    if weekly_modifiers.get("is_opex_week"):
        active_modifiers.append("OPEX")
    if weekly_modifiers.get("is_fomc_week"):
        active_modifiers.append("FOMC")
    if weekly_modifiers.get("is_cpi_week"):
        active_modifiers.append("CPI")
    if weekly_modifiers.get("is_nfp_week"):
        active_modifiers.append("NFP")
    if weekly_modifiers.get("is_jackson_hole_week"):
        active_modifiers.append("JACKSON HOLE")
    if weekly_modifiers.get("has_treasury_auction"):
        active_modifiers.append("TREASURY AUCTION")
    if len(active_modifiers) > 1:
        lines.append(f"Active Modifiers: {' + '.join(active_modifiers)}")

    if archetype_info:
        arch = archetype_info.get("archetype", "")
        if arch:
            lines.append(f"Archetype: {arch}")
            if archetype_info.get("read"):
                lines.append(f"  {archetype_info['read']}")

    for i, (day_name, expectation, regime) in enumerate(pattern):
        day_date = monday + timedelta(days=i)
        is_today = day_date == target_date
        marker = " ← TODAY" if is_today else ""
        lines.append(f"{day_name}{marker}: {expectation} {regime}")

    return "\n".join(lines)


def build_ict_time_map(
    day_type: str = "clean",
    target_date: date | None = None,
    *,
    mode: str = "premarket",
) -> str:
    """Build the ICT intraday time map, filtered by mode.

    Args:
        day_type: output of classify_day_type (clean/cpi/nfp/fomc/jackson_hole/special).
        target_date: today's date (for Friday check).
        mode: "premarket" (full day), "open" (AM only 09:30-11:30),
              "intraday" (PM only 12:00-16:00), "close" (tomorrow's key times).

    Returns:
        Formatted time map block string.
    """
    if mode == "close":
        # Tomorrow's key times only — compact
        lines = ["Tomorrow's Key Times:"]
        key_times = [
            ("08:15-09:45", "Liquidity Hunt Macro"),
            ("09:50-10:10", "Macro Window — MSS/CISD prime"),
            ("10:00-11:00", "Silver Bullet"),
            ("11:30-13:30", "NY Lunch (dead)"),
            ("15:00-16:00", "Power Hour"),
        ]
        for time_str, name in key_times:
            lines.append(f"  {time_str}  {name}")
        return "\n".join(lines)

    # Filter time map by mode
    if mode == "open":
        # AM only: 09:30-11:30
        time_filter = lambda t: _time_in_range(t, "09:30", "11:30")
    elif mode == "intraday":
        # PM only: 12:00-16:00 (exclude 16:00+ post-close)
        time_filter = lambda t: _time_in_range(t, "12:00", "16:00")
    else:
        # premarket: full day (include 16:00+ post-close note)
        time_filter = lambda t: True

    lines: list[str] = []
    if mode == "premarket":
        header = f"== ICT INTRADAY TIME MAP ({day_type.upper()} Day) =="
        lines.append(header)
    elif mode == "open":
        lines.append("== TODAY'S AM TIME WINDOWS ==")
    elif mode == "intraday":
        lines.append("== PM TIME WINDOWS ==")

    for time_str, window_name, regime, action in _INTRADAY_TIME_MAP:
        # Extract start time for filtering
        if "+" in time_str:
            # Post-close entries (16:00+) only in premarket mode
            if mode != "premarket":
                continue
        else:
            start_time = time_str.split("-")[0].strip() if "-" in time_str else time_str.strip()
            if not time_filter(start_time):
                continue

        # Format line with regime tag
        lines.append(f"{time_str:<14s} {regime:<14s} {window_name}")
        lines.append(f"               {action}")

    # Add FOMC-specific warning if FOMC day
    if day_type == "fomc" and mode in ("premarket", "open", "intraday"):
        lines.append("")
        lines.append("⚠ FOMC TODAY at 14:00 ET — NO TRADE 14:00-14:30. Real move is 15:00-16:00 (distribution).")

    # Add Jackson Hole warning
    if day_type == "jackson_hole" and mode in ("premarket", "open"):
        lines.append("")
        lines.append("⚠ JACKSON HOLE: Powell speech 10:00 ET. No entries 15min before. Wait for spike resolution.")

    # Friday close reminder
    if target_date and target_date.weekday() == 4 and mode in ("premarket", "intraday"):
        lines.append("")
        lines.append("⚠ FRIDAY: Close all positions by 15:00 ET. Weekend risk.")

    return "\n".join(lines)


def build_post_news_management_block(day_type: str = "clean") -> str:
    """Build the post-news candle management rules block.

    Only included on event days (cpi/nfp/fomc/jackson_hole/special).
    """
    if day_type not in ("cpi", "nfp", "fomc", "jackson_hole", "special"):
        return ""

    lines = ["== POST-NEWS CANDLE MANAGEMENT =="]
    for rule, source, conf in _POST_NEWS_RULES:
        lines.append(f"  • {rule}")
        lines.append(f"    Source: {source} (conf={conf:.2f})")
    return "\n".join(lines)


def _format_modifiers_short(modifiers: dict) -> str:
    """Format weekly modifiers into a short string for timeline headers."""
    parts: list[str] = []
    if modifiers.get("is_triple_witching_week"):
        parts.append("TRIPLE WITCHING")
    if modifiers.get("is_opex_week"):
        parts.append("OPEX")
    if modifiers.get("is_fomc_week"):
        parts.append("FOMC")
    if modifiers.get("is_cpi_week"):
        parts.append("CPI")
    if modifiers.get("is_nfp_week"):
        parts.append("NFP")
    if modifiers.get("is_jackson_hole_week"):
        parts.append("JACKSON HOLE")
    if modifiers.get("has_treasury_auction"):
        parts.append("TREASURY AUCTION")
    return " + ".join(parts) if parts else "Clean Week"


def _time_in_range(time_str: str, start: str, end: str) -> bool:
    """Check if a time string (HH:MM) falls within [start, end)."""
    # Handle non-standard entries like "16:00+" — only include in premarket (full day)
    if "+" in time_str or not ":" in time_str.split("-")[0].split()[0]:
        return True  # Include in full-day mode, filtered out by mode logic
    try:
        # Extract the start time from range strings like "02:00-05:00" or single "08:30"
        raw = time_str.split("-")[0].strip()
        h, m = raw.split(":")
        t = int(h) * 60 + int(m)
        sh, sm = start.split(":")
        s = int(sh) * 60 + int(sm)
        eh, em = end.split(":")
        e = int(eh) * 60 + int(em)
        return s <= t < e
    except (ValueError, IndexError):
        return True  # If we can't parse, include it


def build_ticker_cheat_sheet(
    ticker: str,
    mode: str = "open",
    loader: DataLoader | None = None,
    target_date: date | None = None,
    now_et: datetime | None = None,
) -> str:
    """Mode-specific assembly of data sources for a SINGLE ticker into a cheat sheet.

    When now_et is provided (simulation mode), the spot price is resolved to the
    09:30 RTH open bar if available (instead of the overnight globex close).
    """
    if loader is None:
        loader = get_dataloader(lookback_days=5)

    if target_date is None:
        target_date = datetime.now(ET).date()

    sections: list[str] = []

    # ── MACRO CONTEXT (Always NQ+ES to gauge broad market) ──
    nq_ctx = build_overnight_context(loader, "NQ1", target_date)
    es_ctx = build_overnight_context(loader, "ES1", target_date)

    ticker_ctx = build_overnight_context(loader, ticker, target_date)
    overnight_lines = ["== OVERNIGHT MACRO (Globex 18:00 → 08:30 ET) =="]
    if not ticker_ctx:
        overnight_lines.append(f"{ticker}: No data available")
    else:
        overnight_lines.append(
            f"{ticker}: Open {ticker_ctx['open']:,.2f} → Globex Close {ticker_ctx['close']:,.2f} ({ticker_ctx['change_pct']}%)"
        )
        overnight_lines.append(
            f"    Session Low: {ticker_ctx['low']:,.2f} at {ticker_ctx['session_low_time']} | Session High: {ticker_ctx['high']:,.2f} at {ticker_ctx['session_high_time']}"
        )
        overnight_lines.append(f"    Trajectory: {ticker_ctx['trajectory']}")
    sections.append("\n".join(overnight_lines))

    vix_ctx = get_vix_checkpoint(loader)
    macro_quotes = get_intermarket_quotes()
    intermarket = build_intermarket_read(nq_ctx, es_ctx, vix_ctx, macro_quotes)
    sections.append("== INTERMARKET OVERNIGHT MACRO (NQ vs ES) ==\n" + intermarket)

    # ── Econ Releases & Earnings ──
    async def run_async_signals():
        _ensure_database_url()
        from prisma import Prisma
        db = Prisma()
        await db.connect()
        try:
            from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
            broker = BrokerService()
            
            # Fetch econ events
            from scripts.trader.signals.econ_calendar import get_econ_releases
            econ_releases = await get_econ_releases(target_date, db)
            
            # Fetch earnings
            from scripts.trader.signals.earnings import fetch_earnings_events
            db_path = str(REPO_ROOT / "web" / "prisma" / "dev.db")
            earnings_list = await fetch_earnings_events(target_date, db_path, broker)
        finally:
            await db.disconnect()
        return econ_releases, earnings_list

    try:
        econ_releases, earnings_data = run_async_safely(run_async_signals())
    except Exception as e:
        log.warning("[cheat_sheet] Failed to fetch econ/earnings signals: %s", e)
        econ_releases, earnings_data = [], []

    # Fetch news
    from scripts.trader.utils.news_scraper import get_macro_headlines
    try:
        headlines = get_macro_headlines()
    except Exception as e:
        log.warning("[cheat_sheet] Failed to fetch headlines: %s", e)
        headlines = []

    # Calculate caution score
    from scripts.trader.signals.caution_score import calculate_caution_score
    try:
        caution_vix = get_vix_vvix_checkpoint()
        caution = calculate_caution_score(caution_vix, nq_ctx, es_ctx, econ_releases, earnings_data)
    except Exception as e:
        log.warning("[cheat_sheet] Failed to calculate caution score: %s", e)
        caution = {"score": 0, "posture": "UNKNOWN", "reasons": []}

    # Format blocks
    sections.append(_format_scheduled_risk_block(econ_releases))
    sections.append(_format_earnings_block(earnings_data))
    sections.append(_format_news_block(headlines))
    sections.append(_format_caution_score_block(caution))

    # ── TICKER SPECIFIC CONTEXT ──
    ticker_ctx = build_overnight_context(loader, ticker, target_date)
    ticker_spot = ticker_ctx.get("close", 0) if ticker_ctx else 0
    base_label = ticker.replace("1", "").upper()

    # For open mode: try to use the 09:30 RTH open as the spot price
    # instead of the overnight globex close. This is the actual price
    # at the RTH open, which is what the trade plan should reference.
    if mode == "open":
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            _df = load_fused_data(ticker, timeframe="1m", require_historical=False)
            if _df is not None and not _df.empty:
                if _df.index.tz is None:
                    _df.index = pd.DatetimeIndex(_df.index).tz_localize("UTC").tz_convert(ET)
                elif _df.index.tz != ET:
                    _df.index = _df.index.tz_convert(ET)
                # Filter to simulation time if provided
                if now_et is not None:
                    _df = _df[_df.index <= now_et]
                # Find the 09:30 bar for target_date
                _rth_open_ts = pd.Timestamp(target_date, tz=ET).replace(hour=9, minute=30)
                _rth_open_bars = _df[_df.index >= _rth_open_ts]
                if not _rth_open_bars.empty:
                    ticker_spot = float(_rth_open_bars["open"].iloc[0])
                    log.info("[cheat_sheet] Using 09:30 RTH open as spot: %.2f", ticker_spot)
                elif now_et is not None:
                    # Pre-open: use the latest available price
                    ticker_spot = float(_df["close"].iloc[-1])
                    log.info("[cheat_sheet] Pre-open, using latest price as spot: %.2f", ticker_spot)
        except Exception as e:
            log.warning("[cheat_sheet] Could not resolve RTH open spot: %s", e)

    rth_lines = [f"== RTH BREAKS ({base_label}) =="]
    if ticker_ctx:
        prth_h = ticker_ctx.get("prior_rth_high")
        prth_l = ticker_ctx.get("prior_rth_low")
        if prth_h is not None and prth_l is not None and ticker_spot:
            if ticker_spot > prth_h:
                scenario = "GAP UP (open above pRTH High) — 70% close holds above"
            elif ticker_spot < prth_l:
                scenario = "GAP DOWN (open below pRTH Low) — 60% close holds below"
            else:
                scenario = "INSIDE RANGE (open within pRTH) — 74% one side breached"
            rth_lines.append(f"pRTH High {prth_h:,.2f} | pRTH Low {prth_l:,.2f}")
            rth_lines.append(f"Current {ticker_spot:,.2f} → {scenario}")
        else:
            rth_lines.append("No pRTH data available")
    sections.append("\n".join(rth_lines))

    # GEX structure (Removed separate block, merged into Structural Levels)
    session_arg = mode if mode in {"open", "close"} else "live"
    unified = load_macro_levels(session=session_arg)
    # If ticker is NQ1 -> NQ, ES1 -> ES, otherwise try directly
    ticker_unified = unified.get(base_label) or unified.get(ticker) or {}
    
    ticker_gex = _extract_gex_levels(ticker_unified, base_label)
    # sections.append(_format_gex_block(base_label, ticker_gex, ticker_spot))

    # ALN
    aln_data: dict = {}
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        from scripts.libs_py.nqstats.engine import NQStatsEngine

        df_t = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_t is not None and not df_t.empty:
            if df_t.index.tz is None:
                df_t.index = pd.DatetimeIndex(df_t.index).tz_localize("UTC").tz_convert(ET)
            elif df_t.index.tz != ET:
                df_t.index = df_t.index.tz_convert(ET)

            _cutoff = pd.Timestamp.now(ET) - timedelta(days=10)
            df_t_recent = df_t[df_t.index >= _cutoff]
            if df_t_recent.empty:
                df_t_recent = df_t

            engine = NQStatsEngine(df_t_recent, ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()

            lh = latest.get("london_high")
            ll = latest.get("london_low")
            lh_val = float(lh) if lh is not None and pd.notna(lh) and not math.isnan(float(lh)) else None
            ll_val = float(ll) if ll is not None and pd.notna(ll) and not math.isnan(float(ll)) else None
            mid_val = (lh_val + ll_val) / 2 if lh_val is not None and ll_val is not None else None
            aln_data = {
                "aln": latest.get("aln", "N/A"),
                "broken": latest.get("broken", "N/A"),
                "asia_status": latest.get("asiabox_status", "N/A"),
                "london_status": latest.get("londonbox_status", "N/A"),
                "ib_bias": latest.get("ib_bias", "N/A"),
                "ib_conviction": latest.get("ib_conviction", 0),
                "noon_curve": latest.get("noon_curve", "N/A"),
                "p12": latest.get("p12"),
                "levels": {
                    "lh": lh_val,
                    "ll": ll_val,
                    "mid": mid_val,
                },
            }

            aln_pattern = aln_data["aln"]
            broken = aln_data["broken"]
            from scripts.libs_py.nqstats.classifiers import compute_aln_bias
            _bias = compute_aln_bias(
                aln_pattern, broken,
                spot=ticker_spot,
                london_high=aln_data["levels"]["lh"],
                london_low=aln_data["levels"]["ll"],
            )
            aln_data["bias"] = _bias["bias"]
            aln_data["conviction"] = _bias["conviction"]
            aln_data["reasoning"] = _bias["reasoning"]
            aln_data["primary_target"] = _bias["primary_target"]
            aln_data["primary_target_pct"] = _bias["primary_target_pct"]
            aln_data["break_high_pct"] = _bias["break_high_pct"]
            aln_data["break_low_pct"] = _bias["break_low_pct"]
            aln_data["edge_spent"] = _bias["edge_spent"]
            aln_data["edge_spent_note"] = _bias["edge_spent_note"]
    except Exception as e:
        log.warning("[cheat_sheet] ALN engine failed for %s: %s", ticker, e)
    
    sections.append(_format_aln_block(base_label, aln_data, ticker_spot))

    # Herman Pre-NY sweep — DOMINANT signal at open
    try:
        from scripts.libs_py.nqstats.classifiers import compute_herman_pre_ny_sweep
        _es_spot_h = ticker_spot if ticker == "ES1" else 0
        from scripts.trader.signals.session_ranges import compute_all_session_ranges
        from scripts.utils.fused_data_loader import load_fused_data
        _df_h = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if _df_h is not None and not _df_h.empty:
            if _df_h.index.tz is None:
                _df_h.index = pd.DatetimeIndex(_df_h.index).tz_localize("UTC").tz_convert(ET)
            elif _df_h.index.tz != ET:
                _df_h.index = _df_h.index.tz_convert(ET)
            _sr = compute_all_session_ranges(_df_h, target_date, ET)
            _pre_ny = _sr.get("PRE_NY", {})
            _london = _sr.get("LONDON", {})
            if _pre_ny and _london:
                _sweep = compute_herman_pre_ny_sweep(_pre_ny, _london.get("high"), _london.get("low"))
                _lines = ["== HERMAN PRE-NY SWEEP (05:00-08:30) — DOMINANT =="]
                _lines.append(f"Result: {_sweep['label']}")
                _lines.append(f"Bias: {_sweep['bias']} ({_sweep['probability']:.1f}%)")
                if _sweep["dominant"]:
                    _lines.append("DOMINANT — overrides ALN. Do not fade.")
                else:
                    _lines.append("Not dominant — wait for 09:30 OR break.")
                _lines.append(f"Read: {_sweep['read']}")
                sections.append("\n".join(_lines))
    except Exception as e:
        log.warning("[cheat_sheet] Herman Pre-NY sweep failed for %s: %s", ticker, e)

    # Daily Profiler (session outcomes, conditional predictions, reference levels)
    # Live sessions come from SessionBoxEngine (reads live 1m parquet); the
    # lookup table provides historical conditional statistics. Without
    # live_sessions the profiler returns no data.
    # Pass now_et as cutoff so only sessions that have actually played out
    # by the current time are classified (e.g. at 09:30 ET, NY2 hasn't
    # started yet so it shows as "None").
    try:
        from scripts.trader.signals.profiler import build_dual_profiler_block
        from scripts.trader.signals.intraday_blocks import _get_live_profiler_sessions, _get_es_live_profiler_sessions
        es_spot = float(es_ctx.get("close", 0)) if es_ctx else 0.0
        # Use now_et (sim time) if provided, else current ET time as cutoff
        _cutoff = now_et if now_et is not None else datetime.now(ET)
        _live, _prev = _get_live_profiler_sessions(ticker, cutoff_time=_cutoff)
        _es_live, _es_prev = (_live, _prev) if ticker == "ES1" else _get_es_live_profiler_sessions(cutoff_time=_cutoff)
        sections.append(build_dual_profiler_block(
            ticker, "ES1", ticker_spot, es_spot, target_date, now_et,
            live_sessions=_live, es_live_sessions=_es_live,
        ))
    except Exception as e:
        log.warning("[cheat_sheet] Profiler block failed for %s: %s", ticker, e)

    # Quarters Theory (overnight combo + hourly candle structure)
    try:
        from scripts.trader.signals.quarters_theory import build_quarters_block
        import pytz as _pytz
        _now_et = datetime.now(_pytz.timezone("America/New_York"))
        from scripts.utils.fused_data_loader import load_fused_data
        _df_q = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if _df_q is not None and not _df_q.empty:
            if _df_q.index.tz is None:
                _df_q.index = pd.DatetimeIndex(_df_q.index).tz_localize("UTC").tz_convert(ET)
            elif _df_q.index.tz != ET:
                _df_q.index = _df_q.index.tz_convert(ET)
            sections.append(build_quarters_block(
                ticker, _df_q, _now_et,
                asia_status=str(aln_data.get("asia_status", "")),
                london_status=str(aln_data.get("london_status", "")),
            ))
    except Exception as e:
        log.warning("[cheat_sheet] Quarters block failed for %s: %s", ticker, e)

    # Classification
    class_data: dict = {}
    try:
        import scripts.analysis.analyze_daily_classification_bias as class_module
        import sys as _sys
        orig_argv = _sys.argv[:]
        _sys.argv = ["analyze_daily_classification_bias.py", "--ticker", ticker, "--date", target_date.isoformat()]
        try:
            _, class_data = class_module.main()
        finally:
            _sys.argv = orig_argv
    except Exception as e:
        log.warning("[cheat_sheet] Classification analysis failed for %s: %s", ticker, e)
    sections.append(_format_classification_block(base_label, class_data))

    # Key levels hierarchy
    # Note: _format_key_levels_hierarchy was originally built taking nq_gex, es_gex. 
    # We will pass ticker_gex as the primary levels dict and an empty dict for the second, or adjust it if needed.
    # The signature in briefing_core is `_format_key_levels_hierarchy(ticker_label, levels, aln_data, spot)`
    sections.append(_format_key_levels_hierarchy(base_label, ticker_gex, aln_data, ticker_spot))

    # Data freshness — omitted from cheat sheet.
    # Herman stats and classification parquets are historical studies (not
    # per-day data). Their probabilities are frozen in narrative_stats.yaml
    # and live session detection reads 1m parquet directly. Showing a
    # "stale" warning misleads the LLM into questioning valid historical data.
    # try:
    #     freshness = check_all()
    #     stale = [f for f in freshness if f.is_stale]
    #     if stale:
    #         sections.append("== DATA FRESHNESS ==\n" + "\n".join(f"⚠ {s.source}: {s.days_stale}d stale (last {s.last_date})" for s in stale))
    # except Exception as e:
    #     log.warning("[cheat_sheet] Freshness check failed: %s", e)

    # VIX/VVIX volatility regime
    try:
        vv = get_vix_vvix_checkpoint()
        sections.append(_format_volatility_block(vv))
    except Exception as e:
        log.warning("[cheat_sheet] Volatility signal failed: %s", e)

    # ICT context
    try:
        ict = compute_ict_from_htf(ticker=ticker, current_price=ticker_spot)
        sections.append(_format_ict_block(base_label, ict, ticker_spot))
    except Exception as e:
        log.warning("[cheat_sheet] ICT context failed for %s: %s", ticker, e)

    # ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
    try:
        from scripts.trader.signals.intraday_blocks import (
            _format_kz_pivots_block,
            _format_ipda_block,
            _format_silver_bullet_block,
            _format_macro_block,
            _format_imbalance_block,
            _format_gaps_block,
        )
        import pytz as _pytz
        now_et = datetime.now(_pytz.timezone("America/New_York"))
        
        kz_block = _format_kz_pivots_block(ticker, ticker_spot, "OPEN")
        if "No pivot data" not in kz_block: sections.append(kz_block)
        
        ipda_block = _format_ipda_block(ticker, ticker_spot)
        if "No IPDA data" not in ipda_block: sections.append(ipda_block)
        
        sb_block = _format_silver_bullet_block(now_et)
        if "No Silver Bullet windows remaining today" not in sb_block and "Data unavailable" not in sb_block: sections.append(sb_block)
        
        macro_block = _format_macro_block(now_et)
        if "No macro windows remaining today" not in macro_block and "Data unavailable" not in macro_block: sections.append(macro_block)
        
        imb_block = _format_imbalance_block(ticker, ticker_spot, target_date, now_et)
        if "No imbalances detected" not in imb_block and "No imbalances yet" not in imb_block: sections.append(imb_block)
        
        gaps_block = _format_gaps_block(ticker, ticker_spot)
        if "No active gaps" not in gaps_block: sections.append(gaps_block)
    except Exception as e:
        log.warning("[cheat_sheet] ICT feature blocks failed for %s: %s", ticker, e)

    # FTFC bias + SMA stance
    try:
        from scripts.trader.signals.intraday_blocks import _format_ftfc_block
        sections.append(_format_ftfc_block(ticker, ticker_spot, now_et))
    except Exception as e:
        log.warning("[cheat_sheet] FTFC failed for %s: %s", ticker, e)

    # Candle Science
    try:
        cs = get_candle_science_read(ticker=ticker)
        sections.append(_format_candle_science_block(base_label, cs))
    except Exception as e:
        log.warning("[cheat_sheet] Candle Science failed for %s: %s", ticker, e)

    # Confluence assessment
    try:
        aln_bias = aln_data.get("bias", "NEUTRAL")
        s1 = "BULLISH" if "BULLISH" in aln_bias else ("BEARISH" if "BEARISH" in aln_bias else "NEUTRAL")

        # RTH break scenario — use compute_rth_bias for pre-computed verdict
        from scripts.libs_py.nqstats.classifiers import compute_rth_bias
        _prth_h = ticker_ctx.get("prior_rth_high") if ticker_ctx else None
        _prth_l = ticker_ctx.get("prior_rth_low") if ticker_ctx else None
        rth_data = compute_rth_bias(ticker_spot, _prth_h, _prth_l)
        rth_scenario = rth_data["scenario"]
        s2 = rth_data["bias"]

        # Emit dedicated RTH break block so LLM doesn't need to re-derive
        sections.append(_format_rth_break_block(base_label, rth_data))

        s3 = "BULLISH" if (cs and cs.get("p_bull", 50) > cs.get("p_bear", 50)) else ("BEARISH" if (cs and cs.get("p_bear", 50) > cs.get("p_bull", 50)) else "NEUTRAL")
        conf = assess_confluence(s1, s2, s3)
        sections.append(_format_confluence_block(base_label, conf))
    except Exception as e:
        log.warning("[cheat_sheet] Confluence failed: %s", e)

    # Day type
    try:
        dt = classify_day_type(econ_releases, target_date)
        sections.append(_format_day_type_block(dt))
    except Exception as e:
        log.warning("[cheat_sheet] Day type failed: %s", e)

    # Weekly profile
    try:
        wp = compute_weekly_profile(ticker=ticker, current_price=ticker_spot)
        sections.append(_format_weekly_profile_block(base_label, wp))
    except Exception as e:
        log.warning("[cheat_sheet] Weekly profile failed for %s: %s", ticker, e)

    # ICT liquidity map
    try:
        lm = build_liquidity_map(
            bias=s1,
            nq_status=aln_data,
            overnight=ticker_ctx or {},
            ict=ict,
            news_tier="HIGH" if any(e.get("impact") == "HIGH" for e in econ_releases) else ("MEDIUM" if any(e.get("impact") == "MEDIUM" for e in econ_releases) else "NONE"),
        )
        sections.append(_format_liquidity_map_block(lm))
    except Exception as e:
        log.warning("[cheat_sheet] Liquidity map failed: %s", e)

    # GEX regime change
    try:
        ticker_gex_full = ticker_unified if isinstance(ticker_unified, dict) else {}
        gr = get_gex_regime_change(ticker_gex_full)
        if gr.get("regime_change") and gr["regime_change"] != "stable":
            sections.append(_format_gex_regime_block(gr))
        if ticker_gex_full:
            save_today_snapshot(ticker_gex_full)
    except Exception as e:
        log.warning("[cheat_sheet] GEX regime change failed: %s", e)

    # GEX positioning verdict (session-aware, pre-computed for LLM)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block
        _es_spot = ticker_spot if ticker == "ES1" else 0
        sections.append(_format_gex_block(ticker_spot, _es_spot, ticker, session="OPEN", target_date=target_date))
    except Exception as e:
        log.warning("[cheat_sheet] GEX positioning failed for %s: %s", ticker, e)

    # Expected Move
    try:
        em_data = get_em_context(spot=ticker_spot, ticker=ticker)
        sections.append(format_em_block(em_data))
    except Exception as e:
        log.warning("[cheat_sheet] EM signal failed for %s: %s", ticker, e)

    # GEX × EM Confluence Verdict
    try:
        from scripts.trader.signals.gex_em_confluence import compute_gex_em_verdict, format_confluence_block
        # Get GEX regime from META_ fields
        meta = parse_meta_fields(unified_entry) if unified_entry else {}
        gex_regime = "NEGATIVE" if meta.get("GEX_TOTAL", 0) < 0 else "POSITIVE" if meta.get("GEX_TOTAL", 0) > 0 else "NEUTRAL"
        regime_label = meta.get("REGIME", "NEUTRAL")
        # Get levels from tokens
        tokens = unified_entry.get("tokens", []) if unified_entry else []
        cw = next((t["strike"] for t in tokens if t.get("label") == "CW"), None)
        pw = next((t["strike"] for t in tokens if t.get("label") == "PW"), None)
        gm = next((t["strike"] for t in tokens if "MAGNET" in t.get("label", "")), None)
        # Get EM bounds from em_data
        em_upper = em_data.get("em_upper") if em_data else None
        em_lower = em_data.get("em_lower") if em_data else None
        if em_upper and em_lower and ticker_spot > 0:
            verdict = compute_gex_em_verdict(
                gex_regime=gex_regime,
                regime_label=regime_label,
                em_upper=em_upper,
                em_lower=em_lower,
                spot=ticker_spot,
                call_wall=cw,
                put_wall=pw,
                gamma_magnet=gm,
            )
            sections.append(format_confluence_block(verdict))
    except Exception as e:
        log.warning("[cheat_sheet] GEX×EM confluence failed for %s: %s", ticker, e)

    # Prior EOD plan
    try:
        from scripts.trader.daily_narrative import get_previous_eod_plan
        prior_plan = run_async_safely(get_previous_eod_plan())
    except Exception as e:
        log.warning("[cheat_sheet] Prior EOD plan fetch failed: %s", e)
        prior_plan = "No previous EOD plan available."
    sections.append("== PRIOR EOD PLAN (overnight continuity) ==\n" + prior_plan)

    # Bias grade feedback
    try:
        grades = get_recent_bias_accuracy(n=5)
        if grades["total"] > 0:
            sections.append(_format_bias_grade_block(grades))
    except Exception as e:
        log.warning("[cheat_sheet] Bias grades failed: %s", e)

    # Bias Consensus Matrix
    try:
        modifiers = get_weekly_modifiers(target_date, econ_releases)
        mod_strings = []
        if modifiers["is_triple_witching_week"]:
            mod_strings.append("TRIPLE WITCHING WEEK")
        elif modifiers["is_opex_week"]:
            mod_strings.append("OPEX WEEK")
        if modifiers["is_fomc_week"]:
            mod_strings.append("FOMC WEEK")
        mod_str = " | ".join(mod_strings) if mod_strings else "Standard Week"
        
        im_chg_nq = nq_ctx.get('change_pct', 0) if nq_ctx else 0
        im_chg_es = es_ctx.get('change_pct', 0) if es_ctx else 0
        im_sig = 'Risk-Off' if im_chg_nq < 0 and im_chg_es < 0 else ('Risk-On' if im_chg_nq > 0 and im_chg_es > 0 else 'Mixed')
        
        prth_h = ticker_ctx.get('prior_rth_high') if ticker_ctx else None
        prth_l = ticker_ctx.get('prior_rth_low') if ticker_ctx else None
        if prth_h is not None and prth_l is not None and prth_h > 0 and prth_l > 0 and ticker_spot:
            if ticker_spot > prth_h:
                rth_sig = 'Gap Up'
            elif ticker_spot < prth_l:
                rth_sig = 'Gap Down'
            else:
                rth_sig = 'Inside Range'
        else:
            rth_sig = 'Inside Range'
        
        matrix = [
            f"== BIAS CONSENSUS MATRIX ({mod_str}) ==",
            f"| Component ({base_label}) | Signal | Context |",
            "|---|---|---|",
            f"| Macro Intermarket | {im_sig} | Divergence checks applied |",
            f"| RTH Open | {rth_sig} | Open Scenario |",
            f"| GEX | {ticker_gex.get('bias', 'N/A')} | {ticker_gex.get('regime', 'N/A')} regime |",
            f"| ALN Pattern | {aln_data.get('bias', 'N/A')} | {aln_data.get('aln', 'N/A')} |",
        ]
        # Add delivery triad 1-liner to the matrix
        try:
            from scripts.trader.signals.intraday_blocks import _format_delivery_triad_1liner
            _triad = _format_delivery_triad_1liner(ticker, ticker_spot, target_date)
            if _triad:
                matrix.append(f"| Delivery Triad | {_triad} | I2E/E2I mode |")
        except Exception:
            pass
        sections.insert(0, "\n".join(matrix))
    except Exception as e:
        log.warning("[cheat_sheet] Matrix failed: %s", e)

    # ── AM time windows + post-news management (open mode) ──
    try:
        _dt = classify_day_type([], target_date)
        _am_map = build_ict_time_map(_dt.get("day_type", "clean"), target_date, mode="open")
        if _am_map:
            sections.append(_am_map)
        _news_mgmt = build_post_news_management_block(_dt.get("day_type", "clean"))
        if _news_mgmt:
            sections.append(_news_mgmt)
    except Exception as e:
        log.warning("[cheat_sheet] AM time windows failed: %s", e)

    return "\n\n".join(sections)


def build_intraday_context(
    loader: DataLoader | None = None,
    ticker: str = "NQ1",
    es_ticker: str = "ES1",
    target_date: date | None = None,
    now_et: datetime | None = None,
) -> str:
    """Build the session-adaptive intraday cheat sheet.

    Detects the current trading session (Asia, London, NY AM, NY Lunch, NY PM)
    and assembles only the blocks relevant to that session. Weekend and after-close
    are handled gracefully.

    When now_et is provided (simulation mode), data is filtered to index <= now_et
    so the cheat sheet sees exactly what it would have seen at that moment.
    """
    import pytz
    from scripts.trader.signals.intraday_blocks import build_intraday_cheat_sheet

    if target_date is None:
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            df_t = load_fused_data(ticker, timeframe="1m", require_historical=False)
            target_date = get_latest_rth_date(df_t)
        except Exception:
            target_date = datetime.now(ET).date()

    # Load 1m data with ET-localized index
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_t = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_t is not None and not df_t.empty:
            if df_t.index.tz is None:
                df_t.index = pd.DatetimeIndex(df_t.index).tz_localize("UTC").tz_convert(ET)
            elif df_t.index.tz != ET:
                df_t.index = df_t.index.tz_convert(ET)
    except Exception as e:
        log.warning("[intraday] Failed to load 1m data: %s", e)
        df_t = None

    # Filter data to simulation time if provided
    if now_et is not None and df_t is not None and not df_t.empty:
        df_t = df_t[df_t.index <= now_et]
        log.info("[intraday] Filtered to %d bars (up to %s)", len(df_t), now_et.strftime("%H:%M ET"))

    if now_et is None:
        now_et = datetime.now(pytz.timezone("America/New_York"))
    return build_intraday_cheat_sheet(df_t, ticker, target_date, now_et=now_et)


def build_eod_context(
    loader: DataLoader | None = None,
    ticker: str = "NQ1",
    target_date: date | None = None,
) -> str:
    """Build the EOD cheat sheet for the 16:05 ET close review.

    Focuses on: session summary, morning bias grade, level outcomes,
    ALN outcome, tomorrow's calendar and setup.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=2)

    if target_date is None:
        try:
            from scripts.utils.fused_data_loader import load_fused_data
            df_t = load_fused_data(ticker, timeframe="1m", require_historical=False)
            target_date = get_latest_rth_date(df_t)
        except Exception:
            target_date = datetime.now(ET).date()

    sections: list[str] = []

    # ── Morning bias (from ticker-specific open narrative) ──
    base_label = ticker.replace("1", "").upper()
    morning_narrative_path = OPTIONS_DATA_DIR / "daily" / f"latest_trader_narrative_open_{ticker}.md"
    if not morning_narrative_path.exists():
        morning_narrative_path = OPTIONS_DATA_DIR / "daily" / "latest_trader_narrative_open.md"
    if morning_narrative_path.exists():
        morning_text = morning_narrative_path.read_text(encoding="utf-8")
        morning_summary = morning_text[:400] + "..." if len(morning_text) > 400 else morning_text
        sections.append("== MORNING BIAS ==\n" + morning_summary)
    else:
        sections.append("== MORNING BIAS ==\nNo morning narrative available.")

    # ── Today's session (from 1m parquet) ──
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_t = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_t is not None and df_t.index.tz is None:
            df_t.index = pd.DatetimeIndex(df_t.index).tz_localize("UTC").tz_convert(ET)
        elif df_t is not None and df_t.index.tz != ET:
            df_t.index = df_t.index.tz_convert(ET)
        
        today_930 = pd.Timestamp(target_date).tz_localize(ET) + pd.Timedelta(hours=9, minutes=30)
        today_1600 = pd.Timestamp(target_date).tz_localize(ET) + pd.Timedelta(hours=16, minutes=0)
        
        lines = ["== TODAY'S SESSION =="]
        base_label = ticker.replace("1", "").upper()
        if df_t is None or df_t.empty:
            lines.append(f"{base_label}: No data")
        else:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if rth.empty:
                lines.append(f"{base_label}: No RTH data")
            else:
                rth_open = float(rth["open"].iloc[0])
                rth_close = float(rth["close"].iloc[-1])
                rth_high = float(rth["high"].max())
                rth_low = float(rth["low"].min())
                chg = (rth_close / rth_open - 1) * 100
                body = abs(rth_close - rth_open)
                lines.append(f"{base_label}: Open {rth_open:,.2f} → Close {rth_close:,.2f} ({chg:+.2f}%) | H: {rth_high:,.2f} L: {rth_low:,.2f} | Body: {body:,.2f}")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Session data failed: %s", e)
        sections.append("== TODAY'S SESSION ==\nSession data unavailable")

    # Delivery triad at EOD — shows the final delivery mode for the day
    try:
        from scripts.trader.signals.intraday_blocks import _format_delivery_triad_1liner
        _eod_close = float(df_t["close"].iloc[-1]) if df_t is not None and not df_t.empty else 0.0
        _triad = _format_delivery_triad_1liner(ticker, _eod_close, target_date)
        if _triad:
            sections.append(f"== EOD DELIVERY ==\n{_triad}")
    except Exception:
        pass

    # ── Level outcomes ──
    try:
        unified = load_macro_levels(session="open")
        base_label = ticker.replace("1", "").upper()
        ticker_unified = unified.get(base_label) or unified.get(ticker) or {}
        ticker_gex = _extract_gex_levels(ticker_unified, base_label)
        ticker_close = 0.0
        if df_t is not None and not df_t.empty:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if not rth.empty:
                ticker_close = float(rth["close"].iloc[-1])

        lines = [f"== LEVEL OUTCOMES ({base_label}) =="]
        if ticker_gex and ticker_close > 0:
            cw = ticker_gex.get("call_wall")
            pw = ticker_gex.get("put_wall")
            flip = ticker_gex.get("flip") or ticker_gex.get("zero_gamma")
            if cw:
                lines.append(f"Call Wall ({cw:,.2f}): {'BROKEN' if ticker_close > cw else 'HELD'} (close {ticker_close:,.2f})")
            if pw:
                lines.append(f"Put Wall ({pw:,.2f}): {'BROKEN' if ticker_close < pw else 'HELD'} (close {ticker_close:,.2f})")
            if flip:
                lines.append(f"Gamma Flip ({flip:,.2f}): {'above' if ticker_close > flip else 'below'} at close")
        else:
            lines.append("No GEX data available for open session.")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Level outcomes failed: %s", e)

    # ── GEX Regime Shift (open -> close) ──
    # The open-snapshot walls are the day's starting structure (graded above).
    # The close-snapshot walls are TOMORROW's starting structure. Surfacing
    # the delta tells the LLM (and the trader) how dealer positioning migrated
    # intraday — the most forward-looking signal the options pipeline makes.
    try:
        open_unified = load_macro_levels(session="open")
        close_unified = load_macro_levels(session="close")
        ticker_open_gex = _extract_gex_levels(
            open_unified.get(base_label) or open_unified.get(ticker) or {},
            base_label,
        )
        ticker_close_gex = _extract_gex_levels(
            close_unified.get(base_label) or close_unified.get(ticker) or {},
            base_label,
        )
        shift_lines = [f"== GEX REGIME SHIFT ({base_label}, open -> close) =="]
        if ticker_open_gex or ticker_close_gex:
            o_cw = ticker_open_gex.get("call_wall")
            c_cw = ticker_close_gex.get("call_wall")
            o_pw = ticker_open_gex.get("put_wall")
            c_pw = ticker_close_gex.get("put_wall")
            o_flip = ticker_open_gex.get("flip") or ticker_open_gex.get("zero_gamma")
            c_flip = ticker_close_gex.get("flip") or ticker_close_gex.get("zero_gamma")
            o_mag = ticker_open_gex.get("gamma_magnet")
            c_mag = ticker_close_gex.get("gamma_magnet")
            o_regime = ticker_open_gex.get("regime", "?")
            c_regime = ticker_close_gex.get("regime", "?")
            o_bias = ticker_open_gex.get("bias", "?")
            c_bias = ticker_close_gex.get("bias", "?")

            def _delta(old, new):
                if old and new:
                    d = new - old
                    return f"{d:+.2f}"
                return "n/a"

            def _fmt(val):
                """Format a price value, handling None gracefully."""
                return f"{val:,.2f}" if val is not None else "n/a"

            shift_lines.append(
                f"Call Wall: {_fmt(o_cw)} -> {_fmt(c_cw)} ({_delta(o_cw, c_cw)}) [tomorrow's ceiling]"
            )
            shift_lines.append(
                f"Put Wall:  {_fmt(o_pw)} -> {_fmt(c_pw)} ({_delta(o_pw, c_pw)}) [tomorrow's floor]"
            )
            if o_flip is not None or c_flip is not None:
                shift_lines.append(
                    f"Gamma Flip: {_fmt(o_flip)} -> {_fmt(c_flip)} ({_delta(o_flip, c_flip)})"
                )
            if o_mag is not None or c_mag is not None:
                shift_lines.append(
                    f"Price Magnet: {_fmt(o_mag)} -> {_fmt(c_mag)} ({_delta(o_mag, c_mag)})"
                )
            shift_lines.append(
                f"Regime/Bias: {o_regime}/{o_bias} -> {c_regime}/{c_bias}"
            )
            # Flag a collapsing wall — a large intraday wall roll is a
            # high-signal event the LLM should emphasise in "Tomorrow".
            if o_cw and c_cw and abs(c_cw - o_cw) > 20:
                shift_lines.append(
                    f"⚠ Call Wall rolled {abs(c_cw - o_cw):.2f}pts intraday — dealer ceiling shifted; "
                    f"{'rolled DOWN into close (bears re-priced ceiling lower)' if c_cw < o_cw else 'rolled UP into close (bulls re-priced ceiling higher)'}."
                )
            if o_pw and c_pw and abs(c_pw - o_pw) > 20:
                shift_lines.append(
                    f"⚠ Put Wall rolled {abs(c_pw - o_pw):.2f}pts intraday — dealer floor shifted; "
                    f"{'rolled DOWN into close (bears re-priced floor lower)' if c_pw < o_pw else 'rolled UP into close (bulls re-priced floor higher)'}."
                )
        else:
            shift_lines.append("No close-snapshot GEX data — regime shift unavailable.")
        sections.append("\n".join(shift_lines))
    except Exception as e:
        log.warning("[eod] GEX regime shift failed: %s", e)

    # ── Next Session Econ Releases & Earnings ──
    async def run_async_eod_signals(next_day: date):
        from prisma import Prisma
        _ensure_database_url()
        db = Prisma()
        await db.connect()
        try:
            from scripts.libs_py.strategy_engine.services.broker_service import BrokerService
            broker = BrokerService()
            
            # Fetch econ events
            from scripts.trader.signals.econ_calendar import get_econ_releases
            econ_releases = await get_econ_releases(next_day, db)
            
            # Fetch earnings
            from scripts.trader.signals.earnings import fetch_earnings_events
            db_path = str(REPO_ROOT / "web" / "prisma" / "dev.db")
            earnings_list = await fetch_earnings_events(next_day, db_path, broker)
        finally:
            await db.disconnect()
        return econ_releases, earnings_list

    try:
        next_trading_day = target_date + timedelta(days=1)
        while next_trading_day.weekday() in (5, 6):
            next_trading_day += timedelta(days=1)
            
        econ_releases, earnings_data = run_async_safely(run_async_eod_signals(next_trading_day))
        
        sections.append(_format_scheduled_risk_block(econ_releases).replace("== SCHEDULED RISK ==", "== NEXT SESSION SCHEDULED RISK =="))
        sections.append(_format_earnings_block(earnings_data).replace("== EARNINGS CATALYSTS ==", "== NEXT SESSION EARNINGS CATALYSTS =="))
    except Exception as e:
        log.warning("[eod] Next session signals failed: %s", e)

    # ── Tomorrow's setup ──
    try:
        if df_t is not None and not df_t.empty:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if not rth.empty:
                prth_high = float(rth["high"].max())
                prth_low = float(rth["low"].min())
                prth_close = float(rth["close"].iloc[-1])
                lines = ["== TOMORROW'S SETUP =="]
                lines.append(f"pRTH High: {prth_high:,.2f} | pRTH Low: {prth_low:,.2f} | Close: {prth_close:,.2f}")
                lines.append(f"Overnight open vs pRTH will determine Gap Up/Down/Inside scenario")
                
                # Fetch Candle Science scenarios for tomorrow's open
                try:
                    cs = get_candle_science_read(ticker=ticker, mode="close")
                    lines.append("")  # blank line separator
                    lines.append(format_candle_science_block(cs))
                except Exception as cs_err:
                    log.warning("[eod] Candle science scenarios failed: %s", cs_err)
                
                sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Tomorrow setup failed: %s", e)

    # ── Phase F: Bias grade feedback loop ──
    try:
        # Morning bias: read the dominant directional lean from the open-mode
        # confluence block (written this morning to the open narrative file).
        morning_narrative_path = OPTIONS_DATA_DIR / "daily" / f"latest_trader_narrative_open_{ticker}.md"
        if not morning_narrative_path.exists():
            morning_narrative_path = OPTIONS_DATA_DIR / "daily" / "latest_trader_narrative_open.md"
        morning_confluence = "NEUTRAL"
        morning_confluence_level = "LOW"
        if morning_narrative_path.exists():
            morning_text = morning_narrative_path.read_text(encoding="utf-8")
            # Extract Confluence line if present, e.g.:
            # "Confluence: HIGH → sizing 100%" or "Confluence: HIGH | Sizing: 100%"
            for line in morning_text.splitlines():
                if line.startswith("Confluence:"):
                    parts = line.split("|")
                    first = parts[0].strip()
                    # Handle old and new formats
                    level = first.replace("Confluence:", "").strip().split()[0]
                    morning_confluence_level = level if level in {"HIGH", "MEDIUM", "LOW"} else "LOW"
                    break

        # Determine actual directional outcome from today's close vs RTH open.
        actual_outcome = "NEUTRAL"
        if df_t is not None and not df_t.empty:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if not rth.empty:
                rth_open = float(rth["open"].iloc[0])
                rth_close = float(rth["close"].iloc[-1])
                if rth_close > rth_open:
                    actual_outcome = "BULLISH"
                elif rth_close < rth_open:
                    actual_outcome = "BEARISH"

        # Morning bias direction is the confluence-dominant direction from open.
        # We recompute it from the same raw signals used by build_trader_cheat_sheet
        # so the grade is deterministic and not prompt-dependent.
        s1 = "NEUTRAL"
        s2 = "NEUTRAL"
        s3 = "NEUTRAL"
        aln_pattern = ""
        try:
            # Reuse open-mode logic with fresh data for today only.
            nq_ctx_morning = build_overnight_context(loader, ticker, target_date)
            df_t_recent = df_t[df_t.index >= (pd.Timestamp.now(ET) - timedelta(days=10))]
            if df_t_recent.empty:
                df_t_recent = df_t
            engine = NQStatsEngine(df_t_recent, ticker=ticker)
            engine.process()
            latest = engine.get_latest_status()
            aln_pattern = latest.get("aln", "N/A")
            broken = latest.get("broken", "N/A")
            from scripts.libs_py.nqstats.classifiers import compute_aln_bias, compute_rth_bias
            _aln_b = compute_aln_bias(aln_pattern, broken)
            aln_bias = _aln_b["bias"]
            s1 = "BULLISH" if "BULLISH" in aln_bias else ("BEARISH" if "BEARISH" in aln_bias else "NEUTRAL")

            _rth_b = compute_rth_bias(
                nq_ctx_morning.get("close", 0) if nq_ctx_morning else None,
                nq_ctx_morning.get("prior_rth_high") if nq_ctx_morning else None,
                nq_ctx_morning.get("prior_rth_low") if nq_ctx_morning else None,
            )
            rth_scenario = _rth_b["scenario"]
            s2 = _rth_b["bias"]

            try:
                cs = get_candle_science_read(ticker=ticker)
                s3 = "BULLISH" if (cs and cs.get("p_bull", 50) > cs.get("p_bear", 50)) else ("BEARISH" if (cs and cs.get("p_bear", 50) > cs.get("p_bull", 50)) else "NEUTRAL")
            except Exception:
                pass

            conf = assess_confluence(s1, s2, s3)
            morning_bias = "NEUTRAL"
            if conf.get("confluence") == "HIGH":
                morning_bias = conf.get("overnight_signal", "NEUTRAL")
            elif conf.get("confluence") == "MEDIUM":
                signals = [conf.get("overnight_signal"), conf.get("rth_open_signal"), conf.get("daily_chart_signal")]
                bull = signals.count("BULLISH")
                bear = signals.count("BEARISH")
                morning_bias = "BULLISH" if bull > bear else ("BEARISH" if bear > bull else "NEUTRAL")
            # If confluence is LOW, leave bias NEUTRAL — no directional call was made.

            correct = (morning_bias == actual_outcome) and morning_bias != "NEUTRAL"
            write_bias_grade(
                morning_bias=morning_bias,
                actual_outcome=actual_outcome,
                correct=correct,
                pattern=aln_pattern,
                confluence_level=morning_confluence_level,
            )
        except Exception:
            pass
    except Exception as e:
        log.warning("[eod] Bias grade recording failed: %s", e)

    # ── ICT Feature Blocks (forward-looking: unfilled gaps, imbalances, KZ pivots, IPDA) ──
    try:
        from scripts.trader.signals.intraday_blocks import (
            _format_kz_pivots_block,
            _format_ipda_block,
            _format_imbalance_block,
            _format_gaps_block,
        )
        from scripts.trader.signals.ict_data_loader import compute_ict_daily_bias, compute_ftfc
        import pytz
        now_et = datetime.now(pytz.timezone("America/New_York"))
        ticker_close = 0.0
        if df_t is not None and not df_t.empty:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if not rth.empty:
                ticker_close = float(rth["close"].iloc[-1])

        # FTFC Bias (Full Timeframe Continuity — the PRIMARY directional bias)
        ftfc = compute_ftfc(ticker, ticker_close, now_et)
        ftfc_lines = ["== FTFC BIAS (Full Timeframe Continuity) =="]
        candle = ftfc.get("candle_ftfc", {})
        ms = ftfc.get("ms_ftfc", {})
        sma = ftfc.get("sma_200", {})
        ftfc_lines.append(f"Candle FTFC: {candle.get('bias', 'N/A')} [{candle.get('alignment', 'N/A')}]")
        ftfc_lines.append(f"MS FTFC: {ms.get('bias', 'N/A')} [{ms.get('alignment', 'N/A')}]")
        ftfc_lines.append(f"200 SMA: {sma.get('direction', 'N/A')}")
        sess = ftfc.get("session_bias", {})
        ftfc_lines.append(f"Session Bias: {sess.get('bias', 'N/A')} via {sess.get('model', 'N/A')} ({sess.get('confidence', 0)}%)")
        ftfc_lines.append(f"Summary: {ftfc.get('summary', 'N/A')}")
        sections.append("\n".join(ftfc_lines))

        sections.append(_format_kz_pivots_block(ticker, ticker_close, "CLOSE"))
        sections.append(_format_ipda_block(ticker, ticker_close))
        sections.append(_format_imbalance_block(ticker, ticker_close, target_date, now_et))
        sections.append(_format_gaps_block(ticker, ticker_close))
    except Exception as e:
        log.warning("[eod] ICT feature blocks failed: %s", e)

    # ── ICT Dealing Range outcome ──
    try:
        ticker_close = 0.0
        if df_t is not None and not df_t.empty:
            rth = df_t[(df_t.index >= today_930) & (df_t.index <= today_1600)]
            if not rth.empty:
                ticker_close = float(rth["close"].iloc[-1])
        ict = compute_ict_from_htf(ticker=ticker, current_price=ticker_close)
        lines = [f"== ICT DEALING RANGE OUTCOME ({base_label}) =="]
        if ict.get("pdh"):
            lines.append(f"PDH: {ict['pdh']:,.2f} | PDL: {ict['pdl']:,.2f} | Midnight: {ict.get('midnight_open') or 'N/A'}")
            lines.append(f"Close in {ict.get('premium_discount','unknown')} ({ict.get('dealing_range_pct','?')}% of range)")
            if ict.get("bsl_target"):
                lines.append(f"BSL (buy stops above PDH): {ict['bsl_target']:,.2f} — {'SWEPT' if ticker_close > ict['bsl_target'] else 'HELD'}")
            if ict.get("ssl_target"):
                lines.append(f"SSL (sell stops below PDL): {ict['ssl_target']:,.2f} — {'SWEPT' if ticker_close < ict['ssl_target'] else 'HELD'}")
        else:
            lines.append("ICT data unavailable")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] ICT dealing range failed: %s", e)

    # ── Tomorrow's preview + weekly position (close mode) ──
    try:
        _modifiers = get_weekly_modifiers(target_date, [])
        _tomorrow_preview = build_weekly_event_timeline(target_date, [], _modifiers, mode="close")
        if _tomorrow_preview:
            sections.append(_tomorrow_preview)
        _tomorrow_times = build_ict_time_map("clean", target_date, mode="close")
        if _tomorrow_times:
            sections.append(_tomorrow_times)
    except Exception as e:
        log.warning("[eod] Tomorrow preview failed: %s", e)

    return "\n\n".join(sections)
    """Build a compact weekly briefing for the LLM.

    The weekly narrative covers multiple tickers (not just SPY/QQQ) because
    it's a macro horizon briefing. But we can still optimize by:
    - Dropping pre-written scenario text (bullish/bearish/neutral) — the LLM
      writes its own scenarios, so feeding it ~300 tokens/ticker of pre-written
      text is waste.
    - Dropping institutional_volatility_context (~218 tokens/ticker) — VIX/VVIX
      is the same for all tickers and can be stated once at the top.
    - Stripping meta fields (id, generated_at, tickers_covered).

    Saves ~800+ tokens vs raw TOON.
    """
    import json as _json

    tickers_raw = briefing_data.get("tickers", [])
    events = briefing_data.get("economic_events", [])

    # Extract VIX/VVIX once from the first ticker's vol context (same for all)
    vix = vvix = dist_21ema = dist_200sma = None
    for t in tickers_raw:
        vc = t.get("institutional_volatility_context", {})
        if vc:
            vix = vc.get("vix")
            vvix = vc.get("vvix")
            dist_21ema = vc.get("dist_21_ema_pct")
            dist_200sma = vc.get("dist_200_sma_pct")
            break

    def _compact_weekly_ticker(t: dict) -> dict:
        proxy_context = t.get("proxy_context", {})
        return {
            "ticker": t.get("ticker"),
            "asset": t.get("asset"),
            "spot": t.get("spot_price"),
            "proxy_symbol": proxy_context.get("proxy_symbol"),
            "futures_symbol": proxy_context.get("futures_symbol"),
            "spot_proxy": proxy_context.get("spot_proxy"),
            "prior_week_change_pct": t.get("prior_week", {}).get("change_pct"),
            "prior_week_range_pct": t.get("prior_week", {}).get("range_pct"),
            "momentum_5d": t.get("recent_momentum", {}).get("last_5d_change_pct"),
            "momentum_10d": t.get("recent_momentum", {}).get("last_10d_change_pct"),
            "trend": t.get("recent_momentum", {}).get("trend"),
            "regime": t.get("gex_regime", {}).get("label"),
            "gex_sign": t.get("gex_regime", {}).get("gex_sign"),
            "total_gex": t.get("gex_regime", {}).get("total_gex"),
            "concentration": t.get("gex_regime", {}).get("concentration_score"),
            "mandated_track": t.get("mandated_execution_track"),
            "call_wall": t.get("key_levels", {}).get("call_wall"),
            "call_wall_proxy": proxy_context.get("call_wall_proxy"),
            "put_wall": t.get("key_levels", {}).get("put_wall"),
            "put_wall_proxy": proxy_context.get("put_wall_proxy"),
            "zero_gamma": t.get("key_levels", {}).get("zero_gamma"),
            "zero_gamma_proxy": proxy_context.get("zero_gamma_proxy"),
            "gamma_magnet": t.get("key_levels", {}).get("gamma_magnet"),
            "gamma_magnet_proxy": proxy_context.get("gamma_magnet_proxy"),
            "pin_strike": t.get("key_levels", {}).get("pin_strike"),
            "pin_odds": t.get("key_levels", {}).get("pin_odds"),
            "wall_separation": t.get("key_levels", {}).get("wall_separation"),
            "atm_iv": t.get("volatility", {}).get("atm_iv"),
            "skew_premium": t.get("volatility", {}).get("skew_premium"),
            "skew_direction": t.get("volatility", {}).get("skew_direction"),
            "hedge_flow_bias": t.get("hedge_flows", {}).get("bias"),
            "bullish_inv": t.get("account_invalidation", {}).get("bullish_invalidation"),
            "bullish_inv_proxy": proxy_context.get("bullish_invalidation_proxy"),
            "bearish_inv": t.get("account_invalidation", {}).get("bearish_invalidation"),
            "bearish_inv_proxy": proxy_context.get("bearish_invalidation_proxy"),
            "dist_to_bullish_inv_pct": t.get("account_invalidation", {}).get("distance_to_bullish_inv_pct"),
            "dist_to_bearish_inv_pct": t.get("account_invalidation", {}).get("distance_to_bearish_inv_pct"),
            "invalidation_mandate": t.get("account_invalidation", {}).get("mandate"),
        }

    compact = {
        "week_start": briefing_data.get("meta", {}).get("week_start_date", ""),
        "week_end": briefing_data.get("meta", {}).get("week_end_date", ""),
        "market_context": {
            "vix": vix,
            "vvix": vvix,
            "dist_21_ema_pct": dist_21ema,
            "dist_200_sma_pct": dist_200sma,
        },
        "events": events,
        "tickers": [_compact_weekly_ticker(t) for t in tickers_raw],
    }
    return _json.dumps(compact, indent=2, ensure_ascii=False)


def _fmt_num(value: Any, decimals: int = 2) -> str:
    """Format a numeric value for markdown output."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def format_translated_level_display(
    translated_value: Any,
    proxy_symbol: str | None = None,
    proxy_value: Any = None,
    decimals: int = 2,
) -> str:
    """Format translated futures levels with optional raw proxy value in brackets."""
    translated = _fmt_num(translated_value, decimals)
    if proxy_symbol and proxy_value is not None:
        proxy = _fmt_num(proxy_value, decimals)
        return f"{translated} ({proxy_symbol} {proxy})"
    return translated


def format_weekly_event_heading(event: dict) -> str:
    """Render a deterministic event heading for the weekly summary."""
    day = event.get("day_of_week") or "[Day]"
    date_str = event.get("date") or "[Date]"
    time_et = event.get("time_et") or "[Time ET]"
    name = event.get("name") or "[Event Name]"
    try:
        dt = datetime.fromisoformat(date_str)
        date_label = dt.strftime("%B %d")
    except ValueError:
        date_label = date_str
    return f"- **{day}, {date_label} ({time_et.replace(' ET', '')} ET)** -- {name}"


def determine_weekly_archetype(events: list[dict]) -> dict:
    """Determine the ICT Weekly Profile Archetype based on the upcoming news calendar.

    Priority waterfall (highest wins):
      1. FOMC — always dominant
      2. Multi-day High-Impact Cluster (3+ high-impact days) — pinball/whipsaw week
      3. CPI week (early Tue catalyst leads rest-of-week trend)
      4. NFP/Friday print — Seek & Destroy chop into the number
      5. Wednesday single catalyst — FOMC-style compression then expansion
      6. Classic Tuesday H/L of the Week
    """
    if not events:
        return {
            "archetype": "Classic Tuesday H/L of the Week",
            "read": "No major catalysts. Expect Monday/Tuesday to set the high or low of the week.",
            "execution": "Trade the standard daily profiles. Fade extremes early week."
        }

    has_fomc = False
    has_nfp = False
    has_cpi = False
    has_ppi = False
    has_claims = False
    high_impact_days: set[str] = set()
    wed_high_impact = False
    fri_high_impact = False
    early_high_impact = False

    for event in events:
        impact = str(event.get("impact", "")).upper()
        name = str(event.get("name", "")).upper()
        day = str(event.get("day_of_week", "")).upper()

        if impact == "HIGH":
            if "FOMC" in name: has_fomc = True
            if "NFP" in name or ("NON" in name and "FARM" in name): has_nfp = True
            if "CPI" in name or "CONSUMER PRICE" in name: has_cpi = True
            if "PPI" in name or "PRODUCER PRICE" in name: has_ppi = True
            if "JOBLESS" in name or "CLAIMS" in name or "UNEMPLOYMENT" in name: has_claims = True

            high_impact_days.add(day)
            if day == "WEDNESDAY": wed_high_impact = True
            if day == "FRIDAY": fri_high_impact = True
            if day in ["MONDAY", "TUESDAY"]: early_high_impact = True

    # Count distinct days with high-impact events
    num_high_impact_days = len(high_impact_days)

    # 1. FOMC always takes priority
    if has_fomc:
        return {
            "archetype": "Wednesday News-Driven Expansion",
            "read": "FOMC week. Market will consolidate Mon-Tue, then expand violently on the announcement.",
            "execution": "Reduce size Mon-Tue. Trade the post-FOMC directional distribution Wed-Fri."
        }

    # 2. Multi-day cluster (CPI + PPI + Claims or any 3+ high-impact days)
    if num_high_impact_days >= 3 or (has_cpi and has_ppi and has_claims):
        evt_labels = [e.get("name", "") for e in events if str(e.get("impact", "")).upper() == "HIGH"]
        evt_str = ", ".join(list(dict.fromkeys(evt_labels))[:3]) if evt_labels else "economic releases"
        return {
            "archetype": "High-Impact Cluster Week",
            "read": f"Multiple tier-1 catalysts across {num_high_impact_days}+ days ({evt_str}). Expect repricing after each print. "
                    "The week will be volatile throughout — not just mid-week.",
            "execution": "Trade reactively, not predictively. Wait for post-print settlement before entering. "
                         "Use tight stops. Respect post-catalyst direction and size down during major data releases."
        }

    # 3. CPI-led early week (dominant single catalyst)
    if has_cpi or early_high_impact:
        return {
            "archetype": "Early Week Catalyst Profile",
            "read": "CPI or major early-week catalyst. Expect violent repricing Tue morning, "
                    "followed by a sustained directional trend for the rest of the week.",
            "execution": "Do NOT pre-position. Wait for the initial news volatility to settle (30-60 min), "
                         "then join the new trend for Wed-Fri."
        }

    # 4. NFP or heavy Friday print
    if has_nfp or fri_high_impact:
        return {
            "archetype": "Seek & Destroy (Broad Chop)",
            "read": "Expect wide, sweeping liquidity runs on both sides Mon-Thu leading into Friday's print.",
            "execution": "Do not trust breakouts Mon-Thu. Fade extremes and target internal liquidity. "
                         "Trade the NFP release on Friday reactively."
        }

    # 5. Isolated Wednesday catalyst
    if wed_high_impact:
        return {
            "archetype": "Wednesday News-Driven Expansion",
            "read": "Single mid-week catalyst. Market will consolidate Mon-Tue, then expand on the print.",
            "execution": "Reduce size Mon-Tue. Trade the post-news distribution Wed-Fri."
        }

    # 6. Default
    return {
        "archetype": "Classic Tuesday H/L of the Week",
        "read": "Standard week. Expect Monday/Tuesday to set the high or low of the week.",
        "execution": "Standard execution. Identify the weekly extreme by Tuesday NY close and trade away from it."
    }


def build_intermarket_macro_summary(quotes: dict | None = None, nq_spot: float | None = None, es_spot: float | None = None) -> dict:
    """Format Intermarket Macro metrics into structured values for briefings & cheat sheets.

    - 10-Yr Treasury Yield (TNX)
    - US Dollar Index (DXY)
    - Brent Crude (Energy)
    - Volatility (VIX & VVIX)
    - NQ/ES Relative Strength Ratio
    """
    if quotes is None:
        quotes = get_intermarket_quotes()

    tnx = quotes.get("tnx", {})
    dxy = quotes.get("dxy", {})
    brent = quotes.get("brent", {})
    vix = quotes.get("vix", {})
    vvix = quotes.get("vvix", {})

    ratio = round(nq_spot / es_spot, 4) if (nq_spot and es_spot and es_spot > 0) else None

    v_val = vix.get("price")
    if v_val:
        if v_val < 15:
            vol_regime = "Low Vol / Complacent (<15)"
        elif v_val < 20:
            vol_regime = "Normal Vol (15-20)"
        elif v_val < 28:
            vol_regime = "Elevated Vol (20-28)"
        else:
            vol_regime = "High Vol / Regime Stress (>28)"
    else:
        vol_regime = "N/A"

    return {
        "us10y": f"{tnx.get('price'):.2f}% ({tnx.get('change'):+.2f}%)" if tnx.get("price") is not None else "N/A",
        "dxy": f"{dxy.get('price'):.2f} ({dxy.get('change'):+.2f}%)" if dxy.get("price") is not None else "N/A",
        "brent": f"${brent.get('price'):.2f} ({brent.get('change'):+.2f}%)" if brent.get("price") is not None else "N/A",
        "vix": f"{vix.get('price'):.2f} ({vix.get('change'):+.2f})" if vix.get("price") is not None else "N/A",
        "vvix": f"{vvix.get('price'):.2f} ({vvix.get('change'):+.2f})" if vvix.get("price") is not None else "N/A",
        "vol_regime": vol_regime,
        "nq_es_ratio": f"{ratio:.4f}" if ratio else "N/A",
    }


def build_weekly_static_template(briefing_data: dict) -> str:
    """Build the deterministic weekly markdown skeleton in Python.

    The LLM fills only bounded analysis slots, while Python renders headings,
    scale-aware numbers, event list formatting, and account protection blocks.
    """
    meta = briefing_data.get("meta", {})
    start_raw = meta.get("week_start_date", "")[:10]
    end_raw = meta.get("week_end_date", "")[:10]
    try:
        start_dt = datetime.fromisoformat(start_raw)
        end_dt = datetime.fromisoformat(end_raw)
        header_dates = f"{start_dt.strftime('%B %d')} - {end_dt.strftime('%B %d, %Y')}"
    except ValueError:
        header_dates = f"{start_raw} - {end_raw}"

    events = briefing_data.get("economic_events", [])
    earnings = briefing_data.get("earnings_events", [])
    tickers = briefing_data.get("tickers", [])
    archetype_info = determine_weekly_archetype(events)

    lines = [
        f"## WEEKLY MACRO EXECUTION HORIZON -- {header_dates}",
        "",
        "### 1. Executive Risk Core & Weekly Profile",
        "{{EXECUTIVE_RISK_CORE}}",
        "",
        "**Expected ICT Weekly Archetype:**",
        f"- **Profile:** {archetype_info['archetype']}",
        f"- **Read:** {archetype_info['read']}",
        f"- **Execution:** {archetype_info['execution']}",
        "",
        "### 2. High-Impact Economic Milestones",
    ]

    if events:
        for index, event in enumerate(events):
            lines.append(format_weekly_event_heading(event))
            lines.append(f"  > **Tactical Impact:** {{{{EVENT_IMPACT_{index}}}}}")
    else:
        lines.append("No market-moving economic events scheduled this week.")

    lines.extend([
        "",
        "### 3. Mega-Cap Earnings Catalysts (index-moving only)",
    ])
    # Filter to only index-moving mega-caps — same filter as the cheat sheet
    INDEX_MOVING_TICKERS = {
        "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META",
        "TSLA", "AVGO", "LLY", "JPM", "V", "UNH", "XOM", "WMT",
        "MA", "ORCL", "COST", "NFLX", "CRM", "AMD", "INTC",
        "IBM", "TXN", "RTX", "AXP", "GS", "MS", "C", "BAC",
        "HD", "DIS", "BABA",
    }
    if earnings:
        for event in earnings:
            name = (event.get("name", "") or "").strip()
            ticker_part = name.replace(" Earnings", "").strip().upper()
            if ticker_part in INDEX_MOVING_TICKERS:
                day = event.get("day_of_week", "Unknown")
                name = event.get("name", "Unknown")
                timing = event.get("timing", "N/A")
                lines.append(f"- **{day}, {timing}**: {name}")
    else:
        lines.append("No index-moving mega-cap earnings scheduled this week.")

    section_idx = 4
    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        proxy_context = ticker_block.get("proxy_context", {})
        proxy_symbol = proxy_context.get("proxy_symbol")

        header = f"### {section_idx}. {ticker} -- Structural Sandbox"
        if ticker == "SPY":
            header = f"### {section_idx}. SPY (MES levels) -- Structural Sandbox"
        elif ticker == "QQQ":
            header = f"### {section_idx}. QQQ (MNQ levels) -- Structural Sandbox"
        section_idx += 1

        spot = format_translated_level_display(
            ticker_block.get("spot_price"),
            proxy_symbol,
            proxy_context.get("spot_proxy"),
        )
        weekly_change = _fmt_pct(ticker_block.get("prior_week", {}).get("change_pct"))
        total_gex = ticker_block.get("gex_regime", {}).get("total_gex")
        total_gex_str = _fmt_num(total_gex, 2)

        key_levels = ticker_block.get("key_levels", {})
        call_wall = format_translated_level_display(
            key_levels.get("call_wall"),
            proxy_symbol,
            proxy_context.get("call_wall_proxy"),
        )
        put_wall = format_translated_level_display(
            key_levels.get("put_wall"),
            proxy_symbol,
            proxy_context.get("put_wall_proxy"),
        )
        zero_gamma = format_translated_level_display(
            key_levels.get("zero_gamma"),
            proxy_symbol,
            proxy_context.get("zero_gamma_proxy"),
        )

        friday_em = ticker_block.get("expected_moves", {}).get("friday", {})
        em_upper = format_translated_level_display(friday_em.get("upper"))
        em_lower = format_translated_level_display(friday_em.get("lower"))
        em_value = _fmt_num(friday_em.get("em"), 2)

        lines.extend([
            "",
            header,
            f"**Spot**: {spot} ({weekly_change}) | **GEX Tape**: {ticker_block.get('gex_regime', {}).get('gex_sign', 'N/A')} / {total_gex_str}",
            f"**Boundaries**: Upside Ceiling {call_wall} | Downside Floor {put_wall} | Volatility Pivot {zero_gamma}",
            f"**Risk Envelope**: Expected High {em_upper} <-> Expected Low {em_lower} (+-{em_value}%)",
        ])

        # Multi-week GEX macro context
        macro_ctx = ticker_block.get("macro_context", {})
        if macro_ctx and macro_ctx.get("summary_str"):
            lines.append(f"**Macro GEX Context**: {macro_ctx['summary_str']}")

        # GEX × EM Confluence verdict
        confluence = ticker_block.get("confluence_verdict", {})
        if confluence and confluence.get("read"):
            lines.append(f"**Confluence**: {confluence['read']}")

        lines.extend([
            "",
            f"**Mandated Track**: {ticker_block.get('mandated_execution_track', 'N/A')} -> {{{{TRACK_NOTE_{ticker}}}}}",
            "",
            "**Scenarios**:",
            f"- Bullish: {{{{BULLISH_SCENARIO_{ticker}}}}}",
            f"- Bearish: {{{{BEARISH_SCENARIO_{ticker}}}}}",
            f"- Range: {{{{RANGE_SCENARIO_{ticker}}}}}",
        ])

    lines.extend([
        "",
        f"### {section_idx}. Account Protection & Invalidation Metrics",
    ])
    section_idx += 1

    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        proxy_context = ticker_block.get("proxy_context", {})
        proxy_symbol = proxy_context.get("proxy_symbol")
        account_inv = ticker_block.get("account_invalidation", {})
        bullish_inv = format_translated_level_display(
            account_inv.get("bullish_invalidation"),
            proxy_symbol,
            proxy_context.get("bullish_invalidation_proxy"),
        )
        bearish_inv = format_translated_level_display(
            account_inv.get("bearish_invalidation"),
            proxy_symbol,
            proxy_context.get("bearish_invalidation_proxy"),
        )
        lines.append(
            f"- **{ticker}**: Fractures at {bullish_inv} (downside) / {bearish_inv} (upside). {account_inv.get('mandate', 'N/A')}"
        )
        lines.append(
            f"- Dist to bullish inv: {_fmt_pct(account_inv.get('distance_to_bullish_inv_pct'))} | Dist to bearish inv: {_fmt_pct(account_inv.get('distance_to_bearish_inv_pct'))}"
        )

    lines.extend([
        "",
        f"### {section_idx}. Possible Weekly Trade Plan",
        "{{WEEKLY_TRADE_PLAN}}",
        "",
        f"### {section_idx+1}. Key Risks This Week",
        "{{KEY_RISKS}}",
        "",
        f"### {section_idx+2}. Watch List",
        "{{WATCH_LIST}}",
    ])

    return "\n".join(lines)


def build_weekly_cheat_sheet(briefing_data: dict) -> str:
    """Build a compact 80-column ASCII Weekly Trader Cheat Sheet.

    Harmonized with the Daily Cheat Sheet design standards.
    Contains cross-market tape, options boundaries, expected moves,
    account invalidation levels, high-impact catalysts, and earnings.
    """
    meta = briefing_data.get("meta", {})
    start_raw = meta.get("week_start_date", "")[:10]
    end_raw = meta.get("week_end_date", "")[:10]
    header_dates = f"{start_raw} -> {end_raw}" if start_raw and end_raw else "CURRENT WEEK"
    generated_at = meta.get("generated_at", "")[:16].replace("T", " ")

    events = briefing_data.get("economic_events", [])
    earnings = briefing_data.get("earnings_events", [])
    tickers = briefing_data.get("tickers", [])
    archetype_info = determine_weekly_archetype(events)

    nq_spot = None
    es_spot = None
    for tb in tickers:
        if tb.get("ticker") in ("NQ", "QQQ"): nq_spot = tb.get("spot_price")
        if tb.get("ticker") in ("ES", "SPY"): es_spot = tb.get("spot_price")
    macro_summary = build_intermarket_macro_summary(nq_spot=nq_spot, es_spot=es_spot)

    border = "═" * 80
    divider = "─" * 80

    lines = [
        border,
        f"  WEEKLY TRADER CHEAT SHEET — HORIZON: {header_dates}",
        f"  Generated: {generated_at} ET",
        border,
        "",
        "[1] INTERMARKET MACRO MATRIX",
        divider,
        f"• US 10-Yr Yield (TNX):  {macro_summary['us10y']:<16} | Dollar Index (DXY): {macro_summary['dxy']}",
        f"• Brent Crude (Energy): {macro_summary['brent']:<16} | Volatility (VIX):   {macro_summary['vix']} ({macro_summary['vol_regime']})",
        f"• Tech/Broad Ratio:     {macro_summary['nq_es_ratio']:<16} | Vol-of-Vol (VVIX):  {macro_summary['vvix']}",
        "",
        "[2] OPTIONS TAPE & GEX POSITIONING",
        divider,
    ]

    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        change_pct = _fmt_pct(ticker_block.get("prior_week", {}).get("change_pct"))
        gex = ticker_block.get("gex_regime", {})
        spot = ticker_block.get("spot_price", 0)
        track = ticker_block.get("mandated_execution_track", "N/A")
        total_gex = gex.get("total_gex", 0) or 0.0
        lines.append(
            f"• {ticker:<4} Spot: {spot:>9,.2f} ({change_pct}) | GEX Tape: {gex.get('gex_sign', 'N/A'):<8} / {total_gex:>13,.2f}"
        )
        lines.append(f"  Mandated Track: {track}")

    lines.extend([
        f"• ICT Profile: {archetype_info['archetype']}",
        f"  Strategy: {archetype_info['execution']}",
    ])

    # ── Weekly Macro Context (multi-week GEX regime) ──
    for ticker_block in tickers:
        macro_ctx = ticker_block.get("macro_context", {})
        if macro_ctx and macro_ctx.get("summary_str"):
            lines.append("")
            lines.append(f"  {ticker_block.get('ticker', '?')} MACRO: {macro_ctx['summary_str']}")

    # ── Weekly Profile Day-by-Day Expectation ──
    # Maps the ICT archetype to a day-by-day behavioral expectation based
    # on ICT weekly profile patterns from the KB.
    profile_lines = ["", "== WEEKLY PROFILE EXPECTATION =="]
    archetype = archetype_info["archetype"]
    if "FOMC" in archetype or "Wednesday News" in archetype:
        profile_lines.extend([
            "Mon-Tue: Range formation / consolidation. Expect Monday to set initial range.",
            "Wed: FOMC/News catalyst → compression pre-announcement, then violent expansion post-announcement.",
            "Thu-Fri: Post-catalyst directional delivery. Trade the new trend established Wednesday.",
        ])
    elif "High-Impact Cluster" in archetype:
        profile_lines.extend([
            "Mon-Tue: Range formation with catalyst-driven repricing after each print. Not a clean trend — expect two-sided volatility.",
            "Wed: Mid-week CSD (Change in State of Delivery) likely — sweep of Mon-Tue range extreme before directional expansion.",
            "Thu-Fri: Continuation or reversal of Wed direction. Friday often marks the weekly extreme (high or low of week).",
        ])
    elif "Early Week Catalyst" in archetype:
        profile_lines.extend([
            "Mon: CPI/catalyst print → violent repricing. Wait 30-60 min post-print for settlement.",
            "Tue-Wed: Sustained directional trend from Monday's catalyst. Trade continuation.",
            "Thu-Fri: Trend continuation or exhaustion. Watch for Friday retracement toward weekly open (NWOG).",
        ])
    elif "Seek & Destroy" in archetype:
        profile_lines.extend([
            "Mon-Thu: Wide, sweeping liquidity runs on both sides. Fade extremes. Do NOT trust breakouts.",
            "Fri: NFP/catalyst print → reactive trade only. Pre-print chop into the number.",
        ])
    else:  # Classic Tuesday H/L
        profile_lines.extend([
            "Mon: Range formation. Identify the weekly open (NWOG) — it's the primary magnet for the week.",
            "Tue: Often sets the High or Low of the week. Trade away from Tuesday's extreme for the rest of the week.",
            "Wed: CSD (Change in State of Delivery) — sweep of Mon-Tue range extreme, then directional expansion.",
            "Thu-Fri: Run in the direction of Wed's CSD. Friday may retrace toward weekly open (NWOG).",
        ])
    # Add opex note if applicable
    modifiers = get_weekly_modifiers(
        datetime.now(ET).date() if 'target_date' not in dir() else target_date,
        events,
    )
    if modifiers.get("is_opex_week"):
        profile_lines.append("⚠ OPEX WEEK: Per KB, Monday-Tuesday tend to trade higher, then sell-off Wednesday. Dealer hedging unwinds into Friday close.")
    if modifiers.get("is_triple_witching_week"):
        profile_lines.append("⚠ TRIPLE WITCHING: Increased volatility from options/futures expiration. Position size down.")
    lines.extend(profile_lines)

    lines.extend([
        "",
        "[3] STRUCTURAL PLAYING FIELD & OPTIONS BOUNDARIES",
        divider,
    ])

    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        proxy_context = ticker_block.get("proxy_context", {})
        proxy_symbol = proxy_context.get("proxy_symbol")
        key_levels = ticker_block.get("key_levels", {})

        cw = format_translated_level_display(key_levels.get("call_wall"), proxy_symbol, proxy_context.get("call_wall_proxy"))
        pw = format_translated_level_display(key_levels.get("put_wall"), proxy_symbol, proxy_context.get("put_wall_proxy"))
        zg = format_translated_level_display(key_levels.get("zero_gamma"), proxy_symbol, proxy_context.get("zero_gamma_proxy"))

        em = ticker_block.get("expected_moves", {}).get("friday", {})
        em_upper = format_translated_level_display(em.get("upper"))
        em_lower = format_translated_level_display(em.get("lower"))

        lines.extend([
            f"• {ticker} Structural Boundaries:",
            f"  - Upside Ceiling (Call Wall): {cw}",
            f"  - Downside Floor (Put Wall):  {pw}",
            f"  - Volatility Pivot (Zero GEX): {zg}",
            f"  - Risk Envelope: Expected High {em_upper} <-> Expected Low {em_lower}",
        ])

    lines.extend([
        "",
        "[4] HIGH-IMPACT CATALYSTS & EARNINGS RADAR",
        divider,
        "• Economic Releases:",
    ])

    if events:
        for evt in events:
            day = evt.get("day_of_week", "")[:3]
            dt_str = evt.get("date", "")[5:]
            t_et = evt.get("time_et", "")
            name = evt.get("name", "")
            impact = evt.get("impact", "")
            lines.append(f"  - {day} {dt_str} {t_et:<8} [{impact:<4}]: {name}")
    else:
        lines.append("  - No major economic events scheduled.")

    lines.append("• Mega-Cap Earnings Radar (index-moving only):")
    if earnings:
        # Filter to only index-moving mega-caps — these are the tickers
        # with enough weight in SPY/QQQ to move the index at the open.
        # Exclude non-index-moving stocks like NVS, SCHW, IBKR, PM, GEV, T, TTE, SAP, TMUS, TMO, UNP, NEE, VZ.
        INDEX_MOVING_TICKERS = {
            "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META",
            "TSLA", "AVGO", "LLY", "JPM", "V", "UNH", "XOM", "WMT",
            "MA", "ORCL", "COST", "NFLX", "CRM", "AMD", "INTC",
            "IBM", "TXN", "RTX", "AXP", "GS", "MS", "C", "BAC",
            "HD", "DIS", "BABA",
        }
        filtered_earnings = []
        for e in earnings:
            name = (e.get("name") or "").strip()
            # Extract the ticker (first word before " Earnings")
            ticker_part = name.replace(" Earnings", "").strip().upper()
            if ticker_part in INDEX_MOVING_TICKERS:
                filtered_earnings.append(e)
        if filtered_earnings:
            for earn in filtered_earnings:
                day = earn.get("day_of_week", "")[:3]
                t_timing = earn.get("timing", "")
                name = earn.get("name", "")
                lines.append(f"  - {day} ({t_timing}): {name}")
        else:
            lines.append("  - No index-moving mega-cap earnings this week.")
    else:
        lines.append("  - No mega-cap earnings scheduled.")

    lines.extend([
        "",
        "[5] EXECUTION RULES & ACCOUNT PROTECTION MANDATE",
        divider,
    ])

    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        proxy_context = ticker_block.get("proxy_context", {})
        proxy_symbol = proxy_context.get("proxy_symbol")
        account_inv = ticker_block.get("account_invalidation", {})
        b_inv = format_translated_level_display(account_inv.get("bullish_invalidation"), proxy_symbol, proxy_context.get("bullish_invalidation_proxy"))
        s_inv = format_translated_level_display(account_inv.get("bearish_invalidation"), proxy_symbol, proxy_context.get("bearish_invalidation_proxy"))
        b_dist = _fmt_pct(account_inv.get("distance_to_bullish_inv_pct"))
        s_dist = _fmt_pct(account_inv.get("distance_to_bearish_inv_pct"))

        lines.append(f"• {ticker} Account Invalidation:")
        lines.append(f"  - Downside Floor Fracture: {b_inv} (Dist: {b_dist})")
        lines.append(f"  - Upside Ceiling Fracture: {s_inv} (Dist: {s_dist})")

    # ── Next week event timeline (weekly mode) ──
    try:
        from datetime import date as _date, datetime as _dt
        _week_start = meta.get("week_start_date", "")
        if _week_start:
            _target_date = _dt.fromisoformat(_week_start[:10]).date()
        else:
            _target_date = _date.today()
        _next_monday = _target_date + timedelta(days=(7 - _target_date.weekday()) if _target_date.weekday() < 4 else (14 - _target_date.weekday()))
        _next_modifiers = get_weekly_modifiers(_next_monday, events)
        _next_timeline = build_weekly_event_timeline(
            _next_monday, events, _next_modifiers,
            archetype_info=archetype_info,
            mode="weekly",
        )
        if _next_timeline:
            lines.extend(["", "[6] NEXT WEEK EVENT TIMELINE", divider])
            lines.append(_next_timeline)
    except Exception as e:
        log.warning("[weekly] Next week timeline failed: %s", e)

    lines.extend([
        border,
        "",
    ])

    return "\n".join(lines)