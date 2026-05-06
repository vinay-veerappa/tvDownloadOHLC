
import os
from collections import OrderedDict

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Optional
from api.features.sessions.service import SessionService
import time
from pathlib import Path
from api.features.shared.data_loader import DATA_DIR
from scripts.libs_py.nqstats.levels import (
    calculate_daily_levels, 
    calculate_session_opens, 
    calculate_p12_levels, 
    get_session_mids
)

class ProfilerService:
    _cache = OrderedDict()
    _json_cache = OrderedDict()  # Cache the loaded JSON data too
    _price_model_cache = OrderedDict()
    _level_touches_cache = OrderedDict()
    _daily_hod_lod_cache = OrderedDict()
    _filtered_stats_cache = OrderedDict()  # Cache for filtered stats results
    _prediction_cache = OrderedDict()  # Cache for prediction datasets

    _MAX_DF_CACHE = int(os.getenv("PROFILER_MAX_DF_CACHE", "2"))
    _MAX_JSON_CACHE = int(os.getenv("PROFILER_MAX_JSON_CACHE", "4"))
    _MAX_FILTERED_STATS_CACHE = int(os.getenv("PROFILER_MAX_FILTERED_STATS_CACHE", "64"))
    _MAX_PRICE_MODEL_CACHE = int(os.getenv("PROFILER_MAX_PRICE_MODEL_CACHE", "48"))
    _MAX_LEVEL_TOUCHES_CACHE = int(os.getenv("PROFILER_MAX_LEVEL_TOUCHES_CACHE", "4"))
    _MAX_DAILY_HOD_LOD_CACHE = int(os.getenv("PROFILER_MAX_DAILY_HOD_LOD_CACHE", "4"))
    _MAX_PREDICTION_CACHE = int(os.getenv("PROFILER_MAX_PREDICTION_CACHE", "16"))

    @staticmethod
    def _cache_get(cache: OrderedDict, key):
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value

    @staticmethod
    def _cache_set(cache: OrderedDict, key, value, max_items: int):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > max_items:
            cache.popitem(last=False)

    
    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        """Standardize ticker for file resolution: ES1! -> ES1, NQ -> NQ1"""
        clean = ticker.replace("!", "")
        aliases = {
            "NQ": "NQ1",
            "ES": "ES1",
            "CL": "CL1",
            "RTY": "RTY1",
            "YM": "YM1",
            "GC": "GC1"
        }
        return aliases.get(clean, clean)

    @staticmethod
    def clear_cache(ticker: str = None):
        """Clear the in-memory cache. If ticker is specified, only clear that ticker."""
        if ticker:
            ticker = ProfilerService._normalize_ticker(ticker)
            ProfilerService._cache.pop(ticker, None)
            ProfilerService._json_cache.pop(ticker, None)
            ProfilerService._level_touches_cache.pop(ticker, None)
            ProfilerService._daily_hod_lod_cache.pop(ticker, None)
            ProfilerService._prediction_cache.pop(ticker, None)
            
            # Clear price model cache for this ticker key prefix
            keys = [k for k in ProfilerService._price_model_cache.keys() if k[0] == ticker]
            for k in keys:
                ProfilerService._price_model_cache.pop(k, None)

            # Clear filtered stats cache for this ticker key prefix
            keys = [k for k in ProfilerService._filtered_stats_cache.keys() if k[0] == ticker]
            for k in keys:
                ProfilerService._filtered_stats_cache.pop(k, None)

            # Clear prediction cache keys for this ticker
            keys = [k for k in ProfilerService._prediction_cache.keys() if str(k).startswith(f"{ticker}_")]
            for k in keys:
                ProfilerService._prediction_cache.pop(k, None)
        else:
            ProfilerService._cache.clear()
            ProfilerService._json_cache.clear()
            ProfilerService._price_model_cache.clear()
            ProfilerService._level_touches_cache.clear()
            ProfilerService._daily_hod_lod_cache.clear()
            ProfilerService._filtered_stats_cache.clear()
            ProfilerService._prediction_cache.clear()
        return {"cleared": ticker or "all"}


    @staticmethod
    def analyze_profiler_stats(ticker: str, days: int = 50, force: bool = False) -> Dict:
        """
        Get Profiler Stats.
        PRIORITY 1: Pre-computed JSON file (Instant)
        PRIORITY 2: Calculate from Parquet (Slow first time, cached df)
        """
        start_time = time.time()
        
        # --- PATH CHECK ---
        ticker = ProfilerService._normalize_ticker(ticker)
        from api.features.shared.data_loader import DATA_DIR
        json_path = DATA_DIR / f"{ticker}_profiler.json"
        
        # 1. Try Loading Pre-computed JSON (if not forced)
        if json_path.exists() and not force:
            # Check memory cache first
            cached_sessions = ProfilerService._cache_get(ProfilerService._json_cache, ticker)
            if cached_sessions is not None:
                all_sessions = cached_sessions
            else:
                try:
                    with open(json_path, 'r') as f:
                        all_sessions = json.load(f)
                    ProfilerService._cache_set(
                        ProfilerService._json_cache,
                        ticker,
                        all_sessions,
                        ProfilerService._MAX_JSON_CACHE,
                    )
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


        # 2. Fallback to Calculation (Modular Library)
        try:
            from scripts.libs_py.profiler import ProfilerData
            data = ProfilerData.from_parquet(ticker, days=days)
            
            elapsed = time.time() - start_time
            return {
                "sessions": data.sessions,
                "metadata": {
                    "ticker": ticker,
                    "days": days,
                    "count": len(data.sessions),
                    "source": "dynamic_calculation",
                    "elapsed_seconds": round(elapsed, 4)
                }
            }
        except Exception as e:
            return {"error": f"Calculation failed: {str(e)}"}


    @staticmethod
    def get_level_stats(ticker: str) -> Dict:
        """
        Get pre-computed level statistics (Hit Rate, Timing) from JSON.
        """
        ticker = ProfilerService._normalize_ticker(ticker)
        from api.features.shared.data_loader import DATA_DIR
        json_path = DATA_DIR / f"{ticker}_level_stats.json"
        
        if json_path.exists():
            try:
                with open(json_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                return {"error": str(e)}
        return {"error": "Stats not found"}

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
            (outcome_name == "Any" or 
             s['status'] == outcome_name or 
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
        df = ProfilerService._load_df(ticker)
        
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
        
        # Use absolute Unix seconds for the index (converts US/Eastern -> UTC Unix)
        np_ts_unix = df.index.astype('int64').to_numpy() // 10**9

        for i, (start_idx, end_idx) in enumerate(zip(start_locs, end_locs)):
            # Bounds check for searchsorted results
            if start_idx >= len(df) or end_idx > len(df) or start_idx >= end_idx:
                continue
                
            sess_open = valid_sessions[i]['open']
            if sess_open is None or sess_open <= 0: continue
            
            # Use the integer Unix timestamps from our pre-converted array
            base_ts_unix = int(valid_starts[i].timestamp())
            
            # Slicing numpy array using Unix seconds
            # Use searchsorted on the Unix array
            start_idx_val = np.searchsorted(np_ts_unix, base_ts_unix)
            end_ts_unix = base_ts_unix + int(duration_hours * 3600)
            end_idx_val = np.searchsorted(np_ts_unix, end_ts_unix)
            
            if start_idx_val >= end_idx_val: continue
            
            chunk_ts_unix = np_ts_unix[start_idx_val:end_idx_val]
            chunk_high = np_high[start_idx_val:end_idx_val]
            chunk_low = np_low[start_idx_val:end_idx_val]
            
            # Vectorized time delta calculation in minutes
            time_deltas_m = (chunk_ts_unix - base_ts_unix) // 60
            
            # Use Prior Close as the initial anchor (V14/V24 Gap Logic)
            sess_anchor = valid_sessions[i].get('prior_close') or sess_open
            if sess_anchor is None or sess_anchor <= 0: continue
            
            # V24 Logic: Chained Session O/U Anchors
            # 1. Asia O/U (18:00-19:30) -> Mins 0-90. Anchors London (540+)
            # 2. London O/U (02:30-03:30) -> Mins 510-570. Anchors NY AM (810+)
            # 3. NY AM O/U (08:00-09:30) -> Mins 840-930. Anchors NY PM (1080+)
            
            # (Already extracted above)
            
            # Calculate O/U Mids for this specific session instance
            asia_ou_mid = sess_open # Fallback
            lon_ou_mid  = sess_open # Fallback
            ny_ou_mid   = sess_open # Fallback
            
            # Asia O/U Mid
            mask_asia = (time_deltas_m >= 0) & (time_deltas_m < 90)
            if mask_asia.any():
                h, l = chunk_high[mask_asia], chunk_low[mask_asia]
                if len(h) > 0: asia_ou_mid = (h.max() + l.min()) / 2.0
                
            # London O/U Mid
            mask_lon = (time_deltas_m >= 510) & (time_deltas_m < 570)
            if mask_lon.any():
                h, l = chunk_high[mask_lon], chunk_low[mask_lon]
                if len(h) > 0: lon_ou_mid = (h.max() + l.min()) / 2.0
                
            # NY AM O/U Mid
            mask_ny = (time_deltas_m >= 840) & (time_deltas_m < 930)
            if mask_ny.any():
                h, l = chunk_high[mask_ny], chunk_low[mask_ny]
                if len(h) > 0: ny_ou_mid = (h.max() + l.min()) / 2.0

            # Apply Dynamic Anchors (V24 Chain)
            anchors = np.full(len(chunk_ts_unix), sess_anchor)
            
            # London (03:00+) -> Asia O/U Mid
            anchors[time_deltas_m >= 540] = asia_ou_mid
            # NY AM (07:30+) -> London O/U Mid
            anchors[time_deltas_m >= 810] = lon_ou_mid
            # NY PM (12:00+) -> NY AM O/U Mid
            anchors[time_deltas_m >= 1080] = ny_ou_mid
            
            norm_high = ((chunk_high - anchors) / anchors) * 100
            norm_low = ((chunk_low - anchors) / anchors) * 100
            
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
                # Parse start time from first session to get base hours/minutes
                from datetime import datetime, timedelta
                s_ts = pd.Timestamp(valid_sessions[0]['start_time'])
                
                # FORCE US/Eastern for labels to avoid UTC drift in display
                if s_ts.tz is not None:
                    s_ts = s_ts.tz_convert('US/Eastern')
                
                base_dt = s_ts.replace(year=2000, month=1, day=1) # Normalize date
            except Exception as e:
                print(f"[DEBUG] Label format error: {e}")
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

        session_rows = []
        for s in sessions:
            date = s.get('date')
            sess_name = s.get('session')
            if not date or not sess_name:
                continue
            session_rows.append({
                'date': date,
                'session': sess_name,
                'status': s.get('status', ''),
                'broken': bool(s.get('broken', False)),
            })

        if not session_rows:
            return []

        session_df = pd.DataFrame(session_rows)
        session_df = session_df.sort_values(['date', 'session'])

        status_pivot = session_df.pivot_table(index='date', columns='session', values='status', aggfunc='last')
        broken_pivot = session_df.pivot_table(index='date', columns='session', values='broken', aggfunc='last')

        # Add previous-session context as shifted columns for transition filters.
        for base_session in ['NY1', 'NY2', 'Asia']:
            if base_session in status_pivot.columns:
                status_pivot[f'Prev {base_session}'] = status_pivot[base_session].shift(1)
            if base_session in broken_pivot.columns:
                broken_pivot[f'Prev {base_session}'] = broken_pivot[base_session].shift(1)

        status_pivot = status_pivot.sort_index()
        broken_pivot = broken_pivot.reindex(status_pivot.index).fillna(False).astype(bool)
        mask = pd.Series(True, index=status_pivot.index)

        # Status filters
        for session_name, required_status in filters.items():
            if not required_status or required_status == 'Any':
                continue
            if session_name not in status_pivot.columns:
                return []

            status_series = status_pivot[session_name].fillna('')
            if required_status in ['Long', 'Short']:
                mask &= status_series.str.startswith(required_status)
            elif required_status in ['True', 'False']:
                mask &= status_series.str.endswith(required_status)
            else:
                mask &= status_series.eq(required_status)

        # Broken filters
        for session_name, required_broken in broken_filters.items():
            if not required_broken or required_broken == 'Any':
                continue
            if session_name not in broken_pivot.columns:
                return []

            is_broken = broken_pivot[session_name]
            if required_broken in ['Broken', 'Yes']:
                mask &= is_broken
            elif required_broken in ['Not Broken', 'No']:
                mask &= ~is_broken

        # Intra-session state filter
        if intra_state and intra_state != 'Any':
            if target_session not in status_pivot.columns:
                return []
            target_status = status_pivot[target_session].fillna('')
            if intra_state in ['Long', 'Short']:
                mask &= target_status.str.startswith(intra_state)
            else:
                mask &= target_status.str.contains(intra_state, regex=False)

        return status_pivot.index[mask].tolist()

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
        ticker = ProfilerService._normalize_ticker(ticker)
        # Create cache key
        cache_key = (
            ticker, 
            target_session, 
            json.dumps(filters, sort_keys=True) if filters else "", 
            json.dumps(broken_filters, sort_keys=True) if broken_filters else "", 
            intra_state
        )
        
        cached_stats = ProfilerService._cache_get(ProfilerService._filtered_stats_cache, cache_key)
        if cached_stats is not None:
            return cached_stats

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
        
        # 6. Calculate Level Hit Rates
        level_hit_rates = {}
        level_keys = [
            "hit_pdh", "hit_pdm", "hit_pdl", 
            "hit_midnight", "hit_0730", 
            "hit_ny_p12h", "hit_ny_p12m", "hit_ny_p12l",
            "hit_p12h", "hit_p12m", "hit_p12l",
            "hit_p_asia_mid", "hit_p_lon_mid", "hit_p_ny1_mid", "hit_p_ny2_mid"
        ]
        
        total_matched = len(target_sessions) if target_sessions else 1
        for k in level_keys:
            hits = sum(1 for s in target_sessions if s.get(k, False))
            level_hit_rates[k] = round((hits / total_matched) * 100, 1) if target_sessions else 0
            
        # 7. HOD / LOD Timing Distribution
        def get_time_buckets(sessions, field):
            buckets = {}
            for s in sessions:
                t = s.get(field)
                if t:
                    # Round to 15m bucket for cleaner table display
                    try:
                        h, m = map(int, t.split(':'))
                        m_bucket = (m // 15) * 15
                        t_bucket = f"{h:02d}:{m_bucket:02d}"
                        buckets[t_bucket] = buckets.get(t_bucket, 0) + 1
                    except: continue
            return buckets

        hod_timing = get_time_buckets(target_sessions, 'high_time')
        lod_timing = get_time_buckets(target_sessions, 'low_time')

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
                'start_time': s.get('start_time'), # Required for PriceModel path generation
                'end_time': s.get('end_time'),
                'open': s.get('open') or s.get('price'), # Required for PriceModel normalization
                'range_high': s.get('range_high'), # Required for Daily range calc
                'range_low': s.get('range_low'),
                'mid': s.get('mid'),
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
            "level_hit_rates": level_hit_rates,
            "hod_timing": hod_timing,
            "lod_timing": lod_timing,
            "sessions": lean_sessions, # Reduced size payload
            "target_session": target_session,
            "filters_applied": filters or {},
            "broken_filters_applied": broken_filters or {}
        }
        
        ProfilerService._cache_set(
            ProfilerService._filtered_stats_cache,
            cache_key,
            result,
            ProfilerService._MAX_FILTERED_STATS_CACHE,
        )
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
        ticker = ProfilerService._normalize_ticker(ticker)
        # Create cache key
        cache_key = (
            ticker, 
            target_session, 
            json.dumps(filters, sort_keys=True) if filters else "", 
            json.dumps(broken_filters, sort_keys=True) if broken_filters else "", 
            intra_state, 
            bucket_minutes
        )
        
        cached_price_model = ProfilerService._cache_get(ProfilerService._price_model_cache, cache_key)
        if cached_price_model is not None:
            return cached_price_model

        # 1. Get filtered stats (which includes matched dates)
        stats = ProfilerService.get_filtered_stats(
            ticker, target_session, filters, broken_filters, intra_state
        )
        
        if "error" in stats:
            return stats
        
        # 2. Extract matched sessions or dates
        # get_filtered_stats returns 'sessions' (filtered list of ALL sessions on matched dates)
        all_matched_sessions = stats.get('sessions', [])
        
        # 3. Filter for specific target session or construct Daily
        matched_sessions = []
        
        if target_session == 'Daily':
            # Construct synthetic Daily sessions (18:00 -> 16:00 next day)
            # We need to find the unique dates and build a daily session for each
            unique_dates = sorted(list(set(s['date'] for s in all_matched_sessions)))
            
            # We need 'Asia' sessions to get the correct open price and start time (18:00 prev day)
            # Find Asia session for each date
            asia_map = {s['date']: s for s in all_matched_sessions if s['session'] == 'Asia'}
            
            for d in unique_dates:
                # If we have the Asia session, use its open/start
                # If not (maybe filtered out?), we might need to look it up or skip
                # But get_filtered_stats returns sessions for *matched dates*. 
                # If Asia was part of the filter criteria, it should be there.
                # If filter was "NY1 Long", Asia might be present if we returned all sessions for that date.
                # Yes, get_filtered_stats returns all sessions for the date.
                
                if d in asia_map:
                    asia = asia_map[d]
                    matched_sessions.append({
                        'start_time': asia['start_time'], 
                        # Daily duration ~22h. End time is mostly for reference in generator bounds check
                        'end_time': (pd.Timestamp(asia['end_time']) + pd.Timedelta(hours=22)).isoformat(), 
                        'open': asia['open'],
                        'session': 'Daily',
                        'date': d
                    })
        else:
            # Strict filter for the requested session type
            matched_sessions = [s for s in all_matched_sessions if s.get('session') == target_session]

        if not matched_sessions:
            return {"median": [], "extreme": [], "count": 0}

        # 4. Generate Composite Path
        # Determine duration
        duration = 7.0
        if target_session == 'Daily':
            duration = 22.0
        elif target_session == 'Asia':
            duration = 8.0 # 18:00 - 02:00
        elif target_session == 'London':
            duration = 6.0
        elif target_session == 'NY1':
            duration = 6.0 # 07:30 - 13:30? (Usually 4-6h is enough for view)
        elif target_session == 'NY2':
            duration = 5.0 # 11:30 - 16:30
            
        result = ProfilerService.generate_composite_path(
            ticker, matched_sessions, duration_hours=duration, bucket_minutes=bucket_minutes
        )
        
        # Cache Result
        ProfilerService._cache_set(
            ProfilerService._price_model_cache,
            cache_key,
            result,
            ProfilerService._MAX_PRICE_MODEL_CACHE,
        )
        return result

    @staticmethod
    def get_daily_hod_lod(ticker: str, unadjusted: bool = False) -> Dict:
        """
        Get pre-computed true daily HOD/LOD times.
        Buffered in memory to avoid repeated disk I/O (1MB+).
        """
        ticker = ProfilerService._normalize_ticker(ticker)
        cache_key = f"{ticker}_unadjusted" if unadjusted else ticker
        
        cached_hod_lod = ProfilerService._cache_get(ProfilerService._daily_hod_lod_cache, cache_key)
        if cached_hod_lod is not None:
            return cached_hod_lod
            
        filename = f"{ticker}_daily_hod_lod_unadjusted.json" if unadjusted else f"{ticker}_daily_hod_lod.json"
        json_path = DATA_DIR / filename
        
        if not json_path.exists():
            return {"error": f"Daily HOD/LOD data for {ticker} ({'Unadjusted' if unadjusted else 'Adjusted'}) not found."}
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            ProfilerService._cache_set(
                ProfilerService._daily_hod_lod_cache,
                cache_key,
                data,
                ProfilerService._MAX_DAILY_HOD_LOD_CACHE,
            )
            return data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_level_touches(ticker: str) -> Dict:
        """
        Get pre-computed reference level touch data.
        Buffered in memory to avoid repeated disk I/O.
        OPTIMIZED: Returns only the first hit per session to reduce payload size.
        """
        ticker = ProfilerService._normalize_ticker(ticker)
        cached_level_touches = ProfilerService._cache_get(ProfilerService._level_touches_cache, ticker)
        if cached_level_touches is not None:
            return cached_level_touches
            
        json_path = DATA_DIR / f"{ticker}_level_touches.json"
        
        if not json_path.exists():
            return {"error": f"Level touch data for {ticker} not found."}
        
        try:
            with open(json_path, 'r') as f:
                raw_data = json.load(f)
                
            # Optimize Payload: Convert raw touch_times list to first_hit dict per session
            # Matches ranges in daily-levels.tsx
            SESSION_RANGES = {
                'Asia':   {'start': 18*60, 'end': 41*60}, # 18:00 - 17:00 (next day)
                'London': {'start': 26*60, 'end': 41*60}, # 02:00 - 17:00
                'NY1':    {'start': 32*60, 'end': 41*60}, # 08:00 - 17:00
                'NY2':    {'start': 36*60, 'end': 41*60}, # 12:00 - 17:00
                'P12':    {'start': 30*60, 'end': 41*60}, # 06:00 - 17:00
                'Daily':  {'start': 18*60, 'end': 41*60}  # 18:00 - 17:00 (next day)
            }
            
            # Flatten all touch events into records; collect untouched levels separately.
            # OPTIMIZED: vectorized session-range check replaces O(dates*levels*touches*sessions) scan.
            touch_records: list = []
            untouched_map: dict = {}

            for date_key, day_levels in raw_data.items():
                for level_name, level_data in day_levels.items():
                    if not isinstance(level_data, dict):
                        continue
                    touched      = level_data.get('touched', False)
                    level_val    = level_data.get('level')
                    touch_times  = level_data.get('touch_times', [])

                    if not touched or not touch_times:
                        untouched_map.setdefault(date_key, {})[level_name] = {
                            'level': level_val, 'touched': False, 'hits': {}
                        }
                        continue

                    for t in touch_times:
                        try:
                            h, m = map(int, t.split(':'))
                            touch_records.append({
                                'date': date_key, 'level_name': level_name,
                                'level_val': level_val, 'mins': h * 60 + m, 'time_str': t
                            })
                        except Exception:
                            pass

            # Seed output with untouched levels
            optimized_data: dict = {d: dict(lvls) for d, lvls in untouched_map.items()}

            if touch_records:
                df_t = pd.DataFrame(touch_records).sort_values('mins')
                # Level metadata: canonical level_val per (date, level_name)
                meta = df_t.groupby(['date', 'level_name'])['level_val'].first()

                # Vectorized first-hit per (date, level, session).
                # Session ranges store minutes relative to a 41-hour trading day window
                # (18:00 prev day = 1080 → 17:00 = 2460). Raw touch mins are 0-1439;
                # touches after-midnight are matched via mins+1440.
                session_hits: dict = {}  # (date_key, level_name) -> {sess_name: time_str}
                for sess_name, rng in SESSION_RANGES.items():
                    start, end = rng['start'], rng['end']
                    direct  = (df_t['mins'] >= start) & (df_t['mins'] < end)
                    wrapped = ((df_t['mins'] + 1440) >= start) & ((df_t['mins'] + 1440) < end)
                    in_rng  = df_t[direct | wrapped]
                    if in_rng.empty:
                        continue
                    # .sort_values('mins') already applied; .first() yields earliest touch
                    first_hits = in_rng.groupby(['date', 'level_name'])['time_str'].first()
                    for (date_k, level_n), time_val in first_hits.items():
                        session_hits.setdefault((date_k, level_n), {})[sess_name] = time_val

                # Build output for touched levels (with ≥1 session hit)
                for (date_k, level_n), hits in session_hits.items():
                    optimized_data.setdefault(date_k, {})[level_n] = {
                        'level': meta.get((date_k, level_n)),
                        'touched': True,
                        'hits': hits,
                    }
                # Touched levels that matched no session range
                all_touched = set(zip(df_t['date'], df_t['level_name']))
                for date_k, level_n in all_touched - set(session_hits.keys()):
                    optimized_data.setdefault(date_k, {})[level_n] = {
                        'level': meta.get((date_k, level_n)),
                        'touched': True,
                        'hits': {},
                    }

            ProfilerService._cache_set(
                ProfilerService._level_touches_cache,
                ticker,
                optimized_data,
                ProfilerService._MAX_LEVEL_TOUCHES_CACHE,
            )
            return optimized_data
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def prewarm_cache(ticker: str = "NQ1", sessions: Optional[List[str]] = None):
        """
        Run heavy calculations on startup to populate cache.
        """
        print(f"[Pre-Warm] Warming cache for {ticker}...")
        try:
            # 1. Load Static Files
            ProfilerService.get_daily_hod_lod(ticker)
            ProfilerService.get_level_touches(ticker)
            
            # 2. Run Heavy Price Model Calculation (selected sessions only)
            if sessions is None:
                env_sessions = os.getenv("PROFILER_PREWARM_SESSIONS", "NY1")
                selected_sessions = [s.strip() for s in env_sessions.split(",") if s.strip()]
            else:
                selected_sessions = sessions

            for session_name in selected_sessions:
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

    @staticmethod
    def _load_df(ticker: str) -> Optional[pd.DataFrame]:
        """
        Unified method to load OHLCV data with perfect Unix -> EST alignment.
        """
        # Check Cache
        cached_df = ProfilerService._cache_get(ProfilerService._cache, ticker)
        if cached_df is not None:
            return cached_df
            
        try:
            # Use robust loader to get synchronized Unix timestamps
            from api.features.shared.data_loader import load_parquet
            df = load_parquet(ticker, "1m")
            
            if df is None or df.empty:
                return None
            
            required = {"time", "high", "low"}
            if not required.issubset(df.columns):
                return None

            # Keep only columns required for composite path generation.
            # This avoids holding millions of unnecessary string/numeric fields in memory.
            df = df[["time", "high", "low"]].copy()
            idx = pd.to_datetime(df["time"].to_numpy(), unit='s', utc=True).tz_convert('US/Eastern')
            df = df.drop(columns=["time"])
            df.index = idx
            df.index.name = "dt_utc"

            ProfilerService._cache_set(
                ProfilerService._cache,
                ticker,
                df,
                ProfilerService._MAX_DF_CACHE,
            )
            return df
        except Exception as e:
            print(f"[Profiling] Load error for {ticker}: {e}")
            return None
    @staticmethod
    def _load_prediction_data(target: str) -> Dict:
        """Load prediction JSONs with caching."""
        ticker = "NQ1"  # Currently hardcoded as we only generated NQ1 data
        cache_key = f"{ticker}_{target}"
        
        cached_prediction = ProfilerService._cache_get(ProfilerService._prediction_cache, cache_key)
        if cached_prediction is not None:
            return cached_prediction
            
        from api.features.shared.data_loader import DATA_DIR
        filename = f"{ticker}_{target}_predictions.json"
        path = DATA_DIR / filename
        
        try:
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                ProfilerService._cache_set(
                    ProfilerService._prediction_cache,
                    cache_key,
                    data,
                    ProfilerService._MAX_PREDICTION_CACHE,
                )
                return data
            return {}
        except Exception as e:
            print(f"[ProfilerService] Error loading prediction data: {e}")
            return {}

    @staticmethod
    def get_asia_prediction(prev_ny1: str, prev_ny2: str) -> Dict:
        """
        Get outcome probabilities for Asia session based on previous NY1/NY2 context.
        """
        data = ProfilerService._load_prediction_data("asia")
        context_key = f"{prev_ny1}|{prev_ny2}"
        
        if context_key in data:
            return data[context_key]
        
        # Fallback or empty result
        return {"error": f"No historical match for context: {context_key}"}

    @staticmethod
    def get_london_prediction(prev_ny2: str, curr_asia: str) -> Dict:
        """
        Get outcome probabilities for London session based on previous NY2 and current Asia context.
        """
        data = ProfilerService._load_prediction_data("london")
        context_key = f"{prev_ny2}|{curr_asia}"
        
        if context_key in data:
            return data[context_key]
            
        return {"error": f"No historical match for context: {context_key}"}
