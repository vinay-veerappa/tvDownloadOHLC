"""
Macro Extractor — Sprint 1
==========================
Extracts macro windows from 1-minute OHLCV data and computes all Sprint 1 fields.

Architecture:
    - DuckDB for I/O, bar filtering, and OHLC aggregation (fast)
    - Pandas for classification logic and feature engineering (flexible)

Design Reference: MACRO_RESEARCH_PIPELINE_DESIGN.md
"""
import pandas as pd
import numpy as np
import duckdb
from .config import STANDARD_MACROS, HYDRA_MACROS, ICT_ALIASES, INSTRUMENTS
from .data_loader import load_bars_duckdb
from .pivots import calculate_pivots_multi
from .classifiers import (
    classify_judas_vectorized,
    classify_indicator_vectorized,
    classify_candle_type_vectorized,
)


def extract_macros_for_instrument(
    instrument: str,
    start_date: str = None,
    end_date: str = None,
    bars_in: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Full Sprint 1 extraction for a single instrument.

    Steps:
        1. Load 1m bars via DuckDB (UTC→ET, trading date assigned)
        2. Compute multi-scale pivots on the full 1m series
        3. DuckDB: aggregate bars into macro windows (OHLCV, timing, bars_above/below)
        4. DuckDB: refine extreme timing (LAST occurrence)
        5. Pandas: percentage fields, candle anatomy, classifications
        6. Pandas: volume phase split, judas_first, final cleanup
    """
    # ──────────────────────────────────────────────────────────────
    # 1. Load bars
    # ──────────────────────────────────────────────────────────────
    df_1m = bars_in if bars_in is not None else load_bars_duckdb(instrument, start_date, end_date)
    if df_1m.empty:
        return pd.DataFrame()

    # ──────────────────────────────────────────────────────────────
    # 2. Multi-scale pivots (5, 13, 21) on full 1m series
    # ──────────────────────────────────────────────────────────────
    print(f"  [{instrument}] Extractor: Calculating multi-scale pivots...")
    df_1m = calculate_pivots_multi(df_1m, lengths=[5, 13, 21])

    # ──────────────────────────────────────────────────────────────
    # 3. DuckDB: Macro window aggregation
    # ──────────────────────────────────────────────────────────────
    print(f"  [{instrument}] Extractor: Connecting to DuckDB...")
    con = duckdb.connect(database=':memory:')
    con.execute("SET TimeZone='US/Eastern'")

    # Prepare macro definitions
    all_macros = STANDARD_MACROS + HYDRA_MACROS
    macros_df = pd.DataFrame(
        [{'name': m[0], 'start_h': m[1], 'start_m': m[2], 'end_h': m[3], 'end_m': m[4]}
         for m in all_macros]
    )

    # Strip timezone for DuckDB registration (values are already ET)
    print(f"  [{instrument}] Extractor: Registering DataFrames with DuckDB...")
    df_reg = df_1m.reset_index().copy()
    df_reg['dt_et'] = df_reg['dt_et'].dt.tz_localize(None)
    con.register('bars', df_reg)
    con.register('macro_definitions', macros_df)

    # Materialize bar_assignments into a TEMP TABLE so it persists across execute() calls
    print(f"  [{instrument}] Extractor: Creating temp table bar_assignments...")
    con.execute("""
        CREATE TEMP TABLE bar_assignments AS 
        SELECT
            b.*,
            m.name AS macro_name_raw,
            TRUE AS is_in_macro
        FROM bars b
        JOIN macro_definitions m
        ON CASE
            -- Same hour: e.g., Hydra 8:20–8:40
            WHEN m.start_h = m.end_h THEN
                (b.hour_et = m.start_h
                 AND b.minute_et >= m.start_m
                 AND b.minute_et < m.end_m)
            -- Adjacent hour (standard case): e.g., 9:50–10:10
            WHEN m.end_h = (m.start_h + 1) % 24 THEN
                ((b.hour_et = m.start_h AND b.minute_et >= m.start_m)
                 OR (b.hour_et = m.end_h AND b.minute_et < m.end_m))
            -- Cross-midnight spanning >1 hour (shouldn't occur with 20-min windows, but defensive)
            ELSE FALSE
        END
    """)

    # Main aggregation query
    # Uses integer hour/minute comparison (not string) for correctness
    # Handles three cases: same-hour (Hydra), adjacent-hour (standard), cross-midnight
    print(f"  [{instrument}] Extractor: Running main aggregation query...")
    agg_query = """
    WITH active_macros AS (
        SELECT * FROM bar_assignments WHERE is_in_macro = TRUE
    ),
    -- Step A: Basic OHLCV aggregation per macro window
    macro_basics AS (
        SELECT
            trading_date,
            macro_name_raw,
            MIN(dt_et)                       AS macro_start,
            MAX(dt_et)                       AS macro_end,
            FIRST(open ORDER BY dt_et)       AS open,
            MAX(high)                        AS high,
            MIN(low)                         AS low,
            LAST(close ORDER BY dt_et)       AS close,
            SUM(volume)                      AS volume,
            COUNT(*)                         AS bar_count
        FROM active_macros
        GROUP BY trading_date, macro_name_raw
    ),
    -- Step B: Count bars above/below the macro open
    -- Requires joining back to individual bars with the computed macro open
    bars_vs_open AS (
        SELECT
            mb.trading_date,
            mb.macro_name_raw,
            SUM(CASE WHEN a.close > mb.open THEN 1 ELSE 0 END) AS bars_above_open,
            SUM(CASE WHEN a.close < mb.open THEN 1 ELSE 0 END) AS bars_below_open
        FROM active_macros a
        JOIN macro_basics mb
            ON a.trading_date = mb.trading_date
            AND a.macro_name_raw = mb.macro_name_raw
        GROUP BY mb.trading_date, mb.macro_name_raw
    ),
    -- Step C: Pivot values at macro start (first bar of each window)
    pivot_at_start AS (
        SELECT
            trading_date,
            macro_name_raw,
            FIRST(ph_5 ORDER BY dt_et)       AS ph_5,
            FIRST(pl_5 ORDER BY dt_et)       AS pl_5,
            FIRST(ph_13 ORDER BY dt_et)      AS ph_13,
            FIRST(pl_13 ORDER BY dt_et)      AS pl_13,
            FIRST(ph_21 ORDER BY dt_et)      AS ph_21,
            FIRST(pl_21 ORDER BY dt_et)      AS pl_21,
            FIRST(ph_5_age ORDER BY dt_et)   AS ph_5_age,
            FIRST(pl_5_age ORDER BY dt_et)   AS pl_5_age,
            FIRST(ph_13_age ORDER BY dt_et)  AS ph_13_age,
            FIRST(pl_13_age ORDER BY dt_et)  AS pl_13_age,
            FIRST(ph_21_age ORDER BY dt_et)  AS ph_21_age,
            FIRST(pl_21_age ORDER BY dt_et)  AS pl_21_age
        FROM active_macros
        GROUP BY trading_date, macro_name_raw
    )
    SELECT
        mb.trading_date,
        mb.macro_name_raw,
        mb.macro_start,
        mb.macro_end,
        mb.open,
        mb.high,
        mb.low,
        mb.close,
        mb.volume,
        mb.bar_count,
        bvo.bars_above_open,
        bvo.bars_below_open,
        p.ph_5, p.pl_5, p.ph_13, p.pl_13, p.ph_21, p.pl_21,
        p.ph_5_age, p.pl_5_age, p.ph_13_age, p.pl_13_age, p.ph_21_age, p.pl_21_age
    FROM macro_basics mb
    JOIN bars_vs_open bvo
        ON mb.trading_date = bvo.trading_date
        AND mb.macro_name_raw = bvo.macro_name_raw
    JOIN pivot_at_start p
        ON mb.trading_date = p.trading_date
        AND mb.macro_name_raw = p.macro_name_raw
    ORDER BY mb.trading_date, mb.macro_start
    """

    macro_df = con.execute(agg_query).df()
    if macro_df.empty:
        return macro_df

    # ──────────────────────────────────────────────────────────────
    # 4. DuckDB: Refine extreme timing (LAST occurrence per design spec)
    # ──────────────────────────────────────────────────────────────
    print(f"  [{instrument}] Extractor: Refining extreme timing...")
    con.register('macro_summary', macro_df)

    refine_query = """
    SELECT
        m.trading_date,
        m.macro_name_raw,
        MAX(CASE WHEN a.high = m.high THEN a.dt_et END) AS high_time_last,
        MAX(CASE WHEN a.low  = m.low  THEN a.dt_et END) AS low_time_last
    FROM macro_summary m
    JOIN (SELECT * FROM bar_assignments WHERE is_in_macro = TRUE) a
        ON m.trading_date = a.trading_date
        AND m.macro_name_raw = a.macro_name_raw
    GROUP BY m.trading_date, m.macro_name_raw
    """

    # bar_assignments is still available in the DuckDB session
    refined = con.execute(refine_query).df()
    macro_df = macro_df.merge(refined, on=['trading_date', 'macro_name_raw'], how='left')

    # ──────────────────────────────────────────────────────────────
    # 5. Pandas: Feature engineering
    # ──────────────────────────────────────────────────────────────

    # Ensure timestamps are proper datetime
    for col in ['macro_start', 'macro_end', 'high_time_last', 'low_time_last']:
        macro_df[col] = pd.to_datetime(macro_df[col])

    # --- Timing offsets (minutes into macro) ---
    macro_df['high_offset_m'] = (
        (macro_df['high_time_last'] - macro_df['macro_start'])
        .dt.total_seconds() / 60
    ).fillna(0).round().astype(int)

    macro_df['low_offset_m'] = (
        (macro_df['low_time_last'] - macro_df['macro_start'])
        .dt.total_seconds() / 60
    ).fillna(0).round().astype(int)

    # Cross-midnight fix: if offset is negative, add 24 hours worth of minutes
    macro_df['high_offset_m'] = macro_df['high_offset_m'].where(
        macro_df['high_offset_m'] >= 0,
        macro_df['high_offset_m'] + 1440
    )
    macro_df['low_offset_m'] = macro_df['low_offset_m'].where(
        macro_df['low_offset_m'] >= 0,
        macro_df['low_offset_m'] + 1440
    )

    # Extreme spread (time gap in minutes between high and low)
    macro_df['extreme_spread'] = (macro_df['high_offset_m'] - macro_df['low_offset_m']).abs()

    # --- Price-derived fields (all as % of macro_open) ---
    macro_open = macro_df['open']
    macro_high = macro_df['high']
    macro_low = macro_df['low']
    macro_close = macro_df['close']
    macro_range = macro_high - macro_low
    safe_range = macro_range.replace(0, np.nan)  # avoid divide-by-zero

    macro_df['macro_mid'] = (macro_high + macro_low) / 2
    macro_df['macro_range_pct'] = macro_range / macro_open * 100
    macro_df['excursion_above_pct'] = (macro_high - macro_open) / macro_open * 100
    macro_df['excursion_below_pct'] = (macro_open - macro_low) / macro_open * 100
    macro_df['close_vs_open_pct'] = (macro_close - macro_open) / macro_open * 100  # signed

    # --- Candle anatomy (as % of range) ---
    max_oc = macro_df[['open', 'close']].max(axis=1)
    min_oc = macro_df[['open', 'close']].min(axis=1)

    macro_df['macro_body_pct'] = ((macro_close - macro_open).abs() / safe_range * 100).fillna(0.0)
    macro_df['upper_wick_pct'] = ((macro_high - max_oc) / safe_range * 100).fillna(0.0)
    macro_df['lower_wick_pct'] = ((min_oc - macro_low) / safe_range * 100).fillna(0.0)

    # --- Day of week ---
    td = pd.to_datetime(macro_df['trading_date'])
    macro_df['day_of_week'] = td.dt.day_name()
    macro_df['day_of_week_int'] = td.dt.dayofweek  # 0=Mon, 4=Fri

    # ──────────────────────────────────────────────────────────────
    # 6. Classifications
    # ──────────────────────────────────────────────────────────────

    # Map ph_13 → prior_pivot_high for the indicator classifier
    macro_df['prior_pivot_high'] = macro_df['ph_13']
    macro_df['prior_pivot_low'] = macro_df['pl_13']

    macro_df = classify_judas_vectorized(macro_df)
    macro_df = classify_indicator_vectorized(macro_df)
    macro_df = classify_candle_type_vectorized(macro_df)

    # ──────────────────────────────────────────────────────────────
    # 7. Post-classification derived fields
    # ──────────────────────────────────────────────────────────────

    # judas_first: did the Judas extreme occur before the real move extreme?
    is_bull_judas = macro_df['judas_classification'] == 'bullish_judas'
    is_bear_judas = macro_df['judas_classification'] == 'bearish_judas'

    macro_df['judas_first'] = np.where(
        is_bull_judas, macro_df['high_offset_m'] < macro_df['low_offset_m'],
        np.where(
            is_bear_judas, macro_df['low_offset_m'] < macro_df['high_offset_m'],
            None
        )
    )

    # ──────────────────────────────────────────────────────────────
    # 8. Volume phase split (Judas phase vs Real move phase)
    #    Uses DuckDB to avoid the memory explosion of a full Pandas merge
    # ──────────────────────────────────────────────────────────────

    # Register the macro summary with classification and refined times
    vol_input = macro_df[['trading_date', 'macro_name_raw', 'macro_start', 'macro_end',
                          'high_time_last', 'low_time_last', 'judas_classification']].copy()
    # Strip tz for DuckDB
    for col in ['macro_start', 'macro_end', 'high_time_last', 'low_time_last']:
        vol_input[col] = pd.to_datetime(vol_input[col]).dt.tz_localize(None)
    con.register('vol_macros', vol_input)

    vol_query = """
    SELECT
        vm.trading_date,
        vm.macro_name_raw,
        SUM(CASE
            WHEN vm.judas_classification = 'bullish_judas'  AND a.dt_et <= vm.high_time_last THEN a.volume
            WHEN vm.judas_classification = 'bearish_judas'  AND a.dt_et <= vm.low_time_last  THEN a.volume
            ELSE 0
        END) AS judas_phase_volume,
        SUM(CASE
            WHEN vm.judas_classification = 'bullish_judas'  AND a.dt_et > vm.high_time_last THEN a.volume
            WHEN vm.judas_classification = 'bearish_judas'  AND a.dt_et > vm.low_time_last  THEN a.volume
            ELSE 0
        END) AS real_move_phase_volume
    FROM vol_macros vm
    JOIN (SELECT * FROM bar_assignments WHERE is_in_macro = TRUE) a
        ON vm.trading_date = a.trading_date
        AND vm.macro_name_raw = a.macro_name_raw
    GROUP BY vm.trading_date, vm.macro_name_raw
    """

    vol_df = con.execute(vol_query).df()
    macro_df = macro_df.merge(vol_df, on=['trading_date', 'macro_name_raw'], how='left')
    macro_df['judas_phase_volume'] = macro_df['judas_phase_volume'].fillna(0).astype(int)
    macro_df['real_move_phase_volume'] = macro_df['real_move_phase_volume'].fillna(0).astype(int)

    # Volume ratio
    macro_df['volume_ratio'] = np.where(
        macro_df['judas_phase_volume'] > 0,
        (macro_df['real_move_phase_volume'] / macro_df['judas_phase_volume']).round(2),
        np.nan
    )

    # ──────────────────────────────────────────────────────────────
    # 9. Final cleanup and output
    # ──────────────────────────────────────────────────────────────

    macro_df['is_complete'] = macro_df['bar_count'] >= 19  # 20 bars expected, allow 1 tolerance
    macro_df['instrument'] = INSTRUMENTS.get(instrument, instrument)
    macro_df['ict_alias'] = macro_df['macro_name_raw'].map(ICT_ALIASES)
    macro_df['macro_id'] = (
        macro_df['instrument'] + '_'
        + macro_df['trading_date'].astype(str) + '_'
        + macro_df['macro_name_raw']
    )

    # Select and order final columns
    final_cols = [
        # Identifiers
        'macro_id', 'trading_date', 'day_of_week', 'day_of_week_int',
        'instrument', 'macro_name_raw', 'ict_alias',
        'macro_start', 'macro_end',

        # Macro OHLCV
        'open', 'high', 'low', 'close', 'macro_mid', 'volume',

        # Timing
        'high_offset_m', 'low_offset_m', 'extreme_spread',

        # Percentage fields (% of macro_open)
        'macro_range_pct', 'excursion_above_pct', 'excursion_below_pct',
        'close_vs_open_pct',

        # Candle anatomy (% of range)
        'macro_body_pct', 'upper_wick_pct', 'lower_wick_pct',

        # Bar counts
        'bar_count', 'is_complete', 'bars_above_open', 'bars_below_open',

        # Judas classification
        'judas_classification', 'judas_extreme',
        'judas_magnitude_pct', 'real_move_magnitude_pct', 'judas_to_real_ratio',
        'judas_first',

        # Volume
        'judas_phase_volume', 'real_move_phase_volume', 'volume_ratio',

        # Indicator classification
        'indicator_label',
        'open_quartile', 'close_quartile',

        # Pivots (multi-scale)
        'ph_5', 'pl_5', 'ph_13', 'pl_13', 'ph_21', 'pl_21',
        'ph_5_age', 'pl_5_age', 'ph_13_age', 'pl_13_age', 'ph_21_age', 'pl_21_age',
    ]

    # Only include columns that actually exist (defensive)
    available_cols = [c for c in final_cols if c in macro_df.columns]
    return macro_df[available_cols]