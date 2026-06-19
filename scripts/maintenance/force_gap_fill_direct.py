import os
import sys
import json
import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from schwab.auth import easy_client

current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR
LIVE_DIR = os.path.join(DATA_DIR, "live")

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
    try:
        return easy_client(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url='https://127.0.0.1:8182',
            token_path='token.json',
            enforce_enums=False)
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def force_fill_direct(client, symbol, start_dt, end_dt):
    print(f"Force fetching {symbol} 1m from {start_dt} to {end_dt}...")
    
    resp = client.get_price_history(
        symbol,
        frequency_type="minute",
        frequency=1,
        start_datetime=start_dt,
        end_datetime=end_dt,
        need_extended_hours_data=True
    )
    
    if resp.status_code != 200:
        print(f"Failed: {resp.status_code} - {resp.text}")
        return
        
    data = resp.json()
    candles = data.get('candles', [])
    
    if not candles:
        print("No candles returned!")
        return
        
    print(f"Got {len(candles)} new candles.")
    
    # Process
    df_new = pd.DataFrame(candles)
    df_new['time'] = df_new['datetime']
    
    df_new = df_new.rename(columns={
        "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"
    })
    df_new = df_new[['time', 'open', 'high', 'low', 'close', 'volume']]
    
    # Load Existing Live Storage
    safe_symbol = symbol.replace("/", "-")
    path = os.path.join(LIVE_DIR, f"live_storage_{safe_symbol}.parquet")
    
    if os.path.exists(path):
        print(f"Merging with {path}...")
        df_old = pd.read_parquet(path)
        
        combined = pd.concat([df_old, df_new])
        original_len = len(combined)
        combined = combined.drop_duplicates(subset=['time'], keep='last')
        combined = combined.sort_values('time')
        
        print(f"Merged: {original_len} -> {len(combined)} rows.")
        combined.to_parquet(path, index=False)
        print("Saved.")
    else:
        print("Live storage not found to merge into!")

def main():
    client = get_client()
    if not client: return
    
    symbols = [
        "AAPL", "AMZN", "GOOGL", "META", "MSFT", 
        "NFLX", "NVDA", "QQQ", "SPY", "TSLA",
        "/CL", "/ES", "/GC", "/NQ", "/RTY", "/YM"
    ]
    
    # Late-May Gap: May 26 to June 2
    start_dt = datetime(2026, 5, 26, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 6, 2, 23, 59, 59, tzinfo=timezone.utc)
    
    for sym in symbols:
        try:
            force_fill_direct(client, sym, start_dt, end_dt)
        except Exception as e:
            print(f"Failed for {sym}: {e}")

if __name__ == "__main__":
    main()
