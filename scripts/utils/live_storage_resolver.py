"""Live Storage Parquet Path Resolver & Bar Loader.

Maps canonical futures & equity tickers to live storage parquet files in data/live/.
Anchors all paths to REPO_ROOT.
Includes mtime-aware in-memory caching for sub-millisecond repeated queries.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

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
        # Standardize timestamp column
        ts_col = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else "datetime")
        if ts_col in df.columns:
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
