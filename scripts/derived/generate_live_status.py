
import json
import logging
import os
import pytz
from datetime import datetime, time, timedelta
import pandas as pd
from pathlib import Path

# --- Configuration ---
DATA_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\data")
LIVE_DATA_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\data\live")
LOG_DIR = Path(r"c:\Users\vinay\tvDownloadOHLC\logs")

# Session Config (EST)
# Windows in minutes from 18:00 (0m)
# 18:00 = 0m, 00:00 = 360m, 02:30 = 510m, 07:30 = 810m, 11:30 = 1050m, 17:00 = 1380m
SESSIONS = {
    "Asia": {
        "ref_start": 0, "ref_end": 90,   # 18:00 - 19:29
        "stat_start": 90, "stat_end": 510, # 19:30 - 02:29
        "bk_start": 510, "bk_end": 1380    # 02:30 - 17:00
    },
    "London": {
        "ref_start": 510, "ref_end": 570,   # 02:30 - 03:29
        "stat_start": 570, "stat_end": 810, # 03:30 - 07:29
        "bk_start": 810, "bk_end": 1380     # 07:30 - 17:00
    },
    "NY1": {
        "ref_start": 810, "ref_end": 870,   # 07:30 - 08:29
        "stat_start": 870, "stat_end": 1050, # 08:30 - 11:29
        "bk_start": 1050, "bk_end": 1380    # 11:30 - 17:00
    },
    "NY2": {
        "ref_start": 1050, "ref_end": 1110,  # 11:30 - 12:29
        "stat_start": 1110, "stat_end": 1380, # 12:30 - 16:59
        "bk_start": 0, "bk_end": 1380        # 12:30 - 17:00 (Aligned with Status)
    }
}

# Values for status codes
MODE_MAP = {0: "Neutral", 1: "Long True", 2: "Long False", 3: "Short True", 4: "Short False"}

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calc_status(df, ref_start_m, ref_end_m, stat_start_m, stat_end_m):
    # Filter for Ref Window
    ref_mask = (df['minutes'] >= ref_start_m) & (df['minutes'] < ref_end_m)
    stat_mask = (df['minutes'] >= stat_start_m) & (df['minutes'] < stat_end_m)
    
    ref_bars = df[ref_mask]
    if ref_bars.empty:
        return 0, 0, 0 # No ref data
        
    ref_h = ref_bars['high'].max()
    ref_l = ref_bars['low'].min()
    
    stat_bars = df[stat_mask]
    
    mode = 0
    # Iterate status bars to find breaks
    for index, row in stat_bars.iterrows():
        h, l = row['high'], row['low']
        b_h = h > ref_h
        b_l = l < ref_l
        
        if mode == 0:
            if b_h and not b_l: mode = 1
            elif b_l and not b_h: mode = 3
            elif b_h and b_l: mode = 2
        elif mode == 1 and b_l:
            mode = 2
        elif mode == 3 and b_h:
            mode = 4
            
    return mode, ref_h, ref_l

def calc_broken(df, win_start_m, win_end_m, ref_h, ref_l, current_day_start):
    if ref_h == 0 or ref_l == 0: return False
    mid = (ref_h + ref_l) / 2
    
    # Calculate absolute window for this cycle
    start_dt = current_day_start + timedelta(minutes=win_start_m)
    end_dt = current_day_start + timedelta(minutes=win_end_m)
    
    mask = (df['datetime'] >= start_dt) & (df['datetime'] < end_dt)
    win_bars = df[mask]
    
    if win_bars.empty: return False
    
    # Check if any bar crosses the mid
    for _, row in win_bars.iterrows():
        if row['low'] <= mid and row['high'] >= mid:
            return True
    return False

def process_ticker(ticker):
    # 1. Load Data (Live Parquet Priority)
    safe_ticker = ticker.replace("1", "").replace("/", "") 
    
    # Check Live Storage first with various patterns
    pq_patterns = [
        LIVE_DATA_DIR / f"live_storage_-{safe_ticker}.parquet",
        LIVE_DATA_DIR / f"live_storage_-{ticker}.parquet",
        LIVE_DATA_DIR / f"live_storage_{ticker}.parquet",
        LIVE_DATA_DIR / f"live_storage_{safe_ticker}.parquet"
    ]
    
    pq_path = None
    for p in pq_patterns:
        if p.exists():
            pq_path = p
            break
        
    if not pq_path:
        logging.warning(f"No data found for {ticker}")
        return

    try:
        df = pd.read_parquet(pq_path, columns=['time', 'high', 'low'])
        df = df.sort_values('time').drop_duplicates('time')
        if len(df) > 5000:
            df = df.iloc[-5000:].copy()
    except Exception as e:
        logging.error(f"Failed to read parquet for {ticker}: {e}")
        return

    # 2. Preprocess Time
    try:
        first_time = df['time'].iloc[0]
        if first_time > 1e11: # Assume ms
            df['datetime'] = pd.to_datetime(df['time'], unit='ms', utc=True).dt.tz_convert('America/New_York')
        else: # Assume s
            df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('America/New_York')
    except Exception as e:
        logging.warning(f"Time conversion failed: {e}")
        df['datetime'] = pd.to_datetime(df['time'], utc=True).dt.tz_convert('America/New_York')

    df['minutes'] = (df['datetime'].dt.hour * 60 + df['datetime'].dt.minute - 1080 + 1440) % 1440
    
    # 3. Determine Current Status
    last_ts = df['datetime'].max()
    
    # current_day_start is the most recent 18:00
    current_day_start = last_ts.replace(hour=18, minute=0, second=0, microsecond=0)
    if last_ts < current_day_start:
        current_day_start = current_day_start - timedelta(days=1)
        
    df_today = df[df['datetime'] >= current_day_start].copy()
    
    status_map = {}
    today_ny = datetime.now(pytz.timezone('America/New_York'))
    # Calculate minutes from 18:00 yesterday (or today if < 18:00? No, 18:00 is start of day)
    # If today_ny is 14:00 (2pm), start was Yesterday 18:00.
    # Logic: If hour < 18, Current Day started Yesterday. If hour >= 18, Current Day started Today.
    if today_ny.hour >= 18:
        cycle_start = today_ny.replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        cycle_start = (today_ny - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        
    delta = today_ny - cycle_start
    last_min = int(delta.total_seconds() / 60)
    
    logging.info(f"Analysis Time (EST): {today_ny} | Minutes from 18:00: {last_min}")

    status_map = {}
    # last_min is now WALL CLOCK EST min, identifying true cycle time.

    for s_name, config in SESSIONS.items():
        key = s_name.lower()
        # Status Confirmation Logic:
        # Active Session:
        # - FALSE (2, 4) is Confirmed Immediately (Irreversible)
        # - TRUE (1, 3) is Pending (Reversible)
        # - Neutral (0) is Pending
        
        mode, ref_h, ref_l = calc_status(df_today, config['ref_start'], config['ref_end'], config['stat_start'], config['stat_end'])
        
        raw_status = MODE_MAP[mode]
        final_status = raw_status
        is_pending_logic = False
        
        # Check if session is still active
        if last_min < config['stat_end'] and last_min != -1:
             # Only confirm FALSE statuses (2=LF, 4=SF). Everything else is Pending.
             # Only confirm FALSE statuses (2=LF, 4=SF). Everything else is Pending.
             if mode not in [2, 4]:
                 if mode == 1: # LT
                     final_status = "Long (Pending)"
                 elif mode == 3: # ST
                     final_status = "Short (Pending)"
                 else:
                     final_status = "Pending"
                 is_pending_logic = True

        # Broken check now uses current_day_start to be cycle-aware
        broken = False
        if mode != 0:
            # If NY2, Broken Window is Next Cycle -> Cannot be broken today
            if s_name == "NY2":
                broken = False
            # If session logic is still pending (status window open), we don't track loose breaks
            elif is_pending_logic: 
                broken = False
            # Otherwise check normally
            else:
                 broken = calc_broken(df, config['bk_start'], config['bk_end'], ref_h, ref_l, current_day_start)
            
        # User Requirement: Broken status can ONLY be confirmed after session ends (or rather, window ends?)
        # Actually, if it breaks, it IS broken. But if it hasn't broken yet, it MIGHT break later.
        # So we report what we see (True/False) but add a flag "broken_final" logic.
        
        # Calculate if Broken Window is closed
        broken_final = last_min >= config['bk_end'] or last_min == -1 # -1 implies data missing/old? No, fallback to safe or false? 
        # If -1, we assume data is complete? No. 
        # If -1, assume finalized (historical/closed)? 
        # Actually last_min calculated from EST. -1 is unlikely unless error.
        
        status_map[key] = {
            'status': final_status, 
            'broken': broken,
            'broken_final': broken_final,
            'developing': raw_status if is_pending_logic else None
        }

    # Write Result
    output = {
        "ticker": ticker,
        "timestamp": int(datetime.utcnow().timestamp()),
        "asia": status_map.get('asia', {'status': 'Pending', 'broken': False, 'broken_final': False}),
        "london": status_map.get('london', {'status': 'Pending', 'broken': False, 'broken_final': False}),
        "ny1": status_map.get('ny1', {'status': 'Pending', 'broken': False, 'broken_final': False}),
        "ny2": status_map.get('ny2', {'status': 'Pending', 'broken': False, 'broken_final': False})
    }
    
    out_path = DATA_DIR / f"{ticker}_live_status.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    logging.info(f"Updated live status for {ticker} at {out_path}")

if __name__ == "__main__":
    setup_logging()
    process_ticker("NQ1")
