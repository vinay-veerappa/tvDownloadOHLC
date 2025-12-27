"""
Precompute 9:30 Opening Range for each ticker.

Generates a JSON file with the 9:30 AM (NY time) 1-minute candle for each trading day.
This data is used as input for opening range breakout strategies.

Output: data/{ticker}_opening_range.json
"""

import pandas as pd
import json
import pytz
from datetime import datetime, time
from pathlib import Path
import sys

# Data directory
DATA_DIR = Path("data")
NY_TZ = pytz.timezone("America/New_York")

def load_1m_data(ticker: str) -> pd.DataFrame:
    """Load 1-minute parquet data for a ticker."""
    parquet_path = DATA_DIR / f"{ticker}_1m.parquet"
    
    if not parquet_path.exists():
        raise FileNotFoundError(f"Data file not found: {parquet_path}")
    
    df = pd.read_parquet(parquet_path)
    
    # Ensure time column is datetime
    if 'time' in df.columns:
        if df['time'].dtype == 'int64':
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['datetime'] = df['time']
    
    # Convert to NY timezone
    if df['datetime'].dt.tz is None:
        df['datetime'] = df['datetime'].dt.tz_localize('UTC')
    df['datetime'] = df['datetime'].dt.tz_convert(NY_TZ)
    
    return df

def extract_opening_range(df: pd.DataFrame) -> list:
    """
    Extract the 9:30 1-minute candle for each trading day.
    
    Returns list of records with:
    - date: YYYY-MM-DD
    - open, high, low, close: OHLC of 9:30 candle
    - range_pts: high - low (points)
    - range_pct: (high - low) / open * 100 (percentage)
    - timestamp: Unix timestamp of 9:30 bar
    """
    # Add date column
    df['date'] = df['datetime'].dt.date
    df['hour'] = df['datetime'].dt.hour
    df['minute'] = df['datetime'].dt.minute
    
    # Filter for 9:30 candles only
    opening_bars = df[(df['hour'] == 9) & (df['minute'] == 30)].copy()
    
    if opening_bars.empty:
        print("Warning: No 9:30 bars found!")
        return []
    
    records = []
    for _, row in opening_bars.iterrows():
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        range_pts = h - l
        range_pct = (range_pts / o * 100) if o > 0 else 0
        
        records.append({
            'date': str(row['date']),
            'open': round(o, 2),
            'high': round(h, 2),
            'low': round(l, 2),
            'close': round(c, 2),
            'range_pts': round(range_pts, 2),
            'range_pct': round(range_pct, 4),
            'timestamp': int(row['datetime'].timestamp())
        })
    
    # Sort by date
    records.sort(key=lambda x: x['date'])
    
    return records

def precompute_opening_range(ticker: str):
    """Generate opening range JSON for a ticker."""
    print(f"Processing {ticker}...")
    
    try:
        df = load_1m_data(ticker)
        print(f"  Loaded {len(df):,} bars")
        
        records = extract_opening_range(df)
        print(f"  Found {len(records):,} opening range records")
        
        if not records:
            print(f"  WARNING: No opening range data extracted!")
            return
        
        # Date range
        first_date = records[0]['date']
        last_date = records[-1]['date']
        print(f"  Date range: {first_date} to {last_date}")
        
        # Save to JSON
        output_file = DATA_DIR / f"{ticker}_opening_range.json"
        with open(output_file, 'w') as f:
            json.dump(records, f, indent=2)
        
        print(f"  Saved to {output_file}")
        
        # Print sample stats
        range_pts = [r['range_pts'] for r in records]
        avg_range = sum(range_pts) / len(range_pts)
        print(f"  Avg range: {avg_range:.2f} pts")
        
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    tickers = ["ES1", "NQ1", "CL1", "GC1", "RTY1", "YM1"]
    
    if len(sys.argv) > 1:
        target = sys.argv[1].upper()
        if target == "ALL":
            for ticker in tickers:
                precompute_opening_range(ticker)
        else:
            precompute_opening_range(target)
    else:
        # Default to all tickers
        print("Usage: python precompute_opening_range.py <TICKER|ALL>")
        print("Running for all tickers...\n")
        for ticker in tickers:
            precompute_opening_range(ticker)

if __name__ == "__main__":
    main()
