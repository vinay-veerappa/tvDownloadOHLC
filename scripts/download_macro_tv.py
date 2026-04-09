import pandas as pd
from tvDatafeed import TvDatafeed, Interval
import os
import time
from datetime import datetime

# Configuration
BASE_DIR = r"c:\Users\vinay\tvDownloadOHLC"
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "macro_records.parquet")

TICKERS = {
    'NQ1': {'symbol': 'NQ1!', 'exchange': 'CME_MINI'},
    'ES1': {'symbol': 'ES1!', 'exchange': 'CME_MINI'},
    'YM1': {'symbol': 'YM1!', 'exchange': 'CBOT_MINI'},
    'RTY1': {'symbol': 'RTY1!', 'exchange': 'CME_MINI'},
    'GC1': {'symbol': 'GC1!', 'exchange': 'COMEX'},
    'CL1': {'symbol': 'CL1!', 'exchange': 'NYMEX'}
}

def get_last_date(ticker):
    path = os.path.join(DATA_DIR, f"{ticker}_1m.parquet")
    if os.path.exists(path):
        df = pd.read_parquet(path)
        return df.index.max()
    return None

def download_data(tv, symbol, exchange, interval, n_bars=10000):
    print(f"Downloading {symbol} from {exchange} ({interval})...")
    try:
        df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=n_bars)
        return df
    except Exception as e:
        print(f"Error downloading {symbol}: {e}")
        return None

def main():
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    tv = TvDatafeed()
    
    all_records = []
    
    for alias, info in TICKERS.items():
        last_date = get_last_date(alias)
        print(f"Ticker: {alias}, Last Local Date: {last_date}")
        
        # 1. Fetch 1m data (Last 10000 bars is roughly 1 week of market time, but we need more if gap is large)
        # For this demo/task, we fetch a significant chunk
        df_1m = download_data(tv, info['symbol'], info['exchange'], Interval.in_1_minute, n_bars=10000)
        
        if df_1m is not None:
            df_1m['ticker'] = alias
            df_1m['timeframe'] = '1m'
            df_1m = df_1m.reset_index()
            all_records.append(df_1m)
            
        # 2. Fetch 1d data
        df_1d = download_data(tv, info['symbol'], info['exchange'], Interval.in_daily, n_bars=500)
        if df_1d is not None:
            df_1d['ticker'] = alias
            df_1d['timeframe'] = '1d'
            df_1d = df_1d.reset_index()
            all_records.append(df_1d)
            
        time.sleep(1) # Simple rate limit avoid
        
    if all_records:
        df_final = pd.concat(all_records)
        # Ensure common columns
        cols = ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'ticker', 'timeframe']
        # Note: tvdatafeed might return 'symbol' or we added 'ticker'
        df_final = df_final.rename(columns={'index': 'datetime'}) # If index wasn't reset properly
        
        # Add trading_date (Date only)
        df_final['trading_date'] = pd.to_datetime(df_final['datetime']).dt.date
        
        print(f"Consolidating {len(df_final)} records to {OUTPUT_FILE}...")
        df_final.to_parquet(OUTPUT_FILE, index=False)
        print("Sprint 1 Complete: macro_records.parquet created.")
    else:
        print("No data downloaded. Verify connection/tickers.")

if __name__ == "__main__":
    main()
