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
    if not path.exists(): return pd.DataFrame()
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
    df_15m = load_data(ticker, "15m")
    if df_1m.empty or df_15m.empty: return []
    
    target_dates = df_1m[(df_1m['date'] >= pd.to_datetime("2026-01-01").date())]['date'].unique()
    
    results = []
    buffer = 1.0 
    
    for d in target_dates:
        m = df_1m[df_1m['date'] == d]
        h15 = df_15m[df_15m['date'] == d]
        
        or_match = m[m['time_only'] == time(9, 30)]
        if or_match.empty:
            continue
        or_bar = or_match.iloc[0]
        or_h, or_l = or_bar['high'], or_bar['low']
        
        rth_15m = h15[(h15['time_only'] >= time(9, 30)) & (h15['time_only'] <= time(15, 0))]
        rth_1m = m[(m['time_only'] >= time(9, 30)) & (m['time_only'] <= time(15, 0))]
        
        # Calculate R1 Hours
        hours_touched = set()
        for t, row in rth_15m.iterrows():
            if row['low'] <= or_h + buffer and row['high'] >= or_l - buffer:
                hours_touched.add(t.hour)
        
        # Calculate R2 Return (after 11:00)
        late_1m = m[(m['time_only'] >= time(11, 0)) & (m['time_only'] <= time(15, 0))]
        returns_late = late_1m[(late_1m['low'] <= or_h) & (late_1m['high'] >= or_l)]
        
        # Check if price moved away significantly before return
        early_body = m[(m['time_only'] > time(9, 31)) & (m['time_only'] < time(11, 0))]
        moved_away = not early_body[(early_body['low'] > or_h + 10) | (early_body['high'] < or_l - 10)].empty
        
        classification = "UNKNOWN"
        reason = ""
        
        # PRECEDENCE:
        # If it returns late AND moved away meaningfully -> R2 (Jan 5)
        # If it just spends 4+ hours in range -> R1 (Jan 13)
        
        if not returns_late.empty and moved_away:
            classification = "R2"
            reason = "Moved away then returned after 11:00"
        elif len(hours_touched) >= 4:
            classification = "R1"
            reason = f"Hours {sorted(list(hours_touched))} spent in 09:30 range"
        else:
            # Trend Rules
            trending_up = rth_1m['close'].iloc[-1] > or_h
            trending_down = rth_1m['close'].iloc[-1] < or_l
            
            if trending_up or trending_down:
                pullbacks = 0
                max_streak = 0
                curr_streak = 0
                prev_ex = None
                
                # Use 15m for structural pullbacks
                for _, row in rth_15m.iterrows():
                    is_pb = False
                    if trending_up:
                        if prev_ex is not None and row['low'] < prev_ex: is_pb = True
                        prev_ex = row['low']
                    else:
                        if prev_ex is not None and row['high'] > prev_ex: is_pb = True
                        prev_ex = row['high']
                    
                    if is_pb:
                        pullbacks += 1
                        curr_streak = 0
                    else:
                        curr_streak += 1
                        max_streak = max(max_streak, curr_streak)
                
                # Check for return to range even if not "late" (before 11:00)
                any_returns = rth_1m[(rth_1m['time_only'] > time(9, 31)) & (rth_1m['low'] <= or_h) & (rth_1m['high'] >= or_l)]
                
                if not any_returns.empty:
                    classification = "R1" # Minor return early
                    reason = "Returned to range before 11:00"
                elif pullbacks >= 2:
                    classification = "DWP"
                    reason = f"Trend with {pullbacks} pullbacks"
                elif max_streak >= 20: # 5 hours
                    classification = "DNP"
                    reason = "Power trend (5hr no-pullback streak)"
                else:
                    classification = "DNP"
                    reason = "Pure trend, no pullbacks"
            else:
                classification = "R1"
                reason = "Closed inside or near 09:30 range"

        results.append({'date': str(d), 'classification': classification, 'reason': reason})
    return results

if __name__ == "__main__":
    report = analyze_ticker("NQ1")
    for r in report:
        print(f"{r['date']}: {r['classification']} ({r['reason']})")
