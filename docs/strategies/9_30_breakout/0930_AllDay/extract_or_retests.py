"""
OR Re-test Extraction Engine (ETL)
==================================
Author: AI Assistant
Date: 2026-01-08

Purpose:
    To extract detailed 'Re-test' events where price returns to the Opening Range (09:30 EST)
    after an initial breakout. Captures depth, timing, and secondary breakout quality.

Architecture:
    1. DataLoader: Handles CSV parsing & Timezone normalization.
    2. ORDetector: Identifies the 09:30 range properties.
    3. RetestEngine: State machine for tracking breakout -> re-test -> secondary breakout.
"""

import pandas as pd
import numpy as np
import glob
import os
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
INPUT_PATTERN = r"data/*_1m.parquet"
OUTPUT_DIR = r"data/derived/retests"
TIMEZONE = "US/Eastern"

class DataLoader:
    """Handles loading of 1-minute OHLC data and timezone standardization."""
    @staticmethod
    def load_data(filepath):
        try:
            # Use read_parquet instead of read_csv
            df = pd.read_parquet(filepath)
            # Standardize columns
            df.columns = [c.lower() for c in df.columns]
            
            # Reset index if it's a DatetimeIndex to make it a column
            # Check if index is datetime
            if isinstance(df.index, pd.DatetimeIndex):
                # Check if 'datetime' or 'time' already exists as column to avoid conflict
                if 'datetime' in df.columns:
                     # Ambiguity case: Index is datetime AND 'datetime' col exists.
                     # Just use the column. Drop index.
                     df = df.reset_index(drop=True)
                else:
                     # Index is datetime, make it a column
                     df = df.reset_index()
                     # Rename index column to 'datetime' if it isn't named or named something else
                     # If index name was None, reset_index creates 'index' col.
                     if 'index' in df.columns and 'datetime' not in df.columns:
                         df.rename(columns={'index': 'datetime'}, inplace=True)
            
            # Now normalize column name to 'datetime'
            if 'time' in df.columns and 'datetime' not in df.columns:
                 df['datetime'] = pd.to_datetime(df['time'])
            
            # Rename whatever came from index if it has a different name
            # Common names: 'date', 'Timestamp', etc.
            # We want 'datetime'
            
            # Last resort check
            if 'datetime' not in df.columns:
                # Try to find a flexible match
                for col in df.columns:
                    if 'date' in col.lower() or 'time' in col.lower():
                        try:
                            df['datetime'] = pd.to_datetime(df[col])
                            break
                        except:
                            continue
            
            df = df.sort_values('datetime').reset_index(drop=True)
            
            # TIMEZONE CONVERSION (UTC -> EST)
            # User confirmed parquet is UTC.
            if df['datetime'].dt.tz is None:
                # If naive, assume UTC
                df['datetime'] = df['datetime'].dt.tz_localize('UTC')
            
            # Convert to US/Eastern
            df['datetime'] = df['datetime'].dt.tz_convert('US/Eastern')
            
            return df
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None

class ORDetector:
    """Identifies the Opening Range (OR) for a specific session."""
    def __init__(self, data_day):
        self.df = data_day
        self.date_str = data_day.iloc[0]['datetime'].strftime('%Y-%m-%d')
        self.or_high = None
        self.or_low = None
        self.or_height = None
        
    def find_or(self):
        # Filter for 09:30 candle
        # Assuming timestamps are 'start of bar' or 'end of bar'? 
        # TV 1m usually '09:30:00'.
        
        # We need to robustly find 09:30 in the datetime column
        mask = (self.df['datetime'].dt.hour == 9) & (self.df['datetime'].dt.minute == 30)
        candle = self.df[mask]
        
        if len(candle) == 0:
            return False
            
        row = candle.iloc[0]
        self.or_high = row['high']
        self.or_low = row['low']
        self.or_height = self.or_high - self.or_low
        return True

class RetestEngine:
    """State machine to detect Breakouts and subsequent Re-tests."""
    def __init__(self, or_high, or_low, data_session):
        self.or_high = or_high
        self.or_low = or_low
        self.or_height = or_high - or_low
        self.data = data_session
        self.events = []
        # Track session extremes for displacement calculation
        self.session_high = or_high
        self.session_low = or_low
        
    def run(self):
        # Prepare arrays for fast access
        # Data is already for the specific day (group)
        # Filter for session time 09:30-16:00
        
        # Ensure sorted
        # self.data is likely sorted but let's be safe if we rely on indexing
        # It was passed from process_file which grouped by date.
        
        times = self.data['datetime'].dt.time
        start_time = pd.Timestamp("09:31").time() # Start AFTER 09:30 candle
        end_time = pd.Timestamp("16:00").time()
        
        # We need 09:31 to 16:00 for the loop
        mask = (times >= start_time) & (times <= end_time)
        session_df = self.data[mask].reset_index(drop=True)
        
        if len(session_df) == 0:
            return {"breakout_detected": False, "retests": []}
            
        # Convert to numpy for speed
        closes = session_df['close'].values
        highs = session_df['high'].values
        lows = session_df['low'].values
        datetimes = session_df['datetime'].dt.strftime('%H:%M').values
        
        # State
        breakout_confirmed = False
        breakout_dir = None
        
        in_retest = False
        current_retest = None
        
        # Iterate using index
        n = len(closes)
        for i in range(n):
            close = closes[i]
            high = highs[i]
            low = lows[i]
            time_str = datetimes[i]
            
            # 1. WAIT FOR BREAKOUT
            if not breakout_confirmed:
                if close > self.or_high:
                    breakout_confirmed = True
                    breakout_dir = 'Bull'
                    self.breakout_time = time_str
                elif close < self.or_low:
                    breakout_confirmed = True
                    breakout_dir = 'Bear'
                    self.breakout_time = time_str
                continue
                
            # 1.5 TRACK MAX DISPLACEMENT
            # Track how far price has moved away from OR since breakout confirmed
            # This is crucial for filtering 'chop' (breakout -> immediate touch without travel)
            current_max_disp = 0.0
            if breakout_confirmed:
                if breakout_dir == 'Bull':
                    self.session_high = max(self.session_high, high)
                    current_max_disp = max(0, self.session_high - self.or_high)
                else:
                    self.session_low = min(self.session_low, low)
                    current_max_disp = max(0, self.or_low - self.session_low)

            # 2. MONITOR FOR RE-TEST
            is_touch = False
            if breakout_dir == 'Bull':
                if low <= self.or_high: is_touch = True
            else: # Bear
                if high >= self.or_low: is_touch = True
                
            if is_touch and not in_retest:
                in_retest = True
                current_retest = {
                    "start_time": time_str,
                    "max_depth_pct_range": 0.0,
                    "time_of_max_depth": time_str,
                    "depth_levels": {"25": None, "50": None, "75": None},
                    "entry_price": self.or_high if breakout_dir == 'Bull' else self.or_low,
                    "lowest_point_in_box": float('inf') if breakout_dir == 'Bull' else float('-inf'),
                    "highest_point_in_box": float('-inf') if breakout_dir == 'Bull' else float('inf'),
                    "exit_time": None,
                    # NEW: Displacement before retest started
                    "pre_retest_fam_points": current_max_disp,
                    "pre_retest_fam_norm": current_max_disp / (self.or_height if self.or_height > 1e-9 else 1.0)
                }
                
            # 3. IN_RETEST LOGIC
            if in_retest:
                or_h = self.or_height if self.or_height > 0 else 1.0
                curr_depth_pct = 0.0
                
                if breakout_dir == 'Bull':
                    dist_into_box = max(0, self.or_high - low)
                    curr_depth_pct = (dist_into_box / or_h) * 100
                    current_retest["lowest_point_in_box"] = min(current_retest["lowest_point_in_box"], low)
                else:
                    dist_into_box = max(0, high - self.or_low)
                    curr_depth_pct = (dist_into_box / or_h) * 100
                    current_retest["highest_point_in_box"] = max(current_retest["highest_point_in_box"], high)
                    
                if curr_depth_pct > current_retest["max_depth_pct_range"]:
                    current_retest["max_depth_pct_range"] = curr_depth_pct
                    current_retest["time_of_max_depth"] = time_str
                    
                if curr_depth_pct >= 25 and not current_retest["depth_levels"]["25"]:
                     current_retest["depth_levels"]["25"] = time_str
                if curr_depth_pct >= 50 and not current_retest["depth_levels"]["50"]:
                     current_retest["depth_levels"]["50"] = time_str
                if curr_depth_pct >= 75 and not current_retest["depth_levels"]["75"]:
                     current_retest["depth_levels"]["75"] = time_str
                     
                # Check Exit/Failure
                has_exited = False
                if breakout_dir == 'Bull' and close > self.or_high: has_exited = True
                elif breakout_dir == 'Bear' and close < self.or_low: has_exited = True
                
                has_failed = False
                if breakout_dir == 'Bull' and close < self.or_low: has_failed = True
                elif breakout_dir == 'Bear' and close > self.or_high: has_failed = True
                
                if has_exited or has_failed:
                    in_retest = False
                    current_retest["exit_time"] = time_str
                    current_retest["is_failure"] = has_failed
                    
                    # MAE/MFE Calculation using Numpy Slicing
                    # Lookahead from current index 'i' to end of 'session_df'
                    
                    mfe_pts = 0.0
                    mae_pts = 0.0
                    
                    if i < n: # Lookahead
                         forward_highs = highs[i:]
                         forward_lows = lows[i:]
                         
                         if breakout_dir == 'Bull':
                             mfe_price = np.max(forward_highs)
                             mfe_pts = max(0, mfe_price - self.or_high)
                             # MAE is how low it went inside the box (relative to entry)
                             # Lowest point is already tracked in current_retest['lowest_point_in_box']
                             mae_pts = (current_retest['lowest_point_in_box'] - self.or_high)
                         else: # Bear
                             mfe_price = np.min(forward_lows)
                             mfe_pts = max(0, self.or_low - mfe_price)
                             # MAE is how high it went (relative to entry)
                             mae_pts = (self.or_low - current_retest['highest_point_in_box'])
                    
                    # Store Points
                    current_retest['excursion_mfe_points'] = mfe_pts
                    current_retest['excursion_mae_points'] = mae_pts
                    
                    # Store Normalized (Time Agnostic)
                    entry_price = float(current_retest['entry_price'])
                    if abs(entry_price) < 1e-9: entry_price = 1.0 # Safety
                    
                    or_h = float(self.or_height) if abs(self.or_height) > 1e-9 else 1.0
                    
                    # 1. Percentage of Price
                    current_retest['excursion_mfe_pct'] = float((mfe_pts / entry_price) * 100)
                    current_retest['excursion_mae_pct'] = float((mae_pts / entry_price) * 100)
                    
                    # 2. Normalized by OR Height (R-multiples of the range)
                    current_retest['excursion_mfe_norm'] = float(mfe_pts / or_h)
                    current_retest['excursion_mae_norm'] = float(mae_pts / or_h)
                    
                    # Ensure all other fields are native types
                    current_retest['entry_price'] = float(current_retest['entry_price'])
                    current_retest['lowest_point_in_box'] = float(current_retest['lowest_point_in_box'])
                    current_retest['highest_point_in_box'] = float(current_retest['highest_point_in_box'])
                    current_retest['pre_retest_fam_points'] = float(current_retest['pre_retest_fam_points'])
                    current_retest['pre_retest_fam_norm'] = float(current_retest['pre_retest_fam_norm'])
                    current_retest['excursion_mfe_points'] = float(current_retest['excursion_mfe_points'])
                    current_retest['excursion_mae_points'] = float(current_retest['excursion_mae_points'])
                    
                    # Retest Index (1-based)
                    current_retest['retest_index'] = int(len(self.events) + 1)
                        
                    self.events.append(current_retest)
                    
        return {
            "breakout_detected": breakout_confirmed,
            "breakout_dir": breakout_dir,
            "breakout_time": self.breakout_time if breakout_confirmed else None,
            "retests": self.events
        }

def process_file(filepath):
    print(f"Processing {filepath}...")
    loader = DataLoader()
    df = loader.load_data(filepath)
    if df is None or len(df) == 0: return
    
    # Get Ticker from filename
    filename = os.path.basename(filepath)
    ticker_guess = filename.split('_')[0] # Usually MNQ1! etc? No, NQ1_1m...
    # The user filenames are "NQ1_1m_continuous.csv"
    ticker = filename.replace('_1m_continuous.csv', '')
    
    # Group by Date
    df['date_only'] = df['datetime'].dt.date
    grouped = df.groupby('date_only')
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outfile = os.path.join(OUTPUT_DIR, f"or_retests_{ticker}.jsonl")
    
    with open(outfile, 'w') as f:
        for date_val, group in grouped:
            ordet = ORDetector(group)
            if ordet.find_or():
                engine = RetestEngine(ordet.or_high, ordet.or_low, group)
                res = engine.run()
                
                if res['breakout_detected']:
                    record = {
                        "date": date_val.strftime('%Y-%m-%d'),
                        "ticker": ticker,
                        "or_high": float(ordet.or_high),
                        "or_low": float(ordet.or_low),
                        "or_height": float(ordet.or_height),
                        "breakout_dir": res['breakout_dir'],
                        "breakout_time": res['breakout_time'],
                        "retests": res['retests']
                    }
                    f.write(json.dumps(record) + "\n")
                    
    print(f"Saved {outfile}")

if __name__ == "__main__":
    files = glob.glob(INPUT_PATTERN)
    for f in files:
        process_file(f)
