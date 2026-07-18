"""
data.py — Profiler data loading and constants.

Loads profiler data from the same JSON files the WebUI backend uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[4]
_DATA = _REPO / "data"

# Status code mappings
STATUS_SHORT = {
    "Long True": "LT", "Long False": "LF",
    "Short True": "ST", "Short False": "SF",
    "None": "—",
}
SHORT_TO_FULL = {v: k for k, v in STATUS_SHORT.items() if v != "—"}
ALL_STATUSES = ["Long True", "Long False", "Short True", "Short False"]
ALL_SHORT = ["LT", "LF", "ST", "SF"]

# Level names tracked in profiler data
LEVEL_NAMES = [
    "pdh", "pdl", "pdm",
    "p12h", "p12m", "p12l",
    "ny_p12h", "ny_p12m", "ny_p12l",
    "daily_open", "midnight_open", "open_0730",
    "asia_mid", "london_mid", "ny1_mid", "ny2_mid",
]

# Hit rate keys (matches WebUI backend's level_keys in get_filtered_stats)
# Includes both current-day session mids (asia_mid, london_mid, etc.) and
# previous-day session mids (prev_asia_mid, etc.) used by the DailyLevels component.
HIT_KEYS = [
    "hit_pdh", "hit_pdm", "hit_pdl",
    "hit_midnight", "hit_0730", "hit_daily_open",
    "hit_ny_p12h", "hit_ny_p12m", "hit_ny_p12l",
    "hit_p12h", "hit_p12m", "hit_p12l",
    "hit_p_asia_mid", "hit_p_lon_mid", "hit_p_ny1_mid", "hit_p_ny2_mid",
    "hit_prev_asia_mid", "hit_prev_lon_mid", "hit_prev_ny1_mid", "hit_prev_ny2_mid",
]

# Context dependency chain (matches WebUI's CONTEXT_CHAIN)
CONTEXT_CHAIN: Dict[str, List[tuple]] = {
    "Asia":   [("prev", "NY1"), ("prev", "NY2")],
    "London": [("curr", "Asia"), ("prev", "NY2")],
    "NY1":    [("curr", "Asia"), ("curr", "London")],
    "NY2":    [("curr", "Asia"), ("curr", "London"), ("curr", "NY1")],
}

# Supported tickers
TICKERS = ["NQ1", "ES1", "CL1", "GC1", "RTY1", "YM1", "SPX", "VIX"]

# Supported target sessions
TARGET_SESSIONS = ["Asia", "London", "NY1", "NY2"]


def load_profiler(ticker: str = "NQ1") -> List[dict]:
    """Load profiler session records from JSON."""
    path = _DATA / f"{ticker}_profiler.json"
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("sessions", [])
    return data


def load_level_touches(ticker: str = "NQ1") -> Dict[str, dict]:
    """Load level touches keyed by date."""
    path = _DATA / f"{ticker}_level_touches.json"
    with open(path) as f:
        return json.load(f)


def load_hod_lod(ticker: str = "NQ1") -> Dict[str, dict]:
    """Load daily HOD/LOD keyed by date (adjusted prices)."""
    path = _DATA / f"{ticker}_daily_hod_lod.json"
    with open(path) as f:
        return json.load(f)


def load_hod_lod_unadjusted(ticker: str = "NQ1") -> Dict[str, dict]:
    """Load daily HOD/LOD with unadjusted prices (matching WebUI frontend)."""
    path = _DATA / f"{ticker}_daily_hod_lod_unadjusted.json"
    with open(path) as f:
        return json.load(f)


def load_lookup(ticker: str = "NQ1") -> dict:
    """Load precomputed profiler lookup table."""
    path = _DATA / "derived" / f"{ticker}_profiler_lookup.json"
    with open(path) as f:
        return json.load(f)
