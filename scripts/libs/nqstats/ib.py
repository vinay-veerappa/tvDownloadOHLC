"""
NQStats Initial Balance (IB) Library.
Implements the 96.1% break rule and the 82.3% Midpoint Bias rule.
"""

import pandas as pd
import numpy as np

def calculate_ib_bias(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates the IB bias based on the 10:30 candle configuration.
    
    Rules implemented:
    - Midpoint Bias: If 10:30 Close > IB Mid -> Long Bias (82.3% High Break).
    - Session Status: 96.1% probability of breaking at least one side.
    """
    ib_high = sessions_df['ib_high']
    ib_low = sessions_df['ib_low']
    ib_close = sessions_df['ib_close']
    ib_mid = sessions_df['ib_mid']
    
    # 1. Determine Midpoint Orientation at 10:30
    # The 'sessions_df' columns are ffilled, so we check the 'ib_close' vs 'ib_mid'
    bias = np.where(ib_close > ib_mid, "LONG", "SHORT")
    bias_conf = np.where(ib_close > ib_mid, 0.823, 0.80) # Using 80% for short as a baseline
    
    # 2. Refined Catalyst: Low set before High?
    # We would need the 1m DF to check timing, but for now we'll use the midpoint rule.
    
    return pd.DataFrame({
        'ib_bias': bias,
        'ib_conviction': bias_conf,
        'ib_break_prob': 0.961
    }, index=sessions_df.index)

def check_ib_broken_vectorized(df_1m: pd.DataFrame, sessions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Checks if IB High or Low has been broken in the RTH session.
    """
    # Ensure US/Eastern for time-based masking
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    times = et_df.index.time
    
    rth_mask = (times >= pd.Timestamp("09:30").time()) & (times < pd.Timestamp("16:00").time())
    
    high_broken = (et_df['high'] > sessions_df['ib_high']) & rth_mask
    low_broken = (et_df['low'] < sessions_df['ib_low']) & rth_mask
    
    # Group by day to see if it EVER broke
    groups = df_1m.index.date
    day_high_broken = high_broken.groupby(groups).transform('max')
    day_low_broken = low_broken.groupby(groups).transform('max')
    
    return pd.DataFrame({
        'ib_high_broken': day_high_broken,
        'ib_low_broken': day_low_broken
    }, index=df_1m.index)
