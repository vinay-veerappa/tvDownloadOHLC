import pandas as pd
import argparse
from pathlib import Path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))
import data_utils
import shutil
import numpy as np
from datetime import timedelta

def parse_interval(interval_str):
    if not interval_str: return timedelta(minutes=1)
    unit = interval_str[-1].lower()
    try:
        value = int(interval_str[:-1])
    except:
        return timedelta(minutes=1)
        
    if unit == 'm': return timedelta(minutes=value)
    elif unit == 'h': return timedelta(hours=value)
    elif unit == 'd': return timedelta(days=value)
    elif unit == 'w': return timedelta(weeks=value)
    return timedelta(minutes=value)

def import_ninjatrader_data(csv_path, ticker, interval, align=False, shift_to_open=True, timezone="America/Los_Angeles"):
    print(f"Importing {csv_path} for {ticker} ({interval})...")
    
    # 0. Parse Interval for Shift
    bar_duration = parse_interval(interval)
    print(f"  Bar Duration: {bar_duration} (Shift to Open: {shift_to_open})")
    print(f"  Source Timezone: {timezone}")

    # 1. Detect Delimiter & Headers
    try:
        with open(csv_path, 'r') as f:
            first_line = f.readline()
            delimiter = ',' if ',' in first_line else ';'
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    print(f"  Detected delimiter: '{delimiter}'")
    
    # Check for headers
    has_headers = "Open" in first_line or "Close" in first_line or "Time" in first_line
    
    try:
        if has_headers:
            # Flexible reading with forced column names to handle ragged rows (e.g. 7 cols then 8 cols)
            # We assume standard order: Date, Time, Open, High, Low, Close, Volume, (TickCount/OI)
            # We provide enough names to catch all fields.
            col_names = ['date_str', 'time_str', 'open', 'high', 'low', 'close', 'volume', 'aux1', 'aux2', 'aux3']
            
            # Read with header=0 to skip the file's header, but use OUR names
            df = pd.read_csv(csv_path, sep=delimiter, on_bad_lines='skip', names=col_names, skiprows=1, engine='python', index_col=False)
            
            # Normalize column names (not needed since we set them, but for safety if logic changes)
            df.columns = [c.strip().lower() for c in df.columns]

            # Filter out repeated headers (if file was concatenated)
            if 'date_str' in df.columns:
                 # Check if 'date_str' column contains the word 'Date' or 'date'
                df = df[~df['date_str'].astype(str).str.contains('Date|date', case=False, na=False)].copy()
            
            # Map columns (Already named correctly by our list, but logic below expects them)
            # We just ensure we keep the ones we want
            pass # names are already set

            # Ensure numeric types for OHLCV
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Parse DateTime
            if 'date_str' in df.columns and 'time_str' in df.columns:
                first_date = str(df['date_str'].dropna().iloc[0])
                date_fmt = '%m/%d/%Y' if '/' in first_date else '%Y%m%d'
                
                # Check first time
                first_time = str(df['time_str'].dropna().iloc[0])
                if ':' in first_time:
                     time_fmt = '%H:%M:%S'
                else:
                     time_fmt = '%H%M%S'
                     df['time_str'] = df['time_str'].astype(str).str.zfill(6)
                
                df['datetime'] = pd.to_datetime(df['date_str'].astype(str) + ' ' + df['time_str'].astype(str), format=f"{date_fmt} {time_fmt}")
        else:
             # Basic Fallback
             df = pd.read_csv(csv_path, sep=delimiter, names=['datetime_str', 'open', 'high', 'low', 'close', 'volume'])
             df['datetime'] = pd.to_datetime(df['datetime_str'])

    except Exception as e:
        print(f"❌ Error parsing CSV: {e}")
        return

    # Set Index & Sort
    df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    # 2. Handle Timezone & Shift
    # A. Timezone Conversion (User Local -> America/New_York)
    if df.index.tz is None:
        print(f"  Converting from Local Time ({timezone}) to UTC (Naive)...")
        # 1. Localize to Input TZ
        df.index = df.index.tz_localize(timezone, ambiguous='infer')
        # 2. Convert to UTC
        df.index = df.index.tz_convert('UTC')
        # 3. Make Naive (Strip TZ info, keep UTC time)
        df.index = df.index.tz_localize(None)

    # B. Shift Close-Time to Open-Time
    if shift_to_open:
        print(f"  Shifting timestamps BACK by {bar_duration} (Close Time -> Open Time)")
        df.index = df.index - bar_duration

    df = df[['open', 'high', 'low', 'close', 'volume']]
    
    # 3. Align Prices (Back-Adjustment Fix)
    target_file = f"{ticker}_{interval}.parquet"
    target_path = Path(data_utils.DATA_DIR) / target_file
    
    if align and target_path.exists():
        print("  Checking for Price Alignment...")
        df_old = pd.read_parquet(target_path)
        
        # Find overlap
        common_idx = df.index.intersection(df_old.index)
        
        if len(common_idx) > 10:
            # Use RECENT 100 points for alignment (Prioritize the seam)
            recent_idx = common_idx[-100:] if len(common_idx) > 100 else common_idx
            
            prices_new = df.loc[recent_idx]['close']
            prices_old = df_old.loc[recent_idx]['close']
            diff = prices_old - prices_new
            mean_diff = diff.mean()
            
            print(f"  Found {len(common_idx)} overlapping points.")
            print(f"  Aligning based on last {len(recent_idx)} points.")
            print(f"  Recent Price Difference (Old - New): {mean_diff:.2f}")
            
            if abs(mean_diff) > 1.0:
                print(f"  ⚠️ Applying Offset: Adding {mean_diff:.2f} to Import Data...")
                df += mean_diff # Apply to all columns (O,H,L,C)
                df['volume'] -= mean_diff # Undo volume shift!
            else:
                print("  ✅ Prices align.")
        else:
            print("  ⚠️ No overlap found. Skipping alignment.")

    # 4. Merge
    if target_path.exists():
        print(f"  Merging with existing {target_file}...")
        data_utils.create_backup(str(target_path))
        df_old = pd.read_parquet(target_path)
        
        # Align Timezones safely
        tz_new = df.index.tz
        tz_old = df_old.index.tz
        
        if tz_new != tz_old:
            print(f"  Adjusting Timezone: New({tz_new}) -> Old({tz_old})")
            if tz_new is None:
                # New is Naive, Old is Aware. Assume New is UTC-Naive.
                df.index = df.index.tz_localize('UTC').tz_convert(tz_old)
            elif tz_old is None:
                 # New is Aware, Old is Naive. Convert New to UTC and strip.
                 df.index = df.index.tz_convert('UTC').tz_localize(None)
            else:
                 # Both Aware
                 df.index = df.index.tz_convert(tz_old)

        # Merge: df (History) + df_old (Recent)
        # We want to PRESERVE df_old values where they exist (Trusted Source)
        # So we concat [df, df_old] and keep last? No.
        # We did: concat([df_old, df]) keep='first' -> Old overwrites New.
        # Wait. df (New Import) is History (2008-2025). df_old is Recent (2025).
        # Overlap is 2025.
        # If we align df to df_old, they match.
        # If we concat, we want df_old (Yahoo) to win for the overlap period because it's our daily driver.
        
        df_combined = pd.concat([df_old, df]) 
        # keep='first' -> If index repeats, keep the FIRST occurrence.
        # If we concat [df_old, df], first is df_old. So Yahoo wins. Good.
        df_combined = df_combined[~df_combined.index.duplicated(keep='first')]
        df_combined.sort_index(inplace=True)
        
        print(f"  Merged Total: {len(df_combined)} rows")
        data_utils.safe_save_parquet(df_combined, str(target_path))
        print(f"✅ Imported to {target_file}")
    else:
        print(f"  Creating new file {target_file}...")
        data_utils.safe_save_parquet(df, str(target_path))
        print(f"✅ Created {target_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to NinjaTrader export file")
    parser.add_argument("ticker", help="Ticker")
    parser.add_argument("interval", help="Interval")
    parser.add_argument("--align", action="store_true", help="Auto-align prices")
    parser.add_argument("--no-shift", action="store_true", help="Disable Close->Open time shift")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="Source timezone (default: America/Los_Angeles)")
    args = parser.parse_args()
    
    import_ninjatrader_data(args.file, args.ticker, args.interval, align=args.align, shift_to_open=not args.no_shift, timezone=args.timezone)
