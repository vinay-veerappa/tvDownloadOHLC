
import os
import sys
import json
import schwab
import pandas as pd
from datetime import datetime, timedelta
import time

# Ensure we can import data_utils from local dir
# Assuming this script is in scripts/market_data/
current_dir = os.path.dirname(os.path.abspath(__file__))
# data_utils is in scripts/utils
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)

import data_utils

# Map App Ticker -> Schwab Ticker
SCHWAB_MAP = {
    # Indices
    "SPX": "$SPX", 
    "VIX": "$VIX", 
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

    # Futures (Trying generic symbols, might need specific contracts)
    # Schwab usually requires /ES, /NQ, or specific month codes like ESZ25
    "ES1": "/ES", 
    "NQ1": "/NQ",
    "RTY1": "/RTY",
    "YM1": "/YM"
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

def fetch_15m_history(client, symbol):
    print(f"Fetching 6mo 15m data for {symbol}...")
    
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=730) # 2 Years
    
    try:
        resp = client.get_price_history(
            symbol,
            period_type='day',
            frequency_type='minute',
            frequency=15,
            start_datetime=start_dt,
            end_datetime=end_dt,
            need_extended_hours_data=True
        ).json()
        
        if 'candles' not in resp or not resp['candles']:
            print(f"No candles found for {symbol}. Response: {resp.get('errors') or 'Empty'}")
            return None
            
        candles = resp['candles']
        print(f"  Got {len(candles)} rows.")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        # Schwab cols: close, datetime (ms), high, low, open, volume
        
        # Normalize to App Standard
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

def update_deep_history():
    client = get_schwab_client()
    if not client: return

    for app_ticker, schwab_ticker in SCHWAB_MAP.items():
        print(f"\n--- Processing {app_ticker} ({schwab_ticker}) ---")
        
        new_df = fetch_15m_history(client, schwab_ticker)
        if new_df is None or new_df.empty:
            continue
            
        # File Path (using app_ticker)
        # UpdateIntraday uses: {ticker}_15m.parquet
        filename = f"{app_ticker}_15m.parquet"
        
        # data_utils.DATA_DIR assumes ../../data usually? 
        # Checking data_utils source would be good, but we can standardise.
        # Assuming data_utils.DATA_DIR is correct.
        
        filepath = os.path.join(data_utils.DATA_DIR, filename)
        
        # Merge Logic
        if os.path.exists(filepath):
            try:
                old_df = pd.read_parquet(filepath)
                # Ensure index
                if not isinstance(old_df.index, pd.DatetimeIndex):
                    if 'datetime' in old_df.columns:
                        old_df['datetime'] = pd.to_datetime(old_df['datetime'])
                        old_df.set_index('datetime', inplace=True)
                
                print(f"  Merging with existing {len(old_df)} rows...")
                combined = pd.concat([old_df, new_df])
                combined = combined[~combined.index.duplicated(keep='last')] # Keep new data for overlaps
                combined.sort_index(inplace=True)
            except Exception as e:
                print(f"  Merge error: {e}. Overwriting.")
                combined = new_df
        else:
            combined = new_df
            
        # Save
        try:
            data_utils.safe_save_parquet(combined, filepath)
            print(f"  Saved {len(combined)} rows to {filename}")
        except Exception as e:
            print(f"  Save Failed: {e}")
            
        # Rate limit kindness
        time.sleep(0.5)

if __name__ == "__main__":
    update_deep_history()
