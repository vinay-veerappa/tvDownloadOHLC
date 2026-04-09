import pandas as pd
import numpy as np
import duckdb

def track_fvg_outcomes(fvg_df: pd.DataFrame, bars_1m: pd.DataFrame, macro_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Tracks if FVGs were filled, held, or inverted using a vectorized join approach.
    """
    if fvg_df.empty or bars_1m.empty or macro_df is None:
        return fvg_df

    con = duckdb.connect(database=':memory:')
    
    # Register data
    # Strip tz for DuckDB
    bars_reg = bars_1m.reset_index().rename(columns={'dt_et': 'bar_time'})
    bars_reg['bar_time'] = bars_reg['bar_time'].dt.tz_localize(None)
    con.register('bars', bars_reg)
    
    fvg_reg = fvg_df.copy()
    fvg_reg['fvg_timestamp'] = pd.to_datetime(fvg_reg['fvg_timestamp']).dt.tz_localize(None)
    # Join macro lookforward end
    m_look = macro_df[['macro_id', 'macro_end', 'lookforward_end']].copy()
    m_look['lookforward_end_raw'] = pd.to_datetime(m_look['lookforward_end']).dt.tz_localize(None)
    fvg_reg = fvg_reg.merge(m_look[['macro_id', 'lookforward_end_raw']], on='macro_id', how='left')
    con.register('fvgs', fvg_reg)

    # For each FVG, join to ALL bars after its formation
    # Limit to e.g. 120 minutes for lookforward performance
    # In a real build, we'd use the next_macro_start logic
    con.execute("""
        CREATE TEMP TABLE fvg_lookforward AS
        SELECT 
            f.fvg_id,
            f.fvg_type,
            f.fvg_high,
            f.fvg_low,
            f.fvg_timestamp,
            b.bar_time,
            b.high as bar_h,
            b.low as bar_l,
            b.close as bar_c
        FROM fvgs f
        JOIN bars b ON b.bar_time > f.fvg_timestamp 
                   AND b.bar_time <= f.lookforward_end_raw
    """)

    # Compute outcomes
    con.execute("""
        CREATE TEMP TABLE fvg_outcomes AS
        SELECT 
            fvg_id,
            -- Was tested: Bullish low enters zone, Bearish high enters zone
            -- Fix: Use MAX(CASE) instead of ANY_VALUE
            MAX(CASE 
                WHEN fvg_type = 'bullish' AND bar_l <= fvg_high THEN 1
                WHEN fvg_type = 'bearish' AND bar_h >= fvg_low THEN 1
                ELSE 0
            END) > 0 as was_tested,
            
            -- Deepest penetration (Clamped to 100%)
            LEAST(MAX(CASE 
                WHEN fvg_type = 'bullish' AND bar_l <= fvg_high 
                THEN (fvg_high - LEAST(bar_l, fvg_low)) / (fvg_high - fvg_low) * 100
                WHEN fvg_type = 'bearish' AND bar_h >= fvg_low 
                THEN (GREATEST(bar_h, fvg_high) - fvg_low) / (fvg_high - fvg_low) * 100
                ELSE 0
            END), 100.0) as fill_depth_pct,
            
            -- Did price close through?
            MAX(CASE 
                WHEN fvg_type = 'bullish' AND bar_c < fvg_low THEN 1
                WHEN fvg_type = 'bearish' AND bar_c > fvg_high THEN 1
                ELSE 0
            END) > 0 as failed,
            
            -- Time to test (minutes)
            MIN(CASE 
                WHEN (fvg_type = 'bullish' AND bar_l <= fvg_high) OR (fvg_type = 'bearish' AND bar_h >= fvg_low)
                THEN date_diff('second', fvg_timestamp, bar_time) / 60.0
                ELSE NULL
            END) as test_time_m
        FROM fvg_lookforward
        GROUP BY fvg_id
    """)

    outcomes = con.execute("SELECT * FROM fvg_outcomes").df()
    res_df = fvg_df.merge(outcomes, on='fvg_id', how='left')
    
    # Held = tested but not failed
    res_df['held'] = res_df['was_tested'] & ~res_df['failed'].infer_objects(copy=False).fillna(True)
    
    return res_df
