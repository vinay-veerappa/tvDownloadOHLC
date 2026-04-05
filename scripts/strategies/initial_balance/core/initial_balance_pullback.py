import pandas as pd
import numpy as np
from datetime import time
from typing import Dict, List, Optional, Any
from scripts.utils.vectorized_indicators import VectorizedIndicators

class IBPullbackStrategy:
    """
    Unified IB Pullback Hunter (Vectorized).
    Implements ICT-style FVG and Fibonacci retracements within the IB range.
    
    Adheres to the STRATEGY_DESIGN_STANDARD.md.
    """
    
    def __init__(self, ticker: str = "NQ1", ib_duration_min: int = 45):
        self.ticker = ticker
        self.ib_duration_min = ib_duration_min
        self.output_cols = ['signal_time', 'direction', 'entry_price', 'stop_price', 'target1_price']
        
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method.
        
        Args:
            data: Standard OHLC DataFrame.
            params: Dictionary of overrides for optimization (Optuna).
            
        Returns:
            Signal DataFrame compliant with the Design Standard (Zero-Loop).
        """
        p = params or {}
        
        # 1. Pre-calculate Daily IB (Vectorized)
        data = data.copy()
        data['date'] = data.index.normalize()
        
        ib_start = time(9, 30)
        from datetime import datetime, timedelta
        ib_end = (datetime.combine(datetime.min, ib_start) + timedelta(minutes=self.ib_duration_min)).time()
        
        ib_window = data.between_time(ib_start, ib_end)
        ib_highs = ib_window.groupby('date')['high'].max()
        ib_lows = ib_window.groupby('date')['low'].min()
        
        # Join IB levels back to the main dataframe
        data['ib_high'] = data['date'].map(ib_highs)
        data['ib_low'] = data['date'].map(ib_lows)
        
        # 3. Define Bias (High first vs Low first in IB)
        ib_window = data.between_time(ib_start, ib_end).copy()
        ib_window['datetime'] = ib_window.index
        
        ib_high_times = ib_window.loc[ib_window['high'] == ib_window['ib_high']].groupby('date')['datetime'].first()
        ib_low_times = ib_window.loc[ib_window['low'] == ib_window['ib_low']].groupby('date')['datetime'].first()
        
        # 4. Map Bias back to data
        data['ib_high_time'] = data['date'].map(ib_high_times)
        data['ib_low_time'] = data['date'].map(ib_low_times)
        data['bias'] = np.where(data['ib_low_time'] < data['ib_high_time'], 'long', 'short')
        
        # 5. Vectorized Indicators (FVG & Fibonacci)
        fvg_df = VectorizedIndicators.find_fvgs(data)
        data = pd.concat([data, fvg_df], axis=1)
        
        fib_df = VectorizedIndicators.calculate_daily_fibs(data)
        data = pd.concat([data, fib_df], axis=1)
        
        # 6. Entry Window Mask (10:16 AM - 12:00 PM per USER REQUEST)
        window_mask = (data.index.time >= time(10, 16)) & (data.index.time <= time(12, 0))
        
        # 7. Pullback Trigger Logic (Zero-Loop)
        # Price must have been 'Above' Fib for Long, or 'Below' Fib for Short before retracing
        data['long_pulsed'] = (data['low'] > data['fib_long_50']).groupby(data['date']).cummax()
        data['short_pulsed'] = (data['high'] < data['fib_short_50']).groupby(data['date']).cummax()
        
        # Entry Masks
        long_mask = (
            window_mask & 
            (data['bias'] == 'long') &
            data['long_pulsed'] & 
            (data['low'] <= data['fib_long_50']) & 
            (data['low'] >= data['ib_low'])
        )
        
        short_mask = (
            window_mask & 
            (data['bias'] == 'short') &
            data['short_pulsed'] & 
            (data['high'] >= data['fib_short_50']) & 
            (data['high'] <= data['ib_high'])
        )
        
        # Filter for first entry per day (Zero-Loop Vectorized)
        long_signals = data[long_mask].copy()
        long_signals['direction'] = 'long'
        
        short_signals = data[short_mask].copy()
        short_signals['direction'] = 'short'
        
        combined = pd.concat([long_signals, short_signals]).sort_index()
        if combined.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        # Select first signal per day
        combined['date'] = combined.index.normalize()
        first_sigs = combined.groupby('date').head(1).copy()
        
        # 8. Optimized Synthesis (Zero-Loop)
        # Instead of for-loops, we use vectorized column operations
        first_sigs['signal_time'] = first_sigs.index
        first_sigs['entry_price'] = np.where(first_sigs['direction'] == 'long', first_sigs['fib_long_50'], first_sigs['fib_short_50'])
        first_sigs['stop_price'] = np.where(first_sigs['direction'] == 'long', first_sigs['ib_low'], first_sigs['ib_high'])
        
        risk = (first_sigs['entry_price'] - first_sigs['stop_price']).abs()
        tp_mult = p.get('tp_r_mult', 1.0)
        
        first_sigs['target1_price'] = np.where(
            first_sigs['direction'] == 'long',
            first_sigs['entry_price'] + (risk * tp_mult),
            first_sigs['entry_price'] - (risk * tp_mult)
        )
        
        # Final Schema Formatting
        return first_sigs[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """
        Returns the standard optimization grid for Optuna.
        Adheres to ADR-017 for strategy research.
        """
        return {
            'tp_r_mult': ('float', 0.5, 3.0),
            'ib_duration_min': ('int', 30, 60),
            # Add other relevant hunters parameters here
        }
