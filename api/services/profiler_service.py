

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Optional
from api.services.session_service import SessionService
import time
from pathlib import Path
from api.services.data_loader import DATA_DIR

class ProfilerService:
    _cache = {}
    _json_cache = {} # Cache the loaded JSON data too
    _price_model_cache = {}
    _level_touches_cache = {}
    _daily_hod_lod_cache = {}
    _filtered_stats_cache = {} # Cache for filtered stats results

    @staticmethod
    def clear_cache(ticker: str = None):
        """Clear the in-memory cache. If ticker is specified, only clear that ticker."""
        if ticker:
            ProfilerService._cache.pop(ticker, None)
            ProfilerService._json_cache.pop(ticker, None)
            ProfilerService._level_touches_cache.pop(ticker, None)
            ProfilerService._daily_hod_lod_cache.pop(ticker, None)
            
            # Clear price model cache for this ticker key prefix
            keys = [k for k in ProfilerService._price_model_cache.keys() if k[0] == ticker]
            for k in keys:
                ProfilerService._price_model_cache.pop(k, None)
        else:
            ProfilerService._cache.clear()
            ProfilerService._json_cache.clear()
            ProfilerService._price_model_cache.clear()
            ProfilerService._level_touches_cache.clear()
            ProfilerService._daily_hod_lod_cache.clear()
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
        
        # --- SAVE TO DISK (PERSISTENT CACHE) ---
        try:
            with open(json_path, 'w') as f:
                json.dump(collected_stats, f, indent=2)
            print(f"[Profiling] Saved {len(collected_stats)} sessions to {json_path}")
            # Update In-Memory Cache
            ProfilerService._json_cache[ticker] = collected_stats
        except Exception as e:
            print(f"Error saving JSON: {e}")
            
        elapsed = time.time() - start_time

        return {
            "sessions": collected_stats,
            "count": len(collected_stats),
            "elapsed_seconds": round(elapsed, 4)
        }

    @staticmethod
    def get_price_model_data(ticker: str, session_name: str, outcome_name: str, days: int = 50) -> Dict:
        """
        Calculate Price Model (Composite High/Low paths) for a specific outcome.
        Returns two models: 
            1. Average (Mean High/Low)
            2. Extreme (Max High/Min Low)
        """
        # 1. Get filtered sessions first to know which dates/times to aggregate
        stats_result = ProfilerService.analyze_profiler_stats(ticker, days)
        if "error" in stats_result: return stats_result
        
        all_sessions = stats_result.get("sessions", [])
        
        # Filter for target session and outcome
        target_sessions = [
            s for s in all_sessions 
            if s['session'] == session_name and 
            (s['status'] == outcome_name or 
             (outcome_name == "Long" and "Long" in s['status']) or 
             (outcome_name == "Short" and "Short" in s['status']))
        ]
        
        # Strict filter for exact outcome string match (e.g. "Short False") if passed
        filtered = [s for s in target_sessions if s['status'] == outcome_name] if " " in outcome_name else target_sessions
        
        print(f"[DEBUG] Calculating Price Model for {ticker} {session_name} {outcome_name}")
        
        if not filtered:
             return {"median": [], "extreme": [], "count": 0}

        return ProfilerService.generate_composite_path(ticker, filtered, duration_hours=7.0)

    @staticmethod
    def generate_composite_path(ticker: str, sessions: List[Dict], duration_hours: float = 7.0, bucket_minutes: int = 1) -> Dict:
        """
        Generic method to generate composite price paths from a list of sessions.
        OPTIMIZED: Uses searchsorted and integer slicing for high performance.
        Supports aggregation into larger buckets (e.g. 5 min, 15 min).
        """
        start_time = time.time()
        
        # ... validation ...
        # (lines 364-453 unchanged)

        # 1. Load 1-minute DataFrame (Cached)
        df = ProfilerService._cache.get(ticker)
        if df is None:
            try:
                from api.services.data_loader import DATA_DIR
                file_path = DATA_DIR / f"{ticker}_1m.parquet"
                if file_path.exists():
                    df = pd.read_parquet(file_path)
                    df = df.sort_index()
                    if df.index.tz is None: df = df.tz_localize('UTC').tz_convert('US/Eastern')
                    else: df = df.tz_convert('US/Eastern')
                    ProfilerService._cache[ticker] = df
            except Exception as e:
                print(f"[DEBUG] Error loading parquet: {e}")
                pass
            
        if df is None: return {"error": "Data not loaded"}

        # 2. Prepare Timestamps & Validate
        # Ensure timestamps match DataFrame timezone
        tz = df.index.tz
        
        start_ts_list = []
        for s in sessions:
            ts = pd.Timestamp(s['start_time'])
            # Ensure timezone matches
            if ts.tz is None and tz is not None:
                ts = ts.tz_localize(tz)
            elif ts.tz is not None and tz is not None and ts.tz != tz:
                ts = ts.tz_convert(tz)
            start_ts_list.append(ts)
        
        # Bounds check
        min_idx_ts = df.index[0]
        max_idx_ts = df.index[-1]
        
        valid_sessions = []
        valid_starts = []
        
        for i, ts in enumerate(start_ts_list):
            end_t = ts + pd.Timedelta(hours=duration_hours)
            if ts >= min_idx_ts and end_t <= max_idx_ts:
                valid_sessions.append(sessions[i])
                valid_starts.append(ts)
                
        if not valid_starts:
             return {"median": [], "extreme": [], "count": 0}

        # 3. Vectorized Lookup (Fast Slicing)
        # Find integer positions for all start and end times
        start_locs = df.index.searchsorted(valid_starts)
        
        end_ts_list = [ts + pd.Timedelta(hours=duration_hours) for ts in valid_starts]
        end_locs = df.index.searchsorted(end_ts_list)
        
        # 4. Extract Data Arrays (Optimized: NumPy)
        all_time_idxs = []
        all_norm_highs = []
        all_norm_lows = []
        
        # Pre-fetch numpy arrays (Zero Copy views)
        np_high = df['high'].values
        np_low = df['low'].values
        np_index = df.index.values

        for i, (start_idx, end_idx) in enumerate(zip(start_locs, end_locs)):
            # Bounds check for searchsorted results
            if start_idx >= len(df) or end_idx > len(df) or start_idx >= end_idx:
                continue
                
            sess_open = valid_sessions[i]['open']
            if sess_open <= 0: continue
            
            # Slicing numpy array is FAST
            chunk_ts = np_index[start_idx:end_idx]
            if len(chunk_ts) == 0: continue
            base_ts = chunk_ts[0]
            
            # Vectorized time delta calculation
            # Time delta in minutes
            time_deltas_m = (chunk_ts - base_ts).astype('timedelta64[m]').astype(int)
            
            # Vectorized Price Normalization
            chunk_high = np_high[start_idx:end_idx]
            chunk_low = np_low[start_idx:end_idx]
            
            norm_high = ((chunk_high - sess_open) / sess_open) * 100
            norm_low = ((chunk_low - sess_open) / sess_open) * 100
            
            # Bucketing Logic
            if bucket_minutes > 1:
                time_idxs = (time_deltas_m // bucket_minutes) * bucket_minutes
            else:
                time_idxs = time_deltas_m
                
            all_time_idxs.append(time_idxs)
            all_norm_highs.append(norm_high)
            all_norm_lows.append(norm_low)

        if not all_time_idxs:
            return {"median": [], "extreme": [], "count": 0}

        # 5. Concatenate (Fast)
        cat_time = np.concatenate(all_time_idxs)
        cat_high = np.concatenate(all_norm_highs)
        cat_low = np.concatenate(all_norm_lows)
        
        # Create SINGLE DataFrame for GroupBy
        combined = pd.DataFrame({
            'time_idx': cat_time,
            'norm_high': cat_high,
            'norm_low': cat_low
        })
        
        # Group by bucketed minute offset and calculate median/extreme
        stats = combined.groupby('time_idx').agg({
            'norm_high': ['median', 'max'],
            'norm_low':  ['median', 'min']
        })
        
        # 6. Format Output
        avg_path = []
        ext_path = []
        
        # Helper to format time
        base_dt = None
        if valid_sessions:
            try:
                # Parse start time from first session to get base hours/minutes
                # Assumes all sessions start around same time (e.g. all 'Daily' or all 'NY1')
                # Handle ISO format with timezone
                from datetime import datetime, timedelta
                s_ts = pd.Timestamp(valid_sessions[0]['start_time'])
                base_dt = s_ts.replace(year=2000, month=1, day=1) # Normalize date
            except:
                pass

        # Using sorted index ensures time order
        for time_idx in sorted(stats.index):
            # Access using MultiIndex columns
            row = stats.loc[time_idx]
            
            # ('col', 'stat') lookup
            avg_h = row[('norm_high', 'median')]
            max_h = row[('norm_high', 'max')]
            avg_l = row[('norm_low', 'median')]
            min_l = row[('norm_low', 'min')]
            
            # Calculate time string
            time_str = ""
            if base_dt:
                curr_dt = base_dt + timedelta(minutes=int(time_idx))
                time_str = curr_dt.strftime("%H:%M")

            avg_path.append({
                "time_idx": int(time_idx),
                "time": time_str,
                "high": round(float(avg_h), 3),
                "low": round(float(avg_l), 3)
            })
            
            ext_path.append({
                "time_idx": int(time_idx),
                "time": time_str,
                "high": round(float(max_h), 3),
                "low": round(float(min_l), 3)
            })
            
        print(f"[DEBUG] Composite Path Gen Time: {time.time() - start_time:.2f}s (Processed {len(valid_sessions)} sessions)")
        return {
            "median": avg_path,
            "extreme": ext_path,
            "count": len(sessions)
        }
    @staticmethod
    def get_custom_price_model(ticker: str, target_session: str, dates: List[str], bucket_minutes: int = 1):
        """
        Generate price model for a specific list of dates and target session.
        If target_session == 'Daily', creates synthetic full-day sessions (18:00->16:00).
        """
        # 1. Get Full History
        stats = ProfilerService.analyze_profiler_stats(ticker, days=10000)
        if "error" in stats:
            return stats
        
        history = stats.get('sessions', [])
        
        # 2. Filter History
        date_set = set(dates)
        
        if target_session == 'Daily':
            matches = []
            asia_map = {s['date']: s for s in history if s['session'] == 'Asia'}
            
            for d in dates:
                if d in asia_map:
                    asia = asia_map[d]
                    # Start: Asia start (18:00 prev day)
                    # Duration: ~22 hours (until 16:00 next day)
                    # We rely on generate_composite_path to slice 7h usually, but here we want more?
                    # generate_composite_path usually uses start_time and finds data.
                    # We need to make sure generate_composite_path fetches enough data (it slices 7h by default?)
                    # Wait, existing `get_price_model_data` sliced 7h. 
                    # `generate_composite_path` takes `sessions` list.
                    # It iterates and does `chunk = df.loc[start_ts : end_ts]`.
                    # So we must set `end_time` correctly here.
                    matches.append({
                        'start_time': asia['start_time'], 
                        'end_time': (pd.Timestamp(d) + pd.Timedelta(hours=16)).isoformat(), 
                        'open': asia['open'],
                        'session': 'Daily',
                        'date': d
                    })
        else:
            matches = [
                s for s in history 
                if s.get('session') == target_session and s.get('date') in date_set
            ]
        
        if not matches:
            return {"median": [], "extreme": [], "count": 0}
            
        print(f"[Profiling] Custom Model: Found {len(matches)} matching sessions for {target_session}")
        
        # Determine duration based on session type
        # Default 7.0 works for partial sessions, but Daily needs full day
        duration = 7.0
        if target_session == 'Daily':
            duration = 22.0
        elif target_session == 'Asia':
            duration = 8.0 # 18:00 - 02:00
        elif target_session == 'London':
            duration = 6.0 # 03:00 - 09:00? 
        
        # 3. Generate Composite Path
        return ProfilerService.generate_composite_path(ticker, matches, duration_hours=duration, bucket_minutes=bucket_minutes)

    # ========================================================================
    # NEW: Filter-Based API Methods (Architecture Refactor)
    # ========================================================================

    @staticmethod
    def apply_filters(
        sessions: List[Dict],
        target_session: str,
        filters: Dict[str, str] = None,
        broken_filters: Dict[str, str] = None,
        intra_state: str = "Any"
    ) -> List[str]:
        """
        Apply filters and return the list of matching dates (intersection logic).
        
        Args:
            sessions: List of all session dicts
            target_session: The primary session to analyze (e.g., "NY1")
            filters: Dict of session -> status filter (e.g., {"Asia": "Short True"})
            broken_filters: Dict of session -> broken filter (e.g., {"Asia": "Broken"})
            intra_state: "Any", "Long", "Short", etc. for intra-session filtering
        
        Returns:
            List of matching date strings
        """
        filters = filters or {}
        broken_filters = broken_filters or {}
        
        # Group sessions by date for intersection logic
        date_sessions: Dict[str, Dict[str, Dict]] = {}
        for s in sessions:
            date = s.get('date')
            sess_name = s.get('session')
            if date and sess_name:
                if date not in date_sessions:
                    date_sessions[date] = {}
                date_sessions[date][sess_name] = s
        
        # Apply filters - find intersection of all conditions
        matched_dates = []
        
        for date, sessions_by_name in date_sessions.items():
            # Check if this date satisfies ALL filters
            matches_all = True
            
            # Check status filters
            for session_name, required_status in filters.items():
                if required_status and required_status != 'Any':
                    sess = sessions_by_name.get(session_name)
                    if not sess:
                        matches_all = False
                        break
                    
                    actual_status = sess.get('status', '')
                    # If filter is just "Long" or "Short", treat as prefix match (matches "Short True" and "Short False")
                    if required_status in ['Long', 'Short']:
                        if not actual_status.startswith(required_status):
                            matches_all = False
                            break
                    elif required_status in ['True', 'False']:
                        if not actual_status.endswith(required_status):
                            matches_all = False
                            break
                    else:
                        # Exact match for full status (e.g. "Short True")
                        if actual_status != required_status:
                            matches_all = False
                            break
            
            if not matches_all:
                continue
            
            # Check broken filters
            for session_name, required_broken in broken_filters.items():
                if required_broken and required_broken != 'Any':
                    sess = sessions_by_name.get(session_name)
                    if not sess:
                        matches_all = False
                        break
                    
                    is_broken = sess.get('broken', False)
                    # "Broken" or "Yes" -> must be broken
                    if required_broken in ['Broken', 'Yes'] and not is_broken:
                        matches_all = False
                        break
                    # "Not Broken" or "No" -> must NOT be broken
                    elif required_broken in ['Not Broken', 'No'] and is_broken:
                        matches_all = False
                        break
            
            if not matches_all:
                continue
            
            # Check intra-session state (direction filter on target session)
            if intra_state and intra_state != 'Any':
                target_sess = sessions_by_name.get(target_session)
                if target_sess:
                    status = target_sess.get('status', '')
                    if intra_state == 'Long' and not status.startswith('Long'):
                        matches_all = False
                    elif intra_state == 'Short' and not status.startswith('Short'):
                        matches_all = False
            
            if matches_all:
                matched_dates.append(date)
        
        return sorted(matched_dates)

    @staticmethod
    def get_filtered_stats(
        ticker: str,
        target_session: str,
        filters: Dict[str, str] = None,
        broken_filters: Dict[str, str] = None,
        intra_state: str = "Any"
    ) -> Dict:
        """
        Get pre-aggregated stats for filtered sessions.
        Returns matched dates, distribution, and aggregated statistics.
        """
        # Create cache key
        cache_key = (
            ticker, 
            target_session, 
            json.dumps(filters, sort_keys=True) if filters else "", 
            json.dumps(broken_filters, sort_keys=True) if broken_filters else "", 
            intra_state
        )
        
        if cache_key in ProfilerService._filtered_stats_cache:
             return ProfilerService._filtered_stats_cache[cache_key]

        # 1. Load all sessions
        # 1. Load all sessions
        stats = ProfilerService.analyze_profiler_stats(ticker, days=10000)
        
        if "error" in stats:
            return stats
        
        all_sessions = stats.get('sessions', [])
        
        # 2. Apply filters to get matched dates
        matched_dates = ProfilerService.apply_filters(
            all_sessions, target_session, filters, broken_filters, intra_state
        )
        
        date_set = set(matched_dates)
        
        # 3. Get sessions for matched dates
        matched_sessions = [s for s in all_sessions if s.get('date') in date_set]
        
        # 4. Calculate distribution (for target session)
        target_sessions = [s for s in matched_sessions if s.get('session') == target_session]
        
        distribution = {}
        for status in ['Long True', 'Long False', 'Short True', 'Short False', 'None']:
            count = sum(1 for s in target_sessions if s.get('status') == status)
            distribution[status] = count
        
        # 5. Calculate range stats
        range_stats = {
            "high_pct": {
                "median": None,
                "mean": None,
                "mode": None
            },
            "low_pct": {
                "median": None,
                "mean": None,
                "mode": None
            }
        }
        
        high_pcts = [s.get('high_pct', 0) for s in target_sessions if s.get('high_pct') is not None]
        low_pcts = [s.get('low_pct', 0) for s in target_sessions if s.get('low_pct') is not None]
        
        if high_pcts:
            range_stats["high_pct"]["median"] = round(float(np.median(high_pcts)), 3)
            range_stats["high_pct"]["mean"] = round(float(np.mean(high_pcts)), 3)
        
        if low_pcts:
            range_stats["low_pct"]["median"] = round(float(np.median(low_pcts)), 3)
            range_stats["low_pct"]["mean"] = round(float(np.mean(low_pcts)), 3)
        

        # Optimize payload size: Strip unused fields locally
        # We only need enough info for charts.
        lean_sessions = []
        for s in matched_sessions:
            # Create a shallow copy with only needed fields
            lean_s = {
                'date': s.get('date'),
                'session': s.get('session'),
                'status': s.get('status'),
                'broken': s.get('broken'),
                'high_time': s.get('high_time'),
                'low_time': s.get('low_time'),
                'high_pct': s.get('high_pct'),
                'low_pct': s.get('low_pct'),
                # Keep numeric ranges for some charts if needed?
                # RangeDistribution needs high_pct/low_pct.
                # HodLod needs times.
                # SessionStats needs status/broken.
                # PriceModel calls a separate endpoint.
                # DailyLevels needs dates (which are in lean_s['date']).
            }
            lean_sessions.append(lean_s)

        result = {
            "matched_dates": matched_dates,
            "count": len(matched_dates),
            "distribution": distribution,
            "range_stats": range_stats,
            "sessions": lean_sessions, # Reduced size payload
            "target_session": target_session,
            "filters_applied": filters or {},
            "broken_filters_applied": broken_filters or {}
        }
        
        ProfilerService._filtered_stats_cache[cache_key] = result
        return result

    @staticmethod
    def get_filtered_price_model(
        ticker: str,
        target_session: str,
        filters: Dict[str, str] = None,
        broken_filters: Dict[str, str] = None,
        intra_state: str = "Any",
        bucket_minutes: int = 1
    ) -> Dict:
        """
        Generate price model using filter criteria instead of explicit date list.
        """
        # Create cache key
        cache_key = (
            ticker, 
            target_session, 
            json.dumps(filters, sort_keys=True) if filters else "", 
            json.dumps(broken_filters, sort_keys=True) if broken_filters else "", 
            intra_state, 
            bucket_minutes
        )
        
        if cache_key in ProfilerService._price_model_cache:
            return ProfilerService._price_model_cache[cache_key]

        # 1. Get filtered stats (which includes matched dates)
        stats = ProfilerService.get_filtered_stats(
            ticker, target_session, filters, broken_filters, intra_state
        )
        
        if "error" in stats:
            return stats
        
        # 2. Extract matched sessions or dates
        # get_filtered_stats returns 'sessions' (filtered list)
        matched_sessions = stats.get('sessions', [])
        
        # 3. Generate Composite Path
        # Determine duration
        duration = 7.0
        if target_session == 'Daily':
            duration = 22.0
        elif target_session == 'Asia':
            duration = 8.0
        elif target_session == 'London':
            duration = 6.0
            
        result = ProfilerService.generate_composite_path(
            ticker, matched_sessions, duration_hours=duration, bucket_minutes=bucket_minutes
        )
        
        # Cache Result
        ProfilerService._price_model_cache[cache_key] = result
        return result

    @staticmethod
    def get_daily_hod_lod(ticker: str) -> Dict:
        """
        Get pre-computed true daily HOD/LOD times.
        Buffered in memory to avoid repeated disk I/O (1MB+).
        """
        if ticker in ProfilerService._daily_hod_lod_cache:
            return ProfilerService._daily_hod_lod_cache[ticker]
            
        json_path = DATA_DIR / f"{ticker}_daily_hod_lod.json"
        
        if not json_path.exists():
            return {"error": f"Daily HOD/LOD data for {ticker} not found."}
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            ProfilerService._daily_hod_lod_cache[ticker] = data
            return data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_level_touches(ticker: str) -> Dict:
        """
        Get pre-computed reference level touch data.
        Buffered in memory to avoid repeated disk I/O (6MB+).
        """
        if ticker in ProfilerService._level_touches_cache:
            return ProfilerService._level_touches_cache[ticker]
            
        json_path = DATA_DIR / f"{ticker}_level_touches.json"
        
        if not json_path.exists():
            return {"error": f"Level touch data for {ticker} not found."}
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            ProfilerService._level_touches_cache[ticker] = data
            return data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def prewarm_cache(ticker: str = "NQ1"):
        """
        Run heavy calculations on startup to populate cache.
        """
        print(f"[Pre-Warm] Warming cache for {ticker}...")
        try:
            # 1. Load Static Files
            ProfilerService.get_daily_hod_lod(ticker)
            ProfilerService.get_level_touches(ticker)
            
            # 2. Run Heavy Price Model Calculation (All Sessions)
            # This pre-computes "Daily", "Asia", "London", "NY1", "NY2" Default Views
            for session_name in ["Daily", "Asia", "London", "NY1", "NY2"]:
                ProfilerService.get_filtered_price_model(
                    ticker=ticker,
                    target_session=session_name,
                    filters={},
                    intra_state="Any",
                    bucket_minutes=5
                )
                # Ensure stats are also cached
                ProfilerService.get_filtered_stats(
                    ticker=ticker, 
                    target_session=session_name,
                    filters={}, 
                    broken_filters={},
                    intra_state="Any"
                )
            print(f"[Pre-Warm] Successfully warmed cache for {ticker}")
        except Exception as e:
            print(f"[Pre-Warm] Failed to warm cache: {e}")
