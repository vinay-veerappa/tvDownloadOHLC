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
    elif timeframe == '1h':
        freq = 60
    elif timeframe == '1d':
        period_type = 'month' # Schwab daily requires month/year period
        freq_type = 'daily'
        freq = 1
    else:
        print(f"Unsupported timeframe: {timeframe}")
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
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        df.set_index('datetime', inplace=True)
        
        # Renaissance keys
        df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
        }, inplace=True)
        
        return df[['open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        print(f"Fetch Error {symbol}: {e}")
        return None

def update_ticker(ticker, timeframe):
    client = get_schwab_client()
    if not client: return

    schwab_ticker = SCHWAB_MAP.get(ticker, ticker) # Default to same if not mapped
    
    filename = f"{ticker}_{timeframe}.parquet"
    filepath = os.path.join(DATA_DIR, filename)
    
    start_dt = datetime.now() - timedelta(days=5) # Default: Last 5 days lookback
    
    existing_df = None
    
    # 1. Check existing data to bridge gap
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_parquet(filepath)
            # Ensure DateTime Index
            if not isinstance(existing_df.index, pd.DatetimeIndex):
                if 'datetime' in existing_df.columns:
                    existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
                    existing_df.set_index('datetime', inplace=True)
                elif 'date' in existing_df.columns:
                     existing_df['datetime'] = pd.to_datetime(existing_df['date'])
                     existing_df.set_index('datetime', inplace=True)
            
            if not existing_df.empty:
                last_dt = existing_df.index.max()
                # Start fetching from last known time
                # Schwab might return overlap, we handle duplication later
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
