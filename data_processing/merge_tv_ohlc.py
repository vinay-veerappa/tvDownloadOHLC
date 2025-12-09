import pandas as pd
import os
import glob
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TV_OHLC_DIR = os.path.join(DATA_DIR, "TV_OHLC")

# Mapping from filename timeframe to standard timeframe
TIMEFRAME_MAP = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "60": "1h",
    "240": "4h",
    "1D": "1D",
    "1W": "1W",
    "W": "1W"
}

# Mapping from filename ticker to standard ticker
# We can try to deduce this, or hardcode common ones
TICKER_MAP = {
    "CME_MINI_ES1!": "ES1",
    "CME_MINI_NQ1!": "NQ1",
    "CME_MINI_RTY1!": "RTY1",
    "CBOT_MINI_YM1!": "YM1",
    "NYMEX_CL1!": "CL1",
    "COMEX_GC1!": "GC1",
    "SP_SPX": "SPX" # Example
}

def parse_filename(filename):
    # Example: CME_MINI_ES1!, 60_8c471.csv
    # Example: CME_MINI_ES1!, 1W.csv
    # Example: CME_MINI_NQ1!, 60 (1).csv
    
    # Special case for known large backup files
    if "nq-1m" in filename.lower():
        return "NQ1", "1m"
    if "es-1m" in filename.lower():
        return "ES1", "1m"

    # Split by comma
    parts = filename.split(',')
    if len(parts) < 2:
        # Fallback: Try underscore split for format like CL1_1m_...
        # Assume format: TICKER_TIMEFRAME_...
        parts_score = filename.split('_')
        if len(parts_score) >= 2:
             # Check if first part is a known ticker or matches pattern
             candidate_ticker = parts_score[0]
             candidate_tf = parts_score[1]
             
             # Validation
             is_ticker = candidate_ticker in TICKER_MAP.values() or candidate_ticker in ["CL1", "ES1", "NQ1"]
             is_tf = candidate_tf in TIMEFRAME_MAP.values() or candidate_tf in ["1m", "5m", "15m", "1h"]
             
             if is_ticker and is_tf:
                 return candidate_ticker, candidate_tf
        
        return None, None
    
    raw_ticker = parts[0].strip()
    remainder = parts[1].strip()
    
    # Clean remainder
    remainder = remainder.replace('.csv', '')
    remainder = re.sub(r'\s*\(\d+\)', '', remainder) # Remove (1) etc
    
    # Split by underscore (if exists, for hash)
    tf_parts = remainder.split('_')
    raw_tf = tf_parts[0].strip()
    
    ticker = TICKER_MAP.get(raw_ticker)
    if not ticker:
        # Try to clean it: remove exchange prefix, remove !
        # e.g. CME_MINI_ES1! -> ES1
        if "ES1" in raw_ticker: ticker = "ES1"
        elif "NQ1" in raw_ticker: ticker = "NQ1"
        elif "YM1" in raw_ticker: ticker = "YM1"
        elif "RTY1" in raw_ticker: ticker = "RTY1"
        elif "CL1" in raw_ticker: ticker = "CL1"
        elif "GC1" in raw_ticker: ticker = "GC1"
        else:
             # Fallback: take last part after underscore
             subparts = raw_ticker.split('_')
             ticker = subparts[-1].replace('!', '')

    timeframe = TIMEFRAME_MAP.get(raw_tf, raw_tf) # Default to raw if not found
    
    return ticker, timeframe

def get_history_files(ticker, timeframe):
    """Finds history files for a given ticker and timeframe."""
    files = glob.glob(os.path.join(TV_OHLC_DIR, "**", "*.csv"), recursive=True)
    matches = []
    for f in files:
        basename = os.path.basename(f)
        t, tf = parse_filename(basename)
        if t == ticker and tf == timeframe:
            matches.append(f)
    return matches

def merge_history(ticker, timeframe, parquet_path):
    """Merges history CSVs into the parquet file."""
    history_files = get_history_files(ticker, timeframe)
    if not history_files:
        # print(f"No history files found for {ticker} {timeframe}")
        return

    print(f"Merging history for {ticker} {timeframe} ({len(history_files)} files)...")
    
    # 1. Load and combine source CSVs
    dfs = []
    for f in history_files:
        try:
            df = pd.read_csv(f)
            # Normalize columns to lowercase
            df.columns = [c.lower() for c in df.columns]
            
            if 'time' not in df.columns:
                print(f"  Warning: 'time' column missing in {os.path.basename(f)}")
                continue
            dfs.append(df)
        except Exception as e:
            print(f"  Error reading {os.path.basename(f)}: {e}")
    
    if not dfs:
        return
        
    source_df = pd.concat(dfs)
    
    # 2. Standardize Source DF
    # Historical CSVs usually have naive timestamps in UTC or EST
    # We assume UTC if from TradingView unless specified otherwise, but for now let's safely handle them
    source_df['datetime'] = pd.to_datetime(source_df['time'], unit='s', utc=True)
    # Convert to US/Eastern to match project standard
    source_df['datetime'] = source_df['datetime'].dt.tz_convert('US/Eastern')
    
    source_df.set_index('datetime', inplace=True)
    source_df.sort_index(inplace=True)
    source_df = source_df[~source_df.index.duplicated(keep='first')]
    
    if 'volume' not in source_df.columns:
        source_df['volume'] = 0
        
    cols = ['open', 'high', 'low', 'close', 'volume']
    source_df = source_df[cols]
    
    # 3. Load Target Parquet
    target_df = None
    if os.path.exists(parquet_path):
        try:
            target_df = pd.read_parquet(parquet_path)
            # Ensure target is also US/Eastern
            if target_df.index.tz is None:
                 # If mistakenly saved as naive, assume Eastern (or UTC and convert)
                 # Better to assume UTC and convert if unknown, but let's check convert_to_parquet logic
                 target_df.index = target_df.index.tz_localize('UTC').tz_convert('US/Eastern')
            elif str(target_df.index.tz) != 'US/Eastern':
                 target_df.index = target_df.index.tz_convert('US/Eastern')
                 
        except Exception as e:
            print(f"  Error reading existing parquet {parquet_path}: {e}")
    
    # 4. Merge
    if target_df is not None:
        # Filter source to only include timestamps NOT in target
        # Both indices are now US/Eastern
        new_rows = source_df[~source_df.index.isin(target_df.index)]
        if len(new_rows) > 0:
            print(f"  Adding {len(new_rows)} new rows from history.")
            final_df = pd.concat([target_df, new_rows])
            final_df.sort_index(inplace=True)
        else:
            print("  No new history rows to add.")
            final_df = target_df
    else:
        print(f"  Creating new parquet from history ({len(source_df)} rows).")
        final_df = source_df
        
    # 5. Save
    final_df.to_parquet(parquet_path)
    print(f"  Saved {len(final_df)} rows to {parquet_path}")

def merge_all():
    print("Scanning TV_OHLC directory...")
    files = glob.glob(os.path.join(TV_OHLC_DIR, "**", "*.csv"), recursive=True)
    
    # Group files by (ticker, timeframe)
    groups = {}
    for f in files:
        basename = os.path.basename(f)
        ticker, timeframe = parse_filename(basename)
        if not ticker or not timeframe:
            continue
        key = (ticker, timeframe)
        groups[key] = True # Just mark existence
        
    print(f"Found {len(groups)} unique ticker/timeframe combinations.")
    
    for (ticker, timeframe) in groups:
        parquet_path = os.path.join(DATA_DIR, f"{ticker}_{timeframe}.parquet")
        merge_history(ticker, timeframe, parquet_path)

if __name__ == "__main__":
    merge_all()
