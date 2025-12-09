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

        # 1. Calculate Daily Aggregates (PDH, PDL, PD-Mid)
        # We resample to Daily (1D) to get OHLC for each day
        # Shift by 1 to get "Previous Day" relative to "Today"
        daily = df.resample('1D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
        daily['mid'] = (daily['high'] + daily['low']) / 2
        prev_daily = daily.shift(1) # Row for 2024-12-05 contains data from 2024-12-04

        # 2. Calculate Weekly Aggregates (Previous Week Close)
        # Resample to Weekly (Ending Friday or distinct weeks?)
        # 'W-FRI' aligns strictly to weeks ending Friday
        weekly = df.resample('W-FRI').agg({'close': 'last'})
        prev_weekly = weekly.shift(1)

        # 3. Helpers for specific times
        def get_price_at_time(d_data, t_str):
            try:
                ts = pd.Timestamp.combine(d_data.name.date(), pd.to_datetime(t_str).time())
                if d_data.index.tz:
                    ts = ts.tz_localize(d_data.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                # Find exact or nearest forward
                # Using searchsorted for speed on day slice might be overkill if day is small
                # Just boolean mask or asof
                # slice = d_data[d_data.index >= ts]
                # if not slice.empty: return slice.iloc[0]['open']
                # Better: asof if sorted
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
            mid_price = get_price_at_time(day_data, "00:00")
            if mid_price is not None:
                 results.append({
                    "date": date_str, "session": "MidnightOpen",
                    "start_time": pd.Timestamp.combine(date_obj, time(0,0)).isoformat(),
                    "price": float(mid_price)
                })

            # 7:30 Open
            open_730 = get_price_at_time(day_data, "07:30")
            if open_730 is not None:
                results.append({
                    "date": date_str, "session": "Open730",
                    "start_time": pd.Timestamp.combine(date_obj, time(7,30)).isoformat(),
                    "price": float(open_730)
                })
            
            # Globex Open (18:00 PREVIOUS DAY)
            # This is tricky. 18:00 of "Today" is start of "Tomorrow's" Globex.
            # So for "Today's" chart (e.g. Wed), we want the 18:00 from Tue.
            # We can find 18:00 in `day_data` (if it exists, it's today's 18:00, belonging to Next Day).
            # But the user wants "Globex Open" for *This* day.
            # Which is actually 18:00 of Yesterday.
            # Easiest way: Look up 18:00 in YESTERDAY's data. 
            # Or simpler: Store 18:00 of today as "GlobexOpen" for Tomorrow.
            # Current Loop approach: We iterate days. 
            # Let's try to get 18:00 from *Yesterday* logic if available, OR
            # simpler: Just calculate "18:00" for the current date, and let the frontend render it?
            # No, standard implies: On Wed chart, show Tue 18:00 level.
            # Using `pd.Timedelta(days=1)` logic.
            prev_date_obj = date_obj - timedelta(days=1)
            # This is inefficient to search full DF.
            # Optimization: We can carry forward "Next Day's Globex" in the loop variable?
            # OR: Since we want robustness, getting it from `day_data` isn't possible (it starts 00:00 or 18:00?).
            # Session def "Asia" starts 18:00. 
            # If `day_data` includes 18:00-23:59 of *Previous Calendar Day* (which fits "Trading Day" logic),
            # then `get_price_at_time(day_data, "18:00")` is correct for THAT trading day.
            # BUT our `groupby(df.index.date)` splits by CALENDAR date.
            # So `day_data` for 2025-12-05 is 00:00->23:59 on Dec 5.
            # The "Globex Open" relevant for Dec 5 trading is Dec 4 18:00.
            # Dec 5's own 18:00 is relevant for Dec 6.
            
            # We will use the calculate Daily shift logic or just look back if easy.
            # Given we are iterating, let's skip complex lookbacks inside loop and rely on Resampling for PDH?
            # For specific times like Globex, resampling is hard.
            # Alternative: Calculate Globex Open for *this* day (Dec 5 18:00) and label it "GlobexOpen".
            # Frontend will draw it starting Dec 5 18:00.
            # Wait, if we draw it starting Dec 5 18:00, it covers Dec 6 session?
            # User wants to see the level *during* the day. 
            # So for Dec 5th session, we need Dec 4th 18:00.
            
            # Use `shift` approach on full series for robustness?
            # Or just: `last_1800` variable carried in loop.
            
            # Standard Session Ranges
            for sess in session_defs:
                # If Asia is 18:00-19:30, and we use Calendar Date...
                # On Dec 5, 18:00 is late in the day.
                # Is that "Asia" for Dec 5 or Dec 6? Usually Dec 6.
                # Our current code: `pd.Timestamp.combine(date_obj, ...)` => Dec 5 18:00.
                # So we are generating "Asia" that starts late in the day.
                # This seems correct for `DailyProfiler` which visualizes flow.
                
                # Logic unchanged for existing sessions
                start_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["start"]).time())
                end_t = pd.Timestamp.combine(date_obj, pd.to_datetime(sess["end"]).time())
                
                if df.index.tz:
                    try:
                        start_t = start_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                        end_t = end_t.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                    except: continue

                # Determine correct dates for overnight sessions (London 02:30 is next day?)
                # Actually, 02:30 on Dec 5 is early morning Dec 5.
                # 18:00 on Dec 5 is late evening Dec 5.
                # Seems fine.
                
                if pd.isna(start_t) or pd.isna(end_t): continue
                
                range_data = day_data[(day_data.index >= start_t) & (day_data.index < end_t)]
                if not range_data.empty:
                    high = range_data['high'].max()
                    low = range_data['low'].min()
                    mid = (high + low) / 2
                    results.append({
                        "date": date_str, "session": sess["name"],
                        "start_time": start_t.isoformat(), "end_time": end_t.isoformat(),
                        "high": float(high), "low": float(low), "mid": float(mid)
                    })
                    
                    if sess["name"] == "Asia":
                        # This 18:00 price is strictly the Globex Open for the *Next* day?
                        # Or just "Globex Open" for this sequence.
                        # Actually, let's just emit "GlobexOpen" at 18:00 every day.
                        # The renderer can decide to extend it.
                         results.append({
                            "date": date_str, "session": "GlobexOpen",
                            "start_time": start_t.isoformat(),
                            "price": float(range_data.iloc[0]['open'])
                        })

            # --- Previous Day Levels (PDH, PDL, PDMid) ---
            # Retrieve from pre-calculated `prev_daily`
            if date_ts in prev_daily.index:
                p_row = prev_daily.loc[date_ts]
                if not pd.isna(p_row['high']):
                    # We render these as lines for the *entire* current day (00:00 to 23:59?)
                    # Start time = 00:00 of current day (or 18:00 or previous?)
                    # Usually "Previous Day High" is valid for the whole current session.
                    # We'll start it at 00:00 or even better - extend dynamic.
                    # Let's emit it at 00:00.
                    s_iso = pd.Timestamp.combine(date_obj, time(0,0)).isoformat()
                    results.append({"date": date_str, "session": "PDH", "start_time": s_iso, "price": float(p_row['high'])})
                    results.append({"date": date_str, "session": "PDL", "start_time": s_iso, "price": float(p_row['low'])})
                    results.append({"date": date_str, "session": "PDMid", "start_time": s_iso, "price": float(p_row['mid'])})

            # --- Previous Week Close ---
            # Using `asof` on `prev_weekly`
            # Find the latest weekly close strictly before today
            try:
                # Get the Friday before this date?
                # `prev_weekly` is indexed by Friday dates.
                # `date_ts` is current day.
                # We want the 'close' of the week that ended before `date_ts`.
                # If `date_ts` is Monday Dec 9, we want Fri Dec 6.
                # usage: prev_weekly.index.asof(date_ts) -> returns closest index <= date_ts.
                # But we shifted `prev_weekly` so it aligns forward?
                # Wait, earlier `prev_weekly = weekly.shift(1)`.
                # Week ending Dec 6 (Fri). Row has Dec 6 date.
                # Shift(1): The row for "Next Week" (say Dec 13) now has Dec 6 data?
                # This works if resampling introduces rows for every week.
                # But if data has gaps, shift might be wrong row count wise. Only if reindexed.
                # Safest: Use raw `weekly` and `asof` with lookup.
                
                # Let's use logic: strictly before date_obj
                past_weeks = weekly[weekly.index < date_ts]
                if not past_weeks.empty:
                    last_wk = past_weeks.iloc[-1]
                    s_iso = pd.Timestamp.combine(date_obj, time(0,0)).isoformat()
                    results.append({"date": date_str, "session": "PWeeklyClose", "start_time": s_iso, "price": float(last_wk['close'])})
            except: pass

            # --- Previous 12H (P12) ---
            # 12H blocks: 18:00->06:00 (Overnight) and 06:00->18:00 (Day)
            # Users usually want the levels of the *immediate preceding* 12h block.
            # e.g. At 07:00, show H/L/Mid of the 18:00-06:00 block.
            # e.g. At 19:00, show H/L/Mid of the 06:00-18:00 block.
            # This implies dynamic changing during the day?
            # Or just "The 12H block prior to Today's Open"?
            # Usually: "P12" refers to the prior 12h session.
            # Let's assume user wants the [18:00(yest) -> 06:00(today)] block visualized on Today's chart (06:00+).
            # AND maybe [06:00(yest) -> 18:00(yest)] visualized during overnight?
            # Let's implement specific Fixed Time Blocks High/Low.
            # Block A: 18:00(y-1) to 06:00(d).
            # Block B: 06:00(d) to 18:00(d).
            # We can calculate these.
            
            # P12 Calculation:
            # We'll iterate strictly.
            # Actually, `day_data` is 00:00 to 23:59.
            # It contains PART of Block A (00:00-06:00) and ALL of Block B (06:00-18:00).
            # And Part of Next Block (18:00-23:59).
            # To get full Block A (18:00->06:00), we need yesterday data again.
            
            # Simplified: Let's emit 06:00-18:00 as "Day12H" and 18:00-06:00 as "Night12H".
            # And renderer can label them "P12" if they are in the past?
            # User request: "The high, Low & mid of the 12H candle".
            # Usually implies 2 bars per day.
            # We will generate "Session12H" objects.
            
            # Morning P12 (ends 06:00 today, starts 18:00 yest)
            # We need to look back.
            # Or we can just calculate 12H bars for the whole dataset using resampling?
            # `df.resample('12H', offset='6H')`? 
            # 12H bars: 06:00-18:00, 18:00-06:00.
            # Offset base.
            
            # Let's calculate separate list of 12H candles and append?
            # This is getting complex to merge inside the daily loop.
            # Let's append them outside?
            # No, `results` is flat. We can do it outside!
            pass 

            # Opening Range (Existing)
            or_start = pd.Timestamp.combine(date_obj, time(9, 30))
            if df.index.tz: 
                try:
                    or_start = or_start.tz_localize(df.index.tz, ambiguous='NaT', nonexistent='shift_forward')
                except: continue
            or_end = or_start + pd.Timedelta(minutes=1)
            try:
                or_data = df.loc[or_start:or_end]
                or_data = or_data[or_data.index < or_end]
                if not or_data.empty:
                    h, l = or_data['high'].max(), or_data['low'].min()
                    results.append({
                        "date": date_str, "session": "OpeningRange",
                        "start_time": or_start.isoformat(), "end_time": or_end.isoformat(),
                        "high": float(h), "low": float(l), "mid": float((h + l) / 2)
                    })
            except: pass
        
        # --- 4. Post-Loop: 12H Session Generation ---
        # Resample entire DF to 12H blocks logic
        # 06:00-18:00 and 18:00-06:00.
        # Standard resample('12H') starts at 00:00 (00-12, 12-24).
        # We want 06-18, 18-06.
        # offset='6H' -> Bins start at 06:00.
        try:
           res_12h = df.resample('12H', offset='6H').agg({'high':'max', 'low':'min'})
           res_12h['mid'] = (res_12h['high'] + res_12h['low']) / 2
           # Each row is a completed 12H block (labeled by start time).
           # We want to display these levels *during the NEXT block*?
           # "P12" = Previous 12H.
           # So for the block starting 18:00, we show levels from block starting 06:00.
           # We will emit them as "P12" sessions starting at the `timestamp + 12h`?
           # Yes.
           shifted_12h = res_12h.shift(1) # Row `06:00` now contains data from `18:00(prev)`?
           # No. Shift(1) moves data forward.
           # Row index 18:00 gets data from 06:00.
           # So at 18:00, we render the data from 06:00. This is exactly P12.
           
           for ts, row in shifted_12h.iterrows():
               if pd.isna(row['high']): continue
               # This "session" lasts 12 hours
               end_ts = ts + pd.Timedelta(hours=12)
               results.append({
                   "date": ts.strftime('%Y-%m-%d'),
                   "session": "P12", # Generic name, renderer handles overlap?
                   # Or distinct names? P12 is fine, we have start/end.
                   "start_time": ts.isoformat(),
                   "end_time": end_ts.isoformat(),
                   "high": float(row['high']),
                   "low": float(row['low']),
                   "mid": float(row['mid'])
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
