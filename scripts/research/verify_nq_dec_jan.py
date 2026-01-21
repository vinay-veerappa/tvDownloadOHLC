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
    df_1h = load_data(ticker, "1h")
    if df_1m.empty or df_1h.empty: return []
    
    # Target range: Dec 2025 to Jan 2026
    start_date = pd.to_datetime("2025-12-01").date()
    target_dates = df_1m[(df_1m['date'] >= start_date)]['date'].unique()
    
    results = []
    
    for d in target_dates:
        m = df_1m[df_1m['date'] == d]
        h = df_1h[df_1h['date'] == d]
        
        or_match = m[m['time_only'] == time(9, 30)]
        if or_match.empty: continue
        or_bar = or_match.iloc[0]
        or_h, or_l = or_bar['high'], or_bar['low']
        
        # Windows
        rth_1m = m[(m['time_only'] >= time(9, 30)) & (m['time_only'] <= time(15, 0))]
        rth_1h = h[(h['time_only'] >= time(9, 30)) & (h['time_only'] <= time(15, 0))]
        first_4h_1h = h[(h['time_only'] >= time(9, 0)) & (h['time_only'] <= time(13, 0))] # 9:00, 10:00, 11:00, 12:00 candles
        
        if rth_1m.empty: continue

        # 1. R1 Rule (First 4 Hours Ranging)
        # Check how many of the first 4 hourly bars touched the range
        early_overlap_count = 0
        for _, h_bar in first_4h_1h.iterrows():
            if h_bar['low'] <= or_h and h_bar['high'] >= or_l:
                early_overlap_count += 1
        
        # 2. R2 Rule (Gap Rule + Return after 11:00)
        # Check if any hourly bar was COMPLETELY outside range
        has_gap = False
        for _, h_bar in rth_1h.iterrows():
            # Hourly High < OR Low OR Hourly Low > OR High
            if h_bar['high'] < or_l or h_bar['low'] > or_h:
                has_gap = True
                break
        
        # Check return after 11:00
        late_1m = rth_1m[rth_1m['time_only'] >= time(11, 0)]
        returns_late = not late_1m[(late_1m['low'] <= or_h) & (late_1m['high'] >= or_l)].empty
        
        classification = "UNKNOWN"
        reason = ""
        
        if returns_late and has_gap:
            classification = "R2"
            reason = "Gap created (full hour away) then returned after 11:00"
        elif early_overlap_count >= 4 or not rth_1m[(rth_1m['time_only'] > time(9, 31)) & (rth_1m['low'] <= or_h) & (rth_1m['high'] >= or_l)].empty:
            # If it stayed in range or touched range early without a gap
            classification = "R1"
            reason = f"Stayed in range/returned without full hour gap ({early_overlap_count} early H overlaps)"
        else:
            # 3. Trend Rules
            trending_up = rth_1m['close'].iloc[-1] > or_h
            trending_down = rth_1m['close'].iloc[-1] < or_l
            
            if trending_up or trending_down:
                pullbacks = 0
                max_streak = 0
                curr_streak = 0
                prev_ex = None
                
                # Using Hourly bars for structural pullbacks as per user rule
                for _, h_bar in rth_1h.iterrows():
                    is_pb = False
                    if trending_up:
                        if prev_ex is not None and h_bar['low'] < prev_ex: is_pb = True
                        prev_ex = h_bar['low']
                    else:
                        if prev_ex is not None and h_bar['high'] > prev_ex: is_pb = True
                        prev_ex = h_bar['high']
                    
                    if is_pb:
                        pullbacks += 1
                        curr_streak = 0
                    else:
                        curr_streak += 1
                        max_streak = max(max_streak, curr_streak)
                
                if pullbacks > 0:
                    classification = "DWP"
                    reason = f"Trend with {pullbacks} hourly pullbacks"
                elif max_streak >= 5:
                    classification = "DNP"
                    reason = f"Power trend (5hr no-pullback streak)"
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
    # Sort to show Dec then Jan
    report.sort(key=lambda x: x['date'])
    for r in report:
        print(f"{r['date']}: {r['classification']} ({r['reason']})")
