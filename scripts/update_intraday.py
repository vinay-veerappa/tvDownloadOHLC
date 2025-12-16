import os
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import data_utils
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
    "VVIX": "^VVIX"
}

def update_ticker_intraday(ticker_key, interval, period):
    # Map Yahoo interval to App Convention (1wk -> 1W)
    file_interval = interval
    if interval == '1wk':
        # Yahoo requires '1wk', but we save as '1W'
        file_interval = '1W'
    elif interval == '1d':
        file_interval = '1d' # ensure lowercase standard if needed (or 1D)
        
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
                 new_df.index = new_df.index.tz_localize(None)

        print(f"Fetched {len(new_df)} rows. Range: {new_df.index.min()} to {new_df.index.max()}")

    except Exception as e:
        print(f"Download failed: {e}")
        return

    # 3. Merge
    if not old_df.empty:
        combined = pd.concat([old_df, new_df])
        combined = combined[~combined.index.duplicated(keep='last')] # Prefer (latest) Yahoo fetch for overlaps? 
        # Actually logic is confusing. If old_df is local history and new_df is recent.
        # We generally trust the new fetch for the recent period.
        combined.sort_index(inplace=True)
    else:
        combined = new_df

    # 4. Save
    data_utils.safe_save_parquet(combined, filepath)
    print(f"Update complete. New count: {len(combined)} rows.")


def upsample_from_1m(ticker_key):
    """
    Generates 5m, 15m, 1h, 4h files from the 1m master file.
    """
    source_file = os.path.join(data_utils.DATA_DIR, f"{ticker_key}_1m.parquet")
    if not os.path.exists(source_file):
        print(f"Skipping upsample for {ticker_key}: No 1m file found.")
        return

    print(f"\n--- Upsampling {ticker_key} from 1m ---")
    try:
        df_1m = pd.read_parquet(source_file)
        if df_1m.empty: return
            
        targets = [
            ("5m", "5min"),
            ("15m", "15min"),
            ("1h", "1h"),
            ("4h", "4h")
        ]
        
        for interval_name, rule in targets:
            print(f"  > Creating {interval_name}...")
            # OHLCV aggregation
            agg_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            
            resampled = df_1m.resample(rule, label='left', closed='left').agg(agg_dict)
            resampled.dropna(inplace=True)
            
            if not resampled.empty:
                dest_file = os.path.join(data_utils.DATA_DIR, f"{ticker_key}_{interval_name}.parquet")
                data_utils.safe_save_parquet(resampled, dest_file)
                print(f"    Saved {dest_file} ({len(resampled)} rows)")
                
    except Exception as e:
        print(f"Upsample failed for {ticker_key}: {e}")

def main():
    tickets_to_update = TICKER_MAP.keys()
    
    for ticker in tickets_to_update:
        update_ticker_intraday(ticker, "1m", "5d")
        update_ticker_intraday(ticker, "1d", "1mo")
        update_ticker_intraday(ticker, "1wk", "3mo")
        upsample_from_1m(ticker)

if __name__ == "__main__":
    main()
