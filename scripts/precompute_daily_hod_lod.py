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

DATA_DIR = Path(__file__).parent.parent / 'data'
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
    ticker = 'NQ1'
    print(f"Computing daily HOD/LOD times for {ticker}...")
    
    results = compute_daily_hod_lod(ticker)
    
    print(f"Computed HOD/LOD for {len(results)} trading days")
    
    # Show sample
    sample_dates = sorted(results.keys())[-5:]
    print("\nSample (last 5 days):")
    for d in sample_dates:
        r = results[d]
        print(f"  {d}: HOD={r['hod_time']} @ {r['hod_price']:.2f}, LOD={r['lod_time']} @ {r['lod_price']:.2f}")
    
    # Show distribution by hour
    from collections import defaultdict
    hod_hours = defaultdict(int)
    lod_hours = defaultdict(int)
    
    for r in results.values():
        hod_h = int(r['hod_time'].split(':')[0])
        lod_h = int(r['lod_time'].split(':')[0])
        hod_hours[hod_h] += 1
        lod_hours[lod_h] += 1
    
    print("\nHOD distribution by hour:")
    for h in sorted(hod_hours.keys()):
        pct = 100 * hod_hours[h] / len(results)
        bar = '█' * int(pct)
        print(f"  {h:02d}:00 - {hod_hours[h]:4d} ({pct:5.1f}%) {bar}")
    
    print("\nLOD distribution by hour:")
    for h in sorted(lod_hours.keys()):
        pct = 100 * lod_hours[h] / len(results)
        bar = '█' * int(pct)
        print(f"  {h:02d}:00 - {lod_hours[h]:4d} ({pct:5.1f}%) {bar}")
    
    # Save to JSON
    output_path = DATA_DIR / f'{ticker}_daily_hod_lod.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
