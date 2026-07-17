"""
context.py - Live trading day context provider.

Reads live storage Parquet, runs SessionBoxEngine (lightweight profiler-only),
and extracts current session statuses for use as profiler filters.

The Parquet file is the single source of truth — no API calls.
"""

import pandas as pd
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Optional, Dict
import pytz

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
_LIVE_DIR = _DATA_DIR / "live"

ET = pytz.timezone("US/Eastern")

# Live storage filename per ticker
_LIVE_FILES = {
    "NQ1":  "live_storage_-NQ.parquet",
    "ES1":  "live_storage_-ES.parquet",
    "YM1":  "live_storage_-YM.parquet",
    "RTY1": "live_storage_-RTY.parquet",
    "CL1":  "live_storage_-CL.parquet",
    "GC1":  "live_storage_-GC.parquet",
}


# ---------------------------------------------------------------------------
# Trading date / session utilities
# ---------------------------------------------------------------------------

def get_current_trading_date() -> str:
    """
    Returns today's institutional trading date as 'YYYY-MM-DD'.

    The trading day starts at 18:00 ET (Globex open):
      - ET time >= 18:00  →  trading date = TOMORROW (next calendar day)
      - ET time <  18:00  →  trading date = TODAY
    """
    now_et = datetime.now(ET)
    if now_et.time() >= dt_time(18, 0):
        td = (now_et + timedelta(days=1)).date()
    else:
        td = now_et.date()
    return td.strftime("%Y-%m-%d")


def get_current_session() -> Optional[str]:
    """
    Returns the name of the currently active session (ET time), or None.

    Windows (ET):
      Asia:   18:00 – 02:30
      London: 02:30 – 07:30
      NY1:    07:30 – 11:30
      NY2:    11:30 – 13:00
    """
    t = datetime.now(ET).time()
    if t >= dt_time(18, 0) or t < dt_time(2, 30):
        return "Asia"
    elif dt_time(2, 30) <= t < dt_time(7, 30):
        return "London"
    elif dt_time(7, 30) <= t < dt_time(11, 30):
        return "NY1"
    elif dt_time(11, 30) <= t < dt_time(13, 0):
        return "NY2"
    return None


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def get_live_context(ticker: str = "NQ1") -> Dict:
    """
    Build the filter context dict for today's trading day directly from Parquet.

    Uses SessionBoxEngine (lightweight, profiler-only) instead of the heavy
    NQStatsEngine. Only computes box statuses — no ALN, IB bias, etc.

    Returns:
      {
        "prev_ny1_status", "prev_ny2_status",    <- previous trading day (prev-shifted)
        "prev_asia_status", "prev_lon_status",
        "prev_ny1_broken", "prev_ny2_broken",
        "asia_status", "lon_status",             <- current trading day
        "ny1_status", "ny2_status",
      }
    """
    empty = {
        "prev_ny1_status": None, "prev_ny2_status": None,
        "prev_asia_status": None, "prev_lon_status": None,
        "prev_ny1_broken": False, "prev_ny2_broken": False,
        "asia_status": None, "lon_status": None,
        "ny1_status": None, "ny2_status": None,
    }

    try:
        from .engine import SessionBoxEngine
        engine = SessionBoxEngine.from_live(ticker)
        live = engine.get_live_sessions()
        prev = engine.get_prev_context()

        return {
            "prev_ny1_status":  prev.get("prev_ny1_status"),
            "prev_ny2_status":  prev.get("prev_ny2_status"),
            "prev_asia_status": prev.get("prev_asia_status"),
            "prev_lon_status":  prev.get("prev_london_status"),
            "prev_ny1_broken":  prev.get("prev_ny1_broken", False),
            "prev_ny2_broken":  prev.get("prev_ny2_broken", False),
            "asia_status": live.get("Asia", {}).get("status") if live.get("Asia") else None,
            "lon_status":  live.get("London", {}).get("status") if live.get("London") else None,
            "ny1_status":  live.get("NY1", {}).get("status") if live.get("NY1") else None,
            "ny2_status":  live.get("NY2", {}).get("status") if live.get("NY2") else None,
        }
    except Exception as e:
        print(f"  [context] SessionBoxEngine error: {e}")
        return empty


# ── Re-export for convenience ───────────────────────────────────────────
from .engine import SessionBoxEngine  # noqa: E402, F401
