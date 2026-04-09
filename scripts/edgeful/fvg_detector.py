import pandas as pd
import numpy as np
import duckdb

def detect_fvgs(macro_df: pd.DataFrame, bars_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Detects Fair Value Gaps (FVG) within each macro window using vectorized DuckDB scan.
    Returns fvg_detail DataFrame.
    """
    if macro_df.empty or bars_1m.empty:
        return pd.DataFrame()

    con = duckdb.connect(database=':memory:')
    
    # Register data
    # We need bar_assignments (bars tagged with macro_id) 
    # For now, let's assume we can map them back or recreate the mapping.
    # Recreating the mapping is safest if bar_assignments isn't passed but we have macro_df
    # However, for Sprint 2, we expect bar_assignments to exist in DuckDB session.
    # We'll use a local join as fallback.
    
    bars_reg = bars_1m.reset_index().copy()
    bars_reg['dt_et_raw'] = bars_reg['dt_et'].dt.tz_localize(None)
    con.register('bars', bars_reg)
    
    macro_reg = macro_df[['macro_id', 'trading_date', 'macro_start', 'macro_end', 'open', 'high_offset_m', 'low_offset_m', 'judas_classification', 'mid_anchor_open']].copy()
    macro_reg['macro_start_raw'] = macro_reg['macro_start'].dt.tz_localize(None)
    macro_reg['macro_end_raw'] = macro_reg['macro_end'].dt.tz_localize(None)
    con.register('macros', macro_reg)

    # 1. Map bars to macros (Standardizes logic from macro_extractor)
    con.execute("""
        CREATE TEMP TABLE bar_to_macro AS
        SELECT 
            b.*,
            m.macro_id,
            m.open as macro_open_lvl,
            m.high_offset_m,
            m.low_offset_m,
            m.judas_classification,
            m.mid_anchor_open,
            row_number() OVER (PARTITION BY m.macro_id ORDER BY b.dt_et_raw) - 1 as bar_index
        FROM bars b
        JOIN macros m ON b.trading_date = m.trading_date 
                     AND b.dt_et_raw >= m.macro_start_raw 
                     AND b.dt_et_raw < m.macro_end_raw
    """)

    # 2. Vectorized 3-bar scan per macro
    con.execute("""
        CREATE TEMP TABLE detected_fvgs AS
        WITH patterns AS (
            SELECT 
                macro_id,
                macro_open_lvl,
                high_offset_m,
                low_offset_m,
                judas_classification,
                mid_anchor_open,
                dt_et_raw,
                bar_index,
                high as curr_h,
                low as curr_l,
                LAG(high, 2) OVER (PARTITION BY macro_id ORDER BY dt_et_raw) as b1_h,
                LAG(low, 2) OVER (PARTITION BY macro_id ORDER BY dt_et_raw) as b1_l,
                close as b3_c
            FROM bar_to_macro
        )
        SELECT 
            macro_id,
            bar_index,
            dt_et_raw as fvg_timestamp,
            CASE 
                WHEN curr_l > b1_h THEN 'bullish'
                WHEN curr_h < b1_l THEN 'bearish'
            END as fvg_type,
            CASE 
                WHEN curr_l > b1_h THEN curr_l 
                ELSE b1_l 
            END as fvg_high,
            CASE 
                WHEN curr_l > b1_h THEN b1_h 
                ELSE curr_h 
            END as fvg_low,
            macro_open_lvl,
            high_offset_m,
            low_offset_m,
            judas_classification,
            mid_anchor_open
        FROM patterns
        WHERE (curr_l > b1_h) OR (curr_h < b1_l)
    """)

    fvg_df = con.execute("SELECT * FROM detected_fvgs").df()
    
    if fvg_df.empty:
        return fvg_df

    # ID and sequencing
    fvg_df['fvg_id'] = fvg_df['macro_id'] + "_FVG_" + fvg_df.groupby('macro_id').cumcount().add(1).astype(str)
    fvg_df['fvg_mid'] = (fvg_df['fvg_high'] + fvg_df['fvg_low']) / 2
    fvg_df['fvg_size_pct'] = (fvg_df['fvg_high'] - fvg_df['fvg_low']) / fvg_df['macro_open_lvl'] * 100
    
    # Phase Classification (Vectorized - O(N))
    jc = fvg_df['judas_classification']
    idx = fvg_df['bar_index']
    infl = np.where(jc == 'bullish_judas', fvg_df['high_offset_m'],
           np.where(jc == 'bearish_judas', fvg_df['low_offset_m'], np.nan))
    
    fvg_df['phase'] = np.where(np.isnan(infl), 'real_move_phase',
                      np.where(idx < infl - 1, 'judas_phase',
                      np.where(idx > infl + 1, 'real_move_phase', 'transition')))

    # Sequencing and Tags
    fvg_df['sequence_in_macro'] = fvg_df.groupby('macro_id').cumcount() + 1
    fvg_df['is_first_macro_fvg'] = fvg_df['sequence_in_macro'] == 1
    
    # is_first_presented: first FVG in real_move_phase that matches the real move direction
    # bullish_judas real move is DOWN (bearish FVG), bearish_judas real move is UP (bullish FVG)
    real_move_fvg_type = np.where(
        fvg_df['judas_classification'] == 'bullish_judas', 'bearish',
        np.where(fvg_df['judas_classification'] == 'bearish_judas', 'bullish', None)
    )
    is_aligned = fvg_df['fvg_type'] == real_move_fvg_type
    is_real_phase = fvg_df['phase'] == 'real_move_phase'
    
    # Vectorized group cumsum for aligned FVGs in real phase
    aligned_in_real = (is_aligned & is_real_phase)
    aligned_cumcount = aligned_in_real.groupby(fvg_df['macro_id']).cumsum()
    
    fvg_df['is_first_presented'] = (aligned_cumcount == 1) & aligned_in_real
    
    # Silver Bullet hours (10:00-11:00, 14:00-15:00)
    # DuckDB already provided fvg_timestamp in ET (naive)
    fvg_df['is_silver_bullet'] = fvg_df['fvg_timestamp'].dt.hour.isin([10, 14])
    
    # is_first_hour_fvg: FVG that forms immediately after an hourly mid_anchor_open
    fvg_df['is_first_hour_fvg'] = False
    fvg_df['is_first_30m_fvg'] = False
    if 'mid_anchor_open' in fvg_df.columns:
        # Check if FVG timestamp (the gap bar) is the hour open or 1m after
        fvg_df['is_first_hour_fvg'] = fvg_df['fvg_timestamp'].dt.minute.isin([0, 1])
        # Half-hour anchor (00 or 30)
        fvg_df['is_first_30m_fvg'] = fvg_df['fvg_timestamp'].dt.minute.isin([0, 1, 30, 31])
    
    return fvg_df
