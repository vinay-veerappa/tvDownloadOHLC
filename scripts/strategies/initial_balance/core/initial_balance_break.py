"""
IB Break Strategy with ICT Concepts (Vectorized ADR-017 Compliant)

This strategy implements Initial Balance (IB) breakout and pullback logic using
100% vectorized Pandas/NumPy operations for maximum backtest performance.
"""

import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
from typing import Dict, List, Optional, Any
from scripts.utils.vectorized_indicators import VectorizedIndicators

class IBBreakStrategy:
    """Initial Balance Break Strategy - ADR-017 Vectorized Version"""
    
    def __init__(
        self,
        ticker: str = "NQ1",
        ib_duration_minutes: int = 60,
        entry_variant: str = 'breakout',
        use_ict_fvg: bool = True,
        use_ict_killzones: bool = True,
        min_ib_range_pct: float = 0.02,
        max_ib_range_pct: float = 5.0,
        stop_loss_type: str = 'ib_opposite',
        take_profit_r_multiple: float = 2.0,
        entry_window_end: time = time(14, 0)
    ):
        self.ticker = ticker
        self.ib_duration_minutes = ib_duration_minutes
        self.entry_variant = entry_variant
        self.use_ict_fvg = use_ict_fvg
        self.use_ict_killzones = use_ict_killzones
        self.min_ib_range_pct = min_ib_range_pct
        self.max_ib_range_pct = max_ib_range_pct
        self.stop_loss_type = stop_loss_type
        self.take_profit_r_multiple = take_profit_r_multiple
        self.entry_window_end = entry_window_end
        
        self.output_cols = [
            'signal_time', 'direction', 'entry_price', 'stop_price', 
            'target1_price', 'ib_range_pct', 'expected_break', 'entry_type'
        ]

    def hunt(self, data: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Vectorized signal hunting method (ADR-017).
        """
        p = params or {}
        ib_dur = int(p.get('ib_duration_minutes', self.ib_duration_minutes))
        entry_var = p.get('entry_variant', self.entry_variant)
        min_range = p.get('min_ib_range_pct', self.min_ib_range_pct)
        max_range = p.get('max_ib_range_pct', self.max_ib_range_pct)
        tp_r = p.get('take_profit_r_multiple', self.take_profit_r_multiple)
        
        df = data.copy()
        df['date'] = df.index.normalize()
        df['time'] = df.index.time
        
        # 1. IB Boundary Calculation (Vectorized)
        ib_start = time(9, 30)
        ib_end_dt = datetime.combine(datetime.min, ib_start) + timedelta(minutes=ib_dur)
        ib_end = ib_end_dt.time()
        
        ib_mask = (df['time'] >= ib_start) & (df['time'] <= ib_end)
        ib_data = df[ib_mask]
        
        daily_ib_high = ib_data.groupby('date')['high'].max()
        daily_ib_low = ib_data.groupby('date')['low'].min()
        daily_ib_close = ib_data.groupby('date')['close'].last()
        
        df['ib_high'] = df['date'].map(daily_ib_high)
        df['ib_low'] = df['date'].map(daily_ib_low)
        df['ib_close'] = df['date'].map(daily_ib_close)
        
        # IB Range Stats
        df['ib_range'] = df['ib_high'] - df['ib_low']
        df['ib_range_pct'] = (df['ib_range'] / df['ib_low']) * 100
        
        # Expected Break (Bias)
        df['ib_pos'] = (df['ib_close'] - df['ib_low']) / df['ib_range']
        df['expected_break'] = np.where(df['ib_pos'] > 0.66, 'HIGH', 
                                       np.where(df['ib_pos'] < 0.33, 'LOW', 'CHOP'))
        
        # 2. Filtering Masks
        valid_range_mask = (df['ib_range_pct'] >= min_range) & (df['ib_range_pct'] <= max_range)
        after_ib_mask = df['time'] > ib_end
        before_end_mask = df['time'] <= self.entry_window_end
        
        # ICT Kill Zones
        if self.use_ict_killzones:
            kz_mask = (
                ((df['time'] >= time(8, 30)) & (df['time'] <= time(11, 0))) |
                ((df['time'] >= time(13, 30)) & (df['time'] <= time(16, 0)))
            )
        else:
            kz_mask = True
            
        # 3. Entry Triggers
        if entry_var == 'breakout':
            # Long Breakout
            long_trigger = (df['high'] > df['ib_high']) & (df['expected_break'] == 'HIGH')
            # Short Breakout
            short_trigger = (df['low'] < df['ib_low']) & (df['expected_break'] == 'LOW')
            entry_type = 'BREAKOUT'
        else:
            # Pullback logic (simplified vectorized version)
            # Requires FVG detection
            fvg = VectorizedIndicators.find_fvgs(df)
            df = pd.concat([df, fvg], axis=1)
            
            # Re-calculating IB high/low based on the actual break first
            # Simplified: entry on first FVG fill after price has pulsed outside IB
            df['has_pulsed_high'] = (df['high'] > df['ib_high']).groupby(df['date']).cummax()
            df['has_pulsed_low'] = (df['low'] < df['ib_low']).groupby(df['date']).cummax()
            
            long_trigger = df['has_pulsed_high'] & (df['fvg_type'] == 1) & (df['low'] <= df['fvg_top'])
            short_trigger = df['has_pulsed_low'] & (df['fvg_type'] == -1) & (df['high'] >= df['fvg_bottom'])
            entry_type = 'PULLBACK_FVG'

        # 4. Construct Signal DataFrame
        df['direction'] = np.nan
        df.loc[long_trigger & after_ib_mask & before_end_mask & valid_range_mask & kz_mask, 'direction'] = 'long'
        df.loc[short_trigger & after_ib_mask & before_end_mask & valid_range_mask & kz_mask, 'direction'] = 'short'
        
        signals = df[df['direction'].notnull()].copy()
        if signals.empty:
            return pd.DataFrame(columns=self.output_cols)
            
        # Select first signal per day
        signals = signals.groupby('date').head(1).copy()
        
        # 5. Risk Calculation (Vectorized)
        signals['signal_time'] = signals.index
        signals['entry_price'] = np.where(signals['direction'] == 'long', signals['ib_high'], signals['ib_low'])
        
        if self.stop_loss_type == 'ib_opposite':
            signals['stop_price'] = np.where(signals['direction'] == 'long', signals['ib_low'], signals['ib_high'])
        else:
            # Default to fixed 0.5% if not specified
            signals['stop_price'] = np.where(signals['direction'] == 'long', signals['entry_price'] * 0.995, signals['entry_price'] * 1.005)
            
        risk = (signals['entry_price'] - signals['stop_price']).abs()
        signals['target1_price'] = np.where(
            signals['direction'] == 'long',
            signals['entry_price'] + (risk * tp_r),
            signals['entry_price'] - (risk * tp_r)
        )
        
        signals['entry_type'] = entry_type
        
        return signals[self.output_cols].reset_index(drop=True)

    @staticmethod
    def get_param_grid() -> Dict[str, Any]:
        """Optimization grid for ADR-017 compliance"""
        return {
            'ib_duration_minutes': ('int', 15, 60),
            'take_profit_r_multiple': ('float', 1.0, 5.0),
            'min_ib_range_pct': ('float', 0.01, 0.1),
            'max_ib_range_pct': ('float', 1.0, 5.0)
        }
