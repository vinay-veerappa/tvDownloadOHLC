"""
Pre-compute Session Data for Hourly and Daily Profilers

This script generates pre-computed session data:
- Hourly (1H + 3H aggregations)
- Daily (Session ranges: Asia, London, NY, etc.)

Output: Parquet files in data/sessions/ directory

Usage:
    python scripts/precompute_sessions.py
    python scripts/precompute_sessions.py --ticker ES1
"""

import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.data_loader import load_parquet, get_available_data
from api.services.session_service import SessionService

# Output directories
SESSIONS_DIR = PROJECT_ROOT.parent / 'data' / 'sessions'
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def precompute_hourly_sessions(ticker: str, timeframe: str = '1m') -> bool:
    """
    Pre-compute hourly (1H + 3H) session data for a ticker.
    Saves as parquet file for fast loading.
    """
    print(f"  [Hourly] Loading {ticker} {timeframe}...")
    
    df = load_parquet(ticker, timeframe)
    if df is None or df.empty:
        print(f"  [Hourly] No data found for {ticker}")
        return False
    
    # Prepare DataFrame for SessionService
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
    else:
        print(f"  [Hourly] Missing time column for {ticker}")
        return False
    
    print(f"  [Hourly] Computing hourly sessions ({len(df):,} rows)...")
    
    try:
        sessions = SessionService.calculate_hourly(df)
    except Exception as e:
        print(f"  [Hourly] Error computing sessions: {e}")
        return False
    
    if not sessions:
        print(f"  [Hourly] No sessions computed for {ticker}")
        return False
    
    # Convert to DataFrame
    sessions_df = pd.DataFrame(sessions)
    
    # Add computed unix timestamps if not present
    if 'startUnix' not in sessions_df.columns:
        sessions_df['startUnix'] = pd.to_datetime(sessions_df['start_time']).astype(int) // 10**9
    if 'endUnix' not in sessions_df.columns:
        sessions_df['endUnix'] = pd.to_datetime(sessions_df['end_time']).astype(int) // 10**9
    
    # Save as parquet
    output_path = SESSIONS_DIR / f'{ticker}_hourly.parquet'
    
    # Add metadata
    metadata = {
        b'ticker': ticker.encode(),
        b'type': b'hourly',
        b'computed_at': datetime.now().isoformat().encode(),
        b'source_rows': str(len(df)).encode(),
        b'session_count': str(len(sessions_df)).encode()
    }
    
    table = pa.Table.from_pandas(sessions_df)
    table = table.replace_schema_metadata({**table.schema.metadata, **metadata})
    pq.write_table(table, output_path, compression='snappy')
    
    print(f"  [Hourly] Saved {len(sessions_df):,} sessions to {output_path.name}")
    return True


def precompute_daily_sessions(ticker: str, timeframe: str = '1m') -> bool:
    """
    Pre-compute daily session data (Asia, London, NY, etc.) for a ticker.
    Saves as JSON file for fast loading (existing format).
    """
    print(f"  [Daily] Loading {ticker} {timeframe}...")
    
    df = load_parquet(ticker, timeframe)
    if df is None or df.empty:
        print(f"  [Daily] No data found for {ticker}")
        return False
    
    # Prepare DataFrame for SessionService
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
        df.index = df.index.tz_convert('US/Eastern')
    else:
        print(f"  [Daily] Missing time column for {ticker}")
        return False
    
    print(f"  [Daily] Computing daily sessions ({len(df):,} rows)...")
    
    try:
        sessions = SessionService.calculate_sessions(df, ticker)
    except Exception as e:
        print(f"  [Daily] Error computing sessions: {e}")
        return False
    
    if not sessions:
        print(f"  [Daily] No sessions computed for {ticker}")
        return False
    
    # Sanitize NaN values for JSON
    def sanitize(data):
        if isinstance(data, dict):
            return {k: sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [sanitize(item) for item in data]
        elif isinstance(data, float):
            import math
            if math.isnan(data) or math.isinf(data):
                return None
            return data
        else:
            return data
    
    sessions = sanitize(sessions)
    
    # Save as JSON (existing format expected by API)
    output_path = SESSIONS_DIR / f'{ticker}_sessions.json'
    with open(output_path, 'w') as f:
        json.dump(sessions, f)
    
    print(f"  [Daily] Saved {len(sessions):,} sessions to {output_path.name}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Pre-compute session data')
    parser.add_argument('--ticker', type=str, help='Specific ticker to compute')
    parser.add_argument('--type', type=str, choices=['hourly', 'daily', 'all'], 
                       default='all', help='Type of sessions to compute')
    args = parser.parse_args()
    
    # Get available tickers
    available = get_available_data()
    
    # Filter to 1m timeframe only
    tickers_1m = set()
    for item in available:
        if item.get('timeframe') == '1m':
            ticker = item.get('ticker', '').replace('!', '')
            if ticker:
                tickers_1m.add(ticker)
    
    if args.ticker:
        ticker = args.ticker.replace('!', '')
        if ticker not in tickers_1m:
            print(f"Ticker {ticker} not found in available 1m data")
            return
        tickers_1m = {ticker}
    
    print(f"Pre-computing sessions for {len(tickers_1m)} tickers...")
    print(f"Output directory: {SESSIONS_DIR}")
    print()
    
    hourly_success = 0
    daily_success = 0
    
    for ticker in sorted(tickers_1m):
        print(f"Processing {ticker}...")
        
        if args.type in ['hourly', 'all']:
            if precompute_hourly_sessions(ticker):
                hourly_success += 1
        
        if args.type in ['daily', 'all']:
            if precompute_daily_sessions(ticker):
                daily_success += 1
        
        print()
    
    print("=" * 50)
    print(f"Completed: {hourly_success} hourly, {daily_success} daily")


if __name__ == '__main__':
    main()
