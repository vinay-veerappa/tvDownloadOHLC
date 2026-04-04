import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

class VectorizedIndicators:
    """
    High-performance technical indicators implemented as 100% vectorized 
    Pandas operations to adhere to ADR-009.
    """
    
    @staticmethod
    def find_fvgs(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect Fair Value Gaps (FVG) across the entire dataset without loops.
        
        Args:
            df: Standard OHLC DataFrame.
            
        Returns:
            DataFrame with 'fvg_type', 'fvg_top', and 'fvg_bottom' columns.
        """
        res = pd.DataFrame(index=df.index)
        
        # Shifted series for 3-bar comparison
        # Bar 1 (i-2), Bar 2 (i-1), Bar 3 (i)
        high_1 = df['high'].shift(2)
        low_1 = df['low'].shift(2)
        high_3 = df['high']
        low_3 = df['low']
        
        # 1. Bullish FVG: Bar 1 High < Bar 3 Low
        bull_mask = high_1 < low_3
        
        # 2. Bearish FVG: Bar 1 Low > Bar 3 High
        bear_mask = low_1 > high_3
        
        # Assign attributes (on Bar 3)
        res['fvg_type'] = 0
        res.loc[bull_mask, 'fvg_type'] = 1  # Bullish
        res.loc[bear_mask, 'fvg_type'] = -1 # Bearish
        
        # FVG Zone Boundaries
        res['fvg_top'] = np.nan
        res['fvg_bottom'] = np.nan
        
        # Bullish Zone: [High_1, Low_3]
        res.loc[bull_mask, 'fvg_top'] = low_3
        res.loc[bull_mask, 'fvg_bottom'] = high_1
        
        # Bearish Zone: [Low_1, High_3]
        res.loc[bear_mask, 'fvg_top'] = low_1
        res.loc[bear_mask, 'fvg_bottom'] = high_3
        
        return res

    @staticmethod
    def calculate_daily_fibs(df: pd.DataFrame, ib_high_col: str = 'ib_high', ib_low_col: str = 'ib_low') -> pd.DataFrame:
        """
        Calculate daily Fibonacci retracement zones in parallel.
        
        Args:
            df: DataFrame containing daily IB high/low (forward-filled).
            
        Returns:
            DataFrame with Fib 50% and 61.8% levels.
        """
        res = pd.DataFrame(index=df.index)
        
        ib_high = df[ib_high_col]
        ib_low = df[ib_low_col]
        ib_range = ib_high - ib_low
        
        # Bullish Pullback Levels (Retracing from High)
        res['fib_long_50'] = ib_high - (ib_range * 0.50)
        res['fib_long_618'] = ib_high - (ib_range * 0.618)
        
        # Bearish Pullback Levels (Retracing from Low)
        res['fib_short_50'] = ib_low + (ib_range * 0.50)
        res['fib_short_618'] = ib_low + (ib_range * 0.618)
        
        return res
