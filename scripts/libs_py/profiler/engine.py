"""
SessionBoxEngine — Lightweight engine for profiler session box status.

Replaces the heavy NQStatsEngine for use cases that ONLY need profiler
box statuses (LT/LF/ST/SF + broken + prev-day context). Skips ALN,
IB bias, hourly mode, noon curve, and all other NQStats computations.

Typical usage:
    from scripts.libs_py.profiler.engine import SessionBoxEngine

    engine = SessionBoxEngine.from_live("NQ1")
    live_sessions = engine.get_live_sessions()
    # → {"Asia": {"status": "Long True", "broken": False}, ...}

    prev_context = engine.get_prev_context()
    # → {"prev_ny1_status": "Short False", "prev_ny2_broken": True, ...}

Then pass to compute_profiler():
    from scripts.trader.signals.profiler import compute_profiler
    result = compute_profiler("NQ1", live_sessions=live_sessions)
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import pytz

from .session_box_status import (
    compute_box_status,
    compute_box_broken,
    compute_prev_day_shifts,
    get_latest_box_status,
    get_latest_prev_context,
    BOX_SESSION_MAP,
    BOX_NAMES,
    STATUS_SHORT_TO_FULL,
)

ET = pytz.timezone("US/Eastern")
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
_LIVE_DIR = _DATA_DIR / "live"

_LIVE_FILES = {
    "NQ1":  "live_storage_-NQ.parquet",
    "ES1":  "live_storage_-ES.parquet",
    "YM1":  "live_storage_-YM.parquet",
    "RTY1": "live_storage_-RTY.parquet",
    "CL1":  "live_storage_-CL.parquet",
    "GC1":  "live_storage_-GC.parquet",
}


class SessionBoxEngine:
    """Lightweight engine that computes ONLY profiler session box statuses.

    Does NOT compute ALN, IB bias, hourly mode, noon curve, or any
    other NQStats-specific metrics. Use this when you only need
    profiler data for live_sessions or context filtering.

    Attributes:
        ticker: Ticker symbol (e.g. "NQ1").
        df: 1-minute OHLC DataFrame (ET-localized).
        boxes: Session box ranges DataFrame.
        status: Box status DataFrame (LT/LF/ST/SF).
        broken: Box broken status DataFrame.
        prev: Previous-day shifted context DataFrame.
    """

    def __init__(self, df_1m: pd.DataFrame, ticker: str = "NQ1"):
        """Initialize with a 1-minute OHLC DataFrame.

        Args:
            df_1m: 1-minute OHLC DataFrame. Index should be DatetimeIndex
                   (any timezone — will be normalized to US/Eastern).
            ticker: Ticker symbol for display/logging.
        """
        self.ticker = ticker
        self._raw_df = df_1m
        self._processed = False

        # Results populated by process()
        self.df: Optional[pd.DataFrame] = None
        self.boxes: Optional[pd.DataFrame] = None
        self.status: Optional[pd.DataFrame] = None
        self.broken: Optional[pd.DataFrame] = None
        self.prev: Optional[pd.DataFrame] = None

    # ── Factory methods ──────────────────────────────────────────────────

    @classmethod
    def from_live(cls, ticker: str = "NQ1") -> "SessionBoxEngine":
        """Create engine from live storage parquet.

        Reads only the last 3 days of data — enough for today's session
        boxes + yesterday's prev-day context. The parquet has 1 row group
        so we can't do predicate pushdown, but filtering to ~4300 rows
        makes extract_all_sessions() near-instant.

        Args:
            ticker: Ticker symbol.

        Returns:
            SessionBoxEngine instance with data loaded and processed.

        Raises:
            FileNotFoundError: If live storage parquet doesn't exist.
            ValueError: If data is empty or unreadable.
        """
        live_file = _LIVE_FILES.get(ticker)
        if not live_file:
            raise ValueError(f"No live file mapping for {ticker}")

        live_path = _LIVE_DIR / live_file
        if not live_path.exists():
            raise FileNotFoundError(f"Live storage not found: {live_path}")

        df = pd.read_parquet(live_path)
        df = _to_datetime_index(df)
        if df is None or df.empty:
            raise ValueError(f"Empty live data for {ticker}")

        # Filter to last 3 days only (today + yesterday + 1 buffer day)
        # This is enough for: today's 4 session boxes + prev-day context
        # The extract_all_sessions() groupby is the real bottleneck,
        # and 3 days (~4300 rows) makes it near-instant.
        cutoff = df.index[-1] - pd.Timedelta(days=3)
        df = df[df.index >= cutoff]

        if df.empty:
            raise ValueError(f"No recent data for {ticker}")

        engine = cls(df, ticker=ticker)
        engine.process()
        return engine

    @classmethod
    def from_fused(cls, ticker: str = "NQ1") -> "SessionBoxEngine":
        """Create engine from fused data (historical + live).

        Uses the fused data loader which merges historical parquet
        with live storage. Best for backtesting or when full history
        is needed.

        Args:
            ticker: Ticker symbol.

        Returns:
            SessionBoxEngine instance with data loaded and processed.
        """
        from scripts.utils.fused_data_loader import load_fused_data

        df = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df is None or df.empty:
            raise ValueError(f"No fused data for {ticker}")

        engine = cls(df, ticker=ticker)
        engine.process()
        return engine

    # ── Processing ──────────────────────────────────────────────────────

    def process(self) -> "SessionBoxEngine":
        """Run all computations: boxes → status → broken → prev shifts.

        Returns self for chaining.
        """
        df = self._raw_df.copy()

        # Normalize to US/Eastern
        if df.index.tz is None:
            df.index = pd.DatetimeIndex(df.index).tz_localize("UTC").tz_convert("US/Eastern")
        elif str(df.index.tz) != "US/Eastern":
            df.index = df.index.tz_convert("US/Eastern")

        self.df = df

        # 1. Extract session box ranges
        from scripts.libs_py.nqstats.sessions import extract_all_sessions
        self.boxes = extract_all_sessions(df)

        # 2. Compute box status (LT/LF/ST/SF)
        self.status = compute_box_status(df, self.boxes)

        # 3. Compute broken status (mid reversion)
        self.broken = compute_box_broken(df, self.status)

        # 4. Compute prev-day shifts
        self.prev = compute_prev_day_shifts(self.status)

        self._processed = True
        return self

    # ── Output methods ──────────────────────────────────────────────────

    def get_live_sessions(self) -> Dict[str, Dict[str, object]]:
        """Get latest session box statuses in live_sessions format.

        Returns a dict suitable for compute_profiler()'s live_sessions
        parameter:

            {
                "Asia":   {"status": "Long True", "broken": False},
                "London": {"status": "Short True", "broken": True},
                "NY1":    {"status": "None", "broken": False},
                "NY2":    {"status": "None", "broken": False},
            }
        """
        if not self._processed:
            self.process()
        return get_latest_box_status(self.status, self.broken)

    def get_prev_context(self) -> Dict[str, object]:
        """Get previous-day context for profiler filtering.

        Returns:
            {
                "prev_asia_status": "Short True",
                "prev_london_status": "None",
                "prev_ny1_status": "Short False",
                "prev_ny2_status": "Short True",
                "prev_asia_broken": False,
                "prev_london_broken": False,
                "prev_ny1_broken": True,
                "prev_ny2_broken": False,
            }
        """
        if not self._processed:
            self.process()
        return get_latest_prev_context(self.prev)

    def get_full_context(self) -> Dict[str, object]:
        """Get combined live sessions + prev context.

        Returns a single dict with all context keys needed by
        the profiler filter chain.
        """
        ctx = {}
        ctx.update(self.get_live_sessions())
        ctx.update(self.get_prev_context())
        return ctx

    def get_summary(self) -> str:
        """One-line summary of current box statuses."""
        if not self._processed:
            self.process()

        latest = self.status.iloc[-1]
        parts = []
        for box_prefix in BOX_NAMES:
            session_name = BOX_SESSION_MAP[box_prefix]
            status = latest.get(f"{box_prefix}_status", "?")
            parts.append(f"{session_name}={status}")
        return f"[{self.ticker}] " + " | ".join(parts)


# ── Internal helpers ──────────────────────────────────────────────────────


def _to_datetime_index(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Convert a parquet DataFrame to UTC DatetimeIndex."""
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

        vals = df[time_col]
        if pd.api.types.is_numeric_dtype(vals):
            t_max = vals.dropna().max() if not vals.dropna().empty else 0
            if t_max > 1e16:
                vals = vals // 10**9
            elif t_max > 1e13:
                vals = vals // 10**6
            elif t_max > 1e10:
                vals = vals // 10**3
            df["datetime"] = pd.to_datetime(vals, unit="s", utc=True)
        else:
            df["datetime"] = pd.to_datetime(vals, utc=True, errors="coerce")

        df = df.set_index("datetime")
        df = df.drop(columns=[time_col], errors="ignore")
        return df
    except Exception:
        return None
