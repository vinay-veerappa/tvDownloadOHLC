import os
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from scripts.utils import data_utils
import numpy as np

# Configuration
# Map custom ticker names to Yahoo Finance tickers
TICKER_MAP = {
    "ES1": "ES=F",
    "NQ1": "NQ=F",
    "RTY1": "RTY=F",
    "YM1": "YM=F",
    "GC1": "GC=F",
    "CL1": "CL=F",
    "SPX": "^GSPC",
    "VIX": "^VIX",
    "QQQ": "QQQ",
    "VVIX": "^VVIX",
    # ETFs
    "SPY": "SPY", "IWM": "IWM", "DIA": "DIA", "TLT": "TLT", "GLD": "GLD", "SLV": "SLV", "USO": "USO", "UNG": "UNG",
    # Tech
    "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", "AMZN": "AMZN", "GOOGL": "GOOGL", "META": "META", "TSLA": "TSLA", "AMD": "AMD",
    # AI/Data
    "PLTR": "PLTR", "MU": "MU", "SMCI": "SMCI", "ARM": "ARM", "VRT": "VRT", "DELL": "DELL", "ORCL": "ORCL",
    "CRWD": "CRWD", "NBIS": "NBIS", "ANET": "ANET", "PSTG": "PSTG", "WDC": "WDC", "SOUN": "SOUN", "AI": "AI",
    # Banks
    "JPM": "JPM", "GS": "GS", "MS": "MS", "BAC": "BAC", "C": "C",
    # High Beta
    "NFLX": "NFLX", "COIN": "COIN", "MSTR": "MSTR", "AVGO": "AVGO"
}

def update_ticker_intraday(ticker_key, interval, period):
    # Map Yahoo interval to App Convention (1wk -> 1W)
    file_interval = interval
    if interval == '1wk':
        file_interval = '1W'
    elif interval == '1d':
        file_interval = '1D' # 1d -> 1D standard
    elif interval == '5m': file_interval = "5m"
    elif interval == '15m': file_interval = "15m"
    elif interval == '1h': file_interval = "1H" # 1h -> 1H
        
    filename = f"{ticker_key}_{file_interval}.parquet"
    filepath = os.path.join(data_utils.DATA_DIR, filename)
    yahoo_ticker = TICKER_MAP.get(ticker_key)
    
    if not yahoo_ticker:
        print(f"Skipping {ticker_key}: No Yahoo mapping found.")
        return

    print(f"\n--- Updating {ticker_key} ({interval}) ---")
    
    # 1. Load Existing Data
    if os.path.exists(filepath):
        try:
            old_df = pd.read_parquet(filepath)
            # Ensure index is Datetime
            if not isinstance(old_df.index, pd.DatetimeIndex):
                 if 'date' in old_df.columns:
                     old_df['datetime'] = pd.to_datetime(old_df['date'])
                     old_df.set_index('datetime', inplace=True)
                 elif 'time' in old_df.columns:
                      old_df['datetime'] = pd.to_datetime(old_df['time'])
                      old_df.set_index('datetime', inplace=True)
                      
            last_date = old_df.index.max()
            print(f"Existing data end: {last_date}")
            
            data_utils.create_backup(filepath)
            
        except Exception as e:
            print(f"Error reading existing file: {e}")
            old_df = pd.DataFrame()
    else:
        print("No existing file found. Creating new.")
        old_df = pd.DataFrame()

    # 2. Fetch New Data
    print(f"Fetching recent data for {yahoo_ticker} (Period: {period})...")
    try:
        new_df = yf.download(tickers=yahoo_ticker, period=period, interval=interval, progress=False)
        
        if new_df.empty:
            print("No data fetched.")
            return

        # Flatten MultiIndex columns if present
        if isinstance(new_df.columns, pd.MultiIndex):
            new_df.columns = new_df.columns.get_level_values(0)
            
        new_df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
        }, inplace=True)
        
        # Timezone Alignment
        # Yahoo often returns UTC or Market Time.
        # Prefer UTC normalization if possible, or keep local.
        target_tz = None
        if not old_df.empty and isinstance(old_df.index, pd.DatetimeIndex):
            target_tz = old_df.index.tz
            
        if target_tz is not None:
             if new_df.index.tz is None:
                 new_df.index = new_df.index.tz_localize("UTC").tz_convert(target_tz)
             else:
                 new_df.index = new_df.index.tz_convert(target_tz)
        else:
            if new_df.index.tz is not None:
                 # If old data had no TZ, but new does?
                 # Keep new TZ.
                 pass
            # If no TZ in new, assume it matches old? 
            # Ideally verify.

        print(f"Fetched {len(new_df)} rows. Range: {new_df.index.min()} to {new_df.index.max()}")

    except Exception as e:
        print(f"Download failed: {e}")
        return

    # 3. Merge
    if not old_df.empty:
        # Concatenate and drop duplicates by index
        combined = pd.concat([old_df, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
    else:
        combined = new_df

    # 4. Save
    data_utils.safe_save_parquet(combined, filepath)
    print(f"Update complete. New count: {len(combined)} rows.")


def upsample_from_1m(ticker_key):
    # Disabled in favor of Direct Fetch for better history
    pass

def main():
    tickets_to_update = TICKER_MAP.keys()
    
    for ticker in tickets_to_update:
        # 1m (5 days max)
        update_ticker_intraday(ticker, "1m", "5d")
        
        # 5m (60 days max)
        update_ticker_intraday(ticker, "5m", "60d")
        
        # 15m (60 days max)
        update_ticker_intraday(ticker, "15m", "60d")
        
        # 1h (730 days max ~ 2 years)
        update_ticker_intraday(ticker, "1h", "730d")
        
        # Daily (Max history)
        update_ticker_intraday(ticker, "1d", "5y")
        
        # Weekly
        update_ticker_intraday(ticker, "1wk", "5y")

if __name__ == "__main__":
    main()
