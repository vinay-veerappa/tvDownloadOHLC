"""
Session Loader Service - Load pre-computed session data

Provides fast access to pre-computed hourly and daily session data.
Falls back to on-demand calculation if pre-computed data is not available.
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import math

# Path to pre-computed session data
SESSIONS_DIR = Path(__file__).parent.parent.parent / 'data' / 'sessions'


def sanitize_for_json(data):
    """
    Recursively sanitize data to be JSON-serializable.
    Replaces NaN, Inf, -Inf with None.
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    else:
        return data


def load_precomputed_hourly(
    ticker: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None
) -> Optional[List[Dict]]:
    """
    Load pre-computed hourly session data from parquet file.
    
    Returns list of session dicts, or None if not available.
    """
    clean_ticker = ticker.replace('!', '')
    path = SESSIONS_DIR / f'{clean_ticker}_hourly.parquet'
    
    if not path.exists():
        return None
    
    try:
        df = pd.read_parquet(path)
        
        # Apply time filter if specified
        if start_ts is not None and 'startUnix' in df.columns:
            df = df[df['startUnix'] >= start_ts]
        if end_ts is not None and 'startUnix' in df.columns:
            df = df[df['startUnix'] <= end_ts]
        
        if df.empty:
            return []
        
        # Convert to list of dicts
        result = df.to_dict('records')
        return sanitize_for_json(result)
        
    except Exception as e:
        print(f'[SessionLoader] Error loading hourly data for {ticker}: {e}')
        return None


def load_precomputed_daily(
    ticker: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None
) -> Optional[List[Dict]]:
    """
    Load pre-computed daily session data from JSON file.
    
    Returns list of session dicts, or None if not available.
    """
    clean_ticker = ticker.replace('!', '')
    path = SESSIONS_DIR / f'{clean_ticker}_sessions.json'
    
    if not path.exists():
        return None
    
    try:
        with open(path, 'r') as f:
            sessions = json.load(f)
        
        # Apply time filter if specified
        if start_ts or end_ts:
            filtered = []
            for session in sessions:
                # Try to get session start time
                session_start = session.get('start_ts')
                if session_start is None and 'start' in session:
                    try:
                        session_start = pd.Timestamp(session['start']).timestamp()
                    except:
                        pass
                
                if session_start is None:
                    # Can't filter, include it
                    filtered.append(session)
                    continue
                
                if start_ts and session_start < start_ts:
                    continue
                if end_ts and session_start > end_ts:
                    continue
                
                filtered.append(session)
            
            return filtered
        
        return sessions
        
    except Exception as e:
        print(f'[SessionLoader] Error loading daily data for {ticker}: {e}')
        return None


def has_precomputed_hourly(ticker: str) -> bool:
    """Check if pre-computed hourly data exists for ticker."""
    clean_ticker = ticker.replace('!', '')
    path = SESSIONS_DIR / f'{clean_ticker}_hourly.parquet'
    return path.exists()


def has_precomputed_daily(ticker: str) -> bool:
    """Check if pre-computed daily data exists for ticker."""
    clean_ticker = ticker.replace('!', '')
    path = SESSIONS_DIR / f'{clean_ticker}_sessions.json'
    return path.exists()


def get_hourly_sessions(
    ticker: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    fallback_df: Optional[pd.DataFrame] = None
) -> Optional[List[Dict]]:
    """
    Get hourly session data - tries pre-computed first, falls back to calculation.
    
    Args:
        ticker: Ticker symbol
        start_ts: Optional start timestamp filter
        end_ts: Optional end timestamp filter
        fallback_df: Optional DataFrame to use for on-demand calculation
        
    Returns:
        List of session dicts, or None if not available
    """
    # Try pre-computed first
    sessions = load_precomputed_hourly(ticker, start_ts, end_ts)
    if sessions is not None:
        return sessions
    
    # Fall back to on-demand calculation
    if fallback_df is not None:
        from api.services.session_service import SessionService
        
        # Apply time filter if needed
        if start_ts or end_ts:
            if 'time' in fallback_df.columns:
                if start_ts:
                    fallback_df = fallback_df[fallback_df['time'] >= start_ts]
                if end_ts:
                    fallback_df = fallback_df[fallback_df['time'] <= end_ts]
        
        if fallback_df.empty:
            return []
        
        # Ensure proper index
        if not isinstance(fallback_df.index, pd.DatetimeIndex):
            if 'datetime' not in fallback_df.columns and 'time' in fallback_df.columns:
                fallback_df['datetime'] = pd.to_datetime(fallback_df['time'], unit='s', utc=True)
            if 'datetime' in fallback_df.columns:
                fallback_df = fallback_df.set_index('datetime')
                if fallback_df.index.tz is None:
                    fallback_df.index = fallback_df.index.tz_localize('UTC')
                fallback_df.index = fallback_df.index.tz_convert('US/Eastern')
        
        sessions = SessionService.calculate_hourly(fallback_df)
        return sanitize_for_json(sessions)
    
    return None


def get_daily_sessions(
    ticker: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    fallback_df: Optional[pd.DataFrame] = None
) -> Optional[List[Dict]]:
    """
    Get daily session data - tries pre-computed first, falls back to calculation.
    """
    # Try pre-computed first
    sessions = load_precomputed_daily(ticker, start_ts, end_ts)
    if sessions is not None:
        return sessions
    
    # Fall back to on-demand calculation
    if fallback_df is not None:
        from api.services.session_service import SessionService
        
        clean_ticker = ticker.replace('!', '')
        
        # Apply time filter if needed
        if start_ts or end_ts:
            if 'time' in fallback_df.columns:
                if start_ts:
                    fallback_df = fallback_df[fallback_df['time'] >= start_ts]
                if end_ts:
                    fallback_df = fallback_df[fallback_df['time'] <= end_ts]
        
        if fallback_df.empty:
            return []
        
        # Ensure proper index
        if not isinstance(fallback_df.index, pd.DatetimeIndex):
            if 'datetime' not in fallback_df.columns and 'time' in fallback_df.columns:
                fallback_df['datetime'] = pd.to_datetime(fallback_df['time'], unit='s', utc=True)
            if 'datetime' in fallback_df.columns:
                fallback_df = fallback_df.set_index('datetime')
                if fallback_df.index.tz is None:
                    fallback_df.index = fallback_df.index.tz_localize('UTC')
                fallback_df.index = fallback_df.index.tz_convert('US/Eastern')
        
        sessions = SessionService.calculate_sessions(fallback_df, clean_ticker)
        return sanitize_for_json(sessions)
    
    return None
