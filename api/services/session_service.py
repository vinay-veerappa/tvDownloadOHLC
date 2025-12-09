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
        if df.empty:
            return []
        
        results = []

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        def safe_float(val):
            if pd.isna(val) or val is None: return None
            return float(val)

        # 1. Calculate Daily Aggregates (PDH, PDL, PD-Mid)
        # We resample to Daily (1D) to get OHLC for each day
        # Shift by 1 to get "Previous Day" relative to "Today"
        daily = df.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        daily['mid'] = (daily['high'] + daily['low']) / 2
        # Normalize index to be timezone-naive for easier lookup with date_obj
        if daily.index.tz is not None:
            daily.index = daily.index.tz_localize(None)
        prev_daily = daily.shift(1) # Row for 2024-12-05 contains data from 2024-12-04

        # 2. Calculate Weekly Aggregates (Previous Week Close)
        # Resample to Weekly (Ending Friday or distinct weeks?)
        # 'W-FRI' aligns strictly to weeks ending Friday
        weekly = df.resample('W-FRI').agg({'close': 'last'})
        if weekly.index.tz is not None:
            weekly.index = weekly.index.tz_localize(None)
        prev_weekly = weekly.shift(1)

        # 3. Helpers for specific times
        def get_price_at_time(d_data, t_str, date_ref):
            try:
                # Use passed date_ref instead of d_data.name (which fails on DataFrame)
                ts = pd.Timestamp.combine(date_ref, pd.to_datetime(t_str).time())
                if d_data.index.tz:
                    ts = ts.tz_localize(d_data.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                # Find exact or nearest forward
                idx = d_data.index.searchsorted(ts)
                if idx < len(d_data):
                    row = d_data.iloc[idx]
                    # Check tolerance (e.g. 30 mins)
                    if (row.name - ts).total_seconds() < 1800:
                        return row['open']
            except:
                pass
            return None

        # Main Loop: Group by Date
        grouped = df.groupby(df.index.date)
        
        for date_obj, day_data in grouped:
            date_str = date_obj.strftime('%Y-%m-%d')
            date_ts = pd.Timestamp(date_str)
            if day_data.empty: continue

            # --- Base Sessions (Asia, London, NY) ---
            session_defs = [
                {"name": "Asia", "start": "18:00", "end": "19:30"},
                {"name": "London", "start": "02:30", "end": "03:30"},
                {"name": "NY1", "start": "07:30", "end": "08:30"},
                {"name": "NY2", "start": "11:30", "end": "12:30"},
            ]

            # Midnight Open (00:00)
            mid_price = get_price_at_time(day_data, "00:00", date_obj)
            if mid_price is not None:
                 val = safe_float(mid_price)
                 if val is not None:
                    results.append({
                        "date": date_str, "session": "MidnightOpen",
                        "start_time": pd.Timestamp.combine(date_obj, time(0,0)).isoformat(),
                        "price": val
                    })

            # 7:30 Open
            open_730 = get_price_at_time(day_data, "07:30", date_obj)
            if open_730 is not None:
                val = safe_float(open_730)
                if val is not None:
                    results.append({
                        "date": date_str, "session": "Open730",
                        "start_time": pd.Timestamp.combine(date_obj, time(7,30)).isoformat(),
                        "price": val
                    })
            
            # Standard Session Ranges
            for sess in session_defs:
                start_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["start"]).time())
                end_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["end"]).time())
                
                if df.index.tz:
                    try:
                        start_t = start_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                        end_t = end_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                    except: continue

                if pd.isna(start_t) or pd.isna(end_t): continue
                
                range_data = day_data[(day_data.index >= start_t) & (day_data.index < end_t)]
                if not range_data.empty:
                    high = range_data['high'].max()
                    low = range_data['low'].min()
                    mid = (high + low) / 2
                    
                    results.append({
                        "date": date_str, "session": sess["name"],
                        "start_time": start_t.isoformat(), "end_time": end_t.isoformat(),
                        "high": safe_float(high), "low": safe_float(low), "mid": safe_float(mid)
                    })
                    
                    if sess["name"] == "Asia":
                        # Emit GlobexOpen line using Asia open
                         op = safe_float(range_data.iloc[0]['open'])
                         if op is not None:
                            results.append({
                                "date": date_str, "session": "GlobexOpen",
                                "start_time": start_t.isoformat(),
                                "price": op
                            })

            # --- Previous Day Levels (PDH, PDL, PDMid) ---
            # Retrieve from pre-calculated `prev_daily` (naive index lookup)
            if date_ts in prev_daily.index:
                p_row = prev_daily.loc[date_ts]
                if not pd.isna(p_row['high']):
                    s_iso = pd.Timestamp.combine(date_obj, time(0,0)).isoformat()
                    results.append({"date": date_str, "session": "PDH", "start_time": s_iso, "price": safe_float(p_row['high'])})
                    results.append({"date": date_str, "session": "PDL", "start_time": s_iso, "price": safe_float(p_row['low'])})
                    results.append({"date": date_str, "session": "PDMid", "start_time": s_iso, "price": safe_float(p_row['mid'])})

            # --- Previous Week Close ---
            try:
                last_wk_idx = prev_weekly.index.asof(date_ts)
                if pd.notna(last_wk_idx):
                    last_wk = prev_weekly.loc[last_wk_idx]
                    s_iso = pd.Timestamp.combine(date_obj, time(0,0)).isoformat()
                    val = safe_float(last_wk['close'])
                    if val is not None:
                        results.append({"date": date_str, "session": "PWeeklyClose", "start_time": s_iso, "price": val})
            except Exception as e: 
                pass

            # --- Opening Range ---
            or_start = pd.Timestamp.combine(date_obj, time(9, 30))
            if df.index.tz: 
                try:
                    or_start = or_start.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                except: continue
            or_end = or_start + pd.Timedelta(minutes=1)
            try:
                or_data = df.loc[or_start:or_end] # Slicing df (Timezone Aware)
                or_data = or_data[or_data.index < or_end]
                if not or_data.empty:
                    h, l = or_data['high'].max(), or_data['low'].min()
                    results.append({
                        "date": date_str, "session": "OpeningRange",
                        "start_time": or_start.isoformat(), "end_time": or_end.isoformat(),
                        "high": safe_float(h), "low": safe_float(l), "mid": safe_float((h + l) / 2)
                    })
            except: pass
        
        # --- 4. Post-Loop: 12H Session Generation ---
        try:
           res_12h = df.resample('12H', offset='6H').agg({'high':'max', 'low':'min'})
           res_12h['mid'] = (res_12h['high'] + res_12h['low']) / 2
           shifted_12h = res_12h.shift(1) 
           
           for ts, row in shifted_12h.iterrows():
               if pd.isna(row['high']): continue
               end_ts = ts + pd.Timedelta(hours=12)
               results.append({
                   "date": ts.strftime('%Y-%m-%d'),
                   "session": "P12", 
                   "start_time": ts.isoformat(),
                   "end_time": end_ts.isoformat(),
                   "high": safe_float(row['high']),
                   "low": safe_float(row['low']),
                   "mid": safe_float(row['mid'])
               })
        except Exception as e:
            print(f"Error calculating 12H sessions: {e}")

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

        def safe_float(val):
            if pd.isna(val) or val is None: return None
            return float(val)

        for date_obj in unique_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            start_ts = pd.Timestamp.combine(date_obj, target_time)
            if df.index.tz: start_ts = start_ts.tz_localize(df.index.tz)
            
            end_ts = start_ts + pd.Timedelta(minutes=duration)
            
            try:
                range_data = df.loc[start_ts:end_ts] 
                range_data = range_data[range_data.index < end_ts]
                
                if not range_data.empty:
                    high = range_data['high'].max()
                    low = range_data['low'].min()
                    mid = (high + low) / 2
                    
                    results.append({
                        "date": date_str,
                        "session": name,
                        "start_time": start_ts.isoformat(),
                        "end_time": end_ts.isoformat(),
                        "high": safe_float(high),
                        "low": safe_float(low),
                        "mid": safe_float(mid)
                    })
            except KeyError:
                 continue
        return results
