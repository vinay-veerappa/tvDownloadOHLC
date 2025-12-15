import os
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import data_utils

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
    "VIX": "^VIX"
}

def update_ticker_intraday(ticker_key, interval="1m"):
    """
    Updates the parquet file for a given ticker with recent intraday data.
    """
    filename = f"{ticker_key}_{interval}.parquet"
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
                 # Try to find a date column if index is not set
                 if 'date' in old_df.columns:
                     old_df['datetime'] = pd.to_datetime(old_df['date']) # Assuming 'date' holds datetime
                     old_df.set_index('datetime', inplace=True)
                 elif 'time' in old_df.columns: # Sometimes 'time'
                      old_df['datetime'] = pd.to_datetime(old_df['time'])
                      old_df.set_index('datetime', inplace=True)
                      
            last_date = old_df.index.max()
            print(f"Existing data end: {last_date}")
            
            # Create Backup before doing anything else
            data_utils.create_backup(filepath)
            
        except Exception as e:
            print(f"Error reading existing file: {e}")
            old_df = pd.DataFrame()
            last_date = None
    else:
        print("No existing file found. Creating new.")
        old_df = pd.DataFrame()
        last_date = None

    # 2. Fetch New Data (Last 5 days is Yahoo limit for 1m)
    print(f"Fetching recent data for {yahoo_ticker}...")
    try:
        # fetch 1m data for last 5 days
        new_df = yf.download(tickers=yahoo_ticker, period="5d", interval=interval, progress=False)
        
        if new_df.empty:
            print("No data fetched.")
            return

        # Flatten MultiIndex columns if present (Yahoo often returns (Price, Ticker))
        if isinstance(new_df.columns, pd.MultiIndex):
            new_df.columns = new_df.columns.get_level_values(0)
            
        # Standardize columns
        new_df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
        }, inplace=True)
        
        # Ensure timezone naive (or match existing). Usually converting to UTC or removing tz is safest for merge.
        if new_df.index.tz is not None:
             new_df.index = new_df.index.tz_localize(None)

        print(f"Fetched {len(new_df)} rows. Range: {new_df.index.min()} to {new_df.index.max()}")

    except Exception as e:
        print(f"Download failed: {e}")
        return

    # 3. Merge
    if not old_df.empty:
        # Combine
        combined = pd.concat([old_df, new_df])
        # Deduplicate by index (datetime)
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
    else:
        combined = new_df

    # 4. Save
    data_utils.safe_save_parquet(combined, filepath)
    print(f"Update complete. New count: {len(combined)} rows.")

def main():
    # Update major indices
    tickets_to_update = ["ES1", "NQ1", "SPX"]
    
    for ticker in tickets_to_update:
        update_ticker_intraday(ticker, "1m")

if __name__ == "__main__":
    main()
