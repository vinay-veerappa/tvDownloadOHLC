"""
Update ticker data using Schwab API

This script updates Parquet files in data/ using the Schwab API.
It bridges gaps between the last recorded timestamp and current time.

Usage:
    python scripts/market_data/update_via_schwab.py VVIX --tf 1m
    python scripts/market_data/update_via_schwab.py VVIX --tf 1d
    python scripts/market_data/update_via_schwab.py --all
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
import asyncio
import httpx
import argparse
import subprocess
from pathlib import Path

# Ensure we can import data_utils from local dir
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR

# Ensure repository root is in sys.path so scripts can find top-level packages
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from scripts.streaming.options.config import HUB_URL

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    # Indices
    "SPX": "$SPX", 
    "VIX": "$VIX",
    "VVIX": "$VVIX",
    "NDX": "$NDX",
    "RUT": "$RUT",
    "DJI": "$DJI",
    
    # ETFs
    "SPY": "SPY", 
    "QQQ": "QQQ", 
    "IWM": "IWM", 
    "DIA": "DIA", 
    "GLD": "GLD", 
    "TLT": "TLT", 
    
    # Key Stocks
    "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", 
    "AMD": "AMD", "TSLA": "TSLA", "AMZN": "AMZN",
    "META": "META", "GOOGL": "GOOGL",
    "PLTR": "PLTR", "JPM": "JPM", "GS": "GS",

    # Futures
    "ES1": "/ES", 
    "NQ1": "/NQ",
    "RTY1": "/RTY",
    "YM1": "/YM",
    "CL1": "/CL",
    "GC1": "/GC",
    "ES": "/ES",
    "NQ": "/NQ",
    "RTY": "/RTY",
    "YM": "/YM",
    "CL": "/CL",
    "GC": "/GC"
}

async def hub_request(method, params):
    """Send a REST request through the Hub's proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=30.0)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            else:
                return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {str(e)}"}

async def fetch_data(symbol, timeframe, start_dt, end_dt):
    """Fetch historical data from Schwab Hub API"""
    # Map timeframe to Schwab params
    period_type = 'day'
    freq_type = 'minute'
    freq = 1
    
    if timeframe == '1m':
        freq = 1
    elif timeframe == '5m':
        freq = 5
    elif timeframe == '15m':
        freq = 15
    elif timeframe == '30m':
        freq = 30
    elif timeframe == '1h':
        freq_type = 'minute'
        freq = 60
    elif timeframe == '1d':
        period_type = 'month'
        freq_type = 'daily'
        freq = 1
    elif timeframe == '1W':
        period_type = 'year'
        freq_type = 'weekly'
        freq = 1
    else:
        print(f"Unsupported timeframe: {timeframe}")
        return None

    print(f"Fetching {symbol} ({timeframe}) from {start_dt} to {end_dt}...")
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    try:
        resp_raw = await hub_request("get_price_history", {
            "symbol": symbol,
            "period_type": period_type,
            "frequency_type": freq_type,
            "frequency": freq,
            "start_date": start_ms,
            "end_date": end_ms,
            "need_extended_hours_data": True
        })
        
        if resp_raw.get("status") != "success":
            print(f"No candles found. Response: {resp_raw.get('message')}")
            return None
            
        resp = resp_raw.get("data", {})
        candles = resp.get('candles', [])
        
        if not candles:
            print("No candles found.")
            return None
            
        print(f"  Got {len(candles)} rows.")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        # Schwab 'datetime' is milliseconds (int)
        df['time'] = pd.to_datetime(df['datetime'], unit='ms')
        df = df.set_index('time')
        
        # Ensure only necessary columns
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        # Drop any NaNs just in case
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        
        return df
        
    except Exception as e:
        print(f"Fetch Error {symbol}: {e}")
        return None

async def update_ticker(ticker, timeframe):
    """Update a single ticker's data for a specific timeframe"""
    schwab_ticker = SCHWAB_MAP.get(ticker)
    if not schwab_ticker:
        print(f"Error: {ticker} not found in SCHWAB_MAP")
        return False
    
    # Map timeframe to filename convention
    file_tf = timeframe
    if timeframe == '1d':
        file_tf = '1d'
    elif timeframe == '1W':
        file_tf = '1W'
    
    # Handle aliases (e.g., NQ -> NQ1) for standard filenames in data/
    storage_ticker = ticker
    if ticker in ["NQ", "ES", "RTY", "YM", "CL", "GC"]:
        storage_ticker = f"{ticker}1"
        
    filename = f"{storage_ticker}_{file_tf}.parquet"
    filepath = os.path.join(DATA_DIR, filename)
    
    print(f"\n--- Updating {ticker} ({timeframe}) ---")
    
    # Determine lookback period
    if timeframe == '1m':
        default_lookback = timedelta(days=5)
    elif timeframe in ['5m', '15m', '30m']:
        default_lookback = timedelta(days=60)
    elif timeframe == '1h':
        default_lookback = timedelta(days=365)
    elif timeframe == '1d':
        default_lookback = timedelta(days=730)  # 2 years
    elif timeframe == '1W':
        default_lookback = timedelta(days=1825)  # 5 years
    else:
        default_lookback = timedelta(days=30)
    
    start_dt = datetime.now(timezone.utc) - default_lookback
    existing_df = None
    
    # 1. Check existing data to bridge gap
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_parquet(filepath)
            
            # Ensure DateTime Index
            if not isinstance(existing_df.index, pd.DatetimeIndex):
                if 'datetime' in existing_df.columns:
                    existing_df.index = pd.to_datetime(existing_df['datetime'])
                elif 'date' in existing_df.columns:
                    existing_df.index = pd.to_datetime(existing_df['date'])
            
            if not existing_df.empty:
                # Ensure index is naive UTC for comparison
                if existing_df.index.tz is not None:
                    existing_df.index = existing_df.index.tz_convert(None)
                
                last_dt = existing_df.index.max()
                # Make last_dt aware
                start_dt = last_dt.replace(tzinfo=timezone.utc)
                print(f"Existing data found. Last timestamp: {last_dt}")
                
                # Create backup before modifying
                data_utils.create_backup(filepath)
        except Exception as e:
            print(f"Error reading existing file: {e}")
            
    # 2. Fetch New Data
    end_dt = datetime.now(timezone.utc)
        
    if start_dt >= end_dt - timedelta(minutes=1): 
        print("Data is up to date.")
        return True

    new_df = await fetch_data(schwab_ticker, timeframe, start_dt, end_dt)
    
    if new_df is None or new_df.empty:
        print("No new data fetched.")
        return False

    # 3. Merge
    if existing_df is not None and not existing_df.empty:
        # Normalize new data to naive UTC as well
        if new_df.index.tz is not None:
            new_df.index = new_df.index.tz_convert(None)
            
        combined = pd.concat([existing_df, new_df])
        # Remove duplicates based on index
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
        # Ensure index has a name for the JSON converter
        combined.index.name = 'datetime'
    else:
        combined = new_df
        if combined.index.tz is not None:
            combined.index = combined.index.tz_convert(None)
        combined.index.name = 'datetime'
        
    # 4. Save
    try:
        data_utils.safe_save_parquet(combined, filepath)
        print(f"Successfully updated {filename} (Total rows: {len(combined)})")
        return True
    except Exception as e:
        print(f"Save Failed: {e}")
        return False

async def run_json_update(ticker):
    """Run the JSON chunking script for the specific ticker"""
    storage_ticker = ticker
    if ticker in ["NQ", "ES", "RTY", "YM", "CL", "GC"]:
        storage_ticker = f"{ticker}1"
        
    print(f"Updating Web JSON chunks for {storage_ticker}...")
    script_path = os.path.join(current_dir, "../data_processing/convert/convert_to_chunked_json.py")
    
    if not os.path.exists(script_path):
        print(f"Warning: JSON converter not found at {script_path}")
        return
        
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_path, storage_ticker,
            cwd=os.path.abspath(os.path.join(current_dir, "../../")),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            print(f"DONE: Web JSON chunks updated for {storage_ticker}")
        else:
            print(f"FAILED: JSON update failed: {stderr.decode()}")
    except Exception as e:
        print(f"Error running JSON update: {e}")

async def run_all(args):
    if args.all:
        timeframes = ['1m', '5m', '15m', '1h', '1d', '1W']
        updated_tickers = set()
        for ticker in SCHWAB_MAP.keys():
            success = False
            for tf in timeframes:
                if await update_ticker(ticker, tf):
                    success = True
                await asyncio.sleep(0.5)
            if success:
                updated_tickers.add(ticker)
        
        if not args.no_json:
            for ticker in updated_tickers:
                await run_json_update(ticker)
                
    elif args.ticker:
        success = await update_ticker(args.ticker, args.tf)
        if success and not args.no_json:
            await run_json_update(args.ticker)
        if not success:
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Update ticker data via Schwab Hub API')
    parser.add_argument("ticker", nargs='?', help="Ticker symbol (e.g. VVIX, SPX, NQ1)")
    parser.add_argument("--tf", default="1m", help="Timeframe (1m, 5m, 15m, 1h, 1d, 1W)")
    parser.add_argument("--all", action="store_true", help="Update all tickers in SCHWAB_MAP")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON chunking update")
    
    args = parser.parse_args()
    
    if not args.ticker and not args.all:
        parser.print_help()
        sys.exit(1)
        
    asyncio.run(run_all(args))

if __name__ == "__main__":
    main()
