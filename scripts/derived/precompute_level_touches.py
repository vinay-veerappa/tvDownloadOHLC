"""
Precompute reference level touch data for each trading day.

For each day, computes:
- Previous Day High/Low/Mid levels
- P12 levels (overnight 18:00-06:00 High/Low/Mid)
- Time-based opens (Daily 18:00, Midnight 00:00, 07:30)
- First touch time for each level during the day
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz
from collections import defaultdict
from scripts.libs_py.nqstats.sessions import get_trading_date

DATA_DIR = Path(__file__).parent.parent.parent / 'data'
ET = pytz.timezone('US/Eastern')


def load_profiler_sessions(ticker: str) -> dict:
    """Load profiler session data to get session mids"""
    profiler_path = DATA_DIR / f'{ticker}_profiler.json'
    if not profiler_path.exists():
        return {}
    
    with open(profiler_path, 'r') as f:
        sessions = json.load(f)
    
    # Group by date
    by_date = defaultdict(dict)
    for s in sessions:
        by_date[s['date']][s['session']] = s
    
    return dict(by_date)


def compute_level_touches(ticker: str) -> dict:
    """
    Compute reference level touch data for each trading day.
    """
    # Load 1-minute data using unified utility
    from api.features.shared.data_loader import load_parquet
    df = load_parquet(ticker, '1m')
    if df is None or df.empty:
        raise FileNotFoundError(f"No data found for {ticker}")
    
    # Load profiler session data for session mids
    profiler_sessions = load_profiler_sessions(ticker)
    
    # Standardize on absolute Unix-to-EST synchronization
    df['dt_utc'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.set_index('dt_utc').tz_convert(ET)
    
    # Defensive: purge the original Unix 'time' column
    if 'time' in df.columns:
        df = df.drop(columns=['time'])
    
    df['trading_date'] = df.index.map(get_trading_date)
    
    # Group by trading date
    daily_data = {}
    
    for trading_date, group in df.groupby('trading_date'):
        if len(group) < 100:  # Skip days with insufficient data
            continue
        
        # Get price at specific times
        def get_price_at_time(target_time, bars):
            """Get the open price at or just after target time"""
            mask = bars.index.time >= target_time
            matching = bars[mask]
            if len(matching) > 0:
                return float(matching.iloc[0]['open'])
            return None
        
        # Daily open (18:00)
        daily_open = get_price_at_time(time(18, 0), group)
        
        # Midnight open (00:00)
        midnight_bars = group[group.index.time >= time(0, 0)]
        midnight_open = float(midnight_bars.iloc[0]['open']) if len(midnight_bars) > 0 else None
        
        # 07:30 open
        open_0730 = get_price_at_time(time(7, 30), group)

        # 08:00 open (NY1 Open)
        open_0800 = get_price_at_time(time(8, 0), group)
        
        daily_data[str(trading_date)] = {
            'high': float(group['high'].max()),
            'low': float(group['low'].min()),
            'mid': float((group['high'].max() + group['low'].min()) / 2),
            'bars': group,
            'daily_open': daily_open,
            'midnight_open': midnight_open,
            'open_0730': open_0730,
            'open_0800': open_0800
        }
    
    results = {}
    sorted_dates = sorted(daily_data.keys())
    
    for i, date in enumerate(sorted_dates):
        if i == 0:
            continue  # Skip first day (no previous day)
        
        prev_date = sorted_dates[i - 1]
        current = daily_data[date]
        prev = daily_data[prev_date]
        
        # Previous Day levels
        pdh = prev['high']
        pdl = prev['low']
        pdm = (pdh + pdl) / 2
        
        # P12 levels (overnight 18:00-06:00)
        bars = current['bars']
        overnight_mask = (bars.index.time >= time(18, 0)) | (bars.index.time < time(6, 0))
        overnight = bars[overnight_mask]
        
        if len(overnight) > 0:
            p12h = float(overnight['high'].max())
            p12l = float(overnight['low'].min())
            p12m = (p12h + p12l) / 2
        else:
            p12h = p12l = p12m = None

        # NY P12 levels (previous day 06:00-17:59)
        prev_bars = prev['bars']
        ny_p12_mask = (prev_bars.index.time >= time(6, 0)) & (prev_bars.index.time < time(18, 0))
        ny_p12_bars = prev_bars[ny_p12_mask]
        
        if len(ny_p12_bars) > 0:
            ny_p12h = float(ny_p12_bars['high'].max())
            ny_p12l = float(ny_p12_bars['low'].min())
            ny_p12m = (ny_p12h + ny_p12l) / 2
        else:
            ny_p12h = ny_p12l = ny_p12m = None
        
        # Find touch times for each level
        def find_touch_times(level, bars_df):
            """Find ALL unique 15-min bucket times the level was touched"""
            if level is None:
                return []
            
            # Strict check: Level must be within (or equal to) the bar's range
            hits = bars_df[(bars_df['low'] <= level) & (bars_df['high'] >= level)]
            
            if hits.empty:
                return []
            
            unique_buckets = set()
            times_list = []
            
            # Iterate hits to bucket them
            # We use 1 minute buckets (raw precision) to allow frontend aggregation
            for ts in hits.index:
                # No rounding, keep 1-min precision
                h = ts.hour
                m = ts.minute
                # m_bucket = m  (effectively)
                bucket_key = f"{h:02d}:{m:02d}"
                
                if bucket_key not in unique_buckets:
                    unique_buckets.add(bucket_key)
                    # Store the bucket timestamp
                    times_list.append(bucket_key)
            
            return times_list
        
        # Day session bars for touch analysis (From 18:00 previous day to 17:00 current day)
        # Actually logic is simpler: 'group' itself IS the trading day (18:00 -> 17:00).
        # We just need to ensure we don't filter out the overnight hours if we want the chart to start at 18:00.
        # The line `day_session = bars[bars.index.time >= time(6, 0)]` was likely excluding overnight.
        # Let's use the full group, but maybe respect the 17:00 close?
        # The 'group' is already bucketed by `get_trading_date`.
        day_session = current['bars']
        
        result = {
            'pdh': {
                'level': round(pdh, 2),
                'touched': False,
                'touch_times': []
            },
            'pdl': {
                'level': round(pdl, 2),
                'touched': False,
                'touch_times': []
            },
            'pdm': {
                'level': round(pdm, 2),
                'touched': False,
                'touch_times': []
            }
        }
        
        # Check PDH/PDL/PDM touches
        pdh_times = find_touch_times(pdh, day_session)
        if pdh_times:
            result['pdh']['touched'] = True
            result['pdh']['touch_times'] = pdh_times
        
        pdl_times = find_touch_times(pdl, day_session)
        if pdl_times:
            result['pdl']['touched'] = True
            result['pdl']['touch_times'] = pdl_times
        
        pdm_times = find_touch_times(pdm, day_session)
        if pdm_times:
            result['pdm']['touched'] = True
            result['pdm']['touch_times'] = pdm_times
        
        # P12 levels
        if p12h is not None:
            result['p12h'] = {
                'level': round(p12h, 2),
                'touched': False,
                'touch_times': []
            }
            result['p12l'] = {
                'level': round(p12l, 2),
                'touched': False,
                'touch_times': []
            }
            result['p12m'] = {
                'level': round(p12m, 2),
                'touched': False,
                'touch_times': []
            }
            
            # Check P12 touches (valid only during 06:00 - 17:00 of the trading day)
            # We filter the day_session to exclude the overnight definition period
            # P12 definition period: 18:00 - 06:00
            # Valid touch period: 06:00 onwards
            p12_session = day_session[~overnight_mask]
            
            p12h_times = find_touch_times(p12h, p12_session)
            if p12h_times:
                result['p12h']['touched'] = True
                result['p12h']['touch_times'] = p12h_times
            
            p12l_times = find_touch_times(p12l, p12_session)
            if p12l_times:
                result['p12l']['touched'] = True
                result['p12l']['touch_times'] = p12l_times
            
            p12m_times = find_touch_times(p12m, p12_session)
            if p12m_times:
                result['p12m']['touched'] = True
                result['p12m']['touch_times'] = p12m_times
                
        # NY P12 levels
        if ny_p12h is not None:
            result['ny_p12h'] = {
                'level': round(ny_p12h, 2),
                'touched': False,
                'touch_times': []
            }
            result['ny_p12l'] = {
                'level': round(ny_p12l, 2),
                'touched': False,
                'touch_times': []
            }
            result['ny_p12m'] = {
                'level': round(ny_p12m, 2),
                'touched': False,
                'touch_times': []
            }
            
            # Check NY P12 touches (valid entirely during current trading day, starting at 18:00)
            ny_p12h_times = find_touch_times(ny_p12h, day_session)
            if ny_p12h_times:
                result['ny_p12h']['touched'] = True
                result['ny_p12h']['touch_times'] = ny_p12h_times
            
            ny_p12l_times = find_touch_times(ny_p12l, day_session)
            if ny_p12l_times:
                result['ny_p12l']['touched'] = True
                result['ny_p12l']['touch_times'] = ny_p12l_times
            
            ny_p12m_times = find_touch_times(ny_p12m, day_session)
            if ny_p12m_times:
                result['ny_p12m']['touched'] = True
                result['ny_p12m']['touch_times'] = ny_p12m_times
        
        # Helper to slice session from start_time (exclusive) to 17:00
        def get_valid_window(bars_df, start_t: time):
            # Trading day ends at 17:00. 
            # If start_t is >= 18:00, it implies previous day part of the session.
            # If 00:00 <= start_t <= 17:00, it's current day.
            
            # Simple approach since bars_df is already the correct trading day sequence:
            # Find the index of the first bar AFTER start_t.
            # But simpler: just filter events.
            
            # Case 1: Start time is 18:00 (Daily Open)
            if start_t == time(18, 0):
                # Filter strictly after 18:00
                # But bars_df might start at 18:00.
                mask = (bars_df.index.time > start_t) | (bars_df.index.time < time(17, 0)) 
                # Careful with "OR" across midnight. 
                # 18:00 -> 23:59 (Prev Day) -> 00:00 -> 17:00 (Curr Day)
                # Valid: 18:01...23:59 OR 00:00...17:00.
                # Actually, easier to just check if index > timestamp of open? 
                # But we only have time objects here.
                
                # Let's filter by requiring time != 18:00 if it's the very first bar?
                # Best way: Iterate and skip until > start_t.
                pass

            # Robust Way: Build a valid mask based on minute of day? 
            # Or just use between_time equivalent on the sorted index.
            
            # Construct a full datetime start for filter
            # bars_df is strictly 18:00 D-1 to 17:00 D.
            # We want [Start Time + 1m, 17:00]
            
            # Let's just pass the sliced DF to find_touch_time.
            # Need a robust slicer.
            return bars_df # Placeholder if complex, but let's do inline below.
        
        # We will do inline slicing for clarity.
        
        # --- Time-based Opens ---
        # Valid from Open Time + 1m (approx) to 17:00. 
        # Actually, "Philosophy" implies subsequent price action.
        
        # Daily Open (18:00)
        daily_open = current['daily_open']
        if daily_open is not None:
             # Valid: > 18:00 prev day through 17:00 current day
             # Filter: exclude exact 18:00 bar if it matches open
             valid_bars = day_session[day_session.index.time != time(18,0)] 
             # (This is rough, assumes 1m bars. safe enough for now)
             do_times = find_touch_times(daily_open, valid_bars)
             result['daily_open'] = {
                'level': round(daily_open, 2),
                'touched': len(do_times) > 0,
                'touch_times': do_times
             }
        
        # Midnight Open (00:00)
        midnight_open = current['midnight_open']
        if midnight_open is not None:
            # Valid: 00:00 to 17:00. 
            # Filter: time > 00:00 and time <= 17:00 (implicit in day_session)
            # Or just >= 00:00? Usually "Open" implies the 00:00 price. Touch means revisiting.
            # Let's filter > 00:00.
            valid_bars = day_session.between_time('00:01', '17:00')
            mo_times = find_touch_times(midnight_open, valid_bars)
            result['midnight_open'] = {
                'level': round(midnight_open, 2),
                'touched': len(mo_times) > 0,
                'touch_times': mo_times
            }
        
        # 07:30 Open
        open_0730 = current['open_0730']
        if open_0730 is not None:
            # Valid: 07:31 - 17:00
            valid_bars = day_session.between_time('07:31', '17:00')
            o730_times = find_touch_times(open_0730, valid_bars)
            result['open_0730'] = {
                'level': round(open_0730, 2),
                'touched': len(o730_times) > 0,
                'touch_times': o730_times
            }

        # Session Mids
        if date in profiler_sessions:
            day_prof = profiler_sessions[date]
            
            # Map session to "Valid Start Time" for checking touches (end of utility window)
            session_check_starts = {
                'Asia': '19:30',
                'London': '03:30',
                'NY1': '08:30',
                'NY2': '12:30'
            }
            
            for sess_name in ['Asia', 'London', 'NY1', 'NY2']:
                if sess_name in day_prof:
                    sess = day_prof[sess_name]
                    mid = sess.get('mid')
                    if mid is not None:
                        key = f'{sess_name.lower()}_mid'
                        
                        start_t_str = session_check_starts.get(sess_name)
                        h, m = map(int, start_t_str.split(':'))
                        start_dt = (datetime.min + timedelta(hours=h, minutes=m, seconds=1)).time()
                        
                        # Search from end of utility until 17:00
                        valid_bars = day_session.between_time(start_dt, time(17,0))
                        mid_times = find_touch_times(mid, valid_bars)
                        
                        result[key] = {
                            'level': round(mid, 2),
                            'touched': len(mid_times) > 0,
                            'touch_times': mid_times
                        }

        # Previous Session Mids (Used for Asia/London sessions)
        if prev_date in profiler_sessions:
            prev_prof = profiler_sessions[prev_date]
            for sess_name in ['Asia', 'London', 'NY1', 'NY2']:
                if sess_name in prev_prof:
                    sess = prev_prof[sess_name]
                    mid = sess.get('mid')
                    if mid is not None:
                        key = f'prev_{sess_name.lower()}_mid'
                        
                        # Previous day's mids are already fully formed by the time the current trading day starts (18:00)
                        # So we can search the entire current trading day
                        mid_times = find_touch_times(mid, day_session)
                        
                        result[key] = {
                            'level': round(mid, 2),
                            'touched': len(mid_times) > 0,
                            'touch_times': mid_times
                        }
        
        results[date] = result
    
    return results


def save_columnar_version(ticker: str, raw_data: dict):
    """
    Format raw touch data to columnar format and save it.
    """
    SESSION_RANGES = {
        'Asia':   {'start': 18*60, 'end': 41*60},
        'London': {'start': 26*60, 'end': 41*60},
        'NY1':    {'start': 32*60, 'end': 41*60},
        'NY2':    {'start': 36*60, 'end': 41*60},
        'P12':    {'start': 30*60, 'end': 41*60},
        'Daily':  {'start': 18*60, 'end': 41*60}
    }
    
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

    raw_processed = {d: dict(lvls) for d, lvls in untouched_map.items()}

    if touch_records:
        df_t = pd.DataFrame(touch_records).sort_values('mins')
        meta = df_t.groupby(['date', 'level_name'])['level_val'].first()

        session_hits = {}
        for sess_name, rng in SESSION_RANGES.items():
            start, end = rng['start'], rng['end']
            direct  = (df_t['mins'] >= start) & (df_t['mins'] < end)
            wrapped = ((df_t['mins'] + 1440) >= start) & ((df_t['mins'] + 1440) < end)
            in_rng  = df_t[direct | wrapped]
            if in_rng.empty:
                continue
            first_hits = in_rng.groupby(['date', 'level_name'])['time_str'].first()
            for (date_k, level_n), time_val in first_hits.items():
                session_hits.setdefault((date_k, level_n), {})[sess_name] = time_val

        for (date_k, level_n), hits in session_hits.items():
            raw_processed.setdefault(date_k, {})[level_n] = {
                'level': meta.get((date_k, level_n)),
                'touched': True,
                'hits': hits,
            }
        all_touched = set(zip(df_t['date'], df_t['level_name']))
        for date_k, level_n in all_touched - set(session_hits.keys()):
            raw_processed.setdefault(date_k, {})[level_n] = {
                'level': meta.get((date_k, level_n)),
                'touched': True,
                'hits': {},
            }

    def time_to_minutes(t):
        if not t: return -1
        try:
            h, m = map(int, t.split(':'))
            return h * 60 + m
        except:
            return -1

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

    output_path = DATA_DIR / f"{ticker}_level_touches_columnar.json"
    with open(output_path, 'w') as f:
        json.dump(cached_columnar, f)
    print(f"    Saved columnar version to {output_path}")


def main():
    ticker = 'NQ1'
    print(f"Computing level touch data for {ticker}...")
    
    results = compute_level_touches(ticker)
    
    print(f"Computed level touches for {len(results)} trading days")
    
    # Show sample
    sample_dates = sorted(results.keys())[-5:]
    print("\nSample (last 5 days):")
    for d in sample_dates:
        r = results[d]
        # Helper to show first hit time or N/A
        def get_1st(times): return times[0] if times else 'N/A'
        
        pdh_t = get_1st(r['pdh']['touch_times'])
        pdl_t = get_1st(r['pdl']['touch_times'])
        pdm_t = get_1st(r['pdm']['touch_times'])
        print(f"  {d}: PDH@{pdh_t}, PDM@{pdm_t}, PDL@{pdl_t} (showing 1st hit)")
    
    # Calculate hit rates
    pdh_hits = sum(1 for r in results.values() if r['pdh']['touched'])
    pdl_hits = sum(1 for r in results.values() if r['pdl']['touched'])
    pdm_hits = sum(1 for r in results.values() if r['pdm']['touched'])
    
    p12_days = [r for r in results.values() if 'p12h' in r]
    p12h_hits = sum(1 for r in p12_days if r['p12h']['touched'])
    p12l_hits = sum(1 for r in p12_days if r['p12l']['touched'])
    p12m_hits = sum(1 for r in p12_days if r['p12m']['touched'])
    
    total = len(results)
    p12_total = len(p12_days)
    
    print(f"\nHit Rates:")
    if total > 0:
        print(f"  PDH: {100*pdh_hits/total:.1f}% ({pdh_hits}/{total})")
        print(f"  PDM: {100*pdm_hits/total:.1f}% ({pdm_hits}/{total})")
        print(f"  PDL: {100*pdl_hits/total:.1f}% ({pdl_hits}/{total})")
    else:
        print("  PDH/PDM/PDL: No data")

    if p12_total > 0:
        print(f"  P12 High: {100*p12h_hits/p12_total:.1f}% ({p12h_hits}/{p12_total})")
        print(f"  P12 Mid:  {100*p12m_hits/p12_total:.1f}% ({p12m_hits}/{p12_total})")
        print(f"  P12 Low:  {100*p12l_hits/p12_total:.1f}% ({p12l_hits}/{p12_total})")
    else:
        print("  P12 High/Mid/Low: No overnight data")
    
    # Save to JSON
    output_path = DATA_DIR / f'{ticker}_level_touches.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {output_path}")

    # Save columnar version too
    save_columnar_version(ticker, results)


if __name__ == '__main__':
    main()
