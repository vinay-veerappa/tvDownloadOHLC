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

# Maps each primary index to its corresponding futures symbol.
INDEX_TO_FUTURES: dict[str, str] = {
    "SPX": ES_FUTURES_SYMBOL,
    "QQQ": NQ_FUTURES_SYMBOL,
    "DIA": YM_FUTURES_SYMBOL,
    "IWM": RTY_FUTURES_SYMBOL,
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
DTE_TARGETS: list[int] = [0, 1]

# ---------------------------------------------------------------------------
# GEX / wall detection
# ---------------------------------------------------------------------------
# Minimum open interest for a strike to qualify as a Call/Put Wall candidate.
MIN_OI_THRESHOLD: int = 50
# Minimum contracts with non-zero open interest required before an index chain
# is considered actionable for wall/GEX profiling during off-hours/weekends.
MIN_NONZERO_OI_CONTRACTS: int = 25

# ---------------------------------------------------------------------------
# Expected-Move calculation
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
OUTPUT_DIR: Path = REPO_ROOT
DAILY_LEVELS_JSON: Path = OUTPUT_DIR / "daily_levels.json"
DAILY_LEVELS_TXT: Path = OUTPUT_DIR / "daily_levels.txt"
LOG_FILE: Path = OUTPUT_DIR / "dealer_levels.log"

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
# HH:MM times (24-hour clock, Eastern) at which the pipeline runs on trading days.
# NOTE: duplicates are silently ignored by run_options_levels.py, but keep
# this list clean to avoid confusion.
SCHEDULE_TIMES: list[str] = ["08:30", "09:30", "10:00", "11:00", "12:00", "13:00", "15:00"]