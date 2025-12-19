"""
Compute true daily HOD/LOD times from 1-minute OHLC data.

Trading day runs from 18:00 ET (previous calendar day) to 17:00 ET.
For each trading day, finds the minute bar where the high/low of the day occurred.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

DATA_DIR = Path(__file__).parent.parent.parent / 'data'
ET = pytz.timezone('US/Eastern')


def compute_daily_hod_lod(ticker: str) -> dict:
    """
    Compute the true HOD/LOD times for each trading day.
    
    Returns dict mapping date -> {hod_time, lod_time, hod_price, lod_price}
    """
    # Load 1-minute data
    parquet_path = DATA_DIR / f'{ticker}_1m.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing {parquet_path}")
    
    df = pd.read_parquet(parquet_path)
    
    # Ensure datetime index in ET
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(ET)
    else:
        df.index = df.index.tz_convert(ET)
    
    # Add trading_date column (day that starts at 18:00)
    # If time >= 18:00, trading_date is next calendar day
    # If time < 18:00, trading_date is current calendar day
    def get_trading_date(ts):
        if ts.time() >= time(18, 0):
            return (ts + timedelta(days=1)).date()
        else:
            return ts.date()
    
    df['trading_date'] = df.index.map(get_trading_date)
    
    # Group by trading date
    results = {}
    
    for trading_date, group in df.groupby('trading_date'):
        if len(group) < 100:  # Skip days with too little data
            continue
        
        # Find HOD (highest high)
        hod_idx = group['high'].idxmax()
        hod_price = group.loc[hod_idx, 'high']
        hod_time = hod_idx.strftime('%H:%M')
        
        # Find LOD (lowest low)
        lod_idx = group['low'].idxmin()
        lod_price = group.loc[lod_idx, 'low']
        lod_time = lod_idx.strftime('%H:%M')
        
        results[str(trading_date)] = {
            'hod_time': hod_time,
            'lod_time': lod_time,
            'hod_price': float(hod_price),
            'lod_price': float(lod_price),
            'daily_high': float(group['high'].max()),
            'daily_low': float(group['low'].min()),
            'daily_open': float(group['open'].iloc[0]),
        }
    
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", default=["NQ1"], help="Tickers to process")
    args = parser.parse_args()

    for ticker in args.tickers:
        print(f"\n=== Computing daily HOD/LOD times for {ticker} ===")
        try:
            results = compute_daily_hod_lod(ticker)
            
            print(f"Computed HOD/LOD for {len(results)} trading days")
            
            # Show sample
            sample_dates = sorted(results.keys())[-5:]
            print("Sample (last 5 days):")
            for d in sample_dates:
                r = results[d]
                print(f"  {d}: HOD={r['hod_time']} @ {r['hod_price']:.2f}, LOD={r['lod_time']} @ {r['lod_price']:.2f}")
            
            # Save to JSON
            output_path = DATA_DIR / f'{ticker}_daily_hod_lod.json'
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Saved to {output_path}")

        except Exception as e:
            print(f"Error processing {ticker}: {e}")


if __name__ == '__main__':
    main()
