"""
ProfilerData - Loads and indexes the pre-computed profiler JSON.

The JSON is a flat list of session records:
  [{ date, session, status, broken, high_time, low_time, high_pct, low_pct, ... }, ...]

Key design:
  - Indexed by (date, session) for O(1) lookup
  - Trading dates are sorted so previous-day lookups are fast
  - No API dependency - reads directly from data/
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import date as Date, datetime

# Default data directory (project root / data)
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"

# Canonical session order within a trading day
SESSION_ORDER = ["Asia", "London", "NY1", "NY2"]
# Full status strings
STATUS_LONG_TRUE  = "Long True"
STATUS_LONG_FALSE = "Long False"
STATUS_SHORT_TRUE = "Short True"
STATUS_SHORT_FALSE= "Short False"
ALL_STATUSES = [STATUS_LONG_TRUE, STATUS_LONG_FALSE, STATUS_SHORT_TRUE, STATUS_SHORT_FALSE]


class ProfilerData:
    """
    Holds all session records for a ticker, indexed for fast lookup.
    
    Attributes:
        ticker:        e.g. "NQ1"
        sessions:      flat list of all session dicts (raw from JSON)
        by_date:       { date_str -> { session_name -> session_dict } }
        trading_dates: sorted list of trading date strings (e.g. ["2024-01-02", ...])
    """

    def __init__(self, ticker: str, sessions: List[dict]):
        self.ticker = ticker
        self.sessions = sessions
        self.by_date: Dict[str, Dict[str, dict]] = {}
        self.trading_dates: List[str] = []
        self._index()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, ticker: str, data_dir: Path = None) -> "ProfilerData":
        """Load profiler JSON for a ticker. Raises FileNotFoundError if missing."""
        data_dir = data_dir or _DATA_DIR
        path = data_dir / f"{ticker}_profiler.json"
        if not path.exists():
            raise FileNotFoundError(f"Profiler JSON not found: {path}")
        with open(path, "r") as f:
            sessions = json.load(f)
        if not isinstance(sessions, list):
            # Legacy format: { "sessions": [...] }
            sessions = sessions.get("sessions", [])
        return cls(ticker, sessions)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def _index(self):
        """Build by_date index and sorted trading_dates list."""
        for s in self.sessions:
            d = s.get("date")
            sess = s.get("session")
            if not d or not sess:
                continue
            if d not in self.by_date:
                self.by_date[d] = {}
            self.by_date[d][sess] = s
        self.trading_dates = sorted(self.by_date.keys())

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def get_session(self, date_str: str, session: str) -> Optional[dict]:
        """Get a specific session record by trading date and session name."""
        return self.by_date.get(date_str, {}).get(session)

    def get_prev_trading_date(self, date_str: str) -> Optional[str]:
        """Return the previous trading date (skips weekends/holidays automatically)."""
        try:
            idx = self.trading_dates.index(date_str)
            return self.trading_dates[idx - 1] if idx > 0 else None
        except ValueError:
            return None

    def get_trading_day_context(self, date_str: str) -> dict:
        """
        For a given trading date, return the full context dict needed for filtering.
        
        Returns:
            {
              # Previous day's session statuses and broken states
              "prev_ny1_status":  str | None,
              "prev_ny2_status":  str | None,
              "prev_asia_status": str | None,
              "prev_lon_status":  str | None,
              "prev_ny1_broken":  bool,
              "prev_ny2_broken":  bool,
              # Current day's in-progress sessions (for intra-state filtering)
              "asia_status":   str | None,
              "lon_status":    str | None,
              "ny1_status":    str | None,
              "ny2_status":    str | None,
            }
        """
        prev_date = self.get_prev_trading_date(date_str)
        prev_day = self.by_date.get(prev_date, {}) if prev_date else {}
        today = self.by_date.get(date_str, {})

        def status(sess_dict: Optional[dict]) -> Optional[str]:
            return sess_dict.get("status") if sess_dict else None

        def broken(sess_dict: Optional[dict]) -> bool:
            return bool(sess_dict.get("broken")) if sess_dict else False

        return {
            # Previous day
            "prev_ny1_status":  status(prev_day.get("NY1")),
            "prev_ny2_status":  status(prev_day.get("NY2")),
            "prev_asia_status": status(prev_day.get("Asia")),
            "prev_lon_status":  status(prev_day.get("London")),
            "prev_ny1_broken":  broken(prev_day.get("NY1")),
            "prev_ny2_broken":  broken(prev_day.get("NY2")),
            # Current day (may be None if session hasn't completed)
            "asia_status":  status(today.get("Asia")),
            "lon_status":   status(today.get("London")),
            "ny1_status":   status(today.get("NY1")),
            "ny2_status":   status(today.get("NY2")),
        }

    # ------------------------------------------------------------------
    # Generation (from Parquet)
    # ------------------------------------------------------------------
    @classmethod
    def from_parquet(cls, ticker: str, days: int = 10000) -> "ProfilerData":
        """
        Dynamically calculate sessions from Parquet and return a ProfilerData instance.
        """
        from api.features.shared.data_loader import load_parquet
        df = load_parquet(ticker, "1m")
        if df is None or df.empty:
            raise ValueError(f"No data available for {ticker}")

        from scripts.libs.nqstats.engine import NQStatsEngine
        import pandas as pd
        # Fast Loading: Use 5-day buffer if 'days' is small
        # Note: NQStatsEngine needs context for p12 and shift. 
        # But we only need to process the tail for speed.
        if days < 2000: # If requesting a subset
            # We load everything but then slice for engine
             pass # slicing below

        # Robust DatetimeIndex conversion
        if not isinstance(df.index, pd.DatetimeIndex):
             if 'time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
                 df = df.set_index('datetime')
             elif 'datetime' in df.columns:
                 df = df.set_index('datetime')
        
        # Localize to ET as engine expects
        if df.index.tz is None:
             df = df.tz_localize('UTC').tz_convert('US/Eastern')
        elif str(df.index.tz) != 'US/Eastern':
             df = df.tz_convert('US/Eastern')

        # Slice for efficiency (requested days + buffer for context)
        if days < 10000:
             cutoff = df.index[-1] - pd.Timedelta(days=days + 30)
             df = df.loc[cutoff:]
        
        # Run engine
        engine = NQStatsEngine(df, ticker=ticker)
        engine.process()
        
        sessions = cls.generate_sessions(engine)
        return cls(ticker, sessions)

    @staticmethod
    def generate_sessions(engine) -> List[dict]:
        """
        Converts NQStatsEngine results into a list of session records for JSON storage.
        """
        import numpy as np
        import pandas as pd
        from datetime import datetime
        
        stats = engine.stats
        sessions_df = engine.sessions # Contains high, low, open, close per bar
        
        # We need ONE record per (trading_date, session)
        trading_dates = sessions_df.index.date
        session_names = ["AsiaBox", "LondonBox", "NY1Box", "NY2Box"]
        final_records = []
        
        # Status expander (short to long)
        expand = {"LT": "Long True", "LF": "Long False", "ST": "Short True", "SF": "Short False"}
        
        # Map Box names to canonical names
        name_map = {"AsiaBox": "Asia", "LondonBox": "London", "NY1Box": "NY1", "NY2Box": "NY2"}

        for box in session_names:
            prefix = box.lower()
            canonical = name_map[box]
            
            # Find the bars where this session is active
            active_mask = sessions_df[f"{prefix}_active"] == 1
            if not active_mask.any(): continue
            
            # Group by trading date
            group_keys = trading_dates[active_mask]
            
            # Extract metrics per day
            subset = stats.loc[active_mask]
            group_metrics = subset.groupby(group_keys).agg({
                f'{prefix}_open': 'first',
                f'{prefix}_high': 'max',
                f'{prefix}_low': 'min',
                f'{prefix}_close': 'last',
                f'{prefix}_status': 'last',
                f'{prefix}_broken': 'last',
                f'{prefix}_mid': 'first',
                'p12': 'first'
            })
            
            # High/Low times are a bit more involved (idxmax per day)
            # Optimization: since we already have the active mask and groups, we can do it efficiently
            h_idx = sessions_df.loc[active_mask, f'{prefix}_high'].groupby(group_keys).idxmax()
            l_idx = sessions_df.loc[active_mask, f'{prefix}_low'].groupby(group_keys).idxmin()
            
            for date, row in group_metrics.iterrows():
                date_str = date.strftime('%Y-%m-%d')
                
                # Check status and expand
                raw_status = row.get(f'{prefix}_status')
                status = expand.get(raw_status, "None")
                if status == "None": continue # Skip sessions that didn't resolve (e.g. today's future sessions)

                # Times
                h_ts = h_idx[date]
                l_ts = l_idx[date]
                
                # Full timestamps for JSON (ISO format)
                # Note: engine.stats index is already localized to ET
                start_ts_dt = subset.loc[subset.index.date == date].index[0]
                end_ts_dt = subset.loc[subset.index.date == date].index[-1]

                sess_open = float(row[f'{prefix}_open'])
                high = float(row[f'{prefix}_high'])
                low = float(row[f'{prefix}_low'])
                
                record = {
                    "date": date_str,
                    "session": canonical,
                    "open": sess_open,
                    "prior_close": float(row['p12']),
                    "range_high": high,
                    "range_low": low,
                    "mid": float(row[f'{prefix}_mid']),
                    "high_time": h_ts.strftime('%H:%M'),
                    "low_time": l_ts.strftime('%H:%M'),
                    "high_pct": round(((high - sess_open) / sess_open) * 100, 2) if sess_open > 0 else 0,
                    "low_pct": round(((low - sess_open) / sess_open) * 100, 2) if sess_open > 0 else 0,
                    "close_pct": round(((float(row[f'{prefix}_close']) - sess_open) / sess_open) * 100, 2) if sess_open > 0 else 0,
                    "status": status,
                    "broken": bool(row[f'{prefix}_broken']),
                    "start_time": start_ts_dt.isoformat(),
                    "start_ts": int(start_ts_dt.timestamp()),
                    "end_time": end_ts_dt.isoformat(),
                    "end_ts": int(end_ts_dt.timestamp()),
                    "high_ts": int(h_ts.timestamp()),
                    "low_ts": int(l_ts.timestamp())
                }
                final_records.append(record)
                
        # Sort by start_ts
        final_records.sort(key=lambda x: x['start_ts'])
        return final_records
