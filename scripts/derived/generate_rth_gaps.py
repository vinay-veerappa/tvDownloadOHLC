import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta, time
import argparse
import pytz

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
try:
    from fused_data_loader import load_fused_data
except ImportError:
    # Fallback
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'utils'))
    from fused_data_loader import load_fused_data

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived')
RTH_GAP_FILE = os.path.join(DATA_DIR, 'rth_gaps.json')

# Define RTH Sessions (ET)
# Open: The start of the gap measurement (End of previous RTH)
# Close: The end of the gap measurement (Start of current RTH)
# Wait, Gap = Open_Today - Close_Yesterday
# So we need "RTH Open Time" and "RTH Close Time".

TICKER_CONFIG = {
    # US Indices (Futures) - Liquid RTH typically 09:30 - 16:15
    "NQ1": {"rth_open": time(9, 30), "rth_close": time(16, 15)},
    "ES1": {"rth_open": time(9, 30), "rth_close": time(16, 15)},
    "YM1": {"rth_open": time(9, 30), "rth_close": time(16, 15)},
    "RTY1": {"rth_open": time(9, 30), "rth_close": time(16, 15)},
    
    # Commodities
    # Crude Oil (CL) - Pit Open 09:00 ET, Settlement 14:30 ET
    "CL1": {"rth_open": time(9, 0), "rth_close": time(14, 30)},
    
    # Gold (GC) - Pit Open 08:20 ET, Settlement 13:30 ET
    "GC1": {"rth_open": time(8, 20), "rth_close": time(13, 30)},
}

def calculate_rth_gaps(ticker):
    print(f"[{ticker}] Loading data...")
    df = load_fused_data(ticker, timeframe="1m", require_historical=True)
    
    if df.empty:
        print(f"[{ticker}] No data found.")
        return []

    # Ensure UTC -> ET
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.set_index('datetime', inplace=False)
    
    try:
        df = df.tz_convert('US/Eastern')
    except:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')

    config = TICKER_CONFIG.get(ticker, TICKER_CONFIG["ES1"])
    rth_open_t = config['rth_open']
    rth_close_t = config['rth_close']
    
    print(f"[{ticker}] Using RTH: {rth_open_t} -> {rth_close_t} ET")
    print(f"[{ticker}] Vectorizing gap calculation for {len(df)} rows...")

    # 1. Extract Daily RTH Open (First bar >= rth_open_t)
    # We can use between_time to get the RTH session, then resample '1D'.first()
    # But strictly we want the exact 09:30 bar.
    
    # Set window for open: [rth_open, rth_open + 15m]
    # Set window for close: [rth_close - 15m, rth_close]
    
    # Create time objects for slicing
    t_open_end = (datetime.combine(datetime.today(), rth_open_t) + timedelta(minutes=15)).time()
    t_close_start = (datetime.combine(datetime.today(), rth_close_t) - timedelta(minutes=15)).time()
    
    # Extract Open Candidates
    # Note: between_time is inclusive
    # For open: 09:30 to 09:45
    opens_df = df.between_time(rth_open_t, t_open_end)[['open']].copy()
    
    # Extract Close Candidates
    # For close: 16:00 to 16:15
    closes_df = df.between_time(t_close_start, rth_close_t)[['close']].copy()
    
    # Resample to Daily
    # For Opens, we want the FIRST open in the window
    daily_opens = opens_df.resample('1D').first()
    daily_opens = daily_opens.dropna(inplace=False)
    
    # For Closes, we want the LAST close in the window
    daily_closes = closes_df.resample('1D').last()
    daily_closes = daily_closes.dropna(inplace=False)
    
    # Align: Gap = Today's Open - Yesterday's Close
    # Shift closes forward by 1 day so "Yesterday" aligns with "Today"
    prev_daily_closes = daily_closes.shift(1)
    
    # Merge
    merged = pd.concat([daily_opens, prev_daily_closes], axis=1)
    merged.columns = ['curr_open', 'prev_close']
    merged = merged.dropna(inplace=False)
    
    if merged.empty:
        print(f"[{ticker}] No aligned gaps found.")
        return []
        
    # Calculate Gaps
    merged['gap_size'] = merged['curr_open'] - merged['prev_close']
    merged['gap_direction'] = np.where(merged['gap_size'] > 0, "UP", "DOWN")
    
    # Output formatting
    gaps = []
    
    # Itrerating over the summarized DF (much smaller ~5000 rows) is fast
    for date_idx, row in merged.iterrows():
        # Get exact timestamps? 
        # The resampled index is the DATE (00:00:00).
        # To get exact times, we'd need to preserve them during resample.
        # But for 'gap' report, just the date and prices is usually enough.
        # If we really need exact times, we can do:
        # daily_open_times = opens_df.reset_index().set_index('datetime').resample('1D')['datetime'].first()
        
        gaps.append({
            "date": date_idx.strftime('%Y-%m-%d'),
            "prev_date": (date_idx - timedelta(days=1)).strftime('%Y-%m-%d') if row.name.weekday() != 0 else (date_idx - timedelta(days=3)).strftime('%Y-%m-%d'), 
            # Vectorized approach creates issues here since 'prev_close' was just shifted.
            # But wait, merged index IS 'date_idx'. 
            # The 'prev_close' column CAME from 'daily_closes.shift(1)'. 
            # So its actual date was index - 1 (business day? or calendar day?).
            # Since we did .shift(1) on daily data, it's the previous available row.
            
            # Simple Fix: We don't have the exact prev date easily in this vectorized structure without more join work.
            # However, for analysis we just need to look up the previous trading day in the 1m data.
            # Let's fix analyze_gap_history.py to find previous trading day dynamically instead.
            
            "prev_close_price": float(row['prev_close']),
            "curr_open_price": float(row['curr_open']),
            "gap_size": round(float(row['gap_size']), 4),
            "gap_direction": row['gap_direction']
        })
        
    gaps.sort(key=lambda x: x['date'], reverse=True)
    print(f"[{ticker}] Found {len(gaps)} RTH gaps. (Vectorized)")
    return gaps

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=["NQ1", "ES1", "RTY1", "YM1", "GC1", "CL1"], help="List of tickers")
    args = parser.parse_args()
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # Load existing db if exists
    db = {}
    if os.path.exists(RTH_GAP_FILE):
        try:
            with open(RTH_GAP_FILE, 'r') as f:
                db = json.load(f)
        except:
            db = {}
            
    for ticker in args.tickers:
        config_key = "ES1" if ticker not in TICKER_CONFIG else ticker # Mapping logic if needed
        # Just pass ticker to func, it handles lookup
        
        ticker_gaps = calculate_rth_gaps(ticker)
        db[ticker] = ticker_gaps
        
    with open(RTH_GAP_FILE, 'w') as f:
        json.dump(db, f, indent=2)
        
    print(f"Saved all RTH gaps to {RTH_GAP_FILE}")

if __name__ == "__main__":
    main()