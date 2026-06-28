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


# ── ETF Scale Note ────────────────────────────────────────────────
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

async def fetch_week_events(start_date: date, end_date: date) -> list[dict]:
    """Fetch economic events for a date range from the Prisma SQLite DB."""
    db = await get_db()
    from datetime import datetime as dt_cls
    
    # ET timezone is defined at the top of briefing_core.py
    start_dt = dt_cls.combine(start_date, dt_cls.min.time(), tzinfo=ET)
    end_dt = dt_cls.combine(end_date, dt_cls.max.time(), tzinfo=ET)
    
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
            # Filter out low impact news to avoid clutter
            if e.impact and e.impact.upper() == "LOW":
                continue
                
            # e.datetime is a python datetime object
            evt_dt = e.datetime.astimezone(ET) if e.datetime.tzinfo else e.datetime.replace(tzinfo=ET)
            res.append({
                "date": evt_dt.strftime("%Y-%m-%d"),
                "time_et": evt_dt.strftime("%H:%M ET"),
                "name": e.name,
                "impact": e.impact.upper()
            })
        return res
    except Exception as e:
        log.warning(f"Failed to fetch economic events from DB: {e}")
        return []


# ── Utility ───────────────────────────────────────────────────────

def get_week_label(reference_date: date | None = None) -> str:
    """Get a human-readable week label (e.g., 'Week of Jun 30 – Jul 4, 2026')."""
    if reference_date is None:
        reference_date = datetime.now(ET).date()

    # Find the Monday of the upcoming week
    days_to_monday = (7 - reference_date.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7  # If today is Monday, go to next Monday
    monday = reference_date + timedelta(days=days_to_monday)
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