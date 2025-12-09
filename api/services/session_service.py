import pandas as pd
import numpy as np
from datetime import time, timedelta
from typing import List, Dict, Optional, Tuple

class SessionService:
    @staticmethod
    def calculate_sessions(df: pd.DataFrame) -> List[Dict]:
        """
        Calculates all required session ranges and levels:
        - Asia: 18:00 - 19:30 EST
        - London: 02:30 - 03:30 EST
        - NY1: 07:30 - 08:30 EST
        - NY2: 11:30 - 12:30 EST
        - Midnight Open: 00:00 EST
        
        Returns flat list of session objects.
        """
        results = []
        if df.empty:
            return results

        # Ensure index is datetime and localized to Eastern
        # (Router generally handles this, but safety check)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index) 
        
        # We assume df is already sorted and has DatetimeIndex in ET (or aware)
        # Verify timezone roughly? 
        # For simplicity, we operate on the index properties.
        
        # Define Sessions Config
        # Name, Start(HH:MM), End(HH:MM)
        # Note: London 02:30 is next day relative to Asia 18:00?
        # We process chronologically.
        
        session_defs = [
            {"name": "Asia", "start": "18:00", "end": "19:30"},
            {"name": "London", "start": "02:30", "end": "03:30"},
            {"name": "NY1", "start": "07:30", "end": "08:30"},
            {"name": "NY2", "start": "11:30", "end": "12:30"},
        ]
        
        
        # Optimize: Group by date once instead of repeated masking
        # Note: df.index.date is computed on the fly, so we group by it directly
        # or create a temporary column if needed. Grouping by index property is cleaner.
        
        # Check if empty handled above
        
        # Group by date
        # Use a generator to avoid creating all groups in memory if not needed, 
        # but pandas groupby object is efficient.
        
        # We need to handle timezone awareness. df.index.date returns python date objects (local to index tz).
        # This matches existing logic.
        
        grouped = df.groupby(df.index.date)
        
        for date_obj, day_data in grouped:
            date_str = date_obj.strftime('%Y-%m-%d')
            if day_data.empty: continue

            # 1. Midnight Open (00:00)
            mid_start = pd.Timestamp.combine(date_obj, time(0, 0))
            if df.index.tz: 
                try:
                    mid_start = mid_start.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                except Exception:
                    continue # Skip if date issues
            
            # Find candle at or immediately after 00:00 (tolerance 5 mins?)
            # Used 'asof' logic or simple search
            mid_slice = day_data[day_data.index >= mid_start]
            if not mid_slice.empty:
                first_candle = mid_slice.iloc[0]
                # Check if it's close enough (e.g. within 30 mins, avoiding gap days)
                delta = (first_candle.name - mid_start).total_seconds() / 60
                if delta < 30:
                    results.append({
                        "date": date_str,
                        "session": "MidnightOpen",
                        "start_time": mid_start.isoformat(),
                        "price": float(first_candle['open'])
                    })

            # 2. Ranges
            for sess in session_defs:
                start_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["start"]).time())
                end_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["end"]).time())
                
                if df.index.tz:
                    try:
                        start_t = start_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                        end_t = end_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                    except Exception:
                         continue # Skip invalid times
                
                # Logic gap: Asia 18:00 - 19:30 works on "Date"
                # But London 02:30 works on "Date".
                # If these belong to same "Trading Day", fine. 
                # If 18:00 is Prev Day... this script treats it as Calendar Day.
                # User will see "Asia" on the day it occurred (e.g. Sunday 18:00).
                # This is technically correct for a generic tool.
                
                # Verify timestamps are valid (not NaT)
                if pd.isna(start_t) or pd.isna(end_t): continue

                range_data = day_data[(day_data.index >= start_t) & (day_data.index < end_t)]
                
                if not range_data.empty:
                    high = range_data['high'].max()
                    low = range_data['low'].min()
                    mid = (high + low) / 2
                    
                    results.append({
                        "date": date_str,
                        "session": sess["name"],
                        "start_time": start_t.isoformat(),
                        "end_time": end_t.isoformat(),
                        "high": float(high),
                        "low": float(low),
                        "mid": float(mid)
                    })
            
            # 3. Opening Range (09:30 - 09:31)
            or_start = pd.Timestamp.combine(date_obj, time(9, 30))
            if df.index.tz: 
                try:
                    or_start = or_start.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                except:
                    continue
            or_end = or_start + pd.Timedelta(minutes=1)
            
            try:
                # Use slicing (assuming index sorted)
                or_data = df.loc[or_start:or_end]
                # Filter strictly < or_end
                or_data = or_data[or_data.index < or_end]
                
                if not or_data.empty:
                    h = or_data['high'].max()
                    l = or_data['low'].min()
                    # Pre-calculate quarters? or just send high/low and letting frontend do it?
                    # Frontend usually does mid. Let's send basic high/low.
                    results.append({
                        "date": date_str,
                        "session": "OpeningRange",
                        "start_time": or_start.isoformat(),
                        "end_time": or_end.isoformat(),
                        "high": float(h),
                        "low": float(l),
                        "mid": float((h + l) / 2)
                    })
            except KeyError:
                pass
                    
        return results

    @staticmethod
    def calculate_opening_range(df: pd.DataFrame, start_time: str = "09:30", duration_minutes: int = 1) -> List[Dict]:
        return SessionService._calculate_single_candle_range(df, start_time, duration_minutes, "OpeningRange")

    @staticmethod
    def _calculate_single_candle_range(df: pd.DataFrame, time_str: str, duration: int, name: str) -> List[Dict]:
        results = []
        if df.empty: return results
        
        target_time = pd.to_datetime(time_str).time()
        unique_dates = np.unique(df.index.date)

        for date_obj in unique_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            start_ts = pd.Timestamp.combine(date_obj, target_time)
            if df.index.tz: start_ts = start_ts.tz_localize(df.index.tz)
            
            end_ts = start_ts + pd.Timedelta(minutes=duration)
            
            # Use searchsorted/slicing for efficiency in real prod, bool mask for now
            # Only search within the day to save time?
            # day_mask = df.index.date == date_obj (This is slow inside loop)
            # Better: Loop is separate.
            
            # Slice strictly by timestamp
            # Be careful with slice if index is not sorted (it is).
            try:
                # loc slice? df.loc[start:end]
                range_data = df.loc[start_ts:end_ts] 
                # This might include end_ts exact match.
                # Filter strictly < end_ts if needed.
                range_data = range_data[range_data.index < end_ts]
            except KeyError:
                 continue
            
            if not range_data.empty:
                high = range_data['high'].max()
                low = range_data['low'].min()
                mid = (high + low) / 2
                
                results.append({
                    "date": date_str,
                    "session": name,
                    "start_time": start_ts.isoformat(),
                    "end_time": end_ts.isoformat(),
                    "high": float(high),
                    "low": float(low),
                    # "open": float(range_data.iloc[0]['open']),
                    # "close": float(range_data.iloc[-1]['close']),
                    "mid": float(mid)
                })
        return results
