"""
Data loader service - reads Parquet files from the data directory
"""

import os
import pandas as pd
from pathlib import Path
from typing import Optional


# Path to data directory - relative to project root
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_parquet(ticker: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Load OHLCV data from Parquet file
    
    Args:
        ticker: e.g., "ES1", "NQ1"
        timeframe: e.g., "5m", "1h", "1D"
    
    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
    filename = f"{ticker}_{timeframe}.parquet"
    filepath = DATA_DIR / filename
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return None
    
    df = pd.read_parquet(filepath)
    
    # Handle datetime index - reset to column and convert to Unix timestamp
    if df.index.name in ['datetime', 'time', 'timestamp']:
        df = df.reset_index()
    
    # Rename datetime column to time if needed
    if 'datetime' in df.columns:
        df = df.rename(columns={'datetime': 'time'})
    elif 'timestamp' in df.columns:
        df = df.rename(columns={'timestamp': 'time'})
    
    # Convert datetime to Unix timestamp (seconds) if needed
    if 'time' in df.columns and pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = df['time'].astype('int64') // 10**9
    
    # Ensure expected columns exist
    expected_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    for col in expected_cols:
        if col not in df.columns:
            print(f"Missing column: {col}")
            return None
    
    # Sort by time
    df = df.sort_values('time').reset_index(drop=True)
    
    return df


def get_available_data() -> list:
    """List all available ticker/timeframe combinations"""
    if not DATA_DIR.exists():
        return []
    
    files = []
    for f in DATA_DIR.glob("*.parquet"):
        parts = f.stem.split("_")
        if len(parts) >= 2:
            ticker = parts[0]
            timeframe = "_".join(parts[1:])
            files.append({"ticker": ticker, "timeframe": timeframe})
    
    return files
