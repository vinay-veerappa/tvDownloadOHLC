from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
import math
from api.services.data_loader import load_parquet
from api.services.session_service import SessionService
from api.services.session_loader import (
    load_precomputed_hourly, 
    load_precomputed_daily,
    has_precomputed_hourly,
    has_precomputed_daily,
    sanitize_for_json
)

router = APIRouter()


def filter_sessions_by_time(sessions: list, start_ts: Optional[int], end_ts: Optional[int]) -> list:
    """
    Filter session data by time range.
    Sessions must have 'startUnix' or 'start_time' field.
    """
    if not start_ts and not end_ts:
        return sessions
    
    filtered = []
    for session in sessions:
        # Get session start time (try startUnix first, then parse start_time)
        session_start = session.get('startUnix')
        if session_start is None and 'start_time' in session:
            try:
                session_start = pd.Timestamp(session['start_time']).timestamp()
            except:
                session_start = None
        
        if session_start is None:
            continue
            
        # Apply time filter
        if start_ts and session_start < start_ts:
            continue
        if end_ts and session_start > end_ts:
            continue
        
        filtered.append(session)
    
    return filtered


@router.get("/{ticker}")
async def get_sessions(
    ticker: str, 
    range_type: str = Query("opening", description="Type of range: opening, custom, hourly"),
    start_time: str = Query("09:30", description="Start time (HH:MM)"),
    duration: int = Query(1, description="Duration in minutes (for opening range)"),
    start_ts: Optional[int] = Query(None, description="Start timestamp (unix seconds) for time filtering"),
    end_ts: Optional[int] = Query(None, description="End timestamp (unix seconds) for time filtering")
):
    """
    Get session ranges for a ticker.
    
    Uses pre-computed data when available (~10ms), falls back to on-demand calculation (~2-9s).
    
    Time filtering: Use start_ts/end_ts to limit results to a time range.
    """
    clean_ticker = ticker.replace("!", "")
    
    # =========================================================================
    # HOURLY: Try pre-computed first
    # =========================================================================
    if range_type == "hourly":
        if has_precomputed_hourly(ticker):
            sessions = load_precomputed_hourly(ticker, start_ts, end_ts)
            if sessions is not None:
                return sessions
        
        # Fall back to on-demand calculation
        df = load_parquet(ticker, "1m")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        # Apply time filter to source data
        if start_ts:
            df = df[df['time'] >= start_ts]
        if end_ts:
            df = df[df['time'] <= end_ts]
        
        if df.empty:
            return []
        
        # Prepare DataFrame for Service
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
        
        sessions = SessionService.calculate_hourly(df)
        return sanitize_for_json(sessions)
    
    # =========================================================================
    # DAILY (ALL): Try pre-computed first
    # =========================================================================
    if range_type == "all":
        if has_precomputed_daily(ticker):
            sessions = load_precomputed_daily(ticker, start_ts, end_ts)
            if sessions is not None:
                return sessions
        
        # Fall back to on-demand calculation
        df = load_parquet(ticker, "1m")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        # Apply time filter to source data
        if start_ts:
            df = df[df['time'] >= start_ts]
        if end_ts:
            df = df[df['time'] <= end_ts]
        
        if df.empty:
            return []
        
        # Prepare DataFrame for Service
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
        
        sessions = SessionService.calculate_sessions(df, clean_ticker)
        return sanitize_for_json(sessions)
    
    # =========================================================================
    # OPENING RANGE: Always calculate on-demand (small dataset)
    # =========================================================================
    if range_type == "opening":
        df = load_parquet(ticker, "1m")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        # Apply time filter
        if start_ts:
            df = df[df['time'] >= start_ts]
        if end_ts:
            df = df[df['time'] <= end_ts]
        
        if df.empty:
            return []
        
        # Prepare DataFrame
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
        
        sessions = SessionService.calculate_opening_range(df, start_time, duration)
        return sanitize_for_json(sessions)
    
    return []



