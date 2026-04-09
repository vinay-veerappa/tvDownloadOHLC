import pandas as pd
import numpy as np
"""from .config import NEUTRAL_THRESHOLD
"""

def classify_judas_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    ICT Judas swings are defined by their relationship to the macro OPEN.
    """
    macro_open = df['open']
    macro_high = df['high']
    macro_low = df['low']
    macro_close = df['close']
    
    has_excursion_above = macro_high > macro_open
    has_excursion_below = macro_low < macro_open
    close_above = macro_close >= macro_open
    close_below = macro_close < macro_open
    
    """
    is_neutral = (macro_close - macro_open).abs() / macro_open * 100 < NEUTRAL_THRESHOLD
    """    
    classification = pd.Series("trend_up", index=df.index)

    
    bull_judas = close_below & has_excursion_above 
    bear_judas = close_above & has_excursion_below 
    trend_up = close_above & ~has_excursion_below 
    trend_down = close_below & ~has_excursion_above 
    
    classification = np.where(bull_judas, "bullish_judas", classification)
    classification = np.where(bear_judas, "bearish_judas", classification)
    classification = np.where(trend_up, "trend_up", classification)
    classification = np.where(trend_down, "trend_down", classification)
    
    df['judas_classification'] = classification
    
    # Judas extreme
    df['judas_extreme'] = np.where(
        classification == "bullish_judas", macro_high,
        np.where(classification == "bearish_judas", macro_low, np.nan)
    )
    
    # Magnitudes as % of macro_open
    df['judas_magnitude_pct'] = np.where(
        classification == "bullish_judas", 
        (macro_high - macro_open) / macro_open * 100,
        np.where(
            classification == "bearish_judas",
            (macro_open - macro_low) / macro_open * 100,
            0.0
        )
    )
    
    df['real_move_magnitude_pct'] = (macro_close - macro_open).abs() / macro_open * 100
    
    df['judas_to_real_ratio'] = np.where(
        df['real_move_magnitude_pct'] > 0,
        (df['judas_magnitude_pct'] / df['real_move_magnitude_pct']).round(2),
        np.nan
    )
    
    return df

def classify_indicator_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Indicator classification relative to prior pivots (Accum/Expansion/Manip).
    """
    # Note: Pivot logic requires prior_pivot_high/low from magnet enrichment (Sprint 2)
    # For Sprint 1, we use current macro high/low if pivots are missing
    macro_open = df['open']
    macro_high = df['high']
    macro_low = df['low']
    macro_close = df['close']
    
    pivot_high = df.get('prior_pivot_high', pd.Series(macro_high, index=df.index)).fillna(macro_high)
    pivot_low = df.get('prior_pivot_low', pd.Series(macro_low, index=df.index)).fillna(macro_low)
    
    broke_high = (macro_high > pivot_high)
    broke_low  = (macro_low < pivot_low)
    
    macro_range = (macro_high - macro_low).replace(0, 1e-9)
    macro_mid = (macro_high + macro_low) / 2
    q1_upper = macro_low + macro_range * 0.25
    q4_lower = macro_high - macro_range * 0.25
    
    open_in_bottom_q  = macro_open < q1_upper
    open_in_top_q     = macro_open > q4_lower
    close_in_bottom_q = macro_close < q1_upper
    close_in_top_q    = macro_close > q4_lower

    full_displacement = (open_in_bottom_q & close_in_top_q) | (open_in_top_q & close_in_bottom_q)
    crossed_mid = ((macro_open > macro_mid) & (macro_close < macro_mid)) | ((macro_open < macro_mid) & (macro_close > macro_mid))
                  
    label_case1 = np.where(full_displacement, "Expansion", "Manip")
    label_case2 = np.where(crossed_mid, "Accum", "Expansion")
    label_case3 = np.where(full_displacement, "Expansion", "Accum")
    
    final_label = np.where(broke_high & broke_low, label_case1,
                           np.where(broke_high | broke_low, label_case2, label_case3))
    
    df['indicator_label'] = final_label
    return df

def classify_candle_type_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds OHLC relationship metadata (quartiles) with zero-range guards.
    """
    macro_range = df['high'] - df['low']
    valid_range = np.where(macro_range > 0, macro_range, 1e-9)
    
    # Default to 2 (mid-point) for zero-range macros
    df['open_quartile'] = np.where(macro_range > 0, 
                                   (((df['open'] - df['low']) / valid_range) * 4).fillna(0).astype(int).clip(1, 4),
                                   2)
    df['close_quartile'] = np.where(macro_range > 0, 
                                    (((df['close'] - df['low']) / valid_range) * 4).fillna(0).astype(int).clip(1, 4),
                                    2)
    
    return df
