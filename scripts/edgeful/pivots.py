import pandas as pd
import numpy as np


def _calculate_pivots_single(df: pd.DataFrame, length: int, suffix: str) -> pd.DataFrame:
    """
    Replicates TradingView's ta.pivothigh / ta.pivotlow for a single length.
    
    A pivot at index i requires high[i] (or low[i]) to be the extreme
    of the range [i-length, i+length]. It is confirmed at bar i+length.
    
    Produces columns: ph_{suffix}, pl_{suffix}, ph_{suffix}_age, pl_{suffix}_age
    All forward-filled after confirmation delay.
    """
    col_ph = f'ph_{suffix}'
    col_pl = f'pl_{suffix}'
    col_ph_age = f'ph_{suffix}_age'
    col_pl_age = f'pl_{suffix}_age'

    if len(df) < 2 * length + 1:
        df[col_ph] = np.nan
        df[col_pl] = np.nan
        df[col_ph_age] = np.nan
        df[col_pl_age] = np.nan
        return df

    window_size = 2 * length + 1

    # Pivot Highs: bar is the highest high in its centered window
    rolling_max = df['high'].rolling(window=window_size, center=True).max()
    is_ph = df['high'] == rolling_max

    # Pivot Lows: bar is the lowest low in its centered window
    rolling_min = df['low'].rolling(window=window_size, center=True).min()
    is_pl = df['low'] == rolling_min

    # Record pivot values at detection points
    ph_series = pd.Series(np.nan, index=df.index)
    pl_series = pd.Series(np.nan, index=df.index)
    ph_series[is_ph] = df['high'][is_ph]
    pl_series[is_pl] = df['low'][is_pl]

    # Shift by length to replicate confirmation delay, then forward-fill
    df[col_ph] = ph_series.shift(length).ffill()
    df[col_pl] = pl_series.shift(length).ffill()

    # Age: bars since the forward-filled value last changed
    ph_changed = df[col_ph] != df[col_ph].shift(1)
    df[col_ph_age] = df.groupby(ph_changed.cumsum()).cumcount()

    pl_changed = df[col_pl] != df[col_pl].shift(1)
    df[col_pl_age] = df.groupby(pl_changed.cumsum()).cumcount()

    return df


def calculate_pivots(df: pd.DataFrame, length: int = 13) -> pd.DataFrame:
    """
    Single-scale pivot calculation. Produces ph_13, pl_13, ph_13_age, pl_13_age.
    """
    return _calculate_pivots_single(df, length, str(length))


def calculate_pivots_multi(df: pd.DataFrame, lengths: list = None) -> pd.DataFrame:
    """
    Multi-scale pivot calculation.
    
    Default lengths: [5, 13, 21]
    Produces: ph_5, pl_5, ph_13, pl_13, ph_21, pl_21 (plus _age variants)
    """
    if lengths is None:
        lengths = [5, 13, 21]

    for length in lengths:
        df = _calculate_pivots_single(df, length, str(length))

    return df