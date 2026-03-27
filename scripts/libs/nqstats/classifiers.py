"""
NQStats Classifier Module - Vectorized ALN and Broken Status logic.
Based on NQStats Unified Bias Algorithm.
"""

import pandas as pd
import numpy as np

def classify_aln_vectorized(sessions_df: pd.DataFrame) -> pd.Series:
    """
    Classify the ALN Pattern (Asia-London-NY relationship).
    LPEU: London High > Asia High, London Low >= Asia Low (Bullish)
    LPED: London Low < Asia Low, London High <= Asia High (Bearish)
    LEA:  London breaks BOTH Asia extremes (Expansion)
    AEL:  London inside Asia (Consolidation)
    """
    # Columns expected: asia_high, asia_low, london_high, london_low
    ah = sessions_df['asia_high'].values
    al = sessions_df['asia_low'].values
    lh = sessions_df['london_high'].values
    ll = sessions_df['london_low'].values
    
    # Conditions
    lea = (lh > ah) & (ll < al)
    lpeu = (lh > ah) & (ll >= al)
    lped = (ll < al) & (lh <= ah)
    ael = (lh <= ah) & (ll >= al)
    
    # Create result series
    results = pd.Series("Unknown", index=sessions_df.index)
    results[lea] = "LEA"
    results[lpeu] = "LPEU"
    results[lped] = "LPED"
    results[ael] = "AEL"
    
    return results

def get_broken_status_vectorized(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Check if subsequent sessions break prior session ranges.
    - Did London break Asia?
    - Did Pre-NY break London?
    - Did NY_AM break London or Asia?
    """
    # 1. London vs Asia
    ah = sessions_df['asia_high'].values
    al = sessions_df['asia_low'].values
    lh = sessions_df['london_high'].values
    ll = sessions_df['london_low'].values
    
    london_broke_asia = (lh > ah) | (ll < al)
    
    # 2. Pre-NY vs London
    ph = sessions_df['pre-ny_high'].values
    pl = sessions_df['pre-ny_low'].values
    
    preny_broke_london = (ph > lh) | (pl < ll)
    
    # Output labels
    l_vs_a = np.where(london_broke_asia, "Broken", "Held")
    p_vs_l = np.where(preny_broke_london, "Broken", "Held")
    
    # Build combo string Series
    combo = pd.Series(l_vs_a, index=sessions_df.index) + "/" + pd.Series(p_vs_l, index=sessions_df.index)
    
    return pd.DataFrame({
        "london_vs_asia": l_vs_a,
        "preny_vs_london": p_vs_l,
        "broken_status": combo
    }, index=sessions_df.index)

def get_profiler_status_vectorized(sessions_df: pd.DataFrame, prior_close: pd.Series) -> pd.Series:
    """
    Check session alignment relative to Prior Close (P12).
    Asia Status (L/S/N) / London Status (L/S/N)
    """
    ac = sessions_df['asia_close'].values
    lc = sessions_df['london_close'].values
    p12 = prior_close.values
    
    a_status = np.where(ac > p12, "L", np.where(ac < p12, "S", "N"))
    l_status = np.where(lc > p12, "L", np.where(lc < p12, "S", "N"))
    
    return pd.Series(a_status, index=sessions_df.index) + "/" + pd.Series(l_status, index=sessions_df.index)

def classify_noon_curve_vectorized(ohlc: pd.DataFrame) -> pd.Series:
    """
    Check if High-of-Day (HOD) and Low-of-Day (LOD) occur on opposite sides of Noon (12:00 ET).
    Window: 08:00 - 16:00 ET.
    """
    # 1. Filter to RTH window (08:00 - 16:00)
    et_df = ohlc.tz_convert('US/Eastern') if ohlc.index.tz else ohlc
    rth = et_df.between_time("08:00", "16:00")
    
    if rth.empty:
        return pd.Series("Unknown", index=ohlc.index)
        
    # 2. Get HOD and LOD times per day
    daily_groups = rth.groupby(rth.index.date)
    
    hod_times = daily_groups['high'].idxmax()
    lod_times = daily_groups['low'].idxmin()
    
    # 3. Check if they are on opposite sides of 12:00
    noon = pd.Timestamp("12:00").time()
    
    is_hod_am = hod_times.apply(lambda x: x.time() < noon)
    is_lod_am = lod_times.apply(lambda x: x.time() < noon)
    
    opposite = is_hod_am != is_lod_am
    
    # Results per date
    results = pd.Series("Same Side", index=hod_times.index)
    results[opposite] = "Opposite"
    
    # Map back to original index using vectorized reindexing
    # Performance: Avoid list comprehension over ohlc.index.date
    dates = ohlc.index.date
    final_output = results.reindex(dates).values
    
    return pd.Series(final_output, index=ohlc.index)
def get_quadrant_status(df_1m: pd.DataFrame, boxes_df: pd.DataFrame) -> pd.DataFrame:
    """
    High-Performance Vectorized Profiler Quadrant logic.
    Identifies session breakout direction and holding power (True vs False).
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    
    box_names = ['asiabox', 'londonbox', 'ny1box', 'ny2box']
    results = pd.DataFrame(index=df_1m.index)
    
    # Pre-calculated evaluations start/end
    eval_config = {
        'asiabox':   {'start': '19:30', 'end': '02:30'},
        'londonbox': {'start': '03:30', 'end': '07:30'},
        'ny1box':    {'start': '08:30', 'end': '11:00'},
        'ny2box':    {'start': '12:30', 'end': '16:00'}
    }
    
    for box_prefix in box_names:
        bh_series = boxes_df[f'{box_prefix}_high']
        bl_series = boxes_df[f'{box_prefix}_low']
        
        # 1. Create evaluation window mask
        cfg = eval_config[box_prefix]
        if cfg['start'] < cfg['end']:
            time_mask = (et_df.index.time >= pd.Timestamp(cfg['start']).time()) & (et_df.index.time < pd.Timestamp(cfg['end']).time())
        else: # AsiaBox is overnight
            time_mask = (et_df.index.time >= pd.Timestamp(cfg['start']).time()) | (et_df.index.time < pd.Timestamp(cfg['end']).time())
        
        # 2. Vectorized Breakout detection
        broke_high = (et_df['high'] > bh_series) & time_mask
        broke_low = (et_df['low'] < bl_series) & time_mask
        
        # 3. Determine first occurrence per day using groupby
        # We find the MIN index (time) where the condition is True
        dates = et_df.index.date
        
        # Use trading dates for grouping (shifts AM hours to the session's starting date)
        # For Asia (18:00 - 02:30), AM hours (00:00 - 02:30) belong to the previous day's session.
        if box_prefix == 'asiabox': 
            am_mask = et_df.index.time < pd.Timestamp('03:00').time()
            adjusted_dates = pd.Series(dates, index=et_df.index)
            adjusted_dates.loc[am_mask] = adjusted_dates.loc[am_mask] - pd.Timedelta(days=1)
            groups = adjusted_dates
        else:
            groups = pd.Series(dates, index=et_df.index)
            
        h_triggers = et_df.index[broke_high].to_series().groupby(groups[broke_high]).min()
        l_triggers = et_df.index[broke_low].to_series().groupby(groups[broke_low]).min()
        
        # 4. Create Status Series for each day
        unique_groups = np.unique(groups.values)
        status_series = pd.Series("None", index=unique_groups)
        
        # Vectorized identification of statuses
        triggered_h = h_triggers.reindex(unique_groups)
        triggered_l = l_triggers.reindex(unique_groups)
        
        has_h = triggered_h.notna()
        has_l = triggered_l.notna()
        
        # First High: has high AND (no low OR high before low)
        first_h = has_h & (~has_l | (triggered_h < triggered_l))
        # First Low: has low AND (no high OR low before high)
        first_l = has_l & (~has_h | (triggered_l < triggered_h))
        
        status_series.loc[first_h & ~has_l] = "LT"
        status_series.loc[first_h & has_l] = "LF"
        status_series.loc[first_l & ~has_h] = "ST"
        status_series.loc[first_l & has_h] = "SF"
        
        # Map back to full index efficiently
        results[f'{box_prefix}_status'] = status_series.reindex(groups.values).values
        
    return results
