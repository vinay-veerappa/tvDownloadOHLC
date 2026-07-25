"""
Data loading and merging — high-performance version.

Performance principles:
  - Parallel I/O: price + all internals loaded concurrently via ThreadPoolExecutor
  - pyarrow engine:  fastest parquet reader, releases GIL during I/O
  - Column pruning:  only OHLCV loaded initially; internals load only 'close'
  - Single concat + one dedup pass — no redundant copies
  - Zero Python loops in hot paths

Usage:
    from scripts.libs_py.data.loader import DataLoader
    from scripts.trading_framework.config.config_loader import load_config

    config = load_config()
    loader = DataLoader(config)
    df = loader.load_enriched("NQ1")
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.trading_framework.config.config_loader import AppConfig

logger = logging.getLogger(__name__)

# Max threads for parallel I/O — parquet reads are I/O-bound; GIL is released
_IO_WORKERS = 8

# Symbol alias: generic names → on-disk parquet prefix
_SYMBOL_ALIAS: dict[str, str] = {
    "MES": "ES1",
    "MNQ": "NQ1",
    "ES":  "ES1",
    "NQ":  "NQ1",
}

# OHLCV columns required in the loaded DataFrame
_PRICE_COLS = {"open", "high", "low", "close", "volume"}
# Timestamp candidate column names (added to every read so _normalise_index works)
_TS_CANDIDATES = ["datetime", "time", "timestamp", "date"]


@dataclass
class DataLoader:
    """
    Loads and merges price + internals parquet files into a single enriched DataFrame.

    All I/O is done in parallel via ThreadPoolExecutor.
    Features are not computed here — that is the FeatureRegistry's job.
    """
    config: AppConfig
    _cache: dict = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_price(self, symbol: str) -> pd.DataFrame:
        """
        Load and validate a single price parquet (parallel-safe, cached).

        Returns a tz-aware US/Eastern DatetimeIndex DataFrame with
        columns: open, high, low, close, volume.
        """
        canon = self._canonicalize(symbol)
        cache_key = f"price:{canon}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Always include timestamp columns so _normalise_index can detect them
        all_cols = list(_PRICE_COLS) + _TS_CANDIDATES
        df = self._read_parquet_fast(self._price_path(canon), columns=all_cols)
        df = self._normalise_index(df)
        df = df.loc[self.config.date_start : self.config.date_end]
        self._validate_price(df, canon)

        if df.empty:
            raise ValueError(f"[{canon}] No data in date range "
                             f"{self.config.date_start} – {self.config.date_end}")

        self._cache[cache_key] = df
        logger.info("Loaded %d bars for %s (%s → %s)", len(df), canon,
                    df.index[0], df.index[-1])
        return df

    def load_internals(self) -> dict[str, pd.DataFrame]:
        """
        Load all internals symbols in parallel.

        Returns dict keyed by symbol name, each with a single column
        named after the symbol.  Missing files are silently skipped.
        """
        cache_key = "internals"
        if cache_key in self._cache:
            return self._cache[cache_key]

        symbols = self.config.symbols_internals
        result: dict[str, pd.DataFrame] = {}

        def _load_one(sym: str) -> tuple[str, Optional[pd.DataFrame]]:
            path = self._price_path(sym)
            if not path.exists():
                logger.warning("Internals parquet missing — skipping: %s", path)
                return sym, None
            try:
                # Include timestamp candidates to avoid losing datetime index
                # when parquet column pruning is applied.
                df = self._read_parquet_fast(path, columns=["close", *_TS_CANDIDATES])
                df = self._normalise_index(df)
                df = df.rename(columns={"close": sym})
                # Keep only the signal column; drop helper timestamp columns
                # to prevent collisions when concatenating many internals.
                return sym, df[[sym]]
            except Exception as e:
                logger.warning("Failed to load internals %s: %s", sym, e)
                return sym, None

        with ThreadPoolExecutor(max_workers=min(_IO_WORKERS, len(symbols) or 1)) as ex:
            futures = {ex.submit(_load_one, sym): sym for sym in symbols}
            for fut in as_completed(futures):
                sym, df = fut.result()
                if df is not None:
                    result[sym] = df

        self._cache[cache_key] = result
        return result

    def compute_vold(self, uvol: pd.DataFrame, dvol: pd.DataFrame) -> pd.Series:
        """UVOL − DVOL as a Series named 'VOLD'."""
        s = uvol.iloc[:, 0] - dvol.iloc[:, 0]
        s.name = "VOLD"
        return s

    def merge_all(self, price_symbol: str) -> pd.DataFrame:
        """
        Load price + internals in parallel, then left-join onto price timeline.

        Steps:
          1. Kick off price load and internals load concurrently
          2. Left-join internals onto price index (single vectorised join)
          3. Add VOLD column
          4. Forward-fill internals (fills ETH/gap bars)
        """
        # Launch price + internals concurrently
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_price     = ex.submit(self.load_price, price_symbol)
            fut_internals = ex.submit(self.load_internals)
            df        = fut_price.result()
            internals = fut_internals.result()

        if internals:
            # One vectorised join — O(n) merge
            internals_df = pd.concat(internals.values(), axis=1)
            df = df.join(internals_df, how="left")

            # VOLD
            if "UVOL" in internals and "DVOL" in internals:
                df["VOLD"] = self.compute_vold(internals["UVOL"], internals["DVOL"])

            # Forward-fill ETH gaps (vectorised ffill)
            internal_cols = list(internals.keys()) + (["VOLD"] if "VOLD" in df.columns else [])
            df[internal_cols] = df[internal_cols].ffill()
        else:
            logger.warning("No internals loaded — price-only DataFrame")

        return df

    def load_enriched(self, symbol: str) -> pd.DataFrame:
        """
        Full enrichment pipeline (seconds, not minutes):
          1. merge_all()              — parallel price + internals I/O
          2. tag_sessions()           — vectorised session tagging
          3. add_resampled_columns()  — merge_asof 5m bars onto 1m
          4. add_vix_context()        — merge_asof daily VIX/VVIX

        Returns a fully enriched DataFrame ready for FeatureRegistry.
        """
        from scripts.libs_py.data.session_tagger import tag_sessions
        from scripts.libs_py.data.resampler import add_resampled_columns

        df = self.merge_all(symbol)
        df = tag_sessions(df, self.config.sessions)
        df = add_resampled_columns(df, freq="5min", prefix="5m_")

        # 4. Add VIX/VVIX Daily Context
        # Load daily data (naive/UTC usually)
        vix_path = self.config.data_dir.parent / "VIX_1d.parquet"
        vvix_path = self.config.data_dir.parent / "VVIX_1d.parquet"

        if vix_path.exists():
            vix_df = pd.read_parquet(vix_path)
            vix_df.index = pd.to_datetime(vix_df.index).tz_localize(None)
            vix_df = vix_df.rename(columns={"close": "vix_daily"})
            
            # VVIX
            if vvix_path.exists():
                vvix_df = pd.read_parquet(vvix_path)
                vvix_df.index = pd.to_datetime(vvix_df.index).tz_localize(None)
                vix_df["vvix_level"] = vvix_df["close"]

            # Compute Regimes for easy grouping
            def get_regime(val, buckets):
                if pd.isna(val): return "Unknown"
                for low, high, label in buckets:
                    if low <= val < high: return label
                return "Extreme"

            vix_df["vix_regime"] = vix_df["vix_daily"].apply(lambda x: get_regime(x, [(0, 13, "Low"), (13, 20, "Normal"), (20, 30, "Elevated"), (30, 200, "High")]))

            # Pre-sort for merge_asof
            vix_df = vix_df.sort_index()

            # Create naive signal index for the merge
            df_naive = df.index.tz_localize(None)

            # Normalize VIX index to ns dtype to match price data (parquet may use us)
            # VIX is tz-naive; cast to ns resolution to match df_naive
            if vix_df.index.dtype != df_naive.dtype:
                vix_df.index = vix_df.index.astype(df_naive.dtype)
            
            # Using join logic would be 1-to-1 if we had a date column, 
            # but merge_asof is safer for aligning daily levels to intraday timestamps.
            df = df.sort_index()
            # We add a temp col for the merge
            df["_ts_naive"] = df_naive
            
            df = pd.merge_asof(
                df,
                vix_df[["vix_daily", "vix_regime"] + (["vvix_level"] if "vvix_level" in vix_df.columns else [])],
                left_on="_ts_naive",
                right_index=True,
                direction="backward"
            )
            df = df.drop(columns=["_ts_naive"])

        logger.info("Enriched: %d bars, %d columns, symbol=%s", len(df), len(df.columns), symbol)
        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _canonicalize(self, symbol: str) -> str:
        return _SYMBOL_ALIAS.get(symbol.upper(), symbol.upper())

    def _price_path(self, symbol: str) -> Path:
        """
        Resolve the parquet path for a symbol.

        Falls back to the parent of config.data_dir when the configured
        directory does not exist (handles data/ vs data/parquet/ mismatch).
        """
        configured = self.config.data_dir / f"{symbol}_1m.parquet"
        if configured.parent.exists():
            return configured
        # Fallback: try the parent directory
        fallback = self.config.data_dir.parent / f"{symbol}_1m.parquet"
        if fallback.parent.exists():
            logger.debug("data_dir '%s' not found — using fallback '%s'",
                         self.config.data_dir, fallback.parent)
            return fallback
        return configured  # return original so error message is informative

    @staticmethod
    def _read_parquet_fast(
        path: Path,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Read parquet using pyarrow directly (fastest engine, GIL-releasing).
        Prunes to requested columns that actually exist in the schema,
        silently skipping any that don't (avoids ArrowInvalid errors).
        """
        pf = pq.ParquetFile(str(path))
        schema_cols = {f.name for f in pf.schema_arrow}
        if columns is not None:
            columns = [c for c in columns if c in schema_cols]
        table = pf.read(columns=columns)
        return table.to_pandas()

    @staticmethod
    def _normalise_index(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure a tz-aware US/Eastern DatetimeIndex.
        Handles: already Eastern, UTC, naive (assumed UTC), and column-based timestamps.
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            for col in ("datetime", "time", "timestamp", "date"):
                if col in df.columns:
                    df = df.set_index(col)
                    break
            df.index = pd.to_datetime(df.index)

        idx = df.index
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        if str(idx.tz) not in ("US/Eastern", "America/New_York"):
            idx = idx.tz_convert("US/Eastern")
        df.index = idx
        df.index.name = "datetime"
        return df

    @staticmethod
    def _validate_price(df: pd.DataFrame, symbol: str) -> None:
        """Fast validation — only checks what can go wrong silently."""
        if df.index.duplicated().any():
            n = df.index.duplicated().sum()
            raise ValueError(f"[{symbol}] {n} duplicate index entries")
        missing = _PRICE_COLS - set(df.columns)
        if missing:
            raise ValueError(f"[{symbol}] Missing columns: {missing}")