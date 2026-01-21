import os
import sys
import json
import schwab
import pandas as pd
from datetime import datetime, timedelta
import argparse

# Ensure we can import data_utils from local dir
# Assuming this script is in scripts/maintenance/
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR

# Live storage is in data/live/
LIVE_DIR = os.path.join(DATA_DIR, "live")
os.makedirs(LIVE_DIR, exist_ok=True)

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    "NQ1": "/NQ",
    "ES1": "/ES",
    "YM1": "/YM",
    "RTY1": "/RTY",
    "CL1": "/CL",
    "GC1": "/GC"
}

def get_schwab_client():
    # Secrets expected in project root (../../)
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

def fetch_data(client, symbol, start_dt, end_dt):
    print(f"Fetching {symbol} from {start_dt} to {end_dt}...")
    
    try:
        resp = client.get_price_history(
            symbol,
            period_type='day',
            frequency_type='minute',
            frequency=1,
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
        
        # Rename columns to standard match
        df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
        }, inplace=True)
        
        # Keep time column as unix timestamp (milliseconds) for consistency with stream_chart.py
        # DatetimeIndex is ns (10^-9). ms is 10^-3. Divide by 10^6.
        df['time'] = (df.index.astype('int64') // 10**6).astype('int64')
        
        return df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
    except Exception as e:
        print(f"Fetch Error {symbol}: {e}")
        return None

def backfill_live(ticker):
    client = get_schwab_client()
    if not client: return

    schwab_ticker = SCHWAB_MAP.get(ticker, ticker)
    
    # Determined Safe Symbol for Filename: /NQ -> -NQ
    safe_symbol = schwab_ticker.replace("/", "-")
    filename = f"live_storage_{safe_symbol}.parquet"
    filepath = os.path.join(LIVE_DIR, filename)
    
    # User Request: Source from Historical Parquet (Jan 1 2025 -> Present)
    # This bypasses Schwab API limits for >45 day old data.
    
    # 1. Load Historical File
    hist_file = os.path.join(DATA_DIR, f"{ticker}_1m.parquet")
    if not os.path.exists(hist_file):
        print(f"Error: Historical file {hist_file} not found.")
        return

    print(f"Loading historical source: {hist_file}...")
    df_hist = pd.read_parquet(hist_file)
    
    # 2. Filter for Range (Jan 1 2025 -> Now)
    # Historical 'time' is in SECONDS (Unix Timestamp)
    start_ts_sec = int(datetime(2025, 1, 1).timestamp())
    
    if 'time' not in df_hist.columns:
        # Fallback if time is index
        df_hist = df_hist.reset_index()
        if 'time' not in df_hist.columns and 'datetime' in df_hist.columns:
             df_hist['time'] = df_hist['datetime'].astype('int64') // 10**9
    
    df_subset = df_hist[df_hist['time'] >= start_ts_sec].copy()
    print(f"  Filtered {len(df_subset)} rows from Jan 1, 2025.")

    # 3. Convert to Live Format (Milliseconds)
    # Live storage expects 'time' in ms. Historical is s.
    df_subset['time'] = df_subset['time'] * 1000
    
    # Ensure columns match live format
    cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    # Live often lacks volume or has it as 0, but we have it, so keep it.
    df_subset = df_subset[cols]

    # 4. Merge with existing Live Storage?
    # User said "copy data from that into live storage".
    # Since historical is now "up to date" (we ran fetch_schwab_data earlier today),
    # this subset effectively covers everything we need.
    # We can just overwrite.
    
    combined = df_subset.sort_values('time')

    # Save
    try:
        combined.to_parquet(filepath, index=False)
        print(f"✅ Successfully backfilled {filename} from local history.")
        print(f"   Total rows: {len(combined)}")
        print(f"   Range: {pd.to_datetime(combined['time'].min(), unit='ms')} -> {pd.to_datetime(combined['time'].max(), unit='ms')}")
    except Exception as e:
        print(f"Save Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker (e.g. NQ1)")
    args = parser.parse_args()
    
    backfill_live(args.ticker)
