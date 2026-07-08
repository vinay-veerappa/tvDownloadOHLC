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
    config.date_end = now.strftime("%Y-%m-%d")
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