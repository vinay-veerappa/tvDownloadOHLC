"""
config.py
=========
All tuneable constants for the Dealer Levels pipeline.
Edit this file to add tickers, change schedule times, or redirect output paths.
No magic numbers live anywhere else in the package.
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import time

# ---------------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------------
# Prefer the DEALER_LEVELS_ROOT environment variable if set; otherwise
# walk up from this file.  The env-var approach is more robust when the
# package is installed via pip or relocated.
_env_root = os.environ.get("DEALER_LEVELS_ROOT")
if _env_root:
    REPO_ROOT: Path = Path(_env_root).resolve()
else:
    # Default: three levels up  (options/ → streaming/ → scripts/ → root)
    REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
SECRETS_PATH: Path = REPO_ROOT / "secrets.json"
TOKEN_PATH: Path = REPO_ROOT / "token.json"

# ---------------------------------------------------------------------------
# Option-chain targets
# ---------------------------------------------------------------------------
# Tickers whose chains are pulled for each index family.
# Keys are the "canonical" names used in DealerLevels output;
# values are resolved to Schwab API symbols in schwab_symbol().
SPX_TICKERS: list[str] = ["SPX", "SPY"]    # S&P 500 family
NDX_TICKERS: list[str] = ["NDX", "QQQ"]    # Nasdaq-100 family

# Front-month futures symbols (Schwab API accepts these directly).
ES_FUTURES_SYMBOL: str = "/ES"
NQ_FUTURES_SYMBOL: str = "/NQ"
YM_FUTURES_SYMBOL: str = "/YM"
RTY_FUTURES_SYMBOL: str = "/RTY"


# Tickers to process in the daily pipeline.
# All tickers listed here will be calculated and included in the Discord update.
# Indices (SPX, QQQ, etc.) are translated to futures if a mapping exists below.
# Single stocks (AAPL, NVDA, etc.) are calculated as cash levels.
ACTIVE_TICKERS: list[str] = [
    "SPX",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "GOOGL",
    "AMZN",
    "AVGO",
]

# Tier 1: High-priority tickers scanned every cycle (each run of the loop).
# Tier 2: All other ACTIVE_TICKERS; only refreshed every TIER2_INTERVAL_SECONDS.
PRIORITY_TICKERS_FILE: Path = REPO_ROOT / "priority_tickers.json"

def get_priority_tickers() -> list[str]:
    import json
    if PRIORITY_TICKERS_FILE.exists():
        try:
            with open(PRIORITY_TICKERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return ["SPX", "SPY", "QQQ"]

PRIORITY_TICKERS: list[str] = get_priority_tickers()
TIER2_INTERVAL_SECONDS: int = 600   # 10 minutes for lower-priority tickers

# Maps each primary index to its corresponding futures symbol.
INDEX_TO_FUTURES: dict[str, str] = {
    "SPX": ES_FUTURES_SYMBOL,
    "QQQ": NQ_FUTURES_SYMBOL,
    "DIA": YM_FUTURES_SYMBOL,
    "IWM": RTY_FUTURES_SYMBOL,
}

# yfinance ticker mappings for futures symbols.
FUTURES_YF_MAP: dict[str, str] = {
    "/ES": "ES=F",
    "/NQ": "NQ=F",
    "/RTY": "RTY=F",
    "/YM": "YM=F",
    "/VX": "VX=F",
    "/GC": "GC=F",
    "/CL": "CL=F",
    "/SI": "SI=F",
    "/HG": "HG=F",
    "/NG": "NG=F",
    "/ZB": "ZB=F",
    "/ZT": "ZT=F",
    "/ZF": "ZF=F",
    "/ZN": "ZN=F"
}

# Fallback tickers used when the primary index has low liquidity/OI.
ETF_FALLBACK: dict[str, str] = {
    "SPX": "SPY", 
    "QQQ": "NDX",
}

# Schwab API requires a leading "$" for cash CBOE indices.
SCHWAB_INDEX_PREFIX: dict[str, str] = {
    "SPX":  "$SPX",
    "SPXW": "$SPXW",
    "NDX":  "$NDX",
    "NDXP": "$NDXP",
    "DJX":  "$DJX",
    "RUT":  "$RUT",
}

# Standard equity-index option contract multiplier.
CONTRACT_MULTIPLIER: int = 100

# ---------------------------------------------------------------------------
# Expiration windows
# ---------------------------------------------------------------------------
# 0 = today (0DTE), 1 = next calendar day (1DTE).
DTE_TARGETS: list[int] = list(range(14))

# Multi-expiry targets for Macro HTF (Weekly/Monthly)
MACRO_DTE_TARGETS: list[int] = [0, 7, 30, 45, 60, 90, 120, 150, 180, 270, 365]

# ---------------------------------------------------------------------------
# GEX / wall detection
# ---------------------------------------------------------------------------
# Minimum open interest for a strike to qualify as a Call/Put Wall candidate.
MIN_OI_THRESHOLD: int = 50
# Minimum contracts with non-zero open interest required before an index chain
# is considered actionable for wall/GEX profiling during off-hours/weekends.
MIN_NONZERO_OI_CONTRACTS: int = 25

# ---------------------------------------------------------------------------
# Position weighting mode
# ---------------------------------------------------------------------------
# Controls how open-interest and volume are combined when computing GEX and DEX.
#   "OI"         — Open interest only (default, classic GEX)
#   "VOLUME"     — Today's volume only (reflects real-money conviction today)
#   "OI_VOL_SUM" — OI + Volume (emphasises active strikes; useful on opex/FOMC)
#   "OI_VOL_MAX" — max(OI, Volume) per contract
WEIGHT_MODE: str = "OI"

# ---------------------------------------------------------------------------
# True  → use ATM straddle (call ask + put ask)
# False → use IV formula: spot × ATM_IV × √(DTE/365)
USE_STRADDLE_EM: bool = False

# Optional scalar applied to the straddle price (0.85 = "85% rule").
# Set to 1.0 for the raw straddle price.
EM_STRADDLE_SCALAR: float = 0.85

# ---------------------------------------------------------------------------
# Basis Translation
# ---------------------------------------------------------------------------
# If True, use the basis established at market open (ES Open - SPX Open)
# for the entire session. If False, use the dynamic real-time basis.
USE_OPENING_BASIS: bool = True

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
DATA_DIR: Path = REPO_ROOT / "data" / "options"
# Create the directory if it doesn't exist to avoid path resolution errors.
DATA_DIR.mkdir(parents=True, exist_ok=True)

DAILY_LEVELS_JSON: Path = DATA_DIR / "daily_levels.json"
DAILY_LEVELS_TXT: Path = DATA_DIR / "daily_levels.txt"
GEX_PROFILES_JSON: Path = DATA_DIR / "gex_profiles.json"
LIVE_TREND_JSON: Path = DATA_DIR / "live_trend.json"
LOG_FILE: Path = DATA_DIR / "dealer_levels.log"
EXPECTED_MOVE_TXT: Path = DATA_DIR / "expected_moves.txt"
MACRO_LEVELS_TXT: Path = DATA_DIR / "macro_levels.txt"
MACRO_QUANT_JSON: Path = DATA_DIR / "macro_quant.json"

# ---------------------------------------------------------------------------
# Next.js UI API Integration
# ---------------------------------------------------------------------------
# The base URL for the Next.js dashboard backend.
NEXT_APP_URL: str = os.environ.get("NEXT_APP_URL", "http://localhost:3000")

# API Endpoints for GEX snapshots and Macro HTF updates.
SNAPSHOT_ENDPOINT: str = f"{NEXT_APP_URL}/api/options-live/snapshot"
MACRO_SNAPSHOT_ENDPOINT: str = f"{NEXT_APP_URL}/api/options-macro/snapshot"

# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
DISCORD_WEBHOOKS_PATH: Path = REPO_ROOT / "discord_webhooks.json"
# Key inside discord_webhooks.json to use for dealer-level notifications.
DISCORD_TARGET_KEY: str = "option-levels"
ENABLE_DISCORD_UPDATES: bool = False

# Embed accent colours (Discord integer format: 0xRRGGBB).
DISCORD_COLOR_POSITIVE: int = 0x00C853   # green  — positive GEX regime
DISCORD_COLOR_NEGATIVE: int = 0xD50000   # red    — negative GEX regime

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
SCHEDULE_TIMEZONE: str = "America/New_York"
# --- Adaptive Refreshing ---
# (RTH: 9:20 - 16:10 ET Weekdays)
EQUITY_RTH_START_TIME: time = time(8, 20)
EQUITY_RTH_END_TIME: time = time(16, 10)
RTH_T1_INTERVAL: int = 60          # Tier-1 (Priority) 1 min
RTH_T2_INTERVAL: int = 600         # Tier-2 (All others) 10 min

# (Off-hours: Monday-Friday pre/post market)
OFF_HOURS_T1_INTERVAL: int = 1800  # 30 min
OFF_HOURS_T2_INTERVAL: int = 3600  # 1 hour

# (Weekend: Fri 17:00 ET to Sun 18:00 ET)
FUTURES_CLOSE_FRIDAY_TIME: time = time(17, 0)
FUTURES_OPEN_SUNDAY_TIME: time = time(18, 0)
WEEKEND_T1_INTERVAL: int = 3600 * 4 # 4 hours
WEEKEND_T2_INTERVAL: int = 3600 * 4 # 4 hours

# (Session Rollover: 16:00 ET)
NY_SESSION_ROLLOVER_TIME: time = time(16, 0)

# --- Loop Control ---
MANUAL_TRIGGER_FILENAME: str = "manual_trigger.json"
TIER1_TICKERS_DEFAULT: list[str] = ["SPX", "SPY", "QQQ"]
LOOP_BEAT_SECONDS: int = 5 

# --- Options Chain ---
OPTION_CHAIN_WIDE_WINDOW: int = 10

# HH:MM times (24-hour clock, Eastern) at which the pipeline runs on trading days.
# NOTE: duplicates are silently ignored by run_options_levels.py, but keep
# this list clean to avoid confusion.
SCHEDULE_TIMES: list[str] = ["08:30", "09:30", "10:00", "11:00", "12:00", "13:00", "15:00"]
SCHEDULER_MISFIRE_GRACE_TIME: int = 300