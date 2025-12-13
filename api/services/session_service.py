import pandas as pd
import numpy as np
from datetime import time, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

class SessionService:
    @staticmethod
    def calculate_sessions(df: pd.DataFrame, ticker: Optional[str] = None) -> List[Dict]:
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

        # Shift index to align Trading Day (18:00 previous day -> 17:00 current day)
        # Adding 6 hours makes 18:00 -> 00:00 (start of next day)
        # So "Tuesday 18:00" becomes "Wednesday 00:00", belonging to Wednesday's trading day.
        df_shifted = df.copy()
        df_shifted.index = df.index + pd.Timedelta(hours=6)

        # 1. Calculate Daily Aggregates (PDH, PDL, PD-Mid) on TRADING DAY
        daily = df_shifted.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        daily['mid'] = (daily['high'] + daily['low']) / 2
        
        # Normalize index to be timezone-naive for easier lookup with date_obj
        if daily.index.tz is not None:
            daily.index = daily.index.tz_localize(None)
        
        # Shift by 1 to get "Previous Day"
        prev_daily = daily.shift(1) 

        # 2. Load Weekly... (unchanged, maybe needs shift too? ignoring for now)
        weekly_df = None
        if ticker:
            try:
                from api.services.data_loader import DATA_DIR
                weekly_file = DATA_DIR / f"{ticker}_1W.parquet"
                if weekly_file.exists():
                    weekly_df = pd.read_parquet(weekly_file)
                    if not isinstance(weekly_df.index, pd.DatetimeIndex): weekly_df.index = pd.to_datetime(weekly_df.index)
                    if weekly_df.index.tz is not None: weekly_df.index = weekly_df.index.tz_localize(None)
            except Exception as e:
                print(f"Warning: Could not load weekly data for {ticker}: {e}")
        
        if weekly_df is None:
            weekly = df.resample('W-FRI').agg({'close': 'last'})
            if weekly.index.tz is not None: weekly.index = weekly.index.tz_localize(None)
            prev_weekly = weekly.shift(1)
        else:
            prev_weekly = weekly_df[['close']].shift(1)

        # 3. Helpers
        def get_price_at_time(d_data, t_str, date_ref):
            try:
                ts = pd.Timestamp.combine(date_ref, pd.to_datetime(t_str).time())
                # If checking 00:00 or 02:30, it is on the 'date_ref' day.
                # If checking 18:00, it is on 'date_ref - 1 day'.
                # But d_data contains the full trading day (18:00 prev -> 17:00 curr).
                # So we just search in d_data.
                
                # Careful: date_ref is the "Trading Date". 
                # e.g. Wednesday. d_data has Tues 18:00 to Wed 17:00.
                # If we ask for "08:00", it is Wed 08:00.
                # If we ask for "18:00", it is ??? 18:00 is START of NEXT day.
                # Usually we want "Globex Open" (18:00 of prev day) or "Midnight Open" (00:00 of curr day).
                
                # We need to construct the correct absolute timestamp for lookup.
                # For 18:00 start, we want (date_ref - 1 day) 18:00.
                # For 00:00, we want date_ref 00:00.
                
                t_obj = pd.to_datetime(t_str).time()
                if t_obj.hour >= 18:
                    ts = pd.Timestamp.combine(date_ref - timedelta(days=1), t_obj)
                else:
                    ts = pd.Timestamp.combine(date_ref, t_obj)
                    
                if d_data.index.tz:
                     ts = ts.tz_localize(d_data.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                
                idx = d_data.index.searchsorted(ts)
                if idx < len(d_data):
                    row = d_data.iloc[idx]
                    if abs((row.name - ts).total_seconds()) < 1800:
                        return row['open']
            except: pass
            return None

        # Main Loop: Group by TRADING Date
        # df_shifted has index shifted by +6H. 
        # So Tuesday 18:00 (+6) -> Wed 00:00.
        # Group by date of shifted index gives "Wednesday".
        # But we need to iterate over original data rows.
        # We can group the original DF by the shifted date.
        
        grouped = df.groupby(df_shifted.index.date)

        
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
            # Standard Session Ranges
            for sess in session_defs:
                t_start = pd.to_datetime(sess["start"]).time()
                t_end = pd.to_datetime(sess["end"]).time()
                
                # If start time is >= 18:00, it belongs to previous calendar day
                if t_start.hour >= 18:
                    start_t = pd.Timestamp.combine(date_obj - timedelta(days=1), t_start)
                else:
                    start_t = pd.Timestamp.combine(date_obj, t_start)
                
                # End time handling:
                # If end time is < start time (crosses midnight)
                # OR if start was shifted back but end is next day?
                # Asia: 18:00 -> 02:00. (18 Prev -> 02 Curr)
                # NY1: 08:00 -> 12:00 (08 Curr -> 12 Curr)
                
                # Logic: If end < start, add 1 day to end.
                # If start was shifted back (18:00), and end is 02:00, 
                # end should be date_obj (02:00). 
                # If we construct end from date_obj, it is 02:00 Current. Correct.
                
                # But if standard logic:
                if t_end < t_start:
                   # This implies crossing midnight relative to start date
                   end_t = pd.Timestamp.combine(start_t.date() + timedelta(days=1), t_end)
                else:
                   # Same day as start
                   end_t = pd.Timestamp.combine(start_t.date(), t_end)
                
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
           res_12h = df.resample('12h', offset='6h').agg({'high':'max', 'low':'min'})
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
    def calculate_hourly(df: pd.DataFrame) -> List[Dict]:
        """
        Calculate hourly and 3-hour profiler data using vectorized operations.
        Returns list of hourly periods with OHLC, 5-min OR, and 3H data.
        
        OPTIMIZED: Uses vectorized operations instead of iterrows()
        """
        if df.empty:
            return []
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # 1. Base Hourly OHLC
        hourly = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        # Filter out empty hours (where open is NaN)
        hourly = hourly.dropna(subset=['open'])
        hourly['mid'] = (hourly['high'] + hourly['low']) / 2
        
        # 2. Vectorized 5-min Opening Range (First 5 mins of each hour)
        # Filter rows where minute < 5
        df_or = df[df.index.minute < 5]
        # Resample to hourly to align with base hourly data
        hourly_or = df_or.resample('1h').agg({'high': 'max', 'low': 'min'})
        
        # 3. Vectorized 1-min Opening Range (First 1 min: minute == 0)
        df_1m = df[df.index.minute == 0]
        hourly_1m = df_1m.resample('1h').agg({'high': 'max', 'low': 'min'})

        # 4. RTH 1-min Range (09:30 - 09:31)
        # Filter for 09:30 candle
        df_rth = df[(df.index.hour == 9) & (df.index.minute == 30)]
        # Map to 09:00 bin by resampling to 1h
        hourly_rth = df_rth.resample('1h').agg({'high': 'max', 'low': 'min'})

        # 5. 3-Hour Blocks (18:00 offset)
        three_hour = df.resample('3h', offset='18h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        three_hour = three_hour.dropna(subset=['open'])
        three_hour['mid'] = (three_hour['high'] + three_hour['low']) / 2

        # Merge all metrics into main hourly dataframe
        # Use suffixes to distinguish columns
        hourly = hourly.join(hourly_or, rsuffix='_or')
        hourly = hourly.join(hourly_1m, rsuffix='_1m')
        hourly = hourly.join(hourly_rth, rsuffix='_rth')

        # OPTIMIZED: Vectorized timestamp calculation
        # Pre-compute start and end times as ISO strings
        hourly.index.name = 'start_ts'  # Ensure consistent column name after reset
        hourly = hourly.reset_index()
        hourly['end_ts'] = hourly['start_ts'] + pd.Timedelta(hours=1)
        
        # Convert timestamps to ISO format strings vectorized
        hourly['start_time'] = hourly['start_ts'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        hourly['end_time'] = hourly['end_ts'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Handle timezone suffix if present
        if hourly['start_ts'].dt.tz is not None:
            # Get timezone offset string
            tz_offset = hourly['start_ts'].iloc[0].strftime('%z')
            tz_str = f"{tz_offset[:3]}:{tz_offset[3:]}" if tz_offset else ""
            hourly['start_time'] = hourly['start_time'] + tz_str
            hourly['end_time'] = hourly['end_time'] + tz_str
        
        # OPTIMIZED: Use to_dict for fast conversion
        # Select and rename columns for output
        hourly_out = hourly[['start_time', 'end_time', 'open', 'high', 'low', 'close', 'mid',
                            'high_or', 'low_or', 'high_1m', 'low_1m', 'high_rth', 'low_rth']].copy()
        hourly_out.columns = ['start_time', 'end_time', 'open', 'high', 'low', 'close', 'mid',
                              'or_high', 'or_low', 'open_1m_high', 'open_1m_low', 'rth_1m_high', 'rth_1m_low']
        
        # Replace NaN with None
        hourly_out = hourly_out.where(pd.notna(hourly_out), None)
        
        # Add type column
        hourly_out['type'] = '1H'
        
        # Convert to list of dicts
        results = hourly_out.to_dict('records')
        
        # Process 3H Data similarly
        if len(three_hour) > 0:
            three_hour.index.name = 'start_ts'  # Ensure consistent column name after reset
            three_hour = three_hour.reset_index()
            three_hour['end_ts'] = three_hour['start_ts'] + pd.Timedelta(hours=3)
            
            three_hour['start_time'] = three_hour['start_ts'].dt.strftime('%Y-%m-%dT%H:%M:%S')
            three_hour['end_time'] = three_hour['end_ts'].dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            if three_hour['start_ts'].dt.tz is not None:
                tz_offset = three_hour['start_ts'].iloc[0].strftime('%z')
                tz_str = f"{tz_offset[:3]}:{tz_offset[3:]}" if tz_offset else ""
                three_hour['start_time'] = three_hour['start_time'] + tz_str
                three_hour['end_time'] = three_hour['end_time'] + tz_str
            
            three_hour_out = three_hour[['start_time', 'end_time', 'open', 'high', 'low', 'close', 'mid']].copy()
            three_hour_out = three_hour_out.where(pd.notna(three_hour_out), None)
            three_hour_out['type'] = '3H'
            
            results.extend(three_hour_out.to_dict('records'))
            
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
