"""Live Storage Parquet Path Resolver & Bar Loader.

Maps canonical futures & equity tickers to live storage parquet files in data/live/.
Anchors all paths to REPO_ROOT.
Includes mtime-aware in-memory caching for sub-millisecond repeated queries.
"""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DATA_DIR = REPO_ROOT / "data" / "live"

TICKER_MAP: Dict[str, str] = {
    # Futures aliases
    "NQ": "live_storage_-NQ.parquet",
    "NQ1": "live_storage_-NQ.parquet",
    "-NQ": "live_storage_-NQ.parquet",
    "MNQ": "live_storage_-NQ.parquet",
    "MNQ1": "live_storage_-NQ.parquet",
    "ES": "live_storage_-ES.parquet",
    "ES1": "live_storage_-ES.parquet",
    "-ES": "live_storage_-ES.parquet",
    "MES": "live_storage_-ES.parquet",
    "MES1": "live_storage_-ES.parquet",
    "YM": "live_storage_-YM.parquet",
    "YM1": "live_storage_-YM.parquet",
    "-YM": "live_storage_-YM.parquet",
    "MYM": "live_storage_-YM.parquet",
    "RTY": "live_storage_-RTY.parquet",
    "RTY1": "live_storage_-RTY.parquet",
    "-RTY": "live_storage_-RTY.parquet",
    "M2K": "live_storage_-RTY.parquet",
    "GC": "live_storage_-GC.parquet",
    "GC1": "live_storage_-GC.parquet",
    "-GC": "live_storage_-GC.parquet",
    "MGC": "live_storage_-GC.parquet",
    "CL": "live_storage_-CL.parquet",
    "CL1": "live_storage_-CL.parquet",
    "-CL": "live_storage_-CL.parquet",
    "MCL": "live_storage_-CL.parquet",
    # Equities / ETFs
    "AAPL": "live_storage_AAPL.parquet",
    "NVDA": "live_storage_NVDA.parquet",
    "MSFT": "live_storage_MSFT.parquet",
    "AMZN": "live_storage_AMZN.parquet",
    "GOOGL": "live_storage_GOOGL.parquet",
    "META": "live_storage_META.parquet",
    "TSLA": "live_storage_TSLA.parquet",
    "SPY": "live_storage_SPY.parquet",
    "QQQ": "live_storage_QQQ.parquet",
    "SPX": "live_storage_SPX.parquet",
    "VIX": "live_storage_VIX.parquet",
    "VVIX": "live_storage_VVIX.parquet"
}

# Cache structure: path_str -> (mtime, df)
_DF_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}


def get_live_storage_path(ticker: str, custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the absolute path to the live storage parquet file for a ticker."""
    target_dir = Path(custom_dir) if custom_dir else LIVE_DATA_DIR
    if not target_dir.is_absolute():
        target_dir = REPO_ROOT / target_dir
        
    normalized = ticker.upper().strip()
    filename = TICKER_MAP.get(normalized, f"live_storage_{normalized}.parquet")
    return target_dir / filename


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Deterministic SHA-256 hash of a DataFrame's sorted byte representation."""
    # Sort by the canonical dt column; hash the stable CSV bytes.
    cols = [c for c in ["dt", "open", "high", "low", "close", "volume"] if c in df.columns]
    sorted_df = df[cols].sort_values("dt").reset_index(drop=True)
    payload = sorted_df.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]}"


def load_session_bars(
    ticker: str,
    session_date: str,
    custom_dir: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """Loads 1-minute OHLCV bars for a ticker on a specific session date with mtime-aware caching."""
    parquet_path = get_live_storage_path(ticker, custom_dir=custom_dir)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Live storage parquet file not found for ticker '{ticker}' at: {parquet_path}")
        
    path_key = str(parquet_path.resolve())
    current_mtime = parquet_path.stat().st_mtime
    
    if path_key in _DF_CACHE and _DF_CACHE[path_key][0] == current_mtime:
        df = _DF_CACHE[path_key][1]
    else:
        df = pd.read_parquet(parquet_path)
        # Standardize timestamp column. Prefer explicit columns in priority order;
        # fall back to an existing pre-normalized 'dt' column; final fallback = index.
        # (Never silently coerce a RangeIndex: that fabricates 1970 timestamps.)
        if "dt" in df.columns and pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], utc=True)
        else:
            ts_col = ("timestamp" if "timestamp" in df.columns
                      else "time" if "time" in df.columns
                      else "datetime" if "datetime" in df.columns
                      else None)
            if ts_col is not None:
                df["dt"] = pd.to_datetime(df[ts_col], utc=True)
            else:
                df["dt"] = pd.to_datetime(df.index, utc=True)
            
        df = df.sort_values("dt").reset_index(drop=True)
        df["dt_et"] = df["dt"].dt.tz_convert("America/New_York")
        df["session_date_str"] = df["dt_et"].dt.strftime("%Y-%m-%d")
        _DF_CACHE[path_key] = (current_mtime, df)
        
    session_str = session_date.split("T")[0]
    session_df = df[df["session_date_str"] == session_str].copy()
    
    return session_df


def load_session_bars_as_of_cutoff(
    ticker: str,
    session_date: str,
    cutoff_utc: pd.Timestamp,
    custom_dir: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """Loads session bars up to and including a UTC cutoff timestamp."""
    df = load_session_bars(ticker, session_date, custom_dir=custom_dir)
    if df.empty:
        return df
    return df[df["dt"] <= cutoff_utc].copy()


def load_futures_session_bars(
    ticker: str,
    session_date: str,
    custom_dir: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """Loads bars for the LOGICAL futures session (prior-evening 18:00 ET open .. 17:00 ET close).

    load_session_bars filters by ET calendar date, which drops the prior-evening Globex
    leg of the session - exactly the window where the overnight profile (P12) lives.
    Consumers that compute on the full logical session must use this, so a sealed
    manifest includes every input the analysis actually consumed.

    The prior-evening leg belongs to the PREVIOUS ET calendar date, so the underlying
    parquet rows are filtered by UTC timestamp window, not by session_date_str.
    """
    from scripts.utils.market_calendar import get_futures_session_bounds
    start_utc, end_utc = get_futures_session_bounds(session_date)
    parquet_path = get_live_storage_path(ticker, custom_dir=custom_dir)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Live storage parquet file not found for ticker '{ticker}' at: {parquet_path}")

    path_key = str(parquet_path.resolve())
    current_mtime = parquet_path.stat().st_mtime
    if path_key in _DF_CACHE and _DF_CACHE[path_key][0] == current_mtime:
        df = _DF_CACHE[path_key][1]
    else:
        # Reuse the standardization path: load via load_session_bars on a nearby date
        # only to prime the cache would double-read; instead read directly and normalize
        # with the same contract as load_session_bars.
        df = pd.read_parquet(parquet_path)
        if "dt" in df.columns and pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], utc=True)
        else:
            ts_col = ("timestamp" if "timestamp" in df.columns
                      else "time" if "time" in df.columns
                      else "datetime" if "datetime" in df.columns
                      else None)
            if ts_col is not None:
                df["dt"] = pd.to_datetime(df[ts_col], utc=True)
            else:
                df["dt"] = pd.to_datetime(df.index, utc=True)
        df = df.sort_values("dt").reset_index(drop=True)
        df["dt_et"] = df["dt"].dt.tz_convert("America/New_York")
        df["session_date_str"] = df["dt_et"].dt.strftime("%Y-%m-%d")
        _DF_CACHE[path_key] = (current_mtime, df)

    start_ts = pd.Timestamp(start_utc)
    end_ts = pd.Timestamp(end_utc)
    if start_ts.tz is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts.tz is None:
        end_ts = end_ts.tz_localize("UTC")
    return df[(df["dt"] >= start_ts) & (df["dt"] <= end_ts)].copy()


def load_session_bars_as_of_cutoff_for_logical_session(
    ticker: str,
    session_date: str,
    cutoff_utc: pd.Timestamp,
    custom_dir: Optional[Union[str, Path]] = None
) -> pd.DataFrame:
    """Logical-session bars up to and including a UTC cutoff (full prior-evening leg included)."""
    df = load_futures_session_bars(ticker, session_date, custom_dir=custom_dir)
    if df.empty:
        return df
    return df[df["dt"] <= cutoff_utc].copy()


def get_session_slice_manifest(
    ticker: str,
    session_date: str,
    cutoff_utc: pd.Timestamp,
    custom_dir: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """Sealed manifest for the LOGICAL futures session slice as-of cutoff (prior-evening leg included)."""
    slice_df = load_session_bars_as_of_cutoff_for_logical_session(ticker, session_date, cutoff_utc, custom_dir=custom_dir)
    if slice_df.empty:
        raise ValueError(
            f"No live storage bars for {ticker} on {session_date} as of {cutoff_utc}. "
            f"Cannot seal an empty input manifest."
        )
    max_ts = slice_df["dt"].max()
    return {
        "provider_name": "LIVE_STORAGE_1M",
        "data_type": "BARS_1M",
        "max_timestamp_utc": max_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_hash": _hash_dataframe(slice_df),
        "row_count": int(len(slice_df)),
    }
