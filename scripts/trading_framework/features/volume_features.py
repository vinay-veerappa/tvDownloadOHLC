import pandas as pd
import numpy as np

# Layer 2: Feature Engineering — Volume Analysis Features.
# Focuses on participation levels and institutional flow.

def compute_volume_features(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Standardizes volume metrics across timeframes.
    1. volume_sma: Long-term average volume.
    2. volume_ratio: Current volume / SMA (above 1.0 = high participation).
    3. volume_trend: SMA(5)/SMA(20) — increasing or decreasing flow.
    """
    if 'volume' not in df.columns:
        return pd.DataFrame()
        
    v_sma = df['volume'].rolling(window=period).mean()
    v_ratio = df['volume'] / v_sma.replace(0, 0.0001)
    
    # Volume short-term vs long-term trend
    v_short = df['volume'].rolling(window=5).mean()
    v_trend = v_short / v_sma.replace(0, 0.0001)
    
    # Volume cumulative for the session (reset logic based on US hours)
    # Using 09:30 as the anchor for volume accumulation (Institutional Session)
    df_temp = df.copy()
    df_temp['date'] = df_temp.index.date
    # Find new day starts (simplification: every day is a session start)
    new_day = (df_temp['date'] != df_temp['date'].shift(1))
    cum_vol = df['volume'].groupby(new_day.cumsum()).cumsum()
    
    return pd.DataFrame({
        'volume_sma': v_sma,
        'volume_ratio': v_ratio,
        'volume_trend': v_trend,
        'session_cum_volume': cum_vol
    }, index=df.index)
