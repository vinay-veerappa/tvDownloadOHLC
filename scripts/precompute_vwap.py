"""
Pre-compute VWAP for all tickers and store as parquet files.
Run this script whenever the source data is updated.

Usage:
    python -m scripts.precompute_vwap
"""

import os
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.data_loader import load_parquet, get_available_data
from api.services.vwap import calculate_vwap_with_settings


# Default settings for pre-computation (covers 90%+ of use cases)
DEFAULT_SETTINGS = {
    'futures': {
        'anchor': 'session',
        'anchor_time': '18:00',
        'anchor_timezone': 'America/New_York',
        'bands': [1.0, 2.0, 3.0],
        'source': 'hlc3'
    },
    'stocks': {
        'anchor': 'session', 
        'anchor_time': '09:30',
        'anchor_timezone': 'America/New_York',
        'bands': [1.0, 2.0, 3.0],
        'source': 'hlc3'
    }
}

# Futures tickers (use 18:00 anchor)
FUTURES_PREFIXES = ['ES', 'NQ', 'YM', 'RTY', 'GC', 'CL', 'MES', 'MNQ']


def is_futures(ticker: str) -> bool:
    """Check if ticker is a futures contract"""
    t = ticker.upper().replace('!', '')
    return any(t.startswith(prefix) for prefix in FUTURES_PREFIXES)


def get_output_path(ticker: str, timeframe: str) -> Path:
    """Get output path for pre-computed VWAP"""
    data_dir = Path(__file__).parent.parent / 'data' / 'indicators'
    data_dir.mkdir(parents=True, exist_ok=True)
    clean_ticker = ticker.replace('!', '')
    return data_dir / f'{clean_ticker}_{timeframe}_vwap.parquet'


def precompute_vwap(ticker: str, timeframe: str) -> bool:
    """Pre-compute VWAP for a single ticker/timeframe combination"""
    print(f'  Processing {ticker} {timeframe}...', end=' ')
    
    try:
        # Load source data
        df = load_parquet(ticker, timeframe)
        if df is None or df.empty:
            print('SKIP (no data)')
            return False
        
        # Get appropriate settings
        settings = DEFAULT_SETTINGS['futures'] if is_futures(ticker) else DEFAULT_SETTINGS['stocks']
        
        # Calculate VWAP
        start = time.time()
        result = calculate_vwap_with_settings(
            df,
            anchor=settings['anchor'],
            anchor_time=settings['anchor_time'],
            anchor_timezone=settings['anchor_timezone'],
            bands=settings['bands'],
            source=settings['source']
        )
        elapsed = (time.time() - start) * 1000
        
        # Convert to DataFrame for storage
        vwap_df = pd.DataFrame({
            'time': df['time'].values,
            'vwap': result['vwap'],
            'upper_1': result.get('vwap_upper_1_0', [None] * len(df)),
            'lower_1': result.get('vwap_lower_1_0', [None] * len(df)),
            'upper_2': result.get('vwap_upper_2_0', [None] * len(df)),
            'lower_2': result.get('vwap_lower_2_0', [None] * len(df)),
            'upper_3': result.get('vwap_upper_3_0', [None] * len(df)),
            'lower_3': result.get('vwap_lower_3_0', [None] * len(df)),
        })
        
        # Store metadata
        metadata = {
            'ticker': ticker,
            'timeframe': timeframe,
            'anchor': settings['anchor'],
            'anchor_time': settings['anchor_time'],
            'anchor_timezone': settings['anchor_timezone'],
            'bands': ','.join(str(b) for b in settings['bands']),
            'source': settings['source'],
            'rows': str(len(df)),
            'computed_at': pd.Timestamp.now().isoformat()
        }
        
        # Save as parquet with metadata
        output_path = get_output_path(ticker, timeframe)
        table = pa.Table.from_pandas(vwap_df)
        table = table.replace_schema_metadata({
            **metadata,
            **(table.schema.metadata or {})
        })
        pq.write_table(table, output_path, compression='snappy')
        
        print(f'OK ({len(df):,} rows, {elapsed:.0f}ms, {output_path.stat().st_size/1024:.0f}KB)')
        return True
        
    except Exception as e:
        print(f'ERROR: {e}')
        return False


def main():
    """Pre-compute VWAP for all available tickers"""
    print('=' * 60)
    print('Pre-computing VWAP for all tickers')
    print('=' * 60)
    
    # Get available data (returns list of {ticker, timeframe} dicts)
    available = get_available_data()
    
    # Only process 1m timeframe (most common for VWAP)
    target_timeframes = ['1m']
    
    # Group by ticker
    ticker_timeframes = {}
    for item in available:
        ticker = item['ticker']
        tf = item['timeframe']
        if ticker not in ticker_timeframes:
            ticker_timeframes[ticker] = []
        ticker_timeframes[ticker].append(tf)
    
    success_count = 0
    fail_count = 0
    
    for ticker, timeframes in ticker_timeframes.items():
        print(f'\n{ticker}:')
        for tf in target_timeframes:
            if tf in timeframes:
                if precompute_vwap(ticker, tf):
                    success_count += 1
                else:
                    fail_count += 1
    
    print('\n' + '=' * 60)
    print(f'Complete: {success_count} success, {fail_count} failed')
    print('=' * 60)


if __name__ == '__main__':
    main()
