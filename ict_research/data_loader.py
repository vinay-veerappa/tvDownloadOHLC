import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import os
from config import TZ_NY, TZ_UTC, DATA_DIR

def load_data(ticker: str, timeframe: str = '1m', data_dir: str = None) -> pd.DataFrame:
    """
    Load data from parquet file.
    Args:
        ticker: Symbol name (e.g., 'NQ')
        timeframe: '1m' or '1d'
        data_dir: Directory containing the parquet files
    """
    if data_dir is None:
        # Check local data dir first, then parent data dir
        if os.path.exists(os.path.join(os.path.dirname(__file__), 'data')):
             data_dir = os.path.join(os.path.dirname(__file__), 'data')
        elif os.path.exists(DATA_DIR):
             data_dir = DATA_DIR
        else:
             # Fallback to the known absolute path from user context
             data_dir = r'c:\Users\vinay\tvDownloadOHLC\data'
    
    # Handle ticker mapping (e.g., NQ -> NQ1) if file doesn't exist
    filename = f"{ticker}_{timeframe}.parquet"
    filepath = os.path.join(data_dir, filename)
    
    if not os.path.exists(filepath):
        # Try finding {ticker}1 if {ticker} requested
        filepath_alt = os.path.join(data_dir, f"{ticker}1_{timeframe}.parquet")
        if os.path.exists(filepath_alt):
            filepath = filepath_alt
    
    if not os.path.exists(filepath):
        # Final fallback to absolute path
        fallback_path = os.path.join(r'c:\Users\vinay\tvDownloadOHLC\data', f"{ticker}_{timeframe}.parquet")
        fallback_path1 = os.path.join(r'c:\Users\vinay\tvDownloadOHLC\data', f"{ticker}1_{timeframe}.parquet")
        
        if os.path.exists(fallback_path):
            filepath = fallback_path
        elif os.path.exists(fallback_path1):
            filepath = fallback_path1
        else:
            raise FileNotFoundError(f"Data file not found for {ticker} in {data_dir}")
        
    df = pd.read_parquet(filepath)
    
    # Process timestamps - data usually has 'time' in seconds
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    elif 'date' in df.columns: # Sometimes 1d data has 'date'
        df['datetime'] = pd.to_datetime(df['date'])
        if df['datetime'].dt.tz is None:
            df['datetime'] = df['datetime'].dt.tz_localize(TZ_UTC) # Assume UTC if naive
    
    # Set index to datetime
    if 'datetime' in df.columns:
        df = df.set_index('datetime')
        
    # Convert to NY time
    df = df.tz_convert(TZ_NY)
    
    return df

def slice_trading_days(df: pd.DataFrame):
    """
    Slice the dataframe into trading days.
    trading_date = index date + 1 day if hour >= 18, else index date
    
    Returns: DataFrame with 'trading_date' column
    """
    # Shift by 6 hours so that 18:00 (prev day) becomes 00:00 (curr day)
    shifted_index = df.index + timedelta(hours=6)
    df['trading_date'] = shifted_index.date
    
    return df

def get_trading_day_data(df: pd.DataFrame, trading_date):
    """
    Get all rows for a specific trading date.
    """
    return df[df['trading_date'] == trading_date]
