"""
config.py
=========
All tuneable constants for the Dealer Levels pipeline.
Edit this file to add tickers, change schedule times, or redirect output paths.
No magic numbers live anywhere else in the package.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Repository root — two levels up: options/ → streaming/ → scripts/ → root
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

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

# Cash-index tickers selected for GEX calculation (one per family).
# If the chain fetch fails for the index, the ETF fallback is used instead.
PRIMARY_INDEX_TICKERS: list[str] = ["SPX", "NDX"]
ETF_FALLBACK: dict[str, str] = {"SPX": "SPY", "NDX": "QQQ"}
TEST_OUTPUT_TICKERS: list[str] = ["SPX", "NDX", "SPY", "QQQ", "IWM", "DIA", "RUT", "DJX"]

# Maps each primary index to its corresponding futures symbol.
INDEX_TO_FUTURES: dict[str, str] = {
    "SPX": ES_FUTURES_SYMBOL,
    "NDX": NQ_FUTURES_SYMBOL,
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
USE_STRADDLE_EM: bool = True

# Optional scalar applied to the straddle price (0.85 = "85% rule").
# Set to 1.0 for the raw straddle price.
EM_STRADDLE_SCALAR: float = 0.85

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR: Path = REPO_ROOT / "data"
DAILY_LEVELS_JSON: Path = OUTPUT_DIR / "daily_levels.json"
DAILY_LEVELS_TXT: Path = OUTPUT_DIR / "daily_levels.txt"
LOG_FILE: Path = OUTPUT_DIR / "dealer_levels.log"

# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
DISCORD_WEBHOOKS_PATH: Path = REPO_ROOT / "discord_webhooks.json"
# Key inside discord_webhooks.json to use for dealer-level notifications.
DISCORD_TARGET_KEY: str = "alerts"
ENABLE_DISCORD_UPDATES: bool = False

# Embed accent colours (Discord integer format: 0xRRGGBB).
DISCORD_COLOR_POSITIVE: int = 0x00C853   # green  — positive GEX regime
DISCORD_COLOR_NEGATIVE: int = 0xD50000   # red    — negative GEX regime

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
SCHEDULE_TIMEZONE: str = "America/New_York"
# HH:MM times (24-hour clock, Eastern) at which the pipeline runs on trading days.
SCHEDULE_TIMES: list[str] = ["08:30", "11:00"]
