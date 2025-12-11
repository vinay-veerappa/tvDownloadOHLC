
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from api.services.session_service import SessionService
import time
from pathlib import Path

class ProfilerService:
    _cache = {}
    _json_cache = {} # Cache the loaded JSON data too

    @staticmethod
    def clear_cache(ticker: str = None):
        """Clear the in-memory cache. If ticker is specified, only clear that ticker."""
        if ticker:
            ProfilerService._cache.pop(ticker, None)
            ProfilerService._json_cache.pop(ticker, None)
        else:
            ProfilerService._cache.clear()
            ProfilerService._json_cache.clear()
        return {"cleared": ticker or "all"}


    @staticmethod
    def analyze_profiler_stats(ticker: str, days: int = 50) -> Dict:
        """
        Get Profiler Stats.
        PRIORITY 1: Pre-computed JSON file (Instant)
        PRIORITY 2: Calculate from Parquet (Slow first time, cached df)
        """
        start_time = time.time()
        
        # --- PATH CHECK ---
        from api.services.data_loader import DATA_DIR
        json_path = DATA_DIR / f"{ticker}_profiler.json"
        
        # 1. Try Loading Pre-computed JSON
        if json_path.exists():
            # Check memory cache first
            if ticker in ProfilerService._json_cache:
                all_sessions = ProfilerService._json_cache[ticker]
            else:
                try:
                    with open(json_path, 'r') as f:
                        all_sessions = json.load(f)
                    ProfilerService._json_cache[ticker] = all_sessions
                except Exception as e:
                    print(f"Error reading JSON: {e}")
                    all_sessions = None
            
            if all_sessions:
                # Filter by days
                # Assuming all_sessions is sorted by time (script sorts it)
                # We need to find the cut-off date.
                # Since it's a list of dicts, and we want "last N days".
                # We can roughly estimate or filter by date string.
                
                # Get unique dates from the sessions
                # This is slightly expensive if list is huge, but much faster than pandas logic
                # Optimization: Just take the last N * 4 sessions (approx) -> inaccurate if missing days
                # Better: Filter properly.
                
                # Optimized Filter:
                # 1. Get last session date
                if not all_sessions: return {"sessions": [], "metadata": {}}
                
                last_sess = all_sessions[-1]
                last_date = datetime.fromisoformat(last_sess['start_time']).date()
                cutoff_date = last_date - timedelta(days=days)
                cutoff_iso = cutoff_date.isoformat()
                
                # Filter
                # sessions are sorted by start_time.
                # binary search would be ideal, but linear scan from end is fine for now
                filtered_sessions = []
                for s in reversed(all_sessions):
                    if s['start_time'] < cutoff_iso: # Rough comparison works for ISO strings
                        break
                    filtered_sessions.append(s)
                
                filtered_sessions.reverse()
                
                elapsed = time.time() - start_time
                return {
                    "sessions": filtered_sessions,
                    "metadata": {
                        "ticker": ticker,
                        "days": days,
                        "count": len(filtered_sessions),
                        "source": "precomputed_json",
                        "elapsed_seconds": round(elapsed, 4)
                    }
                }

        # 2. Fallback to Calculation (Original Logic)
        # ... (Previous implementation below, kept as fallback)
        
        # Load Data (with Cache)
        df = ProfilerService._cache.get(ticker)
        
        if df is None:
            try:
                from api.services.data_loader import DATA_DIR
                file_path = DATA_DIR / f"{ticker}_1m.parquet"
                if not file_path.exists():
                    return {"error": f"Data file for {ticker} not found"}
                
                df = pd.read_parquet(file_path)
                df = df.sort_index()
                
                # Handle Timezone (Standardize to US/Eastern)
                if df.index.tz is None:
                    df = df.tz_localize('UTC').tz_convert('US/Eastern')
                else:
                    df = df.tz_convert('US/Eastern')
                
                ProfilerService._cache[ticker] = df # Store in cache
                
            except Exception as e:
                return {"error": f"Failed to load data: {str(e)}"}
        
        # ... (Rest of the calculation logic)
        # For brevity in this edit, I will call the internal method _calculate_from_df
        # But to be safe with this 'write_to_file', I must include the logic or it breaks.
        # I'll paste the optimized logic I wrote in the previous step.
        
        sessions_def = [
            # Trading day sessions - all should share the same trading_date
            # Asia starts at 18:00 on (trading_date - 1 day)
            # London/NY sessions are on the actual trading_date
            # skip_broken: NY2 has no broken window since trading ends at 17:00
            {"name": "Asia",   "start": "18:00", "end": "19:30", "next_start": "02:30", "day_offset_start": -1, "day_offset_end": -1, "skip_broken": False}, 
            {"name": "London", "start": "02:30", "end": "03:30", "next_start": "07:30", "day_offset_start": 0, "day_offset_end": 0, "skip_broken": False},
            {"name": "NY1",    "start": "07:30", "end": "08:30", "next_start": "11:30", "day_offset_start": 0, "day_offset_end": 0, "skip_broken": False},
            {"name": "NY2",    "start": "11:30", "end": "12:30", "next_start": "17:00", "day_offset_start": 0, "day_offset_end": 0, "skip_broken": True}, 
        ]

        # Get unique calendar dates and derive trading dates
        # Trading date = the date on which the session ENDS (i.e., 18:00 on Dec 3 → trading date Dec 4)
        from datetime import time as dt_time
        
        def get_trading_date(ts):
            """Get trading date: if time >= 18:00, it belongs to next calendar day's trading session"""
            if ts.time() >= dt_time(18, 0):
                return (ts.date() + timedelta(days=1))
            return ts.date()
        
        # Get unique trading dates from the data
        trading_dates = sorted(list(set(get_trading_date(ts) for ts in df.index)))
        target_dates = trading_dates[-days:]
        
        if target_dates:
            # Need to include data from previous calendar day for Asia session
            slice_start = pd.Timestamp(target_dates[0]) - timedelta(days=2)
            if df.index.tz:
                 slice_start = slice_start.tz_localize(df.index.tz)
            df_slice = df.loc[slice_start:] 
        else:
            df_slice = df
        
        tz = df.index.tz
        collected_stats = []

        for trading_date in target_dates:
            trading_date_str = trading_date.strftime('%Y-%m-%d')
            
            for sess in sessions_def:
                # Calculate session start/end based on trading date and offsets
                sess_cal_date_start = trading_date + timedelta(days=sess['day_offset_start'])
                sess_cal_date_end = trading_date + timedelta(days=sess['day_offset_end'])
                
                start_naive = pd.Timestamp(f"{sess_cal_date_start.strftime('%Y-%m-%d')} {sess['start']}")
                end_naive = pd.Timestamp(f"{sess_cal_date_end.strftime('%Y-%m-%d')} {sess['end']}")

                
                try:
                    start_ts = start_naive.tz_localize(tz)
                    end_ts = end_naive.tz_localize(tz)
                except: continue

                try:
                    sess_data = df_slice.loc[start_ts : end_ts - timedelta(seconds=1)]
                except KeyError: continue
                
                if sess_data.empty: continue
                
                # Basic price data
                sess_open = float(sess_data.iloc[0]['open'])
                high = sess_data['high'].max()
                low = sess_data['low'].min()
                mid = (high + low) / 2
                
                # Time when high/low occurred
                high_idx = sess_data['high'].idxmax()
                low_idx = sess_data['low'].idxmin()
                high_time = high_idx.strftime('%H:%M') if pd.notna(high_idx) else None
                low_time = low_idx.strftime('%H:%M') if pd.notna(low_idx) else None
                
                # Percentage from open
                high_pct = round(((high - sess_open) / sess_open) * 100, 2) if sess_open > 0 else 0
                low_pct = round(((low - sess_open) / sess_open) * 100, 2) if sess_open > 0 else 0
                
                mon_start = end_ts
                next_start_time = sess['next_start']
                
                # For next_start calculation: Asia's next_start (02:30) is on the trading_date
                # All other sessions' next_start is also on the trading_date  
                if sess['name'] == 'Asia':
                    # Asia ends at 19:30 on (trading_date - 1), next_start 02:30 is on trading_date
                    mon_end_day = trading_date
                else:
                    # London/NY: next_start is on the same trading_date
                    mon_end_day = trading_date
                
                mon_end_naive = pd.Timestamp(f"{mon_end_day.strftime('%Y-%m-%d')} {next_start_time}")
                try: status_end = mon_end_naive.tz_localize(tz)
                except: continue

                reset_time_naive = pd.Timestamp(f"{trading_date.strftime('%Y-%m-%d')} 18:00")
                try: reset_time = reset_time_naive.tz_localize(tz)
                except: continue
                
                if reset_time <= status_end: reset_time += timedelta(days=1)
                broken_start = status_end
                broken_end = reset_time

                try: status_data = df_slice.loc[mon_start : status_end - timedelta(seconds=1)]
                except KeyError: status_data = pd.DataFrame()
                
                status = 'None'
                triggered_side = None
                status_time = None
                
                if not status_data.empty:
                    for ts, row in status_data.iterrows():
                        h, l = row['high'], row['low']
                        # Current bar checks
                        broke_high = h > high
                        broke_low = l < low
                        
                        if triggered_side is None:
                            if broke_high and broke_low:
                                # Both broken on same bar - infer direction from bar open
                                # If open is closer to low, assume went up first (Long False)
                                # If open is closer to high, assume went down first (Short False)
                                bar_open = row['open']
                                bar_mid = (h + l) / 2
                                if bar_open < bar_mid:
                                    status = 'Long False'  # Started low, went up first
                                else:
                                    status = 'Short False'  # Started high, went down first
                                triggered_side = 'Both'
                                status_time = ts.isoformat()
                                break
                            elif broke_high:
                                triggered_side = 'High'; status = 'Long True'; status_time = ts.isoformat() 
                            elif broke_low:
                                triggered_side = 'Low'; status = 'Short True'; status_time = ts.isoformat()
                        else:
                            if triggered_side == 'High':
                                if broke_low:
                                    status = 'Long False'; status_time = ts.isoformat(); break 
                            elif triggered_side == 'Low':
                                if broke_high:
                                    status = 'Short False'; status_time = ts.isoformat(); break

                try: broken_data = df_slice.loc[broken_start : broken_end - timedelta(seconds=1)]
                except KeyError: broken_data = pd.DataFrame()
                
                broken = False
                broken_time = None
                
                # Skip broken calculation for sessions with no broken window (e.g., NY2 - trading ends at 17:00)
                if not sess.get('skip_broken', False) and not broken_data.empty:
                    break_mask = (broken_data['low'] <= mid) & (broken_data['high'] >= mid)
                    if break_mask.any():
                        broken = True
                        broken_time = break_mask.idxmax().strftime('%H:%M')

                collected_stats.append({
                    "date": trading_date_str,
                    "session": sess['name'],
                    "open": sess_open,
                    "range_high": float(high),
                    "range_low": float(low),
                    "mid": float(mid),
                    "high_time": high_time,
                    "low_time": low_time,
                    "high_pct": high_pct,
                    "low_pct": low_pct,
                    "status": status,
                    "status_time": status_time,
                    "broken": broken,
                    "broken_time": broken_time,
                    "start_time": start_ts.isoformat(),
                    "end_time": end_ts.isoformat()
                })

        collected_stats.sort(key=lambda x: x['start_time'])
        elapsed = time.time() - start_time

        return {
            "sessions": collected_stats,
            "metadata": {
                "ticker": ticker,
                "days": days,
                "count": len(collected_stats),
                "source": "calculated_fallback",
                "elapsed_seconds": round(elapsed, 2)
            }
        }
