"""
provider.py
===========
Pluggable Market Data Provider Engine for Equities.
Provides a unified caching and fetching layer that stores daily stock candles
in `data/stocks/<TICKER>_1D.parquet` using standard OHLCV schema [time, open, high, low, close, volume].

Primary provider: yfinance (batch capable)
Fallback provider: schwab (via Schwab Hub proxy / hub_request)
Configurable via environment variable (EQUITY_DATA_PROVIDER) or function parameters.
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

try:
    import yfinance as yf
except ImportError:
    yf = None

log = logging.getLogger("screener_provider")

REPO_ROOT = Path(__file__).resolve().parents[3]
STOCKS_DATA_DIR = REPO_ROOT / "data" / "stocks"


def ensure_stocks_dir() -> Path:
    """Ensures data/stocks/ directory exists."""
    os.makedirs(STOCKS_DATA_DIR, exist_ok=True)
    return STOCKS_DATA_DIR


def get_stock_parquet_path(ticker: str) -> Path:
    """Returns absolute path to data/stocks/<TICKER>_1D.parquet."""
    clean_t = ticker.upper().strip()
    return ensure_stocks_dir() / f"{clean_t}_1D.parquet"


def is_cache_fresh(file_path: Path, max_age_hours: float = 8.0) -> bool:
    """
    Checks if cached Parquet file is fresh.
    Returns True if file exists and was modified within max_age_hours (or today).
    """
    if not file_path.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        now = datetime.now()
        # If created/modified today, cache is fresh
        if mtime.date() == now.date():
            return True
        # If updated within max_age_hours
        age_hours = (now - mtime).total_seconds() / 3600.0
        return age_hours < max_age_hours
    except Exception:
        return False


def load_cached_stock_parquet(ticker: str) -> Optional[pd.DataFrame]:
    """Loads cached stock daily OHLCV Parquet from data/stocks/<TICKER>_1D.parquet."""
    p_path = get_stock_parquet_path(ticker)
    if not p_path.exists():
        return None
    try:
        df = pd.read_parquet(p_path)
        if df.empty or len(df) < 5:
            return None
        return df
    except Exception as e:
        log.warning(f"Failed to read cached Parquet for {ticker}: {e}")
        return None


def save_stock_parquet(ticker: str, df: pd.DataFrame) -> bool:
    """Persists daily OHLCV DataFrame to data/stocks/<TICKER>_1D.parquet."""
    if df is None or df.empty:
        return False
    try:
        p_path = get_stock_parquet_path(ticker)
        save_df = df.copy()
        
        # Reset DatetimeIndex to column if present
        if isinstance(save_df.index, pd.DatetimeIndex):
            save_df = save_df.reset_index()
            if "index" in save_df.columns:
                save_df.rename(columns={"index": "datetime"}, inplace=True)

        save_df.to_parquet(p_path, index=False)
        return True
    except Exception as e:
        log.error(f"Failed to save Parquet for {ticker}: {e}")
        return False


# ------------------------------------------------------------------------------
# Provider Implementation 1: yfinance
# ------------------------------------------------------------------------------
def fetch_yfinance_single(ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
    """Fetches daily history for a single ticker via yfinance."""
    if yf is None:
        return None
    try:
        t_obj = yf.Ticker(ticker)
        df = t_obj.history(period=period, interval="1d", auto_adjust=False)
        if df is None or df.empty:
            return None
        return normalize_ohlcv_df(df, ticker)
    except Exception as e:
        log.warning(f"yfinance single fetch failed for {ticker}: {e}")
        return None


def fetch_yfinance_batch(tickers: List[str], period: str = "2y") -> Dict[str, pd.DataFrame]:
    """Fetches daily history for multiple tickers via yfinance batch download."""
    if yf is None or not tickers:
        return {}
    
    results = {}
    try:
        data = yf.download(tickers, period=period, interval="1d", group_by="ticker", progress=False, threads=True)
        if data is None or data.empty:
            return {}

        if len(tickers) == 1:
            t = tickers[0]
            norm_df = normalize_ohlcv_df(data, t)
            if norm_df is not None and not norm_df.empty:
                results[t] = norm_df
        else:
            for t in tickers:
                try:
                    # Handle MultiIndex columns safely
                    if hasattr(data.columns, 'levels') and t in data.columns.levels[0]:
                        df_t = data[t].dropna()
                        norm_df = normalize_ohlcv_df(df_t, t)
                        if norm_df is not None and not norm_df.empty:
                            results[t] = norm_df
                except Exception:
                    continue
    except Exception as e:
        log.error(f"yfinance batch download error: {e}")
        
    return results


# ------------------------------------------------------------------------------
# Provider Implementation 2: Schwab API / Hub Fallback
# ------------------------------------------------------------------------------
def fetch_schwab_single(ticker: str) -> Optional[pd.DataFrame]:
    """Fallback fetch via Schwab Hub REST proxy."""
    try:
        import asyncio
        from scripts.market_data.fetch_schwab_data import fetch_data
        
        now = datetime.now(timezone.utc)
        start_dt = now - pd.Timedelta(days=730)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        df = loop.run_until_complete(fetch_data(ticker, "1d", start_dt, now))
        loop.close()

        if df is None or df.empty:
            return None
        return normalize_ohlcv_df(df, ticker)
    except Exception as e:
        log.warning(f"Schwab fallback fetch failed for {ticker}: {e}")
        return None


# ------------------------------------------------------------------------------
# DataFrame Normalization Helper
# ------------------------------------------------------------------------------
def normalize_ohlcv_df(df: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """Normalizes raw provider DataFrame into repository standard schema."""
    if df is None or df.empty:
        return None

    res = df.copy()
    if isinstance(res.columns, pd.MultiIndex):
        res.columns = res.columns.get_level_values(0)

    # Standardize column casing
    col_map = {}
    for col in res.columns:
        c_lower = str(col).lower()
        if c_lower in ["open", "high", "low", "close", "volume", "adj close", "date", "datetime"]:
            col_map[col] = c_lower
    res.rename(columns=col_map, inplace=True)

    if "close" not in res.columns:
        return None

    # Handle datetime / time column
    if "date" in res.columns:
        res["datetime"] = pd.to_datetime(res["date"])
    elif "datetime" not in res.columns:
        if isinstance(res.index, pd.DatetimeIndex):
            res["datetime"] = res.index
        else:
            res["datetime"] = pd.to_datetime(res.index, errors="coerce")

    res = res.dropna(subset=["close"])
    if len(res) < 5:
        return None

    # Sort chronological
    if "datetime" in res.columns:
        res = res.sort_values("datetime").reset_index(drop=True)

    # Ensure required columns
    for req in ["open", "high", "low", "volume"]:
        if req not in res.columns:
            res[req] = res["close"]

    if "adj close" in res.columns:
        res["adj_close"] = res["adj close"]

    return res


# ------------------------------------------------------------------------------
# High Level Pluggable Batch Fetcher with Fallback & Local Parquet Cache
# ------------------------------------------------------------------------------
def fetch_equity_daily_batch(
    tickers: List[str],
    provider: str = None,
    fallback: str = "schwab",
    force_refresh: bool = False
) -> Dict[str, pd.DataFrame]:
    """
    Core pluggable equity data fetcher.
    1. Loads fresh daily candles from data/stocks/<TICKER>_1D.parquet if present.
    2. Batch downloads missing/stale tickers via configured primary provider (default: yfinance).
    3. Fails over to fallback provider (default: schwab) for any failed tickers.
    4. Saves up-to-date data to data/stocks/<TICKER>_1D.parquet.
    """
    preferred_provider = provider or os.getenv("EQUITY_DATA_PROVIDER", "yfinance").lower()
    ensure_stocks_dir()

    results: Dict[str, pd.DataFrame] = {}
    needed_tickers: List[str] = []

    # 1. Check local Parquet cache first
    for t in tickers:
        clean_t = t.upper().strip()
        p_path = get_stock_parquet_path(clean_t)
        if not force_refresh and is_cache_fresh(p_path):
            cached_df = load_cached_stock_parquet(clean_t)
            if cached_df is not None and not cached_df.empty:
                results[clean_t] = cached_df
                continue
        needed_tickers.append(clean_t)

    if not needed_tickers:
        log.info(f"Loaded ALL {len(tickers)} tickers directly from local data/stocks/ Parquet cache.")
        return results

    log.info(f"Local cache hit: {len(results)}/{len(tickers)}. Fetching {len(needed_tickers)} tickers via primary provider [{preferred_provider}]...")

    # 2. Fetch via primary provider
    fetched_map: Dict[str, pd.DataFrame] = {}
    if preferred_provider == "yfinance":
        fetched_map = fetch_yfinance_batch(needed_tickers)
    elif preferred_provider == "schwab":
        for t in needed_tickers:
            df_s = fetch_schwab_single(t)
            if df_s is not None:
                fetched_map[t] = df_s

    # 3. Fallback provider check for missing tickers
    missing_after_primary = [t for t in needed_tickers if t not in fetched_map or fetched_map[t].empty]
    if missing_after_primary and fallback:
        log.warning(f"Primary provider missed {len(missing_after_primary)} tickers. Triggering fallback [{fallback}]...")
        for t in missing_after_primary:
            if fallback == "schwab":
                df_fallback = fetch_schwab_single(t)
            elif fallback == "yfinance":
                df_fallback = fetch_yfinance_single(t)
            else:
                df_fallback = None

            if df_fallback is not None and not df_fallback.empty:
                fetched_map[t] = df_fallback

    # 4. Save and merge results
    for t, df in fetched_map.items():
        if df is not None and not df.empty:
            existing = load_cached_stock_parquet(t) if not force_refresh else None
            if existing is not None and not existing.empty:
                combined = pd.concat([existing, df], ignore_index=True)
                if "datetime" in combined.columns:
                    combined = combined.drop_duplicates(subset=["datetime"], keep="last").sort_values("datetime").reset_index(drop=True)
                else:
                    combined = combined.drop_duplicates().reset_index(drop=True)
                final_df = combined
            else:
                final_df = df

            save_stock_parquet(t, final_df)
            results[t] = final_df

    # Fallback to older disk cache if network fetch completely failed
    for t in needed_tickers:
        if t not in results:
            old_df = load_cached_stock_parquet(t)
            if old_df is not None:
                log.info(f"Using existing (older) cache for {t} after provider failure.")
                results[t] = old_df

    log.info(f"Total active equity feature dataframes ready: {len(results)}/{len(tickers)}.")
    return results
