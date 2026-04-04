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
        
    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Main signal hunting method.
        
        Args:
            data: Standard OHLC DataFrame.
            params: Dictionary of overrides for optimization (Optuna).
            
        Returns:
            Signal DataFrame compliant with the Design Standard.
        """
        p = params or {}
        ticker = self.ticker
        
        # 1. Pre-calculate Daily IB (Vectorized)
        data = data.copy()
        data['date'] = data.index.normalize()
        
        ib_start = time(9, 30)
        ib_end = (pd.Timestamp.combine(pd.Timestamp.today(), ib_start) + pd.Timedelta(minutes=self.ib_duration_min)).time()
        
        ib_window = data.between_time(ib_start, ib_end)
        ib_highs = ib_window.groupby('date')['high'].max()
        ib_lows = ib_window.groupby('date')['low'].min()
        
        # Join IB levels back to the main dataframe
        data['ib_high'] = data['date'].map(ib_highs)
        data['ib_low'] = data['date'].map(ib_lows)
        data['ib_range'] = data['ib_high'] - data['ib_low']
        
        # 3. Define Bias (High first vs Low first in IB)
        # We need the time of the IB High and IB Low for bias
        # Re-slice ib_window to ensure it has the latest mapped columns
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
        
        # 4. Entry Window Mask (10:16 AM - 12:00 PM per USER REQUEST)
        window_mask = (data.index.time >= time(10, 16)) & (data.index.time <= time(12, 0))
        
        # 5. Pullback Trigger Logic (Touch-Based)
        # Price must have been 'Above' Fib for Long, or 'Below' Fib for Short before retracing
        # We calculate 'Has Pulsed Away' per day
        data['long_pulsed'] = (data['low'] > data['fib_long_50']).groupby(data['date']).cummax()
        data['short_pulsed'] = (data['high'] < data['fib_short_50']).groupby(data['date']).cummax()
        
        # Entry Masks
        long_entry_mask = (
            window_mask & 
            (data['bias'] == 'long') & # New: Bias Aware
            data['long_pulsed'] & 
            (data['low'] <= data['fib_long_50']) & 
            (data['low'] >= data['ib_low'])
        )
        
        short_entry_mask = (
            window_mask & 
            (data['bias'] == 'short') & # New: Bias Aware
            data['short_pulsed'] & 
            (data['high'] >= data['fib_short_50']) & 
            (data['high'] <= data['ib_high'])
        )
        
        # Filter for first entry per day
        long_signals = data[long_entry_mask].groupby('date').head(1)
        short_signals = data[short_entry_mask].groupby('date').head(1)
        
        # 6. Schema Synthesis
        signals = []
        
        # Long Signals
        for _, sig in long_signals.iterrows():
            entry_price = sig['fib_long_50']
            stop_price = sig['ib_low']
            risk = abs(entry_price - stop_price)
            
            signals.append({
                'signal_time': sig.name,
                'direction': 'long',
                'entry_price': entry_price,
                'stop_price': stop_price,
                'target1_price': entry_price + (risk * p.get('tp_r_mult', 1.0))
            })
            
        # Short Signals
        for _, sig in short_signals.iterrows():
            entry_price = sig['fib_short_50']
            stop_price = sig['ib_high']
            risk = abs(entry_price - stop_price)
            
            signals.append({
                'signal_time': sig.name,
                'direction': 'short',
                'entry_price': entry_price,
                'stop_price': stop_price,
                'target1_price': entry_price - (risk * p.get('tp_r_mult', 1.0))
            })
            
        return pd.DataFrame(signals).sort_values('signal_time') if signals else pd.DataFrame()
