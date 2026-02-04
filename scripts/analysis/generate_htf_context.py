
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta

# Configuration
DATA_DIR = r"c:\Users\vinay\tvDownloadOHLC\data"
LIVE_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\live"
OUTPUT_DIR = r"c:\Users\vinay\tvDownloadOHLC\data\derived"
TICKER = "-NQ" # Target ticker for derived data
SOURCE_1D = "NQ1_1d.parquet" # Sourcing from fresh, updated daily file
SOURCE_LIVE = "live_storage_-NQ.parquet" 

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def process_htf():
    print(f"Generating HTF Context for {TICKER}...")
    
    # 1. Load History
    path_1d = os.path.join(DATA_DIR, SOURCE_1D)
    df_hist = pd.DataFrame()
    if os.path.exists(path_1d):
        df_hist = pd.read_parquet(path_1d)
        # Ensure standard columns/index
        if 'time' in df_hist.columns and 'datetime' not in df_hist.columns:
             df_hist['datetime'] = pd.to_datetime(df_hist['time'], unit='s', utc=True)
             df_hist = df_hist.set_index('datetime')
        if df_hist.index.tz is None:
             df_hist.index = df_hist.index.tz_localize('UTC')
        df_hist.index = df_hist.index.tz_convert('US/Eastern')
    
    # 2. Load Live & Resample
    path_live = os.path.join(LIVE_DIR, SOURCE_LIVE)
    df_live_daily = pd.DataFrame()
    if os.path.exists(path_live):
        df_live = pd.read_parquet(path_live)
        if 'time' in df_live.columns:
             # Check magnitude for ms vs s
             first_ts = df_live['time'].iloc[0]
             unit = 'ms' if first_ts > 10000000000 else 's'
             df_live['datetime'] = pd.to_datetime(df_live['time'], unit=unit, utc=True)
        elif 'timestamp' in df_live.columns:
             first_ts = df_live['timestamp'].iloc[0]
             unit = 'ms' if first_ts > 10000000000 else 's'
             df_live['datetime'] = pd.to_datetime(df_live['timestamp'], unit=unit, utc=True)
        
        df_live = df_live.set_index('datetime')
        df_live.index = df_live.index.tz_convert('US/Eastern')
        
        # Resample to Daily (D)
        # Market day ends 17:00 ET? Or 16:00 ET?
        # TradingView usually splits at 17:00 or 18:00.
        # Simple 'D' freq in pandas uses calendar days.
        # For HTF context, calendar days often suffice for Crypto/Futures continuous.
        # Let's resample '1D' taking OHLC logic
        
        df_live_daily = df_live.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
    # 3. Stitch
    # Combine history and live, resolve overlaps (Live overwrites history if same day? Or History overwrites?)
    # Usually history is finalized. Live might be developing.
    # But current history ends Feb 1. Live covers Feb 1, 2, 3, 4.
    # We want valid completed days.
    
    full_daily = pd.concat([df_hist, df_live_daily])
    full_daily = full_daily[~full_daily.index.duplicated(keep='last')] # Keep last (Live) if overlap
    full_daily = full_daily.sort_index()
    
    # 4. Filter Completed Days for Context
    # We exclude "Today" (developing) from Context calculations like "Prev Week".
    # Assume the very last bar is "Today" if it matches current system date?
    # Or just calc indicators on all, and let the calculator decide which index to pick.
    
    # Calculate EMA
    full_daily['ema5'] = calculate_ema(full_daily['close'], 5)
    
    # Get Date Info
    full_daily['year'] = full_daily.index.year
    full_daily['week'] = full_daily.index.isocalendar().week
    full_daily['month'] = full_daily.index.month

    # 5. Extract Contexts
    # A. Yesterday's Stats (for Live EMA calc)
    # We assume the last COMPLETE bar is at index -2 if index -1 is Today.
    # Let's assume the script runs during the day. So the last bar in `full_daily` is "Today".
    # Therefore index -1 is Today (developing), index -2 is Yesterday (finalized).
    
    if len(full_daily) < 2:
        print("Not enough data.")
        return

    yesterday_bar = full_daily.iloc[-2]
    # Verify it's not today?
    # Simple check:
    today_date = datetime.now().date() # Local system date
    # Convert index to date
    # ... logic ...
    
    # For Context, easier to group.
    
    # Previous Week
    # Group by Year-Week
    # Get the last COMPLETED week.
    # Note: isocalendar week splits on Monday.
    # If today is Wed, current week is developing. We want prev week.
    
    last_idx = full_daily.index[-1]
    curr_yr, curr_wk, _ = last_idx.isocalendar()
    
    # This might include today.
    # Filter full_daily to exclude "Today" for context grouping?
    # Safest: Use aggregation then pick the one before current.
    
    weekly_agg = full_daily.resample('W').agg({'high':'max', 'low':'min', 'close':'last'})
    # Last row is current week (developing).
    # Second to last is Previous Full Week.
    prev_week = weekly_agg.iloc[-2]
    
    # Previous Month
    monthly_agg = full_daily.resample('ME').agg({'high':'max', 'low':'min', 'close':'last'}) 
    # 'ME' is Month End. Last row is current month.
    # Second to last is Previous Month.
    prev_month = monthly_agg.iloc[-2]
    
    # Yesterday's EMA
    prev_day = full_daily.iloc[-2]
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "prev_day_ema5": float(prev_day['ema5']),
        "prev_day_close": float(prev_day['close']), # Not strictly needed if we have EMA, but good for debug
        "weekly_profile": {
            "high": float(prev_week['high']),
            "low": float(prev_week['low']),
            "mid": float((prev_week['high'] + prev_week['low']) / 2),
            "close": float(prev_week['close'])
        },
        "monthly_profile": {
            "high": float(prev_month['high']),
            "low": float(prev_month['low']),
            "mid": float((prev_month['high'] + prev_month['low']) / 2),
            "close": float(prev_month['close'])
        }
    }
    
    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"htf_context_{TICKER}.json")
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Saved HTF Context to {out_path}")
    print("Preview:", json.dumps(output, indent=2))

if __name__ == "__main__":
    process_htf()
