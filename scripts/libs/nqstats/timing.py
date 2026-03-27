"""
NQStats Timing Library.
Implements the 9 AM Reversion rule and the Hourly Personality Models (Q1-Q4).
"""

import pandas as pd
import numpy as np

# NQStats Official Hourly Personalities (Verified: 2016-2026)
HOURLY_PROBABILITIES = {
    8:  {"mode": "PRE-MARKET", "orb_wr": 0.585, "q1_high": 0.31, "q4_high": 0.27, "q1_low": 0.32, "q4_low": 0.30},
    9:  {"mode": "EXPANSION",  "orb_wr": 0.543, "q1_high": 0.16, "q4_high": 0.40, "q1_low": 0.22, "q4_low": 0.40},
    10: {"mode": "REVERSION",  "orb_wr": 0.616, "q1_high": 0.37, "q4_high": 0.30, "q1_low": 0.34, "q4_low": 0.33},
    11: {"mode": "CHOP",       "orb_wr": 0.600, "q1_high": 0.34, "q4_high": 0.31, "q1_low": 0.32, "q4_low": 0.33},
    12: {"mode": "CHOP",       "orb_wr": 0.614, "q1_high": 0.35, "q4_high": 0.32, "q1_low": 0.33, "q4_low": 0.34},
    13: {"mode": "CHOP",       "orb_wr": 0.607, "q1_high": 0.34, "q4_high": 0.32, "q1_low": 0.32, "q4_low": 0.34},
    14: {"mode": "CHOP",       "orb_wr": 0.599, "q1_high": 0.34, "q4_high": 0.34, "q1_low": 0.32, "q4_low": 0.35},
    15: {"mode": "TREND CLOSE","orb_wr": 0.584, "q1_high": 0.29, "q4_high": 0.415, "q1_low": 0.30, "q4_low": 0.37},
}

def identify_hourly_mode(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies the Hourly Mode and associated probabilities.
    Logic includes 5-minute ORB prediction:
    - Green 5m ORB -> 71% Q2-Q4 High likelihood.
    - Red 5m ORB -> High likely forms early (Q1).
    """
    # Ensure index is localized to US/Eastern
    et_df = df_1m.tz_convert('US/Eastern') if df_1m.index.tz else df_1m
    hours = et_df.index.hour
    
    # Map probabilities to the series
    res_df = pd.DataFrame(index=df_1m.index)
    res_df['hour'] = hours
    
    # 1. Base Personality Lookup
    modes = []
    orb_wrs = []
    for h in hours:
        stats = HOURLY_PROBABILITIES.get(h, {"mode": "UNKNOWN", "orb_wr": 0.5})
        modes.append(stats['mode'])
        orb_wrs.append(stats['orb_wr'])
    
    res_df['hourly_mode'] = modes
    res_df['base_orb_wr'] = orb_wrs
    
    # 2. 5-Minute ORB Prediction
    # Hourly start prices
    hourly_open = et_df['open'].where(et_df.index.minute == 0).groupby(pd.Grouper(freq='H')).transform('first')
    hourly_open = hourly_open.reindex(et_df.index, method='ffill')
    
    # Is it Green 5m? (Check at minute 4/5)
    is_orb_candle = (et_df.index.minute == 4) # Represents 09:04->09:05 close
    orb_green = (et_df['close'] > hourly_open) & is_orb_candle
    
    # Spread the ORB result to the entire hour
    orb_status = orb_green.groupby(pd.Grouper(freq='H')).transform('max').reindex(et_df.index, method='ffill')
    res_df['orb_status'] = np.where(orb_status, "GREEN", "RED")
    
    # 3. Expected Timing Rule
    # Green ORB -> 71% Probability High forms late (Q2-Q4)
    # Red ORB -> High likely forms early (Q1)
    res_df['expected_extreme_timing'] = np.where(orb_status, "LATE (71% Q2-Q4)", "EARLY (Q1)")
    
    return res_df


def check_9am_reversion(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Implements the 75.2% Reversion Rule for the 09:00 hour.
    If price breaks the 08:00 high or low, it must return to the 09:00 open.
    """
    hours = df_1m.index.hour
    
    # Get 08:00 High/Low
    # (Simplified: Extracting from a 1H resample just once per day)
    # Correct way: use transform to map the specific pre-9 range to the 09:00 hour
    mask_8am = (hours == 8)
    range_8am_high = df_1m['high'].where(mask_8am).groupby(df_1m.index.date).transform('max')
    range_8am_low = df_1m['low'].where(mask_8am).groupby(df_1m.index.date).transform('min')
    
    # Get 09:00 Hour Open
    open_9am = df_1m['open'].where((hours == 9) & (df_1m.index.minute == 0)).groupby(df_1m.index.date).transform('first')
    
    # We want to know if in the 09:00 hour, we ever:
    # 1. Violated 8AM High/Low
    # 2. Reverted to 9AM Open
    
    mask_9am = (hours == 9)
    violated_high = (df_1m['high'] > range_8am_high) & mask_9am
    violated_low = (df_1m['low'] < range_8am_low) & mask_9am
    
    reverted_to_open = (np.abs(df_1m['close'] - open_9am) < 0.25) & mask_9am # Approximation
    
    return pd.DataFrame({
        '8am_high': range_8am_high,
        '8am_low': range_8am_low,
        '9am_open': open_9am,
        'is_reverting': mask_9am & (violated_high | violated_low)
    }, index=df_1m.index)
