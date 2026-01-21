import pandas as pd
import numpy as np
import pytz
import json
from datetime import time, timedelta
from pathlib import Path

DATA_DIR = Path("c:/Users/vinay/tvDownloadOHLC/data")
NY_TZ = pytz.timezone("America/New_York")

def load_data(ticker: str, tf: str):
    path = DATA_DIR / f"{ticker}_{tf}.parquet"
    if not path.exists():
        print(f"Error: {path} not found.")
        return pd.DataFrame()
    
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df.index = pd.to_datetime(df['time'], unit='s', utc=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
    df = df.tz_convert(NY_TZ)
    df['date'] = df.index.date
    df['time_only'] = df.index.time
    return df

def analyze_ticker(ticker="NQ1"):
    df_1m = load_data(ticker, "1m")
    if df_1m.empty: return []
    df_15m = load_data(ticker, "15m") # More granular for pullbacks/overlap
    if df_15m.empty: return []
    
    target_dates = df_1m[(df_1m['date'] >= pd.to_datetime("2025-10-01").date())]['date'].unique()
    
    results = []
    buffer = 1.0 # 1 point buffer for NQ
    
    for d in target_dates:
        day_1m = df_1m[df_1m['date'] == d]
        day_15m = df_15m[df_15m['date'] == d]
        
        # 09:30 range
        or_bar = day_1m[day_1m['time_only'] == time(9, 30)]
        if or_bar.empty: continue
        or_h, or_l = or_bar.iloc[0]['high'], or_bar.iloc[0]['low']
        
        # Test Window till 15:00
        rth_15m = day_15m[(day_15m['time_only'] >= time(9, 30)) & (day_15m['time_only'] <= time(15, 0))]
        rth_1m = day_1m[(day_1m['time_only'] >= time(9, 30)) & (day_1m['time_only'] <= time(15, 0))]
        
        if rth_1m.empty: continue

        # 1. R1 RULE: 4+ hours test/spend time
        # Group 15m bars into hours (9, 10, 11, 12, 13, 14, 15)
        # We check if any 15m bar in that hour touched the range
        hours_touched = set()
        for _, row in rth_15m.iterrows():
            if row['low'] <= or_h + buffer and row['high'] >= or_l - buffer:
                hours_touched.add(row.name.hour)
        
        # Special case: 9:00 hour always contains the 09:30 bar, but user specifically said "9, 10, 11, 12" for Jan 13
        # In their image, the 9:00 hour (09:00-10:00) is counted.
        
        classification = "UNKNOWN"
        reason = ""
        
        if len(hours_touched) >= 4:
            classification = "R1"
            reason = f"Hours {sorted(list(hours_touched))} touched 09:30 range"
        else:
            # 2. R2 RULE: Return after 11:00
            returns_late = rth_1m[(rth_1m['time_only'] >= time(11, 0)) & (rth_1m['low'] <= or_h) & (rth_1m['high'] >= or_l)]
            if not returns_late.empty:
                classification = "R2"
                reason = "Returned to 09:30 range after 11:00"
            else:
                # 3. TREND RULES (DWP/DNP)
                trending_up = rth_1m['close'].iloc[-1] > or_h
                trending_down = rth_1m['close'].iloc[-1] < or_l
                
                if trending_up or trending_down:
                    # Check for 15m structural pullbacks to be more sensitive
                    pullbacks = 0
                    streak_15m = 0
                    max_streak_15m = 0
                    
                    prev_extreme = None
                    for _, row in rth_15m.iterrows():
                        is_pb = False
                        if trending_up:
                            if prev_extreme is not None and row['low'] < prev_extreme:
                                is_pb = True
                            prev_extreme = row['low']
                        else:
                            if prev_extreme is not None and row['high'] > prev_extreme:
                                is_pb = True
                            prev_extreme = row['high']
                            
                        if is_pb:
                            pullbacks += 1
                            streak_15m = 0
                        else:
                            streak_15m += 1
                            max_streak_15m = max(max_streak_15m, streak_15m)
                    
                    # If Oct 8 is DWP, it must have had 15m pullbacks.
                    # 15m streak of 5 bars = 1.25 hours. 
                    # If the user says "5 hours can not take out", they'd mean a much longer streak.
                    # A 5-hour streak of 15m bars is 20 bars.
                    
                    if pullbacks >= 2: # Require a bit of structural development for DWP
                        classification = "DWP"
                        reason = f"Trend with {pullbacks} (15m) pullbacks"
                    elif max_streak_15m >= 20: # 5 hours = 20 * 15m bars
                        classification = "DNP"
                        reason = f"Power trend, 5hr streak of no pullbacks"
                    elif pullbacks == 0:
                        classification = "DNP"
                        reason = "Pure trend, no pullbacks"
                    else:
                        classification = "DWP" # Minority pullbacks but not zero
                        reason = f"Trend with {pullbacks} pullbacks (weak)"
        
        results.append({
            'date': str(d),
            'classification': classification,
            'reason': reason
        })
        
    return results

if __name__ == "__main__":
    results = analyze_ticker("NQ1")
    
    # Target dates
    target = ["2026-01-05", "2026-01-12", "2026-01-13", "2025-12-23", "2025-10-08"]
    print("\nTARGET VERIFICATION:")
    for r in results:
        if r['date'] in target:
            print(f"{r['date']}: {r['classification']} ({r['reason']})")
            
    # January
    jan = [r for r in results if "-01-" in r['date']]
    print("\nJANUARY REPORT:")
    for r in jan:
        print(f"{r['date']}: {r['classification']} ({r['reason']})")
