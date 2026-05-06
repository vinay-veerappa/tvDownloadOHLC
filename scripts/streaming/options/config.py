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

# ---------------------------------------------------------------------------
# Ticker Profiles — per-instrument microstructure parameters
# ---------------------------------------------------------------------------
# These replace the one-size-fits-all MIN_OI_THRESHOLD with instrument-aware
# filtering. Each profile describes the OPTIONS SOURCE (where we pull the chain)
# and the TRADING TARGET (what you actually trade).

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TickerProfile:
    """Per-instrument configuration for level scoring."""
    # --- Identity ---
    canonical_name: str                 # "ES", "NQ", "SPY", "AAPL", etc.
    options_source: str                 # Ticker to pull chain for
    futures_target: str | None = None   # None for cash-settled (single stocks)
    basis_mode: str = "additive"        # "additive" or "multiplicative"

    # --- Order Book Microstructure ---
    book_depth_contracts: int = 3000    # Avg RTH top-5 depth (contracts)
    flow_significance_pct: float = 0.10 # Fraction of book = "significant"
    contract_value_per_point: int = 100 # $ per point for the options product

    # --- Noise Filters ---
    min_oi_floor: int = 50              # Absolute minimum OI (dust filter)
    strike_relevance_pct: float = 0.12  # Only consider strikes within ±12% of spot

    # --- Structural Position Detection ---
    oi_anomaly_zscore: float = 2.5      # Std devs above mean to flag as structural
    known_programs: list[str] = field(default_factory=list)  # e.g., ["JHEQX"]

    # --- Time Sensitivity ---
    opex_escalation_dte: int = 2        # Days before expiry when 0DTE gamma matters most
    roll_window_days: int = 21          # Flag structural positions within this many days of roll

@dataclass
class StructuralProgram:
    """Metadata for known institutional hedging programs."""
    name: str
    underlying: str                     # "SPX", "QQQ"
    structure: str                      # "collar", "put_spread", "call_spread"
    schedule: str                       # "quarterly", "monthly"
    roll_months: list[int]              # [3, 6, 9, 12]
    roll_window_days: int = 21
    typical_oi_min: int = 50000         # Minimum OI per leg
    moneyness_range: tuple[float, float] = (0.90, 1.10)
    description: str = ""

@dataclass
class ViewModeConfig:
    """Parameters that control what a view considers relevant."""
    name: str
    dte_range: tuple[int, int]          # (min_dte, max_dte) for level sources
    strike_range_pct: float             # How far from spot to look (% of spot)
    min_significance_for_display: str   # "PRIMARY", "SECONDARY", or "CONTEXT"
    anchor_relevance_filter: list[str]  # Which StructuralAnchor.relevance states to show
    em_expiry_display: str              # "front" (nearest) or "all" (full term structure)
    chart_zoom_pct: float               # Y-axis clamp for charting (% of spot)

    @property
    def significance_mask(self) -> set[str]:
        """Derive the set of allowed significance tags based on the display threshold."""
        ranks = {"PRIMARY": 0, "SECONDARY": 1, "CONTEXT": 2}
        min_rank = ranks.get(self.min_significance_for_display, 2)
        return {s for s, r in ranks.items() if r <= min_rank}

# ── View Mode Definitions ───────────────────────────────────────────

INTRADAY_VIEW = ViewModeConfig(
    name="INTRADAY",
    dte_range=(0, 14),
    strike_range_pct=0.06,              # ±6% of spot — roughly 2× daily EM
    min_significance_for_display="SECONDARY",
    anchor_relevance_filter=["ACTIVE", "CRITICAL"],
    em_expiry_display="front",
    chart_zoom_pct=0.04,                # ±4% chart clamp (tighter for day trading)
)

MACRO_VIEW = ViewModeConfig(
    name="MACRO",
    dte_range=(0, 365),
    strike_range_pct=0.15,              # ±15% of spot — covers quarterly range
    min_significance_for_display="PRIMARY",  # Only show what really matters at this scale
    anchor_relevance_filter=["DORMANT", "APPROACHING", "ACTIVE", "CRITICAL"],
    em_expiry_display="all",
    chart_zoom_pct=0.08,                # ±8% chart clamp
)

VIEW_MODES: dict[str, ViewModeConfig] = {
    "INTRADAY": INTRADAY_VIEW,
    "MACRO": MACRO_VIEW,
}

# ── Library of Ticker Profiles ─────────────────────────────────────

TICKER_PROFILES: dict[str, TickerProfile] = {
    "SPX": TickerProfile("SPX", "SPX", "/ES", "additive", book_depth_contracts=4500, flow_significance_pct=0.12, contract_value_per_point=50, min_oi_floor=500, strike_relevance_pct=0.12, oi_anomaly_zscore=2.8, known_programs=["JHEQX"]),
    "SPY": TickerProfile("SPY", "SPY", "/ES", "multiplicative", book_depth_contracts=25000, contract_value_per_point=100, min_oi_floor=500),
    "NDX": TickerProfile("NDX", "NDX", "/NQ", "additive", book_depth_contracts=1200, flow_significance_pct=0.10, contract_value_per_point=20, min_oi_floor=200, strike_relevance_pct=0.12, oi_anomaly_zscore=2.5),
    "QQQ": TickerProfile("QQQ", "QQQ", "/NQ", "multiplicative", book_depth_contracts=15000, contract_value_per_point=100, min_oi_floor=300),
    "IWM": TickerProfile("IWM", "IWM", "/RTY", "multiplicative", book_depth_contracts=800, flow_significance_pct=0.12, contract_value_per_point=100, min_oi_floor=200, strike_relevance_pct=0.12),
    "DIA": TickerProfile("DIA", "DIA", "/YM", "multiplicative", book_depth_contracts=600, flow_significance_pct=0.12, contract_value_per_point=100, min_oi_floor=100, strike_relevance_pct=0.10),
    "AAPL": TickerProfile("AAPL", "AAPL", None, book_depth_contracts=5000, flow_significance_pct=0.08, contract_value_per_point=100, min_oi_floor=500, strike_relevance_pct=0.08),
    "NVDA": TickerProfile("NVDA", "NVDA", None, book_depth_contracts=4000, flow_significance_pct=0.08, contract_value_per_point=100, min_oi_floor=500, strike_relevance_pct=0.10),
    "TSLA": TickerProfile("TSLA", "TSLA", None, book_depth_contracts=3000, flow_significance_pct=0.10, contract_value_per_point=100, min_oi_floor=500, strike_relevance_pct=0.12),
}

def get_ticker_profile(ticker: str) -> TickerProfile:
    """Look up the profile for a ticker. Returns a generic default if unknown."""
    if ticker in TICKER_PROFILES:
        return TICKER_PROFILES[ticker]
    return TickerProfile(
        canonical_name=ticker,
        options_source=ticker,
        futures_target=None,
        book_depth_contracts=2000,
        flow_significance_pct=0.10,
        contract_value_per_point=100,
        min_oi_floor=100,
        strike_relevance_pct=0.10,
    )

# ── Institutional Programs ───────────────────────────────────────────

STRUCTURAL_PROGRAMS: dict[str, StructuralProgram] = {
    "JHEQX": StructuralProgram(
        name="JPM Hedged Equity (JHEQX)",
        underlying="SPX",
        structure="collar",
        schedule="quarterly",
        roll_months=[3, 6, 9, 12],
        roll_window_days=21,
        typical_oi_min=80000,
        moneyness_range=(0.92, 1.06),
        description="JPMorgan Hedged Equity Fund quarterly rebalance collar"
    ),
    "JEPI": StructuralProgram(
        name="JPM Equity Premium Income (JEPI)",
        underlying="SPX",
        structure="call_spread",
        schedule="monthly",
        roll_months=list(range(1, 13)),
        roll_window_days=7,
        typical_oi_min=20000,
        moneyness_range=(1.00, 1.05),
        description="JPMorgan Equity Premium Income ETF weekly short calls"
    ),
}


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

# Reverse map for navigating from futures to indices for mapped variants.
FUTURES_TO_INDEX: dict[str, str] = {v: k for k, v in INDEX_TO_FUTURES.items()}

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

# Contract multipliers for futures symbols (dollars per point/contract).
# Standard index/equity options default to 100 via CONTRACT_MULTIPLIER.
FUTURES_MULTIPLIER: dict[str, int] = {
    "/ES": 50,
    "/NQ": 20,
    "/YM": 5,
    "/RTY": 50,
    "/VX": 1000,
    "/GC": 100,
    "/CL": 1000,
    "/SI": 5000,
}

# Fallback tickers used when the primary index has low liquidity/OI.
ETF_FALLBACK: dict[str, str] = {
    "SPX": "SPY", 
    "NDX": "QQQ",
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

# Tickers that typically have very dense chains and may cause buffer overflows 
# when fetching a full year's range in one call.
LARGE_INDICES: set[str] = {"SPX", "NDX", "RUT", "SPXW", "NDXP"}

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
INTRADAY_LEVELS_JSON: Path = DATA_DIR / "intraday_levels.json"
MACRO_LEVELS_JSON: Path = DATA_DIR / "macro_levels.json"
DAILY_LEVELS_TXT: Path = DATA_DIR / "daily_levels.txt"
GEX_PROFILES_JSON: Path = DATA_DIR / "gex_profiles.json"
LIVE_TREND_JSON: Path = DATA_DIR / "live_trend.json"
LOG_FILE: Path = DATA_DIR / "dealer_levels.log"
EXPECTED_MOVE_TXT: Path = DATA_DIR / "expected_moves.txt"
MACRO_LEVELS_TXT: Path = DATA_DIR / "macro_levels.txt"
MACRO_QUANT_JSON: Path = DATA_DIR / "macro_quant.json"
SCORED_LEVELS_TXT: Path = DATA_DIR / "scored_levels.txt"
SCORED_MACRO_LEVELS_TXT: Path = DATA_DIR / "scored_macro_levels.txt"
BASIS_ANCHORS_JSON: Path = DATA_DIR / "basis_anchors.json"

# ---------------------------------------------------------------------------
# Next.js UI API Integration
# ---------------------------------------------------------------------------
# The base URL for the Next.js dashboard backend.
NEXT_APP_URL: str = os.environ.get("NEXT_APP_URL", "http://localhost:3000")

# # API Endpoints for GEX snapshots and Macro HTF updates.
SNAPSHOT_ENDPOINT: str = f"{NEXT_APP_URL}/api/options-live/snapshot"
MACRO_SNAPSHOT_ENDPOINT: str = f"{NEXT_APP_URL}/api/options-macro/snapshot"

# Schwab Unified Hub
HUB_HOST: str = os.environ.get("HUB_HOST", "127.0.0.1")
HUB_PORT: int = int(os.environ.get("HUB_PORT", 8080))
HUB_URL: str = os.environ.get("HUB_URL", f"http://{HUB_HOST}:{HUB_PORT}")
HUB_WS_ENDPOINT: str = HUB_URL.replace("http://", "ws://") + "/ws"
HUB_RESOLVE_ENDPOINT: str = f"{HUB_URL}/resolve"

# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
DISCORD_WEBHOOKS_PATH: Path = REPO_ROOT / "discord_webhooks.json"
# Key inside discord_webhooks.json to use for dealer-level notifications.
DISCORD_TARGET_KEY: str = "option-levels"
DISCORD_MACRO_KEY: str = "macro-alerts"
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
SCHEDULE_TIMES: list[str] = ["08:30", "09:30", "10:00", "11:00", "12:00", "13:00", "15:00", "16:00", "16:15"]
SCHEDULER_MISFIRE_GRACE_TIME: int = 300