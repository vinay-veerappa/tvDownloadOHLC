import pandas as pd
import numpy as np
import duckdb

def compute_post_macro_outcomes(macro_df: pd.DataFrame, bars_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Measures Continuation vs Reversion and MAE/MFE after each macro closes.
    Standard macros: look forward until next standard macro.
    Hydra macros: look forward 60 minutes.
    """
    if macro_df.empty or bars_1m.empty:
        return macro_df

    con = duckdb.connect(database=':memory:')
    
    # 1. Precompute Lookforward Windows
    temp_macros = macro_df[['macro_id', 'instrument', 'trading_date', 'macro_start', 'macro_end', 'open', 'high', 'low', 'close', 'judas_classification']].copy()
    temp_macros['macro_start_raw'] = temp_macros['macro_start'].dt.tz_localize(None)
    temp_macros['macro_end_raw'] = temp_macros['macro_end'].dt.tz_localize(None)
    
    # Sort for finding next macro
    temp_macros = temp_macros.sort_values(['instrument', 'macro_start'])
    temp_macros['next_macro_start'] = temp_macros.groupby('instrument')['macro_start_raw'].shift(-1)
    
    # Fallback for last macro: clip at 17:00 ET of the trading session
    # Note: trading_date is date-only at this point in most logic, but let's be safe
    # We construct 17:00 ET for that trading_date
    temp_macros['session_close'] = temp_macros['trading_date'].apply(
        lambda d: pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=17, minute=0)
    )
    
    # lookforward_end is the EARLIEST of: (next macro start) OR (17:00 ET) OR (macro_end + 60min)
    # USER RULE: 17:00 ET cutoff ONLY for RTH sessions. 
    # Asia/Overnight macros should NOT be clipped at 17:00 ET of the PRIOR trading Day.
    is_rth = temp_macros['macro_start'].dt.hour.between(9, 16)
    
    temp_macros['lookforward_end'] = np.where(
        temp_macros['next_macro_start'].isna(),
        temp_macros['macro_end_raw'] + pd.Timedelta(minutes=60),
        temp_macros['next_macro_start']
    )
    
    # Apply 17:00 ET cap ONLY to RTH macros
    temp_macros['lookforward_end'] = np.where(
        is_rth,
        np.minimum(temp_macros['lookforward_end'], temp_macros['session_close']),
        temp_macros['lookforward_end']
    )
    
    # Final clip: NO lookforward can CROSS 17:00 ET of the current trading_date
    temp_macros['lookforward_end'] = pd.to_datetime(temp_macros['lookforward_end'])
    
    # Calculate actual lookforward duration
    temp_macros['post_macro_duration_m'] = (
        (temp_macros['lookforward_end'] - temp_macros['macro_end_raw']).dt.total_seconds() / 60
    ).round(1)
    
    con.register('macros', temp_macros)
    
    # 2. Register Bars
    bars_reg = bars_1m.reset_index().rename(columns={'dt_et': 'bar_time'})
    bars_reg['bar_time'] = bars_reg['bar_time'].dt.tz_localize(None)
    con.register('bars', bars_reg)

    # 3. Aggregate post-macro outcomes (FROM MACRO CLOSE)
    con.execute("""
        CREATE TEMP TABLE post_outcomes AS
        WITH ordered_bars AS (
            SELECT 
                m.macro_id,
                b.high,
                b.low,
                b.close,
                b.bar_time,
                LAST_VALUE(b.close) OVER (PARTITION BY m.macro_id ORDER BY b.bar_time ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as final_c
            FROM macros m
            JOIN bars b ON b.bar_time > m.macro_end_raw AND b.bar_time <= m.lookforward_end
        )
        SELECT 
            macro_id,
            MAX(high) as post_h,
            MIN(low) as post_l,
            ANY_VALUE(final_c) as post_close
        FROM ordered_bars
        GROUP BY macro_id
    """)

    # 4. Aggregate macro-level MAE/MFE (FROM MACRO START - Includes intra-macro bars)
    con.execute("""
        CREATE TEMP TABLE macro_level_bounds AS
        SELECT 
            m.macro_id,
            MAX(b.high) as total_lookforward_h,
            MIN(b.low) as total_lookforward_l
        FROM macros m
        JOIN bars b ON b.bar_time >= m.macro_start_raw AND b.bar_time <= m.lookforward_end
        GROUP BY m.macro_id
    """)

    # 5. Mid Retest Tracking
    con.execute("""
        CREATE TEMP TABLE mid_retests AS
        WITH macro_mids AS (
            SELECT 
                macro_id,
                macro_start_raw,
                macro_end_raw,
                lookforward_end,
                (high + low) / 2 as macro_mid
            FROM macros
        ),
        retest_bars AS (
            SELECT 
                m.macro_id,
                b.bar_time,
                m.macro_mid,
                -- Retest is when price enters the 'mid' after the macro closes
                -- For bullish real direction (UP), retest is price dipping to mid
                -- For bearish real direction (DOWN), retest is price rising to mid
                -- We'll just track ANY touch of the mid for now
                (b.low <= m.macro_mid AND b.high >= m.macro_mid) as touches_mid
            FROM macro_mids m
            JOIN bars b ON b.bar_time > m.macro_end_raw AND b.bar_time <= m.lookforward_end
        )
        SELECT 
            macro_id,
            MAX(touches_mid::INT) > 0 as post_macro_retested_mid,
            MIN(CASE WHEN touches_mid THEN bar_time END) as first_mid_retest_time
        FROM retest_bars
        GROUP BY macro_id
    """)

    # 6. Post-Retest Price Extremes (FROM MID RETEST BAR to LOOKFORWARD END)
    con.execute("""
        CREATE TEMP TABLE mid_retest_outcomes AS
        WITH retest_bars AS (
            SELECT
                r.macro_id,
                b.high as bar_h,
                b.low  as bar_l,
                b.close as bar_c,
                b.bar_time,
                ROW_NUMBER() OVER (PARTITION BY r.macro_id ORDER BY b.bar_time DESC) as rn
            FROM mid_retests r
            JOIN macros m ON r.macro_id = m.macro_id
            JOIN bars b   ON b.bar_time >= r.first_mid_retest_time
                         AND b.bar_time <= m.lookforward_end
            WHERE r.post_macro_retested_mid = TRUE
        )
        SELECT
            macro_id,
            MAX(bar_h)                       as post_retest_high,
            MIN(bar_l)                       as post_retest_low,
            MAX(CASE WHEN rn = 1 THEN bar_c END) as post_retest_close,
            COUNT(*)                         as post_retest_bars
        FROM retest_bars
        GROUP BY macro_id
    """)

    outcomes = con.execute("SELECT * FROM post_outcomes").df()
    macro_bounds = con.execute("SELECT * FROM macro_level_bounds").df()
    retests = con.execute("SELECT * FROM mid_retests").df()
    retest_outcomes = con.execute("SELECT * FROM mid_retest_outcomes").df()
    
    # Merge outcomes AND the lookforward boundaries back to res_df
    res_df = macro_df.merge(outcomes, on='macro_id', how='left')
    res_df = res_df.merge(macro_bounds, on='macro_id', how='left')
    res_df = res_df.merge(retests, on='macro_id', how='left')
    res_df = res_df.merge(retest_outcomes, on='macro_id', how='left')
    res_df = res_df.merge(
        temp_macros[['macro_id', 'lookforward_end', 'post_macro_duration_m']], 
        on='macro_id', 
        how='left'
    )
    
    # 4. Continuation / Reversion logic
    # bullish_judas or trend_down -> Real Direction is DOWN
    # bearish_judas or trend_up -> Real Direction is UP
    
    res_df['real_direction'] = np.where(
        res_df['judas_classification'].isin(['bullish_judas', 'trend_down']), 'down',
        'up'
    )
    
    macro_open = res_df['open']
    macro_close = res_df['close']
    
    # Continuation
    res_df['post_macro_continuation_pct'] = np.where(
        res_df['real_direction'] == 'down', (macro_close - res_df['post_l']) / macro_open * 100,
        np.where(res_df['real_direction'] == 'up', (res_df['post_h'] - macro_close) / macro_open * 100, 0)
    ).clip(min=0)

    # Reversion
    res_df['post_macro_reversion_pct'] = np.where(
        res_df['real_direction'] == 'down', (res_df['post_h'] - macro_close) / macro_open * 100,
        np.where(res_df['real_direction'] == 'up', (macro_close - res_df['post_l']) / macro_open * 100, 0)
    ).clip(min=0)
    
    # Net Change
    res_df['post_macro_net_pct'] = (res_df['post_close'] - macro_close) / macro_open * 100
    
    # MFE / MAE (Measured from macro OPEN through full lookforward)
    res_df['post_macro_mfe_pct'] = np.where(
        res_df['real_direction'] == 'down', (macro_open - res_df['total_lookforward_l']) / macro_open * 100,
        np.where(res_df['real_direction'] == 'up', (res_df['total_lookforward_h'] - macro_open) / macro_open * 100, 0)
    ).clip(min=0)
    
    res_df['post_macro_mae_pct'] = np.where(
        res_df['real_direction'] == 'down', (res_df['total_lookforward_h'] - macro_open) / macro_open * 100,
        np.where(res_df['real_direction'] == 'up', (macro_open - res_df['total_lookforward_l']) / macro_open * 100, 0)
    ).clip(min=0)

    # 5. Position Relative to Macro Mid (Range-based per Design Spec)
    res_df['macro_mid'] = (res_df['high'] + res_df['low']) / 2
    res_df['close_vs_macro_mid_pct'] = (res_df['close'] - res_df['low']) / (res_df['high'] - res_df['low'] + 1e-9) * 100

    # 5b. Mid Retest Entry Analytics (Strategy 2 MFE/MAE from macro_mid entry)
    macro_mid = res_df['macro_mid']
    macro_open = res_df['open']
    mask_retested = res_df['post_macro_retested_mid'] == True

    # MFE: favorable move in real_direction from macro_mid entry
    res_df['mid_retest_mfe_pct'] = np.where(
        mask_retested & (res_df['real_direction'] == 'down'),
        (macro_mid - res_df['post_retest_low']) / macro_open * 100,
        np.where(
            mask_retested & (res_df['real_direction'] == 'up'),
            (res_df['post_retest_high'] - macro_mid) / macro_open * 100,
            np.nan,
        ),
    )
    res_df['mid_retest_mfe_pct'] = res_df['mid_retest_mfe_pct'].clip(lower=0)

    # MAE: adverse move against real_direction from macro_mid entry
    res_df['mid_retest_mae_pct'] = np.where(
        mask_retested & (res_df['real_direction'] == 'down'),
        (res_df['post_retest_high'] - macro_mid) / macro_open * 100,
        np.where(
            mask_retested & (res_df['real_direction'] == 'up'),
            (macro_mid - res_df['post_retest_low']) / macro_open * 100,
            np.nan,
        ),
    )
    res_df['mid_retest_mae_pct'] = res_df['mid_retest_mae_pct'].clip(lower=0)

    # Net P&L: signed, positive = profitable
    res_df['mid_retest_net_pct'] = np.where(
        mask_retested & (res_df['real_direction'] == 'down'),
        (macro_mid - res_df['post_retest_close']) / macro_open * 100,
        np.where(
            mask_retested & (res_df['real_direction'] == 'up'),
            (res_df['post_retest_close'] - macro_mid) / macro_open * 100,
            np.nan,
        ),
    )

    # Win boolean (NaN for non-retested rows)
    res_df['mid_retest_win'] = np.where(
        pd.notna(res_df['mid_retest_net_pct']),
        res_df['mid_retest_net_pct'] > 0,
        np.nan,
    )

    # R:R ratio
    res_df['mid_retest_rr'] = np.where(
        res_df['mid_retest_mae_pct'] > 0,
        (res_df['mid_retest_mfe_pct'] / res_df['mid_retest_mae_pct']).round(2),
        np.nan,
    )

    # 6. Final Retest Analysis
    # Data is already naive ET from DuckDB (we registered it as such). 
    # Just localize to ET directly.
    res_df['first_mid_retest_time'] = pd.to_datetime(res_df['first_mid_retest_time']).dt.tz_localize('US/Eastern')
    # Use localized macro_end but strip tz for the subtraction
    res_df['mid_retest_time_m'] = (res_df['first_mid_retest_time'].dt.tz_localize(None) - res_df['macro_end'].dt.tz_localize(None)).dt.total_seconds() / 60
    
    # Cleanup
    drop_cols = ['total_lookforward_h', 'total_lookforward_l', 'first_mid_retest_time', 'macro_mid']
    res_df = res_df.drop(columns=[c for c in drop_cols if c in res_df.columns])

    return res_df
