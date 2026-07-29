"""
Unified Data Loader for Edgeful Platform

Loads 1m/5m/daily OHLCV and VIX data with automatic historical + live fusion.
Handles timezone conversion to ET (America/New_York) per ADR-001.

All data is returned as naive datetime indices in ET timezone.
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Constants
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
LIVE_DIR = DATA_DIR / "live"

# Symbol mapping for live storage filenames: ES1 -> -ES, NQ1 -> -NQ, etc.
LIVE_TICKER_MAP = {
    "ES1": "-ES",
    "NQ1": "-NQ",
    "RTY1": "-RTY",
    "YM1": "-YM",
    "CL1": "-CL",
    "GC1": "-GC",
}


class DataLoader:
    """
    Unified data loader with intelligent caching and live data fusion.
    
    Loads from `data/{symbol}_{timeframe}.parquet` and fuses with
    `data/live/live_storage_{live_symbol}.parquet` for 1m data.
    
    All returned DataFrames have:
      - Index: datetime (naive, America/New_York timezone)
      - Columns: ['open', 'high', 'low', 'close', 'volume']
    """
    
    def __init__(self, data_root: Path = None):
        self.data_root = data_root or DATA_DIR
        self._cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    
    def load_1m(self, symbol: str, start_date=None, end_date=None) -> pd.DataFrame:
        """
        Load 1-minute OHLCV, fused with live storage.
        
        Args:
            symbol: Ticker (e.g., 'NQ1', 'ES1', 'AAPL', 'QQQ')
            start_date: Optional filter (date or str 'YYYY-MM-DD')
            end_date: Optional filter
        
        Returns:
            DataFrame with index=datetime(ET), cols=[open, high, low, close, volume]
        """
        return self._load_parquet(symbol, "1m", start_date, end_date)
    
    def load_5m(self, symbol: str, start_date=None, end_date=None) -> pd.DataFrame:
        """Load 5-minute OHLCV."""
        return self._load_parquet(symbol, "5m", start_date, end_date)
    
    def load_daily(self, symbol: str, start_date=None, end_date=None) -> pd.DataFrame:
        """Load daily OHLCV."""
        return self._load_parquet(symbol, "1d", start_date, end_date)
    
    def load_vix(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Load VIX daily close."""
        return self._load_parquet("VIX", "1d", start_date, end_date)
    
    def _load_parquet(
        self, symbol: str, timeframe: str, start_date=None, end_date=None
    ) -> pd.DataFrame:
        """
        Internal: Load and fuse parquet files.
        
        For 1m data: Fuses historical + live_storage, deduplicates by time.
        For HTF: Loads historical only.
        """
        cache_key = (symbol, timeframe)
        if cache_key in self._cache:
            df = self._cache[cache_key]
        else:
            df = self._fuse_data(symbol, timeframe)
            self._cache[cache_key] = df
        
        if df.empty:
            return df
        
        # Filter by date if specified
        if start_date or end_date:
            if start_date:
                df = df[df.index >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df.index < pd.to_datetime(end_date) + pd.Timedelta(days=1)]
        
        return df
    
    def _fuse_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load and fuse historical + live parquet for 1m, or just historical for HTF."""
        dfs = []
        
        # 1. Load historical parquet
        hist_path = self.data_root / f"{symbol}_{timeframe}.parquet"
        if hist_path.exists():
            try:
                df_hist = self._read_and_normalize(hist_path, symbol, timeframe)
                dfs.append(df_hist)
                logger.debug(f"Loaded historical {symbol} {timeframe}: {len(df_hist)} rows")
            except Exception as e:
                logger.warning(f"Failed to load {hist_path}: {e}")
        
        # 2. For 1m, also load and fuse live storage
        if timeframe == "1m" and self._get_live_path(symbol).exists():
            try:
                df_live = self._read_and_normalize(self._get_live_path(symbol), symbol, timeframe, is_live=True)
                dfs.append(df_live)
                logger.debug(f"Loaded live {symbol} 1m: {len(df_live)} rows")
            except Exception as e:
                logger.warning(f"Failed to load live storage for {symbol}: {e}")
        
        if not dfs:
            logger.warning(f"No data found for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # 3. Fuse: concatenate and deduplicate on index
        combined = pd.concat(dfs)
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
        
        return combined
    
    def _read_and_normalize(
        self, path: Path, symbol: str, timeframe: str, is_live: bool = False
    ) -> pd.DataFrame:
        """
        Read parquet and normalize to standard schema.
        
        Handles:
        - Variable timestamp formats (Unix s, ms, datetime)
        - Variable column names (datetime, time, timestamp)
        - Timezone conversion to ET
        """
        df = pd.read_parquet(path)
        
        if df.empty:
            return df
        
        # 1. Identify and normalize time column
        # Prefer an existing DatetimeIndex over a numeric 'time' column.
        # NQ1_1m.parquet has a DatetimeIndex (ET-naive) AND a 'time' column
        # (epoch seconds storing ET-naive-as-UTC). Using the 'time' column
        # would shift bars by -5h (UTC->ET conversion on already-ET data).
        # The index is the correct timestamp source.
        time_col = None
        if isinstance(df.index, pd.DatetimeIndex) and df.index.name:
            # Use the index directly — it's already a proper datetime
            time_col = df.index.name
            df = df.reset_index()
        else:
            for candidate in ['datetime', 'timestamp', 'time']:
                if candidate in df.columns:
                    time_col = candidate
                    break

        if time_col is None and isinstance(df.index, pd.DatetimeIndex):
            time_col = df.index.name or 'datetime'
            df = df.reset_index()
        
        if time_col is None:
            raise ValueError(f"No datetime/time column found in {path}")
        
        # 2. Convert time to datetime if needed
        if pd.api.types.is_numeric_dtype(df[time_col]):
            # Detect units: estimate from max value (all UTC)
            # Unix seconds: ~1.7e9 (April 2026), ~2.5e9 by 2050
            # Unix milliseconds: ~1.7e12 (April 2026), ~2.5e12 by 2050
            max_val = df[time_col].max()
            try:
                if 1e9 < max_val < 2e10:  # Likely seconds (2001-2603)
                    df[time_col] = pd.to_datetime(df[time_col], unit='s', utc=True)
                elif 1e12 < max_val < 2e12:  # Likely milliseconds (2001-2603)
                    df[time_col] = pd.to_datetime(df[time_col], unit='ms', utc=True)
                else:
                    raise ValueError(f"Unrecognized time scale in {path}: max={max_val}")
            except Exception as e:
                raise ValueError(f"Failed to parse timestamps in {path}: {e}")
        elif pd.api.types.is_datetime64tz_dtype(df[time_col]):
            # Already tz-aware datetime — convert to UTC for normalization
            df[time_col] = df[time_col].dt.tz_convert('UTC')
        elif pd.api.types.is_datetime64_any_dtype(df[time_col]):
            # Tz-naive datetime — could be ET-naive (from NQ1_1m.parquet index)
            # or UTC-naive (from live_storage 'timestamp' column).
            # live_storage timestamps are UTC; historical index is ET-naive.
            if is_live:
                # live_storage 'timestamp' column is UTC-naive
                df[time_col] = df[time_col].dt.tz_localize('UTC')
            # else: ET-naive from historical DatetimeIndex — keep as-is
        else:
            df[time_col] = pd.to_datetime(df[time_col], utc=True)
        
        # 3. Timezone conversion: UTC -> ET (naive)
        if df[time_col].dt.tz is not None:
            df[time_col] = df[time_col].dt.tz_convert('America/New_York').dt.tz_localize(None)
        
        # 4. Set index and standardize columns
        df = df.set_index(time_col)
        df.index.name = 'datetime'
        
        # Lowercase and filter to expected columns
        df.columns = [c.lower() for c in df.columns]
        expected = ['open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in expected if c in df.columns]]
        
        # Ensure all expected columns exist
        for col in expected:
            if col not in df.columns:
                df[col] = 0.0 if col != 'volume' else 0
        
        df = df[expected].sort_index()
        
        return df
    
    def _get_live_path(self, symbol: str) -> Path:
        """Map symbol to live storage filename."""
        live_symbol = LIVE_TICKER_MAP.get(symbol, symbol)
        return LIVE_DIR / f"live_storage_{live_symbol}.parquet"


# Convenience singleton
_loader = None

def get_loader(data_root: Path = None) -> DataLoader:
    """Get or create the global DataLoader instance."""
    global _loader
    if _loader is None:
        _loader = DataLoader(data_root)
    return _loader
