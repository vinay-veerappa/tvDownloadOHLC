import pandas as pd

def compute_sequences(macro_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes inter-macro relationships: prior macro fields and streaks.
    Input must be sorted by (instrument, trading_date, macro_start).
    """
    if macro_df.empty:
        return macro_df
    
    # Sort for shifting
    req_cols = ['instrument', 'trading_date', 'macro_start']
    res_df = macro_df.sort_values(req_cols).copy()
    
    # 1. Prior Macro Context
    # Group by instrument and trading_date to ensure we don't bleed across days
    grouped = res_df.groupby(['instrument', 'trading_date'])
    
    res_df['prior_macro_name'] = grouped['macro_name_raw'].shift(1)
    res_df['prior_macro_classification'] = grouped['judas_classification'].shift(1)
    res_df['prior_macro_real_direction'] = grouped['real_direction'].shift(1)
    
    # Prior Price Levels
    res_df['prior_macro_high'] = grouped['high'].shift(1)
    res_df['prior_macro_low'] = grouped['low'].shift(1)
    res_df['prior_macro_open'] = grouped['open'].shift(1)
    res_df['prior_macro_mid'] = (res_df['prior_macro_high'] + res_df['prior_macro_low']) / 2
    
    # Direction match
    res_df['same_direction_as_prior'] = (res_df['real_direction'] == res_df['prior_macro_real_direction']) & res_df['real_direction'].notna()
    
    # 2. Sequencing (Streaks)
    # Consecutive macros with same real move direction
    # a. identify direction change
    dir_changed = res_df['real_direction'] != res_df.groupby(['instrument', 'trading_date'])['real_direction'].shift(1)
    
    # b. cumsum to create groups of identical directions
    streak_groups = res_df.groupby(['instrument', 'trading_date'])['real_direction'].transform(
        lambda x: (x != x.shift(1)).cumsum()
    )
    
    # c. count within groups
    res_df['macro_streak'] = res_df.groupby(['instrument', 'trading_date', streak_groups]).cumcount() + 1
    
    # Reset streak if direction is None
    res_df.loc[res_df['real_direction'].isna(), 'macro_streak'] = 0
    
    return res_df
