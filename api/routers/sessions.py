from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
import math
from api.services.data_loader import load_parquet
from api.services.session_service import SessionService

router = APIRouter()


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
    Checks pre-calculated cache first for 'all' range type.
    
    Time filtering: Use start_ts/end_ts to limit results to a time range.
    """
    # 1. OPTIMIZATION: Check for pre-calculated session file
    if range_type == "all":
        # Data loader has cleaning logic "ES1!"->"ES1"
        clean_ticker = ticker.replace("!", "")
        
        # Hardcoded path logic (should match generate_sessions.py)
        # Assuming DATA_DIR is imported
        from api.services.data_loader import DATA_DIR
        session_file = DATA_DIR / "sessions" / f"{clean_ticker}_sessions.json"
        
        if session_file.exists():
            import json
            try:
                with open(session_file, 'r') as f:
                    print(f"Returning cached sessions for {ticker}")
                    data = json.load(f)
                    return filter_sessions_by_time(data, start_ts, end_ts)
            except Exception as e:
                print(f"Failed to load cached sessions: {e}")
                # Fallback to live calc

    # Load 1m data for precision
    df = load_parquet(ticker, "1m")
    
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

    # Apply time filter to source data if provided (optimization)
    if start_ts or end_ts:
        if start_ts:
            df = df[df['time'] >= start_ts]
        if end_ts:
            df = df[df['time'] <= end_ts]
        
        if df.empty:
            return []

    # Prepare DataFrame for Service (Needs DatetimeIndex)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
    else:
        raise HTTPException(status_code=500, detail="Data format error: missing time column")

    if range_type == "opening":
        # Specific Opening Range (09:30)
        sessions = SessionService.calculate_opening_range(df, start_time, duration)
    elif range_type == "all":
        # Return all configured sessions (Asia, London, NY, Midnight)
        clean_ticker = ticker.replace("!", "")
        sessions = SessionService.calculate_sessions(df, clean_ticker)
    elif range_type == "hourly":
        # Return hourly profiler data (1H + 3H)
        sessions = SessionService.calculate_hourly(df)
    else:
        sessions = [] 
    
    # Sanitize NaN/Inf values for JSON serialization
    return sanitize_for_json(sessions)


