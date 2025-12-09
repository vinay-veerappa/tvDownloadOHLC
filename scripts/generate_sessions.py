import sys
import os
import json
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from api.services.data_loader import load_parquet
from api.services.session_service import SessionService

DATA_DIR = Path(__file__).parent.parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

def generate_sessions(ticker):
    print(f"Processing {ticker}...")
    
    # Load data
    df = load_parquet(ticker, "1m")
    if df is None:
        print(f"Error: Could not load data for {ticker}")
        return

    # Prepare DataFrame (similar to sessions.py)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
    
    # Calculate Sessions
    print(f"  Calculating sessions (this may take a while for large files)...")
    sessions = SessionService.calculate_sessions(df, ticker)
    
    # Calculate Opening Ranges (separate pass or included?)
    # sessions.py currently calls calculate_opening_range OR calculate_sessions based on param.
    # DailyProfiler requests 'range_type=all' which calls calculate_sessions.
    # calculate_sessions ALREADY includes 'OpeningRange' (see line 103 of session_service.py).
    # So 'sessions' list is complete for DailyProfiler.

    # Save
    output_file = SESSIONS_DIR / f"{ticker}_sessions.json"
    with open(output_file, 'w') as f:
        json.dump(sessions, f)
    
    print(f"  Saved {len(sessions)} sessions to {output_file}")

if __name__ == "__main__":
    SESSIONS_DIR.mkdir(exist_ok=True)
    
    # Auto-discover all 1m parquet files
    parquet_files = list(DATA_DIR.glob("*_1m.parquet"))
    
    print(f"Found {len(parquet_files)} tickers with 1m data.")
    
    for p_file in parquet_files:
        # Filename format: TICKER_1m.parquet
        # e.g. ES1_1m.parquet -> ES1
        # e.g. NQ1_1m.parquet -> NQ1
        try:
            parts = p_file.stem.split('_')
            ticker = parts[0]
            
            # Check if session file already exists to avoid re-running if desired?
            # User might want to force update. Let's just run it.
            # But maybe skip if very recent?
            # For now, just run all.
            
            generate_sessions(ticker)
        except Exception as e:
            print(f"Skipping {p_file.name}: {e}")
