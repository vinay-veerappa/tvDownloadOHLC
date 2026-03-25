"""
VWAP Loader Service - Load pre-computed VWAP or calculate on-demand
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, List, Optional, Any

from api.services.vwap import calculate_vwap_with_settings
from api.services.data_loader import load_parquet


# Path to pre-computed indicator data
INDICATORS_DIR = Path(__file__).parent.parent.parent / 'data' / 'indicators'

# Futures tickers (use 18:00 anchor)
FUTURES_PREFIXES = ['ES', 'NQ', 'YM', 'RTY', 'GC', 'CL', 'MES', 'MNQ']


def is_futures(ticker: str) -> bool:
    """Check if ticker is a futures contract"""
    t = ticker.upper().replace('!', '')
    return any(t.startswith(prefix) for prefix in FUTURES_PREFIXES)


def get_default_settings(ticker: str) -> Dict[str, Any]:
    """Get default VWAP settings for a ticker"""
    if is_futures(ticker):
        return {
            'anchor': 'session',
            'anchor_time': '18:00',
            'anchor_timezone': 'America/New_York',
            'bands': [1.0, 2.0, 3.0],
            'source': 'hlc3'
        }
    else:
        return {
            'anchor': 'session',
            'anchor_time': '09:30',
            'anchor_timezone': 'America/New_York',
            'bands': [1.0, 2.0, 3.0],
            'source': 'hlc3'
        }


def is_default_settings(ticker: str, settings: Dict[str, Any]) -> bool:
    """Check if provided settings match defaults for this ticker"""
    defaults = get_default_settings(ticker)
    
    # Key settings that must match
    if settings.get('anchor', 'session') != defaults['anchor']:
        return False
    if settings.get('anchor_time', defaults['anchor_time']) != defaults['anchor_time']:
        return False
    if settings.get('source', 'hlc3') != defaults['source']:
        return False
    
    # Bands can be a subset of pre-computed bands
    requested_bands = settings.get('bands', [1.0])
    if not all(b in defaults['bands'] for b in requested_bands):
        return False
    
    return True


def get_precomputed_path(ticker: str, timeframe: str) -> Path:
    """Get path to pre-computed VWAP file"""
    clean_ticker = ticker.replace('!', '')
    return INDICATORS_DIR / f'{clean_ticker}_{timeframe}_vwap.parquet'


def load_precomputed_vwap(
    ticker: str,
    timeframe: str,
    settings: Dict[str, Any],
    start_time: Optional[int] = None,
    end_time: Optional[int] = None
) -> Optional[Dict[str, List]]:
    """
    Load pre-computed VWAP from parquet file.
    Returns None if pre-computed data is not available or settings don't match.
    """
    path = get_precomputed_path(ticker, timeframe)
    
    if not path.exists():
        return None
    
    if not is_default_settings(ticker, settings):
        return None
    
    try:
        # Read parquet file
        df = pd.read_parquet(path)
        
        # Apply time filter if specified
        if start_time is not None:
            df = df[df['time'] >= start_time]
        if end_time is not None:
            df = df[df['time'] <= end_time]
        
        if df.empty:
            return None
        
        # Build result dict matching calculate_vwap_with_settings format
        result = {
            'vwap': df['vwap'].tolist()
        }
        
        # Add bands based on requested settings
        requested_bands = settings.get('bands', [1.0])
        
        band_map = {
            1.0: ('upper_1', 'lower_1'),
            2.0: ('upper_2', 'lower_2'),
            3.0: ('upper_3', 'lower_3'),
        }
        
        for band in requested_bands:
            if band in band_map:
                upper_col, lower_col = band_map[band]
                mult_str = str(band).replace('.', '_')
                
                if upper_col in df.columns:
                    result[f'vwap_upper_{mult_str}'] = df[upper_col].tolist()
                if lower_col in df.columns:
                    result[f'vwap_lower_{mult_str}'] = df[lower_col].tolist()
        
        return result, df['time'].tolist()
        
    except Exception as e:
        print(f'[VWAP Loader] Error loading {path}: {e}')
        return None


def get_vwap(
    ticker: str,
    timeframe: str,
    settings: Dict[str, Any],
    start_time: Optional[int] = None,
    end_time: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Get VWAP data - tries pre-computed first, falls back to on-demand calculation.
    
    Returns dict with 'time' and 'indicators' keys.
    """
    # Try pre-computed data first
    precomputed = load_precomputed_vwap(ticker, timeframe, settings, start_time, end_time)
    
    if precomputed is not None:
        indicators, time_series = precomputed
        return {
            'time': time_series,
            'indicators': indicators,
            'source': 'precomputed'
        }
    
    # Fall back to on-demand calculation
    df = load_parquet(ticker, timeframe)
    if df is None or df.empty:
        return None
    
    # Apply time filter
    if start_time is not None:
        df = df[df['time'] >= start_time]
    if end_time is not None:
        df = df[df['time'] <= end_time]
    
    if df.empty:
        return None
    
    # Calculate on-demand
    result = calculate_vwap_with_settings(
        df,
        anchor=settings.get('anchor', 'session'),
        anchor_time=settings.get('anchor_time', get_default_settings(ticker)['anchor_time']),
        anchor_timezone=settings.get('anchor_timezone', 'America/New_York'),
        bands=settings.get('bands', [1.0]),
        source=settings.get('source', 'hlc3')
    )
    
    return {
        'time': df['time'].tolist(),
        'indicators': result,
        'source': 'calculated'
    }
