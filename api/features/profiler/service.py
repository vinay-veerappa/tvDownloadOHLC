
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
    _pivoted_cache = OrderedDict()  # Cache for pre-pivoted session DataFrames

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
            ProfilerService._pivoted_cache.clear()
        else:
            ProfilerService._cache.clear()
            ProfilerService._json_cache.clear()
            ProfilerService._price_model_cache.clear()
            ProfilerService._level_touches_cache.clear()
            ProfilerService._daily_hod_lod_cache.clear()
            ProfilerService._filtered_stats_cache.clear()
            ProfilerService._prediction_cache.clear()
            ProfilerService._pivoted_cache.clear()
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
        
        # 4. Extract Data Arrays (Optimized: NumPy / Aligned 2D Matrix)
        max_len = int(duration_hours * 60) + 1
        use_matrix = (bucket_minutes == 1)
        
        if use_matrix:
            high_matrix = np.full((len(valid_sessions), max_len), np.nan, dtype=np.float32)
            low_matrix = np.full((len(valid_sessions), max_len), np.nan, dtype=np.float32)
        else:
            all_time_idxs = []
            all_norm_highs = []
            all_norm_lows = []
            
        # Pre-fetch numpy arrays (Zero Copy views)
        np_high = df['high'].values
        np_low = df['low'].values
        
        # Use absolute Unix seconds for the index (converts US/Eastern -> UTC Unix)
        np_ts_unix = df.index.astype('int64').to_numpy() // 10**9

        is_daily = len(valid_sessions) > 0 and valid_sessions[0].get('session') == 'Daily'
        for i, (start_idx, end_idx) in enumerate(zip(start_locs, end_locs)):
            # Bounds check for searchsorted results
            if start_idx >= len(df) or end_idx > len(df) or start_idx >= end_idx:
                continue
                
            sess_open = valid_sessions[i]['open']
            if sess_open is None or sess_open <= 0: continue
            
            start_idx_val = start_idx
            end_idx_val = end_idx
            
            # Use the integer Unix timestamps from our pre-converted array
            base_ts_unix = int(valid_starts[i].timestamp())
            
            chunk_ts_unix = np_ts_unix[start_idx_val:end_idx_val]
            chunk_high = np_high[start_idx_val:end_idx_val]
            chunk_low = np_low[start_idx_val:end_idx_val]
            
            # Vectorized time delta calculation in minutes
            time_deltas_m = (chunk_ts_unix - base_ts_unix) // 60
            
            # Use Prior Close as the initial anchor (V14/V24 Gap Logic)
            sess_anchor = valid_sessions[i].get('prior_close') or sess_open
            if sess_anchor is None or sess_anchor <= 0: continue
            
            if is_daily:
                # Calculate O/U Mids for this specific session instance using fast binary search slicing
                # Batch searchsorted calls to minimize Python interpreter overhead (V24 Chain)
                target_times = [
                    base_ts_unix,
                    base_ts_unix + 90 * 60,
                    base_ts_unix + 510 * 60,
                    base_ts_unix + 570 * 60,
                    base_ts_unix + 840 * 60,
                    base_ts_unix + 930 * 60,
                    base_ts_unix + 540 * 60,
                    base_ts_unix + 810 * 60,
                    base_ts_unix + 1080 * 60
                ]
                indices = np.searchsorted(chunk_ts_unix, target_times)
                idx_asia_start, idx_asia_end = indices[0], indices[1]
                idx_lon_start, idx_lon_end = indices[2], indices[3]
                idx_ny_start, idx_ny_end = indices[4], indices[5]
                idx_540, idx_810, idx_1080 = indices[6], indices[7], indices[8]
                
                h_asia = chunk_high[idx_asia_start:idx_asia_end]
                l_asia = chunk_low[idx_asia_start:idx_asia_end]
                asia_ou_mid = sess_open
                if len(h_asia) > 0:
                    asia_ou_mid = (h_asia.max() + l_asia.min()) / 2.0
                    
                # London O/U Mid (510 to 570 min)
                h_lon = chunk_high[idx_lon_start:idx_lon_end]
                l_lon = chunk_low[idx_lon_start:idx_lon_end]
                lon_ou_mid = sess_open
                if len(h_lon) > 0:
                    lon_ou_mid = (h_lon.max() + l_lon.min()) / 2.0
                    
                # NY AM O/U Mid (840 to 930 min)
                h_ny = chunk_high[idx_ny_start:idx_ny_end]
                l_ny = chunk_low[idx_ny_start:idx_ny_end]
                ny_ou_mid = sess_open
                if len(h_ny) > 0:
                    ny_ou_mid = (h_ny.max() + l_ny.min()) / 2.0

                # Apply Dynamic Anchors (V24 Chain) using binary search slices
                anchors = np.full(len(chunk_ts_unix), sess_anchor)
                
                anchors[idx_540:idx_810] = asia_ou_mid
                anchors[idx_810:idx_1080] = lon_ou_mid
                anchors[idx_1080:] = ny_ou_mid
            else:
                anchors = sess_anchor
            
            norm_high = ((chunk_high - anchors) / anchors) * 100
            norm_low = ((chunk_low - anchors) / anchors) * 100
            
            if use_matrix:
                mask = (time_deltas_m >= 0) & (time_deltas_m < max_len)
                valid_deltas = time_deltas_m[mask]
                high_matrix[i, valid_deltas] = norm_high[mask]
                low_matrix[i, valid_deltas] = norm_low[mask]
            else:
                # Bucketing Logic
                if bucket_minutes > 1:
                    time_idxs = (time_deltas_m // bucket_minutes) * bucket_minutes
                else:
                    time_idxs = time_deltas_m
                    
                all_time_idxs.append(time_idxs)
                all_norm_highs.append(norm_high)
                all_norm_lows.append(norm_low)

        # Helper to format time
        base_dt = None
        if valid_sessions:
            try:
                from datetime import datetime, timedelta
                s_ts = pd.Timestamp(valid_sessions[0]['start_time'])
                
                # FORCE US/Eastern for labels to avoid UTC drift in display
                if s_ts.tz is not None:
                    s_ts = s_ts.tz_convert('US/Eastern')
                
                base_dt = s_ts.replace(year=2000, month=1, day=1) # Normalize date
            except Exception as e:
                print(f"[DEBUG] Label format error: {e}")
                pass

        avg_path = []
        ext_path = []

        if use_matrix:
            # Check if NaNs exist to choose between fast np.median and np.nanmedian
            # Wrap in errstate to suppress All-NaN warnings for early closures
            with np.errstate(all='ignore'):
                if np.isnan(high_matrix).any():
                    median_high = np.nanmedian(high_matrix, axis=0)
                else:
                    median_high = np.median(high_matrix, axis=0)
                    
                if np.isnan(low_matrix).any():
                    median_low = np.nanmedian(low_matrix, axis=0)
                else:
                    median_low = np.median(low_matrix, axis=0)
                    
                max_high = np.nanmax(high_matrix, axis=0)
                min_low = np.nanmin(low_matrix, axis=0)
            
            # Filter valid time indices (ignore where median_high is NaN)
            indices = np.arange(max_len)
            valid_mask = ~np.isnan(median_high)
            indices = indices[valid_mask]
            median_high = median_high[valid_mask]
            max_high = max_high[valid_mask]
            median_low = median_low[valid_mask]
            min_low = min_low[valid_mask]
            
            # Precompute time strings
            time_strs = []
            if base_dt:
                for m in range(max_len + 100):
                    curr_dt = base_dt + timedelta(minutes=m)
                    time_strs.append(curr_dt.strftime("%H:%M"))
                    
            for i, idx in enumerate(indices):
                time_str = time_strs[idx] if base_dt else ""
                avg_path.append({
                    "time_idx": int(idx),
                    "time": time_str,
                    "high": round(float(median_high[i]), 3),
                    "low": round(float(median_low[i]), 3)
                })
                ext_path.append({
                    "time_idx": int(idx),
                    "time": time_str,
                    "high": round(float(max_high[i]), 3),
                    "low": round(float(min_low[i]), 3)
                })
        else:
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
            
            # Precompute time strings
            time_strs = []
            if base_dt:
                max_idx = int(stats.index.max()) + 100
                for m in range(max_idx):
                    curr_dt = base_dt + timedelta(minutes=m)
                    time_strs.append(curr_dt.strftime("%H:%M"))
                    
            indices = stats.index.to_numpy()
            avg_hs = stats[('norm_high', 'median')].to_numpy()
            max_hs = stats[('norm_high', 'max')].to_numpy()
            avg_ls = stats[('norm_low', 'median')].to_numpy()
            min_ls = stats[('norm_low', 'min')].to_numpy()
            
            for i, idx in enumerate(indices):
                time_str = time_strs[idx] if base_dt else ""
                avg_path.append({
                    "time_idx": int(idx),
                    "time": time_str,
                    "high": round(float(avg_hs[i]), 3),
                    "low": round(float(avg_ls[i]), 3)
                })
                ext_path.append({
                    "time_idx": int(idx),
                    "time": time_str,
                    "high": round(float(max_hs[i]), 3),
                    "low": round(float(min_ls[i]), 3)
                })
            
        print(f"[DEBUG] Composite Path Gen Time: {time.time() - start_time:.2f}s (Processed {len(valid_sessions)} sessions)")
        return {
            "median": avg_path,
            "extreme": ext_path,
            "count": len(valid_sessions)
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
        intra_state: str = "Any",
        ticker: str = None
    ) -> List[str]:
        """
        Apply filters and return the list of matching dates (intersection logic).
        
        Args:
            sessions: List of all session dicts
            target_session: The primary session to analyze (e.g., "NY1")
            filters: Dict of session -> status filter (e.g., {"Asia": "Short True"})
            broken_filters: Dict of session -> broken filter (e.g., {"Asia": "Broken"})
            intra_state: "Any", "Long", "Short", etc. for intra-session filtering
            ticker: Optional ticker to cache pivoted DataFrames by ticker instead of list ID
        
        Returns:
            List of matching date strings
        """
        filters = filters or {}
        broken_filters = broken_filters or {}

        cache_key = ticker if ticker else id(sessions)
        cached_pivots = ProfilerService._cache_get(ProfilerService._pivoted_cache, cache_key)
        if cached_pivots is not None:
            status_pivot, broken_pivot = cached_pivots
        else:
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
            
            ProfilerService._cache_set(
                ProfilerService._pivoted_cache,
                cache_key,
                (status_pivot, broken_pivot),
                max_items=8
            )
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
        intra_state: str = "Any",
        start_date: str = None,
        end_date: str = None
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
            intra_state,
            start_date or "",
            end_date or ""
        )
        
        cached_stats = ProfilerService._cache_get(ProfilerService._filtered_stats_cache, cache_key)
        if cached_stats is not None:
            return cached_stats

        # 1. Load all sessions
        stats = ProfilerService.analyze_profiler_stats(ticker, days=10000)
        
        if "error" in stats:
            return stats
        
        all_sessions = stats.get('sessions', [])
        
        # 2. Apply filters to get matched dates
        matched_dates = ProfilerService.apply_filters(
            all_sessions, target_session, filters, broken_filters, intra_state, ticker
        )
        
        # Apply start_date and end_date filters AFTER applying transition filters
        if start_date:
            matched_dates = [d for d in matched_dates if d >= start_date]
        if end_date:
            matched_dates = [d for d in matched_dates if d <= end_date]
            
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
        bucket_minutes: int = 1,
        start_date: str = None,
        end_date: str = None
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
            bucket_minutes,
            start_date or "",
            end_date or ""
        )
        
        cached_price_model = ProfilerService._cache_get(ProfilerService._price_model_cache, cache_key)
        if cached_price_model is not None:
            return cached_price_model

        # 1. Get filtered stats (which includes matched dates)
        stats = ProfilerService.get_filtered_stats(
            ticker, target_session, filters, broken_filters, intra_state, start_date, end_date
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
    def get_daily_hod_lod(ticker: str, unadjusted: bool = False, start_date: str = None, end_date: str = None) -> Dict:
        """
        Get pre-computed true daily HOD/LOD times in a highly optimized columnar format.
        Buffered in memory to avoid repeated disk I/O (1MB+).
        """
        ticker = ProfilerService._normalize_ticker(ticker)
        cache_key = f"{ticker}_unadjusted" if unadjusted else ticker
        
        cached_columnar = ProfilerService._cache_get(ProfilerService._daily_hod_lod_cache, cache_key)
        if cached_columnar is None:
            filename = f"{ticker}_daily_hod_lod_unadjusted.json" if unadjusted else f"{ticker}_daily_hod_lod.json"
            json_path = DATA_DIR / filename
            
            if not json_path.exists():
                return {"error": f"Daily HOD/LOD data for {ticker} ({'Unadjusted' if unadjusted else 'Adjusted'}) not found."}
            
            try:
                with open(json_path, 'r') as f:
                    raw_data = json.load(f)
                
                # Helper to convert HH:MM to minutes
                def time_to_minutes(t):
                    if not t: return -1
                    try:
                        h, m = map(int, t.split(':'))
                        return h * 60 + m
                    except:
                        return -1

                all_dates = sorted(list(raw_data.keys()))
                hod_time = []
                lod_time = []
                hod_price = []
                lod_price = []
                daily_open = []
                daily_high = []
                daily_low = []

                for d in all_dates:
                    entry = raw_data[d]
                    hod_time.append(time_to_minutes(entry.get("hod_time")))
                    lod_time.append(time_to_minutes(entry.get("lod_time")))
                    hod_price.append(entry.get("hod_price") or 0.0)
                    lod_price.append(entry.get("lod_price") or 0.0)
                    daily_open.append(entry.get("daily_open") or 0.0)
                    daily_high.append(entry.get("daily_high") or 0.0)
                    daily_low.append(entry.get("daily_low") or 0.0)

                cached_columnar = {
                    "dates": all_dates,
                    "hod_time": hod_time,
                    "lod_time": lod_time,
                    "hod_price": hod_price,
                    "lod_price": lod_price,
                    "daily_open": daily_open,
                    "daily_high": daily_high,
                    "daily_low": daily_low
                }
                
                ProfilerService._cache_set(
                    ProfilerService._daily_hod_lod_cache,
                    cache_key,
                    cached_columnar,
                    ProfilerService._MAX_DAILY_HOD_LOD_CACHE,
                )
            except Exception as e:
                return {"error": str(e)}

        # Apply optional date filtering to columnar data
        dates = cached_columnar["dates"]
        if not start_date and not end_date:
            return cached_columnar
            
        indices = [i for i, d in enumerate(dates) if (not start_date or d >= start_date) and (not end_date or d <= end_date)]
        if len(indices) == len(dates):
            return cached_columnar
            
        return {
            "dates": [dates[i] for i in indices],
            "hod_time": [cached_columnar["hod_time"][i] for i in indices],
            "lod_time": [cached_columnar["lod_time"][i] for i in indices],
            "hod_price": [cached_columnar["hod_price"][i] for i in indices],
            "lod_price": [cached_columnar["lod_price"][i] for i in indices],
            "daily_open": [cached_columnar["daily_open"][i] for i in indices],
            "daily_high": [cached_columnar["daily_high"][i] for i in indices],
            "daily_low": [cached_columnar["daily_low"][i] for i in indices]
        }

    @staticmethod
    def get_level_touches(ticker: str, start_date: str = None, end_date: str = None) -> Dict:
        """
        Get pre-computed reference level touch data.
        Buffered in memory to avoid repeated disk I/O.
        Returns a highly optimized columnar JSON structure.
        """
        ticker = ProfilerService._normalize_ticker(ticker)
        
        # We cache the fully built, unfiltered columnar dictionary in memory
        cached_columnar = ProfilerService._cache_get(ProfilerService._level_touches_cache, ticker)
        
        if cached_columnar is None:
            # 1. Try loading precomputed columnar json from disk
            columnar_path = DATA_DIR / f"{ticker}_level_touches_columnar.json"
            if columnar_path.exists():
                try:
                    with open(columnar_path, 'r') as f:
                        cached_columnar = json.load(f)
                    ProfilerService._cache_set(
                        ProfilerService._level_touches_cache,
                        ticker,
                        cached_columnar,
                        ProfilerService._MAX_LEVEL_TOUCHES_CACHE,
                    )
                except Exception as e:
                    print(f"Error loading columnar levels for {ticker}: {e}")
                    cached_columnar = None

        # 2. If not found, compute it from the raw JSON file
        if cached_columnar is None:
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
                touch_records = []
                untouched_map = {}

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
                raw_processed = {d: dict(lvls) for d, lvls in untouched_map.items()}

                if touch_records:
                    df_t = pd.DataFrame(touch_records).sort_values('mins')
                    # Level metadata: canonical level_val per (date, level_name)
                    meta = df_t.groupby(['date', 'level_name'])['level_val'].first()

                    # Vectorized first-hit per (date, level, session).
                    session_hits = {}  # (date_key, level_name) -> {sess_name: time_str}
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
                        raw_processed.setdefault(date_k, {})[level_n] = {
                            'level': meta.get((date_k, level_n)),
                            'touched': True,
                            'hits': hits,
                        }
                    # Touched levels that matched no session range
                    all_touched = set(zip(df_t['date'], df_t['level_name']))
                    for date_k, level_n in all_touched - set(session_hits.keys()):
                        raw_processed.setdefault(date_k, {})[level_n] = {
                            'level': meta.get((date_k, level_n)),
                            'touched': True,
                            'hits': {},
                        }

                # Helper to convert HH:MM to minutes
                def time_to_minutes(t):
                    if not t: return -1
                    try:
                        h, m = map(int, t.split(':'))
                        return h * 60 + m
                    except:
                        return -1

                # Format to columnar for ALL dates
                all_dates = sorted(list(raw_processed.keys()))
                level_keys = ["pdh", "pdm", "pdl", "p12h", "p12m", "p12l", "ny_p12h", "ny_p12m", "ny_p12l", "daily_open", "midnight_open", "open_0730", "asia_mid", "london_mid", "ny1_mid", "ny2_mid", "prev_asia_mid", "prev_london_mid", "prev_ny1_mid", "prev_ny2_mid"]
                sessions = ["Asia", "London", "NY1", "NY2", "P12", "Daily"]
                
                levels_columnar = {}
                for lk in level_keys:
                    levels_list = []
                    touched_list = []
                    hits_by_session = {s: [] for s in sessions}
                    
                    for d in all_dates:
                        day_data = raw_processed[d]
                        lvl_data = day_data.get(lk)
                        if lvl_data:
                            levels_list.append(lvl_data.get('level') or 0.0)
                            touched_list.append(1 if lvl_data.get('touched') else 0)
                            hits_dict = lvl_data.get('hits', {})
                            for s in sessions:
                                hits_by_session[s].append(time_to_minutes(hits_dict.get(s)))
                        else:
                            levels_list.append(0.0)
                            touched_list.append(0)
                            for s in sessions:
                                hits_by_session[s].append(-1)
                    
                    levels_columnar[lk] = {
                        "level": levels_list,
                        "touched": touched_list,
                        "hits": hits_by_session
                    }

                cached_columnar = {
                    "dates": all_dates,
                    "levels": levels_columnar
                }

                # Save columnar version to disk for instant load next time
                try:
                    columnar_path = DATA_DIR / f"{ticker}_level_touches_columnar.json"
                    with open(columnar_path, 'w') as f:
                        json.dump(cached_columnar, f)
                except Exception as e:
                    print(f"Error saving columnar levels for {ticker}: {e}")

                ProfilerService._cache_set(
                    ProfilerService._level_touches_cache,
                    ticker,
                    cached_columnar,
                    ProfilerService._MAX_LEVEL_TOUCHES_CACHE,
                )
            except Exception as e:
                return {"error": str(e)}

        # 3. Apply optional date filtering to the columnar data
        dates = cached_columnar["dates"]
        if not start_date and not end_date:
            return cached_columnar
            
        indices = [i for i, d in enumerate(dates) if (not start_date or d >= start_date) and (not end_date or d <= end_date)]
        if len(indices) == len(dates):
            return cached_columnar
            
        filtered_dates = [dates[i] for i in indices]
        filtered_levels = {}
        for lk, lvl_data in cached_columnar["levels"].items():
            filtered_levels[lk] = {
                "level": [lvl_data["level"][i] for i in indices],
                "touched": [lvl_data["touched"][i] for i in indices],
                "hits": {
                    s: [lvl_data["hits"][s][i] for i in indices] for s in lvl_data["hits"]
                }
            }
            
        return {
            "dates": filtered_dates,
            "levels": filtered_levels
        }

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
