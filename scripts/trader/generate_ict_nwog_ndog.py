import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
import argparse
import pytz

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
from fused_data_loader import load_fused_data

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'derived')
GAP_FILE = os.path.join(DATA_DIR, 'ict_nwog_ndog.json')

def get_market_gaps(ticker, lookback_days=365):
    print(f"Loading data for {ticker}...")
    df = load_fused_data(ticker, timeframe="1m", require_historical=True)
    
    if df.empty:
        print(f"No data for {ticker}")
        return []

    # Ensure UTC -> ET
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df.set_index('datetime', inplace=True)
    
    try:
        df = df.tz_convert('US/Eastern')
    except:
        df = df.tz_localize('UTC').tz_convert('US/Eastern')

    # Filter for lookback
    start_date = pd.Timestamp.now(tz='US/Eastern') - timedelta(days=lookback_days)
    df = df[df.index >= start_date]

    gaps = {
        "NWOG": [],
        "NDOG": []
    }

    # Algorithm: Find gaps > 45 minutes
    # We look for the specific 17:00 ET Close -> 18:00 ET Open signature
    # Identify timestamps where the gap to the next bar is > 45 minutes
    
    df['time_diff'] = df.index.to_series().diff().shift(-1)
    
    # Filter for significant gaps (> 45 min)
    # 45 min = 2700 seconds
    gap_indices = df[df['time_diff'] > pd.Timedelta(minutes=45)].index

    print(f"Found {len(gap_indices)} potential gaps...")

    for timestamp in gap_indices:
        # candle BEFORE the gap
        close_candle = df.loc[timestamp]
        
        # candle AFTER the gap (get the next available index)
        # using searchsorted to find the next index position
        next_idx_pos = df.index.get_indexer([timestamp], method='bfill')[0] + 1
        
        if next_idx_pos >= len(df):
            continue
            
        open_candle_time = df.index[next_idx_pos]
        open_candle = df.iloc[next_idx_pos]
        
        # Robust Logic: Anchor on the SESSION OPEN (18:00 ET)
        # Verify it is indeed an 18:00 Open (standard futures session start)
        # Allowing slight variance (e.g., 17:59 or 18:01)
        if open_candle_time.hour != 18:
            continue
            
        is_nwog = False
        is_ndog = False
        
        # NWOG: Session Open is Sunday (6) or Monday (0) - but only if the gap is LONG (Weekend)
        # OR simple check: Did the previous candle close on Friday?
        if timestamp.weekday() == 4: # Close was Friday
            is_nwog = True
        
        # NDOG: Close was Mon-Thu
        elif timestamp.weekday() in [0, 1, 2, 3]:
            is_ndog = True
        
        if is_nwog:
            gap_type = "NWOG"
            session_date = open_candle_time.strftime('%Y-%m-%d')
        elif is_ndog:
            gap_type = "NDOG"
            session_date = open_candle_time.strftime('%Y-%m-%d')
        else:
            continue
            
        # Calculate Gap
        gap_high = max(close_candle['close'], open_candle['open'])
        gap_low = min(close_candle['close'], open_candle['open'])
        
        gap_entry = {
            "session_date": session_date,
            "close_time": timestamp.isoformat(),
            "open_time": open_candle_time.isoformat(),
            "close_price": float(close_candle['close']),
            "open_price": float(open_candle['open']),
            "high": float(gap_high),
            "low": float(gap_low),
            "gap_size": float(gap_high - gap_low)
        }
        
        gaps[gap_type].append(gap_entry)

    # Sort DESC (newest first)
    gaps["NWOG"].sort(key=lambda x: x['open_time'], reverse=True)
    gaps["NDOG"].sort(key=lambda x: x['open_time'], reverse=True)
    
    return gaps

def update_gap_file(new_data, ticker):
    if os.path.exists(GAP_FILE):
        with open(GAP_FILE, 'r') as f:
            try:
                db = json.load(f)
            except:
                db = {}
    else:
        db = {}
    
    # Check if "version" exists, if not struct might be different? 
    # Current struct: { "NQ1": { "NWOG": [], "NDOG": [] } }
    
    db[ticker] = new_data
    
    with open(GAP_FILE, 'w') as f:
        json.dump(db, f, indent=2)
    print(f"Saved gaps for {ticker} to {GAP_FILE}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=["NQ1", "ES1"], help="List of tickers")
    parser.add_argument("--lookback", type=int, default=365, help="Days to look back")
    args = parser.parse_args()
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    for ticker in args.tickers:
        gaps = get_market_gaps(ticker, args.lookback)
        update_gap_file(gaps, ticker)
        
        print(f"[{ticker}] Found {len(gaps['NWOG'])} NWOGs and {len(gaps['NDOG'])} NDOGs.")

if __name__ == "__main__":
    main()
