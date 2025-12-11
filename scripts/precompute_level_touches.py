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

DATA_DIR = Path(__file__).parent.parent / 'data'
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
    # Load 1-minute data
    parquet_path = DATA_DIR / f'{ticker}_1m.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing {parquet_path}")
    
    df = pd.read_parquet(parquet_path)
    
    # Load profiler session data for session mids
    profiler_sessions = load_profiler_sessions(ticker)
    
    # Ensure datetime index in ET
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(ET)
    else:
        df.index = df.index.tz_convert(ET)
    
    # Add trading_date column (day that starts at 18:00)
    def get_trading_date(ts):
        if ts.time() >= time(18, 0):
            return (ts + timedelta(days=1)).date()
        else:
            return ts.date()
    
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
        
        daily_data[str(trading_date)] = {
            'high': float(group['high'].max()),
            'low': float(group['low'].min()),
            'mid': float((group['high'].max() + group['low'].min()) / 2),
            'bars': group,
            'daily_open': daily_open,
            'midnight_open': midnight_open,
            'open_0730': open_0730
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
        
        # Find touch times for each level
        def find_touch_time(level, bars_df, tolerance_pct=0.001):
            """Find first time the level was touched (within tolerance)"""
            if level is None:
                return None
            tolerance = abs(level) * tolerance_pct
            for ts, row in bars_df.iterrows():
                if row['low'] <= level + tolerance and row['high'] >= level - tolerance:
                    return ts.strftime('%H:%M')
            return None
        
        # Day session bars (06:00 onwards for touch analysis)
        day_session = bars[bars.index.time >= time(6, 0)]
        
        result = {
            'pdh': {
                'level': round(pdh, 2),
                'touched': False,
                'touch_time': None
            },
            'pdl': {
                'level': round(pdl, 2),
                'touched': False,
                'touch_time': None
            },
            'pdm': {
                'level': round(pdm, 2),
                'touched': False,
                'touch_time': None
            }
        }
        
        # Check PDH/PDL/PDM touches
        pdh_time = find_touch_time(pdh, day_session)
        if pdh_time:
            result['pdh']['touched'] = True
            result['pdh']['touch_time'] = pdh_time
        
        pdl_time = find_touch_time(pdl, day_session)
        if pdl_time:
            result['pdl']['touched'] = True
            result['pdl']['touch_time'] = pdl_time
        
        pdm_time = find_touch_time(pdm, day_session)
        if pdm_time:
            result['pdm']['touched'] = True
            result['pdm']['touch_time'] = pdm_time
        
        # P12 levels
        if p12h is not None:
            result['p12h'] = {
                'level': round(p12h, 2),
                'touched': False,
                'touch_time': None
            }
            result['p12l'] = {
                'level': round(p12l, 2),
                'touched': False,
                'touch_time': None
            }
            result['p12m'] = {
                'level': round(p12m, 2),
                'touched': False,
                'touch_time': None
            }
            
            # Check P12 touches (during day session 06:00+)
            p12h_time = find_touch_time(p12h, day_session)
            if p12h_time:
                result['p12h']['touched'] = True
                result['p12h']['touch_time'] = p12h_time
            
            p12l_time = find_touch_time(p12l, day_session)
            if p12l_time:
                result['p12l']['touched'] = True
                result['p12l']['touch_time'] = p12l_time
            
            p12m_time = find_touch_time(p12m, day_session)
            if p12m_time:
                result['p12m']['touched'] = True
                result['p12m']['touch_time'] = p12m_time
        
        # Time-based opens
        daily_open = current['daily_open']
        midnight_open = current['midnight_open']
        open_0730 = current['open_0730']
        
        if daily_open is not None:
            do_time = find_touch_time(daily_open, day_session)
            result['daily_open'] = {
                'level': round(daily_open, 2),
                'touched': do_time is not None,
                'touch_time': do_time
            }
        
        if midnight_open is not None:
            mo_time = find_touch_time(midnight_open, day_session)
            result['midnight_open'] = {
                'level': round(midnight_open, 2),
                'touched': mo_time is not None,
                'touch_time': mo_time
            }
        
        if open_0730 is not None:
            o730_time = find_touch_time(open_0730, day_session)
            result['open_0730'] = {
                'level': round(open_0730, 2),
                'touched': o730_time is not None,
                'touch_time': o730_time
            }
        
        # Session mids from profiler data
        if date in profiler_sessions:
            day_prof = profiler_sessions[date]
            for sess_name in ['Asia', 'London', 'NY1', 'NY2']:
                if sess_name in day_prof:
                    sess = day_prof[sess_name]
                    mid = sess.get('mid')
                    if mid is not None:
                        key = f'{sess_name.lower()}_mid'
                        mid_time = find_touch_time(mid, day_session)
                        result[key] = {
                            'level': round(mid, 2),
                            'touched': mid_time is not None,
                            'touch_time': mid_time
                        }
        
        results[date] = result
    
    return results


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
        pdh_t = r['pdh']['touch_time'] or 'N/A'
        pdl_t = r['pdl']['touch_time'] or 'N/A'
        pdm_t = r['pdm']['touch_time'] or 'N/A'
        print(f"  {d}: PDH@{pdh_t}, PDM@{pdm_t}, PDL@{pdl_t}")
    
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
    print(f"  PDH: {100*pdh_hits/total:.1f}% ({pdh_hits}/{total})")
    print(f"  PDM: {100*pdm_hits/total:.1f}% ({pdm_hits}/{total})")
    print(f"  PDL: {100*pdl_hits/total:.1f}% ({pdl_hits}/{total})")
    print(f"  P12 High: {100*p12h_hits/p12_total:.1f}% ({p12h_hits}/{p12_total})")
    print(f"  P12 Mid:  {100*p12m_hits/p12_total:.1f}% ({p12m_hits}/{p12_total})")
    print(f"  P12 Low:  {100*p12l_hits/p12_total:.1f}% ({p12l_hits}/{p12_total})")
    
    # Save to JSON
    output_path = DATA_DIR / f'{ticker}_level_touches.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
