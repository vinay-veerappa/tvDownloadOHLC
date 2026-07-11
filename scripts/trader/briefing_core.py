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
import os
import re
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

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

# ── Paths ──────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
OPTIONS_DATA_DIR = REPO_ROOT / "data" / "options"
MACRO_LEVELS_JSON = OPTIONS_DATA_DIR / "macro_levels.json"
UNIFIED_LEVELS_JSON = OPTIONS_DATA_DIR / "unified_levels.json"
UNIFIED_LEVELS_OPEN_TXT = OPTIONS_DATA_DIR / "current" / "unified_levels_open.txt"
UNIFIED_LEVELS_CLOSE_TXT = OPTIONS_DATA_DIR / "current" / "unified_levels_close.txt"
DB_PATH = REPO_ROOT / "web" / "prisma" / "dev.db"
BIAS_GRADES_PATH = OPTIONS_DATA_DIR / "daily" / "bias_grades.jsonl"

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
    bullish_inv = min(put_wall, friday_em_lower)
    bearish_inv = max(call_wall, friday_em_upper)

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
    """Initialize DataLoader with overridden date range for weekly context.

    Reuses the existing config from sessions.yaml and the existing
    DataLoader from scripts/libs_py/data/loader.py — no new I/O code.
    """
    config = load_config("scripts/trading_framework/config/sessions.yaml")
    now = datetime.now(ET)
    # date_end is inclusive of today: use tomorrow so the full current day
    # (including the Globex session extending into this morning) is captured.
    config.date_end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    config.date_start = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
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

def build_levels_markdown_table(ticker: str) -> str:
    """Build a precise markdown table of option levels mapped to Futures prices."""
    unified_txt_path = UNIFIED_LEVELS_OPEN_TXT if UNIFIED_LEVELS_OPEN_TXT.exists() else Path(OPTIONS_DATA_DIR / "current" / "unified_levels.txt")
    if not unified_txt_path.exists():
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
                # Fallback: split on last underscore
                idx = meta_part.rfind("_")
                if idx > 0:
                    key = meta_part[:idx]
                    val_str = meta_part[idx + 1:]
                    try:
                        meta[key] = float(val_str)
                    except ValueError:
                        meta[key] = val_str

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

    Returns:
        {"monday": {"upper": x, "lower": y, "em": z}, ...}
    """
    tokens = unified_entry.get("tokens", [])

    # Find EM HI and EM LO tokens
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


def load_weekly_ems(unified_entry: dict, spot: float) -> dict:
    """Backward-compatible alias for weekly EM envelope computation."""
    return compute_weekly_ems(unified_entry, spot)


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
    """Map cash/ETF tickers to parquet file prefixes.

    SPX → SPX, SPY → SPY, QQQ → QQQ, etc.
    For index tickers without direct parquet, fall back to the futures prefix.
    """
    # Direct mapping — most tickers have parquet files with their own name
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
    }
    return direct_map.get(ticker, ticker)


def load_weekly_price_context(loader: DataLoader, ticker: str) -> dict:
    """Load HTF price context using the existing DataLoader.

    Uses DataLoader.load_price() (returns 1m bars in ET timezone),
    then resamples to weekly via vectorized Pandas operations.

    Returns prior week OHLCV + momentum metrics.
    """
    parquet_sym = _resolve_parquet_symbol(ticker)

    try:
        df_1m = loader.load_price(parquet_sym)
    except Exception as e:
        log.warning("Could not load price data for %s (%s): %s", ticker, parquet_sym, e)
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


def load_daily_price_context(loader: DataLoader, ticker: str) -> dict:
    """Load today's OHLCV via DataLoader for the daily EOD update.

    Returns today's open/high/low/close/change_pct/range_pct/body.
    """
    parquet_sym = _resolve_parquet_symbol(ticker)

    try:
        df_1m = loader.load_price(parquet_sym)
    except Exception as e:
        log.warning("Could not load price data for %s (%s): %s", ticker, parquet_sym, e)
        return {}

    if df_1m.empty:
        return {}

    # Vectorized daily resampling
    daily = df_1m.resample("B").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    if daily.empty:
        return {}

    today = daily.iloc[-1]
    prev_close = daily["close"].iloc[-2] if len(daily) >= 2 else today.open
    change_pct = round((today.close / prev_close - 1) * 100, 2)
    range_pct = round((today.high - today.low) / today.open * 100, 2) if today.open > 0 else 0.0

    return {
        "open": round(float(today.open), 2),
        "high": round(float(today.high), 2),
        "low": round(float(today.low), 2),
        "close": round(float(today.close), 2),
        "change_pct": change_pct,
        "range_pct": range_pct,
        "body": "bullish" if today.close > today.open else "bearish",
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

    return {
        "call_wall_tested": high >= call_wall > 0,
        "call_wall_broken": close > call_wall > 0,
        "put_wall_tested": low <= put_wall > 0 and put_wall > 0,
        "put_wall_broken": close < put_wall > 0,
        "em_upper_tested": high >= em_upper > 0,
        "em_upper_broken": close > em_upper > 0,
        "em_lower_tested": low <= em_lower > 0 and em_lower > 0,
        "em_lower_broken": close < em_lower > 0,
        "zero_gamma_crossed": (low < zero_gamma < high) if zero_gamma > 0 else False,
        "magnet_tested": (low < gamma_magnet < high) if gamma_magnet > 0 else False,
    }


# ── Economic Events ───────────────────────────────────────────────

# MEDIUM-impact events are only kept if their name matches one of these
# keywords — these are the events that historically move equity futures.
# All HIGH-impact events are kept unconditionally. LOW is always filtered out.
MEDIUM_ALLOWLIST_KEYWORDS = [
    "FOMC", "FED", "INTEREST RATE", "POWELL", "BOSTIC", "WILLIAMS",
    "BOWMAN", "WALLER", "BARR", "COOK", "JEFFERSON", "KASHKARI",
    "DALY", "LOGAN", "SCHMID", "COLLINS",
    "CPI", "PCE", "PPI", "INFLATION",
    "NON-FARM PAYROLL", "NFP", "ADP EMPLOYMENT",
    "GDP", "GDPNOW",
    "ISM", "PMI",
    "RETAIL SALES", "DURABLE GOODS",
    "JOBLESS CLAIMS", "UNEMPLOYMENT",
    "CONSUMER SENTIMENT", "CONSUMER CONFIDENCE",
    "TREASURY AUCTION", "NOTE AUCTION", "BOND AUCTION",
]

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
    await db.connect()
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
            week_start_dt = dt_cls.combine(week_start, dt_cls.min.time())
            briefing = await db.weeklybriefing.find_unique(
                where={"weekStartDate": week_start_dt},
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
                "institutional_volatility_context": fetch_vol_context(snap.ticker, briefing.weekStartDate.date())
            })

        events = await fetch_week_events(briefing.weekStartDate.date(), briefing.weekEndDate.date())

        return {
            "meta": {
                "id": briefing.id,
                "week_start_date": briefing.weekStartDate.isoformat(),
                "week_end_date": briefing.weekEndDate.isoformat(),
                "generated_at": briefing.generatedAt.isoformat(),
                "tickers_covered": briefing.tickersCovered,
            },
            "economic_events": events,
            "tickers": tickers,
        }
    finally:
        await db.disconnect()


async def save_narrative_to_db(briefing_id: str, summary_md: str, is_daily: bool = False, eod_id: str | None = None) -> None:
    """Store the LLM-generated narrative in the DB."""
    db = await get_db()
    try:
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

def build_compact_briefing(briefing_data: dict) -> str:
    """Build a compact pre-processed summary that gives the LLM only what it
    needs for trade plan generation. This replaces the raw TOON JSON to save
    ~1000+ tokens by:
    - Filtering to SPY and QQQ only (drops SPX and other tickers)
    - Extracting only regime, spot, key levels, and bias
    - Pre-computing level interactions into plain English
    - Stripping weekly progress, track assessment, and vol context
      (these are EOD review fields, not trade-plan inputs)
    """
    import json as _json

    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
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

    compact = {
        "date": briefing_data.get("meta", {}).get("date", ""),
        "events": events,
        "SPY": _compact_ticker(tickers.get("SPY")),
        "QQQ": _compact_ticker(tickers.get("QQQ")),
    }
    return _json.dumps(compact, indent=2, ensure_ascii=False)


def build_compact_eod(briefing_data: dict) -> str:
    """Build a compact EOD briefing for the LLM.

    The EOD narrative needs to grade the morning's trades against today's
    price action. It needs: regime, today's OHLC, level interactions, and
    the key levels. It does NOT need: weekly_progress, track_assessment,
    institutional_volatility_context, or SPX (redundant with SPY).

    Saves ~600 tokens vs raw TOON by dropping SPX and stripping review-only fields.
    """
    import json as _json

    tickers = {t["ticker"]: t for t in briefing_data.get("tickers", [])}
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

    compact = {
        "date": briefing_data.get("meta", {}).get("date", ""),
        "events": events,
        "SPY": _compact_eod_ticker(tickers.get("SPY")),
        "QQQ": _compact_eod_ticker(tickers.get("QQQ")),
    }
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


def build_overnight_context(loader: DataLoader | None = None, ticker: str = "NQ1") -> dict:
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

    # Fused loader returns naive ET index. Localize to tz-aware ET.
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize(ET)
    else:
        df_1m.index = df_1m.index.tz_convert(ET)

    now_et = datetime.now(ET)
    target_date = now_et.date()

    # Globex starts prior evening. If before 08:30 ET, use yesterday's globex.
    # Build the globex window: prior day 18:00 → target day 08:30.
    if now_et.hour < _GLOBEX_END_HOUR or (now_et.hour == _GLOBEX_END_HOUR and now_et.minute < _GLOBEX_END_MIN):
        # Pre-open: globex for today's session started yesterday 18:00
        globex_start = datetime.combine(target_date - timedelta(days=1), datetime.min.time(), tzinfo=ET).replace(hour=_GLOBEX_START_HOUR)
        globex_end = datetime.combine(target_date, datetime.min.time(), tzinfo=ET).replace(hour=_GLOBEX_END_HOUR, minute=_GLOBEX_END_MIN)
    else:
        # After open: globex for tomorrow starts today 18:00 (but we want last night's)
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
    rth_start = globex_start - timedelta(days=1)
    rth_start = rth_start.replace(hour=9, minute=30)
    rth_end = rth_start.replace(hour=16, minute=0)
    prior_rth_mask = (df_1m.index >= rth_start) & (df_1m.index < rth_end)
    prior_rth_df = df_1m.loc[prior_rth_mask]
    prior_rth_high = float(prior_rth_df["high"].max()) if not prior_rth_df.empty else None
    prior_rth_low = float(prior_rth_df["low"].min()) if not prior_rth_df.empty else None

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


def build_intermarket_read(
    nq_ctx: dict,
    es_ctx: dict,
    vix_ctx: dict | None = None,
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


def _format_calendar_for_cheat_sheet(events: list[dict]) -> str:
    """Format economic events into the cheat-sheet calendar block."""
    if not events:
        return "No market-moving events today. Clean session."

    lines: list[str] = []
    for e in events:
        impact = (e.get("impact") or "").upper()
        time_et = e.get("time_et", "?? ET")
        name = e.get("name", "Unknown")
        passed = e.get("passed", False)
        marker = "[PASSED]" if passed else ""
        if impact == "HIGH":
            lines.append(f"{time_et} [HIGH] {name} {marker} — This is the landmine. Expect volatility spike. No entries 15 min before. Wait for post-news settlement.")
        elif impact == "MEDIUM":
            lines.append(f"{time_et} [MEDIUM] {name} {marker} — Could move price. Be aware.")
        else:
            lines.append(f"{time_et} [{impact}] {name} {marker}")
    return "\n".join(lines) if lines else "No market-moving events today. Clean session."


def _format_gex_block(ticker_label: str, levels: dict, spot: float) -> str:
    """Format GEX structure into the cheat-sheet block."""
    if not levels:
        return f"== GEX STRUCTURE ({ticker_label}) ==\nNo GEX data available."

    def _pct_from_spot(level: float | None) -> str:
        if not level or not spot or spot == 0:
            return "N/A"
        return f"{'+' if level > spot else ''}{round((level / spot - 1) * 100, 2)}%"

    lines = [f"== GEX STRUCTURE ({ticker_label}) =="]
    cw = levels.get("call_wall")
    pw = levels.get("put_wall")
    flip = levels.get("flip") or levels.get("zero_gamma")
    magnet = levels.get("gamma_magnet")
    regime = levels.get("regime", "N/A")
    bias = levels.get("bias", "N/A")

    if cw:
        desc = "overhead resistance" if (spot and cw > spot) else "breached (below spot support)"
        lines.append(f"Call Wall: {cw:,.2f} ({_pct_from_spot(cw)} from spot) — {desc}")
    if pw:
        desc = "below/at current price (support)" if (spot and pw <= spot) else "breached (overhead resistance)"
        lines.append(f"Put Wall: {pw:,.2f} ({_pct_from_spot(pw)} from spot) — {desc}")
    if flip:
        pos = "above" if (spot and flip > spot) else "below"
        lines.append(f"Gamma Flip: {flip:,.2f} — we're {pos} it ({'negative' if (spot and flip > spot) else 'positive'} gamma, {'amplification' if (spot and flip > spot) else 'pinning'} regime)")
    if magnet:
        lines.append(f"Magnet: {magnet:,.2f} — pulling price toward it")
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
    lh = levels.get("lh")
    ll = levels.get("ll")
    mid = levels.get("mid")
    ib_bias = aln_data.get("ib_bias", "N/A")
    ib_conviction = aln_data.get("ib_conviction", 0)
    p12 = aln_data.get("p12")

    lines = [f"== ALN / SESSION PATTERNS ({ticker_label}) =="]
    lines.append(f"Pattern: {aln}")
    lines.append(f"Broken: {broken}")
    if lh and ll:
        lines.append(f"London High: {lh:,.2f} | London Low: {ll:,.2f} | Mid: {mid:,.2f}" if mid else f"London High: {lh:,.2f} | London Low: {ll:,.2f}")
    if p12:
        lines.append(f"Prior Close (P12): {p12:,.2f}")
    if ib_bias and ib_bias != "N/A":
        lines.append(f"IB Bias: {ib_bias} ({float(ib_conviction)*100:.0f}% conviction)")
    lines.append(f"Bias: {bias} ({conviction})")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")

    # Conflict detection: price vs London Low
    if spot and ll and spot < ll:
        lines.append(f"CONFLICT: Price ({spot:,.2f}) is already below London Low ({ll:,.2f}) — the bullish setup is under pressure")
    elif spot and lh and spot > lh:
        lines.append(f"CONFLICT: Price ({spot:,.2f}) is already above London High ({lh:,.2f}) — the bearish setup is under pressure")

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

    lines = [f"== CLASSIFICATION ({ticker_label}) =="]
    lines.append(f"Yesterday: {prior_type}")
    lines.append(f"Overnight Key: {overnight_key}")
    if seq_probs:
        lines.append("Sequential: " + " | ".join(f"{k}: {v}%" for k, v in seq_probs.items()))
    if over_probs:
        lines.append("Overnight: " + " | ".join(f"{k}: {v}%" for k, v in over_probs.items()))
    lines.append(f"Most Likely Today: {most_likely}")
    return "\n".join(lines)


def _format_key_levels_hierarchy(
    ticker_label: str,
    levels: dict,
    aln_data: dict,
    spot: float,
) -> str:
    """Merge all level sources and sort into overhead/support ladder."""
    overhead: list[tuple[float, str]] = []
    support: list[tuple[float, str]] = []

    def _add(level: float | None, label: str, spot: float):
        if not level or level <= 0 or not spot:
            return
        if level > spot:
            overhead.append((level, label))
        else:
            support.append((level, label))

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

    lines = [f"== KEY LEVELS TO WATCH ({ticker_label}) =="]
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
) -> str:
    """Build the premarket cheat sheet — runs before 09:30 ET open.

    Focuses on: overnight Globex action, GEX structure (live JSON),
    prior EOD classification, today's calendar. No RTH data.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=5)

    sections: list[str] = []

    # ── Overnight context (NQ + ES) ──
    nq_ctx = build_overnight_context(loader, nq_ticker)
    es_ctx = build_overnight_context(loader, es_ticker)

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

    sections.append(_format_gex_block("NQ", nq_gex, nq_spot))
    sections.append(_format_gex_block("ES", es_gex, es_spot))

    # ── Prior EOD classification ──
    try:
        import scripts.analysis.analyze_daily_classification_bias as class_module
        import sys as _sys
        _orig_argv = _sys.argv
        yesterday = (datetime.now(ET) - timedelta(days=1)).date()
        _sys.argv = ["analyze_daily_classification_bias.py", "--ticker", nq_ticker, "--date", yesterday.isoformat()]
        class_data = class_module.main()
        _sys.argv = _orig_argv
    except Exception as e:
        log.warning("[premarket] Classification analysis failed: %s", e)
        class_data = {}
    sections.append(_format_classification_block("NQ", class_data))

    # ── Calendar ──
    try:
        today = datetime.now(ET).date()
        events = asyncio.run(fetch_week_events(today, today))
    except Exception as e:
        log.warning("[premarket] Calendar fetch failed: %s", e)
        events = []
    sections.append("== TODAY'S CALENDAR ==\n" + _format_calendar_for_cheat_sheet(events))

    return "\n\n".join(sections)


def build_trader_cheat_sheet(
    mode: str = "open",
    loader: DataLoader | None = None,
    nq_ticker: str = "NQ1",
    es_ticker: str = "ES1",
    target_date: date | None = None,
) -> str:
    """Mode-specific assembly of all data sources into the cheat sheet text block.

    v1: Open mode only. Returns a ~800-1200 token text block with all
    connections pre-computed (overnight, intermarket, GEX, ALN, classification,
    calendar, prior EOD plan).

    ADR-017: all computations are vectorized or O(1) dict lookups.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=5)

    if target_date is None:
        target_date = datetime.now(ET).date()

    sections: list[str] = []

    # ── Overnight context (NQ + ES) ──
    nq_ctx = build_overnight_context(loader, nq_ticker)
    es_ctx = build_overnight_context(loader, es_ticker)

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

    # ── RTH Breaks (prior day RTH range vs current open) ──
    # nqstats.com/rth_breaks.html — classifies the 09:30 open vs pRTH high/low
    rth_lines = ["== RTH BREAKS (Prior Day RTH Range) =="]
    for label, ctx in [("NQ", nq_ctx), ("ES", es_ctx)]:
        prth_h = ctx.get("prior_rth_high")
        prth_l = ctx.get("prior_rth_low")
        current = ctx.get("close")
        if prth_h is None or prth_l is None or not current:
            rth_lines.append(f"{label}: No pRTH data available")
            continue
        if current > prth_h:
            scenario = "GAP UP (open above pRTH High) — 70% close holds above"
        elif current < prth_l:
            scenario = "GAP DOWN (open below pRTH Low) — 60% close holds below"
        else:
            scenario = "INSIDE RANGE (open within pRTH) — 74% one side breached"
        rth_lines.append(f"{label}: pRTH High {prth_h:,.2f} | pRTH Low {prth_l:,.2f}")
        rth_lines.append(f"    Current {current:,.2f} → {scenario}")
    sections.append("\n".join(rth_lines))

    # ── VIX checkpoint ──
    vix_ctx = get_vix_checkpoint(loader)

    # ── Intermarket read ──
    intermarket = build_intermarket_read(nq_ctx, es_ctx, vix_ctx)
    sections.append("== INTERMARKET READ ==\n" + intermarket)

    # ── Calendar ──
    try:
        events = asyncio.run(fetch_week_events(target_date, target_date))
    except Exception as e:
        log.warning("[cheat_sheet] Failed to fetch calendar: %s", e)
        events = []
    sections.append("== TODAY'S CALENDAR ==\n" + _format_calendar_for_cheat_sheet(events))

    # ── GEX structure (NQ + ES) ──
    unified = load_macro_levels(session="open")
    # NQ uses QQQ proxy, ES uses SPY proxy
    nq_unified = unified.get("QQQ") or unified.get("NQ1") or {}
    es_unified = unified.get("SPY") or unified.get("ES1") or {}

    nq_spot = nq_ctx.get("close", 0) or 0
    es_spot = es_ctx.get("close", 0) or 0

    nq_gex = _extract_gex_levels(nq_unified, "QQQ")
    es_gex = _extract_gex_levels(es_unified, "SPY")

    sections.append(_format_gex_block("NQ", nq_gex, nq_spot))
    sections.append(_format_gex_block("ES", es_gex, es_spot))

    # ── ALN / Session patterns (NQ) ──
    # Use the NQStats library directly (scripts.libs_py.nqstats.engine) instead
    # of the analyze_daily_nqstats.py CLI script, which has a stale column
    # name mismatch (asia_quadrant vs asiabox_status). The engine's
    # get_latest_status() returns the correct current-session fields.
    #
    # PERF (ADR-017): The engine is vectorized but processes every row.
    # Loading the full 6.5M-row fused DataFrame takes ~117s. We only need
    # today's session + enough prior days for P12 (prior close) context.
    # Filtering to the last 10 days (~9K rows) gives identical results
    # in ~0.25s — a 464x speedup.
    aln_data: dict = {}
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        from scripts.libs_py.nqstats.engine import NQStatsEngine

        df_nq = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
        if df_nq is not None and not df_nq.empty:
            # Ensure ET-aware index before any datetime comparison.
            if df_nq.index.tz is None:
                df_nq.index = pd.DatetimeIndex(df_nq.index).tz_localize("UTC").tz_convert(ET)
            elif df_nq.index.tz != ET:
                df_nq.index = df_nq.index.tz_convert(ET)

            # Limit to last 10 days for P12 context (ADR-017: avoid processing
            # millions of rows when only today's session is needed).
            _cutoff = pd.Timestamp.now(ET) - timedelta(days=10)
            df_nq_recent = df_nq[df_nq.index >= _cutoff]
            if df_nq_recent.empty:
                df_nq_recent = df_nq

            engine = NQStatsEngine(df_nq_recent, ticker=nq_ticker)
            engine.process()
            latest = engine.get_latest_status()

            lh = latest.get("london_high")
            ll = latest.get("london_low")
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
                    "lh": float(lh) if lh is not None else None,
                    "ll": float(ll) if ll is not None else None,
                    "mid": (float(lh) + float(ll)) / 2 if lh is not None and ll is not None else None,
                },
            }

            # Derive bias/conviction/reasoning from the ALN pattern
            aln_pattern = aln_data["aln"]
            broken = aln_data["broken"]
            if aln_pattern == "LPEU" and ("Held/Held" in broken or "Broken/Held" in broken):
                aln_data["bias"] = "STRONG BULLISH"
                aln_data["conviction"] = "HIGH"
                aln_data["reasoning"] = "LPEU (78% Continuation) + clean structure."
            elif aln_pattern == "LPEU" and "Broken/Held" in broken:
                aln_data["bias"] = "STRONG BEARISH (REVERSAL)"
                aln_data["conviction"] = "HIGH"
                aln_data["reasoning"] = "LPEU (63% Reversal) + Broken Asia + London Reversal."
            elif aln_pattern == "LPED":
                aln_data["bias"] = "STRONG BEARISH"
                aln_data["conviction"] = "HIGH"
                aln_data["reasoning"] = "LPED (82% Continuation) — bearish continuation."
            elif "Broken/Broken" in broken:
                aln_data["bias"] = "NEUTRAL / CHOP"
                aln_data["conviction"] = "LOW"
                aln_data["reasoning"] = "Market structure broken on both sides. High noise risk."
            else:
                aln_data["bias"] = "NEUTRAL / WAIT"
                aln_data["conviction"] = "LOW"
                aln_data["reasoning"] = f"{aln_pattern} + {broken} — no high-conviction edge."
    except Exception as e:
        log.warning("[cheat_sheet] ALN engine failed: %s", e)
    sections.append(_format_aln_block("NQ", aln_data, nq_spot))

    # ── Classification (NQ) ──
    class_data: dict = {}
    try:
        import scripts.analysis.analyze_daily_classification_bias as class_module
        import sys as _sys
        orig_argv = _sys.argv[:]
        _sys.argv = ["analyze_daily_classification_bias.py", "--ticker", nq_ticker, "--date", target_date.isoformat()]
        try:
            _, class_data = class_module.main()
        finally:
            _sys.argv = orig_argv
    except Exception as e:
        log.warning("[cheat_sheet] Classification analysis failed: %s", e)
    sections.append(_format_classification_block("NQ", class_data))

    # ── Key levels hierarchy ──
    sections.append(_format_key_levels_hierarchy(nq_gex, es_gex, aln_data, nq_spot))

    # ── Phase D: Signal module blocks ──

    # Data freshness check
    try:
        freshness = check_all()
        stale = [f for f in freshness if f.is_stale]
        if stale:
            sections.append("== DATA FRESHNESS ==\n" + "\n".join(f"⚠ {s.source}: {s.days_stale}d stale (last {s.last_date})" for s in stale))
    except Exception as e:
        log.warning("[cheat_sheet] Freshness check failed: %s", e)

    # VIX/VVIX volatility regime
    try:
        vv = get_vix_vvix_checkpoint()
        sections.append(_format_volatility_block(vv))
    except Exception as e:
        log.warning("[cheat_sheet] Volatility signal failed: %s", e)

    # ICT context
    try:
        ict = compute_ict_from_htf(ticker=nq_ticker, current_price=nq_spot)
        sections.append(_format_ict_block("NQ", ict, nq_spot))
    except Exception as e:
        log.warning("[cheat_sheet] ICT context failed: %s", e)

    # Candle Science
    try:
        cs = get_candle_science_read(ticker=nq_ticker)
        sections.append(_format_candle_science_block("NQ", cs))
    except Exception as e:
        log.warning("[cheat_sheet] Candle Science failed: %s", e)

    # Confluence assessment
    try:
        # Derive signal directions from existing data
        aln_bias = aln_data.get("bias", "NEUTRAL")
        s1 = "BULLISH" if "BULLISH" in aln_bias else ("BEARISH" if "BEARISH" in aln_bias else "NEUTRAL")
        # RTH open scenario
        rth_scenario = "INSIDE"
        if nq_ctx:
            prth_h = nq_ctx.get("prior_rth_high")
            prth_l = nq_ctx.get("prior_rth_low")
            cur = nq_ctx.get("close", 0)
            if prth_h and prth_l and cur:
                if cur > prth_h: rth_scenario = "GAP_UP"
                elif cur < prth_l: rth_scenario = "GAP_DOWN"
        s2 = "BULLISH" if rth_scenario == "GAP_UP" else ("BEARISH" if rth_scenario == "GAP_DOWN" else "NEUTRAL")
        # Candle Science direction
        s3 = "BULLISH" if (cs and cs.get("p_bull", 50) > cs.get("p_bear", 50)) else ("BEARISH" if (cs and cs.get("p_bear", 50) > cs.get("p_bull", 50)) else "NEUTRAL")
        conf = assess_confluence(s1, s2, s3)
        sections.append(_format_confluence_block("NQ", conf))
    except Exception as e:
        log.warning("[cheat_sheet] Confluence failed: %s", e)

    # Day type
    try:
        dt = classify_day_type(events, target_date)
        sections.append(_format_day_type_block(dt))
    except Exception as e:
        log.warning("[cheat_sheet] Day type failed: %s", e)

    # Weekly profile
    try:
        wp = compute_weekly_profile(ticker=nq_ticker, current_price=nq_spot)
        sections.append(_format_weekly_profile_block("NQ", wp))
    except Exception as e:
        log.warning("[cheat_sheet] Weekly profile failed: %s", e)

    # ICT liquidity map
    try:
        lm = build_liquidity_map(
            bias=s1,
            nq_status=aln_data,
            overnight=nq_ctx or {},
            ict=ict,
            news_tier="HIGH" if any(e.get("impact") == "HIGH" for e in events) else ("MEDIUM" if any(e.get("impact") == "MEDIUM" for e in events) else "NONE"),
        )
        sections.append(_format_liquidity_map_block(lm))
    except Exception as e:
        log.warning("[cheat_sheet] Liquidity map failed: %s", e)

    # GEX regime change
    try:
        nq_gex_full = nq_unified if isinstance(nq_unified, dict) else {}
        gr = get_gex_regime_change(nq_gex_full)
        if gr.get("regime_change") and gr["regime_change"] != "stable":
            sections.append(_format_gex_regime_block(gr))
        if nq_gex_full:
            save_today_snapshot(nq_gex_full)
    except Exception as e:
        log.warning("[cheat_sheet] GEX regime change failed: %s", e)

    # ── Expected Move ──
    try:
        em_data = get_em_context(spot=nq_spot, ticker=nq_ticker)
        sections.append(format_em_block(em_data))
    except Exception as e:
        log.warning("[cheat_sheet] EM signal failed: %s", e)
        sections.append("== EXPECTED MOVE ==\nEM calculation failed")

    # ── Prior EOD plan (overnight continuity) ──
    try:
        from scripts.trader.daily_narrative import get_previous_eod_plan
        prior_plan = asyncio.run(get_previous_eod_plan())
    except Exception as e:
        log.warning("[cheat_sheet] Prior EOD plan fetch failed: %s", e)
        prior_plan = "No previous EOD plan available."
    sections.append("== PRIOR EOD PLAN (overnight continuity) ==\n" + prior_plan)

    # ── Bias grade feedback (Phase F) ──
    try:
        grades = get_recent_bias_accuracy(n=5)
        if grades["total"] > 0:
            sections.append(_format_bias_grade_block(grades))
    except Exception as e:
        log.warning("[cheat_sheet] Bias grades failed: %s", e)

    return "\n\n".join(sections)


def build_intraday_context(
    loader: DataLoader | None = None,
    nq_ticker: str = "NQ1",
    es_ticker: str = "ES1",
) -> str:
    """Build the intraday cheat sheet for the 12:00 ET update.

    Focuses on: morning bias vs actual, IB status, noon curve, level interactions,
    calendar update, and what changed from the morning narrative.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=2)

    sections: list[str] = []

    # ── Morning bias (from latest open narrative) ──
    morning_narrative_path = OPTIONS_DATA_DIR / "daily" / "latest_trader_narrative_open.md"
    if morning_narrative_path.exists():
        morning_text = morning_narrative_path.read_text(encoding="utf-8")
        # Extract first 500 chars as summary
        morning_summary = morning_text[:500] + "..." if len(morning_text) > 500 else morning_text
        sections.append("== MORNING BIAS ==\n" + morning_summary)
    else:
        sections.append("== MORNING BIAS ==\nNo morning narrative available.")

    # ── Current price (from 1m parquet) ──
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_nq = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
        df_es = load_fused_data(es_ticker, timeframe="1m", require_historical=False)

        nq_current = float(df_nq["close"].iloc[-1]) if df_nq is not None and not df_nq.empty else 0
        es_current = float(df_es["close"].iloc[-1]) if df_es is not None and not df_es.empty else 0

        # RTH open (09:30 bar)
        if df_nq is not None and df_nq.index.tz is None:
            df_nq.index = pd.DatetimeIndex(df_nq.index).tz_localize("UTC").tz_convert(ET)
        elif df_nq is not None and df_nq.index.tz != ET:
            df_nq.index = df_nq.index.tz_convert(ET)
        if df_es is not None and df_es.index.tz is None:
            df_es.index = pd.DatetimeIndex(df_es.index).tz_localize("UTC").tz_convert(ET)
        elif df_es is not None and df_es.index.tz != ET:
            df_es.index = df_es.index.tz_convert(ET)
        nq_open = 0.0
        es_open = 0.0
        today_930 = pd.Timestamp.now(ET).normalize() + pd.Timedelta(hours=9, minutes=30)
        if df_nq is not None:
            today_open_nq = df_nq[df_nq.index >= today_930]
            if not today_open_nq.empty:
                nq_open = float(today_open_nq["open"].iloc[0])
        if df_es is not None:
            today_open_es = df_es[df_es.index >= today_930]
            if not today_open_es.empty:
                es_open = float(today_open_es["open"].iloc[0])

        nq_chg = ((nq_current / nq_open - 1) * 100) if nq_open > 0 else 0
        es_chg = ((es_current / es_open - 1) * 100) if es_open > 0 else 0

        lines = ["== CURRENT PRICE =="]
        lines.append(f"NQ: {nq_current:,.2f} ({nq_chg:+.2f}% from open) | ES: {es_current:,.2f} ({es_chg:+.2f}% from open)")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[intraday] Price fetch failed: %s", e)
        sections.append("== CURRENT PRICE ==\nPrice data unavailable")

    # ── IB Status ──
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_nq is not None and not df_nq.empty:
            _cutoff = pd.Timestamp.now(ET) - pd.Timedelta(days=2)
            df_recent = df_nq[df_nq.index >= _cutoff]
            engine = NQStatsEngine(df_recent, ticker=nq_ticker)
            engine.process()
            status = engine.get_latest_status()

            ib_high = status.get("ib_high")
            ib_low = status.get("ib_low")
            ib_mid = (ib_high + ib_low) / 2 if ib_high and ib_low else None
            ib_broken_high = nq_current > ib_high if ib_high and nq_current else None
            ib_broken_low = nq_current < ib_low if ib_low and nq_current else None

            lines = ["== IB STATUS =="]
            if ib_high and ib_low:
                lines.append(f"IB High: {ib_high:,.2f} | IB Low: {ib_low:,.2f} | Mid: {ib_mid:,.2f}" if ib_mid else "")
                if ib_broken_high:
                    lines.append("IB High BROKEN — bullish intraday")
                elif ib_broken_low:
                    lines.append("IB Low BROKEN — bearish intraday")
                else:
                    lines.append("IB intact — 82.5% break before noon, expect afternoon break")
                if ib_mid and nq_current > ib_mid:
                    lines.append("Price in upper half → 82% chance high breaks first")
                elif ib_mid:
                    lines.append("Price in lower half → watch for low break")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[intraday] IB status failed: %s", e)

    # ── Noon Curve ──
    try:
        if df_nq is not None and not df_nq.empty:
            today_rth = df_nq[(df_nq.index >= pd.Timestamp.now(ET).normalize() + pd.Timedelta(hours=9, minutes=30))]
            if not today_rth.empty:
                am_high = float(today_rth["high"].max())
                am_low = float(today_rth["low"].min())
                am_high_time = today_rth["high"].idxmax()
                am_low_time = today_rth["low"].idxmin()

                lines = ["== NOON CURVE =="]
                lines.append(f"AM High: {am_high:,.2f} at {am_high_time.strftime('%H:%M') if hasattr(am_high_time, 'strftime') else '?'}")
                lines.append(f"AM Low: {am_low:,.2f} at {am_low_time.strftime('%H:%M') if hasattr(am_low_time, 'strftime') else '?'}")
                lines.append("72.8% chance opposite side taken in PM")
                sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[intraday] Noon curve failed: %s", e)

    # ── Level interactions ──
    try:
        # Use live JSON for intraday — the 09:30 open snapshot is stale by noon
        unified = load_macro_levels(session="live")
        # Prefer direct RTD NQ/ES keys; fall back to QQQ/SPY proxy for backward compat
        nq_unified = unified.get("NQ") or unified.get("QQQ") or {}
        es_unified = unified.get("ES") or unified.get("SPY") or {}
        nq_gex = _extract_gex_levels(nq_unified, "NQ" if "NQ" in unified else "QQQ")
        es_gex = _extract_gex_levels(es_unified, "ES" if "ES" in unified else "SPY")
        lines = ["== LEVEL INTERACTIONS =="]
        # NQ
        if nq_gex:
            cw = nq_gex.get("call_wall")
            pw = nq_gex.get("put_wall")
            flip = nq_gex.get("flip") or nq_gex.get("zero_gamma")
            if cw and nq_current > cw:
                lines.append(f"NQ Call Wall ({cw:,.2f}) BROKEN — bullish")
            elif cw:
                lines.append(f"NQ Call Wall ({cw:,.2f}) overhead — untested")
            if pw and nq_current < pw:
                lines.append(f"NQ Put Wall ({pw:,.2f}) BROKEN — bearish")
            elif pw:
                lines.append(f"NQ Put Wall ({pw:,.2f}) below — holding")
            if flip:
                lines.append(f"NQ Gamma Flip: {flip:,.2f} — {'above' if nq_current > flip else 'below'} ({'negative' if nq_current > flip else 'positive'} gamma)")
        # ES
        if es_gex:
            cw = es_gex.get("call_wall")
            pw = es_gex.get("put_wall")
            flip = es_gex.get("flip") or es_gex.get("zero_gamma")
            if cw and es_current > cw:
                lines.append(f"ES Call Wall ({cw:,.2f}) BROKEN — bullish")
            elif cw:
                lines.append(f"ES Call Wall ({cw:,.2f}) overhead — untested")
            if pw and es_current < pw:
                lines.append(f"ES Put Wall ({pw:,.2f}) BROKEN — bearish")
            elif pw:
                lines.append(f"ES Put Wall ({pw:,.2f}) below — holding")
            if flip:
                lines.append(f"ES Gamma Flip: {flip:,.2f} — {'above' if es_current > flip else 'below'} ({'negative' if es_current > flip else 'positive'} gamma)")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[intraday] Level interactions failed: %s", e)

    # ── Calendar update ──
    try:
        events = asyncio.run(fetch_week_events(datetime.now(ET).date(), datetime.now(ET).date()))
        upcoming = [e for e in events if not e.get("passed", False)]
        passed = [e for e in events if e.get("passed", False)]
        lines = ["== CALENDAR UPDATE =="]
        if passed:
            lines.append("Passed: " + ", ".join(f"{e.get('time_et','?')} {e.get('name','?')}" for e in passed))
        if upcoming:
            lines.append("Upcoming: " + ", ".join(f"{e.get('time_et','?')} {e.get('name','?')} [{e.get('impact','?')}]" for e in upcoming))
        else:
            lines.append("No more events today.")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[intraday] Calendar failed: %s", e)

    return "\n\n".join(sections)


def build_eod_context(
    loader: DataLoader | None = None,
    nq_ticker: str = "NQ1",
    es_ticker: str = "ES1",
) -> str:
    """Build the EOD cheat sheet for the 16:05 ET close review.

    Focuses on: session summary, morning bias grade, level outcomes,
    ALN outcome, tomorrow's calendar and setup.
    """
    if loader is None:
        loader = get_dataloader(lookback_days=2)

    sections: list[str] = []

    # ── Morning bias (from latest open narrative) ──
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
        df_nq = load_fused_data(nq_ticker, timeframe="1m", require_historical=False)
        df_es = load_fused_data(es_ticker, timeframe="1m", require_historical=False)

        if df_nq is not None and df_nq.index.tz is None:
            df_nq.index = pd.DatetimeIndex(df_nq.index).tz_localize("UTC").tz_convert(ET)
        elif df_nq is not None and df_nq.index.tz != ET:
            df_nq.index = df_nq.index.tz_convert(ET)
        if df_es is not None and df_es.index.tz is None:
            df_es.index = pd.DatetimeIndex(df_es.index).tz_localize("UTC").tz_convert(ET)
        elif df_es is not None and df_es.index.tz != ET:
            df_es.index = df_es.index.tz_convert(ET)

        today_930 = pd.Timestamp.now(ET).normalize() + pd.Timedelta(hours=9, minutes=30)
        today_1600 = pd.Timestamp.now(ET).normalize() + pd.Timedelta(hours=16, minutes=0)

        lines = ["== TODAY'S SESSION =="]
        for label, df in [("NQ", df_nq), ("ES", df_es)]:
            if df is None or df.empty:
                lines.append(f"{label}: No data")
                continue
            rth = df[(df.index >= today_930) & (df.index <= today_1600)]
            if rth.empty:
                lines.append(f"{label}: No RTH data")
                continue
            rth_open = float(rth["open"].iloc[0])
            rth_close = float(rth["close"].iloc[-1])
            rth_high = float(rth["high"].max())
            rth_low = float(rth["low"].min())
            chg = (rth_close / rth_open - 1) * 100
            body = abs(rth_close - rth_open)
            lines.append(f"{label}: Open {rth_open:,.2f} → Close {rth_close:,.2f} ({chg:+.2f}%) | H: {rth_high:,.2f} L: {rth_low:,.2f} | Body: {body:,.2f}")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Session data failed: %s", e)
        sections.append("== TODAY'S SESSION ==\nSession data unavailable")

    # ── Level outcomes ──
    try:
        unified = load_macro_levels(session="open")
        nq_unified = unified.get("QQQ") or {}
        nq_gex = _extract_gex_levels(nq_unified, "QQQ")
        nq_close = 0.0
        if df_nq is not None and not df_nq.empty:
            rth = df_nq[(df_nq.index >= today_930) & (df_nq.index <= today_1600)]
            if not rth.empty:
                nq_close = float(rth["close"].iloc[-1])

        lines = ["== LEVEL OUTCOMES =="]
        if nq_gex and nq_close > 0:
            cw = nq_gex.get("call_wall")
            pw = nq_gex.get("put_wall")
            flip = nq_gex.get("flip") or nq_gex.get("zero_gamma")
            if cw:
                lines.append(f"Call Wall ({cw:,.2f}): {'BROKEN' if nq_close > cw else 'HELD'} (close {nq_close:,.2f})")
            if pw:
                lines.append(f"Put Wall ({pw:,.2f}): {'BROKEN' if nq_close < pw else 'HELD'} (close {nq_close:,.2f})")
            if flip:
                lines.append(f"Gamma Flip ({flip:,.2f}): {'above' if nq_close > flip else 'below'} at close")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Level outcomes failed: %s", e)

    # ── ALN outcome ──
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        if df_nq is not None and not df_nq.empty:
            _cutoff = pd.Timestamp.now(ET) - pd.Timedelta(days=2)
            df_recent = df_nq[df_nq.index >= _cutoff]
            engine = NQStatsEngine(df_recent, ticker=nq_ticker)
            engine.process()
            status = engine.get_latest_status()
            aln = status.get("aln", "N/A")
            broken = status.get("broken", "N/A")
            lines = ["== ALN OUTCOME =="]
            lines.append(f"Pattern: {aln} | Broken: {broken}")
            lh = status.get("london_high")
            ll = status.get("london_low")
            if lh and ll and nq_close > 0:
                if nq_close > lh:
                    lines.append(f"NY broke London High ({lh:,.2f}) — bullish resolution")
                elif nq_close < ll:
                    lines.append(f"NY broke London Low ({ll:,.2f}) — bearish resolution")
                else:
                    lines.append(f"NY stayed within London range ({ll:,.2f}-{lh:,.2f}) — range day")
            sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] ALN outcome failed: %s", e)

    # ── Tomorrow's calendar ──
    try:
        tomorrow = datetime.now(ET).date() + timedelta(days=1)
        events = asyncio.run(fetch_week_events(tomorrow, tomorrow))
        lines = ["== TOMORROW'S CALENDAR =="]
        if events:
            for e in events:
                lines.append(f"{e.get('time_et','?')} [{e.get('impact','?')}] {e.get('name','?')}")
        else:
            lines.append("No events scheduled.")
        sections.append("\n".join(lines))
    except Exception as e:
        log.warning("[eod] Tomorrow calendar failed: %s", e)

    # ── Tomorrow's setup ──
    try:
        if df_nq is not None and not df_nq.empty:
            rth = df_nq[(df_nq.index >= today_930) & (df_nq.index <= today_1600)]
            if not rth.empty:
                prth_high = float(rth["high"].max())
                prth_low = float(rth["low"].min())
                prth_close = float(rth["close"].iloc[-1])
                lines = ["== TOMORROW'S SETUP =="]
                lines.append(f"pRTH High: {prth_high:,.2f} | pRTH Low: {prth_low:,.2f} | Close: {prth_close:,.2f}")
                lines.append(f"Overnight open vs pRTH will determine Gap Up/Down/Inside scenario")
                
                # Fetch Candle Science scenarios for tomorrow's open
                try:
                    cs = get_candle_science_read(ticker=nq_ticker, mode="close")
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
        if df_nq is not None and not df_nq.empty:
            rth = df_nq[(df_nq.index >= today_930) & (df_nq.index <= today_1600)]
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
            nq_ctx_morning = build_overnight_context(loader, nq_ticker)
            df_nq_recent = df_nq[df_nq.index >= (pd.Timestamp.now(ET) - timedelta(days=10))]
            if df_nq_recent.empty:
                df_nq_recent = df_nq
            engine = NQStatsEngine(df_nq_recent, ticker=nq_ticker)
            engine.process()
            latest = engine.get_latest_status()
            aln_bias = "NEUTRAL"
            aln_pattern = latest.get("aln", "N/A")
            broken = latest.get("broken", "N/A")
            if aln_pattern == "LPEU" and "Held/Held" in broken:
                aln_bias = "BULLISH"
            elif aln_pattern == "LPEU" and "Broken/Held" in broken:
                aln_bias = "STRONG BEARISH (REVERSAL)"
            elif aln_pattern == "LPED":
                aln_bias = "BEARISH"
            elif "Broken/Broken" in broken:
                aln_bias = "NEUTRAL"
            s1 = "BULLISH" if "BULLISH" in aln_bias else ("BEARISH" if "BEARISH" in aln_bias else "NEUTRAL")

            rth_scenario = "INSIDE"
            if nq_ctx_morning:
                prth_h = nq_ctx_morning.get("prior_rth_high")
                prth_l = nq_ctx_morning.get("prior_rth_low")
                cur = nq_ctx_morning.get("close", 0)
                if prth_h and prth_l and cur:
                    if cur > prth_h:
                        rth_scenario = "GAP_UP"
                    elif cur < prth_l:
                        rth_scenario = "GAP_DOWN"
            s2 = "BULLISH" if rth_scenario == "GAP_UP" else ("BEARISH" if rth_scenario == "GAP_DOWN" else "NEUTRAL")

            try:
                cs = get_candle_science_read(ticker=nq_ticker)
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

    return "\n\n".join(sections)


def build_compact_weekly(briefing_data: dict) -> str:
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
    tickers = briefing_data.get("tickers", [])

    lines = [
        f"## WEEKLY MACRO EXECUTION HORIZON -- {header_dates}",
        "",
        "### 0. Prior Week Review",
        "{{PRIOR_WEEK_REVIEW_ANALYSIS}}",
        "",
        "### 1. Executive Risk Core",
        "{{EXECUTIVE_RISK_CORE}}",
        "",
        "### 2. High-Impact Economic Milestones",
    ]

    if events:
        for index, event in enumerate(events):
            lines.append(format_weekly_event_heading(event))
            lines.append(f"  > **Tactical Impact:** {{{{EVENT_IMPACT_{index}}}}}")
    else:
        lines.append("No market-moving economic events scheduled this week.")

    for ticker_block in tickers:
        ticker = ticker_block.get("ticker", "UNKNOWN")
        proxy_context = ticker_block.get("proxy_context", {})
        proxy_symbol = proxy_context.get("proxy_symbol")

        header = f"### 3. {ticker} -- Structural Sandbox"
        if ticker == "SPY":
            header = "### 3. SPY (MES levels) -- Structural Sandbox"
        elif ticker == "QQQ":
            header = "### 3. QQQ (MNQ levels) -- Structural Sandbox"

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
            f"**Boundaries**: Call Wall {call_wall} | Put Wall {put_wall} | Zero Gamma {zero_gamma}",
            f"**Risk Envelope**: EM Upper {em_upper} <-> EM Lower {em_lower} (+-{em_value}%)",
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
        "### 4. Account Protection & Invalidation Metrics",
    ])

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
        "### 5. Key Risks This Week",
        "{{KEY_RISKS}}",
        "",
        "### 6. Watch List",
        "{{WATCH_LIST}}",
    ])

    return "\n".join(lines)