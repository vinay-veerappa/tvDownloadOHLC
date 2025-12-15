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
    "VIX": "^VIX",
    "QQQ": "QQQ",
    "VVIX": "^VVIX"
}

    # Map Yahoo interval to App Convention (1wk -> 1W)
    file_interval = interval
    if interval == '1wk':
        file_interval = '1W'
        
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

    # 2. Fetch New Data
    print(f"Fetching recent data for {yahoo_ticker} (Period: {period})...")
    try:
        new_df = yf.download(tickers=yahoo_ticker, period=period, interval=interval, progress=False)
        
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
        
        # Timezone Alignment
        # The existing file usually has a timezone (e.g. America/New_York or UTC)
        # We must align new data to match old data's timezone before concat.
        
        target_tz = None
        if not old_df.empty and isinstance(old_df.index, pd.DatetimeIndex):
            target_tz = old_df.index.tz
            
        if target_tz is not None:
             # Convert new data to match existing file's timezone
             if new_df.index.tz is None:
                 # Assume fetched data is UTC if naive (unlikely with yfinance, usually returns localized)
                 new_df.index = new_df.index.tz_localize("UTC").tz_convert(target_tz)
             else:
                 new_df.index = new_df.index.tz_convert(target_tz)
        else:
            # If old data is naive, strip timezone from new data
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
        if df_1m.empty:
            return
            
        # Define Targets
        targets = [
            ("5m", "5min"),
            ("15m", "15min"),
            ("1h", "1h"),
            ("4h", "4h")
        ]
        
        for interval_name, rule in targets:
            print(f"  > Creating {interval_name}...")
            # Resample
            # Standard OHLCV aggregation
            agg_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            
            # Pandas resample. 
            # TradingView/Yahoo typically label with start time (left).
            resampled = df_1m.resample(rule, label='left', closed='left').agg(agg_dict)
            
            # Drop NaN rows (e.g. gaps)
            resampled.dropna(inplace=True)
            
            if not resampled.empty:
                dest_file = os.path.join(data_utils.DATA_DIR, f"{ticker_key}_{interval_name}.parquet")
                data_utils.safe_save_parquet(resampled, dest_file)
                print(f"    Saved {dest_file} ({len(resampled)} rows)")
                
    except Exception as e:
        print(f"Upsample failed for {ticker_key}: {e}")

def main():
    # Update all mapped tickers
    tickets_to_update = TICKER_MAP.keys()
    
    for ticker in tickets_to_update:
        # 1. Intraday 1m (Last 5 days) + Direct Downloads
        update_ticker_intraday(ticker, "1m", "5d")
        
        # 2. Daily 1D (Last 1 month) - Direct for Settlement
        update_ticker_intraday(ticker, "1d", "1mo")
        
        # 3. Weekly 1W (Last 3 months) - Direct for Settlement
        # Yahoo interval is '1wk'
        update_ticker_intraday(ticker, "1wk", "3mo")
        
        # 4. Upsample Intermediate Timeframes (5m, 15m, 1h, 4h)
        upsample_from_1m(ticker)

if __name__ == "__main__":
    main()
