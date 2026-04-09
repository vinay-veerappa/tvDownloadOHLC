import pandas as pd
import numpy as np
import duckdb

def enrich_context(macro_df: pd.DataFrame, bars_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Computes developing session levels and anchors for each macro using DuckDB.
    """
    if macro_df.empty or bars_1m.empty:
        return macro_df

    con = duckdb.connect(database=':memory:')
    con.execute("SET TimeZone='US/Eastern'")
    
    # Register bars and macros
    # Strip tz for DuckDB
    bars_reg = bars_1m.reset_index().copy()
    bars_reg['dt_et_raw'] = bars_reg['dt_et'].dt.tz_localize(None)
    con.register('bars_raw', bars_reg)
    
    macro_reg = macro_df.copy()
    macro_reg['macro_start_raw'] = macro_reg['macro_start'].dt.tz_localize(None)
    con.register('macro_summary', macro_reg)

    # 1. Compute specific anchors (Midnight, Globex, RTH Open)
    con.execute("""
        CREATE TEMP TABLE daily_anchors AS
        SELECT 
            trading_date,
            MAX(CASE WHEN hour_et = 0 AND minute_et = 0 THEN dt_et_raw END) as midnight_time,
            MAX(CASE WHEN hour_et = 0 AND minute_et = 0 THEN open END) as midnight_open_lvl,
            MAX(CASE WHEN hour_et = 18 AND minute_et = 0 THEN dt_et_raw END) as globex_time,
            MAX(CASE WHEN hour_et = 18 AND minute_et = 0 THEN open END) as globex_open_lvl,
            MAX(CASE WHEN hour_et = 9 AND minute_et = 30 THEN dt_et_raw END) as daily_open_time,
            MAX(CASE WHEN hour_et = 9 AND minute_et = 30 THEN open END) as daily_open_lvl,
            -- Overnight session anchors (18:00 to 09:30)
            MAX(CASE WHEN hour_et >= 18 OR hour_et < 9 OR (hour_et = 9 AND minute_et < 30) THEN high END) as htf_overnight_high,
            MIN(CASE WHEN hour_et >= 18 OR hour_et < 9 OR (hour_et = 9 AND minute_et < 30) THEN low END) as htf_overnight_low
        FROM bars_raw
        GROUP BY trading_date
    """)

    # 2. Optimized Session Enrichment (Cumulative High/Low)
    # We tag bars by session and compute running max/min
    # Asia: 18:00 (of prior trading date or current if early) to 00:00
    # London: 02:00 to 05:00
    # NY AM: 09:30 to 12:00
    con.execute("""
        CREATE TEMP TABLE session_bars AS
        SELECT 
            *,
            -- Asia: 18:00 to 00:00 (Next day 00:00 bar excluded)
            (hour_et >= 18) AS is_asia,
            -- London: 02:00 to 05:00
            (hour_et >= 2 AND hour_et < 5) AS is_london,
            -- NY AM: 09:30 to 12:00
            ((hour_et = 9 AND minute_et >= 30) OR (hour_et >= 10 AND hour_et < 12)) AS is_ny_am,
            
            -- Session Cumulative (O(N) vs correlated subqueries)
            MAX(CASE WHEN (hour_et >= 18) THEN high END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as asia_h_cum,
            MIN(CASE WHEN (hour_et >= 18) THEN low END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as asia_l_cum,
            
            MAX(CASE WHEN (hour_et >= 2 AND hour_et < 5) THEN high END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as london_h_cum,
            MIN(CASE WHEN (hour_et >= 2 AND hour_et < 5) THEN low END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as london_l_cum,
            
            MAX(CASE WHEN ((hour_et = 9 AND minute_et >= 30) OR (hour_et >= 10 AND hour_et < 12)) THEN high END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as ny_am_h_cum,
            MIN(CASE WHEN ((hour_et = 9 AND minute_et >= 30) OR (hour_et >= 10 AND hour_et < 12)) THEN low END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as ny_am_l_cum,
            
            -- Full Developing Day (Overnight + RTH)
            MAX(high) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as day_h_cum,
            MIN(low) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as day_l_cum,
            
            -- Corrected Prev Hour: Max/Min of previous 60 bars (excluding current)
            MAX(high) OVER (PARTITION BY trading_date ORDER BY dt_et_raw ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) as prev_h_60,
            MIN(low) OVER (PARTITION BY trading_date ORDER BY dt_et_raw ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) as prev_l_60,

            -- Mid Anchor Opens (Hourly for standard, 30m is common for Hydra)
            MAX(CASE WHEN minute_et = 0 THEN open END) OVER (PARTITION BY trading_date ORDER BY dt_et_raw) as hourly_open_cum
        FROM bars_raw
    """)

    # 3. Inside Macro Anchors (The :00 or :30 bar that falls INSIDE the macro window)
    con.execute("""
        CREATE TEMP TABLE inside_anchors AS
        SELECT 
            m.macro_id,
            MAX(CASE WHEN b.minute_et = 0 THEN b.open END) as inside_hour_open,
            MAX(CASE WHEN b.minute_et = 30 THEN b.open END) as inside_30m_open
        FROM macro_summary m
        JOIN bars_raw b ON b.dt_et_raw >= m.macro_start_raw AND b.dt_et_raw <= m.macro_end
        GROUP BY m.macro_id
    """)

    # 4. Join Macro to the Developing Context (Last Bar BEFORE Macro Start)
    con.execute("""
        CREATE TEMP TABLE macro_developing AS
        SELECT 
            m.macro_id,
            b.asia_h_cum as asia_h,
            b.asia_l_cum as asia_l,
            b.london_h_cum as london_h,
            b.london_l_cum as london_l,
            b.ny_am_h_cum as ny_am_h,
            b.ny_am_l_cum as ny_am_l,
            b.day_h_cum as developing_day_high,
            b.day_l_cum as developing_day_low,
            b.prev_h_60 as prev_hour_h,
            b.prev_l_60 as prev_hour_l,
            -- Preceding Anchor (Fallback)
            b.hourly_open_cum as prev_hour_open,
            MAX(CASE WHEN b.minute_et IN (0, 30) THEN b.open END) OVER (PARTITION BY b.trading_date ORDER BY b.dt_et_raw) as prev_30m_open,
            -- RTH Timing
            CASE 
                WHEN b.hour_et >= 9 AND (b.hour_et > 9 OR b.minute_et >= 30) 
                THEN (b.hour_et * 60 + b.minute_et) - (9 * 60 + 30)
                ELSE NULL 
            END as minutes_since_rth_open,
            CASE 
                WHEN b.hour_et < 17 
                THEN (17 * 60) - (b.hour_et * 60 + b.minute_et)
                ELSE NULL 
            END as minutes_to_rth_close
        FROM macro_summary m
        LEFT JOIN session_bars b 
          ON m.trading_date = b.trading_date 
          AND b.dt_et_raw = (SELECT MAX(dt_et_raw) FROM session_bars b2 
                             WHERE b2.trading_date = m.trading_date 
                             AND b2.dt_et_raw < m.macro_start_raw)
    """)

    # 4. Final Assembler
    final_query = """
    SELECT 
        m.*,
        a.midnight_time,
        a.midnight_open_lvl,
        a.globex_time,
        a.globex_open_lvl,
        a.daily_open_time,
        a.daily_open_lvl,
        a.htf_overnight_high as overnight_h,
        a.htf_overnight_low as overnight_l,
        (a.htf_overnight_high + a.htf_overnight_low) / 2 as overnight_mid,
        d.asia_h, d.asia_l,
        d.london_h, d.london_l,
        d.ny_am_h, d.ny_am_l,
        d.developing_day_high,
        d.developing_day_low,
        (d.developing_day_high + d.developing_day_low) / 2 as developing_day_mid,
        d.prev_hour_h, d.prev_hour_l,
        -- Mid Anchor: Preference for the open that falls INSIDE the macro (e.g. 10:00 inside Macro_0950)
        COALESCE(i.inside_hour_open, d.prev_hour_open) as mid_anchor_open,
        COALESCE(i.inside_30m_open, d.prev_30m_open) as mid_anchor_30m,
        d.minutes_since_rth_open,
        d.minutes_to_rth_close,
        CASE WHEN d.minutes_since_rth_open <= 30 THEN TRUE ELSE FALSE END as is_first_rth_macro,
        -- Last RTH macro: NY PM session logic
        CASE WHEN m.macro_start_raw >= (m.trading_date + INTERVAL 15 HOUR) AND m.macro_start_raw < (m.trading_date + INTERVAL 16 HOUR + INTERVAL 15 MINUTE) THEN TRUE ELSE FALSE END as ny_pm_potential
    FROM macro_summary m
    LEFT JOIN daily_anchors a ON m.trading_date = a.trading_date
    LEFT JOIN macro_developing d ON m.macro_id = d.macro_id
    LEFT JOIN inside_anchors i ON m.macro_id = i.macro_id
    """
    
    res_df = con.execute(final_query).df()
    
    # Standardize Dtypes to prevent MergeError (ns vs us)
    res_df['trading_date'] = pd.to_datetime(res_df['trading_date']).astype('datetime64[ns]')
    for col in ['midnight_time', 'globex_time', 'daily_open_time']:
        if col in res_df.columns:
            res_df[col] = pd.to_datetime(res_df[col]).astype('datetime64[ns]')

    # 5. High-Performance Relative Position Flags (Vectorized NumPy)
    res_df['macro_open_idx'] = res_df['open']
    
    def add_pct_flag(df, price_col, target_col, flag_name):
        if target_col in df.columns:
            mask = df[target_col].notna()
            df.loc[mask, flag_name] = np.where(df.loc[mask, price_col] > df.loc[mask, target_col], 'above', 'below')

    add_pct_flag(res_df, 'open', 'midnight_open_lvl', 'open_vs_midnight')
    add_pct_flag(res_df, 'open', 'daily_open_lvl', 'open_vs_daily_open')
    add_pct_flag(res_df, 'open', 'globex_open_lvl', 'open_vs_globex_open')
    
    # Session Mid-Points
    for s in ['asia', 'london', 'ny_am']:
        h_col, l_col = f'{s}_h', f'{s}_l'
        if h_col in res_df.columns and l_col in res_df.columns:
            mid_col = f'{s}_mid'
            res_df[mid_col] = (res_df[h_col] + res_df[l_col]) / 2
            add_pct_flag(res_df, 'open', mid_col, f'open_vs_{s}_mid')
            
    # Developing Day Mid
    add_pct_flag(res_df, 'open', 'developing_day_mid', 'open_vs_developing_day_mid')
    
    # Overnight Mid
    if 'overnight_mid' in res_df.columns:
        add_pct_flag(res_df, 'open', 'overnight_mid', 'open_vs_overnight_mid')
        
    # Prior Day Mid
    if 'pdh' in res_df.columns and 'pdl' in res_df.columns:
        res_df['pd_mid'] = (res_df['pdh'] + res_df['pdl']) / 2
        add_pct_flag(res_df, 'open', 'pd_mid', 'open_vs_prior_day_mid')

    # 6. Final Logic Flags (Vectorized)
    # is_last_rth_macro: group by date and find the last one that marked ny_pm_potential
    res_df['is_last_rth_macro'] = False
    ny_pm_sessions = res_df[res_df['ny_pm_potential'] == True]
    if not ny_pm_sessions.empty:
        last_ids = ny_pm_sessions.sort_values('macro_start').groupby('trading_date')['macro_id'].tail(1)
        res_df.loc[res_df['macro_id'].isin(last_ids), 'is_last_rth_macro'] = True

    # Cleanup
    drop_cols = ['macro_start_raw', 'macro_open_idx', 'pd_mid', 'ny_pm_potential']
    res_df = res_df.drop(columns=[c for c in drop_cols if c in res_df.columns])
    
    return res_df
