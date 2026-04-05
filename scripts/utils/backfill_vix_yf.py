import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Configuration
ET_TZ = ZoneInfo("America/New_York")
DATA_DIR = "data"
VIX_MAP = {
    "VIX": "^VIX",
    "VVIX": "^VVIX"
}

def get_daily_anchor(date_obj):
    """Aligns a date to midnight ET, returned as NAIVE UTC datetime (project standard)."""
    dt_et = datetime.combine(date_obj, datetime.min.time(), tzinfo=ET_TZ)
    # Convert to UTC and then remove TZ info for naive storage
    return dt_et.astimezone(timezone.utc).replace(tzinfo=None)

def backfill_daily(symbol, start_date="2011-01-01"):
    yf_ticker = VIX_MAP.get(symbol)
    if not yf_ticker:
        print(f"No mapping for {symbol}")
        return

    path = os.path.join(DATA_DIR, f"{symbol}_1d.parquet")
    print(f"📊 Processing {symbol} Daily (Source: {yf_ticker})...")

    # Load existing
    existing_df = pd.DataFrame()
    if os.path.exists(path):
        existing_df = pd.read_parquet(path)
        print(f"  Existing rows: {len(existing_df)}. Last date: {existing_df.index[-1]}")

    # Fetch yfinance
    print(f"  Fetching {yf_ticker} from {start_date}...")
    ticker = yf.Ticker(yf_ticker)
    new_data = ticker.history(start=start_date, interval="1d", auto_adjust=False)
    
    if new_data.empty:
        print(f"  No data found for {yf_ticker}")
        return

    # Format yfinance data
    new_data.index = new_data.index.tz_convert(ET_TZ).normalize()
    # Align to project anchor (midnight ET stored as UTC)
    new_data.index = [get_daily_anchor(d.date()) for d in new_data.index]
    new_data.index.name = "datetime"
    
    # Map columns to lowercase
    new_df = new_data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    new_df.columns = [c.lower() for c in new_df.columns]

    # Merge
    if not existing_df.empty:
        # Combine and deduplicate
        combined = pd.concat([existing_df, new_df])
        # Sort by index and take the last occurrence for any duplicates
        combined = combined[~combined.index.duplicated(keep='last')].sort_index()
    else:
        combined = new_df.sort_index()

    combined.to_parquet(path)
    print(f"  ✅ Updated {path}. Total rows: {len(combined)}. New last date: {combined.index[-1]}")

def backfill_minute(symbol):
    yf_ticker = VIX_MAP.get(symbol)
    path = os.path.join(DATA_DIR, f"{symbol}_1m.parquet")
    print(f"⏱️ Processing {symbol} Minute (Source: {yf_ticker})...")

    # Load existing
    existing_df = pd.DataFrame()
    if os.path.exists(path):
        existing_df = pd.read_parquet(path)
        print(f"  Existing rows: {len(existing_df)}. Last date: {existing_df.index[-1]}")

    # Yahoo 1m data is limited to last 30 days, in 7-day chunks
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=29)
    
    all_new_minutes = []
    
    # Iterate in 7-day chunks
    current_start = start_dt
    while current_start < end_dt:
        current_end = min(current_start + timedelta(days=7), end_dt)
        print(f"  Fetching 1m chunk: {current_start.date()} to {current_end.date()}...")
        try:
            ticker = yf.Ticker(yf_ticker)
            chunk = ticker.history(start=current_start, end=current_end, interval="1m", auto_adjust=False)
            if not chunk.empty:
                all_new_minutes.append(chunk)
            # Sleep slightly to avoid rate limiting
            import time
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ Chunk error: {e}")
        
        current_start = current_end

    if not all_new_minutes:
        print(f"  No new 1m data found for {yf_ticker}")
        return

    new_data = pd.concat(all_new_minutes)
    
    # Format yf 1m data
    new_data.index = new_data.index.tz_convert(timezone.utc).tz_localize(None)
    new_data.index.name = "datetime"
    
    new_df = new_data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    new_df.columns = [c.lower() for c in new_df.columns]
    
    # Merge
    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep='last')].sort_index()
    else:
        combined = new_df.sort_index()

    combined.to_parquet(path)
    print(f"  ✅ Updated {path}. Total rows: {len(combined)}. New last date: {combined.index[-1]}")

if __name__ == "__main__":
    for sym in ["VIX", "VVIX"]:
        backfill_daily(sym, start_date="2011-01-01")
