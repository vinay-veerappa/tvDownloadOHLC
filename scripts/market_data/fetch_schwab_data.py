import os
import sys
import json
import schwab
import pandas as pd
from datetime import datetime, timedelta
import time
import argparse

# Ensure we can import data_utils from local dir
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR # Assuming this exists from previous scan

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    "ES1": "/ES", 
    "NQ1": "/NQ",
    "RTY1": "/RTY",
    "YM1": "/YM",
    "CL1": "/CL",
    "GC1": "/GC",
    "SPY": "SPY", 
    "QQQ": "QQQ", 
    "IWM": "IWM", 
    "SPX": "$SPX", 
    "VIX": "$VIX"
}

def get_schwab_client():
    # Secrets expected in project root
    root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
    token_path = os.path.join(root_dir, "token.json")
    secrets_path = os.path.join(root_dir, "secrets.json")
    
    if not os.path.exists(token_path) or not os.path.exists(secrets_path):
        print(f"Error: Credentials not found at {root_dir}")
        return None
        
    with open(secrets_path, "r") as f:
        secrets = json.load(f)
        
    try:
        client = schwab.auth.client_from_token_file(
            token_path=token_path,
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
        return client
    except Exception as e:
        print(f"Auth Failed: {e}")
        return None

def fetch_data(client, symbol, timeframe, start_dt, end_dt):
    # Map timeframe to Schwab params
    # tf input: "1m", "5m", "15m", "30m", "1h", "1d"
    
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
    elif timeframe == '1d':
        period_type = 'month' # Schwab daily requires month/year period
        freq_type = 'daily'
        freq = 1
    else:
        print(f"Unsupported timeframe: {timeframe} (Schwab API only supports 1m, 5m, 15m, 30m, 1d)")
        return None

    print(f"Fetching {symbol} ({timeframe}) from {start_dt} to {end_dt}...")
    
    try:
        resp = client.get_price_history(
            symbol,
            period_type=period_type,
            frequency_type=freq_type,
            frequency=freq,
            start_datetime=start_dt,
            end_datetime=end_dt,
            need_extended_hours_data=True
        ).json()
        
        if 'candles' not in resp or not resp['candles']:
            print(f"No candles found. Response: {resp.get('errors') or 'Empty'}")
            return None
            
        candles = resp['candles']
        print(f"  Got {len(candles)} rows.")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        # Schwab 'datetime' is milliseconds (int)
        df['time'] = df['datetime'] // 1000
        df['datetime_idx'] = pd.to_datetime(df['datetime'], unit='ms')
        df.set_index('datetime_idx', inplace=True)
        
        # Ensure only necessary columns
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
        # Drop any NaNs just in case
        df = df.dropna(subset=['time'])
        
        return df
        
    except Exception as e:
        print(f"Fetch Error {symbol}: {e}")
        return None

def update_ticker(ticker, timeframe):
    client = get_schwab_client()
    if not client: return

    schwab_ticker = SCHWAB_MAP.get(ticker, ticker) # Default to same if not mapped
    
    # *** IMPORTANT: Write to LIVE STORAGE, not Historical ***
    # Live Storage location: data/live/live_storage_{schwab_ticker or ticker}.parquet
    # We use the Schwab ticker format for futures (e.g., -NQ, -ES)
    live_dir = os.path.join(DATA_DIR, "live")
    os.makedirs(live_dir, exist_ok=True)
    
    # Determine filename based on ticker format
    # Futures use Schwab format in live storage (e.g., live_storage_-NQ.parquet)
    if schwab_ticker.startswith("/"):
        storage_ticker = schwab_ticker.replace("/", "-") # /NQ -> -NQ
    else:
        storage_ticker = ticker
        
    filename = f"live_storage_{storage_ticker}.parquet"
    filepath = os.path.join(live_dir, filename)
    
    start_dt = datetime.now() - timedelta(days=5) # Default: Last 5 days lookback
    
    existing_df = None
    
    # 1. Check existing data to bridge gap
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_parquet(filepath)
            
            # Clean existing data: handle NaN 'time' or missing columns
            if 'time' in existing_df.columns:
                 # Drop if 'time' is NaN and we have a valid index
                 if existing_df['time'].isna().any() and isinstance(existing_df.index, pd.DatetimeIndex):
                      existing_df['time'] = (existing_df.index.astype('int64') // 10**9)
                 existing_df = existing_df.dropna(subset=['time'])
            
            # Ensure DateTime Index for deduplication
            if not isinstance(existing_df.index, pd.DatetimeIndex):
                if 'time' in existing_df.columns:
                    existing_df.index = pd.to_datetime(existing_df['time'], unit='s')
                elif 'datetime' in existing_df.columns:
                    existing_df.index = pd.to_datetime(existing_df['datetime'])
                elif 'date' in existing_df.columns:
                     existing_df.index = pd.to_datetime(existing_df['date'])
            
            if not existing_df.empty:
                last_dt = existing_df.index.max()
                start_dt = last_dt
                print(f"Existing data found. Last timestamp: {last_dt}")
        except Exception as e:
            print(f"Error reading existing file: {e}")
            
    # 2. Fetch New Data
    end_dt = datetime.now()
    
    if start_dt >= end_dt - timedelta(minutes=1): 
        print("Data is up to date.")
        return

    new_df = fetch_data(client, schwab_ticker, timeframe, start_dt, end_dt)
    
    if new_df is None or new_df.empty:
        return

    # 3. Merge
    if existing_df is not None:
        combined = pd.concat([existing_df, new_df])
        # Remove duplicates based on index
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
    else:
        combined = new_df
        
    # 4. Save
    try:
        # Save standard columns
        data_utils.safe_save_parquet(combined, filepath)
        print(f"Successfully updated {filename} (Total rows: {len(combined)})")
    except Exception as e:
        print(f"Save Failed: {e}")
        # Metadata update (inventory) could happen here

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    parser.add_argument("--tf", default="1m", help="Timeframe (1m, 5m, 1h, 1d)")
    
    args = parser.parse_args()
    update_ticker(args.ticker, args.tf)
