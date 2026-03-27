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
    
    # Map back to original index using dict lookup for speed and stability
    results_map = results.to_dict()
    final_output = [results_map.get(d, "Unknown") for d in ohlc.index.date]
    
    return pd.Series(final_output, index=ohlc.index)
def get_quadrant_status(df_1m: pd.DataFrame, boxes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Detailed Profiler Quadrant logic (Verified Study).
    LT (Long True): Break High, Hold Low.
    ST (Short True): Break Low, Hold High.
    LF (Long False): Break High, THEN Break Low.
    SF (Short False): Break Low, THEN Break High.
    """
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    
    # We will compute status for each box type
    box_names = ['asiabox', 'londonbox', 'ny1box', 'ny2box']
    results = pd.DataFrame(index=df_1m.index)
    
    # Next session starts for evaluation windows
    next_starts = {
        'asiabox':   '02:30',
        'londonbox': '07:30',
        'ny1box':    '11:30',
        'ny2box':    '16:00'
    }
    
    for box_prefix in box_names:
        # Get daily box extremes
        bh = boxes_df[f'{box_prefix}_high'].values
        bl = boxes_df[f'{box_prefix}_low'].values
        
        status_col = np.full(len(df_1m), "None", dtype=object)
        
        # Iterate days for stateful breakout check
        for date, group in et_df.groupby(et_df.index.date):
            # Find the box extremes for this day
            day_mask = et_df.index.date == date
            day_bh = bh[day_mask][0]
            day_bl = bl[day_mask][0]
            
            if np.isnan(day_bh): continue
            
            # Define evaluation window: from Box End to Next Session Start
            # (Simplified for the library: we just check the rest of the calendar day)
            eval_start_map = {'asiabox': '19:30', 'londonbox': '03:30', 'ny1box': '08:30', 'ny2box': '12:30'}
            eval_start = eval_start_map[box_prefix]
            eval_end = next_starts[box_prefix]
            
            # Create the eval slice
            try:
                # Use between_time for the daily slice
                eval_data = group.between_time(eval_start, eval_end)
            except:
                continue
                
            if eval_data.empty: continue
            
            # Stateful check
            triggered = None
            final_status = "None"
            
            for _, row in eval_data.iterrows():
                h, l, c = row['high'], row['low'], row['close']
                
                if triggered is None:
                    if h > day_bh:
                        triggered = "High"
                    elif l < day_bl:
                        triggered = "Low"
                
                # Determine status based on triggering and current extremes (wicks)
                if triggered == "High":
                    # Long True only if the LOW of the candle stays above the broke level
                    final_status = "LT" if l >= day_bh else "LF"
                elif triggered == "Low":
                    # Short True only if the HIGH of the candle stays below the broke level
                    final_status = "ST" if h <= day_bl else "SF"
                else:
                    final_status = "None"
                
                # Special Case: Check for "Stop Out" (Broken OTHER side)
                if triggered == "High" and l < day_bl:
                    final_status = "LF"
                elif triggered == "Low" and h > day_bh:
                    final_status = "SF"

            
            # Apply to the group
            status_col[day_mask] = final_status

            
        results[f'{box_prefix}_status'] = status_col
        
    return results
