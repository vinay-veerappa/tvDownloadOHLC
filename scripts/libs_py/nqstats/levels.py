"""
NQStats Levels Module - High-Performance Vectorized Level Extraction.
Handles Institutional Standard Anchors: P12, PDH/L/M, Midnight Open, etc.
"""

import pandas as pd
import numpy as np

def calculate_daily_levels(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Institutional Standard Levels (PDH, PDL, PDM, Settle) for all days.
    Input df_1m must be localized or localized to US/Eastern inside.
    Uses daily (1d) parquet data if available to avoid heavy 1m resampling.
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    dates = et_df.index.date
    u_dates = np.unique(dates)
    
    # Try reading from 1d daily parquet
    daily = None
    try:
        from api.features.shared.data_loader import DATA_DIR
        daily_parquet = DATA_DIR / "NQ1_1d.parquet" # Or detect ticker if possible, default NQ1
        if daily_parquet.exists():
            df_d = pd.read_parquet(daily_parquet)
            if df_d.index.tz is None:
                df_d = df_d.tz_localize('UTC').tz_convert('US/Eastern')
            else:
                df_d = df_d.tz_convert('US/Eastern')
            
            # Aggregate standard calendar day and shift by 1
            daily = df_d.resample('D').agg({
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).shift(1)
    except Exception as e:
        print(f"[Levels] Could not load 1d parquet: {e}. Falling back to 1m resampling.")
        daily = None

    if daily is None:
        # Fallback to standard 1m resampling
        daily = et_df.resample('D').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).shift(1)
    
    # Map back to 1m
    daily_naive = daily.copy()
    daily_naive.index = daily_naive.index.tz_localize(None)
    daily_map = daily_naive.reindex(pd.to_datetime(u_dates)).to_dict('index')
    
    levels = pd.DataFrame(index=et_df.index)
    
    # Optimized mapping
    pdh = np.array([daily_map.get(pd.Timestamp(d), {}).get('high', np.nan) for d in dates])
    pdl = np.array([daily_map.get(pd.Timestamp(d), {}).get('low', np.nan) for d in dates])
    pdc = np.array([daily_map.get(pd.Timestamp(d), {}).get('close', np.nan) for d in dates])
    
    levels['pdh'] = pdh
    levels['pdl'] = pdl
    levels['pdm'] = (pdh + pdl) / 2
    levels['settle'] = pdc
    
    # 2. Weekly Close
    weekly_close = et_df['close'].resample('W').last().shift(1)
    levels['pwc'] = weekly_close.reindex(et_df.index, method='ffill')

    return levels

def calculate_session_opens(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Session Open Anchors: Globex (18:00), Midnight (00:00), 07:30.
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    times = et_df.index.time
    
    opens = pd.DataFrame(index=et_df.index)
    
    # 18:00 Globex Open
    is_1800 = times == pd.Timestamp("18:00").time()
    opens['open_glob'] = et_df['open'].where(is_1800).ffill()
    
    # 00:00 Midnight Open
    is_0000 = times == pd.Timestamp("00:00").time()
    opens['open_mid'] = et_df['open'].where(is_0000).ffill()
    
    # 07:30 Open
    is_0730 = times == pd.Timestamp("07:30").time()
    opens['open_0730'] = et_df['open'].where(is_0730).ffill()
    
    return opens

def calculate_p12_levels(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate P12 (18:00-05:59) and NY P12 (06:00-16:59) ranges.
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    times = et_df.index.time
    dates = et_df.index.date
    
    # P12: 18:00 (Day -1) to 05:59 (Day 0)
    p12_mask = (times >= pd.Timestamp("18:00").time()) | (times < pd.Timestamp("06:00").time())
    
    # Grouping logic for overnight: times >= 18:00 belong to "next day" P12
    p12_groups = pd.Series(dates, index=et_df.index)
    p12_groups.loc[times >= pd.Timestamp("18:00").time()] += pd.Timedelta(days=1)
    
    p12_agg = et_df[p12_mask].groupby(p12_groups[p12_mask]).agg({'high': 'max', 'low': 'min'})
    
    # NY P12: 06:00 to 16:59
    nyp_mask = (times >= pd.Timestamp("06:00").time()) & (times < pd.Timestamp("17:00").time())
    nyp_agg = et_df[nyp_mask].groupby(dates[nyp_mask]).agg({'high': 'max', 'low': 'min'})
    
    # Map back
    p12_res = p12_agg.reindex(p12_groups.values)
    p12_res.index = et_df.index
    
    nyp_res = nyp_agg.reindex(dates)
    nyp_res.index = et_df.index
    
    res = pd.DataFrame(index=et_df.index)
    res['p12h'] = p12_res['high']
    res['p12l'] = p12_res['low']
    res['p12m'] = (res['p12h'] + res['p12l']) / 2
    
    res['nyp12h'] = nyp_res['high']
    res['nyp12l'] = nyp_res['low']
    res['nyp12m'] = (res['nyp12h'] + res['nyp12l']) / 2
    
    # For daily profiler comparison, we also need PREVIOUS NY P12 (from day before)
    # NY P12 is within the same calendar day (06:00-16:59), 
    # so we just need to shift the aggregated values.
    prev_nyp_agg = nyp_agg.shift(1)
    prev_nyp_res = prev_nyp_agg.reindex(dates)
    prev_nyp_res.index = et_df.index
    
    res['prev_nyp12h'] = prev_nyp_res['high']
    res['prev_nyp12l'] = prev_nyp_res['low']
    res['prev_nyp12m'] = (res['prev_nyp12h'] + res['prev_nyp12l']) / 2
    
    return res

def get_session_mids(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract midpoints from pre-calculated sessions DataFrame.
    """
    mids = pd.DataFrame(index=sessions_df.index)
    for col in sessions_df.columns:
        if '_mid' in col:
            mids[col] = sessions_df[col]
            
    # Also need PREVIOUS session mids for Context (ctx) filtering
    # These typically come from the day before.
    # We group by date and take the 'last' mid of the previous date.
    dates = sessions_df.index.date
    daily_mids = sessions_df[[c for c in sessions_df.columns if '_mid' in c]].groupby(dates).last().shift(1)
    
    prev_mids = daily_mids.reindex(dates)
    prev_mids.index = sessions_df.index
    prev_mids.columns = [f"prev_{c}" for c in prev_mids.columns]
    
    return pd.concat([mids, prev_mids], axis=1)
