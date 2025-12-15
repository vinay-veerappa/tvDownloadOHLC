"""
Fetch VIX and VVIX historical data from Yahoo Finance

Usage:
    python scripts/fetch_vix_data.py                    # Fetch all history
    python scripts/fetch_vix_data.py --days 30          # Last 30 days
    python scripts/fetch_vix_data.py --start 2024-01-01 # From specific date

Output:
    data/journal/vix_vvix_daily.csv
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
import urllib.request
import json
import csv

def fetch_yahoo_chart(symbol: str, start_ts: int, end_ts: int) -> dict:
    """Fetch chart data from Yahoo Finance API"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval=1d&includePrePost=false"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def parse_yahoo_response(data: dict) -> list:
    """Parse Yahoo Finance response into list of dicts"""
    if not data or 'chart' not in data:
        return []
    
    result = data['chart']['result']
    if not result:
        return []
    
    chart = result[0]
    timestamps = chart.get('timestamp', [])
    
    if not timestamps:
        return []
    
    indicators = chart.get('indicators', {})
    quote = indicators.get('quote', [{}])[0]
    
    opens = quote.get('open', [])
    highs = quote.get('high', [])
    lows = quote.get('low', [])
    closes = quote.get('close', [])
    
    rows = []
    for i, ts in enumerate(timestamps):
        if closes[i] is None:
            continue
            
        date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        rows.append({
            'date': date,
            'timestamp': ts,
            'open': opens[i] if i < len(opens) else None,
            'high': highs[i] if i < len(highs) else None,
            'low': lows[i] if i < len(lows) else None,
            'close': closes[i] if i < len(closes) else None,
        })
    
    return rows

def merge_vix_vvix(vix_data: list, vvix_data: list) -> list:
    """Merge VIX and VVIX data by date"""
    vix_by_date = {row['date']: row for row in vix_data}
    vvix_by_date = {row['date']: row for row in vvix_data}
    
    all_dates = sorted(set(vix_by_date.keys()) | set(vvix_by_date.keys()))
    
    merged = []
    for date in all_dates:
        row = {'date': date}
        
        if date in vix_by_date:
            vix = vix_by_date[date]
            row['vix_open'] = vix['open']
            row['vix_high'] = vix['high']
            row['vix_low'] = vix['low']
            row['vix_close'] = vix['close']
        else:
            row['vix_open'] = None
            row['vix_high'] = None
            row['vix_low'] = None
            row['vix_close'] = None
            
        if date in vvix_by_date:
            vvix = vvix_by_date[date]
            row['vvix_open'] = vvix['open']
            row['vvix_high'] = vvix['high']
            row['vvix_low'] = vvix['low']
            row['vvix_close'] = vvix['close']
        else:
            row['vvix_open'] = None
            row['vvix_high'] = None
            row['vvix_low'] = None
            row['vvix_close'] = None
            
        merged.append(row)
    
    return merged

def save_csv(data: list, output_path: Path):
    """Save merged data to CSV"""
    if not data:
        print("No data to save")
        return
        
    fieldnames = ['date', 'vix_open', 'vix_high', 'vix_low', 'vix_close',
                  'vvix_open', 'vvix_high', 'vvix_low', 'vvix_close']
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"✅ Saved {len(data)} rows to {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Fetch VIX/VVIX data from Yahoo Finance')
    parser.add_argument('--days', type=int, help='Number of days to fetch')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, default='data/journal/vix_vvix_daily.csv')
    args = parser.parse_args()
    
    # Calculate date range
    end_date = datetime.now()
    
    if args.days:
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        # Default: all available history (VVIX started ~2006)
        start_date = datetime(2006, 1, 1)
    
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    
    print(f"📊 Fetching VIX/VVIX data from {start_date.date()} to {end_date.date()}")
    
    # Fetch VIX
    print("Fetching ^VIX...")
    vix_raw = fetch_yahoo_chart('^VIX', start_ts, end_ts)
    vix_data = parse_yahoo_response(vix_raw)
    print(f"  Got {len(vix_data)} VIX records")
    
    # Fetch VVIX
    print("Fetching ^VVIX...")
    vvix_raw = fetch_yahoo_chart('^VVIX', start_ts, end_ts)
    vvix_data = parse_yahoo_response(vvix_raw)
    print(f"  Got {len(vvix_data)} VVIX records")
    
    # Merge
    merged = merge_vix_vvix(vix_data, vvix_data)
    print(f"  Merged: {len(merged)} unique dates")
    
    # Output path
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    save_csv(merged, output_path)
    
    # Print sample
    if merged:
        print("\n📈 Latest data:")
        for row in merged[-5:]:
            vvix_str = f"{row['vvix_close']:.2f}" if row['vvix_close'] else 'N/A'
            print(f"  {row['date']}: VIX={row['vix_close']:.2f}, VVIX={vvix_str}")

if __name__ == '__main__':
    main()
