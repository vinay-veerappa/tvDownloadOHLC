import json
import os
import sys
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from schwab.auth import easy_client
from schwab.client import Client
import time

# Ensure we can import data_utils from local dir
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.abspath(os.path.join(current_dir, "../utils"))
sys.path.append(utils_dir)
import data_utils
from data_utils import DATA_DIR

SCHWAB_MAP = {
    "SPX": "$SPX", "VIX": "$VIX", "VVIX": "$VVIX", "NDX": "$NDX", "RUT": "$RUT", "DJI": "$DJI",
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "DIA": "DIA", "GLD": "GLD", "TLT": "TLT",
    "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", "AMD": "AMD", "TSLA": "TSLA", "AMZN": "AMZN",
    "META": "META", "GOOGL": "GOOGL", "PLTR": "PLTR", "JPM": "JPM", "GS": "GS",
    "ES1": "/ES", "NQ1": "/NQ", "RTY1": "/RTY", "YM1": "/YM", "CL1": "/CL", "GC1": "/GC"
}

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

def fetch_data(client, symbol, timeframe, start_dt, end_dt):
    period_type = Client.PriceHistory.PeriodType.MONTH
    freq_type = Client.PriceHistory.FrequencyType.DAILY
    freq = Client.PriceHistory.Frequency.DAILY
    
    if timeframe == '1W':
        period_type = Client.PriceHistory.PeriodType.YEAR
        freq_type = Client.PriceHistory.FrequencyType.WEEKLY
        freq = Client.PriceHistory.Frequency.WEEKLY

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    resp = client.get_price_history(
        symbol, 
        period_type=period_type,
        frequency_type=freq_type,
        frequency=freq,
        start_datetime=start_dt,
        end_datetime=end_dt,
        need_extended_hours_data=True
    )
    
    if resp.status_code != 200:
        print(f"  Error [{resp.status_code}]: {resp.text}")
        return None
        
    data = resp.json()
    candles = data.get('candles', [])
    if not candles:
        return None
        
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    return df

def update_ticker(client, ticker, timeframe):
    schwab_ticker = SCHWAB_MAP.get(ticker)
    filename = f"{ticker}_{timeframe}.parquet"
    filepath = os.path.join(DATA_DIR, filename)
    
    print(f"Updating {filename} via {schwab_ticker}...")
    
    start_dt = datetime(2025, 12, 20, tzinfo=timezone.utc)
    end_dt = datetime.now(timezone.utc)
    existing_df = None
    
    if os.path.exists(filepath):
        existing_df = pd.read_parquet(filepath)
        if not existing_df.empty:
            if existing_df.index.tz is not None:
                existing_df.index = existing_df.index.tz_convert(None)
            last_dt = existing_df.index.max()
            start_dt = last_dt.replace(tzinfo=timezone.utc)
            
    new_df = fetch_data(client, schwab_ticker, timeframe, start_dt, end_dt)
    if new_df is None or new_df.empty:
        print(f"  No new data fetched for {ticker}.")
        return False
        
    if existing_df is not None and not existing_df.empty:
        if new_df.index.tz is not None:
            new_df.index = new_df.index.tz_convert(None)
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
    else:
        combined = new_df
        if combined.index.tz is not None:
            combined.index = combined.index.tz_convert(None)
            
    combined.index.name = 'datetime'
    data_utils.safe_save_parquet(combined, filepath)
    print(f"  Successfully updated {filename} -> rows: {len(combined)}, end: {combined.index.max()}")
    return True

def main():
    client = get_client()
    if not client: return
    
    for ticker in SCHWAB_MAP.keys():
        update_ticker(client, ticker, '1d')
        time.sleep(0.5)
        update_ticker(client, ticker, '1W')
        time.sleep(0.5)
        
    print("\nAll daily and weekly updates completed!")

if __name__ == "__main__":
    main()
