from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
from api.services.data_loader import load_parquet
from api.services.session_service import SessionService

router = APIRouter()

@router.get("/{ticker}")
async def get_sessions(
    ticker: str, 
    range_type: str = Query("opening", description="Type of range: opening, custom"),
    start_time: str = Query("09:30", description="Start time (HH:MM)"),
    duration: int = Query(1, description="Duration in minutes (for opening range)")
):
    """
    Get session ranges for a ticker.
    Checks pre-calculated cache first for 'all' range type.
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
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load cached sessions: {e}")
                # Fallback to live calc

    # Load 1m data for precision
    df = load_parquet(ticker, "1m")
    
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

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
    else:
        sessions = [] 
        
    return sessions
