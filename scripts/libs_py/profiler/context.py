"""
context.py - Live trading day context provider.

Reads historical 1m Parquet fused with live storage Parquet, runs NQStatsEngine,
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

# Cache to avoid repeated historical parquet loads in persistent sessions
_DF_CACHE = {}

# Live storage filename per ticker
_LIVE_FILES = {
    "NQ1":  "live_storage_-NQ.parquet",
    "ES1":  "live_storage_-ES.parquet",
    "YM1":  "live_storage_-YM.parquet",
    "RTY1": "live_storage_-RTY.parquet",
    "CL1":  "live_storage_-CL.parquet",
    "GC1":  "live_storage_-GC.parquet",
}

# NQStatsEngine returns short codes — map to full strings for JSON filtering
_STATUS_EXPAND = {
    "LT": "Long True",
    "LF": "Long False",
    "ST": "Short True",
    "SF": "Short False",
    "Long True":   "Long True",
    "Long False":  "Long False",
    "Short True":  "Short True",
    "Short False": "Short False",
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

    Loads historical 1m Parquet + live storage Parquet, fuses them,
    runs NQStatsEngine, and returns the latest session statuses.

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

    # 1. Load live storage parquet (Primary source for current sessions)
    live_file = _LIVE_FILES.get(ticker)
    if not live_file:
        print(f"  [context] No live file mapping for {ticker}")
        return empty

    live_path = _LIVE_DIR / live_file
    if not live_path.exists():
        print(f"  [context] Live storage not found: {live_path}")
        return empty

    try:
        df = pd.read_parquet(live_path)
    except Exception as e:
        print(f"  [context] error reading live storage: {e}")
        return empty

    # 2. Convert to DatetimeIndex (NQStatsEngine requirement)
    df = _to_datetime_index(df)
    if df is None or df.empty:
        print("  [context] Could not build DatetimeIndex from parquet")
        return empty

    # 3. Restrict to tail for speed (NQStatsEngine only needs recent context)
    # 7 days is plenty for cross-day shifts
    df = df.tail(10080) # 7 days * 1440 mins
    
    # 4. Localize to ET as engine expects
    if df.index.tz is None:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')
    elif str(df.index.tz) != 'US/Eastern':
        df = df.tz_convert('US/Eastern')

    # 5. Run NQStatsEngine
    try:
        from scripts.libs_py.nqstats.engine import NQStatsEngine
        engine = NQStatsEngine(df, ticker=ticker)
        engine.process()
        latest = engine.get_latest_status()
    except Exception as e:
        print(f"  [context] NQStatsEngine error: {e}")
        return empty

    # 6. Extract and expand status codes to full strings
    # Keys from NQStatsEngine (with fixed 'box' suffix)
    def _exp(k):
        return _STATUS_EXPAND.get(latest.get(k)) if latest.get(k) else None

    return {
        "prev_ny1_status":  _exp("prev_ny1_status"),
        "prev_ny2_status":  _exp("prev_ny2_status"),
        "prev_asia_status": _exp("prev_asia_status"),
        "prev_lon_status":  _exp("prev_london_status"), # Engine uses prev_london_status
        "prev_ny1_broken":  bool(latest.get("prev_ny1_broken", False)),
        "prev_ny2_broken":  bool(latest.get("prev_ny2_broken", False)),
        # Current day
        "asia_status": _exp("asiabox_status"),
        "lon_status":  _exp("londonbox_status"),
        "ny1_status":  _exp("ny1box_status"),
        "ny2_status":  _exp("ny2box_status"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fuse(hist_df: pd.DataFrame, live_df: pd.DataFrame) -> pd.DataFrame:
    """Merge historical and live DataFrames, deduplicating on time (Unix seconds)."""

    def _extract_time_col(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure DataFrame has a numeric 'time' column (Unix seconds)."""
        df = df.copy()
        # If already DatetimeIndex → convert to Unix seconds
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            idx_col = df.columns[0]
            df["time"] = pd.to_datetime(df[idx_col], utc=True, errors="coerce").astype("int64") // 10**9
            df = df.drop(columns=[idx_col], errors="ignore")
        # Rename alternate time column names
        for alias in ("timestamp", "ts", "Timestamp"):
            if alias in df.columns and "time" not in df.columns:
                df = df.rename(columns={alias: "time"})
                break
        # Normalize scale to Unix seconds
        if "time" in df.columns:
            t = pd.to_numeric(df["time"], errors="coerce")
            # Detect and convert nanoseconds / microseconds / milliseconds
            t_max = t.dropna().max() if not t.dropna().empty else 0
            if t_max > 1e16:
                t = t // 10**9
            elif t_max > 1e13:
                t = t // 10**6
            elif t_max > 1e10:
                t = t // 10**3
            df["time"] = t
        return df

    hist_df = _extract_time_col(hist_df)
    live_df = _extract_time_col(live_df)

    if "time" not in hist_df.columns or "time" not in live_df.columns:
        return hist_df  # Can't merge without time column

    # Keep overlapping OHLCV columns
    cols = [c for c in ["time", "open", "high", "low", "close", "volume"]
            if c in hist_df.columns and c in live_df.columns]
    combined = pd.concat([hist_df[cols], live_df[cols]])
    # Drop rows with NaN or invalid timestamps
    combined = combined.dropna(subset=["time"])
    combined = combined[combined["time"].between(946_684_800, 4_102_444_800)]
    combined = combined.drop_duplicates(subset=["time"], keep="last")
    return combined.sort_values("time").reset_index(drop=True)


def _to_datetime_index(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Convert to UTC DatetimeIndex as required by NQStatsEngine."""
    try:
        if isinstance(df.index, pd.DatetimeIndex):
            return df

        df = df.copy()
        time_col = None
        if "timestamp" in df.columns:
            time_col = "timestamp"
        elif "time" in df.columns:
            time_col = "time"
        
        if not time_col:
            return None

        # Try to parse the time column
        vals = df[time_col]
        if pd.api.types.is_numeric_dtype(vals):
            # Assume Unix seconds if numeric
            df["datetime"] = pd.to_datetime(vals, unit="s", utc=True)
        else:
            # Assume string/object
            df["datetime"] = pd.to_datetime(vals, utc=True)

        df = df.set_index("datetime")
        return df
    except Exception as e:
        print(f"  [context] DatetimeIndex conversion error: {e}")
        return None


def _expand(val) -> Optional[str]:
    """Expand short status codes (LT/LF/ST/SF) to full strings. Returns None for invalid."""
    if val is None:
        return None
    s = str(val)
    if s in ("None", "none", "null", "nan", ""):
        return None
    return _STATUS_EXPAND.get(s)  # Returns None if not a recognized status code
