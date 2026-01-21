import os
import sys
import json
import schwab
import pandas as pd
from datetime import datetime, timedelta

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils
from data_utils import DATA_DIR
LIVE_DIR = os.path.join(DATA_DIR, "live")

def get_client():
    root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
    token_path = os.path.join(root_dir, "token.json")
    secrets_path = os.path.join(root_dir, "secrets.json")
    
    with open(secrets_path, "r") as f:
        secrets = json.load(f)
        
    return schwab.auth.client_from_token_file(
        token_path=token_path,
        api_key=secrets["app_key"],
        app_secret=secrets["app_secret"],
        enforce_enums=False
    )

def force_fill(ticker, symbol):
    client = get_client()
    
    # Gap Window
    start_dt = datetime(2026, 1, 14, 0, 0, 0)
    end_dt = datetime(2026, 1, 21, 12, 0, 0) # Up to noon today
    
    print(f"Force fetching {symbol} from {start_dt} to {end_dt}...")
    
    resp = client.get_price_history(
        symbol,
        period_type='day',
        frequency_type='minute',
        frequency=1,
        start_datetime=start_dt,
        end_datetime=end_dt,
        need_extended_hours_data=True
    ).json()
    
    if 'candles' not in resp:
        print("No candles returned!")
        return
        
    candles = resp['candles']
    print(f"Got {len(candles)} new candles.")
    
    # Process
    df_new = pd.DataFrame(candles)
    df_new['time'] = df_new['datetime'] # already in ms? Schwab returns ms.
    
    # Keep only relevant columns
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
        
        # Merge
        combined = pd.concat([df_old, df_new])
        
        # Deduplicate
        original_len = len(combined)
        combined = combined.drop_duplicates(subset=['time'], keep='last')
        combined = combined.sort_values('time')
        
        print(f"Merged: {original_len} -> {len(combined)} rows.")
        
        combined.to_parquet(path, index=False)
        print("Saved.")
    else:
        print("Live storage not found to merge into!")

if __name__ == "__main__":
    force_fill("NQ1", "/NQ")
