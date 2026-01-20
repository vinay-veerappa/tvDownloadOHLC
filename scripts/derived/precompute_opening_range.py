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
    Extract various opening ranges and the 12:00 PM close for each trading day.
    """
    # Add grouping columns
    df['date'] = df['datetime'].dt.date
    df['time_only'] = df['datetime'].dt.time
    
    records = []
    
    # Process each day
    for date_obj, day_df in df.groupby('date'):
        # 1m OR (9:30-9:31)
        or_1m = day_df[day_df['time_only'] == time(9, 30)]
        if or_1m.empty: continue
        
        row_1m = or_1m.iloc[0]
        
        # 12:00 PM Close
        close_12 = day_df[day_df['time_only'] == time(12, 0)]
        close_12_val = close_12.iloc[0]['close'] if not close_12.empty else None
        
        # MFE Calculation (Max Extension from 09:30-12:00 relative to 1m OR)
        window_12 = day_df[(day_df['time_only'] >= time(9, 30)) & (day_df['time_only'] <= time(12, 0))]
        
        o_1m = row_1m['open']
        h_1m = row_1m['high']
        l_1m = row_1m['low']
        
        # Calculate MFEs in the 12:00 window
        max_high = window_12['high'].max()
        min_low = window_12['low'].min()
        
        mfe_bull = max_high - h_1m
        mfe_bear = l_1m - min_low
        
        records.append({
            'date': str(date_obj),
            'or_1m': {
                'open': round(o_1m, 2),
                'high': round(h_1m, 2),
                'low': round(l_1m, 2),
                'close': round(row_1m['close'], 2),
                'range_pts': round(h_1m - l_1m, 2)
            },
            'close_1200': round(close_12_val, 2) if close_12_val else None,
            'mfe_1200': {
                'bull_pts': round(max(0, mfe_bull), 2),
                'bear_pts': round(max(0, mfe_bear), 2),
                'bull_pct': round(max(0, mfe_bull) / o_1m * 100, 4),
                'bear_pct': round(max(0, mfe_bear) / o_1m * 100, 4)
            },
            'timestamp': int(row_1m['datetime'].timestamp())
        })
    
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
