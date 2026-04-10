import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
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

    # Post-test extremes: bars from first test bar to lookforward end, per FVG
    con.execute("""
        CREATE TEMP TABLE fvg_post_test AS
        WITH test_bar_times AS (
            SELECT
                fvg_id,
                fvg_type,
                fvg_high,
                fvg_low,
                MIN(CASE
                    WHEN (fvg_type = 'bullish' AND bar_l <= fvg_high)
                      OR (fvg_type = 'bearish' AND bar_h >= fvg_low)
                    THEN bar_time
                END) as test_bar_time
            FROM fvg_lookforward
            GROUP BY fvg_id, fvg_type, fvg_high, fvg_low
        ),
        post_retest_bars AS (
            SELECT
                t.fvg_id,
                t.fvg_type,
                l.bar_h,
                l.bar_l,
                l.bar_c,
                l.bar_time,
                ROW_NUMBER() OVER (PARTITION BY t.fvg_id ORDER BY l.bar_time DESC) as rn
            FROM test_bar_times t
            JOIN fvg_lookforward l ON t.fvg_id = l.fvg_id
                                  AND l.bar_time >= t.test_bar_time
            WHERE t.test_bar_time IS NOT NULL
        )
        SELECT
            fvg_id,
            MAX(bar_h)                           as post_test_high,
            MIN(bar_l)                           as post_test_low,
            MAX(CASE WHEN rn = 1 THEN bar_c END) as post_test_close
        FROM post_retest_bars
        GROUP BY fvg_id
    """)

    outcomes = con.execute("SELECT * FROM fvg_outcomes").df()
    post_test = con.execute("SELECT * FROM fvg_post_test").df()
    res_df = fvg_df.merge(outcomes, on='fvg_id', how='left')
    res_df = res_df.merge(post_test, on='fvg_id', how='left')
    
    # Held = tested but not failed
    res_df['held'] = (res_df['was_tested'] == True) & (res_df['failed'] == False)

    # FVG entry MFE/MAE from fvg_mid (consequent encroachment = 50% of gap)
    # NULL for untested FVGs (post_test columns are NaN via left join)
    fvg_mid = res_df['fvg_mid']
    denom = res_df['macro_open_lvl']

    res_df['fvg_entry_mfe_pct'] = np.where(
        res_df['fvg_type'] == 'bullish',
        (res_df['post_test_high'] - fvg_mid) / denom * 100,
        np.where(
            res_df['fvg_type'] == 'bearish',
            (fvg_mid - res_df['post_test_low']) / denom * 100,
            np.nan,
        ),
    )
    res_df['fvg_entry_mfe_pct'] = res_df['fvg_entry_mfe_pct'].clip(lower=0)

    res_df['fvg_entry_mae_pct'] = np.where(
        res_df['fvg_type'] == 'bullish',
        (fvg_mid - res_df['post_test_low']) / denom * 100,
        np.where(
            res_df['fvg_type'] == 'bearish',
            (res_df['post_test_high'] - fvg_mid) / denom * 100,
            np.nan,
        ),
    )
    res_df['fvg_entry_mae_pct'] = res_df['fvg_entry_mae_pct'].clip(lower=0)

    res_df['fvg_entry_net_pct'] = np.where(
        res_df['fvg_type'] == 'bullish',
        (res_df['post_test_close'] - fvg_mid) / denom * 100,
        np.where(
            res_df['fvg_type'] == 'bearish',
            (fvg_mid - res_df['post_test_close']) / denom * 100,
            np.nan,
        ),
    )

    res_df['fvg_entry_win'] = np.where(
        pd.notna(res_df['fvg_entry_net_pct']),
        res_df['fvg_entry_net_pct'] > 0,
        np.nan,
    )

    res_df['fvg_entry_rr'] = np.where(
        res_df['fvg_entry_mae_pct'] > 0,
        (res_df['fvg_entry_mfe_pct'] / res_df['fvg_entry_mae_pct']).round(2),
        np.nan,
    )

    return res_df
