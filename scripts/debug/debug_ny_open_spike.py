import pandas as pd
import json
from pathlib import Path

DATA_DIR = Path('data')
TOUCHES_JSON = DATA_DIR / 'NQ1_level_touches.json'
PARQUET_FILE = DATA_DIR / 'NQ1_1m.parquet'

def debug_spike():
    print("Loading JSON...")
    with open(TOUCHES_JSON, 'r') as f:
        touches = json.load(f)
        
    print("Loading Parquet (subset)...")
    # Load full parquet or just query? Fast enough to load full usually.
    # But let's try to be efficient if it's huge. 
    # Just load it, it's fine.
    df = pd.read_parquet(PARQUET_FILE)
    df = pd.read_parquet(PARQUET_FILE)
    print("Columns:", df.columns)
    if 'datetime' in df.columns:
        df.set_index('datetime', inplace=True)
    elif 'time' in df.columns:
        df.set_index('time', inplace=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
         # Try to find a date column
         print("Index is not datetime. Inspect structure.")
         print(df.head())
         return
    spike_days = []
    for date_str, data in touches.items():
        if 'midnight_open' not in data: continue
        entry = data['midnight_open']
        times = entry.get('touch_times', [])
        
        # Check if 08:00 is in the times (or bucket '08:00')
        # Times are buckets or exact? In previous step I made them 5-min buckets.
        # But '08:00' bucket means hit between 08:00:00 and 08:04:59.
        if '08:00' in times:
            spike_days.append(date_str)
            
    print(f"Found {len(spike_days)} days with hit at 08:00.")
    
    # Sample 5 days
    sample_size = 5
    print(f"Sampling {sample_size} days...")
    
    for date_str in spike_days[:sample_size]:
        entry = touches[date_str]['midnight_open']
        level = entry['level']
        
        # Get 08:00 candle
        # format: YYYY-MM-DD
        ts_start = pd.Timestamp(f"{date_str} 08:00:00", tz='US/Eastern')
        # But wait, date_str in JSON might be the "Trading Day" which is ambiguous for 08:00?
        # 08:00 is clearly in the Current Day. 
        # Let's hope date_str matches the calendar date for 08:00.
        
        # Check existence
        if ts_start in df.index:
            row = df.loc[ts_start]
            # print details
            print(f"\nDate: {date_str}")
            print(f"  Level: {level}")
            print(f"  08:00 Candle: Open={row['open']}, High={row['high']}, Low={row['low']}, Close={row['close']}")
            
            # Verify touch
            # Tolerance? Script uses 0.1% or similar.
            # Assuming small tolerance.
            did_touch = row['low'] <= level <= row['high'] # Simple check
            print(f"  Strict Touch Check (Low <= Level <= High): {did_touch}")
            
        else:
            print(f"\nDate: {date_str} - No 08:00 bar found in Parquet?!")

if __name__ == "__main__":
    debug_spike()
